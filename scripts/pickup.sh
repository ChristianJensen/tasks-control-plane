#!/usr/bin/env bash
set -euo pipefail

# Relay Pickup — pull the queue, pick a task, claim it, and assemble context.
#
# Usage:
#   pickup.sh [--cp-dir <path>] [--task N] [--no-launch]
#
# Must be run from a code repo that has .relay/config.md.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Parse CLI flags
TASK_NUM=""
NO_LAUNCH=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir)
      export CP_DIR="$2"
      shift 2
      ;;
    --task)
      TASK_NUM="$2"
      shift 2
      ;;
    --no-launch)
      NO_LAUNCH=true
      shift
      ;;
    -*)
      echo "Usage: relay pickup [--cp-dir <path>] [--task N] [--no-launch]"
      exit 1
      ;;
    *)
      shift
      ;;
  esac
done

# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
_LOG_CONTEXT="pickup"

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

# ── Step 2: Discover Relay framework path ────────────────────────
if [ -z "$RELAY_DIR" ] || [ ! -d "$RELAY_DIR" ]; then
  _relay_path=$(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    for line in f:
        m = re.match(r'^relay-path:\s*(.+)', line)
        if m: print(m.group(1).strip()); break
" "$CP_PATH/.relay-config" 2>/dev/null || true)
  if [ -n "$_relay_path" ] && [ -f "$_relay_path/VERSION" ]; then
    RELAY_DIR="$_relay_path"
  fi
fi

# ── Step 3: Pull latest control plane ────────────────────────────
log "Pulling latest control plane..."
if ! git -C "$CP_PATH" pull --ff-only 2>/dev/null; then
  log_warn "Could not fast-forward control plane. Continuing with local state."
fi

# ── Step 4: Parse the queue ──────────────────────────────────────
PARSE_QUEUE="$SCRIPT_DIR/_parse-queue.py"
QUEUE_DIR="$CP_PATH/queue"
FEATURES_DIR="$CP_PATH/features"

TASKS_JSON=$(python3 "$PARSE_QUEUE" "$QUEUE_DIR" "$REPO_NAME" \
  --status ready 2>/dev/null || echo "[]")

TASK_COUNT=$(echo "$TASKS_JSON" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)

if [ "$TASK_COUNT" -eq 0 ]; then
  log_ok "No ready tasks for ${BOLD}$REPO_NAME${NC}."
  exit 0
fi

# ── Step 5: Show candidates ─────────────────────────────────────
echo ""
echo -e "${BOLD}Ready tasks for $REPO_NAME:${NC}"
echo ""
printf "  ${DIM}%-4s %-45s %-20s %-6s %-8s %-12s${NC}\n" "#" "Task" "Feature" "Wave" "Priority" "Exec"

python3 -c "
import json, sys, os
tasks = json.loads(sys.argv[1])
for i, t in enumerate(tasks, 1):
    filename = os.path.basename(t['path']).replace('.md', '')
    exec_mode = t.get('execution', 'supervised')
    print(f'  {i:<4} {filename:<45} {t[\"feature\"]:<20} {t[\"wave\"]:<6} {t[\"priority\"]:<8} {exec_mode:<12}')
" "$TASKS_JSON"

echo ""

# ── Step 6: Select task ─────────────────────────────────────────
if [ -n "$TASK_NUM" ]; then
  SELECTED="$TASK_NUM"
else
  read -rp "Which task? (default: 1) " SELECTED
  SELECTED="${SELECTED:-1}"
fi

# Validate selection
if ! [[ "$SELECTED" =~ ^[0-9]+$ ]] || [ "$SELECTED" -lt 1 ] || [ "$SELECTED" -gt "$TASK_COUNT" ]; then
  log_err "Invalid selection: $SELECTED (must be 1-$TASK_COUNT)"
  exit 1
fi

# Extract selected task
TASK_PATH=$(echo "$TASKS_JSON" | python3 -c "
import json, sys
tasks = json.load(sys.stdin)
idx = int(sys.argv[1]) - 1
print(tasks[idx]['path'])
" "$SELECTED")

TASK_FEATURE=$(echo "$TASKS_JSON" | python3 -c "
import json, sys
tasks = json.load(sys.stdin)
idx = int(sys.argv[1]) - 1
print(tasks[idx]['feature'])
" "$SELECTED")

TASK_FILE=$(basename "$TASK_PATH")
TASK_FILENAME="${TASK_FILE%.md}"

log "Selected: ${BOLD}$TASK_FILENAME${NC}"

# ── Step 7: Claim the task ──────────────────────────────────────
# Derive branch name
BRANCH=$(derive_branch_slug "$TASK_PATH" "$REPO_NAME")

log "Claiming branch: ${BLUE}$BRANCH${NC}"

# Fetch and create branch
git fetch origin main 2>/dev/null || git fetch origin 2>/dev/null || true
git checkout -b "$BRANCH" origin/main 2>/dev/null || {
  log_err "Could not create branch $BRANCH"
  echo -e "  ${DIM}It may already exist. Check with: git branch -a | grep $BRANCH${NC}"
  exit 1
}

# Claim with empty commit
CLAIM_USER="${USER:-$(whoami)}"
git commit --allow-empty -m "claim: $CLAIM_USER" --quiet

# Push claim
if ! git push origin "$BRANCH" 2>/dev/null; then
  log_warn "Push failed — another agent may have claimed this task."
  git checkout - 2>/dev/null || true
  git branch -D "$BRANCH" 2>/dev/null || true
  echo -e "  ${DIM}Try picking another task.${NC}"
  exit 1
fi

log_ok "Branch pushed — task claimed."

# Update task status (git mv to in-progress/) and claim metadata in control plane
TASK_PATH=$(update_task_status "$TASK_PATH" "in-progress")
set_task_claim "$TASK_PATH" "$CLAIM_USER" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(hostname -s 2>/dev/null || echo unknown)"
git -C "$CP_PATH" add "$TASK_PATH" 2>/dev/null
git -C "$CP_PATH" commit -m "claim: $TASK_FILENAME → in-progress" --quiet 2>/dev/null
push_cp 2>/dev/null || log_warn "Could not push control plane update."

# ── Step 8: Build context and launch agent ───────────────────────
echo ""
log "Assembling context..."

# Read task content (TASK_PATH may have moved to in-progress/ after claim)
TASK_CONTENT=$(cat "$TASK_PATH")

# Read contract (if referenced)
CONTRACT_CONTENT=""
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

for contract in $CONTRACTS; do
  contract_path="$CP_PATH/$contract"
  if [ -f "$contract_path" ]; then
    CONTRACT_CONTENT="${CONTRACT_CONTENT}\n--- $contract ---\n$(cat "$contract_path")\n"
  fi
done

# Read feature spec
FEATURE_SPEC=""
FEATURE_SPEC_FILE=$(find_feature_file "$TASK_FEATURE")
if [ -n "$FEATURE_SPEC_FILE" ] && [ -f "$FEATURE_SPEC_FILE" ]; then
  FEATURE_SPEC=$(cat "$FEATURE_SPEC_FILE")
fi

# Read repo constitution
CONSTITUTION=""
if [ -f "$REPO_DIR/CLAUDE.md" ]; then
  CONSTITUTION=$(cat "$REPO_DIR/CLAUDE.md")
elif [ -f "$REPO_DIR/AGENTS.md" ]; then
  CONSTITUTION=$(cat "$REPO_DIR/AGENTS.md")
fi

# Build the full prompt
CP_GITHUB_URL=""
if [ -n "$CP_NWO" ]; then
  CP_GITHUB_URL="https://github.com/$CP_NWO/blob/main"
fi

PROMPT="# Task Assignment

You are implementing a task from the Relay queue. Follow the task description and acceptance criteria exactly.

## Task File
$TASK_CONTENT

## Feature Context
$FEATURE_SPEC

## Contract
$(echo -e "$CONTRACT_CONTENT")

## Repo Constitution
$CONSTITUTION

## Instructions
1. Read the task description and acceptance criteria carefully.
2. Implement using TDD — write tests first, then implementation.
3. Follow the coding conventions in the repo constitution above.
4. Commit your changes with clear messages.
5. When done, create a PR with this format:
   - Title: [$TASK_FEATURE wave $(echo "$TASK_FILENAME" | sed -E 's/^wave-([0-9]+)-.*/\1/')] $(echo "$TASK_FILENAME" | sed -E 's/^wave-[0-9]+-[a-z0-9]+-//' | tr '-' ' ')
   - Body should reference the task file and feature spec.
"

if [ "$NO_LAUNCH" = true ]; then
  log_ok "Context assembled. Branch ready: ${BOLD}$BRANCH${NC}"
  echo ""
  echo -e "${DIM}Skipping agent launch (--no-launch). You can start working on this branch.${NC}"
  exit 0
fi

# Launch agent
AGENT="${RELAY_AGENT:-}"
if [ -z "$AGENT" ]; then
  if command -v claude &>/dev/null; then
    AGENT="claude"
  elif command -v gemini &>/dev/null; then
    AGENT="gemini"
  fi
fi

if [ -z "$AGENT" ]; then
  log_ok "Context assembled. Branch ready: ${BOLD}$BRANCH${NC}"
  echo ""
  echo -e "${DIM}No AI agent found. Install claude or gemini CLI, or set RELAY_AGENT.${NC}"
  echo -e "${DIM}You can start working on this branch manually.${NC}"
  echo ""
  echo -e "  ${DIM}When done:${NC} ${BOLD}relay done${NC}"
  exit 0
fi

log "Launching ${BOLD}$AGENT${NC}..."

# Write prompt to temp file (used by gemini and custom agents)
PROMPT_FILE=$(mktemp /tmp/relay-pickup-XXXXXX.md)
echo "$PROMPT" > "$PROMPT_FILE"
trap 'rm -f "$PROMPT_FILE"' EXIT

if [ "$AGENT" = "claude" ]; then
  exec claude "$PROMPT"
elif [ "$AGENT" = "gemini" ]; then
  exec gemini --prompt-file "$PROMPT_FILE"
else
  # Custom agent
  exec $AGENT "$PROMPT"
fi
