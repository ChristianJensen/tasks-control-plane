#!/usr/bin/env bash
set -euo pipefail

# relay check-rules — check if compiled constitution is stale.
#
# Compares the SHAs recorded in a constitution file against the current HEAD
# of each tier's repo. Exit 0 = fresh, exit 1 = stale.
#
# Usage: check-rules.sh [--cp-dir <path>] [--fix]

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

CP_DIR=""
FIX=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir) CP_DIR="$2"; shift 2 ;;
    --fix)    FIX=true; shift ;;
    *)        echo "Usage: $0 [--cp-dir <path>] [--fix]"; exit 1 ;;
  esac
done

# Find constitution file
CONSTITUTION=""
if [ -f ".relay/constitution.md" ]; then
  CONSTITUTION=".relay/constitution.md"
elif [ -f "constitution.md" ]; then
  CONSTITUTION="constitution.md"
else
  echo -e "${RED}No constitution.md found.${NC}"
  echo -e "${DIM}Run 'relay compile-constitution' first.${NC}"
  exit 1
fi

echo -e "${BOLD}Check Rules${NC}"
echo -e "  Constitution: ${CONSTITUTION}"
echo ""

# Parse SHAs from header: "> Source SHAs — Relay: abc1234, Control Plane: def5678, Code Repo: ghi9012"
SHA_LINE=$(grep "^> Source SHAs" "$CONSTITUTION" 2>/dev/null || echo "")
if [ -z "$SHA_LINE" ]; then
  echo -e "${RED}Cannot read source SHAs from constitution.${NC}"
  exit 1
fi

STALE=false

check_tier() {
  local label="$1" dir="$2"
  if [ -z "$dir" ] || [ ! -d "$dir" ]; then
    return
  fi

  # Extract recorded SHA for this tier
  recorded=$(echo "$SHA_LINE" | grep -oP "${label}: \K[a-f0-9]+" || echo "")
  if [ -z "$recorded" ]; then
    return
  fi

  current=$(git -C "$dir" rev-parse --short HEAD 2>/dev/null || echo "unknown")

  if [ "$recorded" = "$current" ]; then
    echo -e "  ${GREEN}✓${NC} ${label}: ${recorded} (current)"
  else
    echo -e "  ${YELLOW}!${NC} ${label}: was ${recorded}, now ${current}"
    STALE=true
  fi
}

# Resolve tier directories
# Code repo: cwd if .relay/config.md exists
CODE_DIR=""
if [ -f ".relay/config.md" ]; then
  CODE_DIR="$(pwd)"
fi

# Control plane
if [ -z "$CP_DIR" ] && [ -f ".relay/config.md" ]; then
  CP_DIR=$(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    for line in f:
        m = re.match(r'^control-plane-path:\s*(.+)', line)
        if m: print(m.group(1).strip()); break
" ".relay/config.md" 2>/dev/null || true)
fi

# Relay
RELAY_DIR=""
if [ -n "$CP_DIR" ] && [ -f "$CP_DIR/.relay-config" ]; then
  RELAY_DIR=$(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    for line in f:
        m = re.match(r'^relay-path:\s*(.+)', line)
        if m: print(m.group(1).strip()); break
" "$CP_DIR/.relay-config" 2>/dev/null || true)
fi

# Also try: the script's own location to find relay
if [ -z "$RELAY_DIR" ]; then
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  CAND="$(dirname "$(dirname "$SCRIPT_DIR")")"
  if [ -f "$CAND/VERSION" ]; then
    RELAY_DIR="$CAND"
  fi
fi

check_tier "Relay" "$RELAY_DIR"
check_tier "Control Plane" "$CP_DIR"
check_tier "Code Repo" "$CODE_DIR"

echo ""

if [ "$STALE" = true ]; then
  if [ "$FIX" = true ]; then
    echo -e "${YELLOW}Constitution is stale. Recompiling...${NC}"
    COMPILE_SCRIPT="$(dirname "$0")/compile-constitution.py"
    if [ -f "$COMPILE_SCRIPT" ]; then
      python3 "$COMPILE_SCRIPT" .
    else
      echo -e "${RED}Cannot find compile-constitution.py${NC}"
      exit 1
    fi
  else
    echo -e "${YELLOW}Constitution is stale.${NC}"
    echo -e "${DIM}Run 'relay compile-constitution' or 'relay check-rules --fix' to update.${NC}"
    exit 1
  fi
else
  echo -e "${GREEN}Constitution is up to date.${NC}"
fi
