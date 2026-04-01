#!/usr/bin/env python3
"""Relay Spec — orchestrate feature spec creation through a single AI session.

Usage:
    spec.py [--cp-dir <path>]
    spec.py --replan <slug> [--cp-dir <path>]

Pipeline:
    1. Load context        [DETERMINISTIC] — read prerequisite files
    2. Get feature idea    [INPUT] — feature idea + slug
    3. Interview + Refine  [INTERACTIVE AI] — scoping, write spec, refine
    4. Validate output     [DETERMINISTIC] — check all required sections
    5. Present & commit    [DETERMINISTIC] — show artifacts, prompt for commit, route to planning
"""

import argparse
import os
import re
import subprocess
import sys

# Add scripts directory to path for _workflow import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _workflow as wf


SPEC_PROMPT = """\
You are the Planner. You are helping a developer define a new feature.

The user wants to build: {idea}

Complete all four phases below in this single session. Do not ask the user to \
exit or restart between phases.

## Phase 1: Interview

Interview the user about this feature.

**Important: Ask each question ONE AT A TIME.** After asking, offer your \
recommendation with a brief reason (1-2 sentences). Wait for the user's \
response before moving to the next topic. Never present multiple questions \
in a single message.

1. Start by asking: "Who is the target user for this feature, and what \
business problem are we solving for them?" Understanding the persona \
helps you write better specs — especially for UI/UX decisions.
2. Ask the most important scoping question that determines complexity \
and contract shape. Focus on: what data is needed, which repos are \
affected, API surface, UI requirements. If multiple scoping decisions \
are needed, ask them one at a time.
3. Ask the user to walk through the exact step-by-step user journey when \
everything works perfectly. This happy path will be transformed into \
integration tests by downstream agents.
4. Ask about known technical dependencies: "Are there specific external \
APIs, existing database tables, or UI components we MUST use?" This \
helps the Planning Agent wire up the right dependencies later.
5. Ask: "Are there existing design artifacts for this feature — Figma \
wireframes, mockups, or prototypes? If so, share the Figma frame URL(s) \
and I'll record them as sources." If provided, add them to the Sources \
table with type `wireframe` or `mockup`. If none exist, note that design \
will be derived from the spec during decomposition.
6. Based on their answers, ask follow-up questions to nail down scope — \
one at a time.

## Phase 2: Write Spec

When the interview is complete, write the feature spec to \
`features/draft/{slug}-feature.md`
using the template below. Fill in ALL sections from the interview answers.
Set `lifecycle: draft`, `execution: {execution}`, `priority: {priority}`, \
`total-budget: {total_budget}`, and `epic: {epic}`, `epic-title: {epic_title}` in frontmatter.
Pay special attention to the User Journey section — write out the happy \
path as a numbered step-by-step sequence from the user's perspective.

## Phase 3: Refinement

**Without exiting**, run six refinement rounds on the spec you just wrote.

**Important: Ask each question ONE AT A TIME.** For each challenge: state \
the assumption/concern, ask the question, then offer your recommendation \
with reasoning. Wait for the user's response before moving to the next. \
Never present multiple questions in a single message.

### Round 1: Assumptions
Challenge at least 3 hidden assumptions in the spec. Focus on:
- Deletion behavior
- Edge states (empty, maximum, concurrent)
- Interaction with existing features

Present one assumption at a time: state the assumption, ask whether it holds \
or needs adjustment, then offer your recommendation with reasoning. \
Wait for the answer, then move to the next.
Update the Refinement Log > Round 1: Assumptions table with findings.

### Round 2: Edge Cases
Stress-test with at least 3 edge cases that could break the mental model:
- Boundary values
- Race conditions
- Error states

Present one edge case at a time: state the edge case, ask how it should be \
handled, then offer your recommended handling with reasoning. Wait for the \
user's response. \
Update Round 2: Edge Cases table.

### Round 3: Scope Boundaries
Propose 2-3 adjacent features. Present one at a time: describe the adjacent \
feature, ask whether it should be in or out of scope, then offer your \
recommendation with reasoning. Wait for the user's response.
Update Round 3: Scope Boundaries table and Out of Scope section.

### Round 4: Architecture Review
Challenge at least 2 architectural implications. Focus on:
- New services or infrastructure needed
- API changes (especially breaking changes)
- Dependency additions
- Scalability at 10x current volume

Present one implication at a time: state the architectural concern, ask how \
it should be addressed, then offer your recommended approach with reasoning. \
Wait for the user's response. \
Update Round 4: Architecture Review table.

### Round 5: PII / Compliance Review
Identify all data elements created, stored, transmitted, or displayed.
Classify each as PII, sensitive, internal, or public. For PII/sensitive data,
For each element: state the data element and its classification, ask if \
the handling is correct, then recommend specific retention, access controls, \
audit logging, and deletion flows with reasoning. One at a time.
If no PII is involved, record an explicit N/A with rationale.
Update Round 5: PII / Compliance Review table.

### Round 6: UX & Interaction Review
Challenge at least 2 UX/interaction concerns. Focus on:
- UI states: what does the user see during loading, empty, error, and success?
- Responsive behavior: mobile/tablet support or desktop-only?
- Accessibility: keyboard navigation, screen reader labels, color contrast
- Visual consistency: does this reuse existing UI patterns or introduce new ones?

For non-UI features, record an explicit N/A with rationale.
Present one concern at a time: state the UX concern, ask how it should be \
handled, then offer your recommendation with reasoning. Wait for response.
Update Round 6: UX & Interaction Review table.

## Phase 4: Update Spec

Update the spec file in place with all refinement findings. Check all items in \
the Readiness Checklist that are now satisfied. Update the contract at
`contracts/tasks-api.json` if the refinement changed the API surface (bump \
version, add/modify endpoints or schemas).

## When You Are Done

After completing all four phases, tell the user:

> All phases complete. The spec has been written and refined.
> Please exit this session (type /exit or press Ctrl+C) to continue
> with validation and commit.

## Rules

- Do NOT commit or push — the orchestrator handles that.
- Do NOT explore the codebase — work with requirements only.
- Do NOT skip any refinement round.
- Complete all phases in this single session.
- When asking a question, state the topic first, ask the question, then offer \
your recommendation with reasoning (1-2 sentences). This applies to interview \
questions, refinement challenges, and scope boundary proposals.

## Context

### Current API Contract
{contract}

### Service Catalog
{service_catalog}

### Feature Spec Template
{template}
"""

# ── Per-phase prompts (used by web UI for deterministic orchestration) ──

INTERVIEW_PHASE_PROMPT = """\
You are the Planner. You are helping a developer define a new feature.

The user wants to build: {idea}

## Your Task

Interview the user about scoping decisions for this feature. Keep it \
conversational — ask each question ONE AT A TIME.

**You MUST use this exact format for every message:**

1. **Question:** Ask your question first.
2. **My recommendation:** Then give your recommendation with brief reasoning.

NEVER put the recommendation before the question. The question MUST come \
first. Wait for the user's response before moving to the next topic.

1. Start by asking: "Who is the target user for this feature, and what \
business problem are we solving for them?"
2. Ask the most important scoping question that determines complexity \
and contract shape. Focus on: what data is needed, which repos are \
affected, API surface, UI requirements. If multiple scoping decisions \
are needed, ask them one at a time.
3. Ask the user to walk through the exact step-by-step user journey when \
everything works perfectly.
4. Ask about known technical dependencies: "Are there specific external \
APIs, existing database tables, or UI components we MUST use?"
5. Ask: "Are there existing design artifacts for this feature — Figma \
wireframes, mockups, or prototypes?" If provided, add them to the Sources \
table with type `wireframe` or `mockup`.
6. Based on their answers, ask follow-up questions to nail down scope — \
one at a time.

## Rules

- Do NOT write the spec yet — only interview.
- Do NOT commit or push.
- Ask ONE question at a time.
- ALWAYS lead with your recommendation and reasoning before asking.

## Context

### Current API Contract
{contract}

### Service Catalog
{service_catalog}
"""

DRAFT_PHASE_PROMPT = """\
You are the Planner. Write the feature spec based on the interview transcript.

Write the feature spec to `features/draft/{slug}-feature.md` using the \
template below. Fill in ALL sections from the interview answers.
Set `lifecycle: draft`, `execution: {execution}`, `priority: {priority}`, \
`total-budget: {total_budget}`, `epic: {epic}`, `epic-title: {epic_title}` in frontmatter.
Pay special attention to the User Journey section — write out the happy \
path as a numbered step-by-step sequence from the user's perspective.

Leave the Refinement Log section with empty tables — refinement happens next.

## Rules

- Do NOT commit or push — the orchestrator handles that.
- Fill in ALL sections of the template.

## Context

### Current API Contract
{contract}

### Service Catalog
{service_catalog}

### Feature Spec Template
{template}
"""

REFINE_ROUND_PROMPTS = [
    # Round 1: Assumptions
    """\
You are running refinement Round 1 of 6: **Assumptions**.

Read the feature spec at `features/draft/{slug}-feature.md`.

Challenge at least 3 hidden assumptions in the spec. Focus on:
- Deletion behavior
- Edge states (empty, maximum, concurrent)
- Interaction with existing features

Present one assumption at a time: state the assumption, ask whether it holds \
or needs adjustment, then offer your recommendation with reasoning. Wait for \
the answer, then move to the next.

After discussing all assumptions, update the spec's Refinement Log > \
Round 1: Assumptions table with findings.

You MUST use this exact format for each assumption:
1. **Assumption:** State the assumption
2. **Question:** Ask whether it holds or needs adjustment
3. **My recommendation:** Offer your recommendation with reasoning

NEVER put the recommendation before the question.""",

    # Round 2: Edge Cases
    """\
You are running refinement Round 2 of 6: **Edge Cases**.

Read the feature spec at `features/draft/{slug}-feature.md`.

Stress-test with at least 3 edge cases that could break the mental model:
- Boundary values
- Race conditions
- Error states

Present one edge case at a time: state the edge case, ask how it should be \
handled, then offer your recommended handling with reasoning. Wait for the \
user's response.

After discussing all edge cases, update the spec's Round 2: Edge Cases table.

You MUST use this exact format for each edge case:
1. **Edge case:** State the edge case
2. **Question:** Ask how it should be handled
3. **My recommendation:** Offer your recommendation with reasoning

NEVER put the recommendation before the question.""",

    # Round 3: Scope Boundaries
    """\
You are running refinement Round 3 of 6: **Scope Boundaries**.

Read the feature spec at `features/draft/{slug}-feature.md`.

Propose 2-3 adjacent features. Present one at a time: describe the adjacent \
feature, ask whether it should be in or out of scope, then offer your \
recommendation with reasoning. Wait for the user's response.

After discussing all boundaries, update the spec's Round 3: Scope Boundaries \
table and Out of Scope section.

You MUST use this exact format for each boundary:
1. **Adjacent feature:** Describe the adjacent feature
2. **Question:** Ask whether it should be in or out of scope
3. **My recommendation:** Offer your recommendation with reasoning

NEVER put the recommendation before the question.""",

    # Round 4: Architecture Review
    """\
You are running refinement Round 4 of 6: **Architecture Review**.

Read the feature spec at `features/draft/{slug}-feature.md`.

Challenge at least 2 architectural implications. Focus on:
- New services or infrastructure needed
- API changes (especially breaking changes)
- Dependency additions
- Scalability at 10x current volume

Present one implication at a time: state the architectural concern, ask how \
it should be addressed, then offer your recommended approach with reasoning. \
Wait for the user's response.

After discussing all implications, update the spec's Round 4: Architecture \
Review table.

You MUST use this exact format for each implication:
1. **Concern:** State the architectural concern
2. **Question:** Ask how it should be addressed
3. **My recommendation:** Offer your recommendation with reasoning

NEVER put the recommendation before the question.""",

    # Round 5: PII / Compliance Review
    """\
You are running refinement Round 5 of 6: **PII / Compliance Review**.

Read the feature spec at `features/draft/{slug}-feature.md`.

Identify all data elements created, stored, transmitted, or displayed.
Classify each as PII, sensitive, internal, or public. For PII/sensitive data,
For each element: state the data element and its classification, ask if \
the classification and handling are correct, then recommend specific retention, \
access controls, audit logging, and deletion flows with reasoning.

If no PII is involved, record an explicit N/A with rationale.

After discussing all elements, update the spec's Round 5: PII / Compliance \
Review table.

You MUST use this exact format for each element:
1. **Data element:** State the element and its classification
2. **Question:** Ask if the classification and handling are correct
3. **My recommendation:** Offer your recommendation with reasoning

NEVER put the recommendation before the question.""",

    # Round 6: UX & Interaction Review
    """\
You are running refinement Round 6 of 6: **UX & Interaction Review**.

Read the feature spec at `features/draft/{slug}-feature.md`.

Challenge at least 2 UX/interaction concerns. Focus on:
- UI states: what does the user see during loading, empty, error, and success?
- Responsive behavior: mobile/tablet support or desktop-only?
- Accessibility: keyboard navigation, screen reader labels, color contrast
- Visual consistency: does this reuse existing UI patterns or introduce new ones?

For non-UI features, record an explicit N/A with rationale.
Present one concern at a time: state the UX concern, ask how it should be \
handled, then offer your recommendation with reasoning. Wait for response.

After discussing all concerns, update the spec's Round 6: UX & Interaction \
Review table.

You MUST use this exact format for each concern:
1. **UX concern:** State the concern
2. **Question:** Ask how it should be handled
3. **My recommendation:** Offer your recommendation with reasoning

NEVER put the recommendation before the question.""",
]

UPDATE_PHASE_PROMPT = """\
You are the Planner finishing the refinement process.

Read the feature spec at `features/draft/{slug}-feature.md`.

Update the spec file in place:
1. Ensure all refinement findings from Rounds 1-6 are recorded in the \
Refinement Log tables.
2. Check ALL items in the Readiness Checklist that are now satisfied \
(change `- [ ]` to `- [x]`).
3. Update the contract at `contracts/tasks-api.json` if the refinement \
changed the API surface (bump version, add/modify endpoints or schemas).

## Rules

- Do NOT commit or push — the orchestrator handles that.
- Check every readiness checklist item that was addressed during refinement.
"""

REFINE_ROUND_NAMES = [
    "Assumptions",
    "Edge Cases",
    "Scope Boundaries",
    "Architecture Review",
    "PII / Compliance Review",
    "UX & Interaction Review",
]


REPLAN_PROMPT = """\
You are the Planner. You are helping a developer REPLAN an existing feature.

This feature is being replanned (version {version}). The existing spec, \
completed work, and paused work are provided below. Your job is to interview \
the user about what changed, then update the spec accordingly.

Complete all four phases below in this single session. Do not ask the user to \
exit or restart between phases.

## Phase 1: Interview

The feature is being replanned. Interview the user about what changed.

**Important: Ask each question ONE AT A TIME.** After asking, offer your \
recommendation with a brief reason (1-2 sentences). Wait for the user's \
response before moving to the next topic. Never present multiple questions \
in a single message.

1. Summarize the current spec and completed work so the user can confirm \
context.
2. Ask what triggered the replan (scope change, technical blocker, \
requirements shift, etc.)
3. Ask targeted questions about what specifically needs to change in \
the spec — one at a time.
4. Identify which completed work can be kept vs. what needs rework.

## Phase 2: Update Spec

Update the existing spec file at `features/{slug}-feature.md`.
Do NOT create a new file — edit the existing one in place.

- Preserve completed work references and any still-valid requirements
- Update requirements, acceptance criteria, and scope based on the interview
- Do NOT change the `lifecycle` or `version` fields in frontmatter — the \
orchestrator manages those
- Add a "Replan v{version}" entry to the Refinement Log summarizing what \
changed and why

Use the template below as a structural reference for required sections.

## Phase 3: Refinement

**Without exiting**, run six refinement rounds focused on the CHANGES.

**Important: Ask each question ONE AT A TIME.** For each challenge: state \
the assumption/concern, ask the question, then offer your recommendation \
with reasoning. Wait for the user's response before moving to the next. \
Never present multiple questions in a single message.

### Round 1: Assumptions
Challenge at least 3 hidden assumptions in the updated spec. Focus on:
- Deletion behavior
- Edge states (empty, maximum, concurrent)
- Interaction with existing features

Present one assumption at a time: state the assumption, ask whether it holds \
or needs adjustment, then offer your recommendation with reasoning. \
Wait for the answer, then move to the next.
Update the Refinement Log > Round 1: Assumptions table with findings.

### Round 2: Edge Cases
Stress-test with at least 3 edge cases that could break the mental model:
- Boundary values
- Race conditions
- Error states

Present one edge case at a time: state the edge case, ask how it should be \
handled, then offer your recommended handling with reasoning. Wait for the \
user's response. \
Update Round 2: Edge Cases table.

### Round 3: Scope Boundaries
Propose 2-3 adjacent features. Present one at a time: describe the adjacent \
feature, ask whether it should be in or out of scope, then offer your \
recommendation with reasoning. Wait for the user's response.
Update Round 3: Scope Boundaries table and Out of Scope section.

### Round 4: Architecture Review
Challenge at least 2 architectural implications. Focus on:
- New services or infrastructure needed
- API changes (especially breaking changes)
- Dependency additions
- Scalability at 10x current volume

Present one implication at a time: state the architectural concern, ask how \
it should be addressed, then offer your recommended approach with reasoning. \
Wait for the user's response. \
Update Round 4: Architecture Review table.

### Round 5: PII / Compliance Review
Identify all data elements created, stored, transmitted, or displayed.
Classify each as PII, sensitive, internal, or public. For PII/sensitive data,
For each element: state the data element and its classification, ask if \
the handling is correct, then recommend specific retention, access controls, \
audit logging, and deletion flows with reasoning. One at a time.
If no PII is involved, record an explicit N/A with rationale.
Update Round 5: PII / Compliance Review table.

### Round 6: UX & Interaction Review
Challenge at least 2 UX/interaction concerns. Focus on:
- UI states: what does the user see during loading, empty, error, and success?
- Responsive behavior: mobile/tablet support or desktop-only?
- Accessibility: keyboard navigation, screen reader labels, color contrast
- Visual consistency: does this reuse existing UI patterns or introduce new ones?

For non-UI features, record an explicit N/A with rationale.
Present one concern at a time: state the UX concern, ask how it should be \
handled, then offer your recommendation with reasoning. Wait for response.
Update Round 6: UX & Interaction Review table.

## Phase 4: Update Spec

Update the spec file in place with all refinement findings. Check all items in \
the Readiness Checklist that are now satisfied. Update the contract at
`contracts/tasks-api.json` if the refinement changed the API surface (bump \
version, add/modify endpoints or schemas).

## When You Are Done

After completing all four phases, tell the user:

> All phases complete. The spec has been updated with replan findings.
> Please exit this session (type /exit or press Ctrl+C) to continue
> with validation and commit.

## Rules

- Do NOT commit or push — the orchestrator handles that.
- Do NOT explore the codebase — work with requirements only.
- Do NOT skip any refinement round.
- Complete all phases in this single session.
- When asking a question, state the topic first, ask the question, then offer \
your recommendation with reasoning (1-2 sentences). This applies to interview \
questions, refinement challenges, and scope boundary proposals.

## Context

### Existing Feature Spec
{existing_spec}

### Completed & Paused Work Summary
{replan_summary}

### Current API Contract
{contract}

### Service Catalog
{service_catalog}

### Feature Spec Template (for reference)
{template}
"""


# ── Helpers ──────────────────────────────────────────────────────

def slugify(text):
    """Convert text to a kebab-case slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def load_context(cp_dir, relay_dir):
    """Load shared context files (contract, service catalog, template).

    Returns:
        (contract, service_catalog, template) strings
    """
    contract_path = os.path.join(cp_dir, "contracts", "tasks-api.json")
    contract = ""
    if os.path.exists(contract_path):
        with open(contract_path) as f:
            contract = f.read()
        wf.print_ok("Contract: contracts/tasks-api.json")
    else:
        wf.print_warn("No contract found at contracts/tasks-api.json")

    catalog_path = os.path.join(cp_dir, ".relay", "service-catalog.md")
    service_catalog = ""
    if os.path.exists(catalog_path):
        with open(catalog_path) as f:
            service_catalog = f.read()
        wf.print_ok("Service catalog loaded")
    else:
        wf.print_warn("No service-catalog.md found")

    template_path = os.path.join(relay_dir, "process", "templates", "feature-spec.md")
    template = ""
    if os.path.exists(template_path):
        with open(template_path) as f:
            template = f.read()
        wf.print_ok("Feature spec template loaded")
    else:
        wf.print_fail("Feature spec template not found")
        sys.exit(1)

    return contract, service_catalog, template


def validate_spec(spec_path):
    """Validate a feature spec has required sections and refinement content."""
    required_sections = [
        "Problem Statement",
        "Requirements",
        "Acceptance Criteria",
        "Out of Scope",
        "Refinement Log",
    ]

    ok, errors = wf.validate_sections(spec_path, required_sections)
    if ok:
        wf.print_ok("All required sections present")
    else:
        for err in errors:
            wf.print_warn(err)

    ok, errors = wf.validate_readiness_checklist(spec_path)
    if ok:
        wf.print_ok("Readiness checklist complete")
    else:
        for err in errors:
            wf.print_warn(err)

    with open(spec_path) as f:
        content = f.read()

    assumption_count = len(re.findall(r"^\|\s*A\d+", content, re.MULTILINE))
    edge_case_count = len(re.findall(r"^\|\s*E\d+", content, re.MULTILINE))
    scope_count = len(re.findall(r"^\|\s*B\d+", content, re.MULTILINE))
    arch_count = len(re.findall(r"^\|\s*AR\d+", content, re.MULTILINE))
    pii_count = len(re.findall(r"^\|\s*P\d+", content, re.MULTILINE))
    ux_count = len(re.findall(r"^\|\s*UX\d+", content, re.MULTILINE))

    for label, count, minimum in [
        ("Assumptions challenged", assumption_count, 3),
        ("Edge cases addressed", edge_case_count, 3),
        ("Scope boundaries probed", scope_count, 1),
        ("Architecture implications reviewed", arch_count, 2),
        ("PII/compliance elements reviewed", pii_count, 1),
        ("UX/interaction concerns reviewed", ux_count, 2),
    ]:
        if count >= minimum:
            wf.print_ok(f"{label}: {count}")
        else:
            wf.print_warn(f"Only {count} {label.lower()} (recommend >={minimum})")


def commit_and_route(slug, spec_path, cp_dir, relay_dir, commit_msg):
    """Prompt to commit artifacts and optionally route to planning."""
    contract_path = os.path.join(cp_dir, "contracts", "tasks-api.json")

    spec_rel = os.path.relpath(spec_path, cp_dir)
    wf.print_ok(f"Feature spec: {spec_rel}")

    if os.path.exists(contract_path):
        wf.print_ok("Contract: contracts/tasks-api.json")

    print()
    choice = input(f"  Commit artifacts? [{wf.BOLD}y{wf.NC}/N/open] ").strip().lower()

    if choice == "open":
        subprocess.run(["open", spec_path])
        print()
        choice = input(f"  Commit artifacts? [{wf.BOLD}y{wf.NC}/N] ").strip().lower()

    if choice == "y":
        git_add = ["git", "-C", cp_dir, "add", spec_rel]
        subprocess.run(git_add, capture_output=True)

        if os.path.exists(contract_path):
            subprocess.run(
                ["git", "-C", cp_dir, "add", "contracts/"],
                capture_output=True,
            )

        result = subprocess.run(
            ["git", "-C", cp_dir, "commit", "-m", commit_msg],
            capture_output=True, text=True,
        )

        if result.returncode == 0:
            wf.print_ok(f"Committed: {commit_msg}")
            push_result = subprocess.run(
                ["git", "-C", cp_dir, "push"],
                capture_output=True, text=True,
            )
            if push_result.returncode == 0:
                wf.print_ok("Pushed to remote")
            else:
                wf.print_warn("Push failed — remember to push manually")
        else:
            wf.print_warn("Nothing to commit (files may already be committed)")
    else:
        wf.print_info("Skipped commit. Remember to commit before planning.")

    print()
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


def find_latest_replan(queue_dir):
    """Find the latest _replan-v*.md file in a queue directory."""
    if not os.path.isdir(queue_dir):
        return "(no prior work -- feature had no tasks)", None

    import glob as globmod
    replan_files = sorted(globmod.glob(os.path.join(queue_dir, "_replan-v*.md")))
    if not replan_files:
        return "(no replan document found)", None

    latest = replan_files[-1]
    with open(latest) as f:
        content = f.read()

    m = re.search(r"_replan-v(\d+)\.md$", latest)
    version = int(m.group(1)) if m else None
    return content, version


def print_session_banner(phase_name):
    """Print clear instructions before launching an interactive AI session."""
    print()
    print(f"  {wf.BOLD}{'=' * 60}{wf.NC}")
    print(f"  {wf.BOLD}Entering AI session: {phase_name}{wf.NC}")
    print(f"  {wf.DIM}The AI will guide you through the interview and refinement.{wf.NC}")
    print(f"  {wf.DIM}When the AI says all phases are complete, exit with:{wf.NC}")
    print(f"  {wf.BOLD}  /exit{wf.NC}  {wf.DIM}or{wf.NC}  {wf.BOLD}Ctrl+C{wf.NC}")
    print(f"  {wf.DIM}Validation and commit will run automatically after you exit.{wf.NC}")
    print(f"  {wf.BOLD}{'=' * 60}{wf.NC}")
    print()


def print_post_session_banner():
    """Print clear message after the AI session ends."""
    print()
    print(f"  {wf.BOLD}{'=' * 60}{wf.NC}")
    print(f"  {wf.BOLD}AI session ended. Running validation...{wf.NC}")
    print(f"  {wf.BOLD}{'=' * 60}{wf.NC}")


# ── Flows ────────────────────────────────────────────────────────

def run_replan(slug, cp_dir, relay_dir):
    """Run the replan interview flow for an existing feature."""
    features_dir = os.path.join(cp_dir, "features")
    spec_path = None
    for phase in ["active", "draft", "completed", "cancelled"]:
        candidate = os.path.join(features_dir, phase, f"{slug}-feature.md")
        if os.path.exists(candidate):
            spec_path = candidate
            break

    # ── Load context ─────────────────────────────────────────
    wf.print_header("Spec: Feature Replan")
    print()

    if not spec_path or not os.path.exists(spec_path):
        wf.print_fail(f"Feature spec not found for: {slug}")
        sys.exit(1)

    with open(spec_path) as f:
        existing_spec = f.read()
    wf.print_ok(f"Existing spec: features/{slug}-feature.md")

    fm = wf.parse_frontmatter(spec_path)
    version = fm.get("version", "?")

    queue_dir = os.path.join(cp_dir, "queue", slug)
    replan_summary, _ = find_latest_replan(queue_dir)
    wf.print_ok(f"Replan context loaded (v{version})")

    contract, service_catalog, template = load_context(cp_dir, relay_dir)

    # ── Interactive session ──────────────────────────────────
    print_session_banner("Replan Interview + Refinement")

    replan_prompt = REPLAN_PROMPT.format(
        version=version,
        slug=slug,
        existing_spec=existing_spec,
        replan_summary=replan_summary,
        contract=contract or "(no contract exists yet)",
        service_catalog=service_catalog or "(no service catalog found)",
        template=template,
    )

    planner_model = wf.resolve_model(cp_dir, role="planner")
    wf.invoke_agent(replan_prompt, cp_dir, interactive=True, model=planner_model)

    # ── Validate output ──────────────────────────────────────
    print_post_session_banner()
    print()
    wf.print_header("Validating Output")

    if not os.path.exists(spec_path):
        wf.print_fail(f"Feature spec not found: features/{slug}-feature.md")
        wf.print_info("The AI session should have updated this file.")
        sys.exit(1)

    validate_spec(spec_path)

    # Set lifecycle to active programmatically
    fm = wf.parse_frontmatter(spec_path)
    fm["lifecycle"] = "active"
    wf.write_frontmatter(spec_path, fm)

    # ── Present & commit ─────────────────────────────────────
    print()
    wf.print_header("Replan Complete")
    commit_and_route(slug, spec_path, cp_dir, relay_dir,
                     f"feat: replan spec for {slug} v{version}")


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Create a feature spec via phased AI sessions.")
    parser.add_argument("--cp-dir", help="Control plane directory")
    parser.add_argument("--replan", metavar="SLUG",
                        help="Replan an existing feature")
    args = parser.parse_args()

    cp_dir = args.cp_dir or wf.resolve_cp_dir() or os.environ.get("CP_DIR")
    if not cp_dir:
        print("Error: Cannot determine control plane directory.",
              file=sys.stderr)
        print("Run from a control plane directory or pass --cp-dir.",
              file=sys.stderr)
        sys.exit(1)

    relay_dir = wf.resolve_relay_dir()
    if not relay_dir:
        print("Error: Cannot determine Relay framework directory.",
              file=sys.stderr)
        sys.exit(1)

    if args.replan:
        return run_replan(args.replan, cp_dir, relay_dir)

    # ── Sync repos before starting ──────────────────────────
    pull = subprocess.run(
        ["git", "-C", cp_dir, "pull", "--ff-only"],
        capture_output=True, text=True,
    )
    if pull.returncode != 0:
        wf.print_warn(f"Control plane pull failed: {pull.stderr.strip()}")

    # ── New feature flow ─────────────────────────────────────
    wf.print_header("Spec: Feature Definition")
    print()

    contract, service_catalog, template = load_context(cp_dir, relay_dir)

    print()
    idea = input(f"  {wf.BOLD}What do you want to build?{wf.NC} ")
    if not idea.strip():
        wf.print_fail("No feature idea provided.")
        sys.exit(1)

    suggested_slug = slugify(idea)
    slug_input = input(
        f"  {wf.BOLD}Feature slug{wf.NC} [{suggested_slug}]: ").strip()
    slug = slug_input if slug_input else suggested_slug

    # ── Execution mode ────────────────────────────────────
    print()
    print(f"  {wf.BOLD}Execution mode:{wf.NC}")
    print(f"    1) autonomous — Agents auto-claim, work, and auto-merge on green CI")
    print(f"    2) supervised — Agents auto-claim and work, human reviews + merges PR {wf.DIM}(default){wf.NC}")
    print(f"    3) guided    — Human runs 'relay start', agent assists interactively")
    exec_input = input(f"  {wf.BOLD}Choose [1/2/3]:{wf.NC} ").strip()
    execution_modes = {"1": "autonomous", "2": "supervised", "3": "guided"}
    execution = execution_modes.get(exec_input, "supervised")
    wf.print_ok(f"Execution mode: {execution}")

    # ── Priority ──────────────────────────────────────────
    print()
    print(f"  {wf.BOLD}Priority:{wf.NC}")
    print(f"    1) high")
    print(f"    2) medium {wf.DIM}(default){wf.NC}")
    print(f"    3) low")
    pri_input = input(f"  {wf.BOLD}Choose [1/2/3]:{wf.NC} ").strip()
    priority_modes = {"1": "high", "2": "medium", "3": "low"}
    priority = priority_modes.get(pri_input, "medium")
    wf.print_ok(f"Priority: {priority}")

    # ── Epic linkage ──────────────────────────────────────
    epic = input(
        f"  {wf.BOLD}Jira Epic ID{wf.NC} (leave blank for standalone): ").strip()
    epic_title = ""
    if epic:
        wf.print_ok(f"Epic: {epic}")
        epic_title = input(
            f"  {wf.BOLD}Epic title{wf.NC} (optional, for display): ").strip()
        if epic_title:
            wf.print_ok(f"Epic title: {epic_title}")

    # ── Budget ─────────────────────────────────────────────
    print()
    total_budget = input(
        f"  {wf.BOLD}Feature budget in USD{wf.NC} (e.g. 5.00, leave blank for no limit): ").strip()
    if total_budget:
        wf.print_ok(f"Feature budget: ${total_budget} across all tasks")

    features_dir = os.path.join(cp_dir, "features")
    draft_dir = os.path.join(features_dir, "draft")
    os.makedirs(draft_dir, exist_ok=True)
    spec_path = os.path.join(draft_dir, f"{slug}-feature.md")

    # Check phase dirs for existing spec
    existing_spec = None
    for phase in ["draft", "active", "completed", "cancelled"]:
        for suffix in ["-feature.md", "-bug.md"]:
            candidate = os.path.join(features_dir, phase, f"{slug}{suffix}")
            if os.path.exists(candidate):
                existing_spec = candidate
                break
        if existing_spec:
            break

    # Also check bugs/
    if not existing_spec:
        bugs_dir = os.path.join(cp_dir, "bugs")
        if os.path.isdir(bugs_dir):
            for phase in ["draft", "active", "completed", "cancelled"]:
                for suffix in ["-feature.md", "-bug.md"]:
                    candidate = os.path.join(bugs_dir, phase, f"{slug}{suffix}")
                    if os.path.exists(candidate):
                        existing_spec = candidate
                        break
                if existing_spec:
                    break

    if existing_spec:
        rel = os.path.relpath(existing_spec, cp_dir)
        wf.print_warn(f"Feature spec already exists: {rel}")
        overwrite = input("  Overwrite? [y/N] ").strip().lower()
        if overwrite != "y":
            wf.print_info("Aborting.")
            sys.exit(0)
        spec_path = existing_spec  # Overwrite in place

    # ── Deterministic step engine ───────────────────────────
    from _spec_workflow import SPEC_WORKFLOW, build_spec_config
    from _step_engine import StepEngine
    from _agent_session import CliSession, parse_service_catalog

    engine = StepEngine(
        SPEC_WORKFLOW,
        build_spec_config(
            idea=idea, slug=slug, execution=execution,
            priority=priority, total_budget=total_budget, epic=epic,
            epic_title=epic_title, contract=contract,
            service_catalog=service_catalog, template=template,
        ),
    )

    print_session_banner("Feature Specification")

    repo_paths, _ = parse_service_catalog(cp_dir)
    planner_model = wf.resolve_model(cp_dir, role="planner")
    session = CliSession(cp_dir=cp_dir, repo_paths=repo_paths,
                         model=planner_model)
    err = session._init_client()
    if err:
        wf.print_fail("Could not initialize Anthropic API client.")
        wf.print_info("Set ANTHROPIC_API_KEY or configure it in .relay-config.")
        sys.exit(1)
    session._engine = engine
    session.run_workflow()

    # ── Validate output ──────────────────────────────────────
    print_post_session_banner()
    print()
    wf.print_header("Validating Output")

    if not os.path.exists(spec_path):
        wf.print_fail(
            f"Feature spec not created: features/{slug}-feature.md")
        wf.print_info("The AI session should have written this file.")
        wf.print_info("Re-run to try again, or create the file manually.")
        sys.exit(1)

    validate_spec(spec_path)

    # Ensure metadata is set in frontmatter
    fm = wf.parse_frontmatter(spec_path)
    fm["execution"] = execution
    fm["priority"] = priority
    if epic:
        fm["epic"] = epic
    if epic_title:
        fm["epic-title"] = epic_title
    if total_budget:
        fm["total-budget"] = total_budget
    wf.write_frontmatter(spec_path, fm)

    # ── Present & commit ─────────────────────────────────────
    print()
    wf.print_header("Spec Complete")
    commit_and_route(slug, spec_path, cp_dir, relay_dir,
                     f"feat: feature spec for {slug}")


if __name__ == "__main__":
    main()
