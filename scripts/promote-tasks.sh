#!/usr/bin/env bash
set -euo pipefail

# promote-tasks.sh — Lists pending queue tasks for a feature,
# displays the validation checklist, and promotes selected tasks to ready.
#
# Usage: ./promote-tasks.sh [--cp-dir <path>] <feature-name> [--wave N]

# ── Parse --cp-dir first ──────────────────────────────────────
POSITIONAL=()
WAVE_FILTER=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir)
      export CP_DIR="$2"
      shift 2
      ;;
    --wave)
      WAVE_FILTER="$2"
      shift 2
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

FEATURE="${POSITIONAL[0]:?Usage: promote-tasks.sh [--cp-dir <path>] <feature-name> [--wave N]}"

# Source shared library
source "$(dirname "$0")/_lib.sh"

# Validate CP_DIR
if [ -z "${CP_DIR:-}" ]; then
  echo -e "${RED}Error: CP_DIR not set. Use --cp-dir or run from a control plane.${NC}" >&2
  exit 1
fi

QUEUE_DIR="$CP_DIR/queue/${FEATURE}"

if [ ! -d "$QUEUE_DIR" ]; then
  echo -e "${RED}Error: No queue directory found for feature: ${FEATURE}${NC}"
  echo -e "${DIM}Expected: queue/${FEATURE}/${NC}"
  exit 1
fi

echo -e "${BOLD}Decomposition Validation Gate${NC}"
echo -e "Feature: ${BLUE}${FEATURE}${NC}"
[ -n "$WAVE_FILTER" ] && echo -e "Wave filter: ${BLUE}${WAVE_FILTER}${NC}"
echo ""

# ── Collect pending tasks ───────────────────────────────────────

ALL_TASKS=()
ALL_WAVES=()

for f in "$QUEUE_DIR"/pending/wave-*.md; do
  [ -f "$f" ] || continue

  # Extract wave number
  wave=$(grep "^wave:" "$f" | sed 's/^wave:[[:space:]]*//' | sed 's/[[:space:]]*#.*//')

  # Apply wave filter if set
  if [ -n "$WAVE_FILTER" ] && [ "$wave" != "$WAVE_FILTER" ]; then
    continue
  fi

  ALL_TASKS+=("$f")
  ALL_WAVES+=("$wave")
done

if [ ${#ALL_TASKS[@]} -eq 0 ]; then
  echo -e "${YELLOW}No pending tasks found"
  [ -n "$WAVE_FILTER" ] && echo -e " in wave ${WAVE_FILTER}"
  echo -e ".${NC}"
  exit 0
fi

# ── Display tasks grouped by wave ───────────────────────────────

echo -e "${BOLD}Pending tasks:${NC}"
echo ""

# Get unique sorted wave numbers (bash 3.x compatible — no associative arrays)
UNIQUE_WAVES=$(printf '%s\n' "${ALL_WAVES[@]}" | sort -nu)

for wave in $UNIQUE_WAVES; do
  echo -e "  ${BLUE}Wave ${wave}:${NC}"
  for i in "${!ALL_TASKS[@]}"; do
    [ "${ALL_WAVES[$i]}" != "$wave" ] && continue
    f="${ALL_TASKS[$i]}"
    fname=$(basename "$f" .md)
    priority=$(grep "^priority:" "$f" | sed 's/^priority:[[:space:]]*//' | sed 's/[[:space:]]*#.*//')
    repo=$(grep "^target-repo:" "$f" | sed 's/^target-repo:[[:space:]]*//' | sed 's/[[:space:]]*#.*//')
    echo -e "    ${fname}  [${repo}] [priority:${priority:-?}]"
  done
  echo ""
done

# ── Decomposition Validation Checklist ──────────────────────────

echo -e "${BOLD}Decomposition Validation Checklist:${NC}"
echo ""
echo "  [ ] Each task can be implemented independently within its repo"
echo "  [ ] Cross-repo tasks coordinate only via contracts"
echo "  [ ] No task rated size:large without split justification in AgDR"
echo "  [ ] All tasks have size and priority in frontmatter"
echo "  [ ] Each edge case from Feature Spec maps to at least one task's acceptance criteria"
echo "  [ ] Contract changes are sufficient for all tasks"
echo "  [ ] No circular dependencies"
echo "  [ ] Critical-priority tasks have no unresolved dependencies"
echo ""

# ── Show _validation.md if it exists ────────────────────────────

VALIDATION_FILE="$QUEUE_DIR/_validation.md"
if [ -f "$VALIDATION_FILE" ]; then
  echo -e "${BOLD}Feature Validation Notes:${NC}"
  echo ""
  cat "$VALIDATION_FILE"
  echo ""
fi

# ── Confirm checklist ───────────────────────────────────────────

read -p "$(echo -e "${YELLOW}Have you verified the checklist above? (y/n): ${NC}")" CONFIRMED

if [ "$CONFIRMED" != "y" ]; then
  echo -e "${RED}Promotion cancelled. Review the checklist and try again.${NC}"
  exit 1
fi

# ── Promote options ─────────────────────────────────────────────

echo ""
echo -e "${BOLD}Promote options:${NC}"
echo "  [a] Promote ALL pending tasks to ready"
echo "  [s] Select individual tasks to promote"
echo "  [q] Quit without promoting"
echo ""
read -p "Choice: " CHOICE

case "$CHOICE" in
  a|A)
    for f in "${ALL_TASKS[@]}"; do
      fname=$(basename "$f" .md)
      echo -e "  Promoting ${BLUE}${fname}${NC} → ready"
      update_task_status "$f" "ready" >/dev/null
    done
    echo ""
    echo -e "${GREEN}All ${#ALL_TASKS[@]} tasks promoted to ready.${NC}"
    ;;
  s|S)
    for f in "${ALL_TASKS[@]}"; do
      fname=$(basename "$f" .md)
      read -p "  Promote ${fname}? (y/n): " YN
      if [ "$YN" = "y" ]; then
        update_task_status "$f" "ready" >/dev/null
        echo -e "    ${GREEN}Promoted.${NC}"
      else
        echo -e "    ${YELLOW}Skipped.${NC}"
      fi
    done
    ;;
  *)
    echo -e "${YELLOW}No tasks promoted.${NC}"
    exit 0
    ;;
esac

# ── Commit and push ─────────────────────────────────────────────

echo ""
echo -e "${DIM}Committing status changes...${NC}"
git -C "$CP_DIR" add "queue/${FEATURE}/" 2>/dev/null
git -C "$CP_DIR" commit -m "promote: ${FEATURE} tasks pending → ready" 2>/dev/null || true
push_cp_with_retry
echo -e "${GREEN}Done.${NC}"
