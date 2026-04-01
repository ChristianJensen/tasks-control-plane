#!/usr/bin/env bash
set -euo pipefail

# migrate-state.sh — Migrate a control plane from flat layout to directory-based state.
#
# Moves task files into status subdirectories and feature specs into phase directories.
#
# Usage: migrate-state.sh [--cp-dir <path>] [--dry-run] [--tasks-only] [--features-only] [--feature <name>]

# ── Parse flags ────────────────────────────────────────────────
DRY_RUN=false
TASKS_ONLY=false
FEATURES_ONLY=false
FEATURE_FILTER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir)       export CP_DIR="$2"; shift 2 ;;
    --dry-run)      DRY_RUN=true; shift ;;
    --tasks-only)   TASKS_ONLY=true; shift ;;
    --features-only) FEATURES_ONLY=true; shift ;;
    --feature)      FEATURE_FILTER="$2"; shift 2 ;;
    *)
      echo "Usage: migrate-state.sh [--cp-dir <path>] [--dry-run] [--tasks-only] [--features-only] [--feature <name>]"
      exit 1
      ;;
  esac
done

# Source shared library
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"
_LOG_CONTEXT="migrate"

if [ -z "${CP_DIR:-}" ]; then
  log_err "CP_DIR not set. Use --cp-dir or run from a control plane."
  exit 1
fi

QUEUE_DIR="$CP_DIR/queue"
FEATURES_DIR="$CP_DIR/features"

moved_tasks=0
moved_features=0
skipped=0

# ── Migrate tasks ──────────────────────────────────────────────

migrate_task_file() {
  local file="$1"
  local status

  # Read status from frontmatter
  status=$(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    content = f.read()
m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
if m:
    sm = re.search(r'^status:\s*(.+)', m.group(1), re.MULTILINE)
    if sm: print(sm.group(1).strip())
" "$file" 2>/dev/null || true)

  if [ -z "$status" ]; then
    log_warn "  No status found in $(basename "$file"), skipping"
    skipped=$((skipped + 1))
    return
  fi

  local feature_dir new_dir new_path
  feature_dir="$(dirname "$file")"
  new_dir="${feature_dir}/${status}"
  new_path="${new_dir}/$(basename "$file")"

  if [ "$DRY_RUN" = true ]; then
    echo "  [dry-run] mv $(basename "$file") → ${status}/$(basename "$file")"
  else
    mkdir -p "$new_dir"
    git -C "$CP_DIR" mv "$file" "$new_path" 2>/dev/null || mv "$file" "$new_path"
  fi
  moved_tasks=$((moved_tasks + 1))
}

if [ "$FEATURES_ONLY" != true ]; then
  log "Migrating task files..."

  # Active queue
  for feature_dir in "$QUEUE_DIR"/*/; do
    [ -d "$feature_dir" ] || continue
    feature_name=$(basename "$feature_dir")
    [ "$feature_name" = "_done" ] && continue

    if [ -n "$FEATURE_FILTER" ] && [ "$feature_name" != "$FEATURE_FILTER" ]; then
      continue
    fi

    for task_file in "$feature_dir"wave-*.md; do
      [ -f "$task_file" ] || continue
      migrate_task_file "$task_file"
    done
  done

  # Archived queue (_done/)
  if [ -d "$QUEUE_DIR/_done" ]; then
    for feature_dir in "$QUEUE_DIR/_done"/*/; do
      [ -d "$feature_dir" ] || continue
      feature_name=$(basename "$feature_dir")

      if [ -n "$FEATURE_FILTER" ] && [ "$feature_name" != "$FEATURE_FILTER" ]; then
        continue
      fi

      for task_file in "$feature_dir"wave-*.md; do
        [ -f "$task_file" ] || continue
        migrate_task_file "$task_file"
      done
    done
  fi

  log_ok "Tasks: ${moved_tasks} moved, ${skipped} skipped"
fi

# ── Migrate features ──────────────────────────────────────────

# Lifecycle → phase directory mapping
lifecycle_to_phase() {
  case "$1" in
    draft)                      echo "draft" ;;
    active|paused|replanning)   echo "active" ;;
    live-dev|live-staging)      echo "active" ;;
    completed|live-prod)        echo "completed" ;;
    cancelled)                  echo "cancelled" ;;
    *)                          echo "active" ;;  # default
  esac
}

if [ "$TASKS_ONLY" != true ]; then
  log "Migrating feature specs..."

  for spec in "$FEATURES_DIR"/*-feature.md "$FEATURES_DIR"/*-bug.md; do
    [ -f "$spec" ] || continue

    # Skip if already in a phase directory
    parent=$(basename "$(dirname "$spec")")
    case "$parent" in
      draft|active|completed|cancelled) continue ;;
    esac

    fname=$(basename "$spec")
    slug="${fname%-feature.md}"
    slug="${slug%-bug.md}"

    if [ -n "$FEATURE_FILTER" ] && [ "$slug" != "$FEATURE_FILTER" ]; then
      continue
    fi

    # Read lifecycle from frontmatter
    lifecycle=$(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    content = f.read()
m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
if m:
    sm = re.search(r'^lifecycle:\s*(.+)', m.group(1), re.MULTILINE)
    if sm: print(sm.group(1).strip())
" "$spec" 2>/dev/null || echo "active")

    phase=$(lifecycle_to_phase "$lifecycle")
    new_dir="$FEATURES_DIR/$phase"
    new_path="$new_dir/$fname"

    if [ "$DRY_RUN" = true ]; then
      echo "  [dry-run] mv $fname → ${phase}/$fname (lifecycle: $lifecycle)"
    else
      mkdir -p "$new_dir"
      git -C "$CP_DIR" mv "$spec" "$new_path" 2>/dev/null || mv "$spec" "$new_path"
    fi
    moved_features=$((moved_features + 1))
  done

  log_ok "Features: ${moved_features} moved"
fi

# ── Commit ──────────────────────────────────────────────────────

if [ "$DRY_RUN" = true ]; then
  echo ""
  log "Dry run complete. No files were changed."
  echo "  Tasks: ${moved_tasks} would move"
  echo "  Features: ${moved_features} would move"
  echo "  Skipped: ${skipped}"
else
  if [ $((moved_tasks + moved_features)) -gt 0 ]; then
    git -C "$CP_DIR" add -A 2>/dev/null
    git -C "$CP_DIR" commit -m "chore: migrate to directory-based state machine" 2>/dev/null || true
    log_ok "Committed migration."
  else
    log "Nothing to migrate."
  fi
fi
