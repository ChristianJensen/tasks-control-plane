#!/usr/bin/env python3
"""Shared workflow infrastructure for Relay CLI commands.

Provides frontmatter parsing, validation gates, template rendering,
agent invocation, and control plane resolution. Used by validate.py,
plan.py, and future orchestrated commands.

No external dependencies — stdlib only.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from string import Template


# ── Frontmatter parsing ─────────────────────────────────────────

def parse_frontmatter(path):
    """Extract YAML frontmatter fields from a markdown file.

    Returns dict of key-value pairs. Multi-value fields (like 'contracts')
    are returned as lists. Returns empty dict if no frontmatter found.
    """
    with open(path) as f:
        content = f.read()
    return parse_frontmatter_string(content)


def parse_frontmatter_string(content):
    """Extract YAML frontmatter from a string."""
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}
    front = m.group(1)
    fields = {}
    current_key = None
    for line in front.split("\n"):
        # List item under a key
        list_match = re.match(r"^\s+-\s+(.+)", line)
        if list_match and current_key:
            if not isinstance(fields[current_key], list):
                fields[current_key] = []
            fields[current_key].append(list_match.group(1).strip())
            continue
        # Key-value pair
        kv_match = re.match(r"^(\S+):\s*(.*)", line)
        if kv_match:
            key = kv_match.group(1)
            value = kv_match.group(2).strip()
            # Strip inline comments
            value = re.sub(r"\s+#.*$", "", value)
            if value:
                fields[key] = value
            else:
                fields[key] = []
            current_key = key
        else:
            current_key = None
    return fields


def write_frontmatter(path, fields):
    """Update frontmatter fields in a markdown file, preserving body content."""
    with open(path) as f:
        content = f.read()

    # Extract existing frontmatter and body
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
    if m:
        body = m.group(2)
    else:
        body = content

    # Build new frontmatter
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")

    with open(path, "w") as f:
        f.write("\n".join(lines) + body)


# ── Template rendering ───────────────────────────────────────────

def render_template(template_path, substitutions):
    """Fill $-style placeholders in a template file.

    Uses string.Template safe_substitute so missing keys are left as-is.
    """
    with open(template_path) as f:
        tmpl = Template(f.read())
    return tmpl.safe_substitute(substitutions)


# ── Validation gates ─────────────────────────────────────────────

def validate_frontmatter(path, required=None, allowed_values=None):
    """Validate frontmatter fields.

    Args:
        path: Path to markdown file
        required: List of required field names
        allowed_values: Dict of {field: [allowed_values]}

    Returns:
        (ok: bool, errors: list[str])
    """
    fields = parse_frontmatter(path)
    errors = []

    if not fields:
        return False, [f"No frontmatter found in {path}"]

    if required:
        for field in required:
            if field not in fields:
                errors.append(f"Missing required field: {field}")
            elif isinstance(fields[field], str) and not fields[field]:
                errors.append(f"Empty required field: {field}")

    if allowed_values:
        for field, allowed in allowed_values.items():
            if field in fields and fields[field] not in allowed:
                errors.append(
                    f"Invalid value for {field}: '{fields[field]}' "
                    f"(allowed: {', '.join(allowed)})"
                )

    return len(errors) == 0, errors


def validate_sections(path, required_sections):
    """Check that required markdown sections exist and are non-empty.

    Returns:
        (ok: bool, errors: list[str])
    """
    with open(path) as f:
        content = f.read()
    errors = []

    for section in required_sections:
        # Match ## Section Name (case-insensitive)
        pattern = re.compile(
            rf"^##\s+{re.escape(section)}\s*$",
            re.MULTILINE | re.IGNORECASE,
        )
        match = pattern.search(content)
        if not match:
            errors.append(f"Missing section: ## {section}")
            continue

        # Extract section content (up to next ## or end of file)
        start = match.end()
        next_section = re.search(r"^##\s+", content[start:], re.MULTILINE)
        if next_section:
            section_content = content[start : start + next_section.start()]
        else:
            section_content = content[start:]

        section_text = section_content.strip()

        # Check for empty or template-only content
        if not section_text:
            errors.append(f"Empty section: ## {section}")
        elif re.match(r"^_[^_]+_$", section_text):
            errors.append(f"Section has only template placeholder: ## {section}")
        elif "_TODO" in section_text or "[placeholder]" in section_text.lower():
            errors.append(f"Section contains unfilled placeholders: ## {section}")

    return len(errors) == 0, errors


def validate_readiness_checklist(path):
    """Check that all checklist items are checked (- [x]).

    Returns:
        (ok: bool, errors: list[str])
    """
    with open(path) as f:
        content = f.read()

    # Find the Readiness Checklist section
    match = re.search(r"^##\s+Readiness Checklist\s*$", content, re.MULTILINE)
    if not match:
        return True, []  # No checklist = no errors

    start = match.end()
    next_section = re.search(r"^##\s+", content[start:], re.MULTILINE)
    if next_section:
        checklist_content = content[start : start + next_section.start()]
    else:
        checklist_content = content[start:]

    unchecked = re.findall(r"^-\s+\[ \]\s+(.+)", checklist_content, re.MULTILINE)
    errors = [f"Unchecked: {item.strip()}" for item in unchecked]

    return len(errors) == 0, errors


def validate_queue_filename(path):
    """Validate queue task filename matches pattern wave-N-<repo>-<slug>.md.

    Since repo names and slugs both contain hyphens, we use frontmatter
    to validate the repo/wave portions rather than parsing the filename alone.

    Returns:
        (ok: bool, errors: list[str])
    """
    filename = os.path.basename(path)
    errors = []

    if filename.startswith("_"):
        return True, []  # Skip meta files like _validation.md

    # Guard against filesystem "File name too long" errors
    if len(filename) > 80:
        errors.append(
            f"Filename too long ({len(filename)} chars, max 80): {filename}"
        )
        return False, errors

    # Basic pattern: starts with wave-N- and ends with .md
    basic_pattern = r"^wave-(\d+)-.+\.md$"
    m = re.match(basic_pattern, filename)
    if not m:
        errors.append(f"Invalid filename pattern: {filename} (expected wave-N-<repo>-<slug>.md)")
        return False, errors

    wave_from_name = m.group(1)

    # Cross-check frontmatter
    fields = parse_frontmatter(path)
    if fields:
        if fields.get("wave") and fields["wave"] != wave_from_name:
            errors.append(
                f"Wave mismatch: filename says wave {wave_from_name}, "
                f"frontmatter says {fields['wave']}"
            )

        # Verify repo name appears in filename after wave-N-
        repo = fields.get("target-repo", "")
        if repo:
            expected_prefix = f"wave-{wave_from_name}-{repo}-"
            if not filename.startswith(expected_prefix):
                errors.append(
                    f"Filename doesn't match repo: expected prefix '{expected_prefix}', "
                    f"got '{filename}'"
                )

        # Check feature field matches directory
        # Path is queue/<feature>/<status>/<task>.md — go up two levels
        status_dir = os.path.dirname(path)
        feature_dir = os.path.basename(os.path.dirname(status_dir))
        if feature_dir != "_done" and fields.get("feature") and fields["feature"] != feature_dir:
            errors.append(
                f"Feature mismatch: directory is '{feature_dir}', "
                f"frontmatter says '{fields['feature']}'"
            )

    return len(errors) == 0, errors


def validate_decomposition(tasks, service_catalog_repos):
    """Validate a decomposition (list of task dicts).

    Checks:
    - No task >400 estimated lines
    - All repos are valid (in service catalog)
    - Waves are contiguous (1, 2, 3... no gaps)
    - No circular dependencies (simplified: within-wave tasks don't depend on each other)

    Args:
        tasks: List of dicts with keys: repo, wave, estimated_lines, slug
        service_catalog_repos: Set of valid repo names

    Returns:
        (ok: bool, errors: list[str])
    """
    errors = []

    for t in tasks:
        lines = t.get("estimated_lines", 0)
        if lines > 400:
            errors.append(
                f"Task '{t.get('slug', '?')}' estimated at {lines} lines (max 400)"
            )

        repo = t.get("repo", "")
        if repo and repo not in service_catalog_repos:
            errors.append(
                f"Task '{t.get('slug', '?')}' targets unknown repo: {repo} "
                f"(valid: {', '.join(sorted(service_catalog_repos))})"
            )

    # Check wave contiguity
    waves = sorted(set(t.get("wave", 0) for t in tasks))
    if waves:
        expected = list(range(waves[0], waves[-1] + 1))
        if waves != expected:
            errors.append(f"Non-contiguous waves: {waves} (expected {expected})")

    # Validate behavioral acceptance criteria
    for t in tasks:
        ac = t.get("acceptance_criteria", {})
        if isinstance(ac, dict):
            behaviors = ac.get("behaviors", [])
            if not behaviors:
                errors.append(f"Task '{t.get('slug', '?')}' has no behavioral scenarios")
            for i, b in enumerate(behaviors):
                if not all(k in b for k in ("given", "when", "then")):
                    errors.append(
                        f"Task '{t.get('slug', '?')}' scenario {i+1} missing given/when/then"
                    )
        elif isinstance(ac, list):
            # Old format — warn but don't fail
            pass

    return len(errors) == 0, errors


def validate_contracts(path):
    """Validate that a contract file exists and is valid JSON.

    Returns:
        (ok: bool, errors: list[str])
    """
    errors = []
    if not os.path.exists(path):
        errors.append(f"Contract file not found: {path}")
        return False, errors

    try:
        with open(path) as f:
            json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON in {path}: {e}")
        return False, errors

    return True, []


# ── Context assembly ─────────────────────────────────────────────

def assemble_context(file_paths):
    """Read and concatenate multiple files into a context string.

    Each file is wrapped with a header showing the path.
    Missing files are noted but don't cause failure.
    """
    parts = []
    for p in file_paths:
        if os.path.exists(p):
            with open(p) as f:
                content = f.read()
            parts.append(f"--- {p} ---\n{content}\n")
        else:
            parts.append(f"--- {p} --- (file not found)\n")
    return "\n".join(parts)


# ── Structured prompt building ───────────────────────────────────

def build_structured_prompt(task, context, output_schema, constraints=None):
    """Build a structured prompt for AI agent invocation.

    Args:
        task: Description of what the agent should do
        context: Assembled context string
        output_schema: Description of expected output format
        constraints: Optional list of constraints

    Returns:
        Prompt string
    """
    parts = [
        "# Task",
        task,
        "",
        "# Context",
        context,
        "",
        "# Expected Output",
        output_schema,
    ]

    if constraints:
        parts.extend(["", "# Constraints"])
        for c in constraints:
            parts.append(f"- {c}")

    return "\n".join(parts)


# ── Agent invocation ─────────────────────────────────────────────

def detect_agent():
    """Auto-detect available agent CLI."""
    for name in ["claude", "gemini"]:
        if shutil.which(name):
            return name
    return None


def invoke_agent(prompt, cwd, interactive=False, model=None):
    """Invoke AI agent. Returns stdout for non-interactive mode.

    Agent selection: RELAY_AGENT env var > auto-detect (claude, gemini).
    For custom agents, RELAY_AGENT can be a full command string.

    Args:
        prompt: The prompt string to send
        cwd: Working directory for the agent
        interactive: If True, launch interactive session (no capture)
        model: Model identifier to pass to the agent CLI (optional)

    Returns:
        Agent stdout (non-interactive) or None (interactive)
    """
    agent = os.environ.get("RELAY_AGENT") or detect_agent()
    if not agent:
        print(
            "No AI agent found. Install claude or gemini CLI, or set RELAY_AGENT.",
            file=sys.stderr,
        )
        sys.exit(1)

    if agent == "claude":
        if interactive:
            cmd = [
                "claude",
                "--system-prompt", prompt,
                "Begin. Follow your system prompt instructions.",
            ]
            if model:
                cmd.extend(["--model", model])
            subprocess.run(cmd, cwd=cwd)
            return None
        else:
            cmd = [
                "claude", "-p", prompt,
                "--output-format", "json",
                "--permission-mode", "acceptEdits",
            ]
            if model:
                cmd.extend(["--model", model])
    elif agent == "gemini":
        if interactive:
            cmd = ["gemini"]
        else:
            cmd = ["gemini", "-p", prompt]
    else:
        # Custom agent: split command string, append prompt
        cmd = shlex.split(agent) + [prompt]

    result = subprocess.run(
        cmd, cwd=cwd, capture_output=not interactive, text=True
    )

    if not interactive:
        return result.stdout
    return None


# ── Conversation loop infrastructure ─────────────────────────────

class Transcript:
    """Accumulates conversation context across phases."""

    def __init__(self):
        self.entries = []  # list of (role, content, phase)

    def add(self, role, content, phase=""):
        self.entries.append((role, content, phase))

    def render(self, max_chars=None):
        """Serialize transcript to text for prompt inclusion."""
        parts = []
        for role, content, phase in self.entries:
            label = phase or "general"
            parts.append(f"--- {role.upper()} ({label}) ---\n{content}\n")
        text = "\n".join(parts)
        if max_chars and len(text) > max_chars:
            while len(text) > max_chars and len(parts) > 1:
                parts.pop(0)
                text = "\n".join(parts)
        return text

    def render_summary(self):
        """Compressed Q&A-only view."""
        pairs = []
        for role, content, _phase in self.entries:
            if role in ("ai", "user"):
                pairs.append(f"[{role.upper()}]: {content}")
        return "\n\n".join(pairs)


def _extract_agent_text(raw_response):
    """Extract plain text from agent response.

    Handles claude's --output-format json wrapper and plain text from
    gemini/custom agents.
    """
    if not raw_response:
        return ""
    try:
        data = json.loads(raw_response)
        if isinstance(data, dict):
            for key in ("result", "content", "text", "message"):
                if key in data:
                    return data[key]
        return raw_response
    except (json.JSONDecodeError, TypeError):
        return raw_response.strip()


def collect_user_answers(questions_text):
    """Display AI questions and collect user answers.

    Parses numbered questions from AI output. Falls back to showing
    full text and collecting freeform input if parsing fails.
    """
    questions = re.findall(r"^\d+\.\s*(.+)", questions_text, re.MULTILINE)

    if questions:
        answers = []
        for i, q in enumerate(questions, 1):
            print(f"\n  {BOLD}Q{i}:{NC} {q}")
            answer = input(f"  {BOLD}A{i}:{NC} ")
            answers.append(f"{i}. {q}\n   Answer: {answer}")
        return "\n\n".join(answers)
    else:
        print(f"\n{questions_text}")
        print()
        return input(f"  {BOLD}Your response:{NC} ")


def run_phase(phase_name, prompt, cwd, transcript,
              needs_user_input=False, expect_file=None, model=None):
    """Run a single conversation phase via non-interactive agent call.

    Args:
        phase_name: Label for this phase
        prompt: Full prompt to send
        cwd: Working directory
        transcript: Transcript object to accumulate context
        needs_user_input: If True, parse AI output for questions and
                          collect user answers
        expect_file: If set, verify this file exists after the phase
        model: Model identifier to pass to the agent CLI (optional)

    Returns:
        AI response text
    """
    print_info(f"Phase: {phase_name}")

    response = invoke_agent(prompt, cwd, interactive=False, model=model)
    response_text = _extract_agent_text(response)

    if not response_text:
        print_fail(f"Agent returned no output for phase: {phase_name}")
        return ""

    transcript.add("ai", response_text, phase=phase_name)

    if needs_user_input:
        user_input = collect_user_answers(response_text)
        transcript.add("user", user_input, phase=phase_name)

    if expect_file and not os.path.exists(expect_file):
        # Fallback: try to extract file content from response
        _write_file_from_response(response_text, expect_file)

    return response_text


def _write_file_from_response(response_text, target_path):
    """Fallback: extract markdown file content from response and write it.

    Used when the agent couldn't write the file directly (e.g., gemini -p
    or custom agents without tool access).
    """
    # Look for frontmatter-delimited content
    m = re.search(r"```(?:markdown)?\s*\n(---\n.*?\n---\n.*?)```",
                  response_text, re.DOTALL)
    if not m:
        m = re.search(r"(---\n.*?\n---\n.+)", response_text, re.DOTALL)
    if m:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w") as f:
            f.write(m.group(1))
        print_ok(f"File written from response: {os.path.basename(target_path)}")
    else:
        print_warn(f"Expected file not created: {target_path}")


# ── Control plane resolution ─────────────────────────────────────

def resolve_cp_dir(args=None):
    """Resolve the control plane directory.

    Resolution order:
    1. --cp-dir argument
    2. CP_DIR environment variable
    3. Current directory (if it has .relay-config)

    Returns:
        Path string or None
    """
    # From args
    if args and hasattr(args, "cp_dir") and args.cp_dir:
        return args.cp_dir

    # From env
    cp_dir = os.environ.get("CP_DIR")
    if cp_dir and os.path.isdir(cp_dir):
        return cp_dir

    # Current directory
    if os.path.exists(".relay-config"):
        return os.getcwd()

    return None


def resolve_relay_dir():
    """Resolve the Relay framework directory.

    Resolution order:
    1. RELAY_DIR environment variable
    2. This script's location (process/scripts/ -> up two levels)
    """
    relay_dir = os.environ.get("RELAY_DIR")
    if relay_dir and os.path.isdir(relay_dir):
        return relay_dir

    # Derive from this file's location
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.dirname(os.path.dirname(scripts_dir))
    if os.path.exists(os.path.join(candidate, "VERSION")):
        return candidate

    return None


def read_relay_config(cp_dir, key):
    """Read a value from .relay-config."""
    config_path = os.path.join(cp_dir, ".relay-config")
    if not os.path.exists(config_path):
        return None
    with open(config_path) as f:
        for line in f:
            m = re.match(rf"^{re.escape(key)}:\s*(.+)", line)
            if m:
                return m.group(1).strip()
    return None


DEFAULT_MODEL = "claude-sonnet-4-20250514"


def resolve_model(cp_dir, role=None, task_model=None, feature_model=None):
    """Resolve AI model for a given role.

    Priority: role env var > global env var > task override > feature override
    > role config > global config > default.
    """
    if role:
        env_val = os.environ.get(f"RELAY_{role.upper()}_MODEL")
        if env_val:
            return env_val
    env_val = os.environ.get("RELAY_MODEL")
    if env_val:
        return env_val
    if task_model:
        return task_model
    if feature_model:
        return feature_model
    if role and cp_dir:
        val = read_relay_config(cp_dir, f"{role}-model")
        if val:
            return val
    if cp_dir:
        val = read_relay_config(cp_dir, "model")
        if val:
            return val
    return DEFAULT_MODEL


def read_relay_config_repos(cp_dir):
    """Read repos from .relay-config. Returns list of (short, nwo) tuples."""
    config_path = os.path.join(cp_dir, ".relay-config")
    if not os.path.exists(config_path):
        return []
    repos = []
    in_repos = False
    with open(config_path) as f:
        for line in f:
            if re.match(r"^repos:\s*$", line):
                in_repos = True
                continue
            if in_repos:
                m = re.match(r"^  (\S+):\s*(\S+)", line)
                if m:
                    repos.append((m.group(1), m.group(2)))
                elif not line.startswith(" "):
                    break
    return repos


def parse_service_catalog(cp_dir):
    """Parse service-catalog.md. Returns list of dicts with name, nwo, local_path."""
    catalog_path = os.path.join(cp_dir, ".relay", "service-catalog.md")
    if not os.path.exists(catalog_path):
        return []

    with open(catalog_path) as f:
        content = f.read()

    results = []
    for m in re.finditer(
        r"## (\S+)\n.*?\*\*Repo:\*\*\s*(\S+).*?\*\*Local:\*\*\s*`([^`]+)`",
        content,
        re.DOTALL,
    ):
        results.append({
            "name": m.group(1),
            "nwo": m.group(2),
            "local_path": m.group(3),
        })
    return results


def find_spec(cp_dir, slug):
    """Find a feature or bug spec by slug. Searches features/ and bugs/."""
    for base in ["features", "bugs"]:
        for phase in ["draft", "active", "completed", "cancelled"]:
            for suffix in ["-feature.md", "-bug.md"]:
                path = os.path.join(cp_dir, base, phase, f"{slug}{suffix}")
                if os.path.exists(path):
                    return path
    return None


# ── Output helpers ───────────────────────────────────────────────

# Colors
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
RED = "\033[0;31m"
DIM = "\033[2m"
BOLD = "\033[1m"
NC = "\033[0m"


def print_ok(msg):
    print(f"  {GREEN}✓{NC} {msg}")


def print_fail(msg):
    print(f"  {RED}✗{NC} {msg}")


def print_warn(msg):
    print(f"  {YELLOW}⚠{NC} {msg}")


def print_info(msg):
    print(f"  {BLUE}→{NC} {msg}")


def print_header(msg):
    print(f"\n{BOLD}{msg}{NC}")
