# Relay Control Plane

This is a **Relay control plane** — a Git-native coordination hub for multi-repo feature delivery. Workflows define agent roles; this file provides shared context and reference material.

## Repos

| Repo | GitHub | Local |
|------|--------|-------|
| Api | `ChristianJensen/agentic-sdlc-api` | `/Users/christianjensen/src/agentic-sdlc-demo/api/` |
| Frontend | `ChristianJensen/agentic-sdlc-frontend` | `/Users/christianjensen/src/agentic-sdlc-demo/frontend/` |
| Control Plane | `ChristianJensen/tasks-control-plane` | `/Users/christianjensen/src/agentic-sdlc-demo/tasks-control-plane` |

See `.relay/service-catalog.md` for tech stacks, contracts, and purposes.

## Relay Framework

Process files (scripts, templates, workflows) live in the Relay framework repo at `/Users/christianjensen/src/agentic-sdlc-demo/relay`. This control plane contains only app data (features, queue, contracts, repos, reports).

- **Templates:** `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/templates/`
- **Workflows:** `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/workflows/`
- **CLI:** Use `relay <command>` for automation (relay agents, relay doctor, relay feature-lifecycle, etc.)

## Constitution

Rules from Relay (corporate) and this control plane (app-level) are compiled into each code repo's `.relay/constitution.md`. This control plane also has its own `.relay/constitution.md` with merged rules.

- **Propagate rules:** `relay upgrade --repos` recompiles constitutions for all repos
- **Check freshness:** `relay check-rules` from any repo to detect stale rules
- **Add app rules:** Edit `.relay/manifest.md` and add files to `rules/` in this control plane

## Workflows (MANDATORY)

When the user's request matches a workflow below, you MUST read and follow that workflow file. Do NOT use any plugin, skill, or built-in planning process instead — Relay workflows already contain structured steps, interview flows, and artifact production.

| User Intent | Workflow | Action |
|-------------|----------|--------|
| New feature, create spec, capture requirements | **Spec** | Run `relay spec` (script-orchestrated) |
| Decompose feature, slice, break into tasks | **Slice** | Run `relay slice <feature>` (script-orchestrated) |
| Report a bug, file a bug | **Report Bug** | Run `relay report-bug` (script-orchestrated) |
| Push tasks, hand off to agents, relay work | **Relay** | Read `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/workflows/relay.md` and follow every step |
| Status report, progress report | **Status Report** | Read `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/workflows/status-report.md` and follow every step |

## Reference: Queue Format

Task files live in `queue/<feature>/<status>/` (where status is one of: pending, ready, in-progress, done, blocked, paused, cancelled) and use the template at `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/templates/task-queue-item.md`. The directory is authoritative for task state; the `status:` frontmatter field is kept in sync for readability.

```yaml
---
status: ready          # pending | ready | in-progress | done | blocked | paused | cancelled
target-repo: api       # from service catalog
wave: 1
priority: high         # critical | high | normal | low
feature: <feature>     # matches directory name in queue/
type: feature          # feature | bug
contracts:
  - contracts/tasks-api.json
---
```

Followed by: Description, Why, Implementation Notes, Contract References, and Acceptance Criteria sections.

**Wave sizing rule:** A wave's combined estimated line count must stay **under 400 lines** per repo to keep PRs reviewable.

## Reference: Task Status State Machine

```
pending/ → ready/ → in-progress/ → done/ (or blocked/)
                                 → paused/ (human chose to stop)
                                 → cancelled/ (feature dropped)
```

State transitions are performed via `git mv` between status directories.

| Status | Meaning |
|--------|---------|
| `pending` | Task exists but wave is not yet promoted |
| `ready` | Task is available for agent pickup |
| `in-progress` | Agent has claimed and is working |
| `done` | Agent completed, PR created/merged |
| `blocked` | Agent failed, needs human attention |
| `paused` | Human chose to stop; may resume (distinct from `blocked`) |
| `cancelled` | Feature dropped; terminal |

## Reference: Feature Lifecycle

Feature specs and bug reports share a lifecycle managed via phase directories under `features/`. The phase directory (draft, active, completed, cancelled) is authoritative for lifecycle state; YAML frontmatter echoes it for readability.

```yaml
---
lifecycle: active        # draft | active | paused | cancelled | replanning | completed
version: 1               # incremented on replan
paused-at: ""
paused-by: ""
pause-reason: ""
---
```

**State transitions (via `git mv` between phase directories):**
```
features/draft/ ──→ features/active/ ──→ (paused via frontmatter) ──→ features/active/ (resume)
                                      ──→ features/cancelled/ (terminal)
                                      ──→ (replanning via frontmatter) ──→ features/active/ (new tasks created)
                                      ──→ features/completed/
```

| State | Meaning |
|-------|---------|
| `draft` | Feature spec is being written, not ready for decomposition |
| `active` | Tasks can be claimed and worked on |
| `paused` | Human chose to stop; no new tasks claimed, in-flight agents finish |
| `cancelled` | Feature dropped; terminal state, PRs closed |
| `replanning` | Paused for re-architecture; replan doc generated |
| `completed` | All tasks done, queue archived |

**Watcher gate:** The agent watcher skips tasks for any feature whose spec is not in `features/active/`. In-flight agents are not killed — they finish naturally.

**Tooling:** Use `relay feature-lifecycle <command> <feature-name> [--reason "..."]` with subcommands: `status`, `pause`, `resume`, `cancel`, `replan`, `complete`.

### Replanning Protocol

When a `queue/<feature>/_replan-v<N>.md` file exists:

1. Read the replan document for context on completed and cancelled work
2. Create new tasks starting at the wave number specified in the document
3. Reference the replan document in the AgDR
4. After creating new tasks, run `relay feature-lifecycle resume <feature>` to set lifecycle back to `active`

## Reference: Branch-Claim Protocol

Agent branches use `git push` as an atomic distributed lock — first push wins, all others are rejected.

### Branch Naming

Derive the branch name from the queue file path:

```
queue/add-due-dates/ready/wave-1-api-create-endpoints.md
      └─ feature ─┘        └─────── filename ────────┘

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
2. Scan queue/*/ready/wave-*.md → filter target-repo
3. git ls-remote origin 'refs/heads/agent/*' 'refs/heads/fix/*'  # what's already claimed?
4. For each unclaimed candidate (wave ASC, priority DESC):
   a. Determine prefix: fix/ for type:bug tasks, agent/ for features
   b. git checkout -b <prefix>/<slug> origin/main
   c. git commit --allow-empty -m "claim: <agent-id>"
   d. git push origin <prefix>/<slug>
   e. If push succeeds → CLAIMED; git mv ready/task.md in-progress/task.md, run agent
   f. If push fails → skip, try next candidate
5. On success → create PR (squash merge), git mv in-progress/task.md done/task.md
6. On failure → git mv in-progress/task.md blocked/task.md
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
- Move task file back to `ready/` (`git mv in-progress/task.md ready/task.md`)

## Reference: PR Linking Conventions

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

## Reference: Bug Workflow

Bugs are treated as lightweight features. Bug reports live in `features/<phase>/` (same phase directories as feature specs) with a `-bug.md` suffix and use the template at `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/templates/bug-report.md`.

**Single-task bugs** (one repo, <50 lines): create one task file in `queue/<slug>/ready/` with `type: bug`. Agent claims using `fix/` branch prefix.

**Complex bugs** (multi-repo or multi-step): decompose into waves like a feature — same queue structure, validation gate, wave promotion.

| Severity | Criteria | Response |
|----------|----------|----------|
| **critical** | Data loss, security vulnerability, or complete feature outage | Immediate — sort before all feature work |
| **high** | Core feature broken, no workaround available | Next pickup — sort before features at same wave |
| **medium** | Wrong behavior but workaround exists | Normal queue priority |
| **low** | Cosmetic issue, minor UX annoyance | Low priority |

## Reference: Sizing Guide

- **small:** Single file, <50 lines changed, follows an existing pattern exactly.
- **medium:** 2-4 files, <200 lines changed, may introduce minor new patterns.
- **large:** 5+ files or >200 lines changed. Must explain why this task cannot be split further.

## Reference: Task Archival

When all tasks in a feature are in the `done/` directory:
1. Move the entire feature directory to the archive:
   ```bash
   git mv queue/<feature>/ queue/_done/<feature>/
   ```
2. Commit: `chore: archive completed <feature> tasks`

## Conventions

- **Contracts over conversations** — agents in different repos don't talk to each other; they implement against the shared OpenAPI contract.
- **One task file per task** — each task should be independently implementable within its repo.
- **TDD** — all task files should specify test expectations in acceptance criteria.
- **Git is the source of truth** — status is derived from task file frontmatter, branches, and PRs. No external ticket system needed.
