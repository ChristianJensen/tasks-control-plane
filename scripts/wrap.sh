#!/usr/bin/env bash
set -euo pipefail

# Relay Wrap — finalize a task: push branch, create PR, mark done, push CP.
#
# Usage:
#   wrap.sh [--cp-dir <path>] [--no-pr] [--dry-run]
#
# Must be run from a code repo that has .relay/config.md, on an agent/* or fix/* branch.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Parse CLI flags
NO_PR=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir)
      export CP_DIR="$2"
      shift 2
      ;;
    --no-pr)
      NO_PR=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -*)
      echo "Usage: relay wrap [--cp-dir <path>] [--no-pr] [--dry-run]"
      exit 1
      ;;
    *)
      shift
      ;;
  esac
done

# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
_LOG_CONTEXT="wrap"

REPO_DIR="$(pwd)"

# ── Step 1: Locate config ───────────────────────────────────────
CONFIG_FILE="$REPO_DIR/.relay/config.md"
if [ ! -f "$CONFIG_FILE" ]; then
  log_err "No .relay/config.md found in current directory."
  echo -e "  ${DIM}Run from a code repo bootstrapped with 'relay init'.${NC}"
  exit 1
fi

# Parse config
REPO_NAME=$(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    for line in f:
        m = re.match(r'^repo-name:\s*(.+)', line)
        if m: print(m.group(1).strip()); break
" "$CONFIG_FILE" 2>/dev/null || true)

CP_PATH=$(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    for line in f:
        m = re.match(r'^control-plane-path:\s*(.+)', line)
        if m: print(m.group(1).strip()); break
" "$CONFIG_FILE" 2>/dev/null || true)

CP_NWO=$(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    for line in f:
        m = re.match(r'^control-plane:\s*(.+)', line)
        if m: print(m.group(1).strip()); break
" "$CONFIG_FILE" 2>/dev/null || true)

if [ -z "$REPO_NAME" ]; then
  log_err "Could not determine repo-name from $CONFIG_FILE"
  exit 1
fi

if [ -z "$CP_PATH" ] || [ ! -d "$CP_PATH" ]; then
  log_err "Control plane not found at: $CP_PATH"
  echo -e "  ${DIM}Check control-plane-path in .relay/config.md${NC}"
  exit 1
fi

# Override CP_DIR for _lib.sh functions
export CP_DIR="$CP_PATH"

log "Repo: ${BOLD}$REPO_NAME${NC}"
log "Control plane: ${BLUE}$CP_PATH${NC}"

# ── Step 2: Detect current branch ────────────────────────────────
BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [[ ! "$BRANCH" =~ ^(agent|fix)/ ]]; then
  log_err "Not on an agent/ or fix/ branch (current: ${BOLD}$BRANCH${NC})."
  echo -e "  ${DIM}Run 'relay wrap' from an agent/* or fix/* branch after completing work.${NC}"
  exit 1
fi

log "Branch: ${BLUE}$BRANCH${NC}"

# ── Step 3: Pull latest control plane ────────────────────────────
log "Pulling latest control plane..."
if ! git -C "$CP_PATH" pull --ff-only 2>/dev/null; then
  log_warn "Could not fast-forward control plane. Continuing with local state."
fi

# ── Step 4: Reverse-lookup task file ─────────────────────────────
QUEUE_DIR="$CP_PATH/queue"
FEATURES_DIR="$CP_PATH/features"
TASK_PATH=""

for qfile in "$QUEUE_DIR"/*/*/wave-*.md; do
  [ -f "$qfile" ] || continue
  derived=$(derive_branch_slug "$qfile" "$REPO_NAME")
  if [ "$derived" = "$BRANCH" ]; then
    TASK_PATH="$qfile"
    break
  fi
done

if [ -z "$TASK_PATH" ]; then
  log_err "No matching task found for branch ${BOLD}$BRANCH${NC}."
  echo -e "  ${DIM}Looked in $QUEUE_DIR for tasks matching repo '$REPO_NAME'.${NC}"
  echo -e "  ${DIM}Ensure the task file exists and matches this branch name.${NC}"
  exit 1
fi

TASK_FILE=$(basename "$TASK_PATH")
TASK_FILENAME="${TASK_FILE%.md}"
QUEUE_REL_PATH="${TASK_PATH#$CP_PATH/}"

log "Task: ${BOLD}$TASK_FILENAME${NC}"

CURRENT_STATUS=$(status_from_path "$TASK_PATH")

if [ "$CURRENT_STATUS" = "done" ]; then
  log_warn "Task is already marked ${BOLD}done${NC}."
fi

# Extract feature and wave from task frontmatter
TASK_FEATURE=$(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    content = f.read()
m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
if m:
    sm = re.search(r'^feature:\s*(.+)', m.group(1), re.MULTILINE)
    if sm: print(sm.group(1).strip())
" "$TASK_PATH" 2>/dev/null || true)

TASK_WAVE=$(echo "$TASK_FILENAME" | sed -E 's/^wave-([0-9]+)-.*/\1/')
TASK_DESCRIPTION=$(echo "$TASK_FILENAME" | sed -E "s/^wave-[0-9]+-${REPO_NAME}-//" | tr '-' ' ')

# Resolve friendly feature title from spec heading (falls back to slug)
FEATURE_SPEC_REL=""
FEATURE_TITLE=""
if [ -n "$TASK_FEATURE" ]; then
  for phase in draft active completed cancelled; do
    for suffix in feature bug; do
      _fpath="${CP_PATH}/features/${phase}/${TASK_FEATURE}-${suffix}.md"
      if [ -f "$_fpath" ]; then
        FEATURE_SPEC_REL="features/${phase}/${TASK_FEATURE}-${suffix}.md"
        FEATURE_TITLE=$(sed -n 's/^# \(Feature Spec\|Bug Report\): *//p' "$_fpath" | head -1)
        break 2
      fi
    done
  done
fi

# ── Step 5: Get repo NWO for PR creation ─────────────────────────
REPO_NWO=$(git remote get-url origin 2>/dev/null \
  | sed -E 's|.*github\.com[:/]||; s|\.git$||' || true)

if [ -z "$REPO_NWO" ]; then
  log_err "Could not determine GitHub repo from git remote."
  exit 1
fi

# ── Dry-run summary ──────────────────────────────────────────────
if [ "$DRY_RUN" = true ]; then
  echo ""
  echo -e "${BOLD}Dry run — would perform:${NC}"
  echo -e "  1. Push branch ${BLUE}$BRANCH${NC} to origin"
  if [ "$NO_PR" = false ]; then
    echo -e "  2. Create PR on ${BOLD}$REPO_NWO${NC}"
    echo -e "     Title: [${TASK_FEATURE} wave ${TASK_WAVE}] ${TASK_DESCRIPTION}"
  else
    echo -e "  2. (skipped — --no-pr)"
  fi
  echo -e "  3. Mark task ${BOLD}$TASK_FILENAME${NC} → done"
  echo -e "  4. Commit + push control plane"
  echo ""
  exit 0
fi

# ── Step 6: Push branch ──────────────────────────────────────────
log "Pushing branch..."
if ! git push origin "$BRANCH" 2>/dev/null; then
  log_warn "Push failed or nothing to push — branch may already be up to date."
fi

# ── Step 7: Handle PR ────────────────────────────────────────────
PR_URL=""

if [ "$NO_PR" = false ]; then
  # Check for existing PR
  EXISTING_PR=$(gh pr list --repo "$REPO_NWO" --head "$BRANCH" --json number,url,state --limit 1 2>/dev/null || echo "[]")
  EXISTING_COUNT=$(echo "$EXISTING_PR" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

  if [ "$EXISTING_COUNT" -gt 0 ]; then
    PR_URL=$(echo "$EXISTING_PR" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['url'])" 2>/dev/null)
    PR_STATE=$(echo "$EXISTING_PR" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['state'])" 2>/dev/null)
    log_ok "Existing PR found (${PR_STATE}): ${BLUE}$PR_URL${NC}"
  else
    # Build SHA-pinned CP links
    CP_SHA=$(cp_head_sha)
    CP_GITHUB_URL=""
    CP_NWO_RESOLVED=$(relay_config "relay-nwo" 2>/dev/null || true)
    if [ -n "$CP_NWO_RESOLVED" ]; then
      CP_GITHUB_URL="https://github.com/${CP_NWO_RESOLVED}/blob/${CP_SHA}"
    elif [ -n "$CP_NWO" ]; then
      CP_GITHUB_URL="https://github.com/${CP_NWO}/blob/${CP_SHA}"
    fi

    # Read contracts from task frontmatter
    CONTRACTS=$(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    content = f.read()
m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
if not m: sys.exit()
in_contracts = False
for line in m.group(1).split('\n'):
    if re.match(r'^contracts:', line):
        in_contracts = True
        continue
    if in_contracts:
        cm = re.match(r'^\s+-\s+(.+)', line)
        if cm:
            print(cm.group(1).strip())
        elif not line.startswith(' '):
            break
" "$TASK_PATH" 2>/dev/null || true)

    # Read acceptance criteria from task body (after frontmatter)
    ACCEPTANCE=$(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    content = f.read()
# Strip frontmatter
body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
# Find acceptance criteria section
m = re.search(r'(?:^|\n)##\s*Acceptance Criteria\s*\n(.*?)(?:\n##|\Z)', body, re.DOTALL)
if m:
    print(m.group(1).strip())
else:
    print('See task file')
" "$TASK_PATH" 2>/dev/null || echo "See task file")

    # Build PR body
    PR_TITLE="[${TASK_FEATURE} wave ${TASK_WAVE}] ${TASK_DESCRIPTION}"

    CONTEXT_LINES="- **Feature Spec:** [${TASK_FEATURE}](${CP_GITHUB_URL}/${FEATURE_SPEC_REL})"
    CONTEXT_LINES="${CONTEXT_LINES}
- **Task:** [${TASK_FILE}](${CP_GITHUB_URL}/${QUEUE_REL_PATH})"

    for contract in $CONTRACTS; do
      CONTEXT_LINES="${CONTEXT_LINES}
- **Contract:** [${contract}](${CP_GITHUB_URL}/${contract})"
    done

    PR_BODY="## Context
${CONTEXT_LINES}

## Acceptance Criteria
> **Review focus:** Verify that test names and assertions match the behavioral scenarios below. If they match, the implementation is correct by definition.

${ACCEPTANCE}"

    log "Creating PR..."
    PR_URL=$(gh pr create --repo "$REPO_NWO" --title "$PR_TITLE" --body "$PR_BODY" 2>&1) || {
      log_err "Failed to create PR: $PR_URL"
      PR_URL=""
    }

    if [ -n "$PR_URL" ]; then
      log_ok "PR created: ${BLUE}$PR_URL${NC}"
    fi
  fi
else
  log "Skipping PR creation (--no-pr)."
fi

# ── Slack notification (new or existing PR) ─────────────────────
if [ -n "${SLACK_WEBHOOK_URL:-}" ] && [ -n "${PR_URL:-}" ]; then
  python3 "$SCRIPT_DIR/slack_notify.py" pr-ready \
    --webhook-url "$SLACK_WEBHOOK_URL" \
    --repo "$REPO_NAME" \
    --pr-url "$PR_URL" \
    --pr-title "${PR_TITLE:-PR ready for review}" \
    --feature "${FEATURE_TITLE:-${TASK_FEATURE:-}}" \
    --acceptance "${ACCEPTANCE:-}" \
    2>/dev/null || true
fi

# ── Step 8: Record PR info or mark done ───────────────────────────
if [ "$CURRENT_STATUS" != "done" ]; then
  if [ "$NO_PR" = true ]; then
    # No PR mode — mark done immediately
    log "Marking task done (no PR)..."
    if TASK_PATH=$(update_task_status "$TASK_PATH" "done"); then
      git -C "$CP_PATH" add "$TASK_PATH" 2>/dev/null
      git -C "$CP_PATH" commit -m "done: $TASK_FILENAME (no PR)" --quiet 2>/dev/null
      log "Pushing control plane..."
      push_cp_with_retry 2>/dev/null || log_warn "Could not push control plane update."
      log_ok "Task marked ${BOLD}done${NC}."
    else
      log_err "Failed to move task to done/ — filename may be too long"
    fi
  elif [ -n "$PR_URL" ]; then
    # PR exists — record it, leave task in-progress
    pr_num=$(echo "$PR_URL" | grep -oE '[0-9]+$' || true)
    log "Recording PR info..."
    set_task_pr_info "$TASK_PATH" "$PR_URL" "$pr_num"
    git -C "$CP_PATH" add "$TASK_PATH" 2>/dev/null
    git -C "$CP_PATH" commit -m "review: $TASK_FILENAME (PR #${pr_num})" --quiet 2>/dev/null

    log "Pushing control plane..."
    push_cp_with_retry 2>/dev/null || log_warn "Could not push control plane update."
    log_ok "PR #${pr_num} ready for review: ${PR_URL}"
    log     "  → Review and merge the PR. The watcher will auto-detect the merge."
  else
    # No PR URL captured — mark blocked
    log_warn "No PR URL available — marking task blocked."
    if TASK_PATH=$(update_task_status "$TASK_PATH" "blocked"); then
      git -C "$CP_PATH" add "$TASK_PATH" 2>/dev/null
      git -C "$CP_PATH" commit -m "blocked: $TASK_FILENAME (no PR)" --quiet 2>/dev/null
      push_cp_with_retry 2>/dev/null || log_warn "Could not push control plane update."
    else
      log_err "Failed to move task to blocked/ — filename may be too long"
    fi
  fi
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

# ── Summary ───────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Task wrapped successfully                      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Branch: ${BLUE}$BRANCH${NC}"
if [ -n "$PR_URL" ]; then
  echo -e "  PR:     ${BLUE}$PR_URL${NC}"
fi
echo -e "  Task:   ${BOLD}$TASK_FILENAME${NC} → done"
echo ""
echo -e "  ${DIM}Next: run${NC} ${BOLD}relay next${NC} ${DIM}or${NC} ${BOLD}relay check${NC} ${DIM}to see what's next.${NC}"
echo ""
