#!/usr/bin/env python3
"""Relay Web Console — local HTTP server for browser-based workflows.

Serves the Command Center status page and exposes the relay new interview
workflow via a wizard UI with live AI chat.

Usage:
    relay serve [--port PORT] [--cp-dir DIR]
    python3 serve.py --cp-dir /path/to/control-plane [--port 7433]
"""

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# Add scripts dir to path so we can import _workflow
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import _workflow as wf
import _inbox_db
from _agent_session import (
    BaseAgentSession, resolve_api_key, parse_service_catalog, build_tools,
    HAS_ANTHROPIC,
)
from _agent_runtime import load_agent_def, load_all_agent_defs

# ── Globals ──────────────────────────────────────────────────────

CP_DIR = ""
RELAY_DIR = ""
SESSIONS = {}  # session_id -> InterviewSession
AGENT_PROCESSES = {}  # slug -> subprocess.Popen
INBOX_DB = None  # sqlite3.Connection, initialized in main()


# ── Repo sync ────────────────────────────────────────────────────

def sync_repos():
    """Pull control plane and fetch code repos to ensure fresh state.

    Returns a list of warning strings for any repos with dirty state or failed pulls.
    """
    warnings = []
    repo_paths, _ = parse_service_catalog(CP_DIR)

    # Sync control plane
    dirty = subprocess.run(
        ["git", "-C", CP_DIR, "status", "--porcelain"],
        capture_output=True, text=True, timeout=10
    )
    if dirty.stdout.strip():
        warnings.append("Control plane has uncommitted changes")
    pull = subprocess.run(
        ["git", "-C", CP_DIR, "pull", "--ff-only"],
        capture_output=True, text=True, timeout=15
    )
    if pull.returncode != 0:
        warnings.append(f"Control plane pull failed: {pull.stderr.strip()}")

    # Sync all code repos from service catalog
    for name, repo_path in repo_paths.items():
        if not os.path.isdir(repo_path):
            continue
        dirty = subprocess.run(
            ["git", "-C", repo_path, "status", "--porcelain"],
            capture_output=True, text=True, timeout=10
        )
        if dirty.stdout.strip():
            warnings.append(f"{name} has uncommitted changes")
        subprocess.run(
            ["git", "-C", repo_path, "pull", "--ff-only"],
            capture_output=True, timeout=15
        )

    return warnings


# ── CORS helper ──────────────────────────────────────────────────

def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


# ── Request handler ──────────────────────────────────────────────

class RelayHandler(BaseHTTPRequestHandler):
    """Routes requests to the appropriate handler."""

    def log_message(self, format, *args):
        """Quiet logging — single line per request."""
        sys.stderr.write(f"  {args[0]} {args[1]}\n")

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        for k, v in cors_headers().items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in cors_headers().items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/api/health":
            self._send_json({"status": "ok", "cp_dir": CP_DIR})

        elif path == "/":
            self._serve_status_page()

        elif path == "/interview":
            params = parse_qs(urlparse(self.path).query)
            from_chat = params.get("from", [None])[0]
            session_id = params.get("session", [None])[0]
            if from_chat == "chat" and session_id:
                # Serve the tailored handoff form for chat→interview escalation
                session = SESSIONS.get(session_id)
                brief = {}
                if session and hasattr(session, '_spec_brief') and session._spec_brief:
                    brief = session._spec_brief
                html = HANDOFF_HTML.replace(
                    "__BRIEF_JSON__", json.dumps(brief))
                html = html.replace("__SESSION_ID__", session_id or "")
                self._send_html(html)
            else:
                self._send_html(WIZARD_HTML)

        elif path == "/agents":
            self._send_html(AGENTS_HTML)

        elif path.startswith("/agent/"):
            agent_type = path.split("/agent/", 1)[1]
            agent_defs = load_all_agent_defs(RELAY_DIR)
            if agent_type in agent_defs:
                html = AGENT_HTML.replace("__AGENT_NAME__", agent_defs[agent_type]["name"])
                html = html.replace("__AGENT_TYPE__", agent_type)
                html = html.replace("__AGENT_DESC__", agent_defs[agent_type].get("description", ""))
                self._send_html(html)
            else:
                self._send_json({"error": f"Unknown agent type: {agent_type}"}, 404)

        elif path == "/api/agents":
            self._send_json(load_all_agent_defs(RELAY_DIR))

        elif path.startswith("/plan/"):
            slug = path.split("/plan/", 1)[1]
            self._send_html(PLAN_WIZARD_HTML.replace("__SLUG__", slug))

        elif path.startswith("/api/interview/") and path.endswith("/stream"):
            session_id = path.split("/")[3]
            self._handle_stream(session_id)

        elif path.startswith("/api/interview/") and path.endswith("/state"):
            session_id = path.split("/")[3]
            self._handle_state(session_id)

        elif path.startswith("/api/interview/") and path.endswith("/validate"):
            session_id = path.split("/")[3]
            self._handle_validate(session_id)

        elif path.startswith("/api/interview/") and path.endswith("/spec"):
            session_id = path.split("/")[3]
            self._handle_spec(session_id)

        # ── Inbox routes ─────────────────────────────────────────
        elif path == "/inbox":
            self._send_html(INBOX_HTML)

        elif path == "/api/inbox":
            params = parse_qs(urlparse(self.path).query)
            status_filter = params.get("status", [None])[0]
            self._send_json(_inbox_db.list_items(INBOX_DB, status=status_filter))

        elif re.match(r"^/api/inbox/\d+$", path):
            item_id = path.split("/")[-1]
            item = _inbox_db.get_item(INBOX_DB, item_id)
            if item:
                self._send_json(item)
            else:
                self._send_json({"error": "not found"}, 404)

        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")

        if path == "/api/interview/start":
            body = json.loads(self._read_body())
            self._handle_start(body)

        elif path == "/api/agent/start":
            body = json.loads(self._read_body())
            self._handle_agent_start(body)

        elif path == "/api/session/start":
            body = json.loads(self._read_body())
            self._handle_session_start(body)

        elif path == "/api/plan/start":
            body = json.loads(self._read_body())
            self._handle_plan_start(body)

        elif path.startswith("/api/interview/") and path.endswith("/answer"):
            session_id = path.split("/")[3]
            body = json.loads(self._read_body())
            self._handle_answer(session_id, body)

        elif path.startswith("/api/interview/") and path.endswith("/commit"):
            session_id = path.split("/")[3]
            self._handle_commit(session_id)

        elif path.startswith("/api/plan/") and path.endswith("/commit"):
            session_id = path.split("/")[3]
            self._handle_plan_commit(session_id)

        elif path == "/api/dispatch/local":
            body = json.loads(self._read_body())
            self._handle_local_dispatch(body)

        elif path == "/api/launch/terminal":
            body = json.loads(self._read_body())
            self._handle_launch_terminal(body)

        elif path == "/api/report/compliance":
            body = json.loads(self._read_body()) if self.headers.get("Content-Length", "0") != "0" else {}
            self._handle_compliance_report(body)

        # ── Inbox routes ─────────────────────────────────────────
        elif path == "/api/inbox":
            body = json.loads(self._read_body())
            self._handle_inbox_ingest(body)

        elif re.match(r"^/api/inbox/\d+/triage$", path):
            item_id = path.split("/")[3]
            self._handle_inbox_triage(item_id)

        elif re.match(r"^/api/inbox/\d+/triage-result$", path):
            item_id = path.split("/")[3]
            body = json.loads(self._read_body())
            self._handle_inbox_triage_result(item_id, body)

        elif re.match(r"^/api/inbox/\d+/promote$", path):
            item_id = path.split("/")[3]
            body = json.loads(self._read_body())
            self._handle_inbox_promote(item_id, body)

        elif re.match(r"^/api/inbox/\d+/dismiss$", path):
            item_id = path.split("/")[3]
            self._handle_inbox_dismiss(item_id)

        else:
            self._send_json({"error": "not found"}, 404)

    # ── Handlers ─────────────────────────────────────────────────

    def _serve_status_page(self):
        """Generate and serve the status page.

        Always regenerates from the CP's own script to a temp file to avoid
        dirtying the git working tree. Falls back to committed file if
        generation fails.
        """
        import tempfile
        # Try the CP's own copy first (synced via relay upgrade)
        cp_script = os.path.join(CP_DIR, ".github", "scripts",
                                  "generate-status-page.mjs")
        # Fall back to Relay's copy
        gen_script = cp_script if os.path.exists(cp_script) else os.path.join(
            RELAY_DIR, "process", "scripts", "generate-status-page.mjs")
        if os.path.exists(gen_script):
            tmp_output = os.path.join(tempfile.gettempdir(), "relay-status-page.html")
            result = subprocess.run(
                ["node", gen_script, "--cp-dir", CP_DIR,
                 "--output", tmp_output],
                capture_output=True, text=True
            )
            if result.returncode == 0 and os.path.exists(tmp_output):
                with open(tmp_output) as f:
                    self._send_html(f.read())
                return
        # Fall back to committed status page
        output_path = os.path.join(CP_DIR, "status-page", "index.html")
        if os.path.exists(output_path):
            with open(output_path) as f:
                self._send_html(f.read())
        else:
            self._send_html("<h1>Status page not generated yet. "
                           "Run generate-status-page.mjs first.</h1>", 500)

    def _handle_start(self, body):
        """Start a new interview session."""
        try:
            sync_warnings = sync_repos()
            idea = body.get("idea", "").strip()
            slug = body.get("slug", "").strip()
            execution = body.get("execution", "supervised")
            priority = body.get("priority", "medium")
            epic = body.get("epic", "")
            epic_title = body.get("epicTitle", "")
            total_budget = body.get("totalBudget", "")

            if not idea:
                self._send_json({"error": "idea is required"}, 400)
                return
            if not slug:
                slug = _slugify(idea)

            # Validate slug doesn't conflict
            for phase in ["draft", "active", "completed", "cancelled"]:
                candidate = os.path.join(CP_DIR, "features", phase,
                                         f"{slug}-feature.md")
                if os.path.exists(candidate):
                    self._send_json({
                        "error": f"Feature '{slug}' already exists in {phase}/"
                    }, 409)
                    return

            triage_context = body.get("triage_context", "").strip()
            inbox_id = body.get("inbox_id")

            session = InterviewSession(
                idea=idea, slug=slug, execution=execution,
                priority=priority, epic=epic, epic_title=epic_title,
                total_budget=total_budget, triage_context=triage_context,
                inbox_id=inbox_id,
            )
            SESSIONS[session.session_id] = session
            session.start()

            self._send_json({
                "sessionId": session.session_id,
                "slug": slug,
                "syncWarnings": sync_warnings,
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_stream(self, session_id):
        """SSE stream of AI messages. Replays history on reconnect."""
        session = SESSIONS.get(session_id)
        if not session:
            self._send_json({"error": "session not found"}, 404)
            return

        # Check how many events the client already has (for reconnect)
        params = parse_qs(urlparse(self.path).query)
        last_seen = int(params.get("lastSeen", ["0"])[0])

        self.send_response(200)
        for k, v in cors_headers().items():
            self.send_header(k, v)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        try:
            # Replay missed events from history (IDs are 1-indexed)
            for i, event in enumerate(session.history):
                event_id = i + 1
                if event_id <= last_seen:
                    continue
                data = json.dumps(event)
                self.wfile.write(
                    f"id: {i + 1}\n"
                    f"event: {event.get('type', 'message')}\n"
                    f"data: {data}\n\n".encode()
                )
            self.wfile.flush()

            # If session already complete, send done and stop
            if session.status == "complete":
                self.wfile.write(b"event: done\ndata: {}\n\n")
                self.wfile.flush()
                return

            # Stream new events as they arrive
            while True:
                try:
                    event = session.events.get(timeout=30)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue

                if event is None:
                    self.wfile.write(b"event: done\ndata: {}\n\n")
                    self.wfile.flush()
                    break

                event_id = len(session.history)
                data = json.dumps(event)
                self.wfile.write(
                    f"id: {event_id}\n"
                    f"event: {event.get('type', 'message')}\n"
                    f"data: {data}\n\n".encode()
                )
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _handle_answer(self, session_id, body):
        """Send user's answer to the AI session."""
        session = SESSIONS.get(session_id)
        if not session:
            self._send_json({"error": "session not found"}, 404)
            return

        text = body.get("text", "").strip()

        # Intercept /exit — trigger finalize instead of sending to AI
        if text.lower() in ("/exit", "exit", "/quit", "/done"):
            session.finalize()
            self._send_json({"ok": True, "finalized": True})
            return

        session._emit({"type": "user_message", "text": text})
        session.send_answer(text)
        self._send_json({"ok": True})

    def _handle_state(self, session_id):
        """Get current session state."""
        session = SESSIONS.get(session_id)
        if not session:
            self._send_json({"error": "session not found"}, 404)
            return

        self._send_json({
            "phase": session.phase,
            "step": session.wizard_step,
            "status": session.status,
            "slug": getattr(session, "slug", None),
        })

    def _handle_validate(self, session_id):
        """Run validation and return structured results."""
        session = SESSIONS.get(session_id)
        if not session:
            self._send_json({"error": "session not found"}, 404)
            return

        spec_path = os.path.join(CP_DIR, "features", "draft",
                                  f"{session.slug}-feature.md")
        if not os.path.exists(spec_path):
            self._send_json({"checks": []})
            return

        checks = []

        # Section checks
        required = ["Problem Statement", "Requirements",
                     "Acceptance Criteria", "Out of Scope", "Refinement Log"]
        ok, errors = wf.validate_sections(spec_path, required)
        checks.append({"label": "All required sections present",
                        "pass": ok, "errors": errors})

        # Readiness checklist
        ok, errors = wf.validate_readiness_checklist(spec_path)
        checks.append({"label": "Readiness checklist complete",
                        "pass": ok, "errors": errors})

        # Refinement counts
        with open(spec_path) as f:
            content = f.read()

        for label, pattern, minimum in [
            ("Assumptions challenged", r"^\|\s*A\d+", 3),
            ("Edge cases addressed", r"^\|\s*E\d+", 3),
            ("Scope boundaries probed", r"^\|\s*B\d+", 1),
            ("Architecture implications reviewed", r"^\|\s*AR\d+", 2),
            ("PII/compliance elements reviewed", r"^\|\s*P\d+", 1),
            ("UX/interaction concerns reviewed", r"^\|\s*UX\d+", 2),
        ]:
            count = len(re.findall(pattern, content, re.MULTILINE))
            checks.append({
                "label": f"{label}: {count}",
                "pass": count >= minimum,
                "errors": [] if count >= minimum else [
                    f"Only {count} (recommend >= {minimum})"
                ],
            })

        self._send_json({"checks": checks})

    def _handle_spec(self, session_id):
        """Get the current spec file contents."""
        session = SESSIONS.get(session_id)
        if not session:
            self._send_json({"error": "session not found"}, 404)
            return

        spec_path = os.path.join(CP_DIR, "features", "draft",
                                  f"{session.slug}-feature.md")
        if os.path.exists(spec_path):
            with open(spec_path) as f:
                self._send_json({"content": f.read(), "path": spec_path})
        else:
            self._send_json({"content": None, "path": spec_path})

    def _handle_commit(self, session_id):
        """Commit the spec and run validation."""
        session = SESSIONS.get(session_id)
        if not session:
            self._send_json({"error": "session not found"}, 404)
            return

        spec_path = os.path.join(CP_DIR, "features", "draft",
                                  f"{session.slug}-feature.md")

        if not os.path.exists(spec_path):
            self._send_json({"error": "Spec file not found"}, 404)
            return

        try:
            # Import spec module for validation
            import importlib.util
            spec_mod_path = os.path.join(SCRIPT_DIR, "spec.py")
            loader = importlib.util.spec_from_file_location(
                "spec_mod", spec_mod_path)
            spec_mod = importlib.util.module_from_spec(loader)
            loader.loader.exec_module(spec_mod)

            # Validate
            spec_mod.validate_spec(spec_path)

            # Merge all frontmatter blocks into one, then write
            with open(spec_path) as f:
                raw = f.read()
            # Parse ALL --- blocks and merge fields
            all_fields = {}
            for block_match in re.finditer(r"^---\s*\n(.*?)\n---", raw,
                                            re.DOTALL | re.MULTILINE):
                for line in block_match.group(1).split("\n"):
                    kv = re.match(r"^(\S+):\s*(.*)", line)
                    if kv:
                        key = kv.group(1)
                        val = kv.group(2).strip()
                        # Strip inline comments
                        val = re.sub(r"\s+#.*$", "", val)
                        if val:
                            all_fields[key] = val
            # Strip all --- blocks and comments between them from the body
            body = re.sub(
                r"^---\s*\n.*?\n---\s*\n?(?:<!--.*?-->\s*\n?)?",
                "", raw, flags=re.DOTALL | re.MULTILINE
            ).lstrip("\n")
            # Apply our overrides
            all_fields["execution"] = session.execution
            all_fields["priority"] = session.priority
            if session.epic:
                all_fields["epic"] = session.epic
            if session.epic_title:
                all_fields["epic-title"] = session.epic_title
            if session.total_budget:
                all_fields["total-budget"] = session.total_budget
            # Write clean single frontmatter block + body
            fm_lines = ["---"]
            for k, v in all_fields.items():
                fm_lines.append(f"{k}: {v}")
            fm_lines.append("---\n")
            with open(spec_path, "w") as f:
                f.write("\n".join(fm_lines) + body)

            # Git commit
            spec_rel = os.path.relpath(spec_path, CP_DIR)
            subprocess.run(
                ["git", "-C", CP_DIR, "add", spec_rel],
                capture_output=True
            )
            contract_path = os.path.join(CP_DIR, "contracts", "tasks-api.json")
            if os.path.exists(contract_path):
                subprocess.run(
                    ["git", "-C", CP_DIR, "add", "contracts/"],
                    capture_output=True
                )

            commit_msg = f"feat: feature spec for {session.slug}"
            result = subprocess.run(
                ["git", "-C", CP_DIR, "commit", "-m", commit_msg],
                capture_output=True, text=True
            )

            committed = result.returncode == 0
            pushed = False
            if committed:
                push_result = subprocess.run(
                    ["git", "-C", CP_DIR, "push"],
                    capture_output=True, text=True
                )
                pushed = push_result.returncode == 0
            self._send_json({
                "committed": committed,
                "pushed": pushed,
                "message": commit_msg if committed else "Nothing to commit",
                "specPath": spec_rel,
            })

        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_agent_start(self, body):
        """Start a generic agent session."""
        try:
            sync_repos()
            agent_type = body.get("type", "").strip()
            context = body.get("context", "").strip() or None
            if not agent_type:
                self._send_json({"error": "type is required"}, 400)
                return
            try:
                session = AgentSession(agent_type=agent_type, context=context)
            except ValueError as e:
                self._send_json({"error": str(e)}, 404)
                return
            SESSIONS[session.session_id] = session
            session.start()
            self._send_json({"sessionId": session.session_id})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_session_start(self, body):
        """Unified session start — POST /api/session/start.

        Accepts: {type: str, mode: "interactive"|"headless", context: str}
        - mode "interactive": creates an AgentSession (SSE-streamed)
        - mode "headless": spawns run-agent.py as a subprocess
        """
        try:
            agent_type = body.get("type", "").strip()
            mode = body.get("mode", "interactive").strip()
            context = body.get("context", "").strip() or None

            if not agent_type:
                self._send_json({"error": "type is required"}, 400)
                return

            if mode == "headless":
                # Spawn run-agent.py as subprocess
                import platform
                context_json = json.dumps(body.get("context", ""))
                callback_url = body.get("callback_url", "")
                cmd_parts = [
                    sys.executable,
                    os.path.join(SCRIPT_DIR, "run-agent.py"),
                    "--agent-type", agent_type,
                    "--context", context_json,
                    "--cp-dir", os.path.abspath(CP_DIR),
                ]
                if callback_url:
                    cmd_parts += ["--callback-url", callback_url]
                try:
                    proc = subprocess.Popen(
                        cmd_parts, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    self._send_json({
                        "mode": "headless", "pid": proc.pid, "type": agent_type})
                except Exception as e:
                    self._send_json({"error": str(e)}, 500)
                return

            # Interactive mode — create agent session
            sync_repos()
            try:
                session = AgentSession(agent_type=agent_type, context=context)
            except ValueError as e:
                self._send_json({"error": str(e)}, 404)
                return
            SESSIONS[session.session_id] = session
            session.start()
            self._send_json({"sessionId": session.session_id, "mode": "interactive"})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_plan_start(self, body):
        """Start a planning session for a draft feature."""
        try:
            sync_repos()
            slug = body.get("slug", "").strip()
            if not slug:
                self._send_json({"error": "slug is required"}, 400)
                return

            # Find the feature spec
            spec_path = None
            for phase in ["draft", "active"]:
                for suffix in ["-feature.md", "-bug.md"]:
                    candidate = os.path.join(CP_DIR, "features", phase,
                                             f"{slug}{suffix}")
                    if os.path.exists(candidate):
                        spec_path = candidate
                        break
                if spec_path:
                    break

            if not spec_path:
                self._send_json({"error": f"No spec found for '{slug}'"}, 404)
                return

            session = PlanningSession(slug=slug, spec_path=spec_path)
            SESSIONS[session.session_id] = session
            session.start()

            self._send_json({
                "sessionId": session.session_id,
                "slug": slug,
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_plan_commit(self, session_id):
        """Process decomposition, write task files, move draft→active, commit+push."""
        session = SESSIONS.get(session_id)
        if not session:
            self._send_json({"error": "session not found"}, 404)
            return

        try:
            # Import plan.py functions
            import importlib.util
            plan_mod_path = os.path.join(SCRIPT_DIR, "plan.py")
            loader = importlib.util.spec_from_file_location(
                "plan_mod", plan_mod_path)
            plan_mod = importlib.util.module_from_spec(loader)
            loader.loader.exec_module(plan_mod)

            slug = session.slug
            output_file = os.path.join(CP_DIR, "queue", slug,
                                        "_decomposition.json")

            # Parse decomposition JSON
            if not os.path.exists(output_file):
                self._send_json({"error": "Decomposition file not found"}, 404)
                return

            with open(output_file) as f:
                raw = f.read()

            decomposition = plan_mod.parse_agent_response(raw)
            if not decomposition or not decomposition.get("tasks"):
                self._send_json({"error": "Could not parse decomposition"}, 400)
                return

            tasks = decomposition["tasks"]

            # Write contract diff if present
            contract_diff = decomposition.get("contract_diff")
            if contract_diff:
                contract_filename = contract_diff.get("filename", "contracts/api.json")
                contract_content = contract_diff.get("content")
                if contract_content:
                    contract_path = os.path.join(CP_DIR, contract_filename)
                    os.makedirs(os.path.dirname(contract_path), exist_ok=True)
                    import json as json_mod
                    with open(contract_path, "w") as f:
                        json_mod.dump(contract_content, f, indent=2)
                        f.write("\n")

            # Write task queue files
            template_path = os.path.join(RELAY_DIR, "process", "templates",
                                          "task-queue-item.md")
            fm = wf.parse_frontmatter(session.spec_path)
            execution_mode = fm.get("execution", "supervised")
            spec_is_bug = session.spec_path.endswith("-bug.md")

            created_files = plan_mod.write_task_files(
                CP_DIR, slug, tasks, template_path,
                feature_execution_mode=execution_mode,
                spec_is_bug=spec_is_bug
            )

            # Write validation checklist
            decisions = decomposition.get("decisions", [])
            plan_mod.write_validation_checklist(CP_DIR, slug, tasks, decisions)

            # Clean up decomposition file
            os.remove(output_file)

            # Move draft → active
            spec_path = session.spec_path
            if "/draft/" in spec_path:
                fm["lifecycle"] = "active"
                wf.write_frontmatter(spec_path, fm)
                active_dir = os.path.join(CP_DIR, "features", "active")
                os.makedirs(active_dir, exist_ok=True)
                new_path = os.path.join(active_dir, os.path.basename(spec_path))
                result = subprocess.run(
                    ["git", "-C", CP_DIR, "mv", spec_path, new_path],
                    capture_output=True, text=True
                )
                if result.returncode != 0:
                    os.rename(spec_path, new_path)

            # Git add + commit
            subprocess.run(
                ["git", "-C", CP_DIR, "add",
                 f"queue/{slug}/", "contracts/", "features/"],
                capture_output=True
            )

            wave_count = len(set(t["wave"] for t in tasks))
            repo_count = len(set(t["repo"] for t in tasks))
            commit_msg = (f"feat: plan {slug} — "
                         f"{len(tasks)} tasks, {wave_count} waves, "
                         f"{repo_count} repos")

            result = subprocess.run(
                ["git", "-C", CP_DIR, "commit", "-m", commit_msg],
                capture_output=True, text=True
            )
            committed = result.returncode == 0

            # Push to remote
            pushed = False
            if committed:
                push_result = subprocess.run(
                    ["git", "-C", CP_DIR, "push"],
                    capture_output=True, text=True
                )
                pushed = push_result.returncode == 0

            self._send_json({
                "committed": committed,
                "pushed": pushed,
                "message": commit_msg if committed else "Nothing to commit",
                "taskCount": len(created_files),
                "waveCount": wave_count,
            })

        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    # ── Inbox handlers ────────────────────────────────────────────

    def _handle_inbox_ingest(self, body):
        """POST /api/inbox — ingest a new inbox item."""
        for field in ("source", "source_type", "title", "payload"):
            if field not in body:
                self._send_json({"error": f"missing required field: {field}"}, 400)
                return
        item = _inbox_db.create_item(
            INBOX_DB, body["source"], body["source_type"],
            body["title"], body["payload"],
        )
        self._send_json(item, 201)

    def _handle_inbox_triage(self, item_id):
        """POST /api/inbox/:id/triage — dispatch triage agent.

        ?mode=interactive: just update status (agent runs in browser via AgentSession)
        default: spawn run-agent.py in a terminal (fire-and-forget)
        """
        item = _inbox_db.get_item(INBOX_DB, item_id)
        if not item:
            self._send_json({"error": "not found"}, 404)
            return
        if item["status"] != "new":
            self._send_json({"error": f"cannot triage item in status: {item['status']}"}, 400)
            return
        # Determine dispatch mode
        params = parse_qs(urlparse(self.path).query)
        mode = params.get("mode", ["background"])[0]
        triage_mode = "interactive" if mode == "interactive" else "local-agent"

        try:
            _inbox_db.update_status(INBOX_DB, item_id, "triaging", triage_mode=triage_mode)
        except ValueError as e:
            self._send_json({"error": str(e)}, 400)
            return

        # Interactive mode: just update status, agent runs in browser
        if mode == "interactive":
            self._send_json({"itemId": int(item_id), "mode": "interactive"})
            return

        import platform
        # Build context for the triage agent
        context = json.dumps({
            "title": item["title"],
            "source": item["source"],
            "source_type": item["source_type"],
            "payload": item["payload"],
        })

        # Determine callback URL and port
        host_header = self.headers.get("Host", "localhost:7433")
        callback_url = f"http://{host_header}/api/inbox/{item_id}/triage-result"

        # Spawn run-agent.py in a terminal
        agent_script = os.path.join(SCRIPT_DIR, "run-agent.py")
        cp_abs = os.path.abspath(CP_DIR)
        escaped_context = context.replace("'", "'\\''")

        if platform.system() == "Darwin":
            cmd_str = (
                f"python3 '{agent_script}' "
                f"--agent-type triage "
                f"--cp-dir '{cp_abs}' "
                f"--context '{escaped_context}' "
                f"--callback-url '{callback_url}'"
            )
            # Escape double quotes and backslashes for AppleScript string
            as_escaped = cmd_str.replace("\\", "\\\\").replace('"', '\\"')
            subprocess.Popen(
                ["osascript",
                 "-e", f'tell app "Terminal" to do script "{as_escaped}"',
                 "-e", 'tell app "Terminal" to activate'],
            )
        else:
            subprocess.Popen(
                ["python3", agent_script,
                 "--agent-type", "triage",
                 "--cp-dir", cp_abs,
                 "--context", context,
                 "--callback-url", callback_url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self._send_json({"itemId": int(item_id), "mode": "background"})

    def _handle_inbox_triage_result(self, item_id, body):
        """POST /api/inbox/:id/triage-result — agent callback with triage report."""
        item = _inbox_db.get_item(INBOX_DB, item_id)
        if not item:
            self._send_json({"error": "not found"}, 404)
            return
        try:
            _inbox_db.update_status(INBOX_DB, item_id, "actionable", triage_report=body)
        except ValueError as e:
            self._send_json({"error": str(e)}, 400)
            return
        self._send_json({"ok": True})

    def _handle_inbox_promote(self, item_id, body):
        """POST /api/inbox/:id/promote — mark as promoted, return wizard URL."""
        item = _inbox_db.get_item(INBOX_DB, item_id)
        if not item:
            self._send_json({"error": "not found"}, 404)
            return
        try:
            _inbox_db.update_status(INBOX_DB, item_id, "promoted")
        except ValueError as e:
            self._send_json({"error": str(e)}, 400)
            return
        redirect = f"/interview?inbox_id={item_id}"
        self._send_json({"ok": True, "redirectUrl": redirect})

    def _handle_inbox_dismiss(self, item_id):
        """POST /api/inbox/:id/dismiss — archive the item."""
        item = _inbox_db.get_item(INBOX_DB, item_id)
        if not item:
            self._send_json({"error": "not found"}, 404)
            return
        try:
            _inbox_db.update_status(INBOX_DB, item_id, "dismissed")
        except ValueError as e:
            self._send_json({"error": str(e)}, 400)
            return
        self._send_json({"ok": True})

    # ── Local dispatch handlers ─────────────────────────────────

    def _handle_local_dispatch(self, body):
        """Set execution mode on queue tasks and spawn local-agent.sh."""
        import glob as glob_mod

        slug = body.get("slug", "").strip()
        mode = body.get("mode", "").strip()
        agents = max(1, min(4, int(body.get("agents", 1))))
        if not slug or mode not in ("autonomous", "supervised", "guided"):
            self._send_json({"error": "slug and mode (autonomous|supervised|guided) required"}, 400)
            return

        # Check if an agent is already running for this slug
        existing = AGENT_PROCESSES.get(slug)
        if existing and existing.poll() is None:
            self._send_json({"error": f"Agent already running for {slug} (PID {existing.pid})"}, 409)
            return

        # Update execution mode on queue task files
        pattern = os.path.join(CP_DIR, "queue", slug, "*", "wave-*.md")
        task_files = glob_mod.glob(pattern)
        updated = 0
        for tf in task_files:
            with open(tf) as f:
                content = f.read()
            new_content = re.sub(r"^execution:.*$", f"execution: {mode}", content, flags=re.MULTILINE)
            if new_content != content:
                with open(tf, "w") as f:
                    f.write(new_content)
                updated += 1

        # Git commit + push the mode change
        if updated > 0:
            subprocess.run(
                ["git", "-C", CP_DIR, "add", f"queue/{slug}/"],
                capture_output=True
            )
            subprocess.run(
                ["git", "-C", CP_DIR, "commit", "-m",
                 f"fix: set execution mode to {mode} for {slug}"],
                capture_output=True, text=True
            )
            subprocess.run(
                ["git", "-C", CP_DIR, "push"],
                capture_output=True, text=True
            )

        # Spawn local-agent.sh as a background process
        agent_script = os.path.join(SCRIPT_DIR, "local-agent.sh")
        if not os.path.exists(agent_script):
            self._send_json({"error": "local-agent.sh not found"}, 500)
            return

        import platform
        cp_abs = os.path.abspath(CP_DIR)
        if platform.system() == "Darwin":
            cmd_str = f"'{agent_script}' --cp-dir '{cp_abs}' --agents-per-repo {agents}"
            proc = subprocess.Popen(
                ["osascript",
                 "-e", f'tell app "Terminal" to do script "{cmd_str}"',
                 "-e", 'tell app "Terminal" to activate'],
            )
        else:
            proc = subprocess.Popen(
                [agent_script, "--cp-dir", cp_abs,
                 "--agents-per-repo", str(agents)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        AGENT_PROCESSES[slug] = proc

        self._send_json({
            "status": "ok",
            "pid": proc.pid,
            "slug": slug,
            "mode": mode,
            "agents": agents,
            "tasksUpdated": updated,
        })

    def _handle_compliance_report(self, body):
        """Generate a compliance posture report in a background terminal."""
        import platform

        period = int(body.get("period", 90))
        fmt = body.get("format", "pdf")
        if fmt not in ("pdf", "html", "both"):
            fmt = "pdf"

        report_script = os.path.join(SCRIPT_DIR, "compliance-report.py")
        if not os.path.exists(report_script):
            self._send_json({"error": "compliance-report.py not found"}, 500)
            return

        cp_abs = os.path.abspath(CP_DIR)
        output_dir = os.path.join(cp_abs, "reports")
        os.makedirs(output_dir, exist_ok=True)

        cmd_str = (
            f"python3 '{report_script}' --cp-dir '{cp_abs}'"
            f" --period {period} --output '{output_dir}' --format {fmt}"
            f"; exit"
        )

        if platform.system() == "Darwin":
            as_escaped = cmd_str.replace("\\", "\\\\").replace('"', '\\"')
            subprocess.Popen([
                "osascript",
                "-e", f'tell app "Terminal" to do script "{as_escaped}"',
                "-e", 'tell app "Terminal" to activate',
            ])
        else:
            subprocess.Popen(
                cmd_str, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

        self._send_json({
            "status": "ok",
            "message": "Compliance report generation started",
            "output_dir": output_dir,
            "period": period,
            "format": fmt,
        })

    def _handle_launch_terminal(self, body):
        """Launch a command in a visible Terminal window."""
        command = body.get("command", "").strip()
        if not command:
            self._send_json({"error": "command required"}, 400)
            return

        import platform
        cp_abs = os.path.abspath(CP_DIR)

        # Resolve relay CLI path
        relay_bin = os.path.join(os.path.dirname(SCRIPT_DIR), "..", "relay")
        relay_bin = os.path.abspath(relay_bin)

        # Build the command to run in the CP directory
        cmd_str = f"cd '{cp_abs}' && '{relay_bin}' new"

        if platform.system() == "Darwin":
            subprocess.Popen(
                ["osascript",
                 "-e", f'tell app "Terminal" to do script "{cmd_str}"',
                 "-e", 'tell app "Terminal" to activate'],
            )
        else:
            subprocess.Popen(
                ["bash", "-c", cmd_str],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self._send_json({"status": "ok"})


# ── Interview Session ────────────────────────────────────────────

CODE_REPO_GUIDANCE = """

## Code Repository Access

You have read-only access to the code repositories via `read_repo_file`, \
`list_directory`, and `search_code` tools. Use them to:
- Understand existing APIs, endpoints, schemas, and components
- Validate technical assumptions against actual code
- Identify existing patterns the new feature should follow
- Spot potential conflicts or integration points

Write requirements from the user's perspective, not the implementation's. \
Use code knowledge to ask better questions and make better recommendations, \
but don't over-constrain the spec based on current implementation limitations.
"""


class InterviewSession(BaseAgentSession):
    """Manages a feature interview with deterministic step-engine orchestration.

    Uses StepEngine from _step_engine.py to guarantee all steps execute
    in order. The engine controls transitions — not the AI, not text matching.

    Steps: Interview → Draft → Refine (6 rounds) → Update → Finalize
    """

    def __init__(self, idea, slug, execution, priority, epic, epic_title, total_budget,
                 triage_context="", inbox_id=None):
        repo_paths, _ = parse_service_catalog(CP_DIR)
        planner_model = wf.resolve_model(CP_DIR, role="planner")
        super().__init__(cp_dir=CP_DIR, repo_paths=repo_paths, include_write_tool=True,
                         model=planner_model)
        self.idea = idea
        if triage_context:
            self.idea = (
                f"## Triage Context (from inbox analysis)\n\n"
                f"{triage_context}\n\n"
                f"## Original Request\n\n"
                f"{idea}"
            )
        self.slug = slug
        self.execution = execution
        self.priority = priority
        self.epic = epic
        self.epic_title = epic_title
        self.total_budget = total_budget
        self.inbox_id = inbox_id

    def _load_context(self):
        """Load contract, service catalog, and template."""
        contract_path = os.path.join(CP_DIR, "contracts", "tasks-api.json")
        contract = ""
        if os.path.exists(contract_path):
            with open(contract_path) as f:
                contract = f.read()

        _, service_catalog = parse_service_catalog(CP_DIR)

        template_path = os.path.join(RELAY_DIR, "process", "templates",
                                      "feature-spec.md")
        template = ""
        if os.path.exists(template_path):
            with open(template_path) as f:
                template = f.read()
        else:
            self._emit({"type": "error",
                        "text": "Feature spec template not found"})
            self._emit(None)
            return False

        self._context = {
            "contract": contract,
            "service_catalog": service_catalog,
            "template": template,
        }
        return True

    def start(self):
        """Initialize the step engine and start the first step."""
        if self._init_client():
            return
        if not self._load_context():
            return

        # Ensure draft dir exists
        draft_dir = os.path.join(CP_DIR, "features", "draft")
        os.makedirs(draft_dir, exist_ok=True)

        from _spec_workflow import SPEC_WORKFLOW, build_spec_config
        from _step_engine import StepEngine

        self._engine = StepEngine(
            SPEC_WORKFLOW,
            build_spec_config(
                idea=self.idea, slug=self.slug,
                execution=self.execution, priority=self.priority,
                total_budget=self.total_budget, epic=self.epic,
                epic_title=self.epic_title,
                code_repo_guidance=CODE_REPO_GUIDANCE,
                **self._context,
            ),
        )
        self._start_current_step()

    def _start_current_step(self):
        """Start whatever step the engine says is current."""
        step = self._engine.current_step
        if step is None or step.type == "no-ai":
            self.finalize()
            return

        self.phase = step.id
        self.wizard_step = self._step_to_wizard(step)
        self.system_prompt = self._engine.get_system_prompt()
        self._tools = self._engine.get_tools(build_tools(self._repo_paths))

        self._emit({
            "type": "loading",
            "text": self._engine.progress,
            "phase": self.phase,
            "step": self.wizard_step,
        })

        msg = self._engine.get_kickoff_message()
        thread = threading.Thread(
            target=self._run_step_turn, args=(msg,), daemon=True)
        thread.start()

    def _run_step_turn(self, msg):
        """Run a turn and auto-advance if the step completed."""
        try:
            self._run_turn(msg)
            # _on_response handles advancement — no extra call needed
        except Exception as e:
            self._emit({"type": "error", "text": f"Step failed: {e}"})

    def _on_response(self, text):
        """Called after every AI response (kickoff and user answers).

        This is the single place where step advancement is checked.
        Handles both: kickoff turns via _run_step_turn, and user
        answer turns via send_answer → _run_turn → _on_response.
        """
        self._check_advance()

    def _check_advance(self):
        """If the engine says the current step is done, advance."""
        if not self._engine or not self._engine.on_turn_end():
            return
        next_step = self._engine.advance()
        if next_step is None or next_step.type == "no-ai":
            self.finalize()
        else:
            self._start_current_step()

    def _step_to_wizard(self, step):
        """Map engine step ID to the 5-step wizard UI."""
        if step.id == "interview":
            return 2
        if step.id == "draft":
            return 3
        if step.id == "finalize":
            return 5
        return 4  # refine-*, update

    def finalize(self):
        """Show validation + commit UI."""
        if self.phase == "done":
            return
        self.phase = "done"
        self.wizard_step = 5
        self.status = "complete"
        self._emit({
            "type": "finalize",
            "text": "ready",
            "phase": "done",
            "step": 5,
        })
        self._emit(None)  # Close SSE stream


# ── Planning Session ─────────────────────────────────────────────

class PlanningSession(BaseAgentSession):
    """Manages a planning session — decomposes a feature spec into tasks."""

    def __init__(self, slug, spec_path):
        repo_paths, _ = parse_service_catalog(CP_DIR)
        architect_model = wf.resolve_model(CP_DIR, role="architect")
        super().__init__(cp_dir=CP_DIR, repo_paths=repo_paths, include_write_tool=True,
                         model=architect_model)
        self.slug = slug
        self.spec_path = spec_path

    def start(self):
        if self._init_client():
            return

        # Load feature spec
        with open(self.spec_path) as f:
            feature_content = f.read()

        _, service_catalog = parse_service_catalog(CP_DIR)

        # Load contracts
        contracts = {}
        contracts_dir = os.path.join(CP_DIR, "contracts")
        if os.path.isdir(contracts_dir):
            for fname in os.listdir(contracts_dir):
                if fname.endswith(".json"):
                    with open(os.path.join(contracts_dir, fname)) as f:
                        contracts[fname] = f.read()

        # Load task template
        task_template = ""
        template_path = os.path.join(RELAY_DIR, "process", "templates",
                                      "task-queue-item.md")
        if os.path.exists(template_path):
            with open(template_path) as f:
                task_template = f.read()

        # Generate repo briefs (run generate-brief.sh for each repo)
        briefs = {}
        for repo_name, repo_path in self._repo_paths.items():
            brief_script = os.path.join(RELAY_DIR, "process", "scripts",
                                         "generate-brief.sh")
            manifest_path = os.path.join(CP_DIR, "repos", repo_name,
                                          "repo-manifest.md")
            if os.path.exists(brief_script):
                subprocess.run(
                    ["bash", brief_script, "--repo-dir", repo_path,
                     "--output", manifest_path],
                    capture_output=True, timeout=30
                )
            if os.path.exists(manifest_path):
                with open(manifest_path) as f:
                    briefs[repo_name] = f.read()

        # Build the decomposition prompt using plan.py's function
        import importlib.util
        plan_mod_path = os.path.join(SCRIPT_DIR, "plan.py")
        loader = importlib.util.spec_from_file_location("plan_mod",
                                                         plan_mod_path)
        plan_mod = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(plan_mod)

        # Extract execution mode from feature frontmatter
        fm = wf.parse_frontmatter(self.spec_path)
        execution_mode = fm.get("execution", "supervised")

        output_file_abs = os.path.join(CP_DIR, "queue", self.slug,
                                    "_decomposition.json")
        output_file_rel = os.path.join("queue", self.slug,
                                    "_decomposition.json")
        os.makedirs(os.path.dirname(output_file_abs), exist_ok=True)

        self.system_prompt = plan_mod.build_decomposition_prompt(
            feature_content=feature_content,
            briefs=briefs,
            service_catalog=service_catalog,
            edge_cases="",
            retro_log="",
            contracts=contracts,
            task_template=task_template,
            output_file=output_file_rel,
            feature_execution_mode=execution_mode,
        )

        # Add code repo access guidance
        self.system_prompt += """

## Code Repository Access

You have read-only access to the code repositories via `read_repo_file`, \
`list_directory`, and `search_code` tools. Use them to understand the \
codebase structure, existing APIs, and implementation patterns to produce \
accurate task decompositions with realistic line estimates.
"""

        self.phase = "planning"
        self.wizard_step = 2

        thread = threading.Thread(target=self._run_turn,
                                  args=("Begin. The feature spec is already in your context — do NOT read it from disk. Start by summarizing what you understand from the spec: the key requirements, affected repos, and acceptance criteria. Then propose your task decomposition approach (waves, ordering, dependencies) and ask me to confirm before writing _decomposition.json. Only use the code repo tools if you need to check a specific implementation detail.",),
                                  daemon=True)
        thread.start()

    def _on_response(self, text):
        """Auto-detect decomposition completion."""
        lower = text.lower()
        if "decomposition complete" in lower or "all phases complete" in lower or "task breakdown has been written" in lower:
            self.finalize()

    def finalize(self):
        if self.phase == "done":
            return
        self.phase = "done"
        self.wizard_step = 3
        self.status = "complete"
        self._emit({"type": "finalize", "text": "ready", "phase": "done", "step": 3})


# ── Agent Session (generic, definition-driven) ─────────────────

CREATE_SPEC_BRIEF_TOOL = {
    "name": "create_spec_brief",
    "description": (
        "Distill the current conversation into a structured brief for creating "
        "a feature spec. Call this when the user wants to turn an idea discussed "
        "in chat into a formal feature."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short title for the feature (used as the idea field)",
            },
            "summary": {
                "type": "string",
                "description": "Concise summary of the idea, key requirements, constraints, and open questions discussed",
            },
            "slug": {
                "type": "string",
                "description": "Suggested kebab-case slug for the feature",
            },
        },
        "required": ["title", "summary", "slug"],
    },
}


class AgentSession(BaseAgentSession):
    """Generic agent session driven by a definition file in process/agents/.

    Uses load_agent_def from _agent_runtime for definition loading.
    For chat agents, injects the create_spec_brief tool for feature escalation.
    """

    def __init__(self, agent_type, context=None):
        repo_paths, _ = parse_service_catalog(CP_DIR)
        try:
            self._agent_def = load_agent_def(agent_type, RELAY_DIR)
        except FileNotFoundError as e:
            raise ValueError(str(e))

        include_write = self._agent_def["tools"] == "read-write"
        model = wf.resolve_model(CP_DIR, role="implementer")
        super().__init__(
            cp_dir=CP_DIR,
            repo_paths=repo_paths,
            include_write_tool=include_write,
            model=model,
        )
        self.agent_type = agent_type
        self.agent_name = self._agent_def["name"]
        self.phase = agent_type
        self._context = context
        self._spec_brief = None  # populated when create_spec_brief is called

        # Inject create_spec_brief tool for chat agent
        if agent_type == "chat":
            self._tools.append(CREATE_SPEC_BRIEF_TOOL)

    def _handle_custom_tool(self, name, input_data):
        """Handle session-specific tools like create_spec_brief."""
        if name == "create_spec_brief":
            self._spec_brief = {
                "title": input_data.get("title", ""),
                "summary": input_data.get("summary", ""),
                "slug": input_data.get("slug", ""),
            }
            self._emit({
                "type": "spec_brief",
                "brief": self._spec_brief,
                "phase": self.phase,
                "step": self.wizard_step,
            })
            return (
                f"Brief created for '{self._spec_brief['title']}'. "
                f"The user will be redirected to the Feature Agent to continue."
            )
        return None  # not handled — fall through to canonical executor

    def start(self):
        if self._init_client():
            return

        # Wire up custom tool handler for session-specific tools
        if self._runtime and self.agent_type == "chat":
            self._runtime.custom_tool_handler = self._handle_custom_tool

        self.system_prompt = self._agent_def["prompt"].replace(
            "{repos}", str(list(self._repo_paths.keys()) or "(none configured)"),
        )

        if self._context:
            first_message = self._context
        else:
            first_message = "Hello! I'm ready. What would you like help with?"

        thread = threading.Thread(
            target=self._run_turn,
            args=(first_message,),
            daemon=True,
        )
        thread.start()


# ── Helpers ──────────────────────────────────────────────────────

def _slugify(text):
    """Convert text to kebab-case slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


# ── Handoff HTML (chat → interview) ──────────────────────────────

HANDOFF_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Start Feature — Relay</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0%25' stop-color='%2334d399'/><stop offset='50%25' stop-color='%23818cf8'/><stop offset='100%25' stop-color='%23ec4899'/></linearGradient></defs><rect width='32' height='32' rx='8' fill='url(%23g)'/><text x='16' y='22' text-anchor='middle' font-family='sans-serif' font-weight='800' font-size='18' fill='white'>R</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --font-body: 'DM Sans', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --bg: #0a0e27;
  --bg-card: rgba(255,255,255,0.04);
  --bg-input: rgba(255,255,255,0.05);
  --border: rgba(255,255,255,0.08);
  --border-hover: rgba(255,255,255,0.18);
  --text-primary: #e8ecf4;
  --text-secondary: #94a3b8;
  --text-muted: #475569;
  --accent: #818cf8;
  --green: #34d399;
  --blue: #818cf8;
  --radius: 16px;
  --transition: 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--font-body); background: var(--bg); color: var(--text-primary);
  min-height: 100vh; display: flex; flex-direction: column;
}
body::before {
  content: ''; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background:
    radial-gradient(ellipse 50% 50% at 20% 30%, rgba(0,212,170,0.12), transparent),
    radial-gradient(ellipse 40% 40% at 80% 20%, rgba(124,58,237,0.10), transparent),
    radial-gradient(ellipse 45% 45% at 60% 80%, rgba(59,130,246,0.08), transparent);
}
.navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(10,14,39,0.8); backdrop-filter: blur(30px);
  border-bottom: 1px solid var(--border);
  padding: 0 24px; height: 56px;
  display: flex; align-items: center; justify-content: space-between;
}
.nav-left { display: flex; align-items: center; gap: 12px; }
.nav-logo {
  width: 28px; height: 28px; border-radius: 10px;
  background: linear-gradient(135deg, var(--green), var(--blue), #ec4899);
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 14px; color: #fff;
}
.nav-title { font-weight: 700; font-size: 15px; }
.nav-back { color: var(--text-secondary); text-decoration: none; font-size: 13px; }
.nav-back:hover { color: var(--text-primary); }

.form-wrap {
  max-width: 640px; width: 100%; margin: 40px auto; padding: 0 24px;
}
.form-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 32px;
}
.form-title { font-size: 22px; font-weight: 700; margin-bottom: 24px; }

.brief-section {
  background: rgba(129,140,248,0.08); border: 1px solid rgba(129,140,248,0.2);
  border-radius: 12px; padding: 16px; margin-bottom: 24px;
}
.brief-label {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--accent); margin-bottom: 8px;
}
.brief-title { font-weight: 600; font-size: 16px; margin-bottom: 8px; }
.brief-summary {
  color: var(--text-secondary); font-size: 13px; line-height: 1.6;
  white-space: pre-wrap;
}
.brief-toggle {
  background: none; border: none; color: var(--accent); font-size: 12px;
  cursor: pointer; margin-top: 8px; font-family: var(--font-body);
}

.field-group { margin-bottom: 20px; }
.field-label {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--text-secondary); margin-bottom: 6px;
}
.field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
input, select {
  width: 100%; padding: 10px 14px; background: var(--bg-input);
  border: 1px solid var(--border); border-radius: 10px;
  color: var(--text-primary); font-family: var(--font-body); font-size: 14px;
  outline: none; transition: border-color 0.2s;
}
input:focus, select:focus { border-color: var(--accent); }
select { appearance: none; cursor: pointer; }

.submit-btn {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  width: 100%; padding: 14px; margin-top: 28px;
  background: linear-gradient(135deg, var(--accent), #a78bfa);
  border: none; border-radius: 12px; color: #fff;
  font-family: var(--font-body); font-weight: 600; font-size: 15px;
  cursor: pointer; transition: opacity 0.2s, transform 0.2s;
}
.submit-btn:hover { opacity: 0.9; transform: translateY(-1px); }
</style>
</head>
<body>
<nav class="navbar">
  <div class="nav-left">
    <div class="nav-logo">R</div>
    <span class="nav-title">Relay</span>
  </div>
  <a href="/agents" class="nav-back">Agent Workforce</a>
</nav>

<div class="form-wrap">
  <div class="form-card">
    <h2 class="form-title">Start Feature from Chat</h2>

    <div class="brief-section">
      <div class="brief-label">Brief from Chat Agent</div>
      <div class="brief-title" id="brief-title"></div>
      <div class="brief-summary" id="brief-summary"></div>
      <button class="brief-toggle" id="brief-toggle" onclick="toggleBrief()">Show less</button>
    </div>

    <form id="handoff-form" onsubmit="submitHandoff(event)">
      <div class="field-group">
        <div class="field-label">Feature Slug</div>
        <input type="text" id="slug" placeholder="auto-generated from title">
        <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">kebab-case identifier used for file names and branches</div>
      </div>

      <div class="field-row">
        <div class="field-group">
          <div class="field-label">Execution Mode</div>
          <select id="execution">
            <option value="supervised" selected>Supervised (default)</option>
            <option value="autonomous">Autonomous</option>
            <option value="guided">Guided</option>
          </select>
        </div>
        <div class="field-group">
          <div class="field-label">Priority</div>
          <select id="priority">
            <option value="low">Low</option>
            <option value="medium" selected>Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>
      </div>

      <div class="field-row">
        <div class="field-group">
          <div class="field-label">Jira Epic ID</div>
          <input type="text" id="jira" placeholder="optional, e.g. PLAT-1234">
        </div>
        <div class="field-group">
          <div class="field-label">Epic Title</div>
          <input type="text" id="epic-title" placeholder="optional, for display">
        </div>
      </div>

      <div class="field-group">
        <div class="field-label">Feature Budget (USD)</div>
        <input type="text" id="totalBudget" placeholder="optional, e.g. 5.00">
      </div>

      <button type="submit" class="submit-btn">Start Interview &rarr;</button>
    </form>
  </div>
</div>

<script>
const brief = __BRIEF_JSON__;
const chatSessionId = '__SESSION_ID__';

document.getElementById('brief-title').textContent = brief.title || 'Untitled';
document.getElementById('brief-summary').textContent = brief.summary || '';
document.getElementById('slug').value = brief.slug || slugify(brief.title || '');

let briefExpanded = true;
function toggleBrief() {
  briefExpanded = !briefExpanded;
  const el = document.getElementById('brief-summary');
  const btn = document.getElementById('brief-toggle');
  if (briefExpanded) { el.style.display = ''; btn.textContent = 'Show less'; }
  else { el.style.display = 'none'; btn.textContent = 'Show more'; }
}

function slugify(text) {
  return text.toLowerCase().trim()
    .replace(/[^\\w\\s-]/g, '').replace(/[\\s_]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
}

async function submitHandoff(e) {
  e.preventDefault();
  const body = {
    idea: brief.title || '',
    slug: document.getElementById('slug').value.trim(),
    execution: document.getElementById('execution').value,
    priority: document.getElementById('priority').value,
    jira_epic: document.getElementById('jira').value.trim(),
    epic_title: document.getElementById('epic-title').value.trim(),
    totalBudget: document.getElementById('totalBudget').value.trim(),
    chat_brief: brief.summary || '',
    from_chat_session: chatSessionId,
  };
  try {
    const resp = await fetch('/api/interview/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (data.sessionId) {
      sessionStorage.setItem('relay_interview_session', data.sessionId);
      window.location.href = '/interview';
    } else {
      alert(data.error || 'Failed to start interview');
    }
  } catch (err) { alert('Error: ' + err.message); }
}
</script>
</body>
</html>
"""


# ── Wizard HTML ──────────────────────────────────────────────────

WIZARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>New Feature — Relay</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0%25' stop-color='%2334d399'/><stop offset='50%25' stop-color='%23818cf8'/><stop offset='100%25' stop-color='%23ec4899'/></linearGradient></defs><rect width='32' height='32' rx='8' fill='url(%23g)'/><text x='16' y='22' text-anchor='middle' font-family='sans-serif' font-weight='800' font-size='18' fill='white'>R</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --font-body: 'DM Sans', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --bg: #0a0e27;
  --bg-card: rgba(255,255,255,0.04);
  --bg-card-hover: rgba(255,255,255,0.07);
  --bg-detail: rgba(0,0,0,0.2);
  --bg-input: rgba(255,255,255,0.05);
  --border: rgba(255,255,255,0.08);
  --border-hover: rgba(255,255,255,0.18);
  --text-primary: #e8ecf4;
  --text-secondary: #94a3b8;
  --text-muted: #475569;
  --accent: #818cf8;
  --green: #34d399;
  --blue: #818cf8;
  --amber: #fbbf24;
  --red: #f87171;
  --radius: 16px;
  --transition: 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--font-body); background: var(--bg); color: var(--text-primary);
  min-height: 100vh;
}
body::before {
  content: ''; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background:
    radial-gradient(ellipse 50% 50% at 20% 30%, rgba(0,212,170,0.12), transparent),
    radial-gradient(ellipse 40% 40% at 80% 20%, rgba(124,58,237,0.10), transparent),
    radial-gradient(ellipse 45% 45% at 60% 80%, rgba(59,130,246,0.08), transparent),
    radial-gradient(ellipse 35% 35% at 10% 80%, rgba(236,72,153,0.06), transparent);
  animation: aurora 20s ease-in-out infinite;
}
@keyframes aurora {
  0%, 100% { background-position: 0% 50%, 100% 50%, 50% 0%, 0% 100%; }
  25% { background-position: 100% 0%, 0% 100%, 50% 50%, 100% 0%; }
  50% { background-position: 50% 100%, 50% 0%, 0% 50%, 50% 50%; }
  75% { background-position: 0% 50%, 100% 50%, 100% 100%, 0% 0%; }
}

/* ── Nav ── */
.navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(10,14,39,0.8); backdrop-filter: blur(30px);
  border-bottom: 1px solid var(--border);
  padding: 0 24px; height: 56px;
  display: flex; align-items: center; justify-content: space-between;
}
.nav-left { display: flex; align-items: center; gap: 12px; }
.nav-logo {
  width: 28px; height: 28px; border-radius: 10px;
  background: linear-gradient(135deg, var(--green), var(--blue), #ec4899);
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 14px; color: #fff;
  box-shadow: 0 0 20px rgba(129,140,248,0.3);
}
.nav-title { font-weight: 700; font-size: 15px; }
.nav-back {
  color: var(--text-secondary); text-decoration: none;
  font-size: 13px; font-weight: 600;
  padding: 6px 12px; border-radius: 8px;
  border: 1px solid var(--border); transition: all var(--transition);
}
.nav-back:hover { border-color: var(--border-hover); color: var(--text-primary); }

/* ── Steps Progress ── */
.steps {
  display: flex; align-items: center; justify-content: center;
  gap: 0; padding: 20px 24px 0;
}
.step {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 16px; font-size: 12px; font-weight: 600;
  color: var(--text-muted); transition: all var(--transition);
}
.step.active { color: var(--accent); }
.step.done { color: var(--green); }
.step-num {
  width: 24px; height: 24px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700;
  background: rgba(255,255,255,0.06); border: 1px solid var(--border);
  transition: all var(--transition);
}
.step.active .step-num {
  background: rgba(129,140,248,0.15); border-color: var(--accent);
  color: var(--accent); box-shadow: 0 0 12px rgba(129,140,248,0.2);
}
.step.done .step-num {
  background: rgba(52,211,153,0.15); border-color: var(--green);
  color: var(--green);
}
.step-connector {
  width: 32px; height: 1px; background: var(--border);
  flex-shrink: 0;
}

/* ── Layout ── */
.main { max-width: 900px; margin: 0 auto; padding: 24px; }

/* ── Setup Form ── */
.form-card {
  background: var(--bg-card); backdrop-filter: blur(24px);
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 28px; animation: fadeUp 0.5s ease-out;
}
.form-title { font-size: 16px; font-weight: 700; margin-bottom: 20px; }
.form-group { margin-bottom: 16px; }
.form-label {
  display: block; font-size: 12px; font-weight: 600;
  color: var(--text-secondary); margin-bottom: 6px;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.form-input, .form-select {
  width: 100%; padding: 10px 14px;
  background: var(--bg-input); border: 1px solid var(--border);
  border-radius: 8px; color: var(--text-primary);
  font-family: var(--font-mono); font-size: 13px;
  transition: border-color var(--transition);
}
.form-input:focus, .form-select:focus {
  outline: none; border-color: var(--accent);
  box-shadow: 0 0 20px rgba(129,140,248,0.15);
}
.form-select {
  appearance: none; cursor: pointer;
  background-image: url("data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%2394a3b8' stroke-width='1.5' fill='none'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 14px center;
  padding-right: 36px;
}
option { background: var(--bg); }
.form-row { display: flex; gap: 16px; }
.form-row .form-group { flex: 1; }
.form-hint { font-size: 11px; color: var(--text-muted); margin-top: 4px; }
.form-actions { margin-top: 24px; display: flex; justify-content: flex-end; }
.btn-primary {
  padding: 10px 24px; border-radius: 8px; border: none;
  background: var(--accent); color: #fff;
  font-size: 14px; font-weight: 600; font-family: var(--font-body);
  cursor: pointer; transition: all var(--transition);
  box-shadow: 0 0 20px rgba(129,140,248,0.2);
}
.btn-primary:hover {
  box-shadow: 0 0 30px rgba(129,140,248,0.4);
  transform: translateY(-1px);
}
.btn-primary:disabled {
  opacity: 0.4; cursor: not-allowed; box-shadow: none; transform: none;
}
.btn-secondary {
  padding: 10px 24px; border-radius: 8px;
  border: 1px solid var(--border);
  background: transparent; color: var(--text-secondary);
  font-size: 14px; font-weight: 600; font-family: var(--font-body);
  cursor: pointer; transition: all var(--transition);
}
.btn-secondary:hover {
  border-color: var(--border-hover); color: var(--text-primary);
}

/* ── Chat ── */
.chat-container {
  display: flex; flex-direction: column; position: relative;
  height: calc(100vh - 180px);
  background: var(--bg-card); backdrop-filter: blur(24px);
  border: 1px solid var(--border); border-radius: var(--radius);
  overflow: hidden; animation: fadeUp 0.5s ease-out;
}
.chat-messages {
  flex: 1; overflow-y: auto; padding: 20px;
  display: flex; flex-direction: column; gap: 16px;
}
.chat-msg {
  max-width: 80%; padding: 12px 16px;
  border-radius: 12px; font-size: 13px; line-height: 1.6;
  animation: fadeUp 0.3s ease-out;
}
.chat-msg.ai {
  align-self: flex-start;
  background: var(--bg-detail); border: 1px solid var(--border);
  color: var(--text-primary);
}
.chat-msg.user {
  align-self: flex-end;
  background: rgba(129,140,248,0.15); border: 1px solid rgba(129,140,248,0.25);
  color: var(--text-primary);
}
.chat-msg.system {
  align-self: center; max-width: 90%;
  background: rgba(52,211,153,0.08); border: 1px solid rgba(52,211,153,0.15);
  color: var(--green); text-align: center;
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.05em; padding: 8px 16px;
}
.chat-msg pre {
  background: rgba(0,0,0,0.3); border-radius: 6px;
  padding: 10px 12px; margin: 8px 0; overflow-x: auto;
  font-family: var(--font-mono); font-size: 12px;
}
.chat-msg code {
  font-family: var(--font-mono); font-size: 12px;
  background: rgba(0,0,0,0.2); padding: 2px 5px; border-radius: 3px;
}
.typing-indicator {
  display: flex; gap: 4px; padding: 12px 16px;
  align-self: flex-start;
}
.typing-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--text-muted);
  animation: typingBounce 1.4s infinite;
}
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-6px); }
}
.chat-input-wrap {
  display: flex; gap: 8px; padding: 16px;
  border-top: 1px solid var(--border);
  background: rgba(0,0,0,0.15);
  align-items: flex-end;
}
.chat-input {
  flex: 1; padding: 12px 16px;
  background: var(--bg-input); border: 1px solid var(--border);
  border-radius: 12px; color: var(--text-primary);
  font-family: var(--font-body); font-size: 14px;
  resize: none; min-height: 44px; max-height: 120px;
}
.chat-input:focus { outline: none; border-color: var(--accent); }
.chat-send {
  padding: 0 20px; height: 44px; border-radius: 12px; border: none;
  background: var(--accent); color: #fff;
  font-size: 14px; font-weight: 600; font-family: var(--font-body);
  cursor: pointer; transition: all var(--transition);
  white-space: nowrap; flex-shrink: 0;
}
.chat-send:hover { box-shadow: 0 0 20px rgba(129,140,248,0.3); }
.chat-send:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── Spec Preview ── */
.spec-preview {
  background: var(--bg-card); backdrop-filter: blur(24px);
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 28px; animation: fadeUp 0.5s ease-out;
  max-height: calc(100vh - 240px); overflow-y: auto;
}
.spec-preview pre {
  font-family: var(--font-mono); font-size: 12px;
  line-height: 1.6; color: var(--text-primary);
  white-space: pre-wrap; word-wrap: break-word;
}
.spec-actions {
  display: flex; gap: 12px; justify-content: flex-end;
  margin-top: 20px;
}
.validation-results {
  margin-bottom: 20px; padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}
.validation-title {
  font-size: 13px; font-weight: 700; color: var(--text-secondary);
  text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px;
}
.validation-check {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 0; font-size: 13px;
}
.validation-pass { color: var(--green); }
.validation-warn { color: var(--amber); }
.sync-warning { background:rgba(251,191,36,0.1);border:1px solid rgba(251,191,36,0.3);color:var(--amber);padding:8px 12px;border-radius:8px;font-size:13px;margin-bottom:8px; }
.triage-banner { background:rgba(129,140,248,0.1);border:1px solid rgba(129,140,248,0.3);color:var(--accent);padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:12px;line-height:1.5;cursor:pointer; }
.triage-banner .triage-toggle { font-size:11px;opacity:0.6;margin-left:4px; }
.triage-banner .triage-full { display:none;margin-top:8px;white-space:pre-wrap;opacity:0.85;font-size:12px;line-height:1.6; }
.triage-banner .triage-preview { display:inline; }
.triage-banner.expanded .triage-preview { display:none; }
.triage-banner.expanded .triage-full { display:block; }
.triage-banner.expanded .triage-toggle { display:none; }

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .main { padding: 16px; }
  .form-row { flex-direction: column; gap: 0; }
  .steps { flex-wrap: wrap; gap: 4px; }
  .step-connector { display: none; }
}
</style>
</head>
<body>

<nav class="navbar">
  <div class="nav-left">
    <div class="nav-logo">R</div>
    <span class="nav-title">New Feature</span>
  </div>
  <a href="/" class="nav-back">&larr; Command Center</a>
</nav>

<div class="steps" id="stepsBar">
  <div class="step active" data-step="1"><span class="step-num">1</span> Feature</div>
  <div class="step-connector"></div>
  <div class="step" data-step="2"><span class="step-num">2</span> Interview</div>
  <div class="step-connector"></div>
  <div class="step" data-step="3"><span class="step-num">3</span> Draft</div>
  <div class="step-connector"></div>
  <div class="step" data-step="4"><span class="step-num">4</span> Refine</div>
  <div class="step-connector"></div>
  <div class="step" data-step="5"><span class="step-num">5</span> Finalize</div>
</div>

<div class="main" id="mainContent">
  <!-- Step 1: Setup Form -->
  <div id="step1" class="form-card">
    <div class="form-title">Define Your Feature</div>
    <div class="form-group">
      <label class="form-label">What do you want to build?</label>
      <input type="text" class="form-input" id="ideaInput" placeholder="e.g. Shopping cart with saved items" autofocus>
    </div>
    <div class="form-group">
      <label class="form-label">Feature slug</label>
      <input type="text" class="form-input" id="slugInput" placeholder="auto-generated from idea">
      <div class="form-hint">kebab-case identifier used for file names and branches</div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">Execution Mode</label>
        <select class="form-select" id="executionSelect">
          <option value="supervised" selected>Supervised (default)</option>
          <option value="autonomous">Autonomous</option>
          <option value="guided">Guided</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Priority</label>
        <select class="form-select" id="prioritySelect">
          <option value="medium" selected>Medium (default)</option>
          <option value="high">High</option>
          <option value="low">Low</option>
        </select>
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">Jira Epic ID</label>
        <input type="text" class="form-input" id="epicInput" placeholder="optional, e.g. PLAT-1234">
      </div>
      <div class="form-group">
        <label class="form-label">Epic Title</label>
        <input type="text" class="form-input" id="epicTitleInput" placeholder="optional, for display">
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">Feature Budget (USD)</label>
      <input type="text" class="form-input" id="totalBudgetInput" placeholder="optional, e.g. 5.00">
    </div>
    <div class="form-actions">
      <button class="btn-primary" id="startBtn" onclick="startInterview()">Start Interview &rarr;</button>
    </div>
  </div>

  <!-- Step 2-4: Chat -->
  <div id="chatSection" style="display:none">
    <div class="chat-container">
      <div class="chat-messages" id="chatMessages"></div>
      <div class="chat-input-wrap">
        <textarea class="chat-input" id="chatInput" rows="1"
          placeholder="Type your answer..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendAnswer()}"></textarea>
        <button class="chat-send" id="sendBtn" onclick="sendAnswer()">Send</button>
      </div>
    </div>
  </div>

  <!-- Step 3/5: Spec Preview -->
  <div id="specSection" style="display:none">
    <div class="spec-preview">
      <pre id="specContent">Loading spec...</pre>
    </div>
    <div class="spec-actions" id="specActions"></div>
  </div>
</div>

<script>
var sessionId = null;
var eventSource = null;
var currentStep = 1;
var waitingForAI = false;
var lastEventId = 0;
var streamingMsgEl = null; // current streaming message element
var streamingText = ''; // accumulated streaming text
var pendingUserMsg = false; // skip SSE echo of optimistic user message

// Pre-fill from inbox promotion
var _inboxParams = new URLSearchParams(window.location.search);
var _inboxId = _inboxParams.get('inbox_id');
var _inboxContext = '';
if (_inboxId) {
  window.addEventListener('DOMContentLoaded', function() {
    var startBtn = document.getElementById('startBtn');
    if (startBtn) { startBtn.disabled = true; startBtn.textContent = 'Loading triage data...'; }
    fetch('/api/inbox/' + _inboxId)
      .then(function(r) { return r.json(); })
      .then(function(item) {
        var report = item.triage_report || {};
        var title = report.recommended_title || item.title || '';
        _inboxContext = report.draft_context || '';
        var ideaEl = document.getElementById('ideaInput');
        var slugEl = document.getElementById('slugInput');
        if (title && ideaEl) ideaEl.value = title;
        if (title && slugEl) slugEl.value = slugify(title);
        if (_inboxContext) {
          var escFull = _inboxContext.replace(/</g, '&lt;').replace(/\\n/g, '\\n');
          var escPreview = _inboxContext.substring(0, 120).replace(/</g, '&lt;') + (_inboxContext.length > 120 ? '\\u2026' : '');
          var banner = document.createElement('div');
          banner.className = 'triage-banner';
          banner.onclick = function() { this.classList.toggle('expanded'); };
          banner.innerHTML = '<strong>Triage context loaded</strong>' +
            '<span class="triage-toggle">\\u25B8 show</span>' +
            '<span class="triage-preview"> — ' + escPreview + '</span>' +
            '<div class="triage-full">' + escFull + '</div>';
          var form = document.getElementById('step1');
          if (form) form.insertBefore(banner, form.firstChild);
        }
        if (startBtn) { startBtn.disabled = false; startBtn.innerHTML = 'Start Interview \\u2192'; }
      })
      .catch(function(e) {
        console.warn('Failed to load inbox item:', e);
        if (startBtn) { startBtn.disabled = false; startBtn.innerHTML = 'Start Interview \\u2192'; }
      });
  });
}

function slugify(text) {
  return text.toLowerCase().trim()
    .replace(/[^\\w\\s-]/g, '')
    .replace(/[\\s_]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}

document.getElementById('ideaInput').addEventListener('input', function() {
  var slugInput = document.getElementById('slugInput');
  if (!slugInput.dataset.manual) {
    slugInput.value = slugify(this.value);
  }
});
document.getElementById('slugInput').addEventListener('input', function() {
  this.dataset.manual = this.value ? '1' : '';
});

function setStep(step) {
  currentStep = step;
  document.querySelectorAll('.step').forEach(function(el) {
    var s = parseInt(el.dataset.step);
    el.className = 'step' + (s === step ? ' active' : '') + (s < step ? ' done' : '');
  });

  document.getElementById('step1').style.display = step === 1 ? 'block' : 'none';
  // Steps 2,3,4: show chat (3=draft shows bouncing dots in chat area)
  document.getElementById('chatSection').style.display =
    (step === 2 || step === 3 || step === 4) ? 'block' : 'none';
  document.getElementById('specSection').style.display =
    step === 5 ? 'block' : 'none';

  // Hide chat input row during autonomous steps (draft=3)
  var chatInputWrap = document.querySelector('.chat-input-wrap');
  if (chatInputWrap) chatInputWrap.style.display = (step === 2 || step === 4) ? 'flex' : 'none';

  if (step === 5) { loadSpec(); showCommitActions(); }
}

function startInterview() {
  var idea = document.getElementById('ideaInput').value.trim();
  if (!idea) { document.getElementById('ideaInput').focus(); return; }

  var btn = document.getElementById('startBtn');
  btn.disabled = true;
  btn.textContent = 'Starting...';

  fetch('/api/interview/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      idea: idea,
      slug: document.getElementById('slugInput').value.trim() || slugify(idea),
      execution: document.getElementById('executionSelect').value,
      priority: document.getElementById('prioritySelect').value,
      epic: document.getElementById('epicInput').value.trim(),
      epicTitle: document.getElementById('epicTitleInput').value.trim(),
      totalBudget: document.getElementById('totalBudgetInput').value.trim(),
      triage_context: _inboxContext || '',
      inbox_id: _inboxId || null,
    })
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (data.error) {
      alert(data.error);
      btn.disabled = false;
      btn.textContent = 'Start Interview \\u2192';
      return;
    }
    sessionId = data.sessionId;
    sessionStorage.setItem('relay_interview_session', sessionId);
    if (data.syncWarnings && data.syncWarnings.length) {
      var banner = document.createElement('div');
      banner.className = 'sync-warning';
      banner.innerHTML = '\\u26A0 ' + data.syncWarnings.join(' \\u2022 ') +
        '<span onclick="this.parentNode.remove()" style="cursor:pointer;margin-left:12px;opacity:0.6">\\u2715</span>';
      document.getElementById('chatMessages').appendChild(banner);
    }
    setStep(2);
    waitingForAI = true;
    document.getElementById('sendBtn').disabled = true;
    showTypingIndicator();
    connectSSE();
  })
  .catch(function(err) {
    alert('Failed to start: ' + err.message);
    btn.disabled = false;
    btn.textContent = 'Start Interview \\u2192';
  });
}

function tryResumeSession() {
  var saved = sessionStorage.getItem('relay_interview_session');
  if (!saved) return;

  fetch('/api/interview/' + saved + '/state')
    .then(function(r) {
      if (!r.ok) throw new Error('gone');
      return r.json();
    })
    .then(function(state) {
      if (state.error) {
        sessionStorage.removeItem('relay_interview_session');
        return;
      }
      // Resume — reconnect to existing session
      sessionId = saved;
      lastEventId = 0; // replay full history
      setStep(state.step || 2);
      if (state.status !== 'complete') {
        waitingForAI = true;
        document.getElementById('sendBtn').disabled = true;
      }
      connectSSE();
    })
    .catch(function() {
      sessionStorage.removeItem('relay_interview_session');
    });
}

tryResumeSession();

function connectSSE() {
  if (eventSource) { try { eventSource.close(); } catch(ex) {} }
  eventSource = new EventSource('/api/interview/' + sessionId + '/stream?lastSeen=' + lastEventId);

  // Streaming tokens — build up message character by character
  eventSource.addEventListener('token', function(e) {
    var eid = parseInt(e.lastEventId || '0');
    if (eid && eid <= lastEventId) return;
    if (eid) lastEventId = eid;
    var data = JSON.parse(e.data);
    removeTypingIndicator();

    // Split on double-newline — each paragraph becomes a separate chat bubble
    var newText = data.text;
    if (newText.indexOf('\\n\\n') !== -1 && streamingMsgEl && streamingText.length > 20) {
      var parts = newText.split('\\n\\n');
      // Finish current bubble with first part
      streamingText += parts[0];
      streamingMsgEl.innerHTML = renderMarkdown(streamingText);
      // Start new bubbles for remaining parts
      for (var i = 1; i < parts.length; i++) {
        streamingMsgEl = document.createElement('div');
        streamingMsgEl.className = 'chat-msg ai';
        document.getElementById('chatMessages').appendChild(streamingMsgEl);
        streamingText = parts[i];
        streamingMsgEl.innerHTML = renderMarkdown(streamingText);
      }
    } else {
      if (!streamingMsgEl) {
        streamingMsgEl = document.createElement('div');
        streamingMsgEl.className = 'chat-msg ai';
        document.getElementById('chatMessages').appendChild(streamingMsgEl);
      }
      streamingText += newText;
      streamingMsgEl.innerHTML = renderMarkdown(streamingText);
    }
    autoScroll(document.getElementById('chatMessages'));
  });

  // Loading message — show as AI bubble + typing indicator
  eventSource.addEventListener('loading', function(e) {
    var eid = parseInt(e.lastEventId || '0');
    if (eid && eid <= lastEventId) return;
    if (eid) lastEventId = eid;
    var data = JSON.parse(e.data);
    removeTypingIndicator();
    if (streamingMsgEl) { streamingMsgEl = null; streamingText = ''; }
    addMessage('ai', data.text);
    showTypingIndicator();
    if (data.step && data.step !== currentStep) setStep(data.step);
  });

  // Complete message — finalize streaming or show full message
  eventSource.addEventListener('message', function(e) {
    var eid = parseInt(e.lastEventId || '0');
    if (eid && eid <= lastEventId) return;
    if (eid) lastEventId = eid;
    var data = JSON.parse(e.data);
    removeTypingIndicator();

    // If we were streaming, finalize that message
    if (streamingMsgEl) {
      streamingMsgEl.innerHTML = renderMarkdown(streamingText);
      streamingMsgEl = null;
      streamingText = '';
    } else {
      // Non-streamed message (e.g. replayed from history)
      addMessage('ai', data.text);
    }
    waitingForAI = false;
    document.getElementById('sendBtn').disabled = false;
  });

  // User message replay (for session restore on refresh)
  eventSource.addEventListener('user_message', function(e) {
    var eid = parseInt(e.lastEventId || '0');
    if (eid && eid <= lastEventId) return;
    if (eid) lastEventId = eid;
    if (pendingUserMsg) { pendingUserMsg = false; return; }
    var data = JSON.parse(e.data);
    addMessage('user', data.text);
  });

  eventSource.addEventListener('status', function(e) {
    var eid = parseInt(e.lastEventId || '0');
    if (eid && eid <= lastEventId) return; // skip already-seen replay
    if (eid) lastEventId = eid;
    var data = JSON.parse(e.data);
    removeTypingIndicator();
    addMessage('system', data.text);
    if (data.step && data.step !== currentStep) {
      setStep(data.step);
    }
  });

  eventSource.addEventListener('error', function(e) {
    var data = {};
    try { data = JSON.parse(e.data); } catch(ex) {}
    if (data.text) addMessage('system', 'Error: ' + data.text);
  });

  eventSource.addEventListener('finalize', function(e) {
    var eid = parseInt(e.lastEventId || '0');
    if (eid && eid <= lastEventId) return;
    if (eid) lastEventId = eid;
    removeTypingIndicator();
    if (streamingMsgEl) {
      streamingMsgEl = null;
      streamingText = '';
    }
    setStep(5);
  });

  eventSource.addEventListener('done', function() {
    eventSource.close();
    removeTypingIndicator();
    if (currentStep < 5) setStep(5);
  });

  eventSource.onerror = function() {
    // SSE drops when tab is backgrounded — reconnect instead of ending
    if (eventSource.readyState === EventSource.CLOSED) {
      // Check if the session is actually done before giving up
      fetch('/api/interview/' + sessionId + '/state')
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.status === 'complete') {
            setStep(5);
          } else {
            // Session still active — reconnect after a short delay
            setTimeout(function() { connectSSE(); }, 2000);
          }
        })
        .catch(function() {
          // Server unreachable — retry once more
          setTimeout(function() { connectSSE(); }, 5000);
        });
    }
  };
}

function sendAnswer() {
  var input = document.getElementById('chatInput');
  var text = input.value.trim();
  if (!text || waitingForAI) return;

  pendingUserMsg = true;
  addMessage('user', text);
  // Force scroll to bottom after sending — so auto-scroll follows the AI reply
  var msgs = document.getElementById('chatMessages');
  msgs.scrollTop = msgs.scrollHeight;
  input.value = '';
  input.style.height = 'auto';
  waitingForAI = true;
  document.getElementById('sendBtn').disabled = true;
  showTypingIndicator();

  fetch('/api/interview/' + sessionId + '/answer', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text: text})
  });
}

function autoScroll(el) {
  // Only scroll if user is near the bottom (within 150px)
  // This lets users scroll up to read without being yanked back,
  // but follows along when they're at/near the bottom
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 150) {
    el.scrollTop = el.scrollHeight;
  }
}

function renderMarkdown(text) {
  return text
    .replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
    .replace(/\\n/g, '<br>');
}

function addMessage(role, text) {
  var messages = document.getElementById('chatMessages');
  var div = document.createElement('div');
  div.className = 'chat-msg ' + role;
  div.innerHTML = renderMarkdown(text);
  messages.appendChild(div);
  autoScroll(messages);
}

function showTypingIndicator() {
  var messages = document.getElementById('chatMessages');
  if (document.getElementById('typingIndicator')) return;
  var div = document.createElement('div');
  div.id = 'typingIndicator';
  div.className = 'typing-indicator';
  div.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
  messages.appendChild(div);
  autoScroll(messages);
}

function removeTypingIndicator() {
  var el = document.getElementById('typingIndicator');
  if (el) el.remove();
}

function loadSpec() {
  // Fetch validation and spec in parallel
  Promise.all([
    fetch('/api/interview/' + sessionId + '/validate').then(function(r) { return r.json(); }),
    fetch('/api/interview/' + sessionId + '/spec').then(function(r) { return r.json(); }),
  ]).then(function(results) {
    var validation = results[0];
    var spec = results[1];

    // Build validation HTML
    var valHtml = '<div class="validation-results"><div class="validation-title">Validation</div>';
    if (validation.checks) {
      validation.checks.forEach(function(check) {
        var cls = check.pass ? 'validation-pass' : 'validation-warn';
        var icon = check.pass ? '\\u2713' : '\\u26A0';
        valHtml += '<div class="validation-check ' + cls + '">' + icon + ' ' + check.label + '</div>';
      });
    }
    valHtml += '</div>';

    // Set spec content with validation above it
    var specEl = document.getElementById('specContent');
    specEl.innerHTML = valHtml + '<pre style="margin:0">' +
      (spec.content || 'Spec not yet written...').replace(/&/g,'&amp;').replace(/</g,'&lt;') +
      '</pre>';
  });
}

function showCommitActions() {
  document.getElementById('specActions').innerHTML =
    '<button class="btn-secondary" onclick="setStep(4)">Back to Chat</button>' +
    '<button class="btn-primary" id="commitBtn" onclick="commitSpec()">Commit &amp; Finish</button>';
}

function commitSpec() {
  var btn = document.getElementById('commitBtn');
  btn.disabled = true;
  btn.textContent = 'Committing...';

  fetch('/api/interview/' + sessionId + '/commit', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (data.error) {
      alert('Error: ' + data.error);
      btn.disabled = false;
      btn.textContent = 'Commit & Finish';
      return;
    }
    document.getElementById('specActions').innerHTML =
      '<div style="text-align:center;width:100%">' +
      '<p style="color:var(--green);font-weight:600;margin-bottom:12px">' +
      (data.committed ? '\\u2713 ' + data.message : data.message) + '</p>' +
      '<div style="display:flex;gap:12px;justify-content:center">' +
      '<a href="/" class="btn-secondary" style="display:inline-block;text-decoration:none">Back to Command Center</a>' +
      '<button class="btn-primary" onclick="window.location.href=\\\'/plan/' + data.specPath.replace(/.*\\//, '').replace('-feature.md','') + '\\\'">Continue to Planning</button>' +
      '</div></div>';
  });
}

document.getElementById('chatInput').addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});
</script>
</body>
</html>
"""


PLAN_WIZARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Plan Feature — Relay</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0%25' stop-color='%2334d399'/><stop offset='50%25' stop-color='%23818cf8'/><stop offset='100%25' stop-color='%23ec4899'/></linearGradient></defs><rect width='32' height='32' rx='8' fill='url(%23g)'/><text x='16' y='22' text-anchor='middle' font-family='sans-serif' font-weight='800' font-size='18' fill='white'>R</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --font-body: 'DM Sans', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --bg: #0a0e27; --bg-card: rgba(255,255,255,0.04); --bg-detail: rgba(0,0,0,0.2);
  --bg-input: rgba(255,255,255,0.05); --border: rgba(255,255,255,0.08);
  --border-hover: rgba(255,255,255,0.18); --text-primary: #e8ecf4;
  --text-secondary: #94a3b8; --text-muted: #475569; --accent: #818cf8;
  --green: #34d399; --amber: #fbbf24; --red: #f87171;
  --radius: 16px; --transition: 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--font-body); background: var(--bg); color: var(--text-primary); min-height: 100vh; }
body::before {
  content: ''; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background: radial-gradient(ellipse 50% 50% at 20% 30%, rgba(0,212,170,0.12), transparent),
    radial-gradient(ellipse 40% 40% at 80% 20%, rgba(124,58,237,0.10), transparent),
    radial-gradient(ellipse 45% 45% at 60% 80%, rgba(59,130,246,0.08), transparent);
  animation: aurora 20s ease-in-out infinite;
}
@keyframes aurora { 0%,100%{background-position:0% 50%,100% 50%,50% 0%} 50%{background-position:50% 100%,50% 0%,0% 50%} }
.navbar { position:sticky;top:0;z-index:100;background:rgba(10,14,39,0.8);backdrop-filter:blur(30px);border-bottom:1px solid var(--border);padding:0 24px;height:56px;display:flex;align-items:center;justify-content:space-between; }
.nav-left { display:flex;align-items:center;gap:12px; }
.nav-logo { width:28px;height:28px;border-radius:10px;background:linear-gradient(135deg,var(--green),var(--accent),#ec4899);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px;color:#fff; }
.nav-title { font-weight:700;font-size:15px; }
.nav-back { color:var(--text-secondary);text-decoration:none;font-size:13px;font-weight:600;padding:6px 12px;border-radius:8px;border:1px solid var(--border);transition:all var(--transition); }
.nav-back:hover { border-color:var(--border-hover);color:var(--text-primary); }
.steps { display:flex;align-items:center;justify-content:center;gap:0;padding:20px 24px 0; }
.step { display:flex;align-items:center;gap:8px;padding:8px 16px;font-size:12px;font-weight:600;color:var(--text-muted);transition:all var(--transition); }
.step.active { color:var(--accent); }
.step.done { color:var(--green); }
.step-num { width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;background:rgba(255,255,255,0.06);border:1px solid var(--border);transition:all var(--transition); }
.step.active .step-num { background:rgba(129,140,248,0.15);border-color:var(--accent);color:var(--accent);box-shadow:0 0 12px rgba(129,140,248,0.2); }
.step.done .step-num { background:rgba(52,211,153,0.15);border-color:var(--green);color:var(--green); }
.step-connector { width:32px;height:1px;background:var(--border);flex-shrink:0; }
.main { max-width:900px;margin:0 auto;padding:24px; }
.chat-container { display:flex;flex-direction:column;height:calc(100vh - 180px);background:var(--bg-card);backdrop-filter:blur(24px);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;animation:fadeUp 0.5s ease-out; }
.chat-messages { flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:16px; }
.chat-msg { max-width:80%;padding:12px 16px;border-radius:12px;font-size:13px;line-height:1.6;animation:fadeUp 0.3s ease-out; }
.chat-msg.ai { align-self:flex-start;background:var(--bg-detail);border:1px solid var(--border);color:var(--text-primary); }
.chat-msg.user { align-self:flex-end;background:rgba(129,140,248,0.15);border:1px solid rgba(129,140,248,0.25);color:var(--text-primary); }
.chat-msg.system { align-self:center;max-width:90%;background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.15);color:var(--green);text-align:center;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;padding:8px 16px; }
.chat-msg pre { background:rgba(0,0,0,0.3);border-radius:6px;padding:10px 12px;margin:8px 0;overflow-x:auto;font-family:var(--font-mono);font-size:12px; }
.chat-msg code { font-family:var(--font-mono);font-size:12px;background:rgba(0,0,0,0.2);padding:2px 5px;border-radius:3px; }
.typing-indicator { display:flex;gap:4px;padding:12px 16px;align-self:flex-start; }
.typing-dot { width:6px;height:6px;border-radius:50%;background:var(--text-muted);animation:typingBounce 1.4s infinite; }
.typing-dot:nth-child(2) { animation-delay:0.2s; } .typing-dot:nth-child(3) { animation-delay:0.4s; }
@keyframes typingBounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-6px)} }
.chat-input-wrap { display:flex;gap:8px;padding:16px;border-top:1px solid var(--border);background:rgba(0,0,0,0.15);align-items:flex-end; }
.chat-input { flex:1;padding:12px 16px;background:var(--bg-input);border:1px solid var(--border);border-radius:12px;color:var(--text-primary);font-family:var(--font-body);font-size:14px;resize:none;min-height:44px;max-height:120px; }
.chat-input:focus { outline:none;border-color:var(--accent); }
.chat-send { padding:0 20px;height:44px;border-radius:12px;border:none;background:var(--accent);color:#fff;font-size:14px;font-weight:600;cursor:pointer;transition:all var(--transition);flex-shrink:0; }
.chat-send:hover { box-shadow:0 0 20px rgba(129,140,248,0.3); }
.chat-send:disabled { opacity:0.4;cursor:not-allowed; }
.spec-preview { background:var(--bg-card);backdrop-filter:blur(24px);border:1px solid var(--border);border-radius:var(--radius);padding:28px;max-height:calc(100vh - 240px);overflow-y:auto; }
.spec-preview pre { font-family:var(--font-mono);font-size:12px;line-height:1.6;color:var(--text-primary);white-space:pre-wrap;word-wrap:break-word; }
.spec-actions { display:flex;gap:12px;justify-content:flex-end;margin-top:20px; }
.btn-primary { padding:10px 24px;border-radius:8px;border:none;background:var(--accent);color:#fff;font-size:14px;font-weight:600;cursor:pointer;transition:all var(--transition);box-shadow:0 0 20px rgba(129,140,248,0.2); }
.btn-primary:hover { box-shadow:0 0 30px rgba(129,140,248,0.4);transform:translateY(-1px); }
.btn-primary:disabled { opacity:0.4;cursor:not-allowed;box-shadow:none;transform:none; }
.btn-secondary { padding:10px 24px;border-radius:8px;border:1px solid var(--border);background:transparent;color:var(--text-secondary);font-size:14px;font-weight:600;cursor:pointer;transition:all var(--transition); }
.btn-secondary:hover { border-color:var(--border-hover);color:var(--text-primary); }
@keyframes fadeUp { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }
</style>
</head>
<body>
<nav class="navbar">
  <div class="nav-left"><div class="nav-logo">R</div><span class="nav-title">Plan: __SLUG__</span></div>
  <a href="/" class="nav-back">&larr; Command Center</a>
</nav>
<div class="steps">
  <div class="step done" data-step="1"><span class="step-num">1</span> Feature</div>
  <div class="step-connector"></div>
  <div class="step active" data-step="2"><span class="step-num">2</span> Plan</div>
  <div class="step-connector"></div>
  <div class="step" data-step="3"><span class="step-num">3</span> Finalize</div>
</div>
<div class="main" id="mainContent">
  <div id="chatSection">
    <div class="chat-container">
      <div class="chat-messages" id="chatMessages"></div>
      <div class="chat-input-wrap">
        <textarea class="chat-input" id="chatInput" rows="1" placeholder="Type your answer..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendAnswer()}"></textarea>
        <button class="chat-send" id="sendBtn" onclick="sendAnswer()">Send</button>
      </div>
    </div>
  </div>
  <div id="specSection" style="display:none">
    <div class="spec-preview"><pre id="specContent">Loading...</pre></div>
    <div class="spec-actions" id="specActions"></div>
  </div>
</div>
<script>
var sessionId = null;
var eventSource = null;
var currentStep = 2;
var waitingForAI = true;
var lastEventId = 0;
var streamingMsgEl = null;
var streamingText = '';
var pendingUserMsg = false;
var slug = '__SLUG__';

// Try to resume existing session, or start a new one
function startNewPlanSession() {
  showTypingIndicator();
  fetch('/api/plan/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ slug: slug })
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (data.error) { alert(data.error); return; }
    sessionId = data.sessionId;
    sessionStorage.setItem('relay_plan_session_' + slug, sessionId);
    connectSSE();
  })
  .catch(function(err) { alert('Failed to start: ' + err.message); });
}

(function tryResumePlanSession() {
  var saved = sessionStorage.getItem('relay_plan_session_' + slug);
  if (!saved) { startNewPlanSession(); return; }

  fetch('/api/interview/' + saved + '/state')
    .then(function(r) {
      if (!r.ok) throw new Error('gone');
      return r.json();
    })
    .then(function(state) {
      if (state.error) {
        sessionStorage.removeItem('relay_plan_session_' + slug);
        startNewPlanSession();
        return;
      }
      sessionId = saved;
      lastEventId = 0;
      if (state.step) currentStep = state.step;
      if (state.status !== 'complete') {
        waitingForAI = true;
      }
      connectSSE();
    })
    .catch(function() {
      sessionStorage.removeItem('relay_plan_session_' + slug);
      startNewPlanSession();
    });
})();

function connectSSE() {
  if (eventSource) { try { eventSource.close(); } catch(ex) {} }
  eventSource = new EventSource('/api/interview/' + sessionId + '/stream?lastSeen=' + lastEventId);

  eventSource.addEventListener('token', function(e) {
    var eid = parseInt(e.lastEventId || '0');
    if (eid && eid <= lastEventId) return;
    if (eid) lastEventId = eid;
    var data = JSON.parse(e.data);
    removeTypingIndicator();
    var newText = data.text;
    if (newText.indexOf('\\n\\n') !== -1 && streamingMsgEl && streamingText.length > 20) {
      var parts = newText.split('\\n\\n');
      streamingText += parts[0];
      streamingMsgEl.innerHTML = renderMarkdown(streamingText);
      for (var i = 1; i < parts.length; i++) {
        streamingMsgEl = document.createElement('div');
        streamingMsgEl.className = 'chat-msg ai';
        document.getElementById('chatMessages').appendChild(streamingMsgEl);
        streamingText = parts[i];
        streamingMsgEl.innerHTML = renderMarkdown(streamingText);
      }
    } else {
      if (!streamingMsgEl) {
        streamingMsgEl = document.createElement('div');
        streamingMsgEl.className = 'chat-msg ai';
        document.getElementById('chatMessages').appendChild(streamingMsgEl);
      }
      streamingText += newText;
      streamingMsgEl.innerHTML = renderMarkdown(streamingText);
    }
    autoScroll(document.getElementById('chatMessages'));
  });

  eventSource.addEventListener('message', function(e) {
    var eid = parseInt(e.lastEventId || '0');
    if (eid && eid <= lastEventId) return;
    if (eid) lastEventId = eid;
    var data = JSON.parse(e.data);
    removeTypingIndicator();
    if (streamingMsgEl) { streamingMsgEl = null; streamingText = ''; }
    else { addMessage('ai', data.text); }
    waitingForAI = false;
    document.getElementById('sendBtn').disabled = false;
  });

  eventSource.addEventListener('user_message', function(e) {
    var eid = parseInt(e.lastEventId || '0');
    if (eid && eid <= lastEventId) return;
    if (eid) lastEventId = eid;
    if (pendingUserMsg) { pendingUserMsg = false; return; }
    var data = JSON.parse(e.data);
    addMessage('user', data.text);
  });

  eventSource.addEventListener('loading', function(e) {
    var eid = parseInt(e.lastEventId || '0');
    if (eid && eid <= lastEventId) return;
    if (eid) lastEventId = eid;
    var data = JSON.parse(e.data);
    removeTypingIndicator();
    if (streamingMsgEl) { streamingMsgEl = null; streamingText = ''; }
    addMessage('ai', data.text);
    showTypingIndicator();
  });

  eventSource.addEventListener('finalize', function(e) {
    removeTypingIndicator();
    currentStep = 3;
    document.querySelectorAll('.step').forEach(function(el) {
      var s = parseInt(el.dataset.step);
      el.className = 'step' + (s === 3 ? ' active' : ' done');
    });
    document.getElementById('chatSection').style.display = 'none';
    document.getElementById('specSection').style.display = 'block';
    document.getElementById('specContent').textContent = 'Planning complete. Tasks have been written.';
    document.getElementById('specActions').innerHTML =
      '<a href="/" class="btn-secondary" style="display:inline-block;text-decoration:none">Back to Command Center</a>' +
      '<button class="btn-primary" id="planCommitBtn" onclick="commitPlan()">Commit &amp; Push</button>';
  });

  eventSource.addEventListener('done', function() {
    eventSource.close();
    removeTypingIndicator();
  });

  eventSource.addEventListener('status', function(e) {
    var eid = parseInt(e.lastEventId || '0');
    if (eid && eid <= lastEventId) return;
    if (eid) lastEventId = eid;
    var data = JSON.parse(e.data);
    removeTypingIndicator();
    addMessage('system', data.text);
  });

  eventSource.addEventListener('error', function(e) {
    var data = {};
    try { data = JSON.parse(e.data); } catch(ex) {}
    if (data.text) addMessage('system', 'Error: ' + data.text);
  });

  eventSource.onerror = function() {
    if (eventSource.readyState === EventSource.CLOSED) {
      fetch('/api/interview/' + sessionId + '/state')
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.status !== 'complete') setTimeout(connectSSE, 2000);
        }).catch(function() { setTimeout(connectSSE, 5000); });
    }
  };
}

function sendAnswer() {
  var input = document.getElementById('chatInput');
  var text = input.value.trim();
  if (!text || waitingForAI) return;
  pendingUserMsg = true;
  addMessage('user', text);
  var msgs = document.getElementById('chatMessages');
  msgs.scrollTop = msgs.scrollHeight;
  input.value = '';
  waitingForAI = true;
  document.getElementById('sendBtn').disabled = true;
  showTypingIndicator();
  fetch('/api/interview/' + sessionId + '/answer', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text: text})
  });
}

function autoScroll(el) {
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 150) {
    el.scrollTop = el.scrollHeight;
  }
}

function renderMarkdown(text) {
  return text.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
    .replace(/\\n/g, '<br>');
}

function addMessage(role, text) {
  var messages = document.getElementById('chatMessages');
  var div = document.createElement('div');
  div.className = 'chat-msg ' + role;
  div.innerHTML = renderMarkdown(text);
  messages.appendChild(div);
  autoScroll(messages);
}

function showTypingIndicator() {
  var messages = document.getElementById('chatMessages');
  if (document.getElementById('typingIndicator')) return;
  var div = document.createElement('div');
  div.id = 'typingIndicator';
  div.className = 'typing-indicator';
  div.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
  messages.appendChild(div);
  autoScroll(messages);
}

function removeTypingIndicator() {
  var el = document.getElementById('typingIndicator');
  if (el) el.remove();
}

document.getElementById('chatInput').addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

function commitPlan() {
  var btn = document.getElementById('planCommitBtn');
  btn.disabled = true;
  btn.textContent = 'Committing & pushing...';

  fetch('/api/plan/' + sessionId + '/commit', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (data.error) {
      alert('Error: ' + data.error);
      btn.disabled = false;
      btn.textContent = 'Commit & Push';
      return;
    }
    var msg = data.committed
      ? '\\u2713 ' + data.message + (data.pushed ? ' (pushed to remote)' : ' (push failed)')
      : data.message;
    document.getElementById('specActions').innerHTML =
      '<div style="text-align:center;width:100%">' +
      '<p style="color:var(--green);font-weight:600;margin-bottom:12px">' + msg + '</p>' +
      '<a href="/" class="btn-primary" style="display:inline-block;text-decoration:none">Back to Command Center</a>' +
      '</div>';
  });
}
</script>
</body>
</html>
"""


# ── Agents Grid HTML ─────────────────────────────────────────────

AGENTS_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent Workforce — Relay</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0%25' stop-color='%2334d399'/><stop offset='50%25' stop-color='%23818cf8'/><stop offset='100%25' stop-color='%23ec4899'/></linearGradient></defs><rect width='32' height='32' rx='8' fill='url(%23g)'/><text x='16' y='22' text-anchor='middle' font-family='sans-serif' font-weight='800' font-size='18' fill='white'>R</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --font-body: 'DM Sans', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --bg: #0a0e27;
  --bg-card: rgba(255,255,255,0.04);
  --border: rgba(255,255,255,0.08);
  --border-hover: rgba(255,255,255,0.18);
  --text-primary: #e8ecf4;
  --text-secondary: #94a3b8;
  --text-muted: #475569;
  --accent: #818cf8;
  --green: #34d399;
  --blue: #818cf8;
  --radius: 16px;
  --transition: 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--font-body); background: var(--bg); color: var(--text-primary);
  min-height: 100vh;
}
body::before {
  content: ''; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background:
    radial-gradient(ellipse 50% 50% at 20% 30%, rgba(0,212,170,0.12), transparent),
    radial-gradient(ellipse 40% 40% at 80% 20%, rgba(124,58,237,0.10), transparent),
    radial-gradient(ellipse 45% 45% at 60% 80%, rgba(59,130,246,0.08), transparent),
    radial-gradient(ellipse 35% 35% at 10% 80%, rgba(236,72,153,0.06), transparent);
  animation: aurora 20s ease-in-out infinite;
}
@keyframes aurora {
  0%, 100% { background-position: 0% 50%, 100% 50%, 50% 0%, 0% 100%; }
  25% { background-position: 100% 0%, 0% 100%, 50% 50%, 100% 0%; }
  50% { background-position: 50% 100%, 50% 0%, 0% 50%, 50% 50%; }
  75% { background-position: 0% 50%, 100% 50%, 100% 100%, 0% 0%; }
}

/* ── Nav ── */
.navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(10,14,39,0.8); backdrop-filter: blur(30px);
  border-bottom: 1px solid var(--border);
  padding: 0 24px; height: 56px;
  display: flex; align-items: center; justify-content: space-between;
}
.nav-left { display: flex; align-items: center; gap: 12px; }
.nav-logo {
  width: 28px; height: 28px; border-radius: 10px;
  background: linear-gradient(135deg, var(--green), var(--blue), #ec4899);
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 14px; color: #fff;
  box-shadow: 0 0 20px rgba(129,140,248,0.3);
}
.nav-title { font-weight: 700; font-size: 15px; }
.nav-back {
  color: var(--text-secondary); text-decoration: none; font-size: 13px;
  transition: color 0.2s;
}
.nav-back:hover { color: var(--text-primary); }

/* ── Grid ── */
.page-wrap {
  max-width: 960px; width: 100%; margin: 0 auto; padding: 40px 24px;
}
.page-title { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
.page-subtitle { color: var(--text-secondary); font-size: 14px; margin-bottom: 32px; }

.agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.agent-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  cursor: pointer;
  transition: border-color var(--transition), transform 0.2s, box-shadow 0.3s;
  text-decoration: none;
  color: inherit;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.agent-card:hover {
  border-color: var(--border-hover);
  transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.agent-card-header {
  display: flex; align-items: center; gap: 12px;
}
.agent-icon {
  width: 40px; height: 40px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px;
}
.agent-icon.chat { background: rgba(52,211,153,0.15); color: var(--green); }
.agent-icon.triage { background: rgba(251,191,36,0.15); color: #fbbf24; }
.agent-icon.diagnostics { background: rgba(248,113,113,0.15); color: #f87171; }
.agent-icon.feature { background: rgba(129,140,248,0.15); color: var(--accent); }
.agent-icon.planning { background: rgba(56,189,248,0.15); color: #38bdf8; }
.agent-name { font-weight: 600; font-size: 16px; }
.agent-desc {
  color: var(--text-secondary); font-size: 13px; line-height: 1.5;
}
.agent-badge {
  display: inline-block;
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 3px 8px; border-radius: 6px;
  margin-top: auto;
}
.agent-badge.interactive { background: rgba(52,211,153,0.15); color: var(--green); }
.agent-badge.orchestrated { background: rgba(129,140,248,0.15); color: var(--accent); }
</style>
</head>
<body>
<nav class="navbar">
  <div class="nav-left">
    <div class="nav-logo">R</div>
    <span class="nav-title">Relay</span>
  </div>
  <a href="/" class="nav-back">Command Center</a>
</nav>

<div class="page-wrap">
  <h1 class="page-title">Agent Workforce</h1>
  <p class="page-subtitle">Launch an agent to explore, analyze, or build.</p>

  <div class="agent-grid">

    <a class="agent-card" href="/agent/chat">
      <div class="agent-card-header">
        <div class="agent-icon chat">&#x1f4ac;</div>
        <span class="agent-name">Chat Agent</span>
      </div>
      <div class="agent-desc">Explore the codebase and ask questions. Chat about ideas and optionally escalate to a feature spec.</div>
      <span class="agent-badge interactive">Interactive</span>
    </a>

    <a class="agent-card" href="/agent/triage">
      <div class="agent-card-header">
        <div class="agent-icon triage">&#x1f50d;</div>
        <span class="agent-name">Triage Agent</span>
      </div>
      <div class="agent-desc">Analyze signals and assess impact. Investigate incoming issues and produce structured triage reports.</div>
      <span class="agent-badge interactive">Interactive</span>
    </a>

    <a class="agent-card" href="/agent/diagnostics">
      <div class="agent-card-header">
        <div class="agent-icon diagnostics">&#x1f6e0;</div>
        <span class="agent-name">Diagnostics Agent</span>
      </div>
      <div class="agent-desc">Trace errors to root cause. Analyze telemetry, stack traces, and code to identify what went wrong.</div>
      <span class="agent-badge interactive">Interactive</span>
    </a>

    <a class="agent-card" href="/interview">
      <div class="agent-card-header">
        <div class="agent-icon feature">&#x2728;</div>
        <span class="agent-name">Feature Agent</span>
      </div>
      <div class="agent-desc">Define a new feature through a guided interview, drafting, and refinement workflow.</div>
      <span class="agent-badge orchestrated">Orchestrated</span>
    </a>

    <a class="agent-card" id="planning-card" href="/plan">
      <div class="agent-card-header">
        <div class="agent-icon planning">&#x1f9e9;</div>
        <span class="agent-name">Planning Agent</span>
      </div>
      <div class="agent-desc">Decompose a feature into tasks organized by wave, repo, and priority.</div>
      <span class="agent-badge orchestrated">Orchestrated</span>
    </a>

  </div>
</div>

<script>
// Planning agent needs a feature slug — show a picker
document.getElementById('planning-card').addEventListener('click', function(e) {
  e.preventDefault();
  const slug = prompt('Enter the feature slug to plan (e.g. user-auth-v2):');
  if (slug && slug.trim()) {
    window.location.href = '/plan/' + slug.trim();
  }
});
</script>
</body>
</html>
"""


# ── Agent HTML ───────────────────────────────────────────────────

AGENT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__AGENT_NAME__ — Relay</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0%25' stop-color='%2334d399'/><stop offset='50%25' stop-color='%23818cf8'/><stop offset='100%25' stop-color='%23ec4899'/></linearGradient></defs><rect width='32' height='32' rx='8' fill='url(%23g)'/><text x='16' y='22' text-anchor='middle' font-family='sans-serif' font-weight='800' font-size='18' fill='white'>R</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --font-body: 'DM Sans', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --bg: #0a0e27;
  --bg-card: rgba(255,255,255,0.04);
  --bg-detail: rgba(0,0,0,0.2);
  --bg-input: rgba(255,255,255,0.05);
  --border: rgba(255,255,255,0.08);
  --border-hover: rgba(255,255,255,0.18);
  --text-primary: #e8ecf4;
  --text-secondary: #94a3b8;
  --text-muted: #475569;
  --accent: #818cf8;
  --green: #34d399;
  --blue: #818cf8;
  --radius: 16px;
  --transition: 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--font-body); background: var(--bg); color: var(--text-primary);
  min-height: 100vh; display: flex; flex-direction: column;
}
body::before {
  content: ''; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background:
    radial-gradient(ellipse 50% 50% at 20% 30%, rgba(0,212,170,0.12), transparent),
    radial-gradient(ellipse 40% 40% at 80% 20%, rgba(124,58,237,0.10), transparent),
    radial-gradient(ellipse 45% 45% at 60% 80%, rgba(59,130,246,0.08), transparent),
    radial-gradient(ellipse 35% 35% at 10% 80%, rgba(236,72,153,0.06), transparent);
  animation: aurora 20s ease-in-out infinite;
}
@keyframes aurora {
  0%, 100% { background-position: 0% 50%, 100% 50%, 50% 0%, 0% 100%; }
  25% { background-position: 100% 0%, 0% 100%, 50% 50%, 100% 0%; }
  50% { background-position: 50% 100%, 50% 0%, 0% 50%, 50% 50%; }
  75% { background-position: 0% 50%, 100% 50%, 100% 100%, 0% 0%; }
}

/* ── Nav ── */
.navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(10,14,39,0.8); backdrop-filter: blur(30px);
  border-bottom: 1px solid var(--border);
  padding: 0 24px; height: 56px;
  display: flex; align-items: center; justify-content: space-between;
}
.nav-left { display: flex; align-items: center; gap: 12px; }
.nav-logo {
  width: 28px; height: 28px; border-radius: 10px;
  background: linear-gradient(135deg, var(--green), var(--blue), #ec4899);
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 14px; color: #fff;
  box-shadow: 0 0 20px rgba(129,140,248,0.3);
}
.nav-title { font-weight: 700; font-size: 15px; }
.nav-back {
  color: var(--text-secondary); text-decoration: none; font-size: 13px;
  transition: color 0.2s;
}
.nav-back:hover { color: var(--text-primary); }

/* ── Chat layout (matches wizard) ── */
.chat-wrap {
  max-width: 800px; width: 100%; margin: 0 auto; padding: 20px 16px;
  flex: 1; display: flex; flex-direction: column;
}
.chat-container {
  flex: 1; display: flex; flex-direction: column;
  background: var(--bg-card); backdrop-filter: blur(24px);
  border: 1px solid var(--border); border-radius: 16px;
  overflow: hidden; animation: fadeUp 0.5s ease-out;
}
.chat-messages {
  flex: 1; overflow-y: auto; display: flex; flex-direction: column;
  gap: 16px; padding: 20px;
}
.chat-msg {
  max-width: 80%; padding: 12px 16px; border-radius: 12px;
  font-size: 13px; line-height: 1.6; animation: fadeUp 0.3s ease-out;
}
.chat-msg.ai {
  align-self: flex-start; background: var(--bg-detail);
  border: 1px solid var(--border); color: var(--text-primary);
}
.chat-msg.user {
  align-self: flex-end; background: rgba(129,140,248,0.15);
  border: 1px solid rgba(129,140,248,0.25); color: var(--text-primary);
}
.chat-msg pre {
  background: rgba(0,0,0,0.3); border-radius: 6px; padding: 10px 12px;
  margin: 8px 0; overflow-x: auto; font-family: var(--font-mono); font-size: 12px;
}
.chat-msg code {
  font-family: var(--font-mono); font-size: 12px;
  background: rgba(0,0,0,0.2); padding: 2px 5px; border-radius: 3px;
}
@keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

/* ── Typing indicator (matches wizard bouncy balls) ── */
.typing-indicator {
  display: flex; gap: 4px; padding: 12px 16px; align-self: flex-start;
}
.typing-dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--text-muted);
  animation: typingBounce 1.4s infinite;
}
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-6px); }
}

/* ── Loading indicator ── */
.loading-indicator {
  align-self: flex-start; padding: 8px 14px; border-radius: 10px;
  background: rgba(129,140,248,0.08); border: 1px solid rgba(129,140,248,0.15);
  color: var(--accent); font-size: 11px; font-weight: 600;
  display: flex; align-items: center; gap: 8px;
}
.loading-spinner {
  width: 12px; height: 12px; border: 2px solid rgba(129,140,248,0.3);
  border-top-color: var(--accent); border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Input area ── */
.chat-input-area {
  padding: 16px; border-top: 1px solid var(--border);
  display: flex; gap: 8px; align-items: flex-end;
  background: rgba(0,0,0,0.15);
}
.chat-input {
  flex: 1; background: var(--bg-input); border: 1px solid var(--border);
  border-radius: 12px; padding: 12px 16px; color: var(--text-primary);
  font-family: var(--font-body); font-size: 13px; resize: none;
  min-height: 44px; max-height: 150px; outline: none;
  transition: border-color 0.2s;
}
.chat-input:focus { border-color: var(--accent); }
.chat-input::placeholder { color: var(--text-muted); }
.send-btn {
  background: var(--accent); color: #fff; border: none; border-radius: 12px;
  padding: 12px 20px; font-family: var(--font-body); font-size: 13px;
  font-weight: 600; cursor: pointer; transition: opacity 0.2s;
  white-space: nowrap;
}
.send-btn:hover { opacity: 0.9; }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
</head>
<body>

<nav class="navbar">
  <div class="nav-left">
    <div class="nav-logo">R</div>
    <span class="nav-title">__AGENT_NAME__</span>
  </div>
  <a href="/agents" class="nav-back">&larr; Agent Workforce</a>
</nav>

<div class="chat-wrap">
  <div class="chat-container">
    <div class="chat-messages" id="chatMessages">
      <div style="text-align:center;padding:24px 16px 8px;">
        <div style="font-size:20px;font-weight:700;margin-bottom:4px;">__AGENT_NAME__ Agent</div>
        <div style="font-size:13px;color:var(--text-secondary);">__AGENT_DESC__</div>
      </div>
    </div>
    <div class="chat-input-area">
      <textarea class="chat-input" id="chatInput" rows="1"
        placeholder="Ask about the codebase..."
        onkeydown="handleKey(event)"></textarea>
      <button class="send-btn" id="sendBtn" onclick="sendMessage()">Send</button>
    </div>
  </div>
</div>

<script>
var sessionId = null;
var waitingForAI = false;
var lastEventId = 0;
var streamingMsgEl = null;
var streamingText = '';
var pendingUserMsg = false;

function autoScroll(el) {
  var threshold = 100;
  var isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
  if (isNearBottom) el.scrollTop = el.scrollHeight;
}

function renderMarkdown(text) {
  return text
    .replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
    .replace(/\\n/g, '<br>');
}

function addMessage(role, text) {
  var messages = document.getElementById('chatMessages');
  var div = document.createElement('div');
  div.className = 'chat-msg ' + role;
  div.innerHTML = renderMarkdown(text);
  messages.appendChild(div);
  autoScroll(messages);
  return div;
}

function showTypingIndicator() {
  var messages = document.getElementById('chatMessages');
  if (document.getElementById('typingIndicator')) return;
  var div = document.createElement('div');
  div.id = 'typingIndicator';
  div.className = 'typing-indicator';
  div.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
  messages.appendChild(div);
  autoScroll(messages);
}

function removeTypingIndicator() {
  var el = document.getElementById('typingIndicator');
  if (el) el.remove();
}

function showLoading(text) {
  removeLoading();
  var messages = document.getElementById('chatMessages');
  var div = document.createElement('div');
  div.id = 'loadingIndicator';
  div.className = 'loading-indicator';
  div.innerHTML = '<div class="loading-spinner"></div>' + text;
  messages.appendChild(div);
  autoScroll(messages);
}

function removeLoading() {
  var el = document.getElementById('loadingIndicator');
  if (el) el.remove();
}

function connectSSE() {
  var url = '/api/interview/' + sessionId + '/stream?lastSeen=' + lastEventId;
  var source = new EventSource(url);

  function handleEvent(e) {
    var data = JSON.parse(e.data);
    lastEventId = parseInt(e.lastEventId || '0');
    return data;
  }

  source.addEventListener('token', function(e) {
    var data = handleEvent(e);
    removeTypingIndicator();
    removeLoading();
    if (!streamingMsgEl) {
      streamingMsgEl = addMessage('ai', '');
      streamingText = '';
    }
    streamingText += data.text;
    streamingMsgEl.innerHTML = renderMarkdown(streamingText);
    autoScroll(document.getElementById('chatMessages'));
  });

  source.addEventListener('message', function(e) {
    var data = handleEvent(e);
    removeTypingIndicator();
    removeLoading();
    if (streamingMsgEl) {
      streamingMsgEl.innerHTML = renderMarkdown(data.text);
      checkForTriageReport(streamingMsgEl, data.text);
      streamingMsgEl = null;
      streamingText = '';
    } else {
      var msgEl = addMessage('ai', data.text);
      checkForTriageReport(msgEl, data.text);
    }
    waitingForAI = false;
    document.getElementById('sendBtn').disabled = false;
    document.getElementById('chatInput').focus();
  });

  source.addEventListener('user_message', function(e) {
    handleEvent(e);
    if (pendingUserMsg) { pendingUserMsg = false; }
    else { var data = JSON.parse(e.data); addMessage('user', data.text); }
  });

  source.addEventListener('loading', function(e) {
    var data = handleEvent(e);
    showLoading(data.text);
  });

  source.addEventListener('error', function(e) {
    if (e.data) {
      var data = JSON.parse(e.data);
      removeTypingIndicator();
      removeLoading();
      addMessage('ai', 'Error: ' + data.text);
      waitingForAI = false;
      document.getElementById('sendBtn').disabled = false;
    }
  });

  source.addEventListener('spec_brief', function(e) {
    handleEvent(e);
    removeTypingIndicator();
    removeLoading();
    if (streamingMsgEl) { streamingMsgEl = null; streamingText = ''; }
    addMessage('ai', 'Redirecting to Feature Agent...');
    setTimeout(function() {
      window.location.href = '/interview?from=chat&session=' + sessionId;
    }, 1000);
  });

  source.onerror = function() {
    source.close();
    setTimeout(connectSSE, 2000);
  };
}

var agentType = '__AGENT_TYPE__';
var _agentParams = new URLSearchParams(window.location.search);
var _inboxId = _agentParams.get('inbox_id');

function checkForTriageReport(msgEl, text) {
  if (!_inboxId) return;
  var match = text.match(/```json\\s*\\n(\\{[\\s\\S]*?\\})\\s*\\n```/);
  if (!match) return;
  try {
    var report = JSON.parse(match[1]);
    if (!report.verdict) return;

    // Replace the raw message with a readable summary card
    var severityColors = { critical: '#ef4444', high: '#f97316', medium: '#fbbf24', low: '#94a3b8' };
    var effortLabels = { small: 'Small', medium: 'Medium', large: 'Large' };
    var riskColors = { high: '#ef4444', medium: '#fbbf24', low: '#34d399' };
    var recLabels = {
      create_bug_spec: 'Create Bug Spec',
      create_feature_spec: 'Create Feature Spec',
      needs_more_info: 'Needs More Info',
      not_actionable: 'Not Actionable'
    };

    var html = '<div style="margin-bottom:4px;font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.5px">Triage Report</div>';

    // Verdict
    html += '<div style="font-size:15px;font-weight:600;color:var(--green);margin-bottom:12px">' + escapeHtml(report.verdict) + '</div>';

    // Chips: severity, effort, risk
    html += '<div style="display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap">';
    html += '<span style="font-size:12px;padding:3px 10px;border-radius:6px;background:rgba(255,255,255,0.06)">Severity: <strong style="color:' + (severityColors[report.severity] || '#94a3b8') + '">' + escapeHtml(report.severity || '?') + '</strong></span>';
    html += '<span style="font-size:12px;padding:3px 10px;border-radius:6px;background:rgba(255,255,255,0.06)">Effort: <strong>' + escapeHtml(effortLabels[report.effort] || report.effort || '?') + '</strong></span>';
    html += '<span style="font-size:12px;padding:3px 10px;border-radius:6px;background:rgba(255,255,255,0.06)">Risk: <strong style="color:' + (riskColors[report.risk] || '#94a3b8') + '">' + escapeHtml(report.risk || '?') + '</strong></span>';
    html += '</div>';

    // Context
    if (report.context) {
      html += '<div style="font-size:13px;color:#c0c0d0;line-height:1.7;margin-bottom:12px">' + escapeHtml(report.context) + '</div>';
    }

    // Affected files
    if (report.affected_files && report.affected_files.length) {
      html += '<div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">Affected files</div>';
      html += '<div style="font-family:var(--font-mono);font-size:12px;color:var(--text-secondary);margin-bottom:12px">' + report.affected_files.map(escapeHtml).join(', ') + '</div>';
    }

    // Recommendation
    html += '<div style="font-size:12px;color:var(--accent);font-weight:600;margin-bottom:14px">Recommendation: ' + escapeHtml(recLabels[report.recommendation] || report.recommendation || '?') + '</div>';

    // Confirm button
    html += '<div style="display:flex;gap:8px;align-items:center">';
    html += '<button class="send-btn" onclick="confirmTriageResult(this)" data-report=\\'' + JSON.stringify(report).replace(/'/g, '&#39;') + '\\'>';
    html += 'Confirm &amp; Save to Inbox</button>';
    html += '<span style="font-size:12px;color:var(--text-muted)">Marks item as actionable</span>';
    html += '</div>';

    msgEl.innerHTML = html;
    autoScroll(document.getElementById('chatMessages'));
  } catch(e) {}
}

function escapeHtml(s) {
  var d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}

function confirmTriageResult(btn) {
  var report = JSON.parse(btn.getAttribute('data-report'));
  btn.disabled = true;
  btn.textContent = 'Saving...';
  fetch('/api/inbox/' + _inboxId + '/triage-result', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(report),
  })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.ok) {
        btn.textContent = 'Saved';
        btn.style.background = 'var(--green)';
        btn.nextElementSibling.textContent = 'Item is now actionable in the inbox';
      } else {
        btn.textContent = 'Error: ' + (data.error || 'unknown');
        btn.disabled = false;
      }
    })
    .catch(function(e) {
      btn.textContent = 'Failed';
      btn.disabled = false;
    });
}

function startAgent() {
  function doStart(context) {
    showTypingIndicator();
    var payload = { type: agentType };
    if (context) payload.context = context;
    fetch('/api/agent/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        sessionId = data.sessionId;
        sessionStorage.setItem('relay_agent_session_' + agentType, sessionId);
        waitingForAI = true;
        document.getElementById('sendBtn').disabled = true;
        connectSSE();
      });
  }

  if (_inboxId) {
    var loadingMsg = addMessage('system', 'Loading inbox item...');
    loadingMsg.id = 'system-loading';
    // Set item to triaging status (interactive mode — no agent spawn)
    fetch('/api/inbox/' + _inboxId + '/triage?mode=interactive', { method: 'POST' }).catch(function() {});
    fetch('/api/inbox/' + _inboxId)
      .then(function(r) { return r.json(); })
      .then(function(item) {
        // Replace loading message with triage context
        var el = document.getElementById('system-loading');
        if (el) el.remove();
        addMessage('system', 'Triaging: ' + item.title);
        addMessage('ai', '**Source:** ' + item.source + ' (' + item.source_type + ')\\n\\n' +
          '**Payload:**\\n```json\\n' + JSON.stringify(item.payload, null, 2) + '\\n```');
        showTypingIndicator();

        var context = '## Inbox Item\\n\\n' +
          '**Title:** ' + item.title + '\\n' +
          '**Source:** ' + item.source + ' (' + item.source_type + ')\\n\\n' +
          '**Payload:**\\n```json\\n' + JSON.stringify(item.payload, null, 2) + '\\n```\\n\\n' +
          'Analyze this item and produce your triage report.';
        doStart(context);
      })
      .catch(function() { doStart(); });
  } else {
    doStart();
  }
}

function tryResumeAgent() {
  var saved = sessionStorage.getItem('relay_agent_session_' + agentType);
  if (!saved) { startAgent(); return; }

  fetch('/api/interview/' + saved + '/state')
    .then(function(r) {
      if (!r.ok) throw new Error('gone');
      return r.json();
    })
    .then(function(state) {
      if (state.error) {
        sessionStorage.removeItem('relay_agent_session_' + agentType);
        startAgent();
        return;
      }
      sessionId = saved;
      lastEventId = 0;
      connectSSE();
    })
    .catch(function() {
      sessionStorage.removeItem('relay_agent_session_' + agentType);
      startAgent();
    });
}

function sendMessage() {
  if (waitingForAI) return;
  var input = document.getElementById('chatInput');
  var text = input.value.trim();
  if (!text) return;

  pendingUserMsg = true;
  addMessage('user', text);
  input.value = '';
  input.style.height = 'auto';
  waitingForAI = true;
  document.getElementById('sendBtn').disabled = true;
  showTypingIndicator();

  fetch('/api/interview/' + sessionId + '/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: text }),
  });
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
  // Auto-resize textarea
  var el = e.target;
  setTimeout(function() {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 150) + 'px';
  }, 0);
}

// Start or resume
tryResumeAgent();
</script>
</body>
</html>
"""


# ── Inbox HTML (placeholder — replaced in Task 5) ───────────────

INBOX_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Inbox — Relay</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0%25' stop-color='%2334d399'/><stop offset='50%25' stop-color='%23818cf8'/><stop offset='100%25' stop-color='%23ec4899'/></linearGradient></defs><rect width='32' height='32' rx='8' fill='url(%23g)'/><text x='16' y='22' text-anchor='middle' font-family='sans-serif' font-weight='800' font-size='18' fill='white'>R</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --font-body: 'DM Sans', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --bg: #0a0e27;
  --bg-card: rgba(255,255,255,0.04);
  --bg-detail: rgba(0,0,0,0.2);
  --bg-input: rgba(255,255,255,0.05);
  --border: rgba(255,255,255,0.08);
  --border-hover: rgba(255,255,255,0.18);
  --text-primary: #e8ecf4;
  --text-secondary: #94a3b8;
  --text-muted: #475569;
  --accent: #818cf8;
  --green: #34d399;
  --amber: #fbbf24;
  --red: #f87171;
  --radius: 12px;
  --transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--font-body); background: var(--bg); color: var(--text-primary);
  height: 100vh; display: flex; flex-direction: column; overflow: hidden;
}
body::before {
  content: ''; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background:
    radial-gradient(ellipse 50% 50% at 20% 30%, rgba(0,212,170,0.12), transparent),
    radial-gradient(ellipse 40% 40% at 80% 20%, rgba(124,58,237,0.10), transparent),
    radial-gradient(ellipse 45% 45% at 60% 80%, rgba(59,130,246,0.08), transparent),
    radial-gradient(ellipse 35% 35% at 10% 80%, rgba(236,72,153,0.06), transparent);
}

/* ── Nav ── */
.navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(10,14,39,0.8); backdrop-filter: blur(30px);
  border-bottom: 1px solid var(--border);
  padding: 0 24px; height: 56px;
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
}
.nav-left { display: flex; align-items: center; gap: 12px; }
.nav-logo {
  width: 28px; height: 28px; border-radius: 10px;
  background: linear-gradient(135deg, var(--green), var(--accent), #ec4899);
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 14px; color: #fff;
}
.nav-title { font-weight: 700; font-size: 15px; }
.nav-back { color: var(--text-secondary); text-decoration: none; font-size: 13px; }
.nav-back:hover { color: var(--text-primary); }

/* ── Two-panel layout ── */
.inbox-layout {
  flex: 1; display: flex; overflow: hidden;
}

/* ── Left: Item list ── */
.inbox-list-panel {
  width: 420px; min-width: 360px; max-width: 500px;
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  background: rgba(10,14,39,0.4);
}
.list-header {
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.list-title { font-size: 13px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px; }
.filters { display: flex; gap: 4px; flex-wrap: wrap; }
.filter-tab {
  font-size: 12px; padding: 4px 10px; border-radius: 6px; cursor: pointer;
  color: var(--text-muted); background: transparent; border: 1px solid transparent;
  font-family: var(--font-body); transition: var(--transition);
}
.filter-tab:hover { color: var(--text-secondary); background: rgba(255,255,255,0.03); }
.filter-tab.active { color: var(--accent); background: rgba(129,140,248,0.1); border-color: rgba(129,140,248,0.2); }

.inbox-items {
  flex: 1; overflow-y: auto;
}
.inbox-items::-webkit-scrollbar { width: 4px; }
.inbox-items::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }

.inbox-item {
  padding: 14px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  cursor: pointer;
  transition: background 0.15s;
  display: flex; flex-direction: column; gap: 6px;
  border-left: 3px solid transparent;
}
.inbox-item:hover { background: rgba(255,255,255,0.02); }
.inbox-item.selected { background: rgba(129,140,248,0.08); border-left-color: var(--accent); }
.inbox-item.dismissed { opacity: 0.4; }

.item-top { display: flex; align-items: center; gap: 8px; }
.item-badge {
  font-size: 9px; font-weight: 600; padding: 2px 6px; border-radius: 3px;
  text-transform: uppercase; letter-spacing: 0.03em; flex-shrink: 0;
}
.item-badge-crash { color: #ef4444; background: rgba(239,68,68,0.15); }
.item-badge-alert { color: #f97316; background: rgba(249,115,22,0.15); }
.item-badge-bug { color: #f97316; background: rgba(249,115,22,0.15); }
.item-badge-feature { color: var(--accent); background: rgba(129,140,248,0.15); }
.item-badge-other { color: var(--text-secondary); background: rgba(148,163,184,0.15); }
.item-source { font-size: 11px; color: var(--text-muted); }
.item-time { font-size: 11px; color: var(--text-muted); margin-left: auto; }

.item-title {
  font-size: 13px; font-weight: 500; color: var(--text-primary);
  line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden;
}
.item-status {
  font-size: 11px; font-weight: 500;
}
.st-new { color: var(--text-muted); }
.st-triaging { color: var(--amber); }
.st-actionable { color: var(--green); }
.st-promoted { color: var(--accent); }
.st-dismissed { color: var(--text-muted); }

/* ── Right: Detail panel ── */
.detail-panel {
  flex: 1; overflow-y: auto; padding: 0;
  display: flex; flex-direction: column;
}
.detail-panel::-webkit-scrollbar { width: 4px; }
.detail-panel::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }

.detail-empty {
  flex: 1; display: flex; align-items: center; justify-content: center;
  flex-direction: column; gap: 8px; color: var(--text-muted);
}
.detail-empty-icon { font-size: 32px; opacity: 0.3; }
.detail-empty-text { font-size: 13px; }

.detail-header {
  padding: 24px 28px 0; flex-shrink: 0;
}
.detail-title { font-size: 18px; font-weight: 600; line-height: 1.4; margin-bottom: 12px; }
.detail-meta { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
.meta-chip {
  font-size: 11px; padding: 3px 10px; border-radius: 6px;
  background: rgba(255,255,255,0.05); color: var(--text-secondary);
  display: flex; align-items: center; gap: 4px;
}
.meta-chip strong { color: var(--text-primary); font-weight: 600; }

.detail-body { padding: 0 28px 28px; flex: 1; }

/* Verdict card */
.verdict-card {
  border-radius: 10px; padding: 16px 18px; margin-bottom: 20px;
  border: 1px solid rgba(52,211,153,0.2); background: rgba(52,211,153,0.05);
}
.verdict-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--green); margin-bottom: 6px; opacity: 0.7; }
.verdict-text { font-size: 15px; font-weight: 600; color: var(--green); line-height: 1.4; }
.verdict-chips { display: flex; gap: 10px; margin-top: 12px; }
.v-chip {
  font-size: 12px; color: var(--text-secondary);
}
.v-chip strong { font-weight: 600; }
.sev-critical strong { color: #ef4444; }
.sev-high strong { color: #f97316; }
.sev-medium strong { color: var(--amber); }
.sev-low strong { color: var(--text-secondary); }
.risk-high strong { color: #ef4444; }
.risk-medium strong { color: var(--amber); }
.risk-low strong { color: var(--green); }

.detail-section { margin-bottom: 18px; }
.section-label {
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 8px;
}
.section-text { font-size: 13px; color: var(--text-secondary); line-height: 1.7; }
.section-mono {
  font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary);
  line-height: 1.6;
}

.payload-block {
  background: rgba(0,0,0,0.25); border-radius: 8px; padding: 14px;
  font-family: var(--font-mono); font-size: 11px; color: var(--text-secondary);
  line-height: 1.5; max-height: 250px; overflow: auto; white-space: pre-wrap;
  word-break: break-all; border: 1px solid rgba(255,255,255,0.04);
}

/* Action bar */
.detail-actions {
  padding: 16px 28px;
  border-top: 1px solid var(--border);
  background: rgba(10,14,39,0.6);
  display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
  flex-shrink: 0;
}
.btn {
  font-size: 13px; font-weight: 600; padding: 9px 18px; border-radius: 8px;
  cursor: pointer; border: none; font-family: var(--font-body);
  transition: var(--transition); display: inline-flex; align-items: center; gap: 6px;
}
.btn-primary {
  background: linear-gradient(135deg, var(--accent), #a78bfa);
  color: white; box-shadow: 0 2px 12px rgba(129,140,248,0.25);
}
.btn-primary:hover { opacity: 0.9; transform: translateY(-1px); }
.btn-triage {
  background: linear-gradient(135deg, var(--amber), #f59e0b);
  color: #1a1a2e; box-shadow: 0 2px 12px rgba(251,191,36,0.2);
}
.btn-triage:hover { opacity: 0.9; transform: translateY(-1px); }
.btn-assisted {
  background: linear-gradient(135deg, var(--green), #10b981);
  color: #1a1a2e; box-shadow: 0 2px 12px rgba(52,211,153,0.2);
  text-decoration: none;
}
.btn-assisted:hover { opacity: 0.9; transform: translateY(-1px); }
.btn-ghost {
  background: transparent; color: var(--text-secondary);
  border: 1px solid var(--border); padding: 8px 16px;
}
.btn-ghost:hover { border-color: var(--border-hover); color: var(--text-primary); }
.btn-danger {
  background: transparent; color: var(--text-muted);
  border: 1px solid transparent; padding: 8px 16px;
}
.btn-danger:hover { color: var(--red); }
.action-spacer { flex: 1; }

/* Triaging spinner */
.triaging-status {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: var(--amber); font-weight: 500;
}
.triaging-dot {
  width: 8px; height: 8px; border-radius: 50%; background: var(--amber);
  animation: pulse 1.5s infinite;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

/* Empty state */
.empty-inbox {
  flex: 1; display: flex; align-items: center; justify-content: center;
  flex-direction: column; gap: 8px; color: var(--text-muted); padding: 40px;
}
</style>
</head>
<body>

<nav class="navbar">
  <div class="nav-left">
    <div class="nav-logo">R</div>
    <span class="nav-title">Relay</span>
  </div>
  <a href="/" class="nav-back">Command Center</a>
</nav>

<div class="inbox-layout">
  <!-- Left panel: item list -->
  <div class="inbox-list-panel">
    <div class="list-header">
      <div class="list-title">Inbox</div>
      <div class="filters" id="filters"></div>
    </div>
    <div class="inbox-items" id="inbox-items"></div>
    <div id="empty-list" class="empty-inbox" style="display:none">
      <div style="font-size:14px;color:var(--text-secondary)">No items</div>
      <div style="font-size:12px">Signals arrive via POST /api/inbox</div>
    </div>
  </div>

  <!-- Right panel: detail view -->
  <div class="detail-panel" id="detail-panel">
    <div class="detail-empty" id="detail-empty">
      <div class="detail-empty-icon">&#9993;</div>
      <div class="detail-empty-text">Select an item to view details</div>
    </div>
  </div>
</div>

<script>
var currentFilter = null;
var selectedId = null;
var allItems = [];
var pollTimer = null;

function timeAgo(iso) {
  var diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return Math.floor(diff) + 's ago';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  return Math.floor(diff / 86400) + 'd ago';
}

function badgeClass(sourceType) {
  var map = { crash: 'item-badge-crash', alert: 'item-badge-alert', bug_report: 'item-badge-bug',
              feature_request: 'item-badge-feature' };
  return map[sourceType] || 'item-badge-other';
}

function statusHtml(s) {
  var map = {
    'new': '<span class="item-status st-new">New</span>',
    'triaging': '<span class="item-status st-triaging">Triaging...</span>',
    'actionable': '<span class="item-status st-actionable">Triaged</span>',
    'promoted': '<span class="item-status st-promoted">Promoted</span>',
    'dismissed': '<span class="item-status st-dismissed">Dismissed</span>',
  };
  return map[s] || s;
}

function escHtml(s) {
  var d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}

function formatFieldName(key) {
  return key.replace(/_/g, ' ').replace(/\\b\\w/g, function(c) { return c.toUpperCase(); });
}

function renderPayloadFields(payload) {
  if (!payload || typeof payload !== 'object') return '<div class="section-text" style="opacity:0.5">No details</div>';
  var html = '<div style="display:grid;grid-template-columns:140px 1fr;gap:6px 12px;font-size:13px;">';
  Object.keys(payload).forEach(function(key) {
    var val = payload[key];
    var label = formatFieldName(key);
    var display;
    if (Array.isArray(val)) {
      display = val.map(escHtml).join(', ');
    } else if (typeof val === 'object' && val !== null) {
      display = '<span style="font-family:var(--font-mono);font-size:11px">' + escHtml(JSON.stringify(val)) + '</span>';
    } else if (typeof val === 'number') {
      display = '<strong>' + val.toLocaleString() + '</strong>';
    } else if (typeof val === 'string' && val.length > 120) {
      display = '<span style="line-height:1.6">' + escHtml(val) + '</span>';
    } else {
      display = escHtml(String(val));
    }
    html += '<div style="color:var(--text-muted);font-size:12px;padding-top:2px">' + escHtml(label) + '</div>';
    html += '<div style="color:var(--text-secondary)">' + display + '</div>';
  });
  html += '</div>';
  return html;
}

function renderFilters(items) {
  var counts = { all: items.length };
  items.forEach(function(it) { counts[it.status] = (counts[it.status] || 0) + 1; });
  var tabs = [
    { key: null, label: 'All', count: counts.all },
    { key: 'new', label: 'New', count: counts['new'] || 0 },
    { key: 'triaging', label: 'Triaging', count: counts.triaging || 0 },
    { key: 'actionable', label: 'Actionable', count: counts.actionable || 0 },
  ];
  document.getElementById('filters').innerHTML = tabs.map(function(t) {
    var active = currentFilter === t.key ? ' active' : '';
    return '<button class="filter-tab' + active + '" onclick="setFilter(' +
      (t.key ? "'" + t.key + "'" : 'null') + ')">' + t.label +
      (t.count > 0 ? ' (' + t.count + ')' : '') + '</button>';
  }).join('');
}

function setFilter(f) { currentFilter = f; renderList(); }

function renderList() {
  var filtered = currentFilter ? allItems.filter(function(it) { return it.status === currentFilter; }) : allItems;
  renderFilters(allItems);
  var el = document.getElementById('inbox-items');
  var empty = document.getElementById('empty-list');
  if (!filtered.length) { el.innerHTML = ''; empty.style.display = ''; return; }
  empty.style.display = 'none';
  el.innerHTML = filtered.map(function(it) {
    var sel = selectedId === it.id ? ' selected' : '';
    var dis = it.status === 'dismissed' ? ' dismissed' : '';
    return '<div class="inbox-item' + sel + dis + '" onclick="selectItem(' + it.id + ')">' +
      '<div class="item-top">' +
        '<span class="item-badge ' + badgeClass(it.source_type) + '">' + escHtml(it.source_type) + '</span>' +
        '<span class="item-source">' + escHtml(it.source) + '</span>' +
        statusHtml(it.status) +
        '<span class="item-time">' + timeAgo(it.received_at) + '</span>' +
      '</div>' +
      '<div class="item-title">' + escHtml(it.title) + '</div>' +
    '</div>';
  }).join('');
}

function selectItem(id) {
  selectedId = id;
  renderList();
  renderDetail();
}

function renderDetail() {
  var panel = document.getElementById('detail-panel');
  var item = allItems.find(function(it) { return it.id === selectedId; });
  if (!item) {
    panel.innerHTML = '<div class="detail-empty" id="detail-empty"><div class="detail-empty-icon">&#9993;</div><div class="detail-empty-text">Select an item to view details</div></div>';
    return;
  }

  var r = item.triage_report || {};
  var payload = typeof item.payload === 'string' ? item.payload : JSON.stringify(item.payload, null, 2);

  // Header
  var html = '<div class="detail-header">' +
    '<div class="detail-title">' + escHtml(item.title) + '</div>' +
    '<div class="detail-meta">' +
      '<div class="meta-chip"><span class="item-badge ' + badgeClass(item.source_type) + '">' + escHtml(item.source_type) + '</span></div>' +
      '<div class="meta-chip">Source: <strong>' + escHtml(item.source) + '</strong></div>' +
      '<div class="meta-chip">' + timeAgo(item.received_at) + '</div>' +
      '<div class="meta-chip">' + statusHtml(item.status) + '</div>' +
    '</div></div>';

  // Body
  html += '<div class="detail-body">';

  // Verdict (for triaged/promoted items)
  if ((item.status === 'actionable' || item.status === 'promoted') && r.verdict) {
    html += '<div class="verdict-card">' +
      '<div class="verdict-label">Agent Verdict</div>' +
      '<div class="verdict-text">' + escHtml(r.verdict) + '</div>' +
      '<div class="verdict-chips">' +
        '<span class="v-chip sev-' + (r.severity || 'low') + '">Severity: <strong>' + escHtml(r.severity || '?') + '</strong></span>' +
        '<span class="v-chip">Effort: <strong>' + escHtml(r.effort || '?') + '</strong></span>' +
        '<span class="v-chip risk-' + (r.risk || 'low') + '">Risk: <strong>' + escHtml(r.risk || '?') + '</strong></span>' +
      '</div></div>';
  }

  // Triaging status
  if (item.status === 'triaging') {
    html += '<div class="detail-section"><div class="triaging-status"><div class="triaging-dot"></div> Triage agent is analyzing this item...</div></div>';
  }

  // Context from triage
  if (r.context) {
    html += '<div class="detail-section"><div class="section-label">What the agent found</div>' +
      '<div class="section-text">' + escHtml(r.context) + '</div></div>';
  }

  // Affected files
  if (r.affected_files && r.affected_files.length) {
    html += '<div class="detail-section"><div class="section-label">Affected files</div>' +
      '<div class="section-mono">' + r.affected_files.map(escHtml).join('<br>') + '</div></div>';
  }

  // Promoted info
  if (item.status === 'promoted') {
    if (r.recommended_title) {
      html += '<div class="detail-section"><div class="section-label">Promoted as</div>' +
        '<div class="section-text" style="font-weight:600">' + escHtml(r.recommended_title) + '</div></div>';
    }
    if (item.promoted_to) {
      html += '<div class="detail-section"><div class="section-label">Spec path</div>' +
        '<div class="section-mono">' + escHtml(item.promoted_to) + '</div></div>';
    }
  }

  // Payload as readable fields
  html += '<div class="detail-section"><div class="section-label">Details</div>' +
    renderPayloadFields(item.payload) + '</div>';

  html += '</div>'; // end detail-body

  // Action bar
  html += '<div class="detail-actions">';
  if (item.status === 'new') {
    html += '<button class="btn btn-triage" onclick="triageItem(' + item.id + ')">AI Triage</button>' +
      '<a href="/agent/triage?inbox_id=' + item.id + '" class="btn btn-assisted">Assisted Triage</a>' +
      '<span class="action-spacer"></span>' +
      '<button class="btn btn-danger" onclick="dismissItem(' + item.id + ')">Dismiss</button>';
  } else if (item.status === 'triaging') {
    html += '<div class="triaging-status"><div class="triaging-dot"></div> Agent working...</div>' +
      '<span class="action-spacer"></span>' +
      '<button class="btn btn-danger" onclick="dismissItem(' + item.id + ')">Dismiss</button>';
  } else if (item.status === 'actionable') {
    if (r.recommendation === 'create_bug_spec') {
      html += '<button class="btn btn-primary" onclick="promoteItem(' + item.id + ',&quot;bug&quot;)">Create Bug Spec</button>' +
        '<button class="btn btn-ghost" onclick="promoteItem(' + item.id + ',&quot;feature&quot;)">Create Feature Spec</button>';
    } else {
      html += '<button class="btn btn-primary" onclick="promoteItem(' + item.id + ',&quot;feature&quot;)">Create Feature Spec</button>' +
        '<button class="btn btn-ghost" onclick="promoteItem(' + item.id + ',&quot;bug&quot;)">Create Bug Spec</button>';
    }
    html += '<span class="action-spacer"></span>' +
      '<button class="btn btn-danger" onclick="dismissItem(' + item.id + ')">Dismiss</button>';
  } else if (item.status === 'dismissed') {
    html += '<span style="font-size:13px;color:var(--text-muted)">This item has been dismissed</span>';
  } else if (item.status === 'promoted') {
    html += '<span style="font-size:13px;color:var(--accent)">Promoted to spec</span>';
  }
  html += '</div>';

  panel.innerHTML = html;
}

function loadInbox() {
  var url = '/api/inbox' + (currentFilter ? '?status=' + currentFilter : '');
  fetch(url).then(function(r) { return r.json(); }).then(function(items) {
    allItems = items;
    renderList();
    if (selectedId) renderDetail();
  }).catch(function(e) { console.error('loadInbox error:', e); });
}

function triageItem(id) {
  fetch('/api/inbox/' + id + '/triage', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function() { loadInbox(); });
}

function dismissItem(id) {
  fetch('/api/inbox/' + id + '/dismiss', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function() { loadInbox(); });
}

function promoteItem(id, type) {
  fetch('/api/inbox/' + id + '/promote', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type: type })
  })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.redirectUrl) window.open(data.redirectUrl, '_blank');
      loadInbox();
    });
}

document.addEventListener('DOMContentLoaded', function() {
  loadInbox();
  pollTimer = setInterval(loadInbox, 15000);
});
</script>
</body>
</html>"""


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Relay Web Console — local dev server")
    parser.add_argument("--cp-dir", help="Control plane directory")
    parser.add_argument("--port", type=int, default=7433,
                        help="Port to listen on (default: 7433)")
    args = parser.parse_args()

    global CP_DIR, RELAY_DIR, INBOX_DB
    CP_DIR = args.cp_dir or wf.resolve_cp_dir() or os.environ.get("CP_DIR", "")
    if not CP_DIR:
        print("Error: Cannot determine control plane directory.",
              file=sys.stderr)
        print("Run from a control plane directory or pass --cp-dir.",
              file=sys.stderr)
        sys.exit(1)

    RELAY_DIR = wf.resolve_relay_dir() or ""
    if not RELAY_DIR:
        print("Error: Cannot determine Relay framework directory.",
              file=sys.stderr)
        sys.exit(1)

    INBOX_DB = _inbox_db.init_db(CP_DIR)

    server = ThreadingHTTPServer(("0.0.0.0", args.port), RelayHandler)
    server.daemon_threads = True
    print(f"\n  Relay Web Console")
    print(f"  {'=' * 40}")
    print(f"  Local:   http://localhost:{args.port}")
    print(f"  CP dir:  {CP_DIR}")
    print(f"  {'=' * 40}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
