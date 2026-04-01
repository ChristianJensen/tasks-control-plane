#!/usr/bin/env bash
set -euo pipefail

# Relay Handoff — commit and push queue/contract/feature changes from the control plane.
#
# Usage:
#   handoff.sh [--cp-dir <path>] [--dry-run]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Parse CLI flags
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir)
      export CP_DIR="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -*)
      echo "Usage: relay handoff [--cp-dir <path>] [--dry-run]"
      exit 1
      ;;
    *)
      shift
      ;;
  esac
done

# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
_LOG_CONTEXT="handoff"

CP="${CP_DIR:-$RELAY_DIR}"

# ── Step 1: Verify we're in a control plane ───────────────────────
if [ ! -f "$CP/.relay-config" ]; then
  log_err "Not in a control plane directory."
  echo -e "  ${DIM}Run from a directory with .relay-config, or use --cp-dir.${NC}"
  exit 1
fi

log "Control plane: ${BLUE}$CP${NC}"

# ── Step 2: Check for changes ────────────────────────────────────
CHANGES=$(git -C "$CP" status --porcelain queue/ contracts/ features/ handoffs/ 2>/dev/null || true)

if [ -z "$CHANGES" ]; then
  log_ok "Nothing to hand off — queue/, contracts/, and features/ are clean."
  exit 0
fi

echo -e "\n${BOLD}Changes to hand off:${NC}"
echo "$CHANGES" | while IFS= read -r line; do
  echo -e "  ${DIM}$line${NC}"
done
echo ""

# ── Step 3: Stage changes ────────────────────────────────────────
if [ "$DRY_RUN" = true ]; then
  log_warn "Dry run — skipping commit and push."
  exit 0
fi

git -C "$CP" add queue/ contracts/ features/ handoffs/ 2>/dev/null || true

# Build commit message
FEATURE_DIRS=$(git -C "$CP" diff --cached --name-only | grep "^queue/" | cut -d/ -f2 | sort -u | head -5)
if [ -n "$FEATURE_DIRS" ]; then
  FEATURE_LIST=$(echo "$FEATURE_DIRS" | tr '\n' ', ' | sed 's/,$//')
  COMMIT_MSG="feat: hand off queue tasks for $FEATURE_LIST"
else
  COMMIT_MSG="feat: hand off queue/contract/feature updates"
fi

# Check if there's anything staged
if git -C "$CP" diff --cached --quiet 2>/dev/null; then
  log_ok "Nothing staged to commit."
  exit 0
fi

# ── Step 4: Commit ───────────────────────────────────────────────
git -C "$CP" commit -m "$COMMIT_MSG" --quiet

log_ok "Committed: $COMMIT_MSG"

# ── Step 5: Push with retry ─────────────────────────────────────
push_cp_with_retry

log_ok "Pushed to remote."

# ── Step 6: Report ───────────────────────────────────────────────
echo ""
PARSE_QUEUE="$SCRIPT_DIR/_parse-queue.py"
QUEUE_DIR="$CP/queue"
FEATURES_DIR="$CP/features"

# Count tasks by status
if [ -d "$QUEUE_DIR" ]; then
  echo -e "${BOLD}Queue summary:${NC}"

  while IFS='|' read -r repo_name _repo_nwo _repo_local; do
    [ -z "$repo_name" ] && continue

    READY=$(python3 "$PARSE_QUEUE" "$QUEUE_DIR" "$repo_name" --status ready 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
    PENDING=$(python3 "$PARSE_QUEUE" "$QUEUE_DIR" "$repo_name" --status pending 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
    IN_PROGRESS=$(python3 "$PARSE_QUEUE" "$QUEUE_DIR" "$repo_name" --status in-progress 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)

    if [ "$READY" -gt 0 ] || [ "$PENDING" -gt 0 ] || [ "$IN_PROGRESS" -gt 0 ]; then
      echo -e "  ${BOLD}$repo_name:${NC} ${GREEN}$READY ready${NC}, ${YELLOW}$IN_PROGRESS in-progress${NC}, ${DIM}$PENDING pending${NC}"
    fi
  done < <(parse_service_catalog)
fi

echo ""
log_ok "Work is relayed. Run ${BOLD}relay agents${NC} to launch autonomous agents,"
echo -e "  or open a code repo and run ${BOLD}relay pickup${NC} to claim tasks manually."
