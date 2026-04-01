#!/usr/bin/env python3
"""Relay Handoff Note — generate a structured session handoff document.

Usage:
    _handoff-note.py <task-file> --status <done|blocked> --work-dir <path> --branch <name>
                     [--exit-code N] [--cp-dir <path>]

Extracts git context (commits, changed files, PR status) and writes a handoff
note to handoffs/<feature>/<task-filename>-handoff.md. All external calls use
try/except with timeouts for graceful degradation (D4).
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

# Add scripts directory to path for _workflow import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _workflow import parse_frontmatter_string


def run_cmd(args, cwd=None, timeout=15):
    """Run a command with timeout, returning stdout or '(unavailable)' on failure."""
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, cwd=cwd
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return "(unavailable)"


def get_commits(work_dir, branch):
    """Get commits on branch since diverging from origin/main."""
    output = run_cmd(
        ["git", "log", "origin/main..HEAD", "--oneline"],
        cwd=work_dir,
    )
    if output == "(unavailable)" or not output:
        return "No commits on this branch"
    return output


def get_changed_files(work_dir):
    """Get files changed relative to origin/main."""
    output = run_cmd(
        ["git", "diff", "--name-only", "origin/main"],
        cwd=work_dir,
    )
    if output == "(unavailable)" or not output:
        return "(no files changed)"
    return output


def get_pr_status(branch, work_dir):
    """Check if a PR exists for this branch."""
    # Get repo NWO from git remote
    nwo = run_cmd(["git", "remote", "get-url", "origin"], cwd=work_dir)
    if nwo == "(unavailable)":
        return "(unavailable)"
    # Extract NWO from URL
    nwo = re.sub(r".*github\.com[:/]", "", nwo)
    nwo = re.sub(r"\.git$", "", nwo)
    if not nwo:
        return "(unavailable)"

    output = run_cmd(
        ["gh", "pr", "list", "--head", branch, "--repo", nwo,
         "--json", "number,state,url", "--limit", "1"],
        cwd=work_dir,
        timeout=20,
    )
    if output == "(unavailable)" or not output:
        return "(no PR found)"

    try:
        import json
        prs = json.loads(output)
        if prs:
            pr = prs[0]
            return f"PR #{pr['number']} ({pr['state']}): {pr.get('url', '')}"
    except (ValueError, KeyError, IndexError):
        pass
    return "(no PR found)"


def find_unblocked_tasks(cp_dir, feature, task_filename):
    """Find tasks that may become unblocked now that this task is done."""
    import glob
    queue_dir = os.path.join(cp_dir, "queue", feature)
    unblocked = []
    paths = glob.glob(os.path.join(queue_dir, "*", "wave-*.md"))
    for path in paths:
        with open(path) as f:
            content = f.read()
        fields = parse_frontmatter_string(content)
        deps = fields.get("depends-on", [])
        if isinstance(deps, str):
            deps = [deps] if deps else []
        if task_filename in deps:
            unblocked.append(os.path.basename(path))
    return unblocked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_file", help="Path to the task queue file")
    parser.add_argument("--status", required=True, choices=["done", "blocked"],
                        help="Session outcome")
    parser.add_argument("--work-dir", required=True, help="Code repo working directory")
    parser.add_argument("--branch", required=True, help="Git branch name")
    parser.add_argument("--exit-code", type=int, default=0, help="Agent exit code")
    parser.add_argument("--cp-dir", help="Control plane directory")
    parser.add_argument("--cost-json", default="{}", help="JSON string with cost data")
    args = parser.parse_args()

    # Read task file
    with open(args.task_file) as f:
        task_content = f.read()
    fields = parse_frontmatter_string(task_content)

    feature = fields.get("feature", "unknown")
    task_filename = os.path.basename(args.task_file)
    claimed_by = fields.get("claimed-by", "unknown")
    if claimed_by in ('""', ""):
        claimed_by = "unknown"

    # Extract description from task body
    desc_match = re.search(r"## Description\s*\n(.*?)(?:\n##|\Z)", task_content, re.DOTALL)
    description = desc_match.group(1).strip() if desc_match else task_filename

    # Gather git context
    commits = get_commits(args.work_dir, args.branch)
    changed_files = get_changed_files(args.work_dir)
    pr_status = get_pr_status(args.branch, args.work_dir)

    # Find newly unblocked tasks
    whats_next = ""
    if args.status == "done" and args.cp_dir:
        unblocked = find_unblocked_tasks(args.cp_dir, feature, task_filename)
        if unblocked:
            whats_next = "Newly unblocked tasks:\n" + "\n".join(f"- {t}" for t in unblocked)
        else:
            whats_next = "No tasks were blocked on this one."
    elif args.status == "blocked":
        whats_next = f"Task blocked with exit code {args.exit_code}. Needs investigation."

    # Parse cost data
    cost_section = ""
    try:
        cost_data = json.loads(args.cost_json)
        if cost_data and cost_data.get("cost_usd", 0) > 0:
            cost_usd = cost_data.get("cost_usd", 0)
            input_tokens = cost_data.get("input_tokens", 0)
            output_tokens = cost_data.get("output_tokens", 0)
            duration_ms = cost_data.get("duration_ms", 0)
            duration_s = duration_ms / 1000
            cost_section = f"""
## Cost
**Cost:** ${cost_usd:.4f}  |  **Tokens:** {input_tokens:,} in / {output_tokens:,} out  |  **Duration:** {duration_s:.0f}s
"""
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build resume prompt
    resume_prompt = f"""You are resuming work on branch {args.branch} for task {task_filename}.

{task_content}

Previous session: {args.status}. Commits:
{commits}

Continue from where the previous agent left off."""

    # Build handoff note
    handoff = f"""---
task: {task_filename}
feature: {feature}
branch: {args.branch}
status: {args.status}
timestamp: {timestamp}
agent: {claimed_by}
---
## Session Summary
**Task:** {description}  |  **Status:** {args.status}  |  **Exit:** {args.exit_code}
{cost_section}
## What Was Done
{commits}

## Files Changed
{changed_files}

## PR Status
{pr_status}

## What's Next
{whats_next}

## Resume Prompt
```
{resume_prompt}
```
"""

    # Write handoff note
    cp_dir = args.cp_dir
    if not cp_dir:
        # Infer from task file path: <cp_dir>/queue/<feature>/<status>/wave-*.md (4 levels up)
        cp_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(args.task_file))))

    output_dir = os.path.join(cp_dir, "handoffs", feature)
    os.makedirs(output_dir, exist_ok=True)

    output_filename = task_filename.replace(".md", "-handoff.md")
    output_path = os.path.join(output_dir, output_filename)

    with open(output_path, "w") as f:
        f.write(handoff)

    print(f"Handoff written: {os.path.relpath(output_path, cp_dir)}")


if __name__ == "__main__":
    main()
