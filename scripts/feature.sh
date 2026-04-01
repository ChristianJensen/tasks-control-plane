#!/usr/bin/env bash
set -euo pipefail

# Feature namespace dispatcher — routes `relay feature <subcmd>` to existing scripts.
#
# Usage: feature.sh [--cp-dir <path>] [<subcommand>] [args...]
#
# Subcommands:
#   list (default)  — List active features (draft/active/paused/replanning)
#   history         — List completed/cancelled features (newest first)
#   new             — Define a new feature (alias for spec.py)
#   plan <name>     — Decompose feature into tasks (alias for plan.py)
#   slice <name>    — Legacy alias for plan
#   validate <name> — Validate feature spec + tasks (alias for validate.py)
#   promote <name>  — Promote pending tasks to ready (alias for promote-tasks.sh)
#   status|pause|resume|cancel|complete|replan <name>
#                   — Manage feature lifecycle

# ── Parse --cp-dir ────────────────────────────────────────────
POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir) export CP_DIR="$2"; shift 2 ;;
    *)        POSITIONAL+=("$1"); shift ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"

if [ -z "${CP_DIR:-}" ]; then
  echo -e "${RED}Error: CP_DIR not set. Use --cp-dir or run from a control plane.${NC}" >&2
  exit 1
fi

subcmd="${POSITIONAL[0]:-list}"
# Build remaining args array
ARGS=()
for ((i=1; i<${#POSITIONAL[@]}; i++)); do
  ARGS+=("${POSITIONAL[$i]}")
done
set -- ${ARGS[@]+"${ARGS[@]}"}

case "$subcmd" in
  list|history)
    # Parse history flags
    show_history=0
    limit=20
    show_all=0
    if [ "$subcmd" = "history" ]; then
      show_history=1
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --limit) limit="$2"; shift 2 ;;
          --all)   show_all=1; shift ;;
          *)       shift ;;
        esac
      done
    fi

    features_dir="$CP_DIR/features"
    bugs_dir="$CP_DIR/bugs"
    if [ ! -d "$features_dir" ] && [ ! -d "$bugs_dir" ]; then
      echo "No features directory found."
      exit 0
    fi

    # Collect features into parallel arrays for filtering/sorting
    feat_names=()
    feat_lifecycles=()
    feat_summaries=()
    feat_timestamps=()

    for spec in "$features_dir"/*/*-feature.md "$features_dir"/*/*-bug.md "$bugs_dir"/*/*-bug.md; do
      [ -f "$spec" ] || continue

      # Extract feature name from filename
      fname=$(basename "$spec")
      fname="${fname%-feature.md}"
      fname="${fname%-bug.md}"

      # Infer lifecycle from directory if in a phase directory
      _spec_parent=$(basename "$(dirname "$spec")")
      _phase_lifecycle=""
      case "$_spec_parent" in
        draft|active|completed|cancelled)
          _phase_lifecycle="$_spec_parent"
          # Map phase to lifecycle (completed phase may have live-prod in frontmatter)
          ;;
      esac

      # Read lifecycle (and timestamp for history mode) from frontmatter
      read_fields="lifecycle"
      if [ "$show_history" -eq 1 ]; then
        read_fields="lifecycle,completed-at,cancelled-at"
      fi
      frontmatter=$(python3 -c "
import re, sys
fields = sys.argv[2].split(',')
with open(sys.argv[1]) as f:
    content = f.read()
m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
result = {}
if m:
    for line in m.group(1).splitlines():
        k, _, v = line.partition(':')
        k = k.strip()
        if k in fields:
            result[k] = v.strip().strip('\"').strip(\"'\")
for f in fields:
    print(result.get(f, ''))
" "$spec" "$read_fields" 2>/dev/null || echo "unknown")

      lifecycle=$(echo "$frontmatter" | head -1)
      # Phase directory overrides frontmatter for broad lifecycle
      if [ -n "$_phase_lifecycle" ] && [ "$_phase_lifecycle" != "$lifecycle" ]; then
        lifecycle="${_phase_lifecycle}"
      fi

      # Filter based on mode
      if [ "$show_history" -eq 1 ]; then
        # History: only completed/cancelled
        case "$lifecycle" in
          completed|cancelled) ;;
          *) continue ;;
        esac
      else
        # List: skip completed/cancelled
        case "$lifecycle" in
          completed|cancelled) continue ;;
        esac
      fi

      # Get timestamp for history sorting
      timestamp=""
      if [ "$show_history" -eq 1 ]; then
        timestamp=$(echo "$frontmatter" | sed -n '2p')  # completed-at
        if [ -z "$timestamp" ]; then
          timestamp=$(echo "$frontmatter" | sed -n '3p')  # cancelled-at
        fi
        if [ -z "$timestamp" ]; then
          # Fallback to file modification time
          timestamp=$(stat -f "%Sm" -t "%Y-%m-%dT%H:%M:%SZ" "$spec" 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)
        fi
      fi

      # Count tasks by status
      queue_dir="$CP_DIR/queue/$fname"
      # Also check archived queue for completed features
      if [ ! -d "$queue_dir" ] && [ -d "$CP_DIR/queue/_done/$fname" ]; then
        queue_dir="$CP_DIR/queue/_done/$fname"
      fi
      done_count=0
      total_count=0
      pending_count=0
      ready_count=0
      in_progress_count=0
      if [ -d "$queue_dir" ]; then
        for tf in "$queue_dir"/*/wave-*.md; do
          [ -f "$tf" ] || continue
          total_count=$((total_count + 1))
          _ts=$(status_from_path "$tf")
          case "$_ts" in
            done) done_count=$((done_count + 1)) ;;
            pending) pending_count=$((pending_count + 1)) ;;
            ready) ready_count=$((ready_count + 1)) ;;
            in-progress) in_progress_count=$((in_progress_count + 1)) ;;
          esac
        done
      fi

      # Format task summary
      if [ "$total_count" -eq 0 ]; then
        task_summary="no tasks"
      else
        parts=()
        [ "$done_count" -gt 0 ] && parts+=("${done_count} done")
        [ "$in_progress_count" -gt 0 ] && parts+=("${in_progress_count} active")
        [ "$ready_count" -gt 0 ] && parts+=("${ready_count} ready")
        [ "$pending_count" -gt 0 ] && parts+=("${pending_count} pending")
        task_summary="${total_count} tasks ($(IFS=', '; echo "${parts[*]}"))"
      fi

      feat_names+=("$fname")
      feat_lifecycles+=("$lifecycle")
      feat_summaries+=("$task_summary")
      feat_timestamps+=("$timestamp")
    done

    # Sort by timestamp (newest first) for history mode
    if [ "$show_history" -eq 1 ] && [ ${#feat_names[@]} -gt 0 ]; then
      # Build sortable lines: timestamp|index, sort descending, extract indices
      sorted_indices=()
      sort_input=""
      for i in "${!feat_names[@]}"; do
        sort_input+="${feat_timestamps[$i]}|${i}"$'\n'
      done
      while IFS='|' read -r _ idx; do
        [ -n "$idx" ] && sorted_indices+=("$idx")
      done < <(echo "$sort_input" | sort -r -t'|' -k1)

      # Apply limit
      if [ "$show_all" -eq 0 ] && [ ${#sorted_indices[@]} -gt "$limit" ]; then
        sorted_indices=("${sorted_indices[@]:0:$limit}")
      fi

      # Rebuild arrays in sorted order
      new_names=()
      new_lifecycles=()
      new_summaries=()
      new_timestamps=()
      for idx in "${sorted_indices[@]}"; do
        new_names+=("${feat_names[$idx]}")
        new_lifecycles+=("${feat_lifecycles[$idx]}")
        new_summaries+=("${feat_summaries[$idx]}")
        new_timestamps+=("${feat_timestamps[$idx]}")
      done
      feat_names=("${new_names[@]}")
      feat_lifecycles=("${new_lifecycles[@]}")
      feat_summaries=("${new_summaries[@]}")
      feat_timestamps=("${new_timestamps[@]}")
    fi

    # Print table
    if [ ${#feat_names[@]} -gt 0 ]; then
      if [ "$show_history" -eq 1 ]; then
        printf "${BOLD}%-22s %-14s %-22s %s${NC}\n" "Feature" "Lifecycle" "Date" "Tasks"
        printf "%-22s %-14s %-22s %s\n" "───────" "─────────" "────" "─────"
      else
        printf "${BOLD}%-22s %-14s %s${NC}\n" "Feature" "Lifecycle" "Tasks"
        printf "%-22s %-14s %s\n" "───────" "─────────" "─────"
      fi

      for i in "${!feat_names[@]}"; do
        lifecycle="${feat_lifecycles[$i]}"
        case "$lifecycle" in
          active)    lc_color="$GREEN" ;;
          paused)    lc_color="$YELLOW" ;;
          cancelled|completed) lc_color="$DIM" ;;
          *)         lc_color="$BLUE" ;;
        esac

        if [ "$show_history" -eq 1 ]; then
          # Format date: show just the date portion
          date_display="${feat_timestamps[$i]%%T*}"
          printf "  %-20s ${lc_color}%-14s${NC} %-22s %s\n" "${feat_names[$i]}" "$lifecycle" "$date_display" "${feat_summaries[$i]}"
        else
          printf "  %-20s ${lc_color}%-14s${NC} %s\n" "${feat_names[$i]}" "$lifecycle" "${feat_summaries[$i]}"
        fi
      done
    else
      if [ "$show_history" -eq 1 ]; then
        echo -e "${DIM}No completed or cancelled features found.${NC}"
      else
        # Check if there are any features at all (might all be completed/cancelled)
        has_any=0
        for spec in "$features_dir"/*/*-feature.md "$features_dir"/*/*-bug.md "$bugs_dir"/*/*-bug.md; do
          [ -f "$spec" ] && has_any=1 && break
        done
        if [ "$has_any" -eq 1 ]; then
          echo -e "${DIM}No active features. Run 'relay feature history' to see completed work.${NC}"
        else
          echo -e "${DIM}No features found. Run 'relay feature new' to create one.${NC}"
        fi
      fi
    fi
    ;;

  new)
    exec python3 "$SCRIPT_DIR/spec.py" --cp-dir "$CP_DIR" "$@"
    ;;

  plan|slice)
    exec python3 "$SCRIPT_DIR/plan.py" --cp-dir "$CP_DIR" "$@"
    ;;

  validate)
    exec python3 "$SCRIPT_DIR/validate.py" --cp-dir "$CP_DIR" "$@"
    ;;

  promote)
    exec "$SCRIPT_DIR/promote-tasks.sh" --cp-dir "$CP_DIR" "$@"
    ;;

  status|pause|resume|cancel|complete|replan)
    exec "$SCRIPT_DIR/feature-lifecycle.sh" --cp-dir "$CP_DIR" "$subcmd" "$@"
    ;;

  *)
    echo -e "${RED}Unknown subcommand: relay feature $subcmd${NC}"
    echo ""
    echo "Usage: relay feature [list|history|new|plan|validate|promote|status|pause|resume|cancel|complete|replan]"
    exit 1
    ;;
esac
