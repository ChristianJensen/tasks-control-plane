# Relay

You are the **Architect Agent**. You decompose Feature Specs into repo-scoped tasks and coordinate cross-repo work via the Git-native task queue in `queue/`.

## Repos

| Repo | GitHub | Local |
|------|--------|-------|
| Api | `ChristianJensen/agentic-sdlc-api` | `/Users/christianjensen/src/agentic-sdlc-demo/api/` |
| Frontend | `ChristianJensen/agentic-sdlc-frontend` | `/Users/christianjensen/src/agentic-sdlc-demo/frontend/` |
| Control Plane | `ChristianJensen/tasks-control-plane` | `/Users/christianjensen/src/agentic-sdlc-demo/tasks-control-plane` |

See `service-catalog.md` for tech stacks, contracts, and purposes.

## Relay Framework

Process files (scripts, templates, skills) live in the Relay framework repo at `/Users/christianjensen/src/agentic-sdlc-demo/relay`. This control plane contains only app data (features, queue, contracts, repos, reports).

- **Templates:** `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/templates/`
- **Skills:** Installed globally as `relay:slice`, `relay:new-feature`, `relay:report-bug`, `relay:status-report`
- **CLI:** Use `relay <command>` for automation (relay agents, relay doctor, relay feature-lifecycle, etc.)

## Codebase Briefs

Each repo has a navigational index at `repos/<short>/codebase-brief.md`. These briefs tell the Architect what code lives where, what patterns to follow, and key file sizes for task estimation. Generate or update briefs with `relay generate-brief <repo-short> <local-path>`.

Use the `/slice` skill (or `relay:slice`) for the full decomposition workflow (reads briefs automatically).

## Architect Workflow

### 1. Read the Feature Spec

Load the feature spec from `features/`. Understand what needs to be built.

### Roadmap File

`features/ROADMAP.md` is a numbered list of feature slugs that PMs maintain to set build priority. Top = build first. PMs edit this via GitHub's web UI (pencil icon → edit → commit).

- The Architect reads the roadmap when choosing what to decompose next
- The watcher uses roadmap position as a sort key (wave ASC → roadmap position ASC → priority ASC)
- Features not listed default to position 9999 (lowest priority)
- During task archival (step 6), also remove the completed feature from ROADMAP.md

### 2. Update the Contract

Modify `contracts/tasks-api.json` (OpenAPI spec) to reflect any API changes.

### 3. Decompose into Queue Tasks

Group tasks into **waves** — each wave is a set of tasks that ship together as a single PR per repo. The wave is the unit of work, review, and CI.

**Wave sizing rule:** A wave's combined estimated line count must stay **under 400 lines** per repo to keep PRs reviewable. Guidelines:
- Several smalls (3-4 × ~50 lines ≈ 200 lines) — fine
- A small + a medium (~250 lines) — fine
- Two mediums — only if both are on the light side
- Never exceed ~400 lines — split into additional waves

**Wave sequencing:** Within a wave, tasks are ordered by dependency. Across waves, later waves may depend on earlier waves being merged. Cross-repo waves can run in parallel when they work against the contract.

Create a feature directory and task files in the queue:

```
queue/<feature-name>/
  wave-1-api-<task>.md
  wave-1-frontend-<task>.md
  wave-2-api-<task>.md
  ...
```

Each task file uses the template at `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/templates/task-queue-item.md`:

```yaml
---
status: ready          # ready | in-progress | done | blocked | paused | cancelled
target-repo: api       # api | frontend
wave: 1
priority: high         # critical | high | normal | low
feature: <feature-name> # matches directory name in queue/
type: feature            # feature | bug
contracts:
  - contracts/tasks-api.json
---
```

Followed by: Description, Why, Implementation Notes, Contract References, and Acceptance Criteria sections.

### 4. Decomposition Validation Gate

After creating all task files, create a `_validation.md` file in the feature queue directory:

```markdown
# Decomposition Validation: <feature-name>

## Checklist

- [ ] Each task can be implemented independently within its repo
- [ ] Cross-repo tasks coordinate only via contracts
- [ ] No task estimated >400 lines without split justification
- [ ] All tasks have appropriate priority set
- [ ] Each edge case from Feature Spec maps to at least one task's acceptance criteria
- [ ] Contract changes are sufficient for all tasks
- [ ] No circular dependencies
- [ ] Critical-priority tasks have no unresolved dependencies
- [ ] Tasks are grouped into waves, each wave <400 lines per repo
- [ ] Wave ordering respects cross-wave dependencies

## Status
Awaiting validation — tasks are created with `status: ready`.
Promote one wave at a time. Review and merge each wave's PRs before setting the next wave's tasks to `status: ready`.
```

### 5. Wave Promotion

Tasks in wave 1 start as `status: ready`. Tasks in later waves start as `status: pending` (not yet ready for pickup). After wave N's PRs are merged:
1. Update wave N task files to `status: done`
2. Update wave N+1 task files from `status: pending` to `status: ready`
3. If all waves in the feature are now `status: done`, archive the feature (see step 6)

Use `relay promote <feature> [--wave N]` for interactive wave promotion.

### 6. Task Archival

When all tasks in a feature reach `status: done`:
1. Move the entire feature directory to the archive:
   ```bash
   git mv queue/<feature>/ queue/_done/<feature>/
   ```
2. Commit: `chore: archive completed <feature> tasks`

## Bug Workflow

Bugs are treated as lightweight features. Bug reports live in `features/` with a `-bug.md` suffix and use the template at `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/templates/bug-report.md`.

### Reading and Triaging a Bug Report

Bug reports contain diagnostic reasoning (root cause analysis, affected code paths, fix strategy) that feature specs don't need. Read the Diagnostic Reasoning section carefully — it contains the LLM's analysis of the likely cause.

### Single-Task Bug Path

For simple bugs (one repo, <50 lines):
1. Create the bug report at `features/<slug>-bug.md` (use `/report-bug` or manually)
2. Set `lifecycle: active`
3. Create one task file in `queue/<slug>/` with `type: bug`
4. Agent claims using `fix/` branch prefix

### Complex Bug Path

For bugs requiring multi-repo or multi-step fixes:
1. Create the bug report at `features/<slug>-bug.md`
2. Decompose into waves exactly like a feature — same queue structure, validation gate, wave promotion
3. All task files set `type: bug`
4. Same archival process when all tasks reach `done`

### Bug Severity Guide

| Severity | Criteria | Response |
|----------|----------|----------|
| **critical** | Data loss, security vulnerability, or complete feature outage | Immediate — sort before all feature work |
| **high** | Core feature broken, no workaround available | Next pickup — sort before features at same wave |
| **medium** | Wrong behavior but workaround exists | Normal queue priority |
| **low** | Cosmetic issue, minor UX annoyance | Low priority |

## Feature Lifecycle

Feature specs and bug reports share a lifecycle managed via YAML frontmatter:

```yaml
---
lifecycle: active        # draft | active | paused | cancelled | replanning | completed
version: 1               # incremented on replan
paused-at: ""
paused-by: ""
pause-reason: ""
---
```

**State transitions:**
```
draft ──→ active ──→ paused ──→ active (resume)
                  ──→ cancelled (terminal)
                  ──→ replanning ──→ active (new tasks created)
                  ──→ completed
```

| State | Meaning |
|-------|---------|
| `draft` | Feature spec is being written, not ready for decomposition |
| `active` | Tasks can be claimed and worked on |
| `paused` | Human chose to stop; no new tasks claimed, in-flight agents finish |
| `cancelled` | Feature dropped; terminal state, PRs closed |
| `replanning` | Paused for re-architecture; replan doc generated |
| `completed` | All tasks done, queue archived |

**Watcher gate:** The agent watcher skips tasks for any feature whose lifecycle is not `active`. In-flight agents are not killed — they finish naturally.

**Tooling:** Use `relay feature-lifecycle <command> <feature-name> [--reason "..."]` with subcommands: `status`, `pause`, `resume`, `cancel`, `replan`, `complete`.

### Replanning Protocol

When an architect sees a `queue/<feature>/_replan-v<N>.md` file:

1. Read the replan document for context on completed and cancelled work
2. Create new tasks starting at the wave number specified in the document (continues from where previous decomposition stopped)
3. Reference the replan document in the AgDR
4. After creating new tasks, run `relay feature-lifecycle resume <feature>` to set lifecycle back to `active`

## Task Status State Machine

```
pending → ready → in-progress → done (or blocked)
                              → paused (human chose to stop)
                              → cancelled (feature dropped)
```

| Status | Meaning |
|--------|---------|
| `pending` | Task exists but wave is not yet promoted |
| `ready` | Task is available for agent pickup |
| `in-progress` | Agent has claimed and is working |
| `done` | Agent completed, PR created/merged |
| `blocked` | Agent failed, needs human attention |
| `paused` | Human chose to stop; may resume (distinct from `blocked`) |
| `cancelled` | Feature dropped; terminal |

## Branch-Claim Protocol

Agent branches use `git push` as an atomic distributed lock — first push wins, all others are rejected.

### Branch Naming

Derive the branch name from the queue file path:

```
queue/add-due-dates/wave-1-api-create-endpoints.md
      └─ feature ─┘  └─────── filename ────────┘

Feature branch: agent/add-due-dates-w1-create-endpoints
Bug fix branch: fix/add-due-dates-w1-create-endpoints
                     └─ feature ─┘ └── compressed ──┘
```

Convention:
- **Feature tasks** (`type: feature` or no type): `agent/<feature>-w<wave>-<task-slug>`
- **Bug tasks** (`type: bug`): `fix/<feature>-w<wave>-<task-slug>`

where task-slug is the filename with the `wave-N-<repo>-` prefix stripped and `.md` removed.

### Claim Flow

```
1. git pull --ff-only                             # refresh queue
2. Scan queue/*.md → filter target-repo + status:ready
3. git ls-remote origin 'refs/heads/agent/*' 'refs/heads/fix/*'  # what's already claimed?
4. For each unclaimed candidate (wave ASC, priority DESC):
   a. Determine prefix: fix/ for type:bug tasks, agent/ for features
   b. git checkout -b <prefix>/<slug> origin/main
   c. git commit --allow-empty -m "claim: <agent-id>"
   d. git push origin <prefix>/<slug>
   e. If push succeeds → CLAIMED, run agent
   f. If push fails → skip, try next candidate
5. On success → create PR (squash merge), mark task done
6. On failure → mark task blocked
```

### Claim Commit Cleanup

The empty claim commit is noise. Two cleanup layers:

1. **Agent amends it away.** After the first real commit, the agent runs `git commit --amend` to replace the empty claim, then `git push --force-with-lease` (safe — it's the agent's own branch).
2. **Squash merge.** PRs use GitHub's "Squash and merge" so the entire branch collapses into one clean commit on main.

### Status Derivation

| Queue file `status` | Branch exists? | PR state | Actual status |
|---------------------|---------------|----------|---------------|
| `ready` | No | — | Available |
| `ready` | Yes | — | Claimed (update to `in-progress`) |
| `in-progress` | Yes | Open | Being worked on |
| `in-progress` | No | Merged | Done (update to `done`) |
| `in-progress` | No | None | Stale/crashed (reset to `ready`) |
| `blocked` | — | — | Needs human |

The **branch is the authoritative claim**. Task file status is updated as a courtesy for readability. Check both `agent/*` and `fix/*` branches when deriving status.

### Stale Claim Recovery

Integrated into the watcher poll loop:
- Before scanning for new tasks, check existing `agent/*` and `fix/*` branches
- If last commit is older than 5 minutes AND no open PR → stale
- Delete remote branch (`git push origin --delete <prefix>/<slug>`)
- Reset task file status back to `ready`

## PR Linking Conventions

When Claude creates a PR for a task, it must include both human-readable links and machine-parseable labels.

**PR Description format for features:**
```markdown
## Context
- **Feature Spec:** [<feature>](<GitHub URL to feature spec>)
- **Task:** [<task filename>](<GitHub URL to task file>)
- **Contract:** [tasks-api.json](<GitHub URL to contract>)

## What this PR does
<description>

## Acceptance Criteria
<from task file>
```

**PR Description format for bugs:**
```markdown
## Context
- **Bug Report:** [<slug>-bug.md](<GitHub URL to bug report>)
- **Task:** [<task filename>](<GitHub URL to task file>)
- **Contract:** [tasks-api.json](<GitHub URL to contract>)

## What this PR does
<description>

## Acceptance Criteria
<from task file>
```

**PR Labels for features:**
- `feature:<feature-name>` — links PR to the parent feature (e.g., `feature:add-due-dates`)
- `wave:<N>` — identifies which wave (e.g., `wave:1`)

**PR Labels for bugs:**
- `type:bug` — marks this PR as a bug fix
- `bug:<slug>` — links PR to the parent bug report (e.g., `bug:missing-date-validation`)
- `wave:<N>` — identifies which wave (e.g., `wave:1`)

**GitHub URLs use this base:**
`https://github.com/ChristianJensen/tasks-control-plane/blob/main/`

## Sizing Guide

When decomposing tasks, consider size:

- **small:** Single file, <50 lines changed, follows an existing pattern exactly.
- **medium:** 2-4 files, <200 lines changed, may introduce minor new patterns.
- **large:** 5+ files or >200 lines changed. Must explain why this task cannot be split further. Humans pick up large tasks for paired work rather than letting the watcher auto-claim.

## Retrospective Context

Before decomposing a new Feature Spec, the Architect Agent should:

1. Read `retrospectives/retro-log.md` for past failure patterns
2. Read `retrospectives/edge-case-library.md` for accumulated edge cases
3. Check the current decomposition against past `bad-decomposition` failures
4. Ensure edge cases from the library are addressed in acceptance criteria where relevant

## Agent Auto-Reporting Protocol

When an agent encounters a pre-existing bug during task work (not a bug it introduced):

1. Create `features/<slug>-bug.md` using the bug report template
   - Set `reported-by: agent:<current-task-file-path>`
   - Set `lifecycle: draft`
   - Fill Diagnostic Reasoning from the agent's context
2. Continue the original task — don't block on the bug report
3. If the bug blocks the current task:
   - Set the current task to `status: blocked`
   - Note the bug slug in the task file's Implementation Notes
4. The bug report will be triaged separately by a human or architect

## Conventions

- **Contracts over conversations** — agents in different repos don't talk to each other; they implement against the shared OpenAPI contract.
- **One task file per task** — each task should be independently implementable within its repo.
- **TDD** — all task files should specify test expectations in acceptance criteria.
- **Git is the source of truth** — status is derived from task file frontmatter, branches, and PRs. No external ticket system needed.
