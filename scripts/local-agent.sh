#!/usr/bin/env bash
set -uo pipefail
# Note: no 'set -e' — we handle errors explicitly so the watcher loop survives failures

# Relay Local Agent — polls the Git-native task queue, claims tasks, and runs
# Claude agents locally. Replaces start-agents.sh + agent-watcher.sh.
#
# Usage:
#   ./local-agent.sh [--cp-dir <path>] [--agents-per-repo N] [--poll N]
#
# Reads repos from service-catalog.md. For each repo, launches a watcher loop
# that polls the queue for ready tasks, claims them via atomic branch-push, and
# spins up Claude agents.
#
# Stop with Ctrl+C (kills all watchers and cleans up worktrees).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Defaults
AGENTS_PER_REPO=1
POLL_INTERVAL=10
FILTER_REPO=""
INTERACTIVE=false

# Parse CLI flags (before sourcing _lib.sh so CP_DIR is set)
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir)
      export CP_DIR="$2"
      shift 2
      ;;
    --agents-per-repo)
      AGENTS_PER_REPO="$2"
      shift 2
      ;;
    --poll)
      POLL_INTERVAL="$2"
      shift 2
      ;;
    --repo)
      FILTER_REPO="$2"
      shift 2
      ;;
    --interactive)
      INTERACTIVE=true
      shift
      ;;
    *)
      echo "Usage: $0 [--cp-dir <path>] [--agents-per-repo N] [--poll N] [--repo <name>] [--interactive]"
      exit 1
      ;;
  esac
done

# Source shared library
source "$SCRIPT_DIR/_lib.sh"

# Validate CP_DIR
if [ -z "${CP_DIR:-}" ]; then
  echo -e "${RED}Error: CP_DIR not set. Use --cp-dir or run from a control plane.${NC}" >&2
  exit 1
fi

# ── Read service catalog ──────────────────────────────────────
CATALOG_FILE="$CP_DIR/.relay/service-catalog.md"
if [[ ! -f "$CATALOG_FILE" ]]; then
  echo -e "${YELLOW}ERROR: service-catalog.md not found at $CATALOG_FILE${NC}" >&2
  exit 1
fi

REPO_NAMES=()
REPO_PATHS=()

while IFS='|' read -r name _nwo local_path; do
  local_path="${local_path/#\~/$HOME}"
  REPO_NAMES+=("$name")
  REPO_PATHS+=("$local_path")
done < <(parse_service_catalog "$CATALOG_FILE")

# Filter to a single repo if --repo was given
if [[ -n "$FILTER_REPO" ]]; then
  FOUND=false
  for i in "${!REPO_NAMES[@]}"; do
    if [[ "${REPO_NAMES[$i]}" == "$FILTER_REPO" ]]; then
      REPO_NAMES=("${REPO_NAMES[$i]}")
      REPO_PATHS=("${REPO_PATHS[$i]}")
      FOUND=true
      break
    fi
  done
  if [[ "$FOUND" == false ]]; then
    echo -e "${YELLOW}ERROR: Repo '$FILTER_REPO' not found in $CATALOG_FILE${NC}" >&2
    exit 1
  fi
fi

if [[ ${#REPO_NAMES[@]} -eq 0 ]]; then
  echo -e "${YELLOW}ERROR: No repos found in $CATALOG_FILE${NC}" >&2
  exit 1
fi

# ── Banner ──────────────────────────────────────────────────────
BOX_WIDTH=52

echo -e "${GREEN}╔$(printf '═%.0s' $(seq 1 $BOX_WIDTH))╗${NC}"
echo -e "${GREEN}║  Relay — Local Agent (Git Queue)$(printf ' %.0s' $(seq 1 20))║${NC}"
echo -e "${GREEN}╠$(printf '═%.0s' $(seq 1 $BOX_WIDTH))╣${NC}"

COLORS=("$BLUE" "$YELLOW" '\033[0;35m' '\033[0;36m')
for i in "${!REPO_NAMES[@]}"; do
  color="${COLORS[$((i % ${#COLORS[@]}))]}"
  name="${REPO_NAMES[$i]}"
  label="${name}/"
  printf -v line "  %b%s%b → watching for tasks" "$color" "$label" "$NC"
  visible="  ${label} → watching for tasks"
  pad=$(( BOX_WIDTH - ${#visible} ))
  (( pad < 0 )) && pad=0
  echo -e "${GREEN}║${NC}${line}$(printf ' %.0s' $(seq 1 $pad))${GREEN}║${NC}"
done

echo -e "${GREEN}║${NC}  Agents per repo: ${BLUE}${AGENTS_PER_REPO}${NC}$(printf ' %.0s' $(seq 1 $((BOX_WIDTH - 22))))${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Poll interval:   ${BLUE}${POLL_INTERVAL}s${NC}$(printf ' %.0s' $(seq 1 $((BOX_WIDTH - 23))))${GREEN}║${NC}"
echo -e "${GREEN}╠$(printf '═%.0s' $(seq 1 $BOX_WIDTH))╣${NC}"
echo -e "${GREEN}║${NC}  Press Ctrl+C to stop all agents$(printf ' %.0s' $(seq 1 $((BOX_WIDTH - 34))))${GREEN}║${NC}"
echo -e "${GREEN}╚$(printf '═%.0s' $(seq 1 $BOX_WIDTH))╝${NC}"
echo ""

# ── Queue Parsing ──────────────────────────────────────────────

parse_queue() {
  local target_repo="$1"
  local status_filter="$2"

  python3 "$SCRIPT_DIR/_parse-queue.py" \
    "$CP_DIR/queue" "$target_repo" \
    --status "$status_filter" \
    --execution "autonomous,supervised" 2>/dev/null \
  | python3 -c "
import json, sys
for c in json.load(sys.stdin):
    print(f\"{c['rank']} {c['wave']} {c['path']}\")
" 2>/dev/null
}

# ── Branch Helpers ─────────────────────────────────────────────

# ── Stale Claim Recovery ──────────────────────────────────────

reap_stale_claims() {
  local repo_dir="$1" repo_name="$2" repo_nwo="$3"
  local claimed_branches branch last_commit_epoch now_epoch age
  local STALE_THRESHOLD=300

  claimed_branches=$(get_claimed_branches "$repo_dir")
  if [ -z "$claimed_branches" ]; then
    return
  fi

  now_epoch=$(date +%s)

  while IFS= read -r branch; do
    [ -z "$branch" ] && continue

    last_commit_epoch=$(git -C "$repo_dir" log -1 --format='%ct' "origin/$branch" 2>/dev/null || echo "0")
    if [ "$last_commit_epoch" = "0" ]; then
      continue
    fi

    age=$((now_epoch - last_commit_epoch))
    if [ "$age" -lt "$STALE_THRESHOLD" ]; then
      continue
    fi

    local pr_count
    pr_count=$(gh pr list --repo "$repo_nwo" --head "$branch" --state open --json number --jq 'length' 2>/dev/null || echo "0")
    if [ "$pr_count" != "0" ]; then
      continue
    fi

    # Check if the task was claimed by this machine — if so, skip reaping (we'll resume it)
    local my_host skip_reap
    my_host=$(hostname -s 2>/dev/null || echo unknown)
    skip_reap=false
    for qfile in "$CP_DIR"/queue/*/*/wave-*.md; do
      [ -f "$qfile" ] || continue
      local derived
      derived=$(derive_branch_slug "$qfile" "$repo_name")
      if [ "$derived" = "$branch" ]; then
        local claimed_on
        claimed_on=$(grep '^claimed-on:' "$qfile" 2>/dev/null | sed 's/^claimed-on:[[:space:]]*//')
        if [ "$claimed_on" = "$my_host" ]; then
          skip_reap=true
        fi
        break
      fi
    done

    if [ "$skip_reap" = true ]; then
      continue
    fi

    log_warn "Reaping stale branch: $branch (age: ${age}s, no open PR)"
    git -C "$repo_dir" push origin --delete "$branch" 2>/dev/null || true

    for qfile in "$CP_DIR"/queue/*/*/wave-*.md; do
      [ -f "$qfile" ] || continue
      local derived
      derived=$(derive_branch_slug "$qfile" "$repo_name")
      if [ "$derived" = "$branch" ]; then
        update_task_status "$qfile" "ready"
        log "Reset $qfile to status: ready"
        break
      fi
    done
  done <<< "$claimed_branches"
}

# ── Claim Logic ────────────────────────────────────────────────

has_merged_pr() {
  local queue_file="$1" branch_slug="$2" repo_nwo="$3"

  local merged_count
  merged_count=$(gh pr list --repo "$repo_nwo" --head "$branch_slug" --state merged --json number --jq 'length' 2>/dev/null || echo "0")

  if [ "$merged_count" != "0" ]; then
    log_ok "PR already merged for $branch_slug — marking done"
    if queue_file=$(update_task_status "$queue_file" "done"); then
      git -C "$CP_DIR" add "$queue_file" 2>/dev/null
      git -C "$CP_DIR" commit -m "done: $(basename "$queue_file") (merged PR detected)" 2>/dev/null || true
      push_cp_with_retry || true
    else
      log_err "Failed to move task to done/ — filename may be too long"
    fi
    return 0
  fi
  return 1
}

# ── Merged PR Detection ────────────────────────────────────────────
# Like parse_queue() but without --execution filter, for PR reconciliation
parse_queue_all() {
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

# Scans all in-progress tasks with pr-number set and checks if the PR is merged.
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
      local _feat _wave_num
      _feat=$(feature_from_task_path "$queue_file")
      _wave_num=$(basename "$queue_file" | sed -n 's/^wave-\([0-9]*\)-.*/\1/p')
      if queue_file=$(update_task_status "$queue_file" "done"); then
        git -C "$CP_DIR" add "$queue_file" 2>/dev/null
        git -C "$CP_DIR" commit -m "done: $(basename "$queue_file") (PR #${pr_num} merged)" 2>/dev/null || true
        # Auto-promote next wave if this wave is now complete
        if [ -n "$_feat" ] && [ -n "$_wave_num" ]; then
          auto_promote_next_wave "$_feat" "$_wave_num"
        fi
        push_cp_with_retry || true
      else
        log_err "Failed to move task to done/ — filename may be too long"
      fi
    elif [ "$pr_state" = "CLOSED" ]; then
      log_warn "PR #${pr_num} closed without merge — marking blocked: $(basename "$queue_file")"
      if queue_file=$(update_task_status "$queue_file" "blocked"); then
        git -C "$CP_DIR" add "$queue_file" 2>/dev/null
        git -C "$CP_DIR" commit -m "blocked: $(basename "$queue_file") (PR #${pr_num} closed)" 2>/dev/null || true
        push_cp_with_retry || true
      else
        log_err "Failed to move task to blocked/ — filename may be too long"
      fi
    fi
  done <<< "$candidates"
}

claim_task() {
  local queue_file="$1" work_dir="$2" repo_name="$3"
  local branch_slug

  branch_slug=$(derive_branch_slug "$queue_file" "$repo_name")

  git -C "$work_dir" fetch origin main &>/dev/null || true
  # Ensure we're on a detached HEAD or main so we can delete stale local branches
  git -C "$work_dir" checkout --detach &>/dev/null || true
  git -C "$work_dir" branch -D "$branch_slug" &>/dev/null || true
  git -C "$work_dir" checkout -b "$branch_slug" origin/main &>/dev/null || return 1
  git -C "$work_dir" commit --allow-empty -m "claim: agent-$(hostname -s)-$$" &>/dev/null || return 1

  if git -C "$work_dir" push origin "$branch_slug" &>/dev/null; then
    if queue_file=$(update_task_status "$queue_file" "in-progress"); then
      set_task_claim "$queue_file" "agent-$(hostname -s)-$$" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(hostname -s 2>/dev/null || echo unknown)"
      git -C "$CP_DIR" add "$queue_file" &>/dev/null
      git -C "$CP_DIR" commit -m "claim: $(basename "$queue_file") → in-progress (agent-$(hostname -s)-$$)" &>/dev/null || true
      push_cp_with_retry >/dev/null || true
    else
      log_err "Failed to move task to in-progress/ — filename may be too long"
    fi
    # Echo the updated path so callers can capture it
    echo "$queue_file"
    return 0
  else
    git -C "$work_dir" checkout main &>/dev/null || git -C "$work_dir" checkout - &>/dev/null
    git -C "$work_dir" branch -D "$branch_slug" &>/dev/null
    return 1
  fi
}

# ── Auto-Resume ──────────────────────────────────────────────

try_resume_in_progress() {
  # Check for in-progress tasks claimed by this machine that can be resumed.
  # Returns "<queue_file> <branch_slug>" on success, or returns 1.
  local repo_dir="$1" repo_name="$2"
  local my_host
  my_host=$(hostname -s 2>/dev/null || echo unknown)

  local candidates
  candidates=$(parse_queue "$repo_name" "in-progress")
  [ -z "$candidates" ] && return 1

  while IFS=' ' read -r _rank _wave queue_file; do
    [ -z "$queue_file" ] && continue

    # Skip tasks that already have a PR — they're waiting for review, not stuck
    local has_pr
    has_pr=$(grep -c '^pr-number:' "$queue_file" 2>/dev/null || echo "0")
    if [ "$has_pr" != "0" ]; then
      local pr_val
      pr_val=$(grep '^pr-number:' "$queue_file" | sed 's/^pr-number:[[:space:]]*//')
      if [ -n "$pr_val" ] && [ "$pr_val" != "0" ]; then
        continue
      fi
    fi

    local claimed_on
    claimed_on=$(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    content = f.read()
m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
if m:
    for line in m.group(1).split('\n'):
        km = re.match(r'^claimed-on:\s*(.+)', line)
        if km: print(km.group(1).strip()); break
" "$queue_file" 2>/dev/null || true)

    if [ "$claimed_on" != "$my_host" ]; then
      continue
    fi

    local branch_slug
    branch_slug=$(derive_branch_slug "$queue_file" "$repo_name")

    # Check if branch still exists on remote
    if ! git -C "$repo_dir" ls-remote --heads origin "$branch_slug" 2>/dev/null | grep -q .; then
      continue
    fi

    echo "$queue_file $branch_slug"
    return 0
  done <<< "$candidates"

  return 1
}

resume_task() {
  # Checkout existing branch and re-run the agent on an in-progress task.
  local queue_file="$1" repo_dir="$2" branch_slug="$3" repo_name="$4"

  log "Resuming in-progress task: ${BOLD}$(basename "$queue_file")${NC}"

  git -C "$repo_dir" fetch origin "$branch_slug" 2>/dev/null || true
  git -C "$repo_dir" checkout --detach 2>/dev/null || true
  git -C "$repo_dir" branch -D "$branch_slug" 2>/dev/null || true
  git -C "$repo_dir" checkout -b "$branch_slug" "origin/$branch_slug" 2>/dev/null || {
    log_err "Could not checkout branch $branch_slug"
    return 1
  }

  log_ok "On branch: ${BLUE}$branch_slug${NC}"

  run_agent "$queue_file" "$repo_dir" "$branch_slug" "$repo_name"
}

# ── Agent Prompt Builder ──────────────────────────────────────

build_agent_prompt() {
  local queue_file="$1" branch_slug="$2" repo_name="$3"
  local task_body feature_slug wave contracts_line

  task_body=$(cat "$queue_file")

  feature_slug=$(echo "$task_body" | sed -n '/^---$/,/^---$/p' | grep '^feature:' | sed 's/^feature:[[:space:]]*//')
  wave=$(echo "$task_body" | sed -n '/^---$/,/^---$/p' | grep '^wave:' | sed 's/^wave:[[:space:]]*//')
  contracts_line=$(echo "$task_body" | sed -n '/^---$/,/^---$/p' | grep -A5 '^contracts:' | grep '^\s*-' | sed 's/^\s*-\s*//' | head -1)

  local contract_path=""
  if [ -n "$contracts_line" ]; then
    contract_path="$CP_DIR/$contracts_line"
  fi

  # Derive GitHub blob URL from .relay-config or git remote
  local github_control_plane_url cp_sha
  cp_sha=$(cp_head_sha)
  github_control_plane_url=$(relay_config "relay-nwo" 2>/dev/null || true)
  if [ -n "$github_control_plane_url" ]; then
    github_control_plane_url="https://github.com/${github_control_plane_url}/blob/${cp_sha}"
  else
    github_control_plane_url=$(git -C "$CP_DIR" remote get-url origin 2>/dev/null \
      | sed -E 's|.*github\.com[:/]||; s|\.git$||' || echo "")
    [ -n "$github_control_plane_url" ] && github_control_plane_url="https://github.com/${github_control_plane_url}/blob/${cp_sha}"
  fi

  local queue_rel_path="${queue_file#$CP_DIR/}"

  # Find feature spec path (search phase directories like wrap.sh)
  local feature_spec_rel=""
  for phase in draft active completed cancelled; do
    for suffix in feature bug; do
      if [ -f "$CP_DIR/features/${phase}/${feature_slug}-${suffix}.md" ]; then
        feature_spec_rel="features/${phase}/${feature_slug}-${suffix}.md"
        break 2
      fi
    done
  done
  [ -z "$feature_spec_rel" ] && feature_spec_rel="features/${feature_slug}.md"

  cat <<PROMPT
You are an Implementer Agent for the $repo_name repository.

TASK FILE: $queue_rel_path
BRANCH: $branch_slug
FEATURE: $feature_slug
WAVE: $wave

--- TASK CONTENT ---
$task_body
--- END TASK ---

CONSTITUTION: Read CLAUDE.md in this repo for coding conventions.

$([ -n "$contract_path" ] && echo "CONTRACT: The shared API contract is at $contract_path — your implementation must match it.")

INSTRUCTIONS:
1. You are already on branch $branch_slug with an empty claim commit.
2. Read CLAUDE.md and the contract to understand conventions and the API shape.
3. Implement using behavioral TDD:
   a. Read each GIVEN/WHEN/THEN scenario in the Acceptance Criteria
   b. Write one failing test per scenario (test name mirrors the scenario)
   c. Implement the minimum code to make each test pass
   d. Verify all Invariants (tests pass, contract-compliant)
4. After your FIRST real commit, amend away the empty claim commit:
   git rebase -i HEAD~2  (squash the claim into your first commit)
   OR: git reset --soft HEAD~2 && git commit -m "your message"
   Then: git push --force-with-lease origin $branch_slug
   This keeps the branch history clean.
5. Run tests after each change to verify nothing is broken.
6. When done, push and create a PR:
   git push origin $branch_slug
   gh pr create --title "[$feature_slug wave $wave] <description>" \\
     --body "\$(cat <<'EOF'
## Context
- **Feature Spec:** [$feature_slug]($github_control_plane_url/$feature_spec_rel)
- **Task:** [$(basename "$queue_file")]($github_control_plane_url/$queue_rel_path)
$([ -n "$contracts_line" ] && echo "- **Contract:** [$contracts_line]($github_control_plane_url/$contracts_line)")

## What this PR does
<description>

## Acceptance Criteria
<from task file>
EOF
)"

7. If you discover sub-work needed, create a new task file:
   Write a new wave file in $CP_DIR/queue/$feature_slug/ following the template.

IMPORTANT: Never commit directly to main.
IMPORTANT: Use behavioral TDD — one test per GIVEN/WHEN/THEN scenario, tests first.
IMPORTANT: Create ONE PR for this task.

TOOLS AVAILABLE:
- Bash, Edit, Read, Write, Glob, Grep (all file tools)
- Agent (to dispatch parallel subagents for independent sub-work)
- gh pr create (create PR when done)
- npm test (run tests)
PROMPT
}

# ── Agent Execution ───────────────────────────────────────────

resolve_budget() {
  local queue_file="$1"
  # Read budget from task frontmatter
  local budget budget_source=""
  budget=$(sed -n '/^---$/,/^---$/p' "$queue_file" | grep '^budget:' | sed 's/^budget:[[:space:]]*//' | tr -d '"' | sed 's/[[:space:]]*#.*//')
  if [ -n "$budget" ]; then
    budget_source="task"
  fi
  # Fall back to feature-level budget if task has none
  if [ -z "$budget" ]; then
    local feature_slug
    feature_slug=$(sed -n '/^---$/,/^---$/p' "$queue_file" | grep '^feature:' | sed 's/^feature:[[:space:]]*//')
    if [ -n "$feature_slug" ]; then
      local features_dir="$CP_DIR/features"
      local feature_file=""
      for phase in draft active completed cancelled; do
        for suffix in feature bug; do
          local candidate="$features_dir/$phase/${feature_slug}-${suffix}.md"
          if [ -f "$candidate" ]; then
            feature_file="$candidate"
            break 2
          fi
        done
      done
      if [ -n "$feature_file" ]; then
        budget=$(sed -n '/^---$/,/^---$/p' "$feature_file" | grep '^budget:' | sed 's/^budget:[[:space:]]*//' | tr -d '"' | sed 's/[[:space:]]*#.*//')
        if [ -n "$budget" ]; then
          budget_source="feature"
          log "Budget \$$budget from feature spec: $(basename "$feature_file")" >&2
        fi
      else
        log "No feature spec found for slug '$feature_slug' — cannot inherit budget" >&2
      fi
    fi
  fi
  echo "$budget"
}

is_budget_exceeded() {
  local cost_json="${1:-{\}}"
  python3 -c "
import json, sys
try:
    d = json.loads(sys.argv[1])
    sys.exit(0 if d.get('budget_exceeded') else 1)
except:
    sys.exit(1)
" "$cost_json" 2>/dev/null
}

persist_cost_fields() {
  local queue_file="$1" cost_json="$2"
  if [ -z "$cost_json" ] || [ "$cost_json" = "{}" ]; then
    return
  fi
  # Parse cost fields from JSON using python
  local cost_usd duration_ms input_tokens output_tokens
  eval "$(python3 -c "
import json, sys
d = json.loads(sys.argv[1])
print(f'cost_usd={d.get(\"cost_usd\", 0)}')
print(f'duration_ms={d.get(\"duration_ms\", 0)}')
print(f'input_tokens={d.get(\"input_tokens\", 0)}')
print(f'output_tokens={d.get(\"output_tokens\", 0)}')
" "$cost_json" 2>/dev/null)" || return

  # Update or insert frontmatter fields in the task file
  # Uses python to handle both existing fields (update) and missing fields (insert before closing ---)
  python3 -c "
import sys, re

queue_file = sys.argv[1]
updates = dict(zip(['cost-usd','input-tokens','output-tokens','duration-ms'], sys.argv[2:]))

with open(queue_file) as f:
    content = f.read()

# Parse frontmatter: split on first two '---' markers
parts = content.split('---', 2)
if len(parts) < 3:
    sys.exit(0)

fm = parts[1]
for key, val in updates.items():
    if re.search(rf'^{re.escape(key)}:', fm, re.MULTILINE):
        fm = re.sub(rf'^{re.escape(key)}:.*', f'{key}: {val}', fm, flags=re.MULTILINE)
    else:
        fm = fm.rstrip('\n') + f'\n{key}: {val}\n'

with open(queue_file, 'w') as f:
    f.write('---' + fm + '---' + parts[2])
" "$queue_file" "$cost_usd" "$input_tokens" "$output_tokens" "$duration_ms"
}

run_agent() {
  local queue_file="$1" work_dir="$2" branch_slug="$3" repo_name="$4"

  local prompt
  prompt=$(build_agent_prompt "$queue_file" "$branch_slug" "$repo_name")

  log "Running agent on $(basename "$queue_file") in $work_dir"

  # Resolve budget limit (task → feature → no limit)
  local budget
  budget=$(resolve_budget "$queue_file")

  # Apply feature total-budget envelope (remaining = total-budget - spent)
  local remaining
  remaining=$(resolve_remaining_budget "$queue_file")
  if [ -n "$remaining" ]; then
    # Check if feature budget is exhausted
    local is_exhausted
    is_exhausted=$(python3 -c "import sys; print('yes' if float(sys.argv[1]) <= 0 else 'no')" "$remaining" 2>/dev/null || echo "no")
    if [ "$is_exhausted" = "yes" ]; then
      log_err "Feature budget exhausted (remaining: \$$remaining) — blocking task"
      return 99
    fi
    # Effective budget = min(per-task budget, remaining envelope)
    if [ -n "$budget" ]; then
      budget=$(python3 -c "import sys; print(f'{min(float(sys.argv[1]), float(sys.argv[2])):.4f}')" "$budget" "$remaining" 2>/dev/null || echo "$budget")
    else
      budget="$remaining"
    fi
    log "Feature envelope remaining: \$$remaining"
  fi

  local budget_args=()
  if [ -n "$budget" ]; then
    budget_args=(--max-budget-usd "$budget")
    log "Budget limit: \$$budget"
  else
    log_warn "No budget constraint — agent will run uncapped"
  fi

  if [[ "$INTERACTIVE" == true ]]; then
    # Interactive mode: raw streaming output directly to the terminal
    (cd "$work_dir" && env -u CLAUDECODE claude -p \
      --allowedTools "Bash,Edit,Read,Write,Glob,Grep,Agent" \
      --model sonnet \
      --verbose \
      ${budget_args[@]+"${budget_args[@]}"} \
      "$prompt")
    local exit_code=$?
    # Interactive mode cannot capture exact cost from stream-json.
    # Record the budget limit as spent (conservative) so the feature
    # envelope is decremented and prevents infinite retries.
    if [ -n "$budget" ]; then
      AGENT_COST_JSON="{\"cost_usd\": $budget, \"duration_ms\": 0, \"input_tokens\": 0, \"output_tokens\": 0}"
    fi
    return $exit_code
  fi

  # Headless mode: stream-json piped through Python formatter
  local agent_stderr
  agent_stderr=$(mktemp)

  # Temp file for Python formatter to export cost data back to shell
  if [ -z "${_AGENT_COST_FILE:-}" ]; then
    _AGENT_COST_FILE=$(mktemp)
  fi
  export _AGENT_COST_FILE

  (cd "$work_dir" && env -u CLAUDECODE claude -p \
    --allowedTools "Bash,Edit,Read,Write,Glob,Grep,Agent" \
    --model sonnet \
    --verbose \
    ${budget_args[@]+"${budget_args[@]}"} \
    --output-format stream-json \
    "$prompt" 2>"$agent_stderr") | python3 -u -c "
import sys, json, os

YELLOW = '\033[1;33m'
GREEN = '\033[0;32m'
DIM = '\033[2m'
NC = '\033[0m'

def fmt(line):
    print(f'  {DIM}│{NC} {line}', flush=True)

last_text = ''
for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    try:
        obj = json.loads(raw)
    except:
        continue

    t = obj.get('type', '')

    if t == 'assistant':
        msg = obj.get('message', {})
        for block in msg.get('content', []):
            if block.get('type') == 'text':
                text = block['text']
                if text.startswith(last_text):
                    new = text[len(last_text):]
                else:
                    new = text
                last_text = text
                if new.strip():
                    for line in new.strip().split('\n'):
                        fmt(line)
            elif block.get('type') == 'tool_use':
                name = block.get('name', '')
                inp = block.get('input', {})
                if name == 'Agent':
                    desc = inp.get('description', '')
                    fmt(f'{YELLOW}>> Subagent: {desc}{NC}')
                elif name == 'Bash':
                    cmd = inp.get('command', '')[:100]
                    fmt(f'{YELLOW}$ {cmd}{NC}')
                elif name in ('Edit', 'Write'):
                    path = inp.get('file_path', '').split('/')[-1]
                    fmt(f'{YELLOW}» {name.lower()} {path}{NC}')
                elif name == 'Read':
                    path = inp.get('file_path', '').split('/')[-1]
                    fmt(f'{DIM}  read {path}{NC}')
                else:
                    fmt(f'{YELLOW}» {name}{NC}')
    elif t == 'result':
        cost = obj.get('total_cost_usd', 0) or obj.get('cost_usd', 0)
        duration = obj.get('duration_ms', 0)
        input_tokens = obj.get('usage', {}).get('input_tokens', 0)
        output_tokens = obj.get('usage', {}).get('output_tokens', 0)
        budget_exceeded = obj.get('subtype', '') == 'error_max_budget_usd'
        if budget_exceeded:
            RED = '\033[0;31m'
            fmt(f'{RED}BUDGET EXCEEDED ({duration/1000:.0f}s, \${cost:.4f}){NC}')
        else:
            fmt(f'{GREEN}Done ({duration/1000:.0f}s, \${cost:.4f}){NC}')
        # Export cost data for shell to read
        cost_file = os.environ.get('_AGENT_COST_FILE')
        if cost_file:
            try:
                with open(cost_file, 'w') as f:
                    json.dump({'cost_usd': cost, 'duration_ms': duration,
                               'input_tokens': input_tokens, 'output_tokens': output_tokens,
                               'budget_exceeded': budget_exceeded}, f)
            except:
                pass
"
  local agent_exit=${PIPESTATUS[0]}
  rm -f "$agent_stderr"

  # Read captured cost data
  AGENT_COST_JSON=$(cat "$_AGENT_COST_FILE" 2>/dev/null || echo "{}")
  rm -f "$_AGENT_COST_FILE"
  unset _AGENT_COST_FILE

  return $agent_exit
}

# ── Completion Handling ───────────────────────────────────────

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
    log_ok "PR #${pr_number} ready for review: ${pr_url}"
    log     "  → Review and merge the PR. The watcher will auto-detect the merge."

    # Send Slack notification (if configured)
    if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
      local task_feature pr_title acceptance
      task_feature=$(sed -n '/^---$/,/^---$/{ s/^feature:[[:space:]]*//p; }' "$queue_file" 2>/dev/null | head -1)
      local feature_title=""
      if [ -n "$task_feature" ]; then
        for phase in draft active completed cancelled; do
          for suffix in feature bug; do
            local _spec="${CP_DIR}/features/${phase}/${task_feature}-${suffix}.md"
            if [ -f "$_spec" ]; then
              feature_title=$(sed -n 's/^# \(Feature Spec\|Bug Report\): *//p' "$_spec" | head -1)
              break 2
            fi
          done
        done
      fi
      pr_title=$(gh pr view "$pr_number" --repo "$repo_nwo" --json title --jq '.title' 2>/dev/null || echo "PR #${pr_number}")
      acceptance=$(python3 -c "
import sys
in_ac = False
lines = []
for line in open(sys.argv[1]):
    if line.strip().startswith('## Acceptance'):
        in_ac = True; continue
    if in_ac and line.startswith('## '):
        break
    if in_ac:
        lines.append(line.rstrip())
print('\n'.join(lines).strip())
" "$queue_file" 2>/dev/null || true)
      python3 "$SCRIPT_DIR/slack_notify.py" pr-ready \
        --webhook-url "$SLACK_WEBHOOK_URL" \
        --repo "${target_repo:-unknown}" \
        --pr-url "$pr_url" \
        --pr-title "$pr_title" \
        --feature "${feature_title:-${task_feature:-}}" \
        --acceptance "${acceptance:-}" \
        2>/dev/null || true
    fi
  else
    # No PR found — mark blocked
    if queue_file=$(update_task_status "$queue_file" "blocked"); then
      git -C "$CP_DIR" add "$queue_file" 2>/dev/null
      git -C "$CP_DIR" commit -m "blocked: $(basename "$queue_file") (no PR found)" 2>/dev/null || true
      push_cp_with_retry || true
    else
      log_err "Failed to move task to blocked/ — filename may be too long"
    fi
    log_err "No PR found for branch $branch_slug — task marked blocked"
  fi

  # Generate handoff note
  if [ -n "$work_dir" ] && [ -n "$branch_slug" ]; then
    python3 "$SCRIPT_DIR/_handoff-note.py" "$queue_file" \
      --status "done" --work-dir "$work_dir" --branch "$branch_slug" \
      --cp-dir "$CP_DIR" --cost-json "$cost_json" 2>/dev/null || true
  fi
}

handle_failure() {
  local queue_file="$1" exit_code="$2" work_dir="${3:-}" branch_slug="${4:-}" cost_json="${5:-\{\}}"

  # Persist cost fields in task frontmatter (even on failure — the cost was still incurred)
  persist_cost_fields "$queue_file" "$cost_json"

  local commit_reason
  if [ "$exit_code" -eq 99 ]; then
    commit_reason="budget exceeded"
  else
    commit_reason="exit $exit_code"
  fi

  if queue_file=$(update_task_status "$queue_file" "blocked"); then
    git -C "$CP_DIR" add "$queue_file" 2>/dev/null
    git -C "$CP_DIR" commit -m "blocked: $(basename "$queue_file") ($commit_reason)" 2>/dev/null || true
  else
    log_err "Failed to move task to blocked/ — filename may be too long"
  fi
  push_cp_with_retry || true
  log_err "Task blocked: $(basename "$queue_file") ($commit_reason)"

  local retro_file="$CP_DIR/retrospectives/retro-log.md"
  if [ -f "$retro_file" ]; then
    local retro_date
    retro_date=$(date +%Y-%m-%d)
    cat >> "$retro_file" << RETRO_EOF

### ${retro_date} — Agent blocked: $(basename "$queue_file")

**Signal:** status:blocked
**Root Cause:** [TODO]
**Task File:** ${queue_file#$CP_DIR/}

**What happened:**
Agent failed: ${commit_reason}. [TODO: describe what went wrong]

**What would have prevented it:**
[TODO]

**Upstream fix applied:**
[TODO]
RETRO_EOF
    log "Retro stub appended to retrospectives/retro-log.md"
  fi

  # Generate handoff note for blocked task
  if [ -n "$work_dir" ] && [ -n "$branch_slug" ]; then
    python3 "$SCRIPT_DIR/_handoff-note.py" "$queue_file" \
      --status "blocked" --work-dir "$work_dir" --branch "$branch_slug" \
      --exit-code "$exit_code" --cp-dir "$CP_DIR" --cost-json "$cost_json" 2>/dev/null || true
  fi
}

# ── Worktree Management ───────────────────────────────────────

setup_worktree() {
  local repo_dir="$1" slot="$2"
  local worktree_path="$repo_dir/.worktrees/agent-${slot}"

  if [ ! -d "$worktree_path" ]; then
    git -C "$repo_dir" fetch origin main 2>/dev/null || true
    git -C "$repo_dir" worktree add "$worktree_path" origin/main --detach 2>/dev/null
  fi
  echo "$worktree_path"
}

cleanup_worktrees() {
  local repo_dir="$1"
  log "Cleaning up worktrees for $repo_dir..."
  git -C "$repo_dir" worktree prune 2>/dev/null || true
  rm -rf "$repo_dir/.worktrees" 2>/dev/null || true
}

# ── Watcher Loop (single repo) ────────────────────────────────

run_watcher() {
  local repo_dir="$1" repo_name="$2" num_agents="$3"

  repo_dir="$(cd "$repo_dir" && pwd)"
  _LOG_CONTEXT="$repo_name"
  local repo_nwo
  repo_nwo=$(git -C "$repo_dir" remote get-url origin 2>/dev/null | sed -E 's|.*github\.com[:/]||; s|\.git$||')
  if [ -z "$repo_nwo" ]; then
    log_err "Cannot determine GitHub repo from $repo_dir"
    return 1
  fi

  log "Agent watcher started. Polling every ${POLL_INTERVAL}s..."
  log "Repo: $repo_nwo ($repo_dir)"
  log "Agents: $num_agents"
  log "Waiting for tasks with status: ready..."
  echo ""

  if [ "$num_agents" -eq 1 ]; then
    # ── Single Agent Mode ────────────────────────────────────
    while true; do
      git -C "$CP_DIR" pull --ff-only 2>/dev/null || true
      git -C "$repo_dir" fetch origin 2>/dev/null || true
      check_merged_prs "$repo_name" "$repo_nwo"
      reap_stale_claims "$repo_dir" "$repo_name" "$repo_nwo"

      # Try to resume in-progress work from this machine before looking for new tasks
      local resume_info
      if resume_info=$(try_resume_in_progress "$repo_dir" "$repo_name"); then
        local resume_file resume_branch
        resume_file=$(echo "$resume_info" | cut -d' ' -f1)
        resume_branch=$(echo "$resume_info" | cut -d' ' -f2)

        log_ok "Found resumable task: $(basename "$resume_file")"
        AGENT_COST_JSON="{}"
        if resume_task "$resume_file" "$repo_dir" "$resume_branch" "$repo_name"; then
          if is_budget_exceeded "$AGENT_COST_JSON"; then
            log_err "Agent stopped: budget exceeded"
            handle_failure "$resume_file" 99 "$repo_dir" "$resume_branch" "$AGENT_COST_JSON"
          else
            handle_success "$resume_file" "$repo_dir" "$resume_branch" "$AGENT_COST_JSON"
          fi
        else
          handle_failure "$resume_file" "$?" "$repo_dir" "$resume_branch" "$AGENT_COST_JSON"
        fi
        continue
      fi

      CLAIMED=$(get_claimed_branches "$repo_dir")
      CANDIDATES=$(parse_queue "$repo_name" "ready")

      if [ -z "$CANDIDATES" ]; then
        sleep "$POLL_INTERVAL"
        continue
      fi

      CLAIMED_ONE=false
      while IFS=' ' read -r _rank _wave queue_file; do
        [ -z "$queue_file" ] && continue

        branch_slug=$(derive_branch_slug "$queue_file" "$repo_name")

        if echo "$CLAIMED" | grep -qF "$branch_slug"; then
          continue
        fi

        if has_merged_pr "$queue_file" "$branch_slug" "$repo_nwo"; then
          CLAIMED_ONE=true
          break
        fi

        log_warn "Attempting to claim: $(basename "$queue_file")"

        local claimed_path
        if claimed_path=$(claim_task "$queue_file" "$repo_dir" "$repo_name"); then
          queue_file="$claimed_path"
          log_ok "Claimed: $(basename "$queue_file") → $branch_slug"
          echo ""

          AGENT_COST_JSON="{}"
          if run_agent "$queue_file" "$repo_dir" "$branch_slug" "$repo_name"; then
            if is_budget_exceeded "$AGENT_COST_JSON"; then
              log_err "Agent stopped: budget exceeded"
              handle_failure "$queue_file" 99 "$repo_dir" "$branch_slug" "$AGENT_COST_JSON"
            else
              handle_success "$queue_file" "$repo_dir" "$branch_slug" "$AGENT_COST_JSON"
            fi
          else
            handle_failure "$queue_file" "$?" "$repo_dir" "$branch_slug" "$AGENT_COST_JSON"
          fi

          echo ""
          log "Checking for more work..."
          echo ""
          CLAIMED_ONE=true
          break
        else
          log "Claim failed (another agent got it): $(basename "$queue_file")"
        fi
      done <<< "$CANDIDATES"

      if [ "$CLAIMED_ONE" = false ]; then
        sleep "$POLL_INTERVAL"
      fi
    done
  else
    # ── Multi-Agent Mode (worktrees) ─────────────────────────
    # Use eval-based slot variables for bash 3.2 compat (no declare -A)
    _slot_get() { eval "echo \"\${SLOT_${1}_${2}:-}\""; }
    _slot_set() { eval "SLOT_${1}_${2}=\"\$3\""; }

    cleanup_on_exit() {
      log "Shutting down agents..."
      for slot in $(seq 1 "$num_agents"); do
        local pid
        pid=$(_slot_get PIDS "$slot")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
          kill "$pid" 2>/dev/null || true
        fi
      done
      wait 2>/dev/null || true
      cleanup_worktrees "$repo_dir"
    }
    trap cleanup_on_exit INT TERM EXIT

    for slot in $(seq 1 "$num_agents"); do
      _slot_set PIDS "$slot" ""
      _slot_set FILES "$slot" ""
      _slot_set DIRS "$slot" ""
      _slot_set BRANCHES "$slot" ""
    done

    while true; do
      git -C "$CP_DIR" pull --ff-only 2>/dev/null || true

      for slot in $(seq 1 "$num_agents"); do
        local pid
        pid=$(_slot_get PIDS "$slot")
        if [ -n "$pid" ]; then
          if ! kill -0 "$pid" 2>/dev/null; then
            wait "$pid" 2>/dev/null
            local exit_code=$?
            local qfile
            qfile=$(_slot_get FILES "$slot")

            local wt_dir
            wt_dir=$(_slot_get DIRS "$slot")
            local slot_branch
            slot_branch=$(_slot_get BRANCHES "$slot")

            # Read cost data written by the background run_agent process
            local slot_cost
            slot_cost=$(cat "/tmp/_relay_agent_cost_slot${slot}.json" 2>/dev/null || echo "{}")
            rm -f "/tmp/_relay_agent_cost_slot${slot}.json"

            if [ "$exit_code" -eq 0 ] && is_budget_exceeded "$slot_cost"; then
              log_err "Slot $slot: Agent stopped — budget exceeded"
              handle_failure "$qfile" 99 "$wt_dir" "$slot_branch" "$slot_cost"
            elif [ "$exit_code" -eq 0 ]; then
              handle_success "$qfile" "$wt_dir" "$slot_branch" "$slot_cost"
            else
              handle_failure "$qfile" "$exit_code" "$wt_dir" "$slot_branch" "$slot_cost"
            fi

            git -C "$repo_dir" worktree remove "$wt_dir" --force 2>/dev/null || true

            _slot_set PIDS "$slot" ""
            _slot_set FILES "$slot" ""
            _slot_set DIRS "$slot" ""
            _slot_set BRANCHES "$slot" ""
          fi
        fi
      done

      git -C "$repo_dir" fetch origin 2>/dev/null || true
      check_merged_prs "$repo_name" "$repo_nwo"
      reap_stale_claims "$repo_dir" "$repo_name" "$repo_nwo"

      for slot in $(seq 1 "$num_agents"); do
        local slot_pid
        slot_pid=$(_slot_get PIDS "$slot")
        if [ -n "$slot_pid" ]; then
          continue
        fi

        CLAIMED=$(get_claimed_branches "$repo_dir")
        CANDIDATES=$(parse_queue "$repo_name" "ready")

        if [ -z "$CANDIDATES" ]; then
          break
        fi

        while IFS=' ' read -r _rank _wave queue_file; do
          [ -z "$queue_file" ] && continue

          branch_slug=$(derive_branch_slug "$queue_file" "$repo_name")

          if echo "$CLAIMED" | grep -qF "$branch_slug"; then
            continue
          fi

          if has_merged_pr "$queue_file" "$branch_slug" "$repo_nwo"; then
            break
          fi

          local wt_dir
          wt_dir=$(setup_worktree "$repo_dir" "$slot")

          log_warn "Slot $slot: Attempting to claim $(basename "$queue_file")"

          local claimed_path
          if claimed_path=$(claim_task "$queue_file" "$wt_dir" "$repo_name"); then
            queue_file="$claimed_path"
            log_ok "Slot $slot: Claimed $(basename "$queue_file") → $branch_slug"

            _AGENT_COST_FILE="/tmp/_relay_agent_cost_slot${slot}.json" \
              run_agent "$queue_file" "$wt_dir" "$branch_slug" "$repo_name" &
            _slot_set PIDS "$slot" "$!"
            _slot_set FILES "$slot" "$queue_file"
            _slot_set DIRS "$slot" "$wt_dir"
            _slot_set BRANCHES "$slot" "$branch_slug"
            break
          else
            log "Slot $slot: Claim failed for $(basename "$queue_file")"
            git -C "$repo_dir" worktree remove "$wt_dir" --force 2>/dev/null || true
          fi
        done <<< "$CANDIDATES"
      done

      sleep "$POLL_INTERVAL"
    done
  fi
}

# ── Main: launch watchers ─────────────────────────────────────

PIDS=()

cleanup() {
  echo ""
  echo -e "${YELLOW}Stopping agent watchers...${NC}"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait "${PIDS[@]}" 2>/dev/null || true

  if [ "$AGENTS_PER_REPO" -gt 1 ]; then
    echo -e "${YELLOW}Pruning worktrees...${NC}"
    for repo_path in "${REPO_PATHS[@]}"; do
      git -C "$repo_path" worktree prune 2>/dev/null || true
      rm -rf "$repo_path/.worktrees" 2>/dev/null || true
    done
  fi

  echo -e "${GREEN}All agents stopped.${NC}"
  exit 0
}
trap cleanup INT TERM

for i in "${!REPO_NAMES[@]}"; do
  run_watcher "${REPO_PATHS[$i]}" "${REPO_NAMES[$i]}" "$AGENTS_PER_REPO" &
  PIDS+=($!)
done

wait "${PIDS[@]}"
