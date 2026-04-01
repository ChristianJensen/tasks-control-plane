#!/usr/bin/env python3
"""Relay Validate — standalone validation gates for feature specs and queue tasks.

Usage:
    validate.py <feature-slug> [--cp-dir <path>] [--gate <gate>] [--json]

Gates:
    frontmatter    Required fields and allowed enum values
    sections       Non-empty sections, no template placeholders
    readiness      All checklist items checked
    queue          Filename patterns, frontmatter consistency, contiguous waves
    behavioral     Task files contain GIVEN/WHEN/THEN behavioral scenarios
    contracts      Referenced contract files exist and are valid JSON
    all            Run all gates (default)
"""

import argparse
import glob
import json
import os
import re
import sys

# Add scripts directory to path for _workflow import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _workflow as wf


# ── Gate definitions ─────────────────────────────────────────────

FEATURE_REQUIRED_FIELDS = ["lifecycle", "version"]
FEATURE_ALLOWED_VALUES = {
    "lifecycle": ["draft", "active", "paused", "cancelled", "replanning", "completed", "live-dev", "live-staging", "live-prod"],
}
FEATURE_REQUIRED_SECTIONS = [
    "Problem Statement",
    "Requirements",
    "Acceptance Criteria",
]

BUG_REQUIRED_FIELDS = ["lifecycle", "type", "severity"]
BUG_ALLOWED_VALUES = {
    "lifecycle": ["draft", "active", "paused", "cancelled", "replanning", "completed", "live-dev", "live-staging", "live-prod"],
    "type": ["bug"],
    "severity": ["critical", "high", "medium", "low"],
}

TASK_REQUIRED_FIELDS = ["status", "target-repo", "wave", "priority", "feature", "type"]
TASK_ALLOWED_VALUES = {
    "status": ["ready", "in-progress", "done", "blocked", "pending", "paused", "cancelled"],
    "priority": ["critical", "high", "normal", "low"],
    "type": ["feature", "bug"],
}


def run_frontmatter_gate(feature_path, task_paths):
    """Validate frontmatter on feature spec and all task files."""
    results = []

    # Detect feature vs bug
    fields = wf.parse_frontmatter(feature_path)
    is_bug = fields.get("type") == "bug"

    if is_bug:
        ok, errors = wf.validate_frontmatter(
            feature_path, BUG_REQUIRED_FIELDS, BUG_ALLOWED_VALUES
        )
    else:
        ok, errors = wf.validate_frontmatter(
            feature_path, FEATURE_REQUIRED_FIELDS, FEATURE_ALLOWED_VALUES
        )
    results.append(("feature-spec", feature_path, ok, errors))

    for tp in task_paths:
        ok, errors = wf.validate_frontmatter(
            tp, TASK_REQUIRED_FIELDS, TASK_ALLOWED_VALUES
        )
        results.append(("task", tp, ok, errors))

    return results


def run_sections_gate(feature_path):
    """Validate required sections in feature spec."""
    fields = wf.parse_frontmatter(feature_path)
    is_bug = fields.get("type") == "bug"

    if is_bug:
        required = ["Observed Behavior", "Expected Behavior", "Reproduction Steps"]
    else:
        required = FEATURE_REQUIRED_SECTIONS

    ok, errors = wf.validate_sections(feature_path, required)
    return [("feature-spec", feature_path, ok, errors)]


def run_readiness_gate(feature_path):
    """Validate readiness checklist."""
    ok, errors = wf.validate_readiness_checklist(feature_path)
    return [("readiness", feature_path, ok, errors)]


def _has_cycle(graph, node, visited, stack):
    """DFS cycle detection. Returns the cycle path if found, else None."""
    visited.add(node)
    stack.add(node)
    for dep in graph.get(node, []):
        if dep in stack:
            return [node, dep]
        if dep not in visited:
            result = _has_cycle(graph, dep, visited, stack)
            if result is not None:
                return [node] + result
    stack.remove(node)
    return None


def run_queue_gate(task_paths, service_repos):
    """Validate queue file integrity."""
    results = []

    for tp in task_paths:
        ok, errors = wf.validate_queue_filename(tp)
        results.append(("queue-filename", tp, ok, errors))

    # Check wave contiguity per repo
    repo_waves = {}
    for tp in task_paths:
        fields = wf.parse_frontmatter(tp)
        repo = fields.get("target-repo", "unknown")
        wave = int(fields.get("wave", 0))
        repo_waves.setdefault(repo, set()).add(wave)

    for repo, waves in repo_waves.items():
        waves_sorted = sorted(waves)
        if waves_sorted:
            expected = list(range(waves_sorted[0], waves_sorted[-1] + 1))
            if waves_sorted != expected:
                results.append((
                    "wave-contiguity",
                    repo,
                    False,
                    [f"Non-contiguous waves for {repo}: {waves_sorted} (expected {expected})"],
                ))

    # Warn if in-progress tasks are missing claim metadata
    for tp in task_paths:
        fields = wf.parse_frontmatter(tp)
        if fields.get("status") == "in-progress":
            claimed_by = fields.get("claimed-by", "").strip().strip('"')
            if not claimed_by:
                results.append((
                    "queue-claim",
                    tp,
                    True,  # soft warning, not a failure
                    [f"Warning: {os.path.basename(tp)} is in-progress but has no claimed-by"],
                ))

    # Check repos are valid
    if service_repos:
        for tp in task_paths:
            fields = wf.parse_frontmatter(tp)
            repo = fields.get("target-repo", "")
            if repo and repo not in service_repos:
                results.append((
                    "repo-valid",
                    tp,
                    False,
                    [f"Unknown repo: {repo} (valid: {', '.join(sorted(service_repos))})"],
                ))

    # ── Dependency validation ─────────────────────────────────
    task_filenames = set(os.path.basename(tp) for tp in task_paths)
    dep_graph = {}  # filename -> list of dep filenames

    for tp in task_paths:
        fields = wf.parse_frontmatter(tp)
        depends_on = fields.get("depends-on", [])
        if isinstance(depends_on, str):
            depends_on = [depends_on] if depends_on else []

        filename = os.path.basename(tp)
        dep_graph[filename] = depends_on

        for dep in depends_on:
            # Self-reference check
            if dep == filename:
                results.append((
                    "depends-on",
                    tp,
                    False,
                    [f"Task depends on itself: {dep}"],
                ))
            # Existence check (must be in the same feature directory)
            elif dep not in task_filenames:
                results.append((
                    "depends-on",
                    tp,
                    False,
                    [f"Dependency not found in queue: {dep}"],
                ))

    # Cycle detection across all tasks
    visited = set()
    for node in dep_graph:
        if node not in visited:
            cycle_path = _has_cycle(dep_graph, node, visited, set())
            if cycle_path is not None:
                results.append((
                    "depends-on-cycle",
                    " → ".join(cycle_path),
                    False,
                    [f"Circular dependency detected: {' → '.join(cycle_path)}"],
                ))
                break  # Report first cycle found

    return results


def run_behavioral_gate(task_paths):
    """Validate that task files contain behavioral acceptance criteria."""
    results = []
    for tp in task_paths:
        with open(tp) as f:
            content = f.read()
        body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
        ac_match = re.search(
            r'(?:^|\n)##\s*Acceptance Criteria\s*\n(.*?)(?:\n##[^#]|\Z)',
            body, re.DOTALL
        )
        if not ac_match:
            results.append(("behavioral", tp, False, ["Missing Acceptance Criteria section"]))
            continue
        ac_content = ac_match.group(1)
        given_count = len(re.findall(r'\*\*GIVEN\*\*', ac_content))
        when_count = len(re.findall(r'\*\*WHEN\*\*', ac_content))
        then_count = len(re.findall(r'\*\*THEN\*\*', ac_content))
        if given_count == 0:
            results.append(("behavioral", tp, False,
                ["No behavioral scenarios found (expected **GIVEN**/**WHEN**/**THEN** format)"]))
        elif when_count < given_count or then_count < given_count:
            results.append(("behavioral", tp, False,
                [f"Incomplete scenarios: {given_count} GIVEN, {when_count} WHEN, {then_count} THEN"]))
        else:
            results.append(("behavioral", tp, True, []))
    return results


def run_contracts_gate(feature_path, task_paths, cp_dir):
    """Validate referenced contracts exist and are valid JSON."""
    results = []
    checked = set()

    # Collect contract references from all task files
    for tp in task_paths:
        fields = wf.parse_frontmatter(tp)
        contracts = fields.get("contracts", [])
        if isinstance(contracts, str):
            contracts = [contracts]
        for c in contracts:
            if c in checked:
                continue
            checked.add(c)
            contract_path = os.path.join(cp_dir, c)
            ok, errors = wf.validate_contracts(contract_path)
            results.append(("contract", c, ok, errors))

    return results


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Validate a Relay feature and its queue tasks.")
    parser.add_argument("feature", help="Feature slug (e.g., add-due-dates)")
    parser.add_argument("--cp-dir", help="Control plane directory")
    parser.add_argument(
        "--gate",
        choices=["frontmatter", "sections", "readiness", "queue", "behavioral", "contracts", "all"],
        default="all",
        help="Which validation gate to run (default: all)",
    )
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output JSON")
    args = parser.parse_args()

    # Resolve CP dir
    cp_dir = args.cp_dir or wf.resolve_cp_dir() or os.environ.get("CP_DIR")
    if not cp_dir:
        print("Error: Cannot determine control plane directory.", file=sys.stderr)
        print("Use --cp-dir or set CP_DIR env var.", file=sys.stderr)
        sys.exit(1)

    # Find feature spec in features/<phase>/<name>-{feature,bug}.md
    spec_path = None
    features_dir = os.path.join(cp_dir, "features")
    for phase in ["active", "draft", "completed", "cancelled"]:
        for suffix in ["-feature.md", "-bug.md"]:
            candidate = os.path.join(features_dir, phase, f"{args.feature}{suffix}")
            if os.path.exists(candidate):
                spec_path = candidate
                break
        if spec_path:
            break
    # Also check bugs/ directory
    if not spec_path:
        bugs_dir = os.path.join(cp_dir, "bugs")
        if os.path.isdir(bugs_dir):
            for phase in ["draft", "active", "completed", "cancelled"]:
                candidate = os.path.join(bugs_dir, phase, f"{args.feature}-bug.md")
                if os.path.exists(candidate):
                    spec_path = candidate
                    break
    if not spec_path:
        print(f"Error: No spec found for '{args.feature}'.", file=sys.stderr)
        print(f"  Looked in: {features_dir}/{{active,draft,...}}/{args.feature}-{{feature,bug}}.md", file=sys.stderr)
        sys.exit(1)

    # Find task files: queue/<feature>/<status>/wave-*.md
    queue_dir = os.path.join(cp_dir, "queue", args.feature)
    task_paths = sorted(glob.glob(os.path.join(queue_dir, "*", "wave-*.md")))

    # Resolve service catalog repos
    service_repos = set()
    catalog = wf.parse_service_catalog(cp_dir)
    for entry in catalog:
        service_repos.add(entry["name"])
    # Also try .relay-config repos
    for short, _nwo in wf.read_relay_config_repos(cp_dir):
        service_repos.add(short)

    # Run gates
    gates_to_run = (
        ["frontmatter", "sections", "readiness", "queue", "behavioral", "contracts"]
        if args.gate == "all"
        else [args.gate]
    )

    all_results = []
    for gate in gates_to_run:
        if gate == "frontmatter":
            all_results.extend(run_frontmatter_gate(spec_path, task_paths))
        elif gate == "sections":
            all_results.extend(run_sections_gate(spec_path))
        elif gate == "readiness":
            all_results.extend(run_readiness_gate(spec_path))
        elif gate == "queue":
            if task_paths:
                all_results.extend(run_queue_gate(task_paths, service_repos))
            else:
                all_results.append(("queue", queue_dir, True, ["No task files found (OK if not yet decomposed)"]))
        elif gate == "behavioral":
            if task_paths:
                all_results.extend(run_behavioral_gate(task_paths))
            else:
                all_results.append(("behavioral", "-", True, ["No task files to check behaviors for"]))
        elif gate == "contracts":
            if task_paths:
                all_results.extend(run_contracts_gate(spec_path, task_paths, cp_dir))
            else:
                all_results.append(("contracts", "-", True, ["No task files to check contracts for"]))

    # Output
    if args.json_output:
        json_results = []
        for gate_name, target, ok, errors in all_results:
            json_results.append({
                "gate": gate_name,
                "target": target,
                "pass": ok,
                "errors": errors,
            })
        print(json.dumps(json_results, indent=2))
    else:
        total_pass = 0
        total_fail = 0

        wf.print_header(f"Validating: {args.feature}")
        print()

        current_gate = None
        for gate_name, target, ok, errors in all_results:
            # Print gate header on change
            display_gate = gate_name.split("-")[0] if "-" in gate_name else gate_name
            if display_gate != current_gate:
                current_gate = display_gate

            short_target = os.path.basename(target) if os.path.sep in target else target

            if ok:
                total_pass += 1
                wf.print_ok(f"{gate_name}: {short_target}")
            else:
                total_fail += 1
                wf.print_fail(f"{gate_name}: {short_target}")
                for err in errors:
                    print(f"      {err}")

        print()
        if total_fail == 0:
            wf.print_ok(f"All {total_pass} checks passed")
        else:
            wf.print_fail(f"{total_fail} failed, {total_pass} passed")

    sys.exit(0 if all(r[2] for r in all_results) else 1)


if __name__ == "__main__":
    main()
