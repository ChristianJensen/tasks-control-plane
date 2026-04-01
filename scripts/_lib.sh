#!/usr/bin/env bash
# Shared functions for Relay scripts. Source this, don't execute it.

# ── Colors ──────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

# ── Logging (parameterized by context label) ────────────────
_LOG_CONTEXT="${_LOG_CONTEXT:-relay}"
log()      { echo -e "${DIM}[$(date +%H:%M:%S)]${NC} ${BLUE}[$_LOG_CONTEXT]${NC} $*"; }
log_ok()   { echo -e "${DIM}[$(date +%H:%M:%S)]${NC} ${GREEN}[$_LOG_CONTEXT]${NC} $*"; }
log_warn() { echo -e "${DIM}[$(date +%H:%M:%S)]${NC} ${YELLOW}[$_LOG_CONTEXT]${NC} $*"; }
log_err()  { echo -e "${DIM}[$(date +%H:%M:%S)]${NC} ${RED}[$_LOG_CONTEXT]${NC} $*"; }

# ── RELAY_DIR resolution ────────────────────────────────────
# RELAY_DIR = the Relay framework repo (scripts, skills, templates).
# Derived from this script's own location: scripts live at RELAY_DIR/process/scripts/.
# Callers can override RELAY_DIR before sourcing.
if [ -z "${RELAY_DIR:-}" ]; then
  _SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  RELAY_DIR="$(cd "$_SCRIPTS_DIR/../.." && pwd)"
  unset _SCRIPTS_DIR
fi

# ── CP_DIR resolution ──────────────────────────────────────
# CP_DIR = the control plane repo (data: queue, features, contracts, service-catalog).
# Must be set by the caller (via --cp-dir flag or CP_DIR env var).

# ── .relay-config reader ───────────────────────────────────
# Reads key-value pairs from CP_DIR/.relay-config (YAML-like format).
# Usage: relay_config "relay-nwo"  → prints the value
relay_config() {
  local key="$1"
  local config_file="${CP_DIR:-.}/.relay-config"
  if [ ! -f "$config_file" ]; then
    return 1
  fi
  python3 -c "
import sys, re
key = sys.argv[1]
with open(sys.argv[2]) as f:
    for line in f:
        m = re.match(r'^' + re.escape(key) + r':\s*(.+)', line)
        if m:
            print(m.group(1).strip())
            sys.exit(0)
sys.exit(1)
" "$key" "$config_file" 2>/dev/null
}

# ── .relay-config repos reader ─────────────────────────────
# Outputs: short|nwo (one line per repo listed under 'repos:' in .relay-config)
relay_config_repos() {
  local config_file="${CP_DIR:-.}/.relay-config"
  if [ ! -f "$config_file" ]; then
    return 1
  fi
  python3 -c "
import sys, re
in_repos = False
with open(sys.argv[1]) as f:
    for line in f:
        if re.match(r'^repos:\s*$', line):
            in_repos = True
            continue
        if in_repos:
            m = re.match(r'^  (\S+):\s*(\S+)', line)
            if m:
                print(f'{m.group(1)}|{m.group(2)}')
            elif not line.startswith(' '):
                break
" "$config_file" 2>/dev/null
}

# ── Known status / phase names ────────────────────────────────
# Task statuses (directories under queue/<feature>/)
_TASK_STATUSES="pending ready in-progress done blocked paused cancelled"
# Feature phases (directories under features/)
_FEATURE_PHASES="draft active completed cancelled"

# ── Status from path ──────────────────────────────────────────
# Returns the parent directory name (the status/phase segment).
status_from_path() {
  local file_path="$1"
  basename "$(dirname "$file_path")"
}

# ── Feature slug from task path ──────────────────────────────
# queue/<feature>/<status>/wave-*.md → <feature>
feature_from_task_path() {
  local file_path="$1"
  basename "$(dirname "$(dirname "$file_path")")"
}

# ── Task status update (directory-based with frontmatter sync) ─
# Moves the task file to the new status directory via git mv.
# Also updates frontmatter status: field for human readability.
# Echoes the NEW file path (callers must capture this).
update_task_status() {
  local file_path="$1" new_status="$2"
  local dir_base new_dir new_path cp

  cp="${CP_DIR:-$RELAY_DIR}"
  dir_base="$(dirname "$(dirname "$file_path")")"
  new_dir="${dir_base}/${new_status}"
  new_path="${new_dir}/$(basename "$file_path")"

  # Create destination directory
  mkdir -p "$new_dir"

  # Move the file (git mv stages automatically)
  if [ "$file_path" != "$new_path" ]; then
    git -C "$cp" mv "$file_path" "$new_path" 2>/dev/null \
      || mv "$file_path" "$new_path" 2>/dev/null
  fi

  # Verify the move succeeded
  if [ ! -f "$new_path" ]; then
    echo "ERROR: failed to move task file to ${new_status}/ (file name too long?)" >&2
    echo "  src: $file_path" >&2
    echo "  dst: $new_path" >&2
    echo "$file_path"
    return 1
  fi

  # Sync frontmatter status: field for human readability
  sed -i '' -E "s/^status:[[:space:]]+.*/status: ${new_status}/" "$new_path" 2>/dev/null \
    || sed -i "s/^status:[[:space:]]\+.*/status: ${new_status}/" "$new_path" 2>/dev/null

  echo "$new_path"
}

# ── Auto-promote next wave ──────────────────────────────────
# When all tasks in a wave are done, automatically promote pending
# tasks from the next wave to ready.
# Usage: auto_promote_next_wave <feature> <completed_wave>
auto_promote_next_wave() {
  local feature="$1" completed_wave="$2"
  local cp="${CP_DIR:-$RELAY_DIR}"
  local queue_dir="$cp/queue/$feature"

  # Check: any ready or in-progress tasks left in this wave?
  local remaining=0
  for f in "$queue_dir"/ready/wave-${completed_wave}-*.md \
           "$queue_dir"/in-progress/wave-${completed_wave}-*.md; do
    [ -f "$f" ] && remaining=$((remaining + 1))
  done
  [ "$remaining" -gt 0 ] && return 0  # wave not complete yet

  # Find next wave number and promote pending tasks
  local next_wave=$((completed_wave + 1))
  local promoted=0
  for f in "$queue_dir"/pending/wave-${next_wave}-*.md; do
    [ -f "$f" ] || continue
    update_task_status "$f" "ready" >/dev/null
    promoted=$((promoted + 1))
  done

  if [ "$promoted" -gt 0 ]; then
    log "Auto-promoted $promoted wave-$next_wave task(s) to ready"
    git -C "$cp" add -A "queue/$feature/" 2>/dev/null
    git -C "$cp" commit -m "promote: $feature wave $next_wave auto-promoted ($promoted tasks)" 2>/dev/null
  fi
}

# ── Feature phase update (directory-based with frontmatter sync) ─
# Moves feature spec to the new phase directory via git mv.
# Also updates frontmatter lifecycle: field.
# Echoes the NEW file path.
update_feature_phase() {
  local file_path="$1" new_phase="$2"
  local features_root new_dir new_path cp

  cp="${CP_DIR:-$RELAY_DIR}"
  features_root="$(dirname "$(dirname "$file_path")")"
  new_dir="${features_root}/${new_phase}"
  new_path="${new_dir}/$(basename "$file_path")"

  mkdir -p "$new_dir"

  if [ "$file_path" != "$new_path" ]; then
    git -C "$cp" mv "$file_path" "$new_path" 2>/dev/null \
      || mv "$file_path" "$new_path"
  fi

  # Sync frontmatter lifecycle: field
  sed -i '' -E "s/^lifecycle:[[:space:]]+.*/lifecycle: ${new_phase}/" "$new_path" 2>/dev/null \
    || sed -i "s/^lifecycle:[[:space:]]\+.*/lifecycle: ${new_phase}/" "$new_path" 2>/dev/null

  echo "$new_path"
}

# ── Find feature file across phase directories ───────────────
# Searches features/<phase>/<name>-feature.md and features/<phase>/<name>-bug.md
# Echoes the path if found, empty string otherwise.
find_feature_file() {
  local feature_name="$1"
  local features_dir="${CP_DIR:-$RELAY_DIR}/features"
  local f

  for phase in $_FEATURE_PHASES; do
    for suffix in feature bug; do
      f="${features_dir}/${phase}/${feature_name}-${suffix}.md"
      if [ -f "$f" ]; then
        echo "$f"
        return 0
      fi
    done
  done

  # Also check bugs/ directory
  local bugs_dir
  bugs_dir="$(dirname "$features_dir")/bugs"
  if [ -d "$bugs_dir" ]; then
    for phase in $_FEATURE_PHASES; do
      local f="$bugs_dir/$phase/${feature_name}-bug.md"
      [ -f "$f" ] && echo "$f" && return 0
    done
  fi

  echo ""
}

# ── Branch slug derivation ──────────────────────────────────
derive_branch_slug() {
  local file_path="$1" repo_name="$2"
  local feature_slug filename wave_num task_slug task_type prefix
  feature_slug="$(feature_from_task_path "$file_path")"
  filename="$(basename "$file_path" .md)"
  wave_num=$(echo "$filename" | sed -E 's/^wave-([0-9]+)-.*/\1/')
  task_slug=$(echo "$filename" | sed -E "s/^wave-[0-9]+-${repo_name}-//")

  # Read task type from frontmatter to determine branch prefix
  task_type=$(sed -n '/^---$/,/^---$/{ s/^type:[[:space:]]*//p; }' "$file_path" 2>/dev/null | head -1)
  if [ "$task_type" = "bug" ]; then
    prefix="fix"
  else
    prefix="agent"
  fi
  echo "${prefix}/${feature_slug}-w${wave_num}-${task_slug}"
}

# ── Claimed branches ────────────────────────────────────────
get_claimed_branches() {
  local repo_dir="$1"
  git -C "$repo_dir" ls-remote --heads origin 'refs/heads/agent/*' 'refs/heads/fix/*' 2>/dev/null \
    | awk '{print $2}' | sed 's|refs/heads/||'
}

# ── Control plane push (simple) ──────────────────────────────
push_cp() {
  local cp="${CP_DIR:-$RELAY_DIR}"
  git -C "$cp" push 2>/dev/null || true
}
# ── Control plane push (retry with rebase — for concurrent use) ──
push_cp_with_retry() {
  local cp="${CP_DIR:-$RELAY_DIR}"
  for i in 1 2 3; do
    git -C "$cp" pull --rebase 2>/dev/null || {
      git -C "$cp" rebase --abort 2>/dev/null || true
    }
    if git -C "$cp" push 2>/dev/null; then
      return 0
    fi
    log_warn "Control plane push attempt $i failed, retrying..."
    sleep 1
  done
  log_err "Control plane push failed after 3 attempts — task status may be stale"
  return 1
}
# ── Service catalog parser ──────────────────────────────────
# Outputs: name|nwo|local_path (one line per repo)
parse_service_catalog() {
  local catalog="${1:-${CP_DIR:-$RELAY_DIR}/.relay/service-catalog.md}"
  [ -f "$catalog" ] || return 0
  python3 -c "
import re, sys
content = open(sys.argv[1]).read()
for m in re.finditer(r'## (\S+)\n.*?\*\*Repo:\*\*\s*(\S+).*?\*\*Local:\*\*\s*\x60([^\x60]+)\x60', content, re.DOTALL):
    print(f'{m.group(1)}|{m.group(2)}|{m.group(3)}')
" "$catalog"
}

# ── Frontmatter helpers (feature/bug spec) ────────────────────
# These require FEATURE_FILE to be set by the caller.

get_feature_field() {
  # Extract a field from feature spec YAML frontmatter
  local field="$1"
  python3 -c "
import re, sys
with open('$FEATURE_FILE') as f:
    content = f.read()
m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
if m:
    match = re.search(r'^${field}:\s*(.+)', m.group(1), re.MULTILINE)
    if match:
        val = match.group(1).strip().strip('\"').strip(\"'\")
        print(val)
"
}

set_feature_field() {
  # Update a field in feature spec YAML frontmatter
  local field="$1"
  local value="$2"
  python3 -c "
import re
with open('$FEATURE_FILE') as f:
    content = f.read()
m = re.match(r'^(---\s*\n)(.*?)(\n---)', content, re.DOTALL)
if m:
    front = m.group(2)
    if re.search(r'^${field}:', front, re.MULTILINE):
        front = re.sub(r'^${field}:.*$', '${field}: ${value}', front, flags=re.MULTILINE)
    else:
        front += '\n${field}: ${value}'
    content = m.group(1) + front + m.group(3) + content[m.end():]
with open('$FEATURE_FILE', 'w') as f:
    f.write(content)
"
}

# ── Task claim metadata ──────────────────────────────────────
set_task_claim() {
  local file_path="$1" claimed_by="$2" claimed_at="$3" claimed_on="$4"
  python3 -c "
import re
with open('$file_path') as f:
    content = f.read()
m = re.match(r'^(---\s*\n)(.*?)(\n---)', content, re.DOTALL)
if m:
    front = m.group(2)
    for field, value in [('claimed-by', '$claimed_by'), ('claimed-at', '$claimed_at'), ('claimed-on', '$claimed_on')]:
        if re.search(r'^' + field + ':', front, re.MULTILINE):
            front = re.sub(r'^' + field + ':.*$', field + ': ' + value, front, flags=re.MULTILINE)
        else:
            front += '\n' + field + ': ' + value
    content = m.group(1) + front + m.group(3) + content[m.end():]
with open('$file_path', 'w') as f:
    f.write(content)
"
}

set_task_pr_info() {
  local file_path="$1" pr_url="$2" pr_number="$3"
  python3 -c "
import re
with open('$file_path') as f:
    content = f.read()
m = re.match(r'^(---\s*\n)(.*?)(\n---)', content, re.DOTALL)
if m:
    front = m.group(2)
    for field, value in [('pr-url', '$pr_url'), ('pr-number', '$pr_number')]:
        if re.search(r'^' + field + ':', front, re.MULTILINE):
            front = re.sub(r'^' + field + ':.*$', field + ': ' + value, front, flags=re.MULTILINE)
        else:
            front += '\n' + field + ': ' + value
    content = m.group(1) + front + m.group(3) + content[m.end():]
with open('$file_path', 'w') as f:
    f.write(content)
"
}

get_task_pr_number() {
  local file_path="$1"
  sed -n '/^---$/,/^---$/{ s/^pr-number:[[:space:]]*//p; }' "$file_path" 2>/dev/null \
    | head -1 | sed 's/^"//;s/"$//'
}

# Resolve repo NWO from target-repo name via service catalog
resolve_repo_nwo() {
  local target_repo="$1"
  while IFS='|' read -r _name _nwo _local; do
    if [ "$_name" = "$target_repo" ]; then
      echo "$_nwo"
      return
    fi
  done < <(parse_service_catalog)
}

# ── Control plane HEAD SHA ────────────────────────────────────
cp_head_sha() {
  git -C "${CP_DIR:-.}" rev-parse HEAD 2>/dev/null || echo "main"
}

# ── Feature total-budget envelope ─────────────────────────────
# Returns the remaining budget for a feature based on total-budget minus
# sum of cost-usd across all sibling tasks. Returns empty string if no
# total-budget is set (no envelope constraint).

resolve_remaining_budget() {
  local queue_file="$1"
  local feature_slug feature_file total_budget feature_queue_dir

  # Get feature slug from task path: queue/<feature>/<status>/wave-*.md
  feature_slug=$(feature_from_task_path "$queue_file")
  if [ -z "$feature_slug" ]; then
    echo ""
    return
  fi

  # Find feature spec file
  feature_file=$(find_feature_file "$feature_slug")
  if [ -z "$feature_file" ] || [ ! -f "$feature_file" ]; then
    echo ""
    return
  fi

  # Read total-budget from feature spec
  total_budget=$(sed -n '/^---$/,/^---$/p' "$feature_file" | grep '^total-budget:' | sed 's/^total-budget:[[:space:]]*//' | tr -d '"' | sed 's/[[:space:]]*#.*//')
  if [ -z "$total_budget" ]; then
    echo ""
    return
  fi

  # Sum cost-usd from all sibling task files across all status directories
  feature_queue_dir="$(dirname "$(dirname "$queue_file")")"
  local spent
  spent=$(python3 -c "
import os, re, sys

feature_dir = sys.argv[1]
total = 0.0
for status_dir in os.listdir(feature_dir):
    status_path = os.path.join(feature_dir, status_dir)
    if not os.path.isdir(status_path):
        continue
    for f in os.listdir(status_path):
        if not f.endswith('.md'):
            continue
        fpath = os.path.join(status_path, f)
        with open(fpath) as fh:
            content = fh.read()
        m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if m:
            cost_match = re.search(r'^cost-usd:\s*(.+)', m.group(1), re.MULTILINE)
            if cost_match:
                val = cost_match.group(1).strip().strip('\"').strip(\"'\")
                try:
                    total += float(val)
                except ValueError:
                    pass
print(f'{total:.4f}')
" "$feature_queue_dir" 2>/dev/null || echo "0.0000")

  # Calculate remaining
  local remaining
  remaining=$(python3 -c "
import sys
total = float(sys.argv[1])
spent = float(sys.argv[2])
remaining = total - spent
print(f'{remaining:.4f}')
" "$total_budget" "$spent" 2>/dev/null || echo "0.0000")

  echo "$remaining"
}

# ── Task counting helper ──────────────────────────────────────
# Requires QUEUE_DIR to be set by the caller.

count_tasks_by_status() {
  # Count task files in the given status subdirectory
  local status="$1"
  local count=0
  local status_dir="${QUEUE_DIR}/${status}"
  if [ -d "$status_dir" ]; then
    for f in "$status_dir"/wave-*.md; do
      [ -f "$f" ] || continue
      count=$((count + 1))
    done
  fi
  echo "$count"
}
