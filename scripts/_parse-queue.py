#!/usr/bin/env python3
"""Parse the Relay task queue and output sorted candidates as JSON.

Usage:
    _parse-queue.py <queue-dir> <target-repo>

Output: JSON array of {rank, wave, path, status, priority, feature, type}

Sorts by wave ASC, then priority rank ASC.
Skips tasks whose parent feature lifecycle is not 'active'.
Use --status all to return tasks in any status (for relay status).
"""

import argparse
import glob
import json
import os
import re
import sys

# Add scripts directory to path for _workflow import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _workflow import parse_frontmatter_string

PRIORITY_RANK = {"critical": 0, "high": 1, "normal": 2, "low": 3}

# Known task status directory names
TASK_STATUSES = {"pending", "ready", "in-progress", "done", "blocked", "paused", "cancelled"}
# Known feature phase directory names
FEATURE_PHASES = {"draft", "active", "completed", "cancelled"}


def parse_frontmatter(content):
    """Wrapper for compatibility. Delegates to _workflow parser."""
    return parse_frontmatter_string(content)


def status_from_path(path):
    """Infer task status from parent directory name."""
    return os.path.basename(os.path.dirname(path))


def feature_from_task_path(path):
    """Extract feature slug from task path: queue/<feature>/<status>/wave-*.md."""
    return os.path.basename(os.path.dirname(os.path.dirname(path)))


def find_feature_file(base_dir, feature_name):
    """Find a feature spec in features/<phase>/<name>-{feature,bug}.md."""
    features_dir = os.path.join(base_dir, "features")
    for phase in FEATURE_PHASES:
        for suffix in ("feature", "bug"):
            path = os.path.join(features_dir, phase, f"{feature_name}-{suffix}.md")
            if os.path.exists(path):
                return path
    # Also check bugs/
    bugs_dir = os.path.join(os.path.dirname(features_dir), "bugs")
    if os.path.isdir(bugs_dir):
        for phase in FEATURE_PHASES:
            path = os.path.join(bugs_dir, phase, f"{feature_name}-bug.md")
            if os.path.exists(path):
                return path
    return None


def is_feature_active(queue_dir, feature_name):
    """Check if a feature's lifecycle is 'active'. Returns True if active or no spec found."""
    base_dir = os.path.dirname(queue_dir)
    feature_path = find_feature_file(base_dir, feature_name)
    if not feature_path:
        return True
    phase = os.path.basename(os.path.dirname(feature_path))
    return phase == "active"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue_dir", help="Path to the queue directory")
    parser.add_argument("target_repo", help="Target repo name to filter by")
    parser.add_argument("--with-roadmap", metavar="FEATURES_DIR",
                        help="Deprecated, ignored. Kept for backward compatibility.")
    parser.add_argument("--status", default="ready",
                        help="Task status to filter for (default: ready)")
    parser.add_argument("--execution", default="all",
                        help="Execution mode filter: autonomous, supervised, guided, or comma-separated (default: all)")
    args = parser.parse_args()

    # ── Collect ALL tasks across all repos (needed for cross-repo dep checks) ──
    all_tasks = []

    # Directory layout: queue/<feature>/<status>/wave-*.md
    task_paths = set()
    task_paths.update(glob.glob(os.path.join(args.queue_dir, "*", "*", "wave-*.md")))

    for path in task_paths:
        with open(path) as f:
            content = f.read()

        fields = parse_frontmatter(content)
        if not fields:
            continue

        status = status_from_path(path)
        repo = fields.get("target-repo")
        wave = fields.get("wave")
        priority = fields.get("priority", "normal")
        feature = fields.get("feature") or feature_from_task_path(path)
        task_type = fields.get("type", "feature")

        # Parse depends-on (list field from frontmatter)
        depends_on = fields.get("depends-on", [])
        if isinstance(depends_on, str):
            depends_on = [depends_on] if depends_on else []

        # Skip tasks for non-active features
        if feature and not is_feature_active(args.queue_dir, feature):
            continue

        rank = PRIORITY_RANK.get(priority, 2)
        wave_num = int(wave) if wave else 0

        all_tasks.append({
            "rank": rank,
            "wave": wave_num,
            "path": path,
            "status": status,
            "priority": priority,
            "feature": feature or "",
            "type": task_type,
            "task_id": fields.get("task-id", ""),
            "execution": fields.get("execution", ""),
            "claimed_by": fields.get("claimed-by", ""),
            "claimed_at": fields.get("claimed-at", ""),
            "claimed_on": fields.get("claimed-on", ""),
            "depends_on": depends_on,
            "target_repo": repo or "",
        })

    # ── Build status lookup for dependency resolution ──
    # Index by task-id (preferred), full filename, and short name (backward compat)
    dep_status = {}
    for t in all_tasks:
        filename = os.path.basename(t["path"])
        dep_status[filename] = t["status"]
        if t["task_id"]:
            dep_status[t["task_id"]] = t["status"]
            dep_status[t["task_id"] + ".md"] = t["status"]
        # Short name: strip wave-N-repo- prefix for legacy deps
        short = re.sub(r"^wave-\d+-\w+-", "", filename)
        if short != filename:
            dep_status[short] = t["status"]

    # ── Filter by repo, status, and dependency satisfaction ──
    results = []
    for task in all_tasks:
        # Filter by target repo
        if task["target_repo"] != args.target_repo:
            continue

        # Filter by status
        if args.status != "all" and task["status"] != args.status:
            continue

        # Check dependencies (only for actionable statuses like "ready")
        deps = task["depends_on"]
        if deps and args.status != "all":
            all_met = all(dep_status.get(d) == "done" for d in deps)
            if not all_met:
                continue

        # Resolve effective execution mode (task → feature → default)
        exec_mode = task["execution"]
        if not exec_mode:
            feature_name = task["feature"]
            if feature_name:
                base_dir = os.path.dirname(args.queue_dir)
                feature_path = find_feature_file(base_dir, feature_name)
                if feature_path:
                    with open(feature_path) as ff:
                        ff_fields = parse_frontmatter(ff.read())
                    exec_mode = ff_fields.get("execution", "supervised")
            if not exec_mode:
                exec_mode = "supervised"

        # Filter by execution mode if requested
        if args.execution and args.execution != "all":
            allowed = [e.strip() for e in args.execution.split(",")]
            if exec_mode not in allowed:
                continue

        # Build result (exclude internal fields)
        results.append({
            "rank": task["rank"],
            "wave": task["wave"],
            "path": task["path"],
            "status": task["status"],
            "priority": task["priority"],
            "feature": task["feature"],
            "type": task["type"],
            "execution": exec_mode,
            "claimed_by": task["claimed_by"],
            "claimed_at": task["claimed_at"],
            "claimed_on": task["claimed_on"],
            "depends_on": task["depends_on"],
        })

    # Sort by wave ASC, then priority rank ASC
    results.sort(key=lambda x: (x["wave"], x["rank"]))
    print(json.dumps(results))


if __name__ == "__main__":
    main()
