#!/usr/bin/env bash
set -euo pipefail

# Relay add-repo — adds a code repo to an existing control plane.
#
# Usage:
#   relay add-repo --short <name> --nwo <org/repo> --local <path> \
#                  --tech <stack> --purpose <desc> --role <provider|consumer>

# ── Source shared library ─────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"
_LOG_CONTEXT="add-repo"

# ── Parse arguments ───────────────────────────────────────

SHORT=""
NWO=""
LOCAL=""
TECH=""
PURPOSE=""
ROLE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir)   CP_DIR="$2"; shift 2 ;;
    --short)    SHORT="$2"; shift 2 ;;
    --nwo)      NWO="$2"; shift 2 ;;
    --local)    LOCAL="$2"; shift 2 ;;
    --tech)     TECH="$2"; shift 2 ;;
    --purpose)  PURPOSE="$2"; shift 2 ;;
    --role)     ROLE="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: relay add-repo --short <name> --nwo <org/repo> --local <path>"
      echo "                      --tech <stack> --purpose <desc> --role <provider|consumer>"
      echo ""
      echo "Adds a code repo to an existing control plane."
      echo "Must be run from a control plane directory."
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown argument: $1${NC}" >&2
      exit 1
      ;;
  esac
done

# ── Validate required args ────────────────────────────────

MISSING=""
[ -z "$SHORT" ]   && MISSING="${MISSING}  --short\n"
[ -z "$NWO" ]     && MISSING="${MISSING}  --nwo\n"
[ -z "$LOCAL" ]   && MISSING="${MISSING}  --local\n"
[ -z "$TECH" ]    && MISSING="${MISSING}  --tech\n"
[ -z "$PURPOSE" ] && MISSING="${MISSING}  --purpose\n"
[ -z "$ROLE" ]    && MISSING="${MISSING}  --role\n"

if [ -n "$MISSING" ]; then
  echo -e "${RED}Missing required arguments:${NC}"
  echo -e "$MISSING"
  echo "Run 'relay add-repo --help' for usage."
  exit 1
fi

# ── Validate control plane ────────────────────────────────

if [ -z "${CP_DIR:-}" ]; then
  echo -e "${RED}Error: must be run from a control plane directory.${NC}"
  exit 1
fi

if [ ! -f "$CP_DIR/.relay-config" ]; then
  echo -e "${RED}Error: $CP_DIR/.relay-config not found.${NC}"
  exit 1
fi

# ── Check for duplicates ──────────────────────────────────

REPO_ALREADY_IN_CONFIG=false
if relay_config_repos | grep -q "^${SHORT}|"; then
  REPO_ALREADY_IN_CONFIG=true
fi

# ── Read control plane config ─────────────────────────────

RELAY_NWO=$(relay_config "relay-nwo" || echo "")
EXECUTION_MODE=$(relay_config "execution-mode" || echo "supervised")

if [ -z "$RELAY_NWO" ]; then
  echo -e "${RED}Error: relay-nwo not found in .relay-config.${NC}"
  exit 1
fi

# Expand ~ in local path
LOCAL="${LOCAL/#\~/$HOME}"

# Display name
DISPLAY_NAME="$(echo "$SHORT" | python3 -c "import sys; print(sys.stdin.read().strip().capitalize())")"

echo -e "${GREEN}Adding repo:${NC} ${BOLD}${SHORT}${NC} (${NWO})"
echo ""

# ══════════════════════════════════════════════════════════
# Phase 1: Update control plane
# ══════════════════════════════════════════════════════════

log "Updating control plane..."

# ── 1. Append to .relay-config repos block ────────────────

if [ "$REPO_ALREADY_IN_CONFIG" = true ]; then
  log "Repo '${SHORT}' already in .relay-config — skipping"
else
  python3 -c "
import sys
config_file = sys.argv[1]
short = sys.argv[2]
nwo = sys.argv[3]

with open(config_file) as f:
    lines = f.readlines()

# Find the repos: block and append after its last indented line
in_repos = False
insert_at = len(lines)
for i, line in enumerate(lines):
    if line.strip() == 'repos:':
        in_repos = True
        continue
    if in_repos:
        if line.startswith('  ') and ':' in line:
            insert_at = i + 1
        elif not line.startswith(' '):
            insert_at = i
            break

lines.insert(insert_at, f'  {short}: {nwo}\n')

with open(config_file, 'w') as f:
    f.writelines(lines)
" "$CP_DIR/.relay-config" "$SHORT" "$NWO"

  log_ok "Updated .relay-config"
fi

# ── 2. Append to service-catalog.md ───────────────────────

CATALOG="$CP_DIR/.relay/service-catalog.md"
if [ -f "$CATALOG" ] && grep -q "^## ${SHORT}$" "$CATALOG" 2>/dev/null; then
  log "Repo '${SHORT}' already in service-catalog.md — skipping"
else
  SERVICE_ENTRY="\n## ${SHORT}\n\n- **Repo:** ${NWO}\n- **Local:** \`${LOCAL}\`\n- **Tech:** ${TECH}\n- **Contract:** contracts/tasks-api.json (${ROLE})\n- **Purpose:** ${PURPOSE}\n"
  if [ -f "$CATALOG" ]; then
    echo -e "$SERVICE_ENTRY" >> "$CATALOG"
  else
    echo -e "# Service Catalog\n${SERVICE_ENTRY}" > "$CATALOG"
  fi
  log_ok "Updated service-catalog.md"
fi

# ── 3. Update CLAUDE.md repo table ────────────────────────

CLAUDE_CP="$CP_DIR/CLAUDE.md"
NEW_TABLE_ROW="| ${DISPLAY_NAME} | \`${NWO}\` | \`${LOCAL}\` |"
if [ -f "$CLAUDE_CP" ] && grep -qF "\`${NWO}\`" "$CLAUDE_CP" 2>/dev/null; then
  log "Repo already in CLAUDE.md table — skipping"
elif [ -f "$CLAUDE_CP" ]; then
  python3 -c "
import sys

claude_file = sys.argv[1]
new_row = sys.argv[2]

with open(claude_file) as f:
    lines = f.readlines()

# Find the repo table and insert before the Control Plane row or the sentinel line
inserted = False
for i, line in enumerate(lines):
    # Insert before the Control Plane row if it exists
    if '| Control Plane |' in line:
        lines.insert(i, new_row + '\n')
        inserted = True
        break
    # Or before the 'See service-catalog' sentinel
    if line.startswith('See \`service-catalog.md\`') or line.startswith('See '):
        # Walk back to find last table row
        for j in range(i - 1, -1, -1):
            if lines[j].strip().startswith('|'):
                lines.insert(j + 1, new_row + '\n')
                inserted = True
                break
        break

if not inserted:
    # Fallback: just append (shouldn't happen with well-formed CLAUDE.md)
    lines.append(new_row + '\n')

with open(claude_file, 'w') as f:
    f.writelines(lines)
" "$CLAUDE_CP" "$NEW_TABLE_ROW"

  log_ok "Updated CLAUDE.md repo table"
else
  log_warn "CLAUDE.md not found in control plane — skipping table update"
fi

# ══════════════════════════════════════════════════════════
# Phase 2: Configure code repo
# ══════════════════════════════════════════════════════════

if [ ! -d "$LOCAL" ]; then
  # Try to clone if gh is available
  if [ -n "$NWO" ] && command -v gh &>/dev/null; then
    log "Local path not found: $LOCAL — attempting clone..."
    mkdir -p "$(dirname "$LOCAL")"
    if gh repo clone "$NWO" "$LOCAL" 2>/dev/null; then
      log_ok "Cloned $NWO to $LOCAL"
    else
      log_warn "Could not clone $NWO — control plane updated, but code repo setup skipped."
      echo -e "  ${DIM}Clone the repo manually, then re-run:${NC}"
      echo -e "  ${DIM}  relay add-repo --short $SHORT --nwo $NWO --local $LOCAL --tech \"$TECH\" --purpose \"$PURPOSE\" --role $ROLE${NC}"
      exit 0
    fi
  else
    log_warn "Local path not found: $LOCAL — control plane updated, but code repo setup skipped."
    echo -e "  ${DIM}Clone the repo, then re-run this command to configure it.${NC}"
    exit 0
  fi
fi

log "Configuring code repo at $LOCAL..."

# ── 4. Create .relay/config.md ────────────────────────────

mkdir -p "$LOCAL/.relay"
cat > "$LOCAL/.relay/config.md" << RELAY_CONFIG
---
control-plane: ${RELAY_NWO}
control-plane-path: ${CP_DIR}
repo-name: ${SHORT}
execution-mode: ${EXECUTION_MODE}
---
RELAY_CONFIG

log_ok "Created .relay/config.md"

# ── 5. Create .relay/relay shim ───────────────────────────

cat > "$LOCAL/.relay/relay" << 'RELAY_SHIM'
#!/usr/bin/env bash
set -euo pipefail
SHIM_DIR="$(cd "$(dirname "$0")" && pwd)"
CP_PATH=$(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    for line in f:
        m = re.match(r'^control-plane-path:\s*(.+)', line)
        if m: print(m.group(1).strip()); break
" "$SHIM_DIR/config.md" 2>/dev/null)
if [ -z "$CP_PATH" ] || [ ! -d "$CP_PATH" ]; then
  echo "Error: control-plane-path not found or invalid in .relay/config.md" >&2
  exit 1
fi
RELAY_PATH=$(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    for line in f:
        m = re.match(r'^relay-path:\s*(.+)', line)
        if m: print(m.group(1).strip()); break
" "$CP_PATH/.relay-config" 2>/dev/null)
if [ -z "$RELAY_PATH" ] || [ ! -f "$RELAY_PATH/relay" ]; then
  echo "Error: relay-path not found or invalid in $CP_PATH/.relay-config" >&2
  exit 1
fi
exec "$RELAY_PATH/relay" "$@"
RELAY_SHIM
chmod +x "$LOCAL/.relay/relay"

log_ok "Created .relay/relay shim"

# ── 6. Add .relay/relay to .gitignore ─────────────────────

GITIGNORE="$LOCAL/.gitignore"
if [ -f "$GITIGNORE" ]; then
  if ! grep -qxF '.relay/relay' "$GITIGNORE" 2>/dev/null; then
    echo '.relay/relay' >> "$GITIGNORE"
  fi
else
  echo '.relay/relay' > "$GITIGNORE"
fi

# ── 7. Content DNS: scaffold manifest and rules directory ─

if [ ! -f "$LOCAL/.relay/manifest.md" ] && [ -f "$RELAY_DIR/process/templates/manifest.md.tmpl" ]; then
  sed "s/{{TIER}}/code-repo/" "$RELAY_DIR/process/templates/manifest.md.tmpl" > "$LOCAL/.relay/manifest.md"
  log_ok "Created .relay/manifest.md (Content DNS)"
fi
mkdir -p "$LOCAL/.relay/rules"

# Compile constitution if relay manifest exists
if [ -f "$RELAY_DIR/process/manifest.md" ]; then
  python3 "$RELAY_DIR/process/scripts/compile-constitution.py" "$LOCAL" >/dev/null 2>&1 || true
  if [ -f "$LOCAL/.relay/constitution.md" ]; then
    log_ok "Compiled .relay/constitution.md"
  fi
fi

# ── 8. Cloud-agent workflow (if cloud mode) ───────────────

if [ "$EXECUTION_MODE" = "cloud" ]; then
  mkdir -p "$LOCAL/.github/workflows"
  cat > "$LOCAL/.github/workflows/cloud-agent.yml" << 'CLOUD_WORKFLOW'
name: Agent Runner
on:
  repository_dispatch:
    types: [agent-task-available]

jobs:
  agent:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        instance: ${{ fromJson(github.event.client_payload.instances) }}
    steps:
      - uses: actions/checkout@v6
      - name: Install Claude CLI
        run: npm install -g @anthropic-ai/claude-code
      - name: Run agent
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          RELAY_PAT: ${{ secrets.RELAY_PAT }}
        run: |
          git clone https://${RELAY_PAT}@github.com/${{ github.event.client_payload.relay_nwo }}.git /tmp/control-plane
          /tmp/control-plane/scripts/cloud-agent.sh --repo $(basename ${{ github.repository }})
CLOUD_WORKFLOW
  log_ok "Created .github/workflows/cloud-agent.yml"
fi

# ── 9. Append Relay section to code repo CLAUDE.md ────────

CLAUDE_MD_PATH="$LOCAL/CLAUDE.md"
CP_BASENAME="$(basename "$CP_DIR")"

RELAY_SECTION="## Agent Workflow (Git Queue)

Work is coordinated via the Git-native task queue in the control plane at \`../${CP_BASENAME}/queue/\`.

### Pick up work

Follow the relay workflow. It handles:
- Pulling the latest queue state from the control plane
- Finding the highest-priority ready task for this repo
- Claiming it via atomic branch push
- Loading the task spec so you can start implementing

To find the relay workflow path, read \`.relay/config.md\` for the \`control-plane-path\`, then read that directory's \`.relay-config\` for the \`relay-path\`. The workflow is at \`<relay-path>/process/workflows/relay.md\`.

### Quick reference

\`\`\`bash
# Refresh queue
git -C ../${CP_BASENAME} pull --ff-only

# See what's claimed
git ls-remote origin 'refs/heads/agent/*'
\`\`\`

### Contract
API contract: \`../${CP_BASENAME}/contracts/tasks-api.json\`

### Discovered sub-work
If you discover additional work needed, create a new task file in \`../${CP_BASENAME}/queue/<feature>/\` following the task template.

## Relay

This repo is managed by the Relay framework. The control plane is at \`${RELAY_NWO}\`.

- **Control plane:** https://github.com/${RELAY_NWO}
- **Config:** \`.relay/config.md\`
- **Task queue:** Control plane \`queue/\` directory
- **Contracts:** Control plane \`contracts/\` directory"

if [ -f "$CLAUDE_MD_PATH" ]; then
  if ! grep -q "This repo is managed by the Relay framework" "$CLAUDE_MD_PATH" 2>/dev/null; then
    echo "" >> "$CLAUDE_MD_PATH"
    echo "$RELAY_SECTION" >> "$CLAUDE_MD_PATH"
    log_ok "Appended Relay section to CLAUDE.md"
  else
    log "CLAUDE.md already has Relay section — skipping"
  fi
else
  echo "$RELAY_SECTION" > "$CLAUDE_MD_PATH"
  log_ok "Created CLAUDE.md with Relay section"
fi

# ══════════════════════════════════════════════════════════
# Phase 3: Post-setup
# ══════════════════════════════════════════════════════════

# ── 10. Run doctor ────────────────────────────────────────

DOCTOR_SCRIPT="$RELAY_DIR/process/scripts/doctor.sh"
if [ -f "$DOCTOR_SCRIPT" ]; then
  log "Running health check..."
  "$DOCTOR_SCRIPT" --cp-dir "$CP_DIR" 2>/dev/null || log_warn "Doctor reported issues — run 'relay doctor' for details"
fi

# ── 11. Generate repo manifest ────────────────────────────

BRIEF_SCRIPT="$RELAY_DIR/process/scripts/generate-brief.sh"
if [ -f "$BRIEF_SCRIPT" ]; then
  log "Generating repo manifest for ${SHORT}..."
  "$BRIEF_SCRIPT" --cp-dir "$CP_DIR" "$SHORT" "$LOCAL" 2>/dev/null || log_warn "Could not generate repo manifest — run 'relay generate-brief $SHORT $LOCAL' manually"
fi

# ── 12. Summary ───────────────────────────────────────────

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Repo added successfully!                          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Repo:${NC}            ${SHORT} (${NWO})"
echo -e "  ${BOLD}Local:${NC}           ${LOCAL}"
echo -e "  ${BOLD}Execution mode:${NC}  ${EXECUTION_MODE}"
echo ""
echo -e "  ${BOLD}Control plane changes:${NC}"
echo -e "    ${DIM}• .relay-config — added repo entry${NC}"
echo -e "    ${DIM}• service-catalog.md — added service entry${NC}"
echo -e "    ${DIM}• CLAUDE.md — added repo table row${NC}"
echo ""
echo -e "  ${BOLD}Code repo changes:${NC}"
echo -e "    ${DIM}• .relay/config.md — control plane pointer${NC}"
echo -e "    ${DIM}• .relay/relay — CLI shim (gitignored)${NC}"
echo -e "    ${DIM}• CLAUDE.md — Relay workflow section${NC}"
echo ""
echo -e "  ${BOLD}Next steps:${NC}"
echo -e "  ${GREEN}1.${NC} Review changes in both repos"
echo -e "  ${GREEN}2.${NC} Commit control plane changes"
echo -e "     ${DIM}cd $CP_DIR && git add .relay-config .relay/service-catalog.md CLAUDE.md && git commit -m 'chore: add $SHORT repo'${NC}"
echo -e "  ${GREEN}3.${NC} Commit code repo changes"
echo -e "     ${DIM}cd $LOCAL && git checkout -b relay-setup && git add .relay/ CLAUDE.md && git commit -m 'chore: add Relay config' && git push${NC}"
