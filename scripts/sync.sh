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
      local _feat _wave_num
      _feat=$(feature_from_task_path "$queue_file")
      _wave_num=$(basename "$queue_file" | sed -n 's/^wave-\([0-9]*\)-.*/\1/p')
      queue_file=$(update_task_status "$queue_file" "done")
      git -C "${CP_DIR:-$RELAY_DIR}" add "$queue_file" 2>/dev/null
      git -C "${CP_DIR:-$RELAY_DIR}" commit -m "done: $(basename "$queue_file") (PR #${pr_num} merged)" 2>/dev/null || true
      # Auto-promote next wave if this wave is now complete
      if [ -n "$_feat" ] && [ -n "$_wave_num" ]; then
        auto_promote_next_wave "$_feat" "$_wave_num"
      fi
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

if [ "$SYNCED" = true ]; then
  # Push accumulated changes (includes any auto-promoted waves)
  push_cp_with_retry || log_warn "Could not push control plane update."
else
  log "Nothing to sync."
fi
