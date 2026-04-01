#!/usr/bin/env bash
set -euo pipefail

# Feature Lifecycle Manager — pause, cancel, resume, replan, complete, or check status of a feature.
#
# Usage: feature-lifecycle.sh [--cp-dir <path>] <command> <feature-name> [--reason "..."]
#
# Commands:
#   status   — Show lifecycle state and task/PR summary
#   pause    — Stop new work, let in-flight finish
#   resume   — Unpause, restore paused tasks to ready
#   cancel   — Abandon feature, close PRs, cancel tasks
#   replan   — Pause + set up for re-architecture
#   complete — Mark feature done, archive queue

# ── Parse --cp-dir first (before positional args) ────────────
POSITIONAL=()
REASON=""
FORCE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir)
      export CP_DIR="$2"
      shift 2
      ;;
    --reason)
      REASON="$2"
      shift 2
      ;;
    --force)
      FORCE=true
      shift
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

# Source shared library
source "$(dirname "$0")/_lib.sh"

# Validate CP_DIR
if [ -z "${CP_DIR:-}" ]; then
  echo -e "${RED}Error: CP_DIR not set. Use --cp-dir or run from a control plane.${NC}" >&2
  exit 1
fi

# ── Argument Parsing ──────────────────────────────────────────

COMMAND="${POSITIONAL[0]:-}"
FEATURE="${POSITIONAL[1]:-}"

if [ -z "$COMMAND" ] || [ -z "$FEATURE" ]; then
  echo "Usage: feature-lifecycle.sh [--cp-dir <path>] <command> <feature-name> [--reason \"...\"]"
  echo ""
  echo "Commands: status, pause, resume, cancel, replan, complete"
  exit 1
fi

# ── Path Resolution ───────────────────────────────────────────

QUEUE_DIR="$CP_DIR/queue/${FEATURE}"

# Find feature spec across phase directories
FEATURE_FILE=$(find_feature_file "$FEATURE")
if [ -z "$FEATURE_FILE" ] || [ ! -f "$FEATURE_FILE" ]; then
  echo -e "${RED}Error: No feature spec or bug report found for: ${FEATURE}${NC}"
  echo -e "${DIM}Looked in: features/{draft,active,...}/ and bugs/{draft,active,...}/${NC}"
  exit 1
fi

# Determine artifact type from filename
if [[ "$FEATURE_FILE" == *-bug.md ]]; then
  ARTIFACT_TYPE="bug"
else
  ARTIFACT_TYPE="feature"
fi

# ── Frontmatter & task helpers from _lib.sh ──────────────────
# get_feature_field, set_feature_field, count_tasks_by_status
# are now provided by _lib.sh (requires FEATURE_FILE / QUEUE_DIR to be set).

# ── Task File Helpers ────────────────────────────────────────

update_tasks_status() {
  # Move tasks from one status directory to another
  local from_status="$1"
  local to_status="$2"
  local changed=0

  local from_dir="$QUEUE_DIR/$from_status"
  if [ -d "$from_dir" ]; then
    for f in "$from_dir"/wave-*.md; do
      [ -f "$f" ] || continue
      update_task_status "$f" "$to_status" >/dev/null
      changed=$((changed + 1))
    done
  fi

  echo "$changed"
}

# ── Git Helpers ──────────────────────────────────────────────

git_commit_and_push() {
  local message="$1"
  git -C "$CP_DIR" add -A 2>/dev/null
  git -C "$CP_DIR" commit -m "$message" 2>/dev/null || true
  git -C "$CP_DIR" push 2>/dev/null || true
}

# ── PR/Branch Helpers ────────────────────────────────────────

get_target_repos() {
  # Extract unique target-repo values from queue task files
  if [ ! -d "$QUEUE_DIR" ]; then
    return
  fi
  for f in "$QUEUE_DIR"/*/wave-*.md; do
    [ -f "$f" ] || continue
    grep "^target-repo:" "$f" | sed 's/^target-repo:[[:space:]]*//'
  done | sort -u
}

get_repo_nwo() {
  # Map repo name to GitHub NWO using shared service catalog parser
  local repo_name="$1"
  parse_service_catalog "$CP_DIR/.relay/service-catalog.md" | while IFS='|' read -r name nwo _path; do
    if [ "$name" = "$repo_name" ]; then
      echo "$nwo"
      return 0
    fi
  done
}

close_feature_prs() {
  # Close open PRs matching agent/<feature>-* or fix/<feature>-* branches across target repos
  local closed=0
  local prefixes=("agent")
  [ "$ARTIFACT_TYPE" = "bug" ] && prefixes+=("fix")

  for repo_name in $(get_target_repos); do
    local nwo
    nwo=$(get_repo_nwo "$repo_name")
    [ -z "$nwo" ] && continue

    for prefix in "${prefixes[@]}"; do
      local prs
      prs=$(gh pr list --repo "$nwo" --state open --json number,headRefName \
        --jq ".[] | select(.headRefName | startswith(\"${prefix}/${FEATURE}-\")) | .number" 2>/dev/null || true)

      for pr_num in $prs; do
        echo -e "  ${YELLOW}Closing PR #${pr_num} on ${nwo}${NC}"
        gh pr close "$pr_num" --repo "$nwo" --comment "Closed by feature lifecycle: ${COMMAND}" 2>/dev/null || true
        closed=$((closed + 1))
      done
    done
  done
  echo "$closed"
}

delete_unclaimed_branches() {
  # Delete agent/<feature>-* and fix/<feature>-* branches that have no open or merged PR
  local deleted=0
  local prefixes=("agent")
  [ "$ARTIFACT_TYPE" = "bug" ] && prefixes+=("fix")

  for repo_name in $(get_target_repos); do
    local nwo
    nwo=$(get_repo_nwo "$repo_name")
    [ -z "$nwo" ] && continue

    for prefix in "${prefixes[@]}"; do
      local branches
      branches=$(gh api "repos/${nwo}/git/matching-refs/heads/${prefix}/${FEATURE}-" \
        --jq '.[].ref' 2>/dev/null | sed 's|refs/heads/||' || true)

      for branch in $branches; do
        [ -z "$branch" ] && continue
        local pr_count
        pr_count=$(gh pr list --repo "$nwo" --head "$branch" --state all --json number --jq 'length' 2>/dev/null || echo "0")
        if [ "$pr_count" = "0" ]; then
          echo -e "  ${DIM}Deleting unclaimed branch: ${branch} on ${nwo}${NC}"
          gh api -X DELETE "repos/${nwo}/git/refs/heads/${branch}" 2>/dev/null || true
          deleted=$((deleted + 1))
        fi
      done
    done
  done
  echo "$deleted"
}

delete_remote_feature_branches() {
  # Delete all agent/<feature>-* and fix/<feature>-* remote branches.
  # Safe to call after validate_prs_merged() confirms all PRs are merged.
  local deleted=0
  local prefixes=("agent")
  [ "$ARTIFACT_TYPE" = "bug" ] && prefixes+=("fix")

  for repo_name in $(get_target_repos); do
    local nwo
    nwo=$(get_repo_nwo "$repo_name")
    [ -z "$nwo" ] && continue

    for prefix in "${prefixes[@]}"; do
      local branches
      branches=$(gh api "repos/${nwo}/git/matching-refs/heads/${prefix}/${FEATURE}-" \
        --jq '.[].ref' 2>/dev/null | sed 's|refs/heads/||' || true)

      for branch in $branches; do
        [ -z "$branch" ] && continue
        echo -e "  ${DIM}Deleting remote branch: ${branch} on ${nwo}${NC}"
        gh api -X DELETE "repos/${nwo}/git/refs/heads/${branch}" 2>/dev/null || true
        deleted=$((deleted + 1))
      done
    done
  done
  echo "$deleted"
}

validate_prs_merged() {
  # Verify all task PRs are in MERGED state. Returns 0 if all merged, 1 otherwise.
  # Outputs merged count on stdout; details of unmerged PRs on stderr.
  local unmerged=0 merged=0 open_prs="" closed_prs=""

  if [ ! -d "$QUEUE_DIR" ]; then
    echo "0"
    return 0
  fi

  for f in "$QUEUE_DIR"/*/wave-*.md; do
    [ -f "$f" ] || continue
    local pr_num
    pr_num=$(get_task_pr_number "$f")
    [ -z "$pr_num" ] && continue

    local repo_name
    repo_name=$(sed -n '/^---$/,/^---$/{ s/^target-repo:[[:space:]]*//p; }' "$f" | head -1)
    [ -z "$repo_name" ] && continue

    local nwo
    nwo=$(get_repo_nwo "$repo_name")
    [ -z "$nwo" ] && continue

    local state
    state=$(gh pr view "$pr_num" --repo "$nwo" --json state --jq '.state' 2>/dev/null || echo "UNKNOWN")

    case "$state" in
      MERGED) merged=$((merged + 1)) ;;
      OPEN)   unmerged=$((unmerged + 1)); open_prs="${open_prs}  PR #${pr_num} on ${nwo} (OPEN)\n" ;;
      CLOSED) unmerged=$((unmerged + 1)); closed_prs="${closed_prs}  PR #${pr_num} on ${nwo} (CLOSED without merge)\n" ;;
      *)      unmerged=$((unmerged + 1)); open_prs="${open_prs}  PR #${pr_num} on ${nwo} (${state})\n" ;;
    esac
  done

  if [ "$unmerged" -gt 0 ]; then
    echo -e "${RED}Error: ${unmerged} PR(s) not merged:${NC}" >&2
    [ -n "$open_prs" ] && echo -e "$open_prs" >&2
    [ -n "$closed_prs" ] && echo -e "$closed_prs" >&2
    return 1
  fi
  echo "$merged"
  return 0
}

delete_local_branches() {
  # Delete local agent/<feature>-* and fix/<feature>-* branches from target repo clones
  local deleted=0
  local prefixes=("agent")
  [ "$ARTIFACT_TYPE" = "bug" ] && prefixes+=("fix")

  for repo_name in $(get_target_repos); do
    local local_path=""
    while IFS='|' read -r _name _nwo _local; do
      if [ "$_name" = "$repo_name" ]; then
        local_path="$_local"
        break
      fi
    done < <(parse_service_catalog "$CP_DIR/.relay/service-catalog.md")

    [ -z "$local_path" ] || [ ! -d "$local_path/.git" ] && continue

    for prefix in "${prefixes[@]}"; do
      local branches
      branches=$(git -C "$local_path" branch --list "${prefix}/${FEATURE}-*" 2>/dev/null | sed 's/^[* ]*//')

      for branch in $branches; do
        [ -z "$branch" ] && continue
        local current
        current=$(git -C "$local_path" rev-parse --abbrev-ref HEAD 2>/dev/null)
        if [ "$branch" = "$current" ]; then
          echo -e "  ${YELLOW}Skipping local branch (currently checked out): ${branch}${NC}"
          continue
        fi
        echo -e "  ${DIM}Deleting local branch: ${branch} in ${repo_name}${NC}"
        git -C "$local_path" branch -d "$branch" 2>/dev/null \
          || git -C "$local_path" branch -D "$branch" 2>/dev/null || true
        deleted=$((deleted + 1))
      done
    done
  done
  echo "$deleted"
}

warn_merged_prs() {
  # Warn about already-merged PRs that cannot be auto-reverted
  local prefixes=("agent")
  [ "$ARTIFACT_TYPE" = "bug" ] && prefixes+=("fix")

  for repo_name in $(get_target_repos); do
    local nwo
    nwo=$(get_repo_nwo "$repo_name")
    [ -z "$nwo" ] && continue

    for prefix in "${prefixes[@]}"; do
      local merged_prs
      merged_prs=$(gh pr list --repo "$nwo" --state merged --json number,headRefName \
        --jq ".[] | select(.headRefName | startswith(\"${prefix}/${FEATURE}-\")) | \"#\\(.number) (\\(.headRefName))\"" 2>/dev/null || true)

      if [ -n "$merged_prs" ]; then
        echo -e "  ${YELLOW}Warning: Already-merged PRs on ${nwo} (manual revert if needed):${NC}"
        echo "$merged_prs" | while read -r line; do
          echo -e "    ${DIM}${line}${NC}"
        done
      fi
    done
  done
}

# ── Commands ─────────────────────────────────────────────────

cmd_status() {
  local lifecycle
  lifecycle=$(get_feature_field "lifecycle")
  local version
  version=$(get_feature_field "version")

  local label="Feature"
  [ "$ARTIFACT_TYPE" = "bug" ] && label="Bug Report"
  echo -e "${BOLD}${label}: ${FEATURE}${NC}"
  echo -e "Lifecycle: ${BLUE}${lifecycle:-unknown}${NC}  Version: ${version:-1}"

  local paused_at
  paused_at=$(get_feature_field "paused-at")
  if [ -n "$paused_at" ] && [ "$paused_at" != '""' ]; then
    local paused_by
    paused_by=$(get_feature_field "paused-by")
    local pause_reason
    pause_reason=$(get_feature_field "pause-reason")
    echo -e "Paused at: ${paused_at}  By: ${paused_by}"
    [ -n "$pause_reason" ] && [ "$pause_reason" != '""' ] && echo -e "Reason: ${pause_reason}"
  fi

  if [[ "$lifecycle" == "live-dev" || "$lifecycle" == "live-staging" || "$lifecycle" == "live-prod" ]]; then
    local deployed_at deployed_env
    deployed_at=$(get_feature_field "deployed-at")
    deployed_env=$(get_feature_field "deployed-env")
    echo -e "Deployed: ${deployed_env} at ${deployed_at}"
  fi

  echo ""
  echo -e "${BOLD}Task Status:${NC}"

  if [ ! -d "$QUEUE_DIR" ]; then
    echo "  No queue directory found."
  else
    for status in pending ready in-progress done blocked paused cancelled; do
      local count
      count=$(count_tasks_by_status "$status")
      if [ "$count" -gt 0 ]; then
        echo -e "  ${status}: ${count}"
      fi
    done
  fi

  echo ""
  echo -e "${BOLD}PRs:${NC}"
  local pr_prefixes=("agent")
  [ "$ARTIFACT_TYPE" = "bug" ] && pr_prefixes+=("fix")

  for repo_name in $(get_target_repos); do
    local nwo
    nwo=$(get_repo_nwo "$repo_name")
    [ -z "$nwo" ] && continue

    local open_count=0 merged_count=0
    for prefix in "${pr_prefixes[@]}"; do
      local o m
      o=$(gh pr list --repo "$nwo" --state open --json headRefName \
        --jq "[.[] | select(.headRefName | startswith(\"${prefix}/${FEATURE}-\"))] | length" 2>/dev/null || echo "0")
      m=$(gh pr list --repo "$nwo" --state merged --json headRefName \
        --jq "[.[] | select(.headRefName | startswith(\"${prefix}/${FEATURE}-\"))] | length" 2>/dev/null || echo "0")
      open_count=$((open_count + o))
      merged_count=$((merged_count + m))
    done
    echo -e "  ${repo_name}: ${open_count} open, ${merged_count} merged"
  done
}

cmd_pause() {
  local lifecycle
  lifecycle=$(get_feature_field "lifecycle")

  if [[ "$lifecycle" != "active" && "$lifecycle" != live-* ]]; then
    echo -e "${RED}Error: Can only pause an active or live feature (current: ${lifecycle})${NC}"
    exit 1
  fi

  echo -e "${YELLOW}Pausing feature: ${FEATURE}${NC}"

  # Update feature frontmatter
  set_feature_field "lifecycle" "paused"
  set_feature_field "paused-at" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  set_feature_field "paused-by" "$(whoami)"
  [ -n "$REASON" ] && set_feature_field "pause-reason" "$REASON"

  # Pause ready/pending tasks
  local paused_ready paused_pending
  paused_ready=$(update_tasks_status "ready" "paused")
  paused_pending=$(update_tasks_status "pending" "paused")

  local in_progress done_count
  in_progress=$(count_tasks_by_status "in-progress")
  done_count=$(count_tasks_by_status "done")

  git_commit_and_push "lifecycle: pause ${FEATURE}$([ -n "$REASON" ] && echo " — ${REASON}")"

  echo -e "${GREEN}Paused.${NC}"
  echo -e "  Tasks paused: $((paused_ready + paused_pending)) (${paused_ready} ready, ${paused_pending} pending)"
  echo -e "  Still in-progress: ${in_progress} (will finish naturally)"
  echo -e "  Already done: ${done_count}"
  echo ""
  echo -e "  ${DIM}Next:${NC} ${BOLD}relay manage resume ${FEATURE}${NC} ${DIM}to restart, or${NC} ${BOLD}relay manage replan ${FEATURE}${NC} ${DIM}to re-architect.${NC}"
}

cmd_resume() {
  local lifecycle
  lifecycle=$(get_feature_field "lifecycle")

  if [ "$lifecycle" != "paused" ]; then
    echo -e "${RED}Error: Can only resume a paused feature (current: ${lifecycle})${NC}"
    exit 1
  fi

  echo -e "${GREEN}Resuming feature: ${FEATURE}${NC}"

  # Update feature frontmatter
  set_feature_field "lifecycle" "active"
  set_feature_field "paused-at" ""
  set_feature_field "paused-by" ""
  set_feature_field "pause-reason" ""

  # Restore paused tasks to ready
  local restored
  restored=$(update_tasks_status "paused" "ready")

  git_commit_and_push "lifecycle: resume ${FEATURE}"

  echo -e "${GREEN}Resumed.${NC}"
  echo -e "  Tasks restored to ready: ${restored}"
  echo ""
  echo -e "  ${DIM}Next:${NC} ${BOLD}relay check ${FEATURE}${NC} ${DIM}to see task status, or${NC} ${BOLD}relay next${NC} ${DIM}for guidance.${NC}"
}

cmd_cancel() {
  local lifecycle
  lifecycle=$(get_feature_field "lifecycle")

  if [ "$lifecycle" = "cancelled" ] || [ "$lifecycle" = "completed" ]; then
    echo -e "${RED}Error: Feature is already ${lifecycle}${NC}"
    exit 1
  fi

  echo -e "${RED}Cancelling feature: ${FEATURE}${NC}"

  # Update feature frontmatter and move to cancelled/ phase
  set_feature_field "cancelled-at" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  set_feature_field "lifecycle" "cancelled"
  FEATURE_FILE=$(update_feature_phase "$FEATURE_FILE" "cancelled")

  # Cancel non-done tasks
  local cancelled_ready cancelled_pending cancelled_paused cancelled_inprog
  cancelled_ready=$(update_tasks_status "ready" "cancelled")
  cancelled_pending=$(update_tasks_status "pending" "cancelled")
  cancelled_paused=$(update_tasks_status "paused" "cancelled")
  cancelled_inprog=$(update_tasks_status "in-progress" "cancelled")

  local total_cancelled=$((cancelled_ready + cancelled_pending + cancelled_paused + cancelled_inprog))

  # Close open PRs
  echo -e "\n${BOLD}Closing open PRs...${NC}"
  local closed_prs
  closed_prs=$(close_feature_prs)

  # Delete unclaimed branches
  echo -e "\n${BOLD}Cleaning up unclaimed branches...${NC}"
  local deleted_branches
  deleted_branches=$(delete_unclaimed_branches)

  # Warn about merged PRs
  echo ""
  warn_merged_prs

  git_commit_and_push "lifecycle: cancel ${FEATURE}$([ -n "$REASON" ] && echo " — ${REASON}")"

  echo -e "\n${RED}Cancelled.${NC}"
  echo -e "  Tasks cancelled: ${total_cancelled}"
  echo -e "  PRs closed: ${closed_prs}"
  echo -e "  Branches deleted: ${deleted_branches}"
  echo ""
  echo -e "  ${DIM}Next:${NC} ${BOLD}relay new${NC} ${DIM}to start a new feature, or${NC} ${BOLD}relay check${NC} ${DIM}to see remaining work.${NC}"
}

cmd_replan() {
  local lifecycle
  lifecycle=$(get_feature_field "lifecycle")

  if [ "$lifecycle" = "cancelled" ] || [ "$lifecycle" = "completed" ]; then
    echo -e "${RED}Error: Cannot replan a ${lifecycle} feature${NC}"
    exit 1
  fi

  echo -e "${BLUE}Replanning feature: ${FEATURE}${NC}"

  # Increment version
  local current_version
  current_version=$(get_feature_field "version")
  local new_version=$(( ${current_version:-1} + 1 ))

  # Update feature frontmatter
  set_feature_field "lifecycle" "replanning"
  set_feature_field "version" "$new_version"
  set_feature_field "paused-at" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  set_feature_field "paused-by" "$(whoami)"
  [ -n "$REASON" ] && set_feature_field "pause-reason" "$REASON"

  # Pause non-done tasks
  local paused_ready paused_pending paused_inprog
  paused_ready=$(update_tasks_status "ready" "paused")
  paused_pending=$(update_tasks_status "pending" "paused")
  paused_inprog=$(update_tasks_status "in-progress" "paused")

  # Close open PRs
  echo -e "\n${BOLD}Closing open PRs...${NC}"
  local closed_prs
  closed_prs=$(close_feature_prs)

  # Generate replan document
  mkdir -p "$QUEUE_DIR"
  local replan_file="$QUEUE_DIR/_replan-v${new_version}.md"
  echo -e "\n${BOLD}Generating replan document...${NC}"

  {
    echo "# Replan v${new_version}: ${FEATURE}"
    echo ""
    echo "**Triggered:** $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "**By:** $(whoami)"
    [ -n "$REASON" ] && echo "**Reason:** ${REASON}"
    echo ""
    echo "## Completed Work"
    echo ""
    echo "| Task | Wave | Repo | PR | Merged |"
    echo "|------|------|------|----|--------|"

    if [ -d "$QUEUE_DIR" ]; then
      for f in "$QUEUE_DIR"/*/wave-*.md; do
        [ -f "$f" ] || continue
        local task_st
        task_st=$(status_from_path "$f")
        if [ "$task_st" = "done" ]; then
          local fname wave repo
          fname=$(basename "$f" .md)
          wave=$(grep "^wave:" "$f" | sed 's/^wave:[[:space:]]*//')
          repo=$(grep "^target-repo:" "$f" | sed 's/^target-repo:[[:space:]]*//')
          echo "| ${fname} | ${wave} | ${repo} | — | — |"
        fi
      done
    fi

    echo ""
    echo "## Cancelled/Paused Work"
    echo ""
    echo "| Task | Wave | Repo | Previous Status |"
    echo "|------|------|------|-----------------|"

    if [ -d "$QUEUE_DIR" ]; then
      for f in "$QUEUE_DIR"/*/wave-*.md; do
        [ -f "$f" ] || continue
        local task_st
        task_st=$(status_from_path "$f")
        if [ "$task_st" = "paused" ] || [ "$task_st" = "cancelled" ]; then
          local fname wave repo
          fname=$(basename "$f" .md)
          wave=$(grep "^wave:" "$f" | sed 's/^wave:[[:space:]]*//')
          repo=$(grep "^target-repo:" "$f" | sed 's/^target-repo:[[:space:]]*//')
          echo "| ${fname} | ${wave} | ${repo} | ${task_st} |"
        fi
      done
    fi

    echo ""
    echo "## Instructions for Architect"
    echo ""
    echo "This feature is being replanned. When creating new tasks:"
    echo ""

    # Find the highest existing wave number
    local max_wave=0
    if [ -d "$QUEUE_DIR" ]; then
      for f in "$QUEUE_DIR"/*/wave-*.md; do
        [ -f "$f" ] || continue
        local w
        w=$(grep "^wave:" "$f" | sed 's/^wave:[[:space:]]*//')
        if [ "${w:-0}" -gt "$max_wave" ]; then
          max_wave="$w"
        fi
      done
    fi

    echo "1. **Start new tasks at wave $((max_wave + 1))** — preserves audit trail, avoids filename collisions"
    echo "2. Build on the merged state from completed work above"
    echo "3. Reference this replan document in the AgDR"
    echo "4. After creating new tasks, update feature lifecycle to \`active\`"
  } > "$replan_file"

  git_commit_and_push "lifecycle: replan ${FEATURE} v${new_version}$([ -n "$REASON" ] && echo " — ${REASON}")"

  echo -e "\n${BLUE}Replanning initiated.${NC}"
  echo -e "  Version: ${new_version}"
  echo -e "  Tasks paused: $((paused_ready + paused_pending + paused_inprog))"
  echo -e "  PRs closed: ${closed_prs}"
  echo -e "  Replan doc: ${replan_file#$CP_DIR/}"

  # Launch interactive replan interview
  echo -e "\n${BLUE}Launching replan interview...${NC}"
  local script_dir
  script_dir="$(cd "$(dirname "$0")" && pwd)"
  exec python3 "$script_dir/spec.py" --replan "$FEATURE" --cp-dir "$CP_DIR"
}

cmd_complete() {
  local lifecycle
  lifecycle=$(get_feature_field "lifecycle")

  if [ "$lifecycle" = "completed" ]; then
    echo -e "${DIM}Feature is already completed.${NC}"
    exit 0
  fi

  # Validate all tasks are done
  if [ -d "$QUEUE_DIR" ]; then
    for f in "$QUEUE_DIR"/*/wave-*.md; do
      [ -f "$f" ] || continue
      local task_status
      task_status=$(status_from_path "$f")
      if [ "$task_status" != "done" ]; then
        echo -e "${RED}Error: Not all tasks are done. $(basename "$f") is '${task_status}'${NC}"
        echo -e "${DIM}Use 'relay check ${FEATURE}' to see task breakdown.${NC}"
        exit 1
      fi
    done
  fi

  # Validate all PRs are merged
  echo -e "${DIM}Validating PR merge status...${NC}"
  local merged_count
  if ! merged_count=$(validate_prs_merged); then
    if [ "$FORCE" = true ]; then
      echo -e "${YELLOW}Warning: Proceeding despite unmerged PRs (--force)${NC}"
      echo -e "\n${BOLD}Closing open PRs (forced)...${NC}"
      local force_closed
      force_closed=$(close_feature_prs)
      [ "$force_closed" -gt 0 ] && echo -e "  Closed ${force_closed} open PR(s)"
    else
      echo -e "${DIM}Use --force to close the feature anyway (open PRs will be closed).${NC}"
      exit 1
    fi
  else
    [ "$merged_count" -gt 0 ] && log "All ${merged_count} PR(s) verified merged"
  fi

  echo -e "${GREEN}Completing feature: ${FEATURE}${NC}"

  # Generate feature summary
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  log "Generating feature summary..."
  mkdir -p "$CP_DIR/features/_summaries"
  python3 "$SCRIPT_DIR/_compact.py" "$FEATURE" --cp-dir "$CP_DIR" \
    || echo -e "${YELLOW}Warning: Summary generation failed — continuing without it${NC}"

  # Clean up ephemeral handoff notes (per D2)
  if [ -d "$CP_DIR/handoffs/$FEATURE" ]; then
    rm -rf "$CP_DIR/handoffs/$FEATURE"
    log "Cleaned up handoff notes for $FEATURE"
  fi

  # Aggregate cost data from all task files
  local total_cost=0 total_input=0 total_output=0
  if [ -d "$QUEUE_DIR" ]; then
    for f in "$QUEUE_DIR"/*/wave-*.md; do
      [ -f "$f" ] || continue
      local fm
      fm=$(sed -n '/^---$/,/^---$/p' "$f")
      local c i o
      c=$(echo "$fm" | { grep '^cost-usd:' || true; } | sed 's/^cost-usd:[[:space:]]*//' | tr -d '"')
      i=$(echo "$fm" | { grep '^input-tokens:' || true; } | sed 's/^input-tokens:[[:space:]]*//' | tr -d '"')
      o=$(echo "$fm" | { grep '^output-tokens:' || true; } | sed 's/^output-tokens:[[:space:]]*//' | tr -d '"')
      [ -n "$c" ] && total_cost=$(python3 -c "print(round($total_cost + $c, 6))")
      [ -n "$i" ] && total_input=$((total_input + i))
      [ -n "$o" ] && total_output=$((total_output + o))
    done
  fi
  local total_tokens=$((total_input + total_output))
  if [ "$total_tokens" -gt 0 ] || [ "$total_cost" != "0" ]; then
    set_feature_field "total-cost-usd" "$total_cost"
    set_feature_field "total-tokens" "$total_tokens"
    log "Feature cost: \$$total_cost ($total_tokens tokens)"
  fi

  # Update feature frontmatter and move to completed/ phase
  set_feature_field "completed-at" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  set_feature_field "lifecycle" "completed"
  FEATURE_FILE=$(update_feature_phase "$FEATURE_FILE" "completed")

  # Archive queue directory
  if [ -d "$QUEUE_DIR" ]; then
    mkdir -p "$CP_DIR/queue/_done"
    # Remove stale empty directory from prior attempts to prevent git mv nesting
    # (git mv moves source INTO an existing target dir instead of replacing it)
    if [ -d "$CP_DIR/queue/_done/${FEATURE}" ]; then
      rm -rf "$CP_DIR/queue/_done/${FEATURE}"
    fi
    git -C "$CP_DIR" mv "queue/${FEATURE}/" "queue/_done/${FEATURE}/" 2>/dev/null \
      || mv "$QUEUE_DIR" "$CP_DIR/queue/_done/${FEATURE}"
  fi

  # Clean up remote branches
  log "Cleaning up remote branches..."
  local remote_deleted
  remote_deleted=$(delete_remote_feature_branches)
  [ "$remote_deleted" -gt 0 ] && log "Deleted $remote_deleted remote branch(es)"

  # Clean up local branches
  log "Cleaning up local branches..."
  local local_deleted
  local_deleted=$(delete_local_branches)
  [ "$local_deleted" -gt 0 ] && log "Deleted $local_deleted local branch(es)"

  git_commit_and_push "lifecycle: complete ${FEATURE}"

  echo -e "${GREEN}Completed.${NC}"
  echo -e "  Queue archived to: queue/_done/${FEATURE}/"
  [ "$remote_deleted" -gt 0 ] && echo -e "  Remote branches deleted: ${remote_deleted}"
  [ "$local_deleted" -gt 0 ] && echo -e "  Local branches deleted: ${local_deleted}"
  if [ -f "$CP_DIR/features/_summaries/${FEATURE}-summary.md" ]; then
    echo -e "  Summary: features/_summaries/${FEATURE}-summary.md"
  fi
  echo ""
  echo -e "  ${DIM}Next:${NC} ${BOLD}relay new${NC} ${DIM}to start another feature, or${NC} ${BOLD}relay check${NC} ${DIM}to see remaining work.${NC}"
}

# ── Reset (dev/demo escape hatch) ────────────────────────────

strip_claim_metadata() {
  # Remove claim, cost, and PR fields from a task file's frontmatter.
  local file_path="$1"
  python3 -c "
import re
with open('$file_path') as f:
    content = f.read()
m = re.match(r'^(---\s*\n)(.*?)(\n---)', content, re.DOTALL)
if m:
    front = m.group(2)
    for field in ['claimed-by', 'claimed-at', 'claimed-on', 'cost-usd',
                  'input-tokens', 'output-tokens', 'duration-ms', 'pr-url', 'pr-number']:
        front = re.sub(r'^' + field + ':.*\n?', '', front, flags=re.MULTILINE)
    front = front.rstrip('\n')
    front = re.sub(r'^status:.*$', 'status: ready', front, flags=re.MULTILINE)
    content = m.group(1) + front + m.group(3) + content[m.end():]
with open('$file_path', 'w') as f:
    f.write(content)
"
}

cmd_reset() {
  echo -e "${YELLOW}Resetting feature: ${FEATURE}${NC}"
  echo ""

  # 1. Close open PRs
  echo -e "${BOLD}Closing open PRs...${NC}"
  local closed_prs
  closed_prs=$(close_feature_prs)
  if [ "$closed_prs" -gt 0 ]; then
    echo -e "  ${GREEN}Closed ${closed_prs} PR(s)${NC}"
  else
    echo -e "  ${DIM}No open PRs to close${NC}"
  fi

  # 2. Delete orphaned branches
  echo ""
  echo -e "${BOLD}Deleting orphaned branches...${NC}"
  local deleted_branches
  deleted_branches=$(delete_unclaimed_branches)
  if [ "$deleted_branches" -gt 0 ]; then
    echo -e "  ${GREEN}Deleted ${deleted_branches} branch(es)${NC}"
  else
    echo -e "  ${DIM}No orphaned branches${NC}"
  fi

  # 3. Move in-progress and blocked tasks back to ready
  echo ""
  echo -e "${BOLD}Resetting tasks...${NC}"
  local reset_inprog reset_blocked
  reset_inprog=$(update_tasks_status "in-progress" "ready")
  reset_blocked=$(update_tasks_status "blocked" "ready")
  local total_reset=$((reset_inprog + reset_blocked))

  # 4. Strip claim metadata from all ready tasks (they may have stale metadata)
  local ready_dir="$QUEUE_DIR/ready"
  if [ -d "$ready_dir" ]; then
    for f in "$ready_dir"/wave-*.md; do
      [ -f "$f" ] || continue
      strip_claim_metadata "$f"
    done
  fi

  if [ "$total_reset" -gt 0 ]; then
    echo -e "  ${GREEN}Reset ${total_reset} task(s) to ready${NC} (${reset_inprog} in-progress, ${reset_blocked} blocked)"
  else
    echo -e "  ${DIM}No tasks to reset${NC}"
  fi

  # 5. Delete local branches in target repos
  echo ""
  echo -e "${BOLD}Cleaning local branches...${NC}"
  local local_deleted=0
  for repo_name in $(get_target_repos); do
    local repo_path=""
    while IFS='|' read -r name _nwo path; do
      if [ "$name" = "$repo_name" ]; then
        repo_path="$path"
        break
      fi
    done < <(parse_service_catalog "$CP_DIR/.relay/service-catalog.md")

    if [ -n "$repo_path" ] && [ -d "$repo_path" ]; then
      local branches
      branches=$(git -C "$repo_path" branch --list "agent/${FEATURE}-*" "fix/${FEATURE}-*" 2>/dev/null || true)
      for b in $branches; do
        b=$(echo "$b" | tr -d ' *')
        [ -z "$b" ] && continue
        git -C "$repo_path" checkout main 2>/dev/null || true
        git -C "$repo_path" branch -D "$b" 2>/dev/null && {
          echo -e "  ${DIM}Deleted local branch: $b ($repo_name)${NC}"
          local_deleted=$((local_deleted + 1))
        }
      done
    fi
  done
  if [ "$local_deleted" -eq 0 ]; then
    echo -e "  ${DIM}No local branches to delete${NC}"
  fi

  # 6. Commit and push
  echo ""
  git_commit_and_push "reset: ${FEATURE} — tasks moved back to ready"

  echo ""
  echo -e "${GREEN}Done.${NC} ${total_reset} task(s) reset to ready."
  echo ""
  echo -e "  ${DIM}Next:${NC} ${BOLD}relay check ${FEATURE}${NC} ${DIM}to verify, or dispatch from the Command Center.${NC}"
}

# ── Dispatch ─────────────────────────────────────────────────

case "$COMMAND" in
  status)   cmd_status ;;
  pause)    cmd_pause ;;
  resume)   cmd_resume ;;
  cancel)   cmd_cancel ;;
  replan)   cmd_replan ;;
  complete) cmd_complete ;;
  reset)    cmd_reset ;;
  *)
    echo -e "${RED}Unknown command: ${COMMAND}${NC}"
    echo "Commands: status, pause, resume, cancel, replan, complete, reset"
    exit 1
    ;;
esac
