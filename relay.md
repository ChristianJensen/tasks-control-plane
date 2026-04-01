# Relay

**A methodology for software development where AI agents do most of the implementation.**

> "The Scrum Guide for AI-native development."

---

## 1. Preamble

### What

Relay is a methodology for building software when AI coding agents handle most implementation work. It provides structure for the new division of labor between humans (who define intent, review outcomes, and make judgment calls) and agents (who decompose, implement, and validate).

### Who

Relay is for engineering teams that have moved beyond "AI-assisted coding" (Copilot autocomplete) into "AI-agentic development" (agents that autonomously implement features across codebases). It assumes:

- Agents can read/write code, run tests, and interact with tools
- Multiple agents may work in parallel across repositories
- Humans remain accountable for shipped software

### Why

Traditional development methodologies (Scrum, Kanban, Shape Up) assume humans do all implementation. Their ceremonies, artifacts, and feedback loops are designed for human cognitive limits: standups to synchronize understanding, sprints to bound complexity, tickets to track who's doing what.

When agents implement, these assumptions break:

- **Tickets become bottlenecks.** Agents can start work in seconds, not after a grooming session.
- **Standups are pointless.** Agent state is observable from git and task trees.
- **Estimation is meaningless.** Agent velocity is not bounded by human fatigue or context-switching.
- **Code review changes shape.** Reviewing 50 agent PRs/day requires different patterns than reviewing 5 human PRs.

Relay replaces ceremony-heavy coordination with **signal-driven collaboration**: contracts, constitutions, and observable state.

---

## 2. Principles

### Conversations over Tickets

A feature starts as a conversation — spoken, sketched, written. Tickets are a lossy compression of that conversation. In Relay, the full conversation (audio, wireframes, notes) feeds directly into an AI planner that synthesizes a structured Feature Spec with source attribution. No information is lost to ticket templates.

### Contracts over Task Trees

Queue files coordinate *what* needs doing. But the real coordination mechanism is **contracts** — shared API specifications, schema definitions, and interface boundaries. Agents in different repos don't talk to each other; they talk to the contract. If two agents both implement against the same OpenAPI spec, their code will integrate. Queue files track progress; contracts ensure compatibility.

### Constitution over Supervision

Each repo has a `CLAUDE.md` that defines how agents should behave: coding conventions, test requirements, architectural constraints. This is the agent's "constitution" — it governs behavior without requiring a human to watch over every action. Good constitutions make supervision unnecessary for routine work.

### Signals over Status Updates

Project state should be *derived*, not *reported*. Git commits, test results, issue label changes, and CI pipeline signals compose into a real-time view of progress. No one files a status update. Status is a query against observable signals.

### Directories over Fields

Coordination state — the thing that gates the next action and that actors compete on — lives in the directory path, not in a YAML field. Tasks live in `queue/<feature>/<status>/wave-*.md`; features live in `features/<phase>/<name>-feature.md`. Moving a file between directories (`git mv ready/task.md in-progress/task.md`) is the atomic state transition. Frontmatter fields like `status:` and `lifecycle:` are kept in sync for human readability, but when directory and frontmatter diverge, the directory is authoritative. Non-task files (`_replan-*.md`, `_validation.md`) stay at the feature root since they are not subject to the status state machine.

### Judgment over Data

AI can generate more data, metrics, and analysis than any human can consume. The scarce resource is human *judgment* — deciding what matters, what's good enough, what to ship. Relay concentrates human attention on the decisions that require taste, ethics, and accountability, while delegating data-gathering and implementation to agents.

---

## 3. Roles

### Human Roles

| Role | Responsibility | When Active |
|------|---------------|-------------|
| **Product Mind** | Defines intent, sets priorities, makes trade-offs | Feature Definition, Human Validation |
| **Engineering Lead** | Reviews architecture, approves contracts, makes technical judgment calls | Architect Decomposition, Human Validation |
| **Reviewer** | Reviews agent output for correctness, security, and quality | Human Validation |
| **Platform Engineer** | Maintains CI/CD, agent infrastructure, and tooling | CI/CD Validation, ongoing |

### Agent Roles

| Role | Responsibility | Governed By |
|------|---------------|-------------|
| **Planner Agent** | Synthesizes multi-modal inputs into structured Feature Specs | Synthesis protocol |
| **Architect Agent** | Decomposes Feature Specs into repo-scoped Task Specs, updates contracts, creates queue task files in the control plane | Cross-repo access |
| **Implementer Agent** | Implements tasks within a single repo, writes tests, creates PRs | CLAUDE.md (constitution) |

### Emerging: Feature Engineer

As multi-modal feature capture matures, a new role emerges: the **Feature Engineer** — someone skilled at expressing requirements through the optimal combination of sketches, voice, examples, and constraints to maximize the quality of the synthesized spec. This role blends product thinking with AI prompt craft.

---

## 4. The 5 Stages

### Stage 1: Feature Definition

**Purpose:** Capture what should be built, from the humans who know.

**Inputs (multi-modal):**
- Voice memos and conversations (audio → transcript)
- Wireframe sketches (images, Excalidraw → visual analysis)
- Written notes and documents (markdown, PDF, DOCX)
- Screenshots of existing systems
- Conversations with stakeholders

**Process:**
1. Gather all inputs into a shared location (`features/draft/`)
2. AI Planner loads all inputs into a single context
3. Cross-reference: what the wireframe shows vs. what the audio says vs. what the notes specify
4. Detect conflicts between sources (e.g., wireframe shows a dropdown, notes say radio buttons)
5. Ask clarifying questions where confidence is low
6. Synthesize into a structured **Feature Spec** with:
   - Source attribution per requirement
   - Confidence rating (High/Medium/Low) per requirement
   - Detected conflicts and their resolutions
   - Open questions
   - Acceptance criteria

**Output:** Feature Spec (markdown) saved to `features/draft/`

**Context layers active:** 3 (domain knowledge) + 4 (organizational context)

**Refinement Protocol:** Before marking a Feature Spec as ready, run the 5-round refinement protocol (see `templates/refinement-protocol.md`):
1. **Round 1: Assumptions** — identify and challenge at least 3 hidden assumptions
2. **Round 2: Edge Cases** — stress-test with edge cases from the edge case library
3. **Round 3: Scope Boundaries** — probe adjacent features and confirm in/out of scope
4. **Round 4: Architecture Review** — challenge architectural implications, dependencies, and performance impacts
5. **Round 5: PII / Compliance Review** — identify PII, data retention, and regulatory requirements

**"Done enough" threshold:** A Feature Spec is ready for decomposition when the **Readiness Checklist** passes:
- All High-confidence requirements have acceptance criteria
- No unresolved conflicts remain
- Open questions are non-blocking or have owners assigned
- At least 3 assumptions explicitly challenged and resolved
- At least 3 edge cases explicitly addressed
- Out of Scope section reviewed via scope boundary probe
- At least 2 architectural implications reviewed
- PII and sensitive data elements identified with handling requirements (or explicit N/A)

### Stage 2: Architect Decomposition

**Purpose:** Break the Feature Spec into implementable, repo-scoped work.

**Inputs:**
- Feature Spec from Stage 1
- Existing contracts (`contracts/`)
- Current codebase state (both repos)

**Process:**
1. Read `retrospectives/retro-log.md` and `retrospectives/edge-case-library.md` for past failure patterns
2. Analyze the Feature Spec for cross-repo implications
3. Update shared contracts (OpenAPI specs, schema definitions)
4. Decompose into repo-scoped **Task Specs** with size and priority labels
5. **Group tasks into waves** — each wave ships as a single PR per repo (see Wave System below)
6. Create queue task files in `queue/<feature>/pending/` and `queue/<feature>/ready/`
7. Ensure feature spec in `features/` links to the queue directory
8. Write an **Agent Decision Record (AgDR)** explaining decomposition choices, including split justification for any `size:large` tasks
9. Write the **Decomposition Validation Checklist** to `queue/<feature>/_validation.md`
10. After validation, promote tasks **one wave at a time** by moving files from `pending/` → `ready/` using `scripts/promote-tasks.sh`

**Output:**
- Updated contracts
- Task Specs per repo (with size, priority, dependencies, and risk notes)
- Queue task files created in `queue/<feature>/pending/` (promoted to `ready/` after validation)
- AgDR documenting the decomposition rationale
- Decomposition Validation Checklist in `queue/<feature>/_validation.md`
- Feature spec moved to `features/active/` (lifecycle set to `active`)

**Context layers active:** 2 (codebase architecture) + 4 (organizational context)

**Key principle:** The Architect Agent must ensure that tasks in different repos can be implemented *independently*. If Task A in `api/` must complete before Task B in `frontend/` can start, the decomposition is wrong. Contracts should provide enough information for parallel work.

#### Wave System

A **wave** is a group of tasks that ship together as a single PR per repo. Waves solve two problems: they keep PRs reviewable (under ~400 lines) and they sequence dependent work into logical chunks.

**Wave sizing rule:** A wave's combined estimated line count must stay under ~400 lines per repo. This keeps PRs reviewable by humans in one sitting.

| Combination | Estimated Lines | OK? |
|-------------|----------------|-----|
| 3-4 smalls | ~150-200 | Yes |
| 1 small + 1 medium | ~250 | Yes |
| 2 light mediums | ~300 | Yes |
| 2 full mediums | ~400 | Borderline |
| 1 medium + 2 smalls | ~300 | Yes |

**Wave sequencing:**
- Within a wave: tasks are ordered by dependency and implemented sequentially on one branch
- Across waves: later waves depend on earlier waves being merged (promote one wave at a time)
- **Branching rule:** The agent must not create a wave N+1 branch until wave N's PR is merged into `main` and `main` is pulled. This prevents merge conflicts from overlapping file changes within the same repo.
- Cross-repo waves: can run in parallel when both repos work against the contract

**Wave promotion (crawl):** Promote one wave at a time. Review and merge the PR. Then promote the next wave. This is "measure twice, cut once" applied to delivery.

**Wave promotion (walk):** Same as crawl, but the watcher handles batching automatically — it picks up all tasks in a wave together and implements them sequentially on one branch.

**Wave promotion (run):** Waves auto-promote when the previous wave's PRs are merged and CI is green.

### Stage 3: Agent Execution

**Purpose:** Implement the decomposed tasks.

**Inputs:**
- Task Specs
- Queue task files (discovered by scanning `queue/*/ready/wave-*.md`)
- CLAUDE.md constitution
- Shared contracts

**Process:**
1. Watcher scans `queue/*/ready/wave-*.md` for claimable tasks
2. Watcher groups tasks by wave, sorts waves by priority (critical > high > normal > low)
3. Watcher skips `size:large` tasks (reserved for human paired work in crawl mode)
4. Watcher claims the highest-priority wave: moves all wave tasks from `ready/` → `in-progress/` via `git mv`
5. Agent creates one feature branch for the wave **from the latest `main`**. For wave 2+, the previous wave's PR must be merged first — the agent pulls `main` to pick up those changes before branching.
6. Agent implements tasks **sequentially in wave order** using TDD
7. Agent commits after each task (for traceability), runs tests after each
8. Agent creates a **single PR** referencing the queue task files in the control plane
9. On success: all wave tasks moved to `done/`; on failure: moved to `blocked/` + retro stub
10. Repeat until no `ready` tasks remain

**Output:** Code changes, tests, commits — one PR per wave per repo

**Context layers active:** 1 (repo-level constitution via CLAUDE.md)

**Key principles:**
- **One agent per repo.** Agents don't cross repo boundaries.
- **Contract-driven.** Agents implement against shared contracts, not against each other's code.
- **Self-organizing.** Agents discover sub-tasks and create new queue task files for them.
- **Observable.** All state changes are visible via queue file status and `git log`.

### Stage 4: CI/CD Validation

**Purpose:** Automated verification that implementation meets contracts and quality standards.

**Checks:**
- Unit tests pass in all repos
- Contract compliance (API responses match OpenAPI spec)
- Integration tests (start both apps, verify end-to-end flow)
- Security scans, linting, type checks (if configured)

**Process:**
1. CI pipeline runs on push/PR
2. Contract compliance check validates API responses against OpenAPI spec
3. On all-green: mark repo-level yaks done in the control plane
4. On failure: agent investigates, fixes, and re-runs

**Context layers active:** 5 (pipeline signals)

**Key principle:** The pipeline is the umpire. It doesn't negotiate. Green means the contract is satisfied. Red means it isn't. Human judgment is not needed at this stage (though humans may investigate persistent failures).

### Stage 5: Human Validation

**Purpose:** Verify that what was built matches what was intended.

**Process:**
1. Human reviews running application against the Feature Spec
2. Each acceptance criterion is verified: pass/fail
3. Judgment calls on quality, UX, edge cases
4. Decision: ship, iterate, or reject
5. On ship: merge PRs, move feature spec to `features/completed/` via `feature-lifecycle.sh complete`

**Mid-flight controls:** At any point during Stages 2-5, humans can intervene:
- **Pause** (`feature-lifecycle.sh pause <feature>`) — stops new task claims, in-flight agents finish naturally
- **Cancel** (`feature-lifecycle.sh cancel <feature>`) — abandons the feature, closes PRs, cancels tasks
- **Replan** (`feature-lifecycle.sh replan <feature>`) — pauses + generates a replan document for the architect to re-decompose
- **Resume** (`feature-lifecycle.sh resume <feature>`) — restores paused tasks to ready

These controls provide graceful mid-flight correction without killing running agents. The `paused` task status is semantically distinct from `blocked` (human choice vs agent failure).

**Context layers active:** 4 (organizational context) + 5 (outcome signals)

**Key principle:** Humans validate *outcomes*, not *process*. The question is "does this solve the problem?" not "did the agent follow the right steps?" Trust the constitution and the pipeline for process; reserve human attention for judgment.

---

## 5. The 5-Layer Context Stack

AI agents need context to make good decisions. Relay organizes context into 5 layers, each active at different stages:

| Layer | Name | Contains | Source |
|-------|------|----------|--------|
| **1** | Constitution | Coding conventions, test requirements, architectural constraints | `CLAUDE.md` per repo |
| **2** | Codebase | Architecture, dependencies, existing patterns | Source code + git history |
| **3** | Domain | Business rules, user needs, domain terminology | Feature Specs, conversations |
| **4** | Organization | Service ownership, team norms, risk tolerance, velocity data | Observability platforms, team docs |
| **5** | Signal | Pipeline health, test trends, deployment status, DORA metrics | CI/CD, monitoring |

### Layer × Stage Matrix

| | Feature Definition | Architect | Execution | CI/CD | Human |
|---|---|---|---|---|---|
| L1: Constitution | | | ★ | | |
| L2: Codebase | | ★ | ★ | | |
| L3: Domain | ★ | | | | |
| L4: Organization | ★ | ★ | | | ★ |
| L5: Signal | | | | ★ | ★ |

★ = primary context layer for that stage

---

## 6. Cross-Repo Coordination

### The Problem

In a microservices world, a single feature often spans multiple repos. Traditional approaches use tickets with cross-references, meetings to align teams, and shared Slack channels. These don't scale when agents are implementing.

### The Solution: Three Coordination Mechanisms

**1. Queue Files — Task State**
The control plane holds all queue task files organized by feature. Agents discover work by scanning queue files; humans observe progress globally.

```
queue/add-due-dates/
  ├── ready/
  │   ├── wave-1-api-add-due-date-field.md
  │   ├── wave-1-api-add-date-validation.md
  │   └── wave-1-frontend-date-picker.md
  ├── pending/
  │   └── wave-2-frontend-overdue-indicator.md
  └── _validation.md

Directory = coordination state. Frontmatter echoes it for readability.
Agent claiming: git mv ready/task.md in-progress/task.md

Status directories:
  pending/ → ready/ → in-progress/ → done/ (or blocked/)
```

**2. Contracts — Technical Coordination**
The shared OpenAPI spec in `contracts/` is the source of truth for API shape. The Architect Agent updates it during decomposition. Both repo agents implement against it. No agent-to-agent communication needed.

**3. Git Signals — Progress**
Commits, branches, PRs, and CI status provide real-time progress signals. No status reports needed — query the repos.

---

## 7. Multi-Modal Feature Capture

### Why Multi-Modal?

People think in different modalities. A PM might sketch a wireframe on a whiteboard. An engineer might describe the technical constraint in a voice memo. A designer might provide a screenshot of the current UI with annotations. The best Feature Specs come from combining all of these.

### Processing Pipeline

| Input Type | How It's Processed | External Tool Required? |
|---|---|---|
| Wireframe/screenshot (PNG/JPG) | AI reads image directly | No |
| Excalidraw sketch (.excalidraw) | AI reads JSON directly | No |
| PDF document | AI reads PDF directly (up to 100 pages) | No |
| Markdown notes | AI reads .md directly | No |
| DOCX/PPTX | `pandoc` converts to markdown | Yes (pandoc) |
| Audio recording (.mp3/.wav) | Deepgram/Whisper API transcribes to JSON | Yes (API call) |

### Synthesis Protocol

1. **Load** all processed inputs into a single AI context
2. **Catalog** each source with type, contributor, and date
3. **Extract** requirements from each source independently
4. **Cross-reference** requirements across sources:
   - Same requirement from multiple sources → High confidence
   - Requirement from single source, no conflicts → Medium confidence
   - Conflicting requirements between sources → Flag for resolution
5. **Detect conflicts** explicitly (e.g., "Source 1 says dropdown, Source 3 says radio buttons")
6. **Ask** clarifying questions where confidence is Low or conflicts exist
7. **Synthesize** into Feature Spec with full source attribution

---

## 7b. Feedback Loop

### The Virtuous Cycle

Agent failures are not just problems to fix — they are signals that improve the entire process:

```
Feedback → Refinement → Sizing → Validation → fewer failures → better Feedback
```

### How It Works

1. **Signal:** When an agent is blocked (`status: blocked`), CI fails, or human validation rejects work, the watcher auto-creates a retro stub in `retrospectives/retro-log.md`
2. **Root cause analysis:** A human triages the stub, categorizing the root cause as one of: `ambiguous-requirement`, `bad-decomposition`, `missing-edge-case`, `contract-gap`, or `tooling-issue`
3. **Edge case capture:** If the failure revealed an edge case, it's added to `retrospectives/edge-case-library.md`
4. **Upstream fix:** The root cause drives a process improvement — a better refinement question, a tighter validation check, or a new edge case pattern
5. **Next cycle:** Before the next Feature Definition, the Planner Agent reads the retro log and edge case library. Before the next decomposition, the Architect Agent checks past `bad-decomposition` failures.

### Crawl Behavior

- Retro stubs are auto-created by the watcher with `[TODO]` fields
- Humans manually fill in root cause analysis and update the edge case library
- Review the retro log before each new Feature Definition

---

## 8. Artifacts

| Artifact | Created By | Used By | Location |
|----------|-----------|---------|----------|
| **Feature Spec** | Planner Agent (from human inputs) | Architect Agent | `features/<phase>/` (draft, active, completed, cancelled) |
| **Task Spec** | Architect Agent | Implementer Agent | Per-repo or control plane |
| **API Contract** | Architect Agent | Both Implementer Agents | `contracts/` |
| **Queue Task Files** | Architect Agent (created), Watcher (claimed) | All agents + humans | `queue/<feature>/<status>/wave-*.md` |
| **Agent Decision Record (AgDR)** | Architect Agent | Humans (review) | control plane |
| **Refinement Protocol** | Planner Agent / Human | Feature Definition | `templates/refinement-protocol.md` |
| **Retro Log** | Agent Watcher (stubs) + Humans (analysis) | Architect Agent, Planner Agent | `retrospectives/retro-log.md` |
| **Edge Case Library** | Humans (from retros) | Planner Agent (Round 2) | `retrospectives/edge-case-library.md` |
| **Constitution (CLAUDE.md)** | Humans | Implementer Agent | Per-repo root |

### Agent Decision Record (AgDR)

An AgDR is the agent equivalent of an ADR (Architecture Decision Record). It documents:

- **Context:** What the agent was asked to do
- **Decision:** What the agent decided and why
- **Alternatives considered:** What other approaches were evaluated
- **Consequences:** What trade-offs the decision implies
- **Task tree:** The resulting decomposition (feature spec → queue task files)

AgDRs provide transparency into agent reasoning. They're written by the Architect Agent during Stage 2 and reviewed by humans.

---

## 9. Deriving State from Git + Queue Files

### No Jira Required

Project state is derived from two sources:

**Queue files** provide task-level state (directory is authoritative):
```bash
# Pending work
ls queue/*/ready/wave-*.md

# In progress
ls queue/*/in-progress/wave-*.md

# Completed
ls queue/*/done/wave-*.md

# Needs attention
ls queue/*/blocked/wave-*.md

# Full feature status
feature-lifecycle.sh status <feature-name>
```

**Git** provides implementation-level signals:
```bash
git log --oneline      # What was done and when
git diff               # What's in progress
gh pr list             # Active PRs
```

### Composing a Project View

To see the state of a feature:

1. Run `feature-lifecycle.sh status <feature>` for task breakdown and PR summary
2. Scan `queue/<feature>/*/` status directories for task-level detail and frontmatter
3. Check PRs and git history for implementation evidence
4. Check CI for quality signals
5. Run `/status-report` for a full HTML dashboard across all features

This replaces: Jira board + standup + status email + Slack thread.

---

## 10. Adoption Guide

### Level 1: Single-Repo Agent

- One repo, one agent, one CLAUDE.md
- Agent picks up work from queue task files
- Human creates task files manually with `status: ready`
- Human reviews all PRs

**Good for:** Teams trying agentic development for the first time.

### Level 2: Multi-Repo with Contracts

- Multiple repos, one agent per repo
- Shared contracts in a control plane repo
- Architect Agent decomposes Feature Specs
- CI validates contract compliance
- Human reviews outcomes, not code

**Good for:** Teams with microservices wanting to parallelize agent work.

### Level 3: Full Relay

- Multi-modal feature capture
- All 5 stages operational
- Observability platform (like Cortex) provides Layer 4-5 context
- Humans focus on intent, judgment, and accountability
- Agents handle decomposition, implementation, and validation

**Good for:** Teams where AI agents are the primary implementers and human attention is the bottleneck.

---

## 11. Appendix

### Comparison to Existing Methodologies

| Aspect | Scrum | Shape Up | Relay |
|--------|-------|----------|--------------|
| **Planning unit** | User story | Pitch | Feature Spec |
| **Time box** | Sprint (2 weeks) | Cycle (6 weeks) | None (signal-driven) |
| **Decomposition** | Team in planning | Shaping table | Architect Agent |
| **Implementation** | Developer | Developer | Implementer Agent |
| **Coordination** | Standup, Jira | Hill chart, pitch | Queue files, contracts, git signals |
| **Progress tracking** | Burndown chart | Hill chart | Queue file status + git signals |
| **Quality gate** | PR review | QA | CI pipeline + human validation |
| **Status reporting** | Standup, sprint review | Hill chart update | Derived from signals |

### Glossary

- **AgDR:** Agent Decision Record — documents agent reasoning during decomposition
- **Constitution:** `CLAUDE.md` — the per-repo constitution document for agents
- **Contract:** Shared API specification (OpenAPI) that coordinates cross-repo work
- **Decomposition Validation Gate:** Checklist-based review step between `pending` and `ready` that verifies task independence, sizing, and coverage
- **Edge Case Library:** Accumulated edge cases from past failures, used during refinement
- **Feature Spec:** Structured synthesis of multi-modal inputs describing what to build
- **Queue Task File:** A markdown file in `queue/<feature>/<status>/wave-*.md` with YAML frontmatter tracking wave, priority, and target repo — the primary unit of work tracking in Relay. The containing status directory (pending, ready, in-progress, done, blocked, paused, cancelled) is authoritative for task state; the `status:` frontmatter field is kept in sync for human readability.
- **Refinement Protocol:** 5-round structured challenge process (assumptions, edge cases, scope boundaries, architecture review, PII/compliance review) applied during Feature Definition
- **Retro Log:** Append-only log of agent failures with root cause analysis, driving process improvements
- **Task Spec:** Repo-scoped implementation specification derived from a Feature Spec
- **Wave:** A group of tasks that ship together as a single PR per repo. Keeps PRs reviewable (<400 lines) and sequences dependent work into logical delivery chunks.

---

## 12. Optional: GitHub Issues Integration

Teams that want GitHub Issues for visibility (e.g., cross-team stakeholders, external contributors) can optionally mirror queue file status to Issues. **Queue files remain the source of truth; Issues are read-only mirrors.**

### Label Mapping

| Queue File Status | GitHub Issue Label |
|-------------------|--------------------|
| `pending`         | `agent:review`     |
| `ready`           | `agent:ready`      |
| `in-progress`     | `agent:wip`        |
| `done`            | `agent:done`       |
| `blocked`         | `agent:blocked`    |

### How to Mirror

1. Create GitHub Issues per task (one issue per queue file), with the corresponding label
2. When queue file status changes (via scripts or manually), update the Issue label to match
3. Optionally add `Closes #N` to PR bodies to auto-close Issues on merge

### Important Caveats

- Scripts and agents operate on **queue files only** — they do not read or write GitHub Issues
- If queue file and Issue status diverge, the queue file is authoritative
- Issue mirroring is a convenience for human observability, not a coordination mechanism
