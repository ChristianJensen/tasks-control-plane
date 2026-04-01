#!/usr/bin/env bash
set -euo pipefail

# Relay Agents — scans the queue for repos with ready tasks, then launches
# split terminal panes (one per repo) using tmux or Windows Terminal.
#
# Usage:
#   agents.sh [--cp-dir <path>] [--agents-per-repo N] [--poll N] [--no-split] [--gui] [--tmux]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Defaults
AGENTS_PER_REPO=1
POLL_INTERVAL=10
NO_SPLIT=false
INTERACTIVE=false
GUI=false
FORCE_TMUX=false

# Parse CLI flags (before sourcing _lib.sh so CP_DIR is set)
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
    --no-split)
      NO_SPLIT=true
      shift
      ;;
    --interactive)
      INTERACTIVE=true
      shift
      ;;
    --gui)
      GUI=true
      shift
      ;;
    --tmux)
      FORCE_TMUX=true
      shift
      ;;
    *)
      echo "Usage: $0 [--cp-dir <path>] [--agents-per-repo N] [--poll N] [--no-split] [--gui] [--tmux] [--interactive]"
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

if [[ ${#REPO_NAMES[@]} -eq 0 ]]; then
  echo -e "${YELLOW}ERROR: No repos found in $CATALOG_FILE${NC}" >&2
  exit 1
fi

# ── Scan queue for repos with ready tasks ─────────────────────
ACTIVE_REPOS=()
ACTIVE_PATHS=()
ACTIVE_COUNTS=()

echo -e "${DIM}Scanning queue for ready tasks...${NC}"

for i in "${!REPO_NAMES[@]}"; do
  name="${REPO_NAMES[$i]}"
  count=$(python3 "$SCRIPT_DIR/_parse-queue.py" \
    "$CP_DIR/queue" "$name" \
    --status ready \
    --execution "autonomous,supervised" 2>/dev/null \
  | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

  if [[ "$count" -gt 0 ]]; then
    ACTIVE_REPOS+=("$name")
    ACTIVE_PATHS+=("${REPO_PATHS[$i]}")
    ACTIVE_COUNTS+=("$count")
    echo -e "  ${GREEN}✓${NC} ${BOLD}$name${NC} — $count ready task(s)"
  else
    echo -e "  ${DIM}· $name — no ready tasks${NC}"
  fi
done

echo ""

if [[ ${#ACTIVE_REPOS[@]} -eq 0 ]]; then
  echo -e "${YELLOW}No repos have ready tasks. Nothing to launch.${NC}"
  echo -e "${DIM}Push tasks to the queue first, then re-run 'relay agents'.${NC}"
  exit 0
fi

# ── Build the local-agent.sh command for a given repo ─────────
agent_cmd() {
  local repo_name="$1"
  local cmd="$SCRIPT_DIR/local-agent.sh --cp-dir $CP_DIR --repo $repo_name --agents-per-repo $AGENTS_PER_REPO --poll $POLL_INTERVAL"
  if [[ "$INTERACTIVE" == true ]]; then
    cmd="$cmd --interactive"
  fi
  echo "$cmd"
}

# ── Detect multiplexer and launch ─────────────────────────────

launch_tmux() {
  local session="relay-agents"

  # Kill existing session if present
  tmux kill-session -t "$session" 2>/dev/null || true

  # Create session with first repo
  tmux new-session -d -s "$session" -n "${ACTIVE_REPOS[0]}" \
    "$(agent_cmd "${ACTIVE_REPOS[0]}")"

  # Split for each additional repo
  for i in $(seq 1 $((${#ACTIVE_REPOS[@]} - 1))); do
    tmux split-window -t "$session" \
      "$(agent_cmd "${ACTIVE_REPOS[$i]}")"
    tmux select-layout -t "$session" tiled
  done

  echo -e "${GREEN}Launching tmux session '${session}' with ${#ACTIVE_REPOS[@]} pane(s)...${NC}"
  echo ""

  # Attach
  exec tmux attach -t "$session"
}

launch_wt() {
  # Build Windows Terminal command with split panes
  local cmd="wt.exe new-tab --title \"${ACTIVE_REPOS[0]}\" bash -c \"$(agent_cmd "${ACTIVE_REPOS[0]}")\""

  for i in $(seq 1 $((${#ACTIVE_REPOS[@]} - 1))); do
    cmd="$cmd \\; split-pane --title \"${ACTIVE_REPOS[$i]}\" bash -c \"$(agent_cmd "${ACTIVE_REPOS[$i]}")\""
  done

  echo -e "${GREEN}Launching Windows Terminal with ${#ACTIVE_REPOS[@]} pane(s)...${NC}"
  echo ""

  eval "$cmd"
}

launch_fallback() {
  echo -e "${YELLOW}No terminal multiplexer found (tmux/wt.exe).${NC}"
  echo -e "${YELLOW}Running agents in background with interleaved output...${NC}"
  echo ""

  PIDS=()
  cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping agents...${NC}"
    for pid in "${PIDS[@]}"; do
      kill "$pid" 2>/dev/null || true
    done
    wait "${PIDS[@]}" 2>/dev/null || true
    echo -e "${GREEN}All agents stopped.${NC}"
    exit 0
  }
  trap cleanup INT TERM

  for i in "${!ACTIVE_REPOS[@]}"; do
    eval "$(agent_cmd "${ACTIVE_REPOS[$i]}")" &
    PIDS+=($!)
  done

  wait "${PIDS[@]}"
}

# ── GUI launcher (macOS only) ─────────────────────────────────

launch_gui() {
  if [ -d "/Applications/iTerm.app" ]; then
    # iTerm2: open tabs in a single window
    local first=true
    for repo in "${ACTIVE_REPOS[@]}"; do
      local cmd
      cmd=$(agent_cmd "$repo")
      if [[ "$first" == true ]]; then
        osascript <<EOF
tell application "iTerm"
  activate
  set newWindow to (create window with default profile)
  tell current session of newWindow
    set name to "relay: $repo"
    write text "$cmd"
  end tell
end tell
EOF
        first=false
      else
        osascript <<EOF
tell application "iTerm"
  tell current window
    set newTab to (create tab with default profile)
    tell current session of newTab
      set name to "relay: $repo"
      write text "$cmd"
    end tell
  end tell
end tell
EOF
      fi
    done
    echo -e "${GREEN}Launched ${#ACTIVE_REPOS[@]} iTerm2 tab(s). Switch to iTerm to watch.${NC}"
  else
    # Terminal.app: open separate windows
    for repo in "${ACTIVE_REPOS[@]}"; do
      local cmd
      cmd=$(agent_cmd "$repo")
      osascript <<EOF
tell application "Terminal"
  activate
  set newWindow to do script "$cmd"
  set custom title of front window to "relay: $repo"
end tell
EOF
    done
    echo -e "${GREEN}Launched ${#ACTIVE_REPOS[@]} Terminal window(s). Switch to Terminal.app to watch.${NC}"
  fi
}

# ── Auto-detect GUI mode on macOS ─────────────────────────────
# Default to separate terminal windows on macOS (use --tmux to override).
if [[ "$(uname -s)" == "Darwin" ]] && [[ "$GUI" == false ]] && [[ "$NO_SPLIT" == false ]] && [[ "$FORCE_TMUX" == false ]]; then
  GUI=true
fi

# ── Dispatch ──────────────────────────────────────────────────

if [[ "$GUI" == true ]]; then
  launch_gui
elif [[ "$NO_SPLIT" == true ]]; then
  launch_fallback
elif [[ "$(uname -s)" == MINGW* ]] || [[ "$(uname -s)" == MSYS* ]] || [[ "$(uname -s)" == CYGWIN* ]]; then
  if command -v wt.exe &>/dev/null; then
    launch_wt
  else
    launch_fallback
  fi
else
  if command -v tmux &>/dev/null; then
    launch_tmux
  else
    launch_fallback
  fi
fi
