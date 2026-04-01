"""Unified agent runtime for Relay.

Consolidates tool execution, agent definition loading, and conversation
management into a single module. All execution surfaces (headless run-agent.py,
SSE-streaming serve.py, CLI terminal) delegate to this module.

Tool execution exists in ONE place — here.
"""

import os
import re
import subprocess
import time

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# ── API key & service catalog ───────────────────────────────────

def resolve_api_key(cp_dir):
    """Resolve Anthropic API key from env var or .relay-config command."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key

    config_path = os.path.join(cp_dir, ".relay-config")
    if os.path.exists(config_path):
        with open(config_path) as f:
            for line in f:
                m = re.match(r"^anthropic-api-key-cmd:\s*(.+)", line)
                if m:
                    cmd = m.group(1).strip()
                    try:
                        result = subprocess.run(
                            cmd, shell=True, capture_output=True, text=True,
                            timeout=10
                        )
                        if result.stdout.strip():
                            return result.stdout.strip()
                    except Exception:
                        pass
    return None


def parse_service_catalog(cp_dir):
    """Parse .relay/service-catalog.md and return dict of repo_name -> local_path."""
    catalog_path = os.path.join(cp_dir, ".relay", "service-catalog.md")
    if not os.path.exists(catalog_path):
        return {}, ""

    with open(catalog_path) as f:
        text = f.read()

    repo_paths = {}
    current_repo = None
    for line in text.split("\n"):
        m = re.match(r"^## (\S+)", line)
        if m:
            current_repo = m.group(1)
        elif current_repo:
            m = re.match(r"^- \*\*Local:\*\*\s*`?([^`]+)`?", line)
            if m:
                local_path = m.group(1).strip().rstrip("/")
                if os.path.isdir(local_path):
                    repo_paths[current_repo] = local_path

    return repo_paths, text


# ── Tool definitions ────────────────────────────────────────────

def build_tools(repo_paths, include_write=True):
    """Build the tool definitions list for Anthropic API.

    Args:
        repo_paths: dict of repo_name -> local_path
        include_write: if False, omits write_file tool (for read-only agents)
    """
    repo_names = list(repo_paths.keys())
    tools = []

    if include_write:
        tools.append({
            "name": "write_file",
            "description": "Write content to a file in the control plane.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path from the control plane root"},
                    "content": {"type": "string", "description": "Full file content to write"},
                },
                "required": ["path", "content"],
            },
        })

    tools.extend([
        {
            "name": "read_file",
            "description": "Read a file from the control plane.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path from the control plane root"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "read_repo_file",
            "description": "Read a file from a code repository.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": f"Repo short name. Available: {repo_names}"},
                    "path": {"type": "string", "description": "Relative file path within the repo"},
                },
                "required": ["repo", "path"],
            },
        },
        {
            "name": "list_directory",
            "description": "List files and directories in a code repository path.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": f"Repo short name. Available: {repo_names}"},
                    "path": {"type": "string", "description": "Relative directory path (use '' for repo root)"},
                },
                "required": ["repo"],
            },
        },
        {
            "name": "search_code",
            "description": "Search for a text pattern across files in a code repository.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": f"Repo short name. Available: {repo_names}"},
                    "pattern": {"type": "string", "description": "Search pattern (grep regex)"},
                    "glob": {"type": "string", "description": "Optional file glob filter, e.g. '*.ts' or '*.py'"},
                },
                "required": ["repo", "pattern"],
            },
        },
    ])

    return tools


# ── Tool execution (the ONE implementation) ─────────────────────

def _resolve_repo_path(repo_paths, repo, path=""):
    """Resolve a repo + relative path to an absolute path, with safety checks."""
    repo_root = repo_paths.get(repo)
    if not repo_root:
        return None, f"Unknown repo: {repo}. Available: {list(repo_paths.keys())}"
    full = os.path.join(repo_root, path) if path else repo_root
    if not os.path.realpath(full).startswith(os.path.realpath(repo_root)):
        return None, "Path traversal not allowed"
    return full, None


def execute_tool(name, input_data, cp_dir, repo_paths, engine=None):
    """Execute a tool call. This is the single canonical implementation.

    Args:
        name: tool name (write_file, read_file, read_repo_file, list_directory, search_code)
        input_data: tool input dict
        cp_dir: control plane directory path
        repo_paths: dict of repo_name -> local_path
        engine: optional StepEngine for intercepting complete_step and tracking writes
    """
    # Let the step engine intercept (e.g. complete_step tool)
    if engine:
        result = engine.handle_tool_call(name, input_data)
        if result is not None:
            return result

    if name == "write_file":
        path = input_data.get("path", "")
        content = input_data.get("content", "")
        full_path = os.path.join(cp_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        if engine:
            engine.notify_write_file()
        return f"File written successfully to {path}"

    elif name == "read_file":
        path = input_data.get("path", "")
        full_path = os.path.join(cp_dir, path)
        if os.path.isfile(full_path):
            with open(full_path) as f:
                content = f.read()
            if len(content) > 50000:
                return content[:50000] + "\n\n... (truncated at 50k chars)"
            return content
        return f"File not found: {path}"

    elif name == "read_repo_file":
        full, err = _resolve_repo_path(
            repo_paths, input_data.get("repo", ""), input_data.get("path", ""))
        if err:
            return err
        if os.path.isfile(full):
            with open(full) as f:
                content = f.read()
            if len(content) > 50000:
                return content[:50000] + "\n\n... (truncated at 50k chars)"
            return content
        return f"File not found: {input_data.get('path', '')}"

    elif name == "list_directory":
        full, err = _resolve_repo_path(
            repo_paths, input_data.get("repo", ""), input_data.get("path", ""))
        if err:
            return err
        if os.path.isdir(full):
            entries = sorted(os.listdir(full))
            result = []
            for e in entries[:200]:
                ep = os.path.join(full, e)
                prefix = "d " if os.path.isdir(ep) else "f "
                result.append(prefix + e)
            return "\n".join(result)
        return f"Directory not found: {input_data.get('path', '')}"

    elif name == "search_code":
        repo = input_data.get("repo", "")
        full, err = _resolve_repo_path(repo_paths, repo)
        if err:
            return err
        pattern = input_data.get("pattern", "")
        glob_filter = input_data.get("glob", "")
        cmd = ["grep", "-rn"]
        if glob_filter:
            cmd += ["--include", glob_filter]
        cmd += [pattern, full]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10)
            output = result.stdout
            if len(output) > 20000:
                output = output[:20000] + "\n\n... (truncated)"
            return output or "No matches found"
        except subprocess.TimeoutExpired:
            return "Search timed out"

    return f"Unknown tool: {name}"


# ── Agent definition loading ────────────────────────────────────

def load_agent_def(agent_type, relay_dir):
    """Load an agent definition from process/agents/<type>.md.

    Returns dict with keys: name, description, tools, output, prompt.
    Raises FileNotFoundError if agent type doesn't exist.
    """
    agents_dir = os.path.join(relay_dir, "process", "agents")
    fpath = os.path.join(agents_dir, f"{agent_type}.md")
    if not os.path.isfile(fpath):
        available = [f[:-3] for f in os.listdir(agents_dir)
                     if f.endswith(".md")]
        raise FileNotFoundError(
            f"Unknown agent type '{agent_type}'. Available: {available}")

    with open(fpath) as f:
        content = f.read()

    fm, body = {}, content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip()
            body = parts[2].strip()

    return {
        "name": fm.get("name", agent_type.title()),
        "description": fm.get("description", ""),
        "tools": fm.get("tools", "read-only"),
        "output": fm.get("output", "markdown"),
        "prompt": body,
    }


def load_all_agent_defs(relay_dir):
    """Load all agent definitions. Returns dict of type -> agent_def."""
    agents_dir = os.path.join(relay_dir, "process", "agents")
    defs = {}
    if not os.path.isdir(agents_dir):
        return defs
    for fname in sorted(os.listdir(agents_dir)):
        if fname.endswith(".md"):
            agent_type = fname[:-3]
            try:
                defs[agent_type] = load_agent_def(agent_type, relay_dir)
            except Exception:
                pass
    return defs


# ── AgentRuntime ────────────────────────────────────────────────

class AgentRuntime:
    """Unified execution core for all Relay agents.

    Surface-agnostic — has no knowledge of SSE, HTTP, or terminals.
    Uses callbacks for token streaming. All tool execution goes through
    the canonical execute_tool() function.

    Three execution methods:
      - run_headless()  — single-pass, no user interaction, returns result
      - run_turn()      — one conversation turn with streaming callbacks
      - execute_tool()  — delegate to the canonical implementation
    """

    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 8192

    def __init__(self, agent_def, cp_dir, repo_paths, api_key, model=None):
        self.agent_def = agent_def
        self.cp_dir = cp_dir
        self.repo_paths = repo_paths
        self.model = model or self.MODEL
        self.messages = []
        self.engine = None  # Optional StepEngine for orchestrated workflows
        self.custom_tool_handler = None  # Optional callback(name, input_data) -> str or None

        include_write = agent_def["tools"] == "read-write"
        self.tools = build_tools(repo_paths, include_write=include_write)
        self.system_prompt = agent_def["prompt"].replace(
            "{repos}", str(list(repo_paths.keys()) or "(none configured)"),
        )

        if not HAS_ANTHROPIC:
            raise ImportError("anthropic SDK not installed. Run: pip install anthropic")
        self.client = anthropic.Anthropic(api_key=api_key)

    def execute_tool(self, name, input_data):
        """Execute a tool call via the canonical implementation.

        Checks custom_tool_handler first (for session-specific tools like
        create_spec_brief), then falls through to the canonical executor.
        """
        if self.custom_tool_handler:
            result = self.custom_tool_handler(name, input_data)
            if result is not None:
                return result
        return execute_tool(
            name, input_data, self.cp_dir, self.repo_paths,
            engine=self.engine,
        )

    def run_headless(self, context):
        """Single-pass execution. No user interaction.

        Runs the conversation loop with tool use until the agent stops.
        Returns (final_text, input_tokens, output_tokens).
        """
        self.messages = [{"role": "user", "content": context}]
        all_text = ""
        total_input_tokens = 0
        total_output_tokens = 0

        for _ in range(30):  # safety cap
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.MAX_TOKENS,
                system=self.system_prompt,
                tools=self.tools,
                messages=self.messages,
            )

            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            text_parts = []
            tool_calls = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_calls.append(block)

            turn_text = "\n".join(text_parts)
            all_text += turn_text

            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                break

            # Execute tool calls
            tool_results = []
            for tc in tool_calls:
                try:
                    result = self.execute_tool(tc.name, tc.input)
                except Exception as exc:
                    result = f"Error executing {tc.name}: {exc}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result,
                })
            self.messages.append({"role": "user", "content": tool_results})

        return all_text, total_input_tokens, total_output_tokens

    def run_turn(self, user_message, on_token=None, on_loading=None):
        """Run one conversation turn with streaming.

        Surface-agnostic — uses callbacks for I/O:
          on_token(text)   — called for each streamed text delta
          on_loading(text) — called when entering a tool-use loop

        Returns the full response text for this turn.
        """
        self.messages.append({"role": "user", "content": user_message})
        is_tool_loop = False
        all_text = ""

        while True:
            response_text = ""

            with self.client.messages.stream(
                model=self.model,
                max_tokens=self.MAX_TOKENS,
                system=self.system_prompt,
                messages=self.messages,
                tools=self.tools,
            ) as stream:
                for event in stream:
                    if hasattr(event, 'type'):
                        if event.type == 'content_block_delta':
                            if hasattr(event.delta, 'text'):
                                response_text += event.delta.text
                                if not is_tool_loop and on_token:
                                    on_token(event.delta.text)

                final = stream.get_final_message()

            self.messages.append({"role": "assistant", "content": final.content})
            all_text += response_text

            if final.stop_reason == "tool_use":
                if not is_tool_loop:
                    is_tool_loop = True
                    if on_loading:
                        on_loading("Reading codebase...")
                tool_results = []
                for block in final.content:
                    if block.type == "tool_use":
                        try:
                            result = self.execute_tool(block.name, block.input)
                        except Exception as exc:
                            result = f"Error executing {block.name}: {exc}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                self.messages.append({"role": "user", "content": tool_results})
                continue

            return all_text
