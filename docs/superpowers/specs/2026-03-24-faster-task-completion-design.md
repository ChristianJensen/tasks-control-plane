# Faster Task Completion: Merged-PR-Driven Status Updates

## Problem

Tasks are marked `done` when the agent exits, not when the PR is merged. For supervised workflows (agent creates PR, human reviews and merges), this is wrong — the task should stay `in-progress` until the PR is actually merged.

When the agent exits without cleanly calling `handle_success()` (crash, timeout), the watcher relies on stale branch reaping with a 5-minute threshold. This creates a slow, confusing sequence: `in-progress` → (5 min wait) → reap branch → `ready` → detect merged PR → `done`.

Additionally, `relay check <feature>` is broken due to a bash quoting bug in `status.sh` — the `$TASKS_JSON` variable is interpolated into the `python3 -c "..."` command line, and shell metacharacters in task data break the invocation. The manual fallback doesn't work.

## Design

### Principle

**`done` means the PR is merged.** No other condition should move a task to `done`.

**Exception:** `wrap.sh --no-pr` (skip PR creation) retains the current behavior of marking `done` immediately, since there is no PR to wait for.

### Approach: Frontmatter PR tracking + watcher polling

Instead of adding a new status directory, tasks stay `in-progress` after the agent finishes. A `pr-url` frontmatter field distinguishes "agent working" from "awaiting review." The watcher checks PR state on every poll (~10s) and marks tasks `done` only when the PR is merged.

## Changes

### 1. `handle_success()` in `local-agent.sh`

**Current behavior:** Moves task to `done/`, commits, pushes.

**New behavior:**
- Derive the branch name, then look up the PR (via `gh pr list --head <branch> --repo <repo-nwo> --json url,number`)
- Write `pr-url` and `pr-number` fields into the task's YAML frontmatter (these fields are added to the task template with empty defaults — see section 9)
- Task stays in `in-progress/` — do NOT call `update_task_status "done"`
- Commit message: `review: <task-filename> (PR #N)`
- Push control plane
- Print message: "Task awaiting review — will be marked done when PR #N is merged"

If no PR is found (agent failed to create one), fall back to current behavior of marking `blocked`.

### 2. `wrap.sh`

**Current behavior:** Creates PR, then marks task `done`.

**New behavior:** Creates PR, writes `pr-url` and `pr-number` to task frontmatter, task stays `in-progress`. Same commit message pattern as above. Prints "Task awaiting review" message.

**Exception:** `wrap.sh --no-pr` retains the old behavior — marks `done` immediately since there is no PR to track.

### 3. New function: `check_merged_prs()` in `local-agent.sh`

Scans all `in-progress` tasks that have a `pr-number` field. For each:
1. Resolve the repo NWO from the task's `target-repo` field via the service catalog
2. Call `gh pr view <pr-number> --repo <repo-nwo> --json state --jq '.state'`
3. If state is `MERGED`: move task to `done/`, commit, push
4. If state is `CLOSED` (without merge): move task to `blocked/`, commit, push (PR was rejected)
5. If state is `OPEN`: skip (still awaiting review)

This function is called in the watcher loop on every poll iteration, **before** stale reaping.

**Error handling:** `gh pr view` failures (network errors, rate limits, invalid token) should be silently skipped — log a warning but do not block the watcher loop. The watcher uses `set -uo pipefail`; guard each `gh` call with `|| true` or a try/skip pattern.

**Implementation note:** Use `_parse-queue.py` with `--status in-progress` to find candidate tasks, then grep frontmatter for `pr-number`. This keeps the queue scanning logic centralized.

### 4. Watcher loop changes in `local-agent.sh`

**Current single-agent loop (line ~620):**
```
git pull + fetch
reap_stale_claims()
parse ready tasks → check merged PRs → claim
```

**New loop:**
```
git pull + fetch
check_merged_prs()          ← NEW: scan in-progress tasks with PRs
reap_stale_claims()         ← unchanged
parse ready tasks → claim   ← remove has_merged_pr() check from here
```

The `has_merged_pr()` check at line 642 (inside the ready-task loop) is kept as a safety net for edge cases where a task ended up in `ready/` but its PR was already merged (e.g., after manual `git mv` or a corrupted state recovery).

Same change applies to the multi-agent loop.

### 5. Fix `derive_branch_slug()` for bug-type tasks

**Pre-existing bug:** `derive_branch_slug()` in `_lib.sh` (line ~185) hardcodes the `agent/` prefix and ignores the task's `type` field. Bug-type tasks use `fix/` branches but the function generates `agent/` names. This means:
- `reap_stale_claims()` never matches bug task branches
- `check_merged_prs()` would generate wrong branch names for bug tasks
- `get_claimed_branches()` only lists `agent/*` branches, missing `fix/*`

**Fix:**
- `derive_branch_slug()`: read the task `type` from the file's frontmatter internally (avoids changing all callers). Use `fix/` prefix for `type: bug` tasks, `agent/` otherwise.
- `get_claimed_branches()`: list both `refs/heads/agent/*` and `refs/heads/fix/*`
- Note: `status.sh`'s inline Python has its own `derive_branch()` that already handles `fix/` correctly. After extracting to `_status-render.py`, ensure this stays in sync with the shell version.

### 6. Extract inline Python from `status.sh` into standalone scripts

**Problem:** Two inline Python blocks in `status.sh` — the main rendering block (lines 82-408) and the feature overview block (lines 427-577) — are passed via `python3 -c "..."`. The `$TASKS_JSON` argv expansion breaks when task data contains shell metacharacters.

**Fix:** Extract both blocks into standalone scripts:
- `_status-render.py` — main task table rendering and cross-referencing
- Keep the feature overview block inline if it's small, or extract to `_status-overview.py` if it has the same vulnerability

The shell wrapper handles arg parsing, service catalog iteration, and branch fetching, then delegates to the Python scripts.

**Display change:** When a task is `in-progress` and has a `pr-url` field, display status as `in-progress (awaiting review)` in both text and JSON output modes.

### 7. New command: `relay sync [feature]`

**Replaces** the existing `relay sync` alias (currently an alias for `relay handoff` — manual CP commit+push). The new `sync` subsumes the old behavior (commit+push) and adds PR checking and wave promotion.

A new script `sync.sh` that:
1. Pulls the control plane
2. For each repo in the service catalog, scans `in-progress` tasks (optionally filtered by feature) for merged PRs
3. Marks merged tasks as `done`
4. If all tasks in the current wave are `done`, auto-promotes the next wave (`pending` → `ready`)
5. Commits and pushes the control plane

Reuses the same underlying functions as `check_merged_prs()` to avoid duplication.

**Usage:**
```bash
relay sync              # check all features, all repos
relay sync darkmode     # check one feature
```

**Note:** The watcher's `check_merged_prs()` does NOT auto-promote waves — it only marks tasks done. Wave promotion is only triggered by `relay sync` (explicit user action) or `relay advance` (existing command). This avoids surprising automatic wave escalation.

### 8. CLI routing and help in `relay`

Split the existing `sync|handoff)` case into two separate cases:
```bash
sync)
    SCRIPT=$(find_script "sync.sh")
    if [ -n "$SCRIPT" ]; then
      exec "$SCRIPT" $(cp_dir_args) "$@"
    else
      echo -e "${RED}Error: sync.sh not found.${NC}"
      exit 1
    fi
    ;;

handoff)
    SCRIPT=$(find_script "handoff.sh")
    if [ -n "$SCRIPT" ]; then
      exec "$SCRIPT" $(cp_dir_args) "$@"
    else
      echo -e "${RED}Error: handoff.sh not found.${NC}"
      exit 1
    fi
    ;;
```

Update the help output to include `sync` in the core workflow section:
```
relay sync [<feature>]     Check merged PRs, update tasks, promote next wave
```

### 9. Documentation updates

**`relay` help command:** Add `sync` to the core workflow section and command listing.

**Control plane `CLAUDE.md`:** Update the following sections:
- **Task Status State Machine:** Add note that `done` requires a merged PR (exception: `--no-pr` mode)
- **Branch-Claim Protocol → Claim Flow:** Step 5 ("On success") should reference `in-progress` with PR tracking, not `done`
- **Reference section:** Add `relay sync` to the workflow/command list
- **Conventions:** Add note about `pr-url`/`pr-number` frontmatter fields

**`process/workflows/relay.md`** (if it references the done flow): Update to reflect that tasks stay `in-progress` until PR merges.

**Task queue item template:** Add `pr-url: ""` and `pr-number: ""` fields with empty defaults so `sed`-based frontmatter updates work consistently.

## State Flow (Updated)

```
pending/ → ready/ → in-progress/ → done/
                     (agent working)
                     ↓
                     in-progress/ (pr-url set, awaiting review)
                     ↓
                     done/ (PR merged — detected by watcher or relay sync)

                     in-progress/ → blocked/ (agent failed, or PR closed without merge)
```

The directory structure is unchanged. The `pr-url` frontmatter field is the discriminator.

## Not Changed

- Status directories (no new `awaiting-review/` directory)
- `_parse-queue.py` (no changes needed)
- Stale reaping logic (still handles crashed agents with no PR)
- Multi-agent mode (uses same `handle_success()` and watcher functions)
- `has_merged_pr()` function (kept as safety net for ready-task edge cases)

## Task Frontmatter Addition

```yaml
---
status: in-progress
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/42
pr-number: 42
# ... existing fields ...
---
```

## API Call Considerations

`check_merged_prs()` makes one `gh pr view` call per in-progress task with a PR on each poll (~10s). For typical workloads (1-5 in-progress tasks), this is negligible. If the number of concurrent tasks grows, consider batching via `gh api graphql` or adding a short cache (skip re-checking PRs that were `OPEN` less than 30s ago).
