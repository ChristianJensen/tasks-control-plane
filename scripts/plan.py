#!/usr/bin/env python3
"""Relay Plan — decompose a feature spec into repo-scoped, wave-grouped queue tasks.

Usage:
    plan.py <feature-slug> [--cp-dir <path>] [--dry-run]

Pipeline:
    1. Preconditions   [DETERMINISTIC]    — verify spec, lifecycle
    2. Load context    [DETERMINISTIC]    — generate repo manifests, assemble context
    3. Decompose       [INTERACTIVE AI]   — AI writes JSON to _decomposition.json
    4. Validate        [DETERMINISTIC]    — <400 lines, valid repos, contiguous waves
    5. Write contracts [DETERMINISTIC]    — apply contract diff
    6. Write tasks     [DETERMINISTIC]    — create queue files from template
    7. Write checklist [DETERMINISTIC]    — _validation.md
    8. Commit          [DETERMINISTIC]
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Add scripts directory to path for _workflow import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _workflow as wf


FEATURE_PHASES = ("draft", "active", "completed", "cancelled")


def find_feature_spec(features_dir, slug):
    """Find the feature spec file for a slug in features/<phase>/ or bugs/<phase>/."""
    for phase in FEATURE_PHASES:
        for suffix in ["-feature.md", "-bug.md"]:
            path = os.path.join(features_dir, phase, f"{slug}{suffix}")
            if os.path.exists(path):
                return path
    # Also check bugs/ directory
    bugs_dir = os.path.join(os.path.dirname(features_dir), "bugs")
    if os.path.isdir(bugs_dir):
        for phase in FEATURE_PHASES:
            path = os.path.join(bugs_dir, phase, f"{slug}-bug.md")
            if os.path.exists(path):
                return path
    return None


def generate_repo_manifests(cp_dir, relay_dir):
    """Generate repo manifests inline by running generate-brief.sh for each repo in the service catalog."""
    script = os.path.join(relay_dir, "process", "scripts", "generate-brief.sh")
    if not os.path.exists(script):
        return {}

    entries = wf.parse_service_catalog(cp_dir)
    if not entries:
        # Fallback: try .relay-config repos (older format)
        for short, _nwo in wf.read_relay_config_repos(cp_dir):
            repos_dir = os.path.join(cp_dir, "repos", short)
            if os.path.isdir(repos_dir):
                entries.append({"name": short, "local_path": ""})

    generated = 0
    for entry in entries:
        local_path = entry.get("local_path", "")
        if not local_path or not os.path.isdir(local_path):
            continue
        result = subprocess.run(
            [script, "--cp-dir", cp_dir, entry["name"], local_path],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            generated += 1

    return generated


def load_repo_manifests(cp_dir):
    """Load all repo manifests from repos/*/repo-manifest.md (or legacy codebase-brief.md)."""
    manifests = {}
    repos_dir = os.path.join(cp_dir, "repos")
    if not os.path.isdir(repos_dir):
        return manifests
    # Prefer repo-manifest.md, fall back to codebase-brief.md
    for repo_dir in sorted(glob.glob(os.path.join(repos_dir, "*"))):
        if not os.path.isdir(repo_dir):
            continue
        repo_name = os.path.basename(repo_dir)
        manifest_path = os.path.join(repo_dir, "repo-manifest.md")
        legacy_path = os.path.join(repo_dir, "codebase-brief.md")
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                manifests[repo_name] = f.read()
        elif os.path.exists(legacy_path):
            with open(legacy_path) as f:
                manifests[repo_name] = f.read()
    return manifests


def build_decomposition_prompt(feature_content, briefs, service_catalog,
                               edge_cases, retro_log, contracts,
                               task_template, output_file,
                               validation_errors=None, past_summaries=None,
                               feature_execution_mode=None):
    """Build the structured prompt for AI decomposition."""
    context_parts = []

    context_parts.append("## Feature Spec\n" + feature_content)

    if service_catalog:
        context_parts.append("## Service Catalog\n" + service_catalog)

    for repo, brief in briefs.items():
        context_parts.append(f"## Repo Manifest: {repo}\n{brief}")

    if edge_cases:
        context_parts.append("## Edge Case Library\n" + edge_cases)

    if retro_log:
        context_parts.append("## Retro Log (relevant failures)\n" + retro_log)

    for name, content in contracts.items():
        context_parts.append(f"## Current Contract: {name}\n{content}")

    if past_summaries:
        for name, content in past_summaries.items():
            context_parts.append(f"## Past Feature Summary: {name}\n{content}")

    context_parts.append("## Task Template Format\n" + task_template)

    context = "\n\n".join(context_parts)

    task_description = """Decompose this feature spec into implementable, repo-scoped queue tasks grouped by wave.

Analyze the feature spec and repo manifests to determine:
1. Which repos need changes
2. What the API contract changes are (if any)
3. How to slice the work into user story tasks (see slicing rules below)
4. How to group tasks into waves for delivery
5. What execution mode each task should use

## Slicing Rules — User Story Vertical Slices

CRITICAL: Slice by USER STORY, not by technical layer.

BAD (technical/horizontal slicing — creates sequential dependencies):
  - Task 1: "Create page foundation and routing"
  - Task 2: "Migrate existing data displays to page"
  - Task 3: "Add pie chart visualization"
  These chain sequentially and cannot be parallelized.

GOOD (user story/vertical slicing — enables parallel execution):
  - Task 1: "User can see task counts by status on analytics page"
  - Task 2: "User can see daily completion trends on analytics page"
  - Task 3: "User can see tasks by category with pie chart"
  Each is independently deployable. Multiple agents work simultaneously.

Each task must:
- Deliver a thin, end-to-end slice of user value
- Be independently deployable and testable
- Touch its own files/components where possible to minimize merge conflicts
- NOT depend on other tasks in the same wave (maximize parallelism for agents)

Wave strategy:
- Wave 1: Shared infrastructure ONLY if absolutely needed (e.g., new API endpoint
  that multiple frontend tasks will call). Keep minimal — often not needed at all.
- Wave 2+: Independent user story slices that can run in parallel.

Dependencies (depends_on) should be RARE — only when a task literally cannot compile
or run without another task's output (e.g., API endpoint must exist before frontend
can call it). Conceptual ordering is NOT a dependency.

## TDD — Behavioral Test-Driven Development

Each task MUST follow TDD with behavioral scenarios:
1. Each GIVEN/WHEN/THEN scenario in the task becomes exactly one test
2. Agent writes failing tests FIRST — test names mirror the scenario language
3. Agent implements the minimum code to make each test pass
4. Agent refactors while keeping tests green

Behavioral scenarios must be:
- Written from the USER's perspective (what they do, what they see)
- Concrete enough to translate directly into a test assertion
- Independent of implementation details (no file names, function names, or framework specifics)
- Derived from the feature spec's User Journey, narrowed to this task's slice

Never create separate test-only tasks.

Sizing constraints:
- Each task must be under 400 estimated lines (including tests)
- Each wave should stay under ~400 lines per repo total
- Individual tasks: small (<50 lines), medium (50-200 lines), large (200-400 lines)
"""
    if feature_execution_mode:
        task_description += f"\nExecution mode: All tasks MUST use '{feature_execution_mode}' (inherited from the feature spec). Do not override per-task.\n"
    else:
        task_description += "\nExecution mode: No feature-level mode set. Use 'supervised' for all tasks.\n"

    if validation_errors:
        task_description += "\n\n## PREVIOUS ATTEMPT FAILED VALIDATION\n"
        task_description += "Fix these errors and try again:\n"
        for err in validation_errors:
            task_description += f"- {err}\n"

    output_schema = f"""When you have finalized the decomposition, write the result as a single JSON file to `{output_file}`.

The JSON must have this exact format (no markdown fences, no surrounding text in the file):

{{
  "contract_diff": {{
    "filename": "contracts/tasks-api.json",
    "content": {{ ... full updated contract JSON ... }}
  }},
  "tasks": [
    {{
      "repo": "api",
      "wave": 1,
      "priority": "high",
      "execution": "supervised",
      "slug": "add-due-date-field",
      "description": "What needs to be built",
      "why": "How this connects to the feature",
      "implementation_notes": "Architectural guidance, specific files to modify",
      "contract_references": "Relevant contract sections",
      "acceptance_criteria": {{
        "behaviors": [
          {{
            "given": "a user viewing the task list",
            "when": "they set a due date on a task",
            "then": "the due date is saved and displayed on the task card"
          }}
        ],
        "invariants": ["Tests pass", "Contract-compliant"]
      }},
      "estimated_lines": 150,
      "depends_on": ["add-field"]
    }}
  ],
  "decisions": [
    "Why 3 waves instead of 2: ...",
    "Why task X is large: ..."
  ]
}}

The "depends_on" field is optional — only include it when a task literally cannot compile
or run without another task's output (e.g., API endpoint must exist). Reference tasks by
their slug (task-id), not filename. Omit it or use an empty array when there are no
dependencies. Tasks in the same wave should almost NEVER depend on each other.

After writing the file, tell the user:

> Decomposition complete. The task breakdown has been written.
> Please exit this session (type /exit or press Ctrl+C) to continue
> with validation and commit."""

    constraints = [
        "Each task targets exactly one repo from the service catalog",
        "No task may exceed 400 estimated lines (including tests)",
        "Waves must be contiguous (1, 2, 3 — no gaps)",
        "Wave 1 = shared infrastructure only if needed (keep minimal). Wave 2+ = independent user story slices",
        "Tasks in the same wave targeting the same repo MUST be parallelizable — no depends_on between them",
        "Every edge case from the feature spec must map to at least one task's acceptance criteria",
        "Cross-repo tasks coordinate only via contracts",
        "All repos must be valid names from the service catalog",
        "Each task follows TDD — behavioral scenarios (GIVEN/WHEN/THEN) become test cases written before implementation. Never create standalone test-only tasks",
        "Every acceptance criterion must be a behavioral scenario (GIVEN/WHEN/THEN) derived from the feature spec's User Journey — no implementation-detail criteria like 'add column to table' or 'create endpoint'",
        "All tasks inherit the feature's execution mode. Never override execution mode per-task",
    ]

    return wf.build_structured_prompt(task_description, context, output_schema, constraints)


def parse_agent_response(response):
    """Extract JSON from agent response, handling various formats."""
    if not response:
        return None

    # Try direct JSON parse first
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Try to extract from markdown code fences
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", response, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find JSON object in the response
    # Look for outermost { ... }
    brace_start = response.find("{")
    if brace_start >= 0:
        depth = 0
        for i in range(brace_start, len(response)):
            if response[i] == "{":
                depth += 1
            elif response[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(response[brace_start : i + 1])
                    except json.JSONDecodeError:
                        break

    # If claude --output-format json, the response may be a JSON wrapper
    try:
        wrapper = json.loads(response)
        if isinstance(wrapper, dict) and "result" in wrapper:
            text = wrapper["result"]
            if isinstance(text, str):
                return parse_agent_response(text)
    except (json.JSONDecodeError, TypeError):
        pass

    return None


def write_task_files(cp_dir, feature_slug, tasks, template_path,
                     feature_execution_mode=None, spec_is_bug=False):
    """Write queue task files from decomposition output into status subdirectories."""
    feature_queue_dir = os.path.join(cp_dir, "queue", feature_slug)

    created = []
    for task in tasks:
        wave = task["wave"]
        repo = task["repo"]
        slug = task["slug"]
        status = "ready" if wave == 1 else "pending"
        priority = task.get("priority", "normal")
        execution = feature_execution_mode or "supervised"

        # Truncate slug to keep filenames under 80 chars total
        max_slug_len = 40
        if len(slug) > max_slug_len:
            slug = slug[:max_slug_len].rstrip("-")
            print(f"  ⚠ Slug truncated to '{slug}' (max {max_slug_len} chars)")

        filename = f"wave-{wave}-{repo}-{slug}.md"
        status_dir = os.path.join(feature_queue_dir, status)
        os.makedirs(status_dir, exist_ok=True)
        filepath = os.path.join(status_dir, filename)

        # Build frontmatter
        contracts_list = []
        if task.get("contract_references"):
            # Try to extract contract filenames
            for ref in re.findall(r"contracts/\S+\.json", str(task["contract_references"])):
                contracts_list.append(ref)

        lines = ["---"]
        lines.append(f"task-id: {slug}")
        lines.append(f"status: {status}")
        lines.append(f"execution: {execution}")
        lines.append(f"target-repo: {repo}")
        lines.append(f"wave: {wave}")
        lines.append(f"priority: {priority}")
        lines.append(f"feature: {feature_slug}")
        lines.append(f"type: {'bug' if spec_is_bug else 'feature'}")
        if contracts_list:
            lines.append("contracts:")
            for c in contracts_list:
                lines.append(f"  - {c}")
        depends_on = task.get("depends_on", [])
        if depends_on:
            lines.append("depends-on:")
            for dep in depends_on:
                lines.append(f"  - {dep}")
        lines.append("---")
        lines.append("")
        lines.append("## Description")
        lines.append("")
        lines.append(task.get("description", ""))
        lines.append("")
        lines.append("## Why")
        lines.append("")
        lines.append(task.get("why", ""))
        lines.append("")
        lines.append("## Implementation Notes")
        lines.append("")
        lines.append(task.get("implementation_notes", ""))
        lines.append("")
        lines.append("## Contract References")
        lines.append("")
        lines.append(task.get("contract_references", "") if isinstance(task.get("contract_references"), str) else "")
        lines.append("")
        lines.append("## Acceptance Criteria")
        lines.append("")
        ac = task.get("acceptance_criteria", {})
        if isinstance(ac, dict):
            behaviors = ac.get("behaviors", [])
            invariants = ac.get("invariants", ["Tests pass", "Contract-compliant"])
            if behaviors:
                lines.append("### Behaviors")
                lines.append("")
                for b in behaviors:
                    given = b.get("given", "")
                    when = b.get("when", "")
                    then = b.get("then", "")
                    lines.append(f"- **GIVEN** {given}")
                    lines.append(f"  **WHEN** {when}")
                    lines.append(f"  **THEN** {then}")
                    for a in b.get("and", []):
                        lines.append(f"  **AND** {a}")
                    lines.append("")
            lines.append("### Invariants")
            lines.append("")
            for inv in invariants:
                lines.append(f"- [ ] {inv}")
        elif isinstance(ac, list):
            # Backward compatibility with old format
            for item in ac:
                lines.append(f"- [ ] {item}")
        lines.append("")

        with open(filepath, "w") as f:
            f.write("\n".join(lines))
        created.append(filepath)

    return created


def write_validation_checklist(cp_dir, feature_slug, tasks, decisions):
    """Write _validation.md for the decomposition."""
    queue_dir = os.path.join(cp_dir, "queue", feature_slug)
    os.makedirs(queue_dir, exist_ok=True)

    filepath = os.path.join(queue_dir, "_validation.md")

    lines = [f"# Decomposition Validation: {feature_slug}", ""]

    # Task summary
    lines.append("## Task Summary")
    lines.append("")
    lines.append("| Wave | Repo | Task | Priority | Est. Lines |")
    lines.append("|------|------|------|----------|------------|")
    for t in sorted(tasks, key=lambda x: (x["wave"], x["repo"])):
        lines.append(
            f"| {t['wave']} | {t['repo']} | {t['slug']} | "
            f"{t.get('priority', 'normal')} | {t.get('estimated_lines', '?')} |"
        )
    lines.append("")

    # Validation checklist
    lines.append("## Validation Checklist")
    lines.append("")
    lines.append("- [ ] Each task can be implemented independently within its repo")
    lines.append("- [ ] Cross-repo tasks coordinate only via contracts")
    lines.append("- [ ] No task estimated >400 lines without split justification")
    lines.append("- [ ] All tasks have appropriate priority set")
    lines.append("- [ ] Each edge case from the Feature Spec maps to at least one task's acceptance criteria")
    lines.append("- [ ] Contract changes are sufficient for all tasks")
    lines.append("- [ ] No circular dependencies")
    lines.append("- [ ] Tasks are grouped into waves, each wave <400 lines per repo")
    lines.append("- [ ] All tasks use the feature's execution mode (no per-task overrides)")
    lines.append("- [ ] Every task is a vertical slice (implementation + tests together, no test-only tasks)")
    lines.append("- [ ] Every Wave 2+ task is named as a user story (user-can-X, user-sees-Y)")
    lines.append("- [ ] Every behavioral scenario (GIVEN/WHEN/THEN) traces to a feature spec User Journey step")
    lines.append("")

    # Decisions
    if decisions:
        lines.append("## Decisions")
        lines.append("")
        for d in decisions:
            lines.append(f"- **{d}**")
        lines.append("")

    with open(filepath, "w") as f:
        f.write("\n".join(lines))

    return filepath


def main():
    parser = argparse.ArgumentParser(description="Decompose a feature into queue tasks.")
    parser.add_argument("feature", help="Feature slug (e.g., add-due-dates)")
    parser.add_argument("--cp-dir", help="Control plane directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without writing files")
    parser.add_argument("--non-interactive", action="store_true", help="Skip interactive prompts (for CI/automation)")
    args = parser.parse_args()

    # Resolve directories
    cp_dir = args.cp_dir or wf.resolve_cp_dir() or os.environ.get("CP_DIR")
    if not cp_dir:
        print("Error: Cannot determine control plane directory.", file=sys.stderr)
        sys.exit(1)

    relay_dir = wf.resolve_relay_dir()
    if not relay_dir:
        print("Error: Cannot determine Relay framework directory.", file=sys.stderr)
        sys.exit(1)

    features_dir = os.path.join(cp_dir, "features")
    queue_dir = os.path.join(cp_dir, "queue")

    # ── Sync repos before starting ──────────────────────────
    pull = subprocess.run(
        ["git", "-C", cp_dir, "pull", "--ff-only"],
        capture_output=True, text=True,
    )
    if pull.returncode != 0:
        wf.print_warn(f"Control plane pull failed: {pull.stderr.strip()}")

    # ── Step 1: Preconditions ────────────────────────────────────
    wf.print_header(f"Planning: {args.feature}")
    print()

    # Verify feature spec exists
    spec_path = find_feature_spec(features_dir, args.feature)
    if not spec_path:
        wf.print_fail(f"No feature spec found for '{args.feature}'")
        print(f"  Expected: features/{args.feature}-feature.md")
        sys.exit(1)
    wf.print_ok(f"Feature spec: {os.path.basename(spec_path)}")

    # Check lifecycle and read execution mode
    fields = wf.parse_frontmatter(spec_path)
    lifecycle = fields.get("lifecycle", "draft")
    if lifecycle not in ("draft", "active"):
        wf.print_fail(f"Feature lifecycle is '{lifecycle}' (must be draft or active)")
        sys.exit(1)
    wf.print_ok(f"Lifecycle: {lifecycle}")

    feature_execution_mode = fields.get("execution", "")
    if feature_execution_mode:
        wf.print_ok(f"Execution mode: {feature_execution_mode}")

    # Generate repo manifests inline (always fresh)
    gen_count = generate_repo_manifests(cp_dir, relay_dir)
    if gen_count:
        wf.print_ok(f"Repo manifests: generated {gen_count}")
    briefs = load_repo_manifests(cp_dir)
    if not briefs:
        wf.print_warn("No repo manifests found — planning will proceed with limited context")
    else:
        wf.print_ok(f"Repo manifests: {', '.join(briefs.keys())}")

    # Check for existing queue files
    existing_tasks = glob.glob(os.path.join(queue_dir, args.feature, "*", "wave-*.md"))
    if existing_tasks:
        wf.print_warn(f"Queue already has {len(existing_tasks)} task(s) for {args.feature}")
        print("  Existing files will be overwritten.")

    # ── Step 2: Load context ─────────────────────────────────────
    print()
    wf.print_info("Loading context...")

    with open(spec_path) as f:
        feature_content = f.read()

    # Service catalog
    catalog_path = os.path.join(cp_dir, ".relay", "service-catalog.md")
    service_catalog = ""
    if os.path.exists(catalog_path):
        with open(catalog_path) as f:
            service_catalog = f.read()

    # Resolve valid repo names
    service_repos = set()
    for entry in wf.parse_service_catalog(cp_dir):
        service_repos.add(entry["name"])
    for short, _nwo in wf.read_relay_config_repos(cp_dir):
        service_repos.add(short)

    # Edge case library
    edge_cases = ""
    ecl_path = os.path.join(relay_dir, "process", "retrospectives", "edge-case-library.md")
    if os.path.exists(ecl_path):
        with open(ecl_path) as f:
            edge_cases = f.read()

    # Retro log
    retro_log = ""
    retro_path = os.path.join(relay_dir, "process", "retrospectives", "retro-log.md")
    if os.path.exists(retro_path):
        with open(retro_path) as f:
            retro_log = f.read()

    # Past feature summaries (from memory compaction)
    past_summaries = {}
    summaries_dir = os.path.join(cp_dir, "features", "_summaries")
    if os.path.isdir(summaries_dir):
        for summary_file in sorted(glob.glob(os.path.join(summaries_dir, "*-summary.md"))):
            with open(summary_file) as f:
                past_summaries[os.path.basename(summary_file)] = f.read()
    if past_summaries:
        wf.print_ok(f"Past summaries: {len(past_summaries)}")

    # Contracts
    contracts = {}
    contracts_dir = os.path.join(cp_dir, "contracts")
    if os.path.isdir(contracts_dir):
        for cp_file in glob.glob(os.path.join(contracts_dir, "*.json")):
            name = os.path.basename(cp_file)
            with open(cp_file) as f:
                contracts[name] = f.read()

    # Task template
    template_path = os.path.join(relay_dir, "process", "templates", "task-queue-item.md")
    task_template = ""
    if os.path.exists(template_path):
        with open(template_path) as f:
            task_template = f.read()

    wf.print_ok("Context assembled")

    # ── Step 3-5: Decompose (interactive) + Validate ─────────────
    output_file = os.path.join(cp_dir, "queue", args.feature, "_decomposition.json")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Clean up any previous output
    if os.path.exists(output_file):
        os.remove(output_file)

    print()
    wf.print_info("Launching AI session for decomposition...")
    print()
    print(f"  {wf.BOLD}{'=' * 60}{wf.NC}")
    print(f"  {wf.BOLD}Entering AI session: Planning{wf.NC}")
    print(f"  {wf.DIM}The AI will decompose the feature into tasks.{wf.NC}")
    print(f"  {wf.DIM}When the AI says decomposition is complete, exit with:{wf.NC}")
    print(f"  {wf.BOLD}  /exit{wf.NC}  {wf.DIM}or{wf.NC}  {wf.BOLD}Ctrl+C{wf.NC}")
    print(f"  {wf.DIM}Validation and commit will run automatically after you exit.{wf.NC}")
    print(f"  {wf.BOLD}{'=' * 60}{wf.NC}")
    print()

    prompt = build_decomposition_prompt(
        feature_content, briefs, service_catalog,
        edge_cases, retro_log, contracts,
        task_template, output_file,
        past_summaries=past_summaries,
        feature_execution_mode=feature_execution_mode,
    )

    if args.dry_run:
        wf.print_warn("Dry run — would invoke agent with prompt:")
        print(f"  Prompt length: {len(prompt)} chars")
        print(f"  Context files: feature spec, {len(briefs)} repo manifests, "
              f"{len(contracts)} contracts")
        sys.exit(0)

    model = wf.resolve_model(cp_dir, role="architect",
                              feature_model=fields.get("model"))
    wf.invoke_agent(prompt, cp_dir, interactive=not args.non_interactive,
                    model=model)

    # Read and parse the output file
    print()
    wf.print_header("Validating Decomposition")

    if not os.path.exists(output_file):
        wf.print_fail(f"Decomposition file not created: {os.path.relpath(output_file, cp_dir)}")
        wf.print_info("The AI session should have written this file.")
        sys.exit(1)

    with open(output_file) as f:
        raw = f.read()

    decomposition = parse_agent_response(raw)
    if not decomposition:
        wf.print_fail("Could not parse decomposition JSON")
        print(f"\n  Raw content (first 500 chars):\n  {raw[:500]}")
        sys.exit(1)

    tasks = decomposition.get("tasks", [])
    if not tasks:
        wf.print_fail("No tasks in decomposition")
        sys.exit(1)

    ok, errors = wf.validate_decomposition(tasks, service_repos)
    if ok:
        wf.print_ok(f"Decomposition validated ({len(tasks)} tasks)")
    else:
        wf.print_fail("Validation failed")
        for err in errors:
            print(f"      {err}")
        wf.print_info(f"Fix the JSON at {os.path.relpath(output_file, cp_dir)} and re-run.")
        sys.exit(1)

    # Clean up the temp file
    os.remove(output_file)

    tasks = decomposition["tasks"]
    decisions = decomposition.get("decisions", [])

    # ── Step 6: Write contracts ──────────────────────────────────
    contract_diff = decomposition.get("contract_diff")
    if contract_diff:
        print()
        contract_filename = contract_diff.get("filename", "contracts/api.json")
        contract_content = contract_diff.get("content")
        if contract_content:
            contract_path = os.path.join(cp_dir, contract_filename)
            os.makedirs(os.path.dirname(contract_path), exist_ok=True)
            with open(contract_path, "w") as f:
                json.dump(contract_content, f, indent=2)
                f.write("\n")
            wf.print_ok(f"Contract written: {contract_filename}")

    # ── Step 7: Write task files ─────────────────────────────────
    print()
    spec_is_bug = spec_path.endswith("-bug.md") or fields.get("type") == "bug"
    created_files = write_task_files(cp_dir, args.feature, tasks, template_path,
                                     feature_execution_mode=feature_execution_mode,
                                     spec_is_bug=spec_is_bug)
    wf.print_ok(f"Created {len(created_files)} task files")
    for fp in created_files:
        rel = os.path.relpath(fp, cp_dir)
        wf.print_info(rel)

    # ── Step 8: Write validation checklist ───────────────────────
    checklist_path = write_validation_checklist(cp_dir, args.feature, tasks, decisions)
    wf.print_ok(f"Validation checklist: {os.path.relpath(checklist_path, cp_dir)}")

    # ── Step 9: Commit ───────────────────────────────────────────
    print()

    # Update feature lifecycle to active if draft — move to active/ directory
    if lifecycle == "draft":
        fields["lifecycle"] = "active"
        wf.write_frontmatter(spec_path, fields)
        active_dir = os.path.join(features_dir, "active")
        os.makedirs(active_dir, exist_ok=True)
        new_spec_path = os.path.join(active_dir, os.path.basename(spec_path))
        result = subprocess.run(
            ["git", "-C", cp_dir, "mv", spec_path, new_spec_path],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            # Fallback for untracked files
            os.rename(spec_path, new_spec_path)
        spec_path = new_spec_path
        wf.print_ok("Feature lifecycle → active (moved to features/active/)")

    # Stage and commit
    subprocess.run(
        ["git", "-C", cp_dir, "add",
         f"queue/{args.feature}/",
         "contracts/",
         "features/"],
        capture_output=True,
    )

    task_count = len(tasks)
    wave_count = len(set(t["wave"] for t in tasks))
    repo_count = len(set(t["repo"] for t in tasks))
    commit_msg = (
        f"feat: decompose {args.feature} — "
        f"{task_count} tasks across {wave_count} wave(s), {repo_count} repo(s)"
    )

    result = subprocess.run(
        ["git", "-C", cp_dir, "commit", "-m", commit_msg],
        capture_output=True, text=True,
    )

    if result.returncode == 0:
        wf.print_ok(f"Committed: {commit_msg}")
    else:
        wf.print_warn("Nothing to commit (files may already be committed)")

    # Wave 1 tasks are already written into ready/ directory — no promotion needed
    wave1_files = [fp for fp in created_files
                   if os.path.basename(fp).startswith("wave-1-")]
    if wave1_files:
        wf.print_ok(f"{len(wave1_files)} wave-1 task(s) created in ready/")

    # ── Auto-sync control plane ─────────────────────────────────
    push_result = subprocess.run(
        ["git", "-C", cp_dir, "push"],
        capture_output=True, text=True,
    )
    if push_result.returncode == 0:
        wf.print_ok("Control plane pushed")
    else:
        wf.print_warn("Control plane push failed (run 'git push' manually)")

    # Summary
    print()
    wf.print_header("Summary")
    print(f"  Tasks: {task_count}")
    print(f"  Waves: {wave_count}")
    print(f"  Repos: {', '.join(sorted(set(t['repo'] for t in tasks)))}")
    print()
    print(f"  Wave 1 tasks are {wf.GREEN}ready{wf.NC} (auto-promoted). Later waves are {wf.DIM}pending{wf.NC}.")

    # Offer next steps
    print()
    if not args.non_interactive:
        choice = input(f"  Next: [{wf.BOLD}v{wf.NC}]alidate / [{wf.BOLD}c{wf.NC}]heck / [{wf.BOLD}q{wf.NC}]uit? ").strip().lower()
    else:
        choice = "q"

    if choice in ("v", "validate"):
        validate_script = os.path.join(relay_dir, "process", "scripts", "validate.py")
        if os.path.exists(validate_script):
            print()
            os.execv(sys.executable, [sys.executable, validate_script, args.feature, "--cp-dir", cp_dir])
        else:
            wf.print_fail("validate.py not found")
            sys.exit(1)
    elif choice in ("c", "check"):
        status_script = os.path.join(relay_dir, "process", "scripts", "status.sh")
        if os.path.exists(status_script):
            print()
            os.execv(status_script, [status_script, "--cp-dir", cp_dir, args.feature])
        else:
            wf.print_fail("status.sh not found")
            sys.exit(1)
    else:
        print()
        print(f"  Run {wf.BOLD}relay check {args.feature}{wf.NC} to see status, or {wf.BOLD}relay validate {args.feature}{wf.NC} to verify.")
        print()


if __name__ == "__main__":
    main()
