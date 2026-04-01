#!/usr/bin/env bash
set -euo pipefail

# Relay Status — cross-references queue files, git branches, and GitHub PRs
# to show a unified view of task status with mismatch warnings.
#
# Usage:
#   status.sh [--cp-dir <path>] [<feature>] [--fix] [--json]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Parse CLI flags
FIX_MODE=false
JSON_MODE=false
FEATURE_FILTER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir)
      export CP_DIR="$2"
      shift 2
      ;;
    --fix)
      FIX_MODE=true
      shift
      ;;
    --json)
      JSON_MODE=true
      shift
      ;;
    -*)
      echo "Usage: relay status [<feature>] [--fix] [--json]"
      exit 1
      ;;
    *)
      FEATURE_FILTER="$1"
      shift
      ;;
  esac
done

# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
_LOG_CONTEXT="status"

QUEUE_DIR="${CP_DIR:-$RELAY_DIR}/queue"
FEATURES_DIR="${CP_DIR:-$RELAY_DIR}/features"
PARSE_QUEUE="$SCRIPT_DIR/_parse-queue.py"

# Temp file for accumulating JSON across repos
JSON_TMP=$(mktemp)
echo "[]" > "$JSON_TMP"
trap 'rm -f "$JSON_TMP"' EXIT

# Track which features we've already printed headers for (text mode)
SEEN_FEATURES_FILE=$(mktemp)
trap 'rm -f "$JSON_TMP" "$SEEN_FEATURES_FILE"' EXIT

# Read service catalog
while IFS='|' read -r repo_name repo_nwo repo_local; do
  [ -z "$repo_name" ] && continue

  # Get all tasks for this repo
  TASKS_JSON=$(python3 "$PARSE_QUEUE" "$QUEUE_DIR" "$repo_name" --status all 2>/dev/null || true)
  TASKS_JSON="${TASKS_JSON#"${TASKS_JSON%%[![:space:]]*}"}"
  [ -z "$TASKS_JSON" ] && TASKS_JSON="[]"

  # Skip repos with no tasks
  if [ "$TASKS_JSON" = "[]" ]; then
    continue
  fi

  # Get remote branches (agent/* and fix/*)
  BRANCHES=""
  if [ -d "$repo_local" ]; then
    BRANCHES=$(git -C "$repo_local" ls-remote --heads origin 'refs/heads/agent/*' 'refs/heads/fix/*' 2>/dev/null \
      | awk '{print $2}' | sed 's|refs/heads/||' || true)
  fi

  # Parse tasks and cross-reference with branches/PRs
  python3 "$SCRIPT_DIR/_status-render.py" "$TASKS_JSON" "$BRANCHES" "$repo_local" "$repo_nwo" "$repo_name" "$FEATURE_FILTER" "$FIX_MODE" "$JSON_MODE" "${CP_DIR:-$RELAY_DIR}" "$JSON_TMP" "$SEEN_FEATURES_FILE"

done < <(parse_service_catalog)

# In JSON mode, output the accumulated result at the end
if [ "$JSON_MODE" = true ]; then
  cat "$JSON_TMP"
elif [ "$(cat "$JSON_TMP")" = "[]" ]; then
  if [ -n "$FEATURE_FILTER" ]; then
    echo "No tasks found for feature '$FEATURE_FILTER'."
  else
    echo "No tasks found."
  fi
fi

# ── Feature overview & actionable suggestions ──────────────────────────
# Show feature listing when no feature filter, and suggestions always (text mode only)
if [ "$JSON_MODE" != true ]; then
  python3 -c "
import json, os, re, sys, glob

cp_dir = sys.argv[1]
json_tmp = sys.argv[2]
feature_filter = sys.argv[3]

# Colors
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
BLUE = '\033[0;34m'
DIM = '\033[2m'
BOLD = '\033[1m'
NC = '\033[0m'

features_dir = os.path.join(cp_dir, 'features')
bugs_dir = os.path.join(cp_dir, 'bugs')
queue_dir = os.path.join(cp_dir, 'queue')

# Load accumulated task data
with open(json_tmp) as f:
    all_tasks = json.load(f)

if not all_tasks and feature_filter:
    sys.exit(0)

def read_field(filepath, field):
    try:
        with open(filepath) as f:
            content = f.read()
        m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if m:
            match = re.search(r'^' + field + r':\s*(.+)', m.group(1), re.MULTILINE)
            if match:
                val = match.group(1).strip().strip(chr(34)).strip(chr(39))
                val = re.sub(r'\s+#.*$', '', val)
                return val
    except Exception:
        pass
    return ''

# Gather feature info
feature_stats = {}  # feat_name -> {done, total, ready, pending, in_progress, guided_ready, lifecycle, execution}

TASK_STATUS_DIRS = {'pending', 'ready', 'in-progress', 'done', 'blocked', 'paused', 'cancelled'}

def scan_features():
    \"\"\"Scan features from phase directories.\"\"\"
    seen = set()
    results = []
    for search_dir in (features_dir, bugs_dir):
        if not os.path.isdir(search_dir):
            continue
        for phase in ('active', 'draft', 'completed', 'cancelled'):
            phase_dir = os.path.join(search_dir, phase)
            if not os.path.isdir(phase_dir):
                continue
            globs = [os.path.join(phase_dir, '*-bug.md')]
            if search_dir == features_dir:
                globs.insert(0, os.path.join(phase_dir, '*-feature.md'))
            for spec in sorted([f for g in globs for f in glob.glob(g)]):
                fname = os.path.basename(spec)
                for suffix in ('-feature.md', '-bug.md'):
                    if fname.endswith(suffix):
                        fname = fname[:-len(suffix)]
                        break
                if fname not in seen:
                    seen.add(fname)
                    results.append((fname, spec, phase))
    return results

for fname, spec, phase_or_lifecycle in scan_features():
    lifecycle = phase_or_lifecycle
    # Map phase dir names to lifecycle values
    if lifecycle in ('active', 'draft', 'completed', 'cancelled'):
        pass
    feature_exec = read_field(spec, 'execution') or 'supervised'

    if lifecycle not in ('active', 'live-dev', 'live-staging', 'live-prod'):
        continue

    feat_queue = os.path.join(queue_dir, fname)
    pending = ready = in_progress = done_count = guided_ready = awaiting_review = 0
    review_urls = []

    if os.path.isdir(feat_queue):
        for tf in glob.glob(os.path.join(feat_queue, '*', 'wave-*.md')):
            parent = os.path.basename(os.path.dirname(tf))
            status = parent if parent in TASK_STATUS_DIRS else ''
            exec_mode = read_field(tf, 'execution') or ''
            if not exec_mode:
                exec_mode = feature_exec
            if status == 'pending':
                pending += 1
            elif status == 'ready':
                ready += 1
                if exec_mode == 'guided':
                    guided_ready += 1
            elif status == 'in-progress':
                in_progress += 1
                pr_url_val = read_field(tf, 'pr-url')
                if pr_url_val:
                    awaiting_review += 1
                    review_urls.append(pr_url_val)
            elif status == 'done':
                done_count += 1

    total = pending + ready + in_progress + done_count
    if total == 0:
        continue

    feature_stats[fname] = {
        'done': done_count,
        'total': total,
        'ready': ready,
        'pending': pending,
        'in_progress': in_progress,
        'guided_ready': guided_ready,
        'awaiting_review': awaiting_review,
        'review_urls': review_urls,
        'lifecycle': lifecycle,
        'execution': feature_exec,
    }

# Feature overview (only when no feature filter)
if not feature_filter and feature_stats:
    print(f'\n{BOLD}Features{NC}')
    print()
    h = ['Feature', 'Progress', 'Exec', 'Lifecycle']
    print(f'  {h[0]:<30} {h[1]:<16} {h[2]:<13} {h[3]:<12}')
    for fname in sorted(feature_stats.keys()):
        s = feature_stats[fname]
        progress = '%d/%d done' % (s['done'], s['total'])
        if s['in_progress'] > 0:
            progress += ', %d active' % s['in_progress']
        s_exec = s['execution']
        s_life = s['lifecycle']
        print(f'  {fname:<30} {progress:<16} {s_exec:<13} {s_life:<12}')

# Actionable suggestions
suggestions = []
target_features = [feature_filter] if feature_filter else sorted(feature_stats.keys())

for fname in target_features:
    if fname not in feature_stats:
        continue
    s = feature_stats[fname]

    if s['done'] == s['total'] and s['total'] > 0:
        suggestions.append(f'All tasks done for {BOLD}{fname}{NC}! Run {GREEN}relay close {fname}{NC}')
    elif s['guided_ready'] > 0:
        gr = s['guided_ready']
        suggestions.append(f'{gr} guided task(s) waiting in {BOLD}{fname}{NC}: run {GREEN}relay start{NC} from code repo')
    elif s.get('awaiting_review', 0) > 0:
        ar = s['awaiting_review']
        urls = s.get('review_urls', [])
        url_lines = ''.join(f'\n      {u}' for u in urls)
        suggestions.append(f'{ar} task(s) in {BOLD}{fname}{NC} awaiting your review — merge to continue:{url_lines}')
        agent_working = s['in_progress'] - ar
        if agent_working > 0:
            suggestions.append(f'{agent_working} task(s) in {BOLD}{fname}{NC} still being worked on by agents')
        if s['pending'] > 0:
            suggestions.append(f'After current wave completes, promote next wave: {GREEN}relay advance {fname}{NC}')
    elif s['pending'] > 0 and s['ready'] == 0 and s['in_progress'] == 0:
        suggestions.append(f'No ready tasks in {BOLD}{fname}{NC}: run {GREEN}relay advance {fname}{NC} to promote next wave')

if suggestions:
    print(f'\n{BOLD}Suggestions{NC}')
    print()
    for sg in suggestions:
        print(f'  \u2192 {sg}')
    print()
" "${CP_DIR:-$RELAY_DIR}" "$JSON_TMP" "$FEATURE_FILTER"
fi
