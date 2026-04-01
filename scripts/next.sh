#!/usr/bin/env bash
set -euo pipefail

# relay next — inspect state and suggest what to do next.
# Reads feature lifecycle, queue task statuses, and execution modes
# to give context-aware guidance.

_LOG_CONTEXT="next"

# ── Parse args ────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir) CP_DIR="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# ── Source shared library ─────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"

if [ -z "${CP_DIR:-}" ]; then
  echo -e "${RED}Error: CP_DIR not set. Use --cp-dir or run from a control plane.${NC}"
  exit 1
fi

features_dir="$CP_DIR/features"
bugs_dir="$CP_DIR/bugs"

# ── Detect context ────────────────────────────────────────
_in_code_repo=""
if [ -f "$(pwd)/.relay/config.md" ]; then
  _in_code_repo=1
fi

# ── Helper: read frontmatter field ────────────────────────
read_field() {
  local file="$1" field="$2"
  python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    content = f.read()
m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
if m:
    match = re.search(r'^${field}:\s*(.+)', m.group(1), re.MULTILINE)
    if match:
        val = match.group(1).strip().strip('\"').strip(\"'\")
        # Strip inline comments
        import re as r2
        val = r2.sub(r'\s+#.*$', '', val)
        print(val)
" "$file" 2>/dev/null || true
}

# ── Helper: count tasks by status ─────────────────────────
count_tasks() {
  local queue_dir="$1"
  local pending=0 ready=0 in_progress=0 done=0 guided_ready=0 awaiting_review=0

  if [ ! -d "$queue_dir" ]; then
    echo "0 0 0 0 0 0"
    return
  fi

  for tf in "$queue_dir"/*/wave-*.md; do
    [ -f "$tf" ] || continue
    local status
    status=$(basename "$(dirname "$tf")")
    local exec_mode=$(grep -m1 '^execution:' "$tf" | sed 's/^execution:[[:space:]]*//' | sed 's/[[:space:]]*#.*//' || true)
    case "$status" in
      pending) pending=$((pending + 1)) ;;
      ready)
        ready=$((ready + 1))
        if [ "$exec_mode" = "guided" ]; then
          guided_ready=$((guided_ready + 1))
        fi
        ;;
      in-progress)
        in_progress=$((in_progress + 1))
        local has_pr
        has_pr=$(grep -m1 '^pr-url:' "$tf" 2>/dev/null | sed 's/^pr-url:[[:space:]]*//' || true)
        if [ -n "$has_pr" ]; then
          awaiting_review=$((awaiting_review + 1))
        fi
        ;;
      done) done=$((done + 1)) ;;
    esac
  done

  echo "$pending $ready $in_progress $done $guided_ready $awaiting_review"
}

# ── Code repo context ─────────────────────────────────────
if [ -n "$_in_code_repo" ]; then
  BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

  # On a task branch? Suggest finishing it.
  if [[ "$BRANCH" == agent/* ]] || [[ "$BRANCH" == fix/* ]]; then
    echo ""
    echo -e "${BOLD}You're on branch ${BLUE}$BRANCH${NC}"
    echo -e "  Continue working on your task. When done:"
    echo ""
    echo -e "  ${GREEN}relay done${NC}"
    echo ""
    exit 0
  fi

  # Otherwise check for ready guided tasks
  echo ""
  echo -e "${BOLD}Checking for tasks that need you...${NC}"
  echo ""

  _found_guided=0
  if [ -d "$features_dir" ]; then
    for spec in "$features_dir"/active/*-feature.md "$features_dir"/active/*-bug.md "$bugs_dir"/active/*-bug.md; do
      [ -f "$spec" ] || continue

      fname=$(basename "$spec")
      fname="${fname%-feature.md}"
      fname="${fname%-bug.md}"
      feature_exec=$(read_field "$spec" "execution")
      [ -z "$feature_exec" ] && feature_exec="supervised"

      queue_dir="$CP_DIR/queue/$fname"
      [ -d "$queue_dir" ] || continue

      for tf in "$queue_dir"/ready/wave-*.md; do
        [ -f "$tf" ] || continue
        exec_mode=$(grep -m1 '^execution:' "$tf" | sed 's/^execution:[[:space:]]*//' | sed 's/[[:space:]]*#.*//' || true)
        [ -z "$exec_mode" ] && exec_mode="$feature_exec"
        if [ "$exec_mode" = "guided" ]; then
          task_name=$(basename "$tf" .md)
          echo -e "  ${YELLOW}guided${NC} task: ${BOLD}$task_name${NC} (feature: $fname)"
          _found_guided=1
        fi
      done
    done
  fi

  if [ "$_found_guided" = "1" ]; then
    echo ""
    echo -e "  ${GREEN}relay start${NC}"
    echo ""
  else
    echo -e "  No guided tasks need you right now."
    echo -e "  Check overall progress from the control plane:"
    echo ""
    echo -e "  ${GREEN}relay check${NC}"
    echo ""
  fi
  exit 0
fi

# ── Control plane context ─────────────────────────────────
echo ""

# Gather feature states
_has_features=0
declare -a _suggestions=()

if [ -d "$features_dir" ]; then
  for spec in "$features_dir"/active/*-feature.md "$features_dir"/active/*-bug.md \
              "$bugs_dir"/active/*-bug.md \
              "$features_dir"/draft/*-feature.md "$features_dir"/draft/*-bug.md \
              "$bugs_dir"/draft/*-bug.md; do
    [ -f "$spec" ] || continue
    _has_features=1

    fname=$(basename "$spec")
    fname="${fname%-feature.md}"
    fname="${fname%-bug.md}"

    # Infer lifecycle from directory
    spec_parent=$(basename "$(dirname "$spec")")
    case "$spec_parent" in
      active)    lifecycle="active" ;;
      draft)     lifecycle="draft" ;;
      completed) lifecycle="completed" ;;
      cancelled) lifecycle="cancelled" ;;
      *)         lifecycle="unknown" ;;
    esac
    feature_exec=$(read_field "$spec" "execution")
    [ -z "$feature_exec" ] && feature_exec="supervised"

    queue_dir="$CP_DIR/queue/$fname"
    read -r pending ready in_progress done_count guided_ready awaiting_review <<< "$(count_tasks "$queue_dir")"
    total=$((pending + ready + in_progress + done_count))

    case "$lifecycle" in
      draft)
        if [ "$total" -eq 0 ]; then
          _suggestions+=("$(echo -e "Feature ${BOLD}$fname${NC} is a draft with no tasks.\n    ${GREEN}relay plan $fname${NC}")")
        else
          _suggestions+=("$(echo -e "Feature ${BOLD}$fname${NC} is a draft.\n    Review the spec, then: ${GREEN}relay manage resume $fname${NC}")")
        fi
        ;;
      active)
        if [ "$total" -eq 0 ]; then
          _suggestions+=("$(echo -e "Feature ${BOLD}$fname${NC} is active but has no tasks.\n    ${GREEN}relay plan $fname${NC}")")
        elif [ "$in_progress" -gt 0 ] && [ "$ready" -eq 0 ] && [ "$pending" -eq 0 ]; then
          if [ "$awaiting_review" -gt 0 ]; then
            pr_urls=""
            for _tf in "$queue_dir"/in-progress/wave-*.md; do
              [ -f "$_tf" ] || continue
              _pu=""
              _pu=$(grep -m1 '^pr-url:' "$_tf" 2>/dev/null | sed 's/^pr-url:[[:space:]]*//' || true)
              if [ -n "$_pu" ]; then
                pr_urls="${pr_urls}\n      ${_pu}"
              fi
            done
            agent_working=$(( in_progress - awaiting_review ))
            msg="Feature ${BOLD}$fname${NC}: $awaiting_review task(s) awaiting your review — merge to continue:${pr_urls}"
            if [ "$agent_working" -gt 0 ]; then
              msg="${msg}\n    Plus $agent_working task(s) still being worked on by agents."
            fi
            _suggestions+=("$(echo -e "$msg")")
          else
            _suggestions+=("$(echo -e "Feature ${BOLD}$fname${NC}: $in_progress task(s) in progress. Check progress:\n    ${GREEN}relay check $fname${NC}")")
          fi
        elif [ "$ready" -gt 0 ]; then
          if [ "$guided_ready" -gt 0 ]; then
            _suggestions+=("$(echo -e "Feature ${BOLD}$fname${NC}: $guided_ready guided task(s) waiting for you.\n    From code repo: ${GREEN}relay start${NC}")")
          fi
          auto_ready=$((ready - guided_ready))
          if [ "$auto_ready" -gt 0 ]; then
            _suggestions+=("$(echo -e "Feature ${BOLD}$fname${NC}: $auto_ready autonomous/supervised task(s) ready.\n    Agents should handle these. Launch: ${GREEN}relay agents${NC}")")
          fi
        elif [ "$pending" -gt 0 ] && [ "$ready" -eq 0 ] && [ "$in_progress" -eq 0 ]; then
          _suggestions+=("$(echo -e "Feature ${BOLD}$fname${NC}: $pending pending task(s) — wave may need advancing.\n    ${GREEN}relay advance $fname${NC}")")
        elif [ "$done_count" -eq "$total" ] && [ "$total" -gt 0 ]; then
          _suggestions+=("$(echo -e "Feature ${BOLD}$fname${NC}: all $total tasks done!\n    ${GREEN}relay close $fname${NC}")")
        else
          _suggestions+=("$(echo -e "Feature ${BOLD}$fname${NC}: ${done_count}/${total} done, $in_progress in-progress, $ready ready, $pending pending.\n    ${GREEN}relay check $fname${NC}")")
        fi
        ;;
      paused)
        _suggestions+=("$(echo -e "Feature ${BOLD}$fname${NC} is paused.\n    ${GREEN}relay manage resume $fname${NC}")")
        ;;
      replanning)
        _suggestions+=("$(echo -e "Feature ${BOLD}$fname${NC} is being replanned.\n    ${GREEN}relay new --replan $fname${NC}")")
        ;;
    esac
  done
fi

if [ "$_has_features" -eq 0 ]; then
  echo -e "${BOLD}No features found.${NC} Start by defining one:"
  echo ""
  echo -e "  ${GREEN}relay new${NC}"
  echo ""
  exit 0
fi

if [ ${#_suggestions[@]} -eq 0 ]; then
  echo -e "${BOLD}Everything looks good.${NC} No actions needed right now."
  echo ""
  echo -e "  ${DIM}Create a new feature:${NC} ${GREEN}relay new${NC}"
  echo -e "  ${DIM}Check status:${NC}         ${GREEN}relay check${NC}"
  echo ""
  exit 0
fi

echo -e "${BOLD}What needs your attention:${NC}"
echo ""
for suggestion in "${_suggestions[@]}"; do
  echo -e "  → $suggestion"
  echo ""
done
