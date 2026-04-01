#!/usr/bin/env python3
"""Relay Handle Telemetry — non-interactive telemetry alert → bug spec pipeline.

Usage:
    handle-telemetry.py --payload '<json>' [--cp-dir <path>] [--dry-run]
    handle-telemetry.py --payload-file <path> [--cp-dir <path>] [--dry-run]

Pipeline:
    1. Parse payload    [DETERMINISTIC]        — extract fields from JSON
    2. Load context     [DETERMINISTIC]        — read service catalog, bug template, repo manifest
    3. Generate spec    [NON-INTERACTIVE AI]    — single-pass LLM call to write bug report
    4. Validate         [DETERMINISTIC]        — check required sections exist
    5. Commit & push    [DETERMINISTIC]        — auto-commit, push to remote
"""

import argparse
import json
import os
import re
import subprocess
import sys

# Add scripts directory to path for _workflow import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _workflow as wf


def slugify(error_message):
    """Generate a kebab-case slug from an error message."""
    # Strip common prefixes
    text = re.sub(r"^(TypeError|ReferenceError|SyntaxError|Error):\s*", "", error_message)
    # Remove quotes and parens
    text = re.sub(r"['\"\(\)]", "", text)
    # Replace non-alphanumeric with hyphens
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text)
    # Clean up
    text = text.strip("-").lower()
    # Truncate to reasonable length
    return text[:60].rstrip("-")


TELEMETRY_TRIAGE_PROMPT = """\
You are a senior SRE triaging a production alert. A monitoring system has
detected an error and sent the following telemetry payload.

## Your Task

Diagnose this bug by exploring the codebase, then write a complete bug report.

## Phase 1: Understand the Alert

Read the telemetry payload below. Identify the affected service, the error
type, and the likely code path from the stack trace.

## Phase 2: Diagnose

Search the affected repo for the relevant code paths using Grep and Read.
Trace the logic from the stack trace through the codebase. Identify the
likely root cause — reference specific files, functions, and line numbers.

## Phase 3: Write Bug Report

Write the bug report to `bugs/active/{slug}-bug.md` using the template
below. Fill ALL sections. Set frontmatter exactly as shown:

```
lifecycle: active
type: bug
version: 1
severity: {severity}
affected-repos:
  - {service}
reported-by: telemetry
```

For the severity, use this rubric:
- **critical**: Data loss, security vulnerability, or complete feature outage
- **high**: Core feature broken, no workaround
- **medium**: Wrong behavior but workaround exists
- **low**: Cosmetic issue, minor UX annoyance

## Rules

- Do NOT ask questions. You are autonomous — infer from the code.
- Do NOT commit or push — the orchestrator handles that.
- Be specific: reference actual file paths, function names, line numbers.
- If you cannot determine root cause with confidence, state your best
  hypothesis and mark the Fix Strategy with [REQUIRES HUMAN REVIEW].
- Fill ALL sections of the template.
- Complete all phases in this single session.

## Telemetry Payload

```json
{payload_json}
```

## Service Catalog
{service_catalog}

## Repo Manifest: {service}
{repo_manifest}

## Bug Report Template
{template}
"""


def main():
    parser = argparse.ArgumentParser(
        description="Ingest a telemetry alert and generate a bug spec."
    )
    parser.add_argument("--payload", help="JSON payload string")
    parser.add_argument("--payload-file", help="Path to JSON payload file")
    parser.add_argument("--cp-dir", help="Control plane directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate spec but do not commit or push")
    parser.add_argument("--no-commit", action="store_true",
                        help="Generate spec but skip git commit/push (for CI workflows that handle git externally)")
    parser.add_argument("--plan", action="store_true",
                        help="Run plan.py after triage to decompose bug into queue tasks")
    args = parser.parse_args()

    # ── Parse payload ─────────────────────────────────────────────
    if args.payload:
        payload = json.loads(args.payload)
    elif args.payload_file:
        with open(args.payload_file) as f:
            payload = json.load(f)
    else:
        print("Error: Provide --payload or --payload-file.", file=sys.stderr)
        sys.exit(1)

    error_message = payload.get("error_message", "Unknown error")
    file_path = payload.get("file", "")
    service = payload.get("service", "unknown")
    severity = payload.get("severity", "high")
    user_impact = payload.get("user_impact", "")
    stack_trace = payload.get("stack_trace", "")

    slug = slugify(error_message)
    if not slug:
        slug = "telemetry-alert"

    wf.print_header("Handle Telemetry Alert")
    print()
    wf.print_info(f"Error: {error_message}")
    wf.print_info(f"Service: {service}")
    wf.print_info(f"Severity: {severity}")
    if user_impact:
        wf.print_info(f"Impact: {user_impact}")
    wf.print_info(f"Slug: {slug}")

    # ── Resolve directories ───────────────────────────────────────
    cp_dir = args.cp_dir or wf.resolve_cp_dir() or os.environ.get("CP_DIR")
    if not cp_dir:
        print("Error: Cannot determine control plane directory.", file=sys.stderr)
        print("Run from a control plane directory or pass --cp-dir.", file=sys.stderr)
        sys.exit(1)

    relay_dir = wf.resolve_relay_dir()
    if not relay_dir:
        print("Error: Cannot determine Relay framework directory.", file=sys.stderr)
        sys.exit(1)

    # ── Load context ──────────────────────────────────────────────
    print()
    wf.print_header("Loading Context")

    # Service catalog
    catalog_path = os.path.join(cp_dir, ".relay", "service-catalog.md")
    service_catalog = ""
    if os.path.exists(catalog_path):
        with open(catalog_path) as f:
            service_catalog = f.read()
        wf.print_ok("Service catalog loaded")
    else:
        wf.print_warn("No service-catalog.md found")

    # Bug report template
    template_path = os.path.join(relay_dir, "process", "templates", "bug-report.md")
    template = ""
    if os.path.exists(template_path):
        with open(template_path) as f:
            template = f.read()
        wf.print_ok("Bug report template loaded")
    else:
        wf.print_fail("Bug report template not found")
        sys.exit(1)

    # Repo manifest for affected service
    repo_manifest = ""
    manifest_path = os.path.join(cp_dir, "repos", service, "repo-manifest.md")
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            repo_manifest = f.read()
        wf.print_ok(f"Repo manifest loaded for {service}")
    else:
        wf.print_warn(f"No repo manifest found for {service}")

    # ── Generate bug spec ─────────────────────────────────────────
    print()
    wf.print_header("Generating Bug Spec")
    wf.print_info("Invoking AI agent for autonomous triage...")

    payload_json = json.dumps(payload, indent=2)

    prompt = TELEMETRY_TRIAGE_PROMPT.format(
        slug=slug,
        severity=severity,
        service=service,
        payload_json=payload_json,
        service_catalog=service_catalog or "(no service catalog found)",
        repo_manifest=repo_manifest or "(no repo manifest found)",
        template=template,
    )

    model = wf.resolve_model(cp_dir)
    response = wf.invoke_agent(prompt, cp_dir, interactive=False, model=model)

    # ── Detect the bug report file ────────────────────────────────
    print()
    wf.print_header("Detecting Bug Report")

    # Check features/active/ first (where we told the agent to write)
    bug_path = os.path.join(cp_dir, "bugs", "active", f"{slug}-bug.md")

    if not os.path.exists(bug_path):
        # Fallback: check features/ root (agent might have written there)
        alt_path = os.path.join(cp_dir, "bugs", f"{slug}-bug.md")
        if os.path.exists(alt_path):
            bug_path = alt_path
        else:
            # Last resort: try to extract from response
            os.makedirs(os.path.join(cp_dir, "bugs", "active"), exist_ok=True)
            wf.print_warn("Bug report file not found — extracting from agent response")
            if response:
                response_text = response
                try:
                    data = json.loads(response)
                    if isinstance(data, dict):
                        for key in ("result", "content", "text", "message"):
                            if key in data:
                                response_text = data[key]
                                break
                except (json.JSONDecodeError, TypeError):
                    response_text = response.strip()
                wf._write_file_from_response(response_text, bug_path)

    if not os.path.exists(bug_path):
        wf.print_fail("No bug report generated. Agent may have failed.")
        sys.exit(1)

    wf.print_ok(f"Bug report: {os.path.relpath(bug_path, cp_dir)}")

    # ── Validate ──────────────────────────────────────────────────
    print()
    wf.print_header("Validating Bug Report")

    required_sections = [
        "Observed Behavior",
        "Expected Behavior",
        "Reproduction Steps",
        "Acceptance Criteria",
    ]

    ok, errors = wf.validate_sections(bug_path, required_sections)
    if ok:
        wf.print_ok("Bug report has all required sections")
    else:
        for err in errors:
            wf.print_warn(err)

    # Check diagnostic sections
    diagnostic_sections = [
        "Root Cause Analysis",
        "Affected Code Paths",
        "Fix Strategy",
    ]
    ok2, errors2 = wf.validate_sections(bug_path, diagnostic_sections)
    if ok2:
        wf.print_ok("Diagnostic reasoning complete")
    else:
        for err in errors2:
            wf.print_warn(err)

    # Read severity from frontmatter
    fields = wf.parse_frontmatter(bug_path)
    actual_severity = fields.get("severity", severity)
    wf.print_info(f"Severity: {actual_severity}")

    # Check scope assessment
    with open(bug_path) as f:
        content = f.read()
    is_single = bool(re.search(r"- \[x\] Single-task fix", content, re.IGNORECASE))
    is_multi = bool(re.search(r"- \[x\] Multi-task fix", content, re.IGNORECASE))
    if is_single:
        wf.print_info("Scope: single-task fix")
    elif is_multi:
        wf.print_info("Scope: multi-task fix")
    else:
        wf.print_warn("Scope assessment not completed")

    # ── Plan (optional) ───────────────────────────────────────────
    if args.plan:
        print()
        wf.print_header("Planning Bug Fix")
        wf.print_info("Running plan.py --non-interactive to decompose into tasks...")

        plan_script = os.path.join(relay_dir, "process", "scripts", "plan.py")
        if os.path.exists(plan_script):
            plan_result = subprocess.run(
                [sys.executable, plan_script, slug, "--cp-dir", cp_dir, "--non-interactive"],
                text=True,
            )
            if plan_result.returncode == 0:
                wf.print_ok("Bug decomposed into queue tasks")
            else:
                wf.print_warn("Planning failed — bug spec created but no tasks queued")
        else:
            wf.print_warn("plan.py not found — skipping decomposition")

    # ── Commit & push ─────────────────────────────────────────────
    if args.dry_run or args.no_commit:
        print()
        wf.print_header("Complete")
        wf.print_ok(f"Bug spec generated: {os.path.relpath(bug_path, cp_dir)}")
        if args.dry_run:
            wf.print_info("Skipping commit and push (--dry-run)")
        else:
            wf.print_info("Skipping commit (--no-commit, handled externally)")
        return

    print()
    wf.print_header("Committing Bug Spec")

    rel_path = os.path.relpath(bug_path, cp_dir)
    wf.print_info(f"Staging: {rel_path}")
    # Stage the specific file and also any other new files in bugs/
    subprocess.run(["git", "-C", cp_dir, "add", rel_path], capture_output=True)
    subprocess.run(["git", "-C", cp_dir, "add", "bugs/"], capture_output=True)

    commit_msg = f"fix: telemetry bug report for {slug} (severity: {actual_severity})"
    result = subprocess.run(
        ["git", "-C", cp_dir, "commit", "-m", commit_msg],
        capture_output=True, text=True,
    )

    if result.returncode == 0:
        wf.print_ok(f"Committed: {commit_msg}")
    else:
        wf.print_warn("Nothing to commit (files may already be committed)")
        return

    # Push
    push_result = subprocess.run(
        ["git", "-C", cp_dir, "push"],
        capture_output=True, text=True,
    )

    if push_result.returncode == 0:
        wf.print_ok("Pushed to remote")
    else:
        wf.print_warn(f"Push failed: {push_result.stderr.strip()}")

    # ── Summary ───────────────────────────────────────────────────
    print()
    wf.print_header("Telemetry Alert Handled")
    wf.print_ok(f"Bug spec: {rel_path}")
    wf.print_info(f"Next: review the spec, then run {wf.BOLD}relay plan {slug}{wf.NC}")
    print()


if __name__ == "__main__":
    main()
