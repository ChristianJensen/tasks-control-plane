#!/usr/bin/env python3
"""Scan the task queue and dispatch GitHub Actions agent runners.

Reads queue/**/wave-*.md files, groups ready tasks by target-repo, and fires
repository_dispatch events to each code repo with a matrix of parallel instances
(capped at MAX_INSTANCES per repo).

Reads repo mapping from .relay-config in the control plane.
Requires: GH_TOKEN env var (PAT with contents:write on target repos).
"""

import glob
import json
import os
import re
import subprocess
import sys

MAX_INSTANCES = 4  # Cap parallel runners per repo

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Determine CP_DIR: from env or --cp-dir arg
CP_DIR = os.environ.get("CP_DIR", "")
for i, arg in enumerate(sys.argv[1:], 1):
    if arg == "--cp-dir" and i < len(sys.argv) - 1:
        CP_DIR = sys.argv[i + 1]

if not CP_DIR:
    print("ERROR: CP_DIR not set. Use --cp-dir or set CP_DIR env var.", file=sys.stderr)
    sys.exit(1)

QUEUE_DIR = os.path.join(CP_DIR, "queue")


def load_repo_map() -> dict[str, str]:
    """Load repo name → GitHub NWO mapping from .relay-config."""
    config_path = os.path.join(CP_DIR, ".relay-config")
    repo_map = {}

    if os.path.exists(config_path):
        in_repos = False
        with open(config_path) as f:
            for line in f:
                if re.match(r"^repos:\s*$", line):
                    in_repos = True
                    continue
                if in_repos:
                    m = re.match(r"^  (\S+):\s*(\S+)", line)
                    if m:
                        repo_map[m.group(1)] = m.group(2)
                    elif not line.startswith(" "):
                        break

    if not repo_map:
        # Fallback: parse service-catalog.md
        catalog_path = os.path.join(CP_DIR, ".relay", "service-catalog.md")
        if os.path.exists(catalog_path):
            content = open(catalog_path).read()
            for m in re.finditer(
                r"## (\S+)\n.*?\*\*Repo:\*\*\s*(\S+)", content, re.DOTALL
            ):
                repo_map[m.group(1)] = m.group(2)

    return repo_map


REPO_MAP = load_repo_map()


def get_frontmatter(path: str) -> dict[str, str]:
    """Extract YAML frontmatter key-value pairs from a task file."""
    with open(path) as f:
        content = f.read()
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"^(\w[\w-]*):\s*(.+)", line)
        if kv:
            result[kv.group(1)] = kv.group(2).strip()
    return result


def check_feature_active(feature: str) -> bool:
    """Return True if the feature's lifecycle is 'active' (or if no feature file exists)."""
    features_dir = os.path.join(CP_DIR, "features")
    for suffix in ["-feature.md", "-bug.md"]:
        path = os.path.join(features_dir, "active", f"{feature}{suffix}")
        if os.path.exists(path):
            return True
    for phase in ["draft", "completed", "cancelled"]:
        for suffix in ["-feature.md", "-bug.md"]:
            path = os.path.join(features_dir, phase, f"{feature}{suffix}")
            if os.path.exists(path):
                return False
    # Also check bugs/ directory
    bugs_dir = os.path.join(os.path.dirname(features_dir), "bugs")
    if os.path.isdir(bugs_dir):
        for suffix in ["-feature.md", "-bug.md"]:
            path = os.path.join(bugs_dir, "active", f"{feature}{suffix}")
            if os.path.exists(path):
                return True
        for phase in ["draft", "completed", "cancelled"]:
            for suffix in ["-feature.md", "-bug.md"]:
                path = os.path.join(bugs_dir, phase, f"{feature}{suffix}")
                if os.path.exists(path):
                    return False
    return True  # No feature file — assume active


def scan_queue() -> dict[str, int]:
    """Scan queue for ready tasks, return {repo: count}."""
    counts: dict[str, int] = {}

    for path in glob.glob(os.path.join(QUEUE_DIR, "*", "ready", "wave-*.md")):
        fm = get_frontmatter(path)

        repo = fm.get("target-repo")
        if repo not in REPO_MAP:
            continue

        feature = os.path.basename(os.path.dirname(os.path.dirname(path)))
        if feature and not check_feature_active(feature):
            continue

        counts[repo] = counts.get(repo, 0) + 1

    return counts


def dispatch(repo_key: str, task_count: int) -> bool:
    """Fire a repository_dispatch event to a code repo. Returns True on success."""
    github_repo = REPO_MAP[repo_key]
    instance_count = min(task_count, MAX_INSTANCES)
    instances = list(range(instance_count))

    # Read relay NWO and relay repo from config for the payload
    relay_nwo = ""
    relay_repo = ""
    config_path = os.path.join(CP_DIR, ".relay-config")
    if os.path.exists(config_path):
        with open(config_path) as f:
            for line in f:
                m = re.match(r"^relay-nwo:\s*(.+)", line)
                if m:
                    relay_nwo = m.group(1).strip()
                m = re.match(r"^relay-repo:\s*(.+)", line)
                if m:
                    relay_repo = m.group(1).strip()

    payload = json.dumps({
        "event_type": "agent-task-available",
        "client_payload": {
            "instances": json.dumps(instances),
            "task_count": task_count,
            "relay_nwo": relay_nwo,
            "relay_repo": relay_repo,
        },
    })

    print(f"Dispatching {instance_count} agent(s) to {github_repo} ({task_count} ready tasks)")

    result = subprocess.run(
        [
            "gh", "api",
            f"repos/{github_repo}/dispatches",
            "--method", "POST",
            "--input", "-",
        ],
        input=payload,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}", file=sys.stderr)
        return False
    else:
        print(f"  OK")
        return True


def main() -> None:
    if not os.environ.get("GH_TOKEN"):
        print("ERROR: GH_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    counts = scan_queue()

    if not counts:
        print("No ready tasks found. Nothing to dispatch.")
        return

    failures = []
    for repo_key, task_count in sorted(counts.items()):
        if not dispatch(repo_key, task_count):
            failures.append(repo_key)

    if failures:
        print(f"FATAL: Failed to dispatch to: {', '.join(failures)}", file=sys.stderr)
        sys.exit(1)

    print(f"\nDispatched to {len(counts)} repo(s): {', '.join(sorted(counts.keys()))}")


if __name__ == "__main__":
    main()
