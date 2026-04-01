#!/usr/bin/env python3
"""Relay Report Bug — orchestrate bug reporting through a single AI session.

Usage:
    report-bug.py [--cp-dir <path>]

Pipeline:
    1. Load context        [DETERMINISTIC] — read service catalog, bug template
    2. Interview + Diagnose [SINGLE INTERACTIVE AI] — collect details, write report, diagnose
    3. Validate            [DETERMINISTIC] — check bug report has required sections
    4. Present & commit    [DETERMINISTIC] — show report, ask about commit, route to next step
"""

import argparse
import os
import re
import subprocess
import sys

# Add scripts directory to path for _workflow import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _workflow as wf


BUG_REPORT_PROMPT = """\
You are helping a developer report and diagnose a bug.

Complete all four phases below in this single session. Do not ask the user to exit or restart between phases.

## Phase 1: Interview

Ask these questions conversationally, one round at a time (2-3 questions per round):

1. **What did you observe?** — Collect actual behavior: error messages, status codes, unexpected output.
2. **What did you expect to happen?** — Collect the expected behavior.
3. **Steps to reproduce** — Collect numbered reproduction steps.
4. **Which repo(s) are affected?** — Reference the service catalog below.
5. **Environment details** — Repo/branch, endpoint/component, trigger frequency.
6. **Evidence** — Ask if they have screenshots, logs, or other evidence to attach.

## Phase 2: Write Bug Report

After the interview, derive a kebab-case slug from the bug description (e.g., `duplicate-task-creation`).

Write the bug report to `bugs/draft/{{slug}}-bug.md` using the template below.
Set `lifecycle: draft`, `type: bug`, and fill in the severity based on this rubric:
- **critical**: Data loss, security vulnerability, or complete feature outage
- **high**: Core feature broken, no workaround
- **medium**: Wrong behavior but workaround exists
- **low**: Cosmetic issue, minor UX annoyance

Tell the user what severity you chose and why. They can override.

## Phase 3: Diagnosis

**Without exiting**, diagnose the bug by exploring the codebase:

1. Read the bug report you just wrote to confirm the observed behavior and reproduction steps.
2. Search the affected repo(s) for relevant code paths using Grep and Read.
3. Trace the logic from the reproduction steps through the codebase.
4. Identify the likely root cause — reference specific files, functions, and line numbers.

## Phase 4: Update Bug Report

Update the bug report file in place with diagnostic findings:
- Fill in "Root Cause Analysis" with your findings
- Fill in the "Affected Code Paths" table (Repo | File | Function/Line | Issue)
- Propose a "Fix Strategy"
- Assess scope: is this a single-task fix (one repo, <50 lines) or multi-task?
  Check the appropriate box in the "Scope Assessment" section.

## Rules

- Do NOT commit or push — the orchestrator handles that.
- Fill ALL sections of the template from the interview answers.
- Be specific in diagnosis: reference actual file paths, function names, and line numbers.
- If you cannot determine root cause with confidence, say so and explain what you tried.
- Complete all phases in this single session.

## Context

### Service Catalog
{service_catalog}

### Bug Report Template
{template}
"""


def main():
    parser = argparse.ArgumentParser(description="Report and diagnose a bug via phased AI sessions.")
    parser.add_argument("--cp-dir", help="Control plane directory")
    args = parser.parse_args()

    # Resolve directories
    cp_dir = args.cp_dir or wf.resolve_cp_dir() or os.environ.get("CP_DIR")
    if not cp_dir:
        print("Error: Cannot determine control plane directory.", file=sys.stderr)
        print("Run from a control plane directory or pass --cp-dir.", file=sys.stderr)
        sys.exit(1)

    relay_dir = wf.resolve_relay_dir()
    if not relay_dir:
        print("Error: Cannot determine Relay framework directory.", file=sys.stderr)
        sys.exit(1)

    # ── Step 1: Load context ────────────────────────────────────
    wf.print_header("Report Bug")
    print()

    # Read prerequisites
    catalog_path = os.path.join(cp_dir, ".relay", "service-catalog.md")
    service_catalog = ""
    if os.path.exists(catalog_path):
        with open(catalog_path) as f:
            service_catalog = f.read()
        wf.print_ok("Service catalog loaded")
    else:
        wf.print_warn("No service-catalog.md found")

    template_path = os.path.join(relay_dir, "process", "templates", "bug-report.md")
    template = ""
    if os.path.exists(template_path):
        with open(template_path) as f:
            template = f.read()
        wf.print_ok("Bug report template loaded")
    else:
        wf.print_fail("Bug report template not found")
        sys.exit(1)

    # ── Step 2: Interview + Diagnosis (single session) ──────────
    print()
    wf.print_header("Interview + Diagnosis")
    wf.print_info("Launching AI session for bug interview and diagnosis...")
    print()

    bug_prompt = BUG_REPORT_PROMPT.format(
        service_catalog=service_catalog or "(no service catalog found)",
        template=template,
    )

    model = wf.resolve_model(cp_dir, role="planner")
    wf.invoke_agent(bug_prompt, cp_dir, interactive=True, model=model)

    # ── Detect the bug report file ──────────────────────────────
    print()
    wf.print_header("Detecting Bug Report")

    bugs_dir = os.path.join(cp_dir, "bugs")
    bug_files = []
    if os.path.isdir(bugs_dir):
        for phase in os.listdir(bugs_dir):
            phase_dir = os.path.join(bugs_dir, phase)
            if not os.path.isdir(phase_dir):
                continue
            for f in os.listdir(phase_dir):
                if f.endswith("-bug.md"):
                    path = os.path.join(phase_dir, f)
                    bug_files.append((os.path.getmtime(path), path, f))

    if not bug_files:
        wf.print_fail("No bug report found in bugs/")
        wf.print_info("The AI session should have created a bugs/draft/<slug>-bug.md file.")
        sys.exit(1)

    # Pick the most recently modified bug file
    bug_files.sort(reverse=True)
    bug_path = bug_files[0][1]
    bug_filename = bug_files[0][2]
    slug = bug_filename.replace("-bug.md", "")

    wf.print_ok(f"Bug report: {os.path.relpath(bug_path, cp_dir)}")

    # ── Step 3: Validate ────────────────────────────────────────
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

    # Read severity and scope from frontmatter
    fields = wf.parse_frontmatter(bug_path)
    severity = fields.get("severity", "unknown")
    wf.print_info(f"Severity: {severity}")

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

    # ── Step 4: Present & commit ────────────────────────────────
    print()
    wf.print_header("Bug Report Complete")

    wf.print_ok(f"Bug report: {os.path.relpath(bug_path, cp_dir)}")

    print()
    choice = input(f"  Commit artifacts? [{wf.BOLD}y{wf.NC}/N/open] ").strip().lower()

    if choice == "open":
        subprocess.run(["open", bug_path])
        print()
        choice = input(f"  Commit artifacts? [{wf.BOLD}y{wf.NC}/N] ").strip().lower()

    if choice == "y":
        git_add = ["git", "-C", cp_dir, "add", os.path.relpath(bug_path, cp_dir)]
        subprocess.run(git_add, capture_output=True)

        # Add evidence directory if it exists
        evidence_dir = os.path.join(bugs_dir, slug, "evidence")
        if os.path.isdir(evidence_dir):
            subprocess.run(
                ["git", "-C", cp_dir, "add", os.path.relpath(evidence_dir, cp_dir)],
                capture_output=True,
            )

        commit_msg = f"fix: bug report for {slug} (severity: {severity})"
        result = subprocess.run(
            ["git", "-C", cp_dir, "commit", "-m", commit_msg],
            capture_output=True, text=True,
        )

        if result.returncode == 0:
            wf.print_ok(f"Committed: {commit_msg}")
        else:
            wf.print_warn("Nothing to commit (files may already be committed)")
    else:
        wf.print_info("Skipped commit.")

    # Route to next step
    print()
    if is_multi:
        continue_to_plan = input(f"  Continue to planning? [{wf.BOLD}y{wf.NC}/N] ").strip().lower()

        if continue_to_plan == "y":
            plan_script = os.path.join(relay_dir, "process", "scripts", "plan.py")
            if os.path.exists(plan_script):
                print()
                os.execv(sys.executable, [sys.executable, plan_script, slug, "--cp-dir", cp_dir])
            else:
                wf.print_fail("plan.py not found")
                sys.exit(1)
        else:
            print(f"  Next: {wf.BOLD}relay plan {slug}{wf.NC}")
            print()
    else:
        print(f"  Next: Create a task in {wf.BOLD}queue/{slug}/{wf.NC} and run {wf.BOLD}relay handoff{wf.NC}")
        print()


if __name__ == "__main__":
    main()
