# Faster Task Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make task completion driven by merged PRs instead of agent exit, with ~10s detection latency.

**Architecture:** Tasks stay `in-progress` after agent finishes, with `pr-url`/`pr-number` recorded in frontmatter. The watcher polls PR state every 10s and marks `done` only when merged. A new `relay sync` command provides manual instant reconciliation.

**Tech Stack:** Bash, Python 3, `gh` CLI, Git

**Spec:** `docs/superpowers/specs/2026-03-24-faster-task-completion-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `relay/process/templates/task-queue-item.md` | Modify | Add `pr-url` and `pr-number` empty defaults |
| `relay/process/scripts/_lib.sh` | Modify | Fix `derive_branch_slug()` for bug tasks, fix `get_claimed_branches()` for `fix/*` branches, add `set_task_pr_info()` |
| `relay/process/scripts/local-agent.sh` | Modify | Change `handle_success()`, add `check_merged_prs()`, update both watcher loops |
| `relay/process/scripts/wrap.sh` | Modify | Stop marking done, record PR info instead |
| `relay/process/scripts/_status-render.py` | Create | Extracted Python block from status.sh |
| `relay/process/scripts/status.sh` | Modify | Replace inline Python with call to `_status-render.py`, add "awaiting review" display |
| `relay/process/scripts/sync.sh` | Create | New `relay sync` command |
| `relay/relay` | Modify | Add `sync)` case, split `handoff)`, update help text |
| `tasks-control-plane/CLAUDE.md` | Modify | Update state machine docs, add `relay sync` |

---

### Task 1: Add PR fields to task template

**Files:**
- Modify: `relay/process/templates/task-queue-item.md`

- [ ] **Step 1: Read the current template**

Read `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/templates/task-queue-item.md` to confirm current frontmatter fields.

- [ ] **Step 2: Add pr-url and pr-number fields**

Add after the `claimed-on` field and before `cost-usd`:

```yaml
pr-url: ""
pr-number: ""
```

The full frontmatter should now include:
```yaml
claimed-by: ""
claimed-at: ""
claimed-on: ""
pr-url: ""
pr-number: ""
cost-usd: ""
```

- [ ] **Step 3: Commit**

```bash
cd /Users/christianjensen/src/agentic-sdlc-demo/relay
git add process/templates/task-queue-item.md
git commit -m "feat: add pr-url and pr-number fields to task template"
```

---

### Task 2: Fix `derive_branch_slug()` and `get_claimed_branches()` in `_lib.sh`

**Files:**
- Modify: `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/scripts/_lib.sh:177-193`

- [ ] **Step 1: Fix `derive_branch_slug()` to handle bug tasks**

Current code (lines 177-186):
```bash
derive_branch_slug() {
  local file_path="$1" repo_name="$2"
  local feature_slug filename wave_num task_slug
  feature_slug="$(feature_from_task_path "$file_path")"
  filename="$(basename "$file_path" .md)"
  wave_num=$(echo "$filename" | sed -E 's/^wave-([0-9]+)-.*/\1/')
  task_slug=$(echo "$filename" | sed -E "s/^wave-[0-9]+-${repo_name}-//")
  echo "agent/${feature_slug}-w${wave_num}-${task_slug}"
}
```

Replace with:
```bash
derive_branch_slug() {
  local file_path="$1" repo_name="$2"
  local feature_slug filename wave_num task_slug task_type prefix
  feature_slug="$(feature_from_task_path "$file_path")"
  filename="$(basename "$file_path" .md)"
  wave_num=$(echo "$filename" | sed -E 's/^wave-([0-9]+)-.*/\1/')
  task_slug=$(echo "$filename" | sed -E "s/^wave-[0-9]+-${repo_name}-//")

  # Read task type from frontmatter to determine branch prefix
  task_type=$(sed -n '/^---$/,/^---$/{ s/^type:[[:space:]]*//p; }' "$file_path" 2>/dev/null | head -1)
  if [ "$task_type" = "bug" ]; then
    prefix="fix"
  else
    prefix="agent"
  fi
  echo "${prefix}/${feature_slug}-w${wave_num}-${task_slug}"
}
```

- [ ] **Step 2: Fix `get_claimed_branches()` to include `fix/*` branches**

Current code (lines 188-193):
```bash
get_claimed_branches() {
  local repo_dir="$1"
  git -C "$repo_dir" ls-remote --heads origin 'refs/heads/agent/*' 2>/dev/null \
    | awk '{print $2}' | sed 's|refs/heads/||'
}
```

Replace with:
```bash
get_claimed_branches() {
  local repo_dir="$1"
  git -C "$repo_dir" ls-remote --heads origin 'refs/heads/agent/*' 'refs/heads/fix/*' 2>/dev/null \
    | awk '{print $2}' | sed 's|refs/heads/||'
}
```

- [ ] **Step 3: Verify no callers break**

Search for all callers of `derive_branch_slug` and `get_claimed_branches`:
```bash
grep -rn 'derive_branch_slug\|get_claimed_branches' /Users/christianjensen/src/agentic-sdlc-demo/relay/process/scripts/
```

Confirm all callers still pass the same args (file_path, repo_name). The function now reads type internally so no caller changes needed.

- [ ] **Step 4: Commit**

```bash
cd /Users/christianjensen/src/agentic-sdlc-demo/relay
git add process/scripts/_lib.sh
git commit -m "fix: derive_branch_slug handles bug tasks, get_claimed_branches includes fix/* branches"
```

---

### Task 3: Add `set_task_pr_info()` to `_lib.sh`

**Files:**
- Modify: `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/scripts/_lib.sh`

- [ ] **Step 1: Add the function after `set_task_claim()` (after line ~288)**

Follow the same pattern as `set_task_claim()` (lines 270-288). Add this function:

```bash
set_task_pr_info() {
  local file_path="$1" pr_url="$2" pr_number="$3"
  python3 -c "
import re
with open('$file_path') as f:
    content = f.read()
m = re.match(r'^(---\s*\n)(.*?)(\n---)', content, re.DOTALL)
if m:
    front = m.group(2)
    for field, value in [('pr-url', '$pr_url'), ('pr-number', '$pr_number')]:
        if re.search(r'^' + field + ':', front, re.MULTILINE):
            front = re.sub(r'^' + field + ':.*$', field + ': ' + value, front, flags=re.MULTILINE)
        else:
            front += '\n' + field + ': ' + value
    content = m.group(1) + front + m.group(3) + content[m.end():]
with open('$file_path', 'w') as f:
    f.write(content)
"
}
```

- [ ] **Step 2: Add a helper to read pr-number from a task file**

Add after `set_task_pr_info`:

```bash
get_task_pr_number() {
  local file_path="$1"
  sed -n '/^---$/,/^---$/{ s/^pr-number:[[:space:]]*//p; }' "$file_path" 2>/dev/null \
    | head -1 | sed 's/^"//;s/"$//'
}

# Resolve repo NWO from target-repo name via service catalog
resolve_repo_nwo() {
  local target_repo="$1"
  while IFS='|' read -r _name _nwo _local; do
    if [ "$_name" = "$target_repo" ]; then
      echo "$_nwo"
      return
    fi
  done < <(parse_service_catalog)
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/christianjensen/src/agentic-sdlc-demo/relay
git add process/scripts/_lib.sh
git commit -m "feat: add set_task_pr_info() and get_task_pr_number() to _lib.sh"
```

---

### Task 4: Change `handle_success()` in `local-agent.sh`

**Files:**
- Modify: `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/scripts/local-agent.sh:513-531`

- [ ] **Step 1: Replace `handle_success()` function**

Current code (lines 513-531):
```bash
handle_success() {
  local queue_file="$1" work_dir="$2" branch_slug="$3" cost_json="${4:-\{\}}"

  # Persist cost fields in task frontmatter
  persist_cost_fields "$queue_file" "$cost_json"

  queue_file=$(update_task_status "$queue_file" "done")
  git -C "$CP_DIR" add "$queue_file" 2>/dev/null
  git -C "$CP_DIR" commit -m "done: $(basename "$queue_file")" 2>/dev/null || true
  push_cp_with_retry || true
  log_ok "Task completed: $(basename "$queue_file")"

  # Generate handoff note
  if [ -n "$work_dir" ] && [ -n "$branch_slug" ]; then
    python3 "$SCRIPT_DIR/_handoff-note.py" "$queue_file" \
      --status "done" --work-dir "$work_dir" --branch "$branch_slug" \
      --cp-dir "$CP_DIR" --cost-json "$cost_json" 2>/dev/null || true
  fi
}
```

Replace with:
```bash
handle_success() {
  local queue_file="$1" work_dir="$2" branch_slug="$3" cost_json="${4:-\{\}}"
  local repo_nwo pr_number pr_url

  # Persist cost fields in task frontmatter
  persist_cost_fields "$queue_file" "$cost_json"

  # Look up the repo NWO from the task's target-repo via service catalog
  local target_repo
  target_repo=$(sed -n '/^---$/,/^---$/{ s/^target-repo:[[:space:]]*//p; }' "$queue_file" 2>/dev/null | head -1)
  repo_nwo=$(resolve_repo_nwo "$target_repo")

  # Look up PR for this branch
  if [ -n "$repo_nwo" ] && [ -n "$branch_slug" ]; then
    local pr_json
    pr_json=$(gh pr list --repo "$repo_nwo" --head "$branch_slug" --json number,url --limit 1 2>/dev/null || echo "[]")
    pr_number=$(echo "$pr_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['number'] if d else '')" 2>/dev/null || true)
    pr_url=$(echo "$pr_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['url'] if d else '')" 2>/dev/null || true)
  fi

  if [ -n "$pr_number" ]; then
    # PR exists — record it and leave task in-progress (awaiting review)
    set_task_pr_info "$queue_file" "$pr_url" "$pr_number"
    git -C "$CP_DIR" add "$queue_file" 2>/dev/null
    git -C "$CP_DIR" commit -m "review: $(basename "$queue_file") (PR #${pr_number})" 2>/dev/null || true
    push_cp_with_retry || true
    log_ok "Task awaiting review — will be marked done when PR #${pr_number} is merged"
  else
    # No PR found — mark blocked
    queue_file=$(update_task_status "$queue_file" "blocked")
    git -C "$CP_DIR" add "$queue_file" 2>/dev/null
    git -C "$CP_DIR" commit -m "blocked: $(basename "$queue_file") (no PR found)" 2>/dev/null || true
    push_cp_with_retry || true
    log_err "No PR found for branch $branch_slug — task marked blocked"
  fi

  # Generate handoff note
  if [ -n "$work_dir" ] && [ -n "$branch_slug" ]; then
    python3 "$SCRIPT_DIR/_handoff-note.py" "$queue_file" \
      --status "done" --work-dir "$work_dir" --branch "$branch_slug" \
      --cp-dir "$CP_DIR" --cost-json "$cost_json" 2>/dev/null || true
  fi
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/christianjensen/src/agentic-sdlc-demo/relay
git add process/scripts/local-agent.sh
git commit -m "feat: handle_success records PR info instead of marking done"
```

---

### Task 5: Add `check_merged_prs()` and update watcher loops in `local-agent.sh`

**Files:**
- Modify: `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/scripts/local-agent.sh`

- [ ] **Step 1: Add `check_merged_prs()` function before the watcher loops (before line ~600)**

Add after `has_merged_pr()` (after line 214):

```bash
# ── Merged PR Detection ────────────────────────────────────────────
# Scans all in-progress tasks with pr-number set and checks if the PR is merged.
# Uses parse_queue_all() to get tasks (JSON→lines conversion included).
parse_queue_all() {
  # Like parse_queue() but without --execution filter, for PR reconciliation
  local target_repo="$1" status_filter="$2"
  python3 "$SCRIPT_DIR/_parse-queue.py" \
    "$CP_DIR/queue" "$target_repo" \
    --status "$status_filter" 2>/dev/null \
  | python3 -c "
import json, sys
for c in json.load(sys.stdin):
    print(f\"{c['rank']} {c['wave']} {c['path']}\")
" 2>/dev/null
}

check_merged_prs() {
  local repo_name="$1" repo_nwo="$2"
  local pr_num pr_state queue_file

  # Find in-progress tasks for this repo
  local candidates
  candidates=$(parse_queue_all "$repo_name" "in-progress")
  [ -z "$candidates" ] && return

  while IFS=' ' read -r _rank _wave queue_file; do
    [ -z "$queue_file" ] && continue

    pr_num=$(get_task_pr_number "$queue_file")
    [ -z "$pr_num" ] && continue

    # Check PR state (skip on error — don't block the watcher)
    pr_state=$(gh pr view "$pr_num" --repo "$repo_nwo" --json state --jq '.state' 2>/dev/null || echo "")
    if [ -z "$pr_state" ]; then
      continue
    fi

    if [ "$pr_state" = "MERGED" ]; then
      log_ok "PR #${pr_num} merged — marking done: $(basename "$queue_file")"
      queue_file=$(update_task_status "$queue_file" "done")
      git -C "$CP_DIR" add "$queue_file" 2>/dev/null
      git -C "$CP_DIR" commit -m "done: $(basename "$queue_file") (PR #${pr_num} merged)" 2>/dev/null || true
      push_cp_with_retry || true
    elif [ "$pr_state" = "CLOSED" ]; then
      log_warn "PR #${pr_num} closed without merge — marking blocked: $(basename "$queue_file")"
      queue_file=$(update_task_status "$queue_file" "blocked")
      git -C "$CP_DIR" add "$queue_file" 2>/dev/null
      git -C "$CP_DIR" commit -m "blocked: $(basename "$queue_file") (PR #${pr_num} closed)" 2>/dev/null || true
      push_cp_with_retry || true
    fi
  done <<< "$candidates"
}
```

- [ ] **Step 3: Insert `check_merged_prs` call in single-agent watcher loop**

In the single-agent loop (line ~620), after `git fetch` and **before** `reap_stale_claims`, add:

```bash
      check_merged_prs "$repo_name" "$repo_nwo"
```

The loop should now read:
```bash
      git -C "$CP_DIR" pull --ff-only 2>/dev/null || true
      git -C "$repo_dir" fetch origin 2>/dev/null || true
      check_merged_prs "$repo_name" "$repo_nwo"
      reap_stale_claims "$repo_dir" "$repo_name" "$repo_nwo"
```

- [ ] **Step 4: Insert `check_merged_prs` call in multi-agent watcher loop**

In the multi-agent loop, after `git fetch` and before `reap_stale_claims` (around line ~740), add the same call:

```bash
    check_merged_prs "$repo_name" "$repo_nwo"
```

- [ ] **Step 5: Commit**

```bash
cd /Users/christianjensen/src/agentic-sdlc-demo/relay
git add process/scripts/local-agent.sh
git commit -m "feat: add check_merged_prs() to watcher loop — detect merged PRs every poll"
```

---

### Task 6: Update `wrap.sh` to record PR info instead of marking done

**Files:**
- Modify: `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/scripts/wrap.sh:294-315`

- [ ] **Step 1: Replace Step 8 (mark task done) with PR recording**

Current code (lines 294-315):
```bash
# ── Step 8: Mark task done ────────────────────────────────────────
if [ "$CURRENT_STATUS" != "done" ]; then
  log "Marking task done..."
  TASK_PATH=$(update_task_status "$TASK_PATH" "done")
  git -C "$CP_PATH" add "$TASK_PATH" 2>/dev/null
  git -C "$CP_PATH" commit -m "done: $TASK_FILENAME" --quiet 2>/dev/null

  log "Pushing control plane..."
  push_cp_with_retry 2>/dev/null || log_warn "Could not push control plane update."
  log_ok "Task marked ${BOLD}done${NC}."
else
  log "Task already done — skipping CP update."
fi

# ── Step 9: Generate handoff note ─────────────────────────────────
log "Generating session handoff..."
if ! python3 "$SCRIPT_DIR/_handoff-note.py" "$TASK_PATH" \
    --status "done" \
    --work-dir "$REPO_DIR" --branch "$BRANCH" \
    --cp-dir "$CP_PATH"; then
  log_warn "Handoff generation failed (continuing)"
fi
```

Replace with:
```bash
# ── Step 8: Record PR info or mark done ───────────────────────────
if [ "$CURRENT_STATUS" != "done" ]; then
  if [ "$NO_PR" = true ]; then
    # No PR mode — mark done immediately
    log "Marking task done (no PR)..."
    TASK_PATH=$(update_task_status "$TASK_PATH" "done")
    git -C "$CP_PATH" add "$TASK_PATH" 2>/dev/null
    git -C "$CP_PATH" commit -m "done: $TASK_FILENAME (no PR)" --quiet 2>/dev/null

    log "Pushing control plane..."
    push_cp_with_retry 2>/dev/null || log_warn "Could not push control plane update."
    log_ok "Task marked ${BOLD}done${NC}."
  elif [ -n "$PR_URL" ]; then
    # PR exists — record it, leave task in-progress
    pr_num=$(echo "$PR_URL" | grep -oE '[0-9]+$' || true)
    log "Recording PR info..."
    set_task_pr_info "$TASK_PATH" "$PR_URL" "$pr_num"
    git -C "$CP_PATH" add "$TASK_PATH" 2>/dev/null
    git -C "$CP_PATH" commit -m "review: $TASK_FILENAME (PR #${pr_num})" --quiet 2>/dev/null

    log "Pushing control plane..."
    push_cp_with_retry 2>/dev/null || log_warn "Could not push control plane update."
    log_ok "Task awaiting review — will be marked done when PR #${pr_num} is merged."
  else
    # No PR URL captured — mark blocked
    log_warn "No PR URL available — marking task blocked."
    TASK_PATH=$(update_task_status "$TASK_PATH" "blocked")
    git -C "$CP_PATH" add "$TASK_PATH" 2>/dev/null
    git -C "$CP_PATH" commit -m "blocked: $TASK_FILENAME (no PR)" --quiet 2>/dev/null
    push_cp_with_retry 2>/dev/null || log_warn "Could not push control plane update."
  fi
else
  log "Task already done — skipping CP update."
fi

# ── Step 9: Generate handoff note ─────────────────────────────────
log "Generating session handoff..."
if ! python3 "$SCRIPT_DIR/_handoff-note.py" "$TASK_PATH" \
    --status "review" \
    --work-dir "$REPO_DIR" --branch "$BRANCH" \
    --cp-dir "$CP_PATH"; then
  log_warn "Handoff generation failed (continuing)"
fi
```

- [ ] **Step 2: Commit**

```bash
cd /Users/christianjensen/src/agentic-sdlc-demo/relay
git add process/scripts/wrap.sh
git commit -m "feat: wrap.sh records PR info instead of marking done"
```

---

### Task 7: Extract inline Python from `status.sh` into `_status-render.py`

**Files:**
- Create: `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/scripts/_status-render.py`
- Modify: `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/scripts/status.sh:81-409`

- [ ] **Step 1: Create `_status-render.py`**

Extract lines 82-408 from `status.sh` into a new file `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/scripts/_status-render.py`. Add a shebang and make it executable.

The file should start with:
```python
#!/usr/bin/env python3
"""Relay status renderer — cross-references tasks with branches and PRs.

Usage: _status-render.py <tasks_json> <branches> <repo_local> <repo_nwo> <repo_name>
                         <feature_filter> <fix_mode> <json_mode> <cp_dir> <json_tmp>
                         <seen_features_file>
"""
import json, subprocess, sys, os, time, re
```

Then paste the entire Python block (lines 82-408 of status.sh) as the body.

- [ ] **Step 2: Add "awaiting review" display logic**

In the `_status-render.py` file, find the status display section (around original line 334-345). After computing `status_label`, add logic to read `pr-url` from the task file (since `_parse-queue.py` does not output this field):

```python
        # Check if task has a PR recorded in frontmatter (read from file)
        task_pr_url = ''
        task_pr_number = ''
        try:
            with open(task_path) as _f:
                _content = _f.read()
            _fm = re.match(r'^---\s*\n(.*?)\n---', _content, re.DOTALL)
            if _fm:
                _m = re.search(r'^pr-url:\s*(.+)', _fm.group(1), re.MULTILINE)
                if _m: task_pr_url = _m.group(1).strip().strip('"').strip("'")
                _m = re.search(r'^pr-number:\s*(.+)', _fm.group(1), re.MULTILINE)
                if _m: task_pr_number = _m.group(1).strip().strip('"').strip("'")
        except Exception:
            pass

        # Show "awaiting review" for in-progress tasks with a PR
        if task_status == 'in-progress' and task_pr_url:
            status_label = 'in-progress (awaiting review)'
```

Also in the JSON output section (around original line 349-371), add PR fields to the task JSON:
```python
            task_json = {
                ...existing fields...
                'pr_url': task_pr_url or None,
                'pr_number': task_pr_number or None,
                'awaiting_review': bool(task_pr_url),
            }
```

- [ ] **Step 3: Make `_status-render.py` executable**

```bash
chmod +x /Users/christianjensen/src/agentic-sdlc-demo/relay/process/scripts/_status-render.py
```

- [ ] **Step 4: Update `status.sh` to call the external script**

Replace lines 81-409 in `status.sh`:

From:
```bash
  python3 -c "
import json, subprocess, sys, os, time, re
...330 lines of Python...
" "$TASKS_JSON" "$BRANCHES" "$repo_local" "$repo_nwo" "$repo_name" "$FEATURE_FILTER" "$FIX_MODE" "$JSON_MODE" "${CP_DIR:-$RELAY_DIR}" "$JSON_TMP" "$SEEN_FEATURES_FILE"
```

To:
```bash
  python3 "$SCRIPT_DIR/_status-render.py" "$TASKS_JSON" "$BRANCHES" "$repo_local" "$repo_nwo" "$repo_name" "$FEATURE_FILTER" "$FIX_MODE" "$JSON_MODE" "${CP_DIR:-$RELAY_DIR}" "$JSON_TMP" "$SEEN_FEATURES_FILE"
```

This is a single line replacing the entire `python3 -c "..."` block.

- [ ] **Step 5: Test that `relay check` works**

```bash
cd /Users/christianjensen/src/agentic-sdlc-demo/tasks-control-plane
relay check darkmode
relay check darkmode --json
relay check
```

All three should now show task data instead of "No tasks found."

- [ ] **Step 6: Commit**

```bash
cd /Users/christianjensen/src/agentic-sdlc-demo/relay
git add process/scripts/_status-render.py process/scripts/status.sh
git commit -m "fix: extract status.sh inline Python to _status-render.py — fixes quoting bug"
```

---

### Task 8: Create `sync.sh` and wire up CLI routing

**Files:**
- Create: `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/scripts/sync.sh`
- Modify: `/Users/christianjensen/src/agentic-sdlc-demo/relay/relay:326-335`

- [ ] **Step 1: Create `sync.sh`**

Create `/Users/christianjensen/src/agentic-sdlc-demo/relay/process/scripts/sync.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Relay Sync — check merged PRs, update task status, promote next wave.
#
# Usage:
#   sync.sh [--cp-dir <path>] [<feature>]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Parse CLI flags
FEATURE_FILTER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir)
      export CP_DIR="$2"
      shift 2
      ;;
    -*)
      echo "Usage: relay sync [<feature>]"
      exit 1
      ;;
    *)
      FEATURE_FILTER="$1"
      shift
      ;;
  esac
done

# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
_LOG_CONTEXT="sync"

QUEUE_DIR="${CP_DIR:-$RELAY_DIR}/queue"

# Helper: parse queue JSON into "rank wave path" lines (like parse_queue but no execution filter)
parse_queue_all() {
  python3 "$SCRIPT_DIR/_parse-queue.py" \
    "$QUEUE_DIR" "$1" \
    --status "$2" 2>/dev/null \
  | python3 -c "
import json, sys
for c in json.load(sys.stdin):
    print(f\"{c['rank']} {c['wave']} {c['path']}\")
" 2>/dev/null
}

# Pull latest control plane
git -C "${CP_DIR:-$RELAY_DIR}" pull --ff-only 2>/dev/null || true

SYNCED=false

while IFS='|' read -r repo_name repo_nwo repo_local; do
  [ -z "$repo_name" ] && continue

  # Fetch latest branches
  if [ -d "$repo_local" ]; then
    git -C "$repo_local" fetch origin 2>/dev/null || true
  fi

  # Find in-progress tasks
  CANDIDATES=$(parse_queue_all "$repo_name" "in-progress")
  [ -z "$CANDIDATES" ] && continue

  while IFS=' ' read -r _rank _wave queue_file; do
    [ -z "$queue_file" ] && continue

    # Filter by feature if specified
    if [ -n "$FEATURE_FILTER" ]; then
      feat=$(feature_from_task_path "$queue_file")
      if [ "$feat" != "$FEATURE_FILTER" ]; then
        continue
      fi
    fi

    pr_num=$(get_task_pr_number "$queue_file")
    [ -z "$pr_num" ] && continue

    # Check PR state
    pr_state=$(gh pr view "$pr_num" --repo "$repo_nwo" --json state --jq '.state' 2>/dev/null || echo "")
    if [ -z "$pr_state" ]; then
      log_warn "Could not check PR #${pr_num} for $(basename "$queue_file")"
      continue
    fi

    if [ "$pr_state" = "MERGED" ]; then
      log_ok "PR #${pr_num} merged → $(basename "$queue_file") → done"
      queue_file=$(update_task_status "$queue_file" "done")
      git -C "${CP_DIR:-$RELAY_DIR}" add "$queue_file" 2>/dev/null
      git -C "${CP_DIR:-$RELAY_DIR}" commit -m "done: $(basename "$queue_file") (PR #${pr_num} merged)" 2>/dev/null || true
      SYNCED=true
    elif [ "$pr_state" = "CLOSED" ]; then
      log_warn "PR #${pr_num} closed → $(basename "$queue_file") → blocked"
      queue_file=$(update_task_status "$queue_file" "blocked")
      git -C "${CP_DIR:-$RELAY_DIR}" add "$queue_file" 2>/dev/null
      git -C "${CP_DIR:-$RELAY_DIR}" commit -m "blocked: $(basename "$queue_file") (PR #${pr_num} closed)" 2>/dev/null || true
      SYNCED=true
    else
      log "PR #${pr_num} still open — $(basename "$queue_file") awaiting review"
    fi
  done <<< "$CANDIDATES"
done < <(parse_service_catalog)

# Auto-promote next wave if all current wave tasks are done
if [ "$SYNCED" = true ]; then
  # Push accumulated changes
  push_cp_with_retry || log_warn "Could not push control plane update."

  # Check if we should promote
  PROMOTE_SCRIPT="$SCRIPT_DIR/promote-tasks.sh"
  if [ -x "$PROMOTE_SCRIPT" ]; then
    if [ -n "$FEATURE_FILTER" ]; then
      log "Checking if next wave can be promoted..."
      "$PROMOTE_SCRIPT" --cp-dir "${CP_DIR:-$RELAY_DIR}" "$FEATURE_FILTER" 2>/dev/null || true
    fi
  fi
else
  log "Nothing to sync."
fi
```

- [ ] **Step 2: Make `sync.sh` executable**

```bash
chmod +x /Users/christianjensen/src/agentic-sdlc-demo/relay/process/scripts/sync.sh
```

- [ ] **Step 3: Update CLI routing in `relay` — split `sync|handoff)` case**

In `/Users/christianjensen/src/agentic-sdlc-demo/relay/relay`, replace the `sync|handoff)` case (lines 326-335):

From:
```bash
  sync|handoff)
    # relay sync — manual CP commit+push (alias: relay handoff)
    SCRIPT=$(find_script "handoff.sh")
    if [ -n "$SCRIPT" ]; then
      exec "$SCRIPT" $(cp_dir_args) "$@"
    else
      echo -e "${RED}Error: handoff.sh not found.${NC}"
      exit 1
    fi
    ;;
```

To:
```bash
  sync)
    # relay sync — check merged PRs, update tasks, promote next wave
    SCRIPT=$(find_script "sync.sh")
    if [ -n "$SCRIPT" ]; then
      exec "$SCRIPT" $(cp_dir_args) "$@"
    else
      echo -e "${RED}Error: sync.sh not found.${NC}"
      exit 1
    fi
    ;;

  handoff)
    # relay handoff — manual CP commit+push
    SCRIPT=$(find_script "handoff.sh")
    if [ -n "$SCRIPT" ]; then
      exec "$SCRIPT" $(cp_dir_args) "$@"
    else
      echo -e "${RED}Error: handoff.sh not found.${NC}"
      exit 1
    fi
    ;;
```

- [ ] **Step 4: Update help text**

In the `relay help --all` section (around line 521), replace:
```bash
      echo -e "  ${_cp}   relay sync [--dry-run]                     Manual CP commit + push"
```

With:
```bash
      echo -e "  ${_cp}   relay sync [<feature>]                     Check merged PRs, update tasks, promote"
      echo -e "  ${_cp}   relay handoff [--dry-run]                  Manual CP commit + push"
```

In the compact help (around line 537-546), add after the `relay check` line:
```bash
      echo -e "  ${_cp}   relay sync [<feature>]      Check merged PRs, update tasks"
```

In the workflow guide help (around line 475-480), add after step 4 (relay check):
```bash
      echo -e "  ${DIM}5.${NC} ${_cp}   ${BOLD}relay sync [<feature>]${NC}        Sync merged PRs → done + promote"
```

And renumber the existing step 5 (relay close) to step 6.

- [ ] **Step 5: Test the new command**

```bash
cd /Users/christianjensen/src/agentic-sdlc-demo/tasks-control-plane
relay sync --help 2>&1 || true
relay sync darkmode
relay help --all
```

- [ ] **Step 6: Commit**

```bash
cd /Users/christianjensen/src/agentic-sdlc-demo/relay
git add process/scripts/sync.sh relay
git commit -m "feat: add relay sync command — check merged PRs, update tasks, promote waves"
```

---

### Task 9: Update documentation

**Files:**
- Modify: `/Users/christianjensen/src/agentic-sdlc-demo/tasks-control-plane/CLAUDE.md`

- [ ] **Step 1: Update the Workflows table**

In the `## Workflows (MANDATORY)` section, add a row:

```markdown
| Sync merged PRs, update task status | **Sync** | Run `relay sync [feature]` |
```

- [ ] **Step 2: Update the Task Status State Machine**

In the `## Reference: Task Status State Machine` section, add a note after the state machine diagram:

```markdown
**Done requires merged PR:** Tasks are only moved to `done/` when their PR is merged (detected by the watcher every ~10s or manually via `relay sync`). Exception: `relay done --no-pr` marks done immediately.
```

- [ ] **Step 3: Update the Branch-Claim Protocol → Claim Flow**

Change step 5 from:
```
5. On success → create PR (squash merge), git mv in-progress/task.md done/task.md
```
To:
```
5. On success → create PR, record pr-url/pr-number in frontmatter (task stays in-progress)
6. On PR merge → watcher or relay sync detects merge, git mv in-progress/task.md done/task.md
```

- [ ] **Step 4: Add pr-url/pr-number to the Queue Format reference**

In the `## Reference: Queue Format` section, add to the YAML example:

```yaml
pr-url: ""
pr-number: ""
```

- [ ] **Step 5: Add `relay sync` to reference**

Add a brief section or add to the Workflows table:
```markdown
| Sync merged PRs, promote waves | **Sync** | Run `relay sync [feature]` |
```

- [ ] **Step 6: Commit**

```bash
cd /Users/christianjensen/src/agentic-sdlc-demo/tasks-control-plane
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md — done requires merged PR, add relay sync"
```

---

### Task 10: End-to-end verification

- [ ] **Step 1: Verify `relay check darkmode` works**

```bash
cd /Users/christianjensen/src/agentic-sdlc-demo/tasks-control-plane
relay check darkmode
```

Should show the darkmode tasks with their current status instead of "No tasks found."

- [ ] **Step 2: Verify `relay check darkmode --json` works**

```bash
relay check darkmode --json
```

Should return JSON with task objects.

- [ ] **Step 3: Verify `relay sync darkmode` works**

```bash
relay sync darkmode
```

Should check PR state for any in-progress tasks with pr-number set. If the wave-1 task is already done, it should report "Nothing to sync."

- [ ] **Step 4: Verify `relay help --all` shows sync**

```bash
relay help --all
```

Should show `relay sync [<feature>]` in the command listing.

- [ ] **Step 5: Verify the task template has new fields**

```bash
grep -A2 'pr-url' /Users/christianjensen/src/agentic-sdlc-demo/relay/process/templates/task-queue-item.md
```

Should show `pr-url: ""` and `pr-number: ""`.

- [ ] **Step 6: Verify `derive_branch_slug` handles bug tasks**

Create a temporary task file with `type: bug` and verify the branch prefix:
```bash
grep -A1 'derive_branch_slug' /Users/christianjensen/src/agentic-sdlc-demo/relay/process/scripts/_lib.sh
```

Confirm the function reads `type` from frontmatter and uses `fix/` prefix for bug tasks.

- [ ] **Step 7: Mark verification complete**

All changes verified. The implementation is complete.
