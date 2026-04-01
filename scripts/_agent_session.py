"""Shared agent session infrastructure for Relay web console and CLI.

Provides BaseAgentSession — a reusable base class for AI-powered
conversational agents with streaming, tool execution, and SSE support.
Subclass and override start() + _on_response() for each agent type.

Also provides CliSession — a terminal-based session that prints to stdout,
reads from stdin, and auto-advances between steps via the step engine.

All tool execution and conversation management is delegated to AgentRuntime
(in _agent_runtime.py). This module handles surface-specific concerns:
SSE event emission, session state, and UI coordination.
"""

import os
import queue
import sys
import threading
import uuid

# Re-export from _agent_runtime for backward compatibility.
# Existing code that imports these from _agent_session will continue to work.
from _agent_runtime import (
    resolve_api_key,
    parse_service_catalog,
    build_tools,
    execute_tool,
    load_agent_def,
    load_all_agent_defs,
    AgentRuntime,
    HAS_ANTHROPIC,
)


class BaseAgentSession:
    """Base class for AI agent sessions with streaming and tool execution.

    Wraps AgentRuntime to provide SSE event emission and session management.

    Subclasses must implement:
        start() — load context, set system_prompt, init client, kick off first turn

    Subclasses may override:
        _on_response(text) — called after each AI response (for phase detection, etc.)
    """

    def __init__(self, cp_dir, repo_paths=None, include_write_tool=True, model=None):
        self.session_id = str(uuid.uuid4())[:8]
        self.cp_dir = cp_dir
        self.phase = "starting"
        self.wizard_step = 1
        self.status = "active"
        self.events = queue.Queue()
        self.history = []
        self._repo_paths = repo_paths or {}
        self._engine = None  # Optional StepEngine for deterministic workflows
        self._turn_lock = threading.Lock()

        # Runtime is created lazily in _init_client() once we have an API key.
        # Before that, we still need tools for the step engine.
        self._runtime = None
        self._system_prompt = None
        self._include_write_tool = include_write_tool
        self._model = model
        self._tools = build_tools(self._repo_paths, include_write=include_write_tool)

    @property
    def messages(self):
        """Proxy to runtime messages for backward compat."""
        if self._runtime:
            return self._runtime.messages
        return []

    @messages.setter
    def messages(self, value):
        if self._runtime:
            self._runtime.messages = value

    @property
    def system_prompt(self):
        if self._runtime:
            return self._runtime.system_prompt
        return self._system_prompt if hasattr(self, '_system_prompt') else None

    @system_prompt.setter
    def system_prompt(self, value):
        self._system_prompt = value
        if self._runtime:
            self._runtime.system_prompt = value

    def _init_client(self):
        """Initialize the AgentRuntime with API key. Returns error string or None."""
        if not HAS_ANTHROPIC:
            self._emit({"type": "error",
                        "text": "anthropic SDK not installed. Run: pip install anthropic"})
            self._emit(None)
            return "no_sdk"

        api_key = resolve_api_key(self.cp_dir)
        if not api_key:
            self._emit({"type": "error",
                        "text": "ANTHROPIC_API_KEY not set. Export it in your shell profile."})
            self._emit(None)
            return "no_key"

        # Create a minimal agent def for the runtime
        agent_def = {
            "name": "session",
            "description": "",
            "tools": "read-write" if self._include_write_tool else "read-only",
            "output": "markdown",
            "prompt": self._system_prompt or "",
        }
        self._runtime = AgentRuntime(
            agent_def, self.cp_dir, self._repo_paths, api_key,
            model=self._model)
        # Sync tools — the runtime built its own, but subclasses may have
        # modified self._tools (e.g. step engine adding complete_step)
        self._runtime.tools = self._tools
        if hasattr(self, '_system_prompt') and self._system_prompt:
            self._runtime.system_prompt = self._system_prompt
        return None

    def _emit(self, event):
        """Push an event to the SSE queue and record in history."""
        if event is not None:
            self.history.append(event)
        self.events.put(event)

    def _sanitize_messages(self):
        """Ensure every assistant tool_use block has a matching tool_result.

        Scans the message history and injects synthetic tool_results for any
        orphaned tool_use blocks. This prevents 400 errors from the API when
        the history is corrupted by exceptions, race conditions, or edge cases.
        """
        messages = self._runtime.messages if self._runtime else []
        i = 0
        while i < len(messages):
            msg = messages[i]
            if msg["role"] == "assistant":
                tool_use_ids = []
                for block in (msg.get("content") or []):
                    bid = getattr(block, "id", None) or (
                        block.get("id") if isinstance(block, dict) else None)
                    btype = getattr(block, "type", None) or (
                        block.get("type") if isinstance(block, dict) else None)
                    if btype == "tool_use" and bid:
                        tool_use_ids.append(bid)
                if tool_use_ids:
                    next_msg = (messages[i + 1]
                                if i + 1 < len(messages) else None)
                    existing_ids = set()
                    if (next_msg and next_msg["role"] == "user"
                            and isinstance(next_msg.get("content"), list)):
                        for block in next_msg["content"]:
                            if (isinstance(block, dict)
                                    and block.get("type") == "tool_result"):
                                existing_ids.add(block.get("tool_use_id"))
                    missing = [tid for tid in tool_use_ids
                               if tid not in existing_ids]
                    if missing:
                        results = [
                            {"type": "tool_result", "tool_use_id": tid,
                             "content": "Error: tool result was lost"}
                            for tid in missing
                        ]
                        if (next_msg and next_msg["role"] == "user"
                                and isinstance(next_msg.get("content"), list)):
                            next_msg["content"].extend(results)
                        else:
                            messages.insert(
                                i + 1, {"role": "user", "content": results})
            i += 1

    def _run_turn(self, user_message):
        """Run a conversation turn via AgentRuntime with SSE emission.

        Serialized via _turn_lock to prevent concurrent threads from
        interleaving messages (e.g. user input arriving while a tool
        loop or step transition is in progress).
        """
        with self._turn_lock:
            try:
                self._sanitize_messages()
                # Sync engine to runtime so tool calls go through it
                if self._runtime:
                    self._runtime.engine = self._engine
                    self._runtime.tools = self._tools

                def on_token(text):
                    self._emit({
                        "type": "token",
                        "text": text,
                        "phase": self.phase,
                        "step": self.wizard_step,
                    })

                def on_loading(text):
                    self._emit({
                        "type": "loading",
                        "text": text,
                        "phase": self.phase,
                        "step": self.wizard_step,
                    })

                response_text = self._runtime.run_turn(
                    user_message, on_token=on_token, on_loading=on_loading)

                if response_text:
                    self._emit({
                        "type": "message",
                        "text": response_text,
                        "phase": self.phase,
                        "step": self.wizard_step,
                    })
                self._on_response(response_text)

            except Exception as e:
                self._emit({"type": "error", "text": str(e)})

    def _on_response(self, text):
        """Hook called after each AI response. Override for phase detection, etc."""
        pass

    def _execute_tool(self, name, input_data):
        """Execute a tool call — delegates to AgentRuntime."""
        if self._runtime:
            return self._runtime.execute_tool(name, input_data)
        # Fallback for sessions that haven't initialized the runtime yet
        return execute_tool(
            name, input_data, self.cp_dir, self._repo_paths,
            engine=self._engine)

    def send_answer(self, text):
        """Send user input — runs the next conversation turn in a background thread."""
        if self.status != "active":
            self._emit({"type": "error", "text": "Session is no longer active"})
            return

        thread = threading.Thread(target=self._run_turn, args=(text,),
                                  daemon=True)
        thread.start()


# ── CLI Session ──────────────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"
CYAN = "\033[36m"
GREEN = "\033[32m"


class CliSession(BaseAgentSession):
    """Terminal-based session with streaming output and stdin input.

    Used by CLI workflows for auto-advancing step engine execution.
    Prints AI tokens to stdout, reads user input from stdin,
    and auto-advances between steps via the step engine.
    """

    def __init__(self, cp_dir, repo_paths=None, model=None):
        super().__init__(cp_dir=cp_dir, repo_paths=repo_paths,
                         include_write_tool=True, model=model)
        self._step_advanced = False

    def _emit(self, event):
        """Print to terminal instead of queueing SSE events."""
        if event is None:
            return
        super()._emit(event)  # Record in history for conversation context

        etype = event.get("type", "")
        if etype == "token":
            sys.stdout.write(event["text"])
            sys.stdout.flush()
        elif etype == "message":
            sys.stdout.write("\n\n")
            sys.stdout.flush()
        elif etype == "loading":
            text = event.get("text", "")
            sys.stdout.write(f"\n  {DIM}\u23f3 {text}{NC}\n")
            sys.stdout.flush()
        elif etype == "error":
            sys.stderr.write(f"\n  \u274c {event['text']}\n")
            sys.stderr.flush()

    def _on_response(self, text):
        """Check if step engine wants to advance after this turn."""
        if self._engine and self._engine.on_turn_end():
            self._step_advanced = True

    def run_workflow(self):
        """Run the full workflow, auto-advancing between steps.

        For interactive steps, reads user input from stdin.
        For autonomous steps, runs without user input.
        Auto-advances when complete_step tool is called or write_file completes.
        """
        while not self._engine.is_complete:
            step = self._engine.current_step
            if step is None or step.type == "no-ai":
                self._engine.advance()
                break

            # Print step banner
            print(f"\n  {BOLD}{CYAN}{self._engine.progress}{NC}")
            print(f"  {'\u2550' * 50}")

            self.system_prompt = self._engine.get_system_prompt()
            self._tools = self._engine.get_tools(
                build_tools(self._repo_paths))

            # Run the kickoff turn
            self._step_advanced = False
            kickoff = self._engine.get_kickoff_message()
            self._run_turn(kickoff)

            # Interactive steps: read stdin until step advances
            if step.type == "interactive":
                while not self._step_advanced:
                    try:
                        user_input = input(f"\n  {GREEN}>{NC} ")
                    except (EOFError, KeyboardInterrupt):
                        print()
                        break
                    if not user_input.strip():
                        continue
                    self._step_advanced = False
                    self._run_turn(user_input)

            # Advance to next step
            self._engine.advance()
