#!/usr/bin/env bash
set -euo pipefail

# Relay Doctor — health checks for a control plane setup.
#
# Usage: ./doctor.sh [--cp-dir <path>]
#
# Runs from inside a control plane repo (or specify --cp-dir).
# Checks structure, service catalog, code repo configuration, and connectivity.

# ── Colors ─────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── Arguments ──────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir)
      export CP_DIR="$2"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--cp-dir <path>]"
      exit 1
      ;;
  esac
done

# Auto-detect control plane directory
if [ -z "${CP_DIR:-}" ]; then
  if [ -f "$(pwd)/.relay-config" ]; then
    CP_DIR="$(pwd)"
  else
    echo -e "${RED}Error: Not inside a control plane repo. Use --cp-dir <path>${NC}"
    exit 1
  fi
fi

# ── Counters ───────────────────────────────────────────────

PASS=0
WARN=0
FAIL=0

check_pass() { echo -e "  ${GREEN}✓${NC} $1"; PASS=$((PASS + 1)); }
check_warn() { echo -e "  ${YELLOW}!${NC} $1"; WARN=$((WARN + 1)); }
check_fail() { echo -e "  ${RED}✗${NC} $1"; FAIL=$((FAIL + 1)); }

# ── Version Info ───────────────────────────────────────────

echo -e "${BOLD}Relay Doctor${NC}"
echo -e "  Control plane: ${BLUE}${CP_DIR}${NC}"
echo ""

# ── 1. Control Plane Structure ─────────────────────────────

echo -e "${BOLD}Control Plane Structure${NC}"

for dir in features queue contracts; do
  if [ -d "$CP_DIR/$dir" ]; then
    check_pass "$dir/ exists"
  else
    check_fail "$dir/ missing"
  fi
done

if [ -f "$CP_DIR/CLAUDE.md" ]; then
  check_pass "CLAUDE.md exists"
else
  check_fail "CLAUDE.md missing"
fi

if [ -f "$CP_DIR/.relay-config" ]; then
  check_pass ".relay-config exists"
else
  check_fail ".relay-config missing — run 'relay init' to create"
fi

echo ""

# ── 2. Service Catalog ────────────────────────────────────

echo -e "${BOLD}Service Catalog${NC}"

CATALOG="$CP_DIR/.relay/service-catalog.md"
if [ -f "$CATALOG" ]; then
  check_pass "service-catalog.md exists"

  # Count repos in catalog
  REPO_COUNT=$(grep -c '^## ' "$CATALOG" 2>/dev/null || echo "0")
  if [ "$REPO_COUNT" -gt 0 ]; then
    check_pass "$REPO_COUNT repo(s) listed"
  else
    check_warn "No repos found in service catalog"
  fi
else
  check_fail "service-catalog.md missing"
fi

echo ""

# ── 3. Code Repo Checks ───────────────────────────────────

echo -e "${BOLD}Code Repos${NC}"

# Parse service catalog for repo info
if [ -f "$CATALOG" ]; then
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    repo_name=$(echo "$line" | cut -d'|' -f1 | xargs)
    repo_nwo=$(echo "$line" | cut -d'|' -f2 | xargs)
    repo_local=$(echo "$line" | cut -d'|' -f3 | xargs)

    # Expand ~
    repo_local="${repo_local/#\~/$HOME}"

    echo -e "  ${BLUE}${repo_name}${NC} (${repo_nwo})"

    # Check GitHub existence
    if command -v gh &>/dev/null; then
      if gh repo view "$repo_nwo" --json name &>/dev/null 2>&1; then
        check_pass "  GitHub repo exists"
      else
        check_warn "  GitHub repo not found (may be private or not yet created)"
      fi
    fi

    # Check local path
    if [ -d "$repo_local" ]; then
      check_pass "  Local path exists: $repo_local"

      # Check .relay/config.md
      if [ -f "$repo_local/.relay/config.md" ]; then
        check_pass "  .relay/config.md present"
      else
        check_warn "  .relay/config.md missing — run 'relay init' to configure"
      fi

      # Check CLAUDE.md references Relay
      if [ -f "$repo_local/CLAUDE.md" ]; then
        if grep -qi "relay\|control.plane" "$repo_local/CLAUDE.md" 2>/dev/null; then
          check_pass "  CLAUDE.md references Relay"
        else
          check_warn "  CLAUDE.md exists but doesn't reference Relay"
        fi
      else
        check_warn "  CLAUDE.md missing"
      fi

      # Check cloud-agent.yml (if cloud mode)
      if [ -f "$repo_local/.relay/config.md" ]; then
        exec_mode=$(grep -i "execution-mode:" "$repo_local/.relay/config.md" 2>/dev/null | sed 's/.*://;s/[[:space:]]*//' || echo "")
        if [ "$exec_mode" = "cloud" ]; then
          if [ -f "$repo_local/.github/workflows/cloud-agent.yml" ]; then
            check_pass "  cloud-agent.yml present (cloud mode)"
          else
            check_warn "  cloud-agent.yml missing (cloud mode configured)"
          fi
        fi
      fi
    else
      check_warn "  Local path not found: $repo_local"
    fi

  done < <(python3 -c "
import re, sys
content = open(sys.argv[1]).read()
for m in re.finditer(r'## (\S+)\n.*?\*\*Repo:\*\*\s*(\S+).*?\*\*Local:\*\*\s*\x60([^\x60]+)\x60', content, re.DOTALL):
    print(f'{m.group(1)}|{m.group(2)}|{m.group(3)}')
" "$CATALOG" 2>/dev/null)
fi

echo ""

# ── 4. Skills Check ──────────────────────────────────────

echo -e "${BOLD}Skills${NC}"

SKILLS_DIR="$HOME/.claude/skills/relay"
if [ -d "$SKILLS_DIR" ]; then
  skill_count=$(find "$SKILLS_DIR" -name "SKILL.md" | wc -l | tr -d ' ')
  check_pass "Global skills installed ($skill_count skills in ~/.claude/skills/relay/)"
else
  check_warn "Global skills not installed — run 'relay init' to install"
fi

echo ""

# ── 5. GitHub Configuration ──────────────────────────────

echo -e "${BOLD}GitHub Configuration${NC}"

if command -v gh &>/dev/null; then
  check_pass "gh CLI installed"

  if gh auth status &>/dev/null 2>&1; then
    check_pass "gh authenticated"
  else
    check_fail "gh not authenticated — run 'gh auth login'"
  fi
else
  check_warn "gh CLI not installed — cannot check GitHub configuration"
fi

if command -v claude &>/dev/null; then
  check_pass "claude CLI installed"
else
  check_warn "claude CLI not installed — needed for agent execution"
fi

echo ""

echo ""

# ── Constitution Health ────────────────────────────────────

echo -e "${BOLD}Constitution (Content DNS)${NC}"

if [ -f "$CP_DIR/.relay/constitution.md" ]; then
  check_pass "Control plane constitution.md exists"
  # Check if stale
  SHA_LINE=$(grep "^> Source SHAs" "$CP_DIR/.relay/constitution.md" 2>/dev/null || echo "")
  if [ -n "$SHA_LINE" ]; then
    RELAY_SHA_RECORDED=$(echo "$SHA_LINE" | grep -oP "Relay: \K[a-f0-9]+" || echo "")
    # Resolve RELAY_DIR from .relay-config
    _RELAY_DIR=$(python3 -c "
import re
with open('$CP_DIR/.relay-config') as f:
    for line in f:
        m = re.match(r'^relay-path:\s*(.+)', line)
        if m: print(m.group(1).strip()); break
" 2>/dev/null || echo "")
    if [ -n "$RELAY_SHA_RECORDED" ] && [ -n "$_RELAY_DIR" ] && [ -d "$_RELAY_DIR" ]; then
      RELAY_SHA_CURRENT=$(git -C "$_RELAY_DIR" rev-parse --short HEAD 2>/dev/null || echo "")
      if [ "$RELAY_SHA_RECORDED" = "$RELAY_SHA_CURRENT" ]; then
        check_pass "Relay SHA current ($RELAY_SHA_RECORDED)"
      else
        check_warn "Relay SHA stale (was $RELAY_SHA_RECORDED, now $RELAY_SHA_CURRENT) — run: relay upgrade"
      fi
    fi
  fi
elif [ -f "$CP_DIR/.relay/manifest.md" ]; then
  check_warn "manifest.md exists but constitution.md not compiled — run: relay upgrade"
else
  echo -e "  ${DIM}Content DNS not configured (optional — add manifest.md to enable)${NC}"
fi

echo ""

# ── Summary ────────────────────────────────────────────────

echo -e "${BOLD}Summary${NC}"
echo -e "  ${GREEN}${PASS} passed${NC}  ${YELLOW}${WARN} warnings${NC}  ${RED}${FAIL} failed${NC}"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo -e "${RED}Some checks failed. Fix the issues above and re-run 'relay doctor'.${NC}"
  exit 1
elif [ "$WARN" -gt 0 ]; then
  echo -e "${YELLOW}All critical checks passed, but some warnings to review.${NC}"
  exit 0
else
  echo -e "${GREEN}All checks passed!${NC}"
  exit 0
fi
