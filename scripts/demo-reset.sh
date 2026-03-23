#!/usr/bin/env bash
set -euo pipefail

# Demo Reset Script
# Resets all repos (api, frontend, control-plane) to the demo-baseline tag
# and cleans up branches + PRs created during a demo run.
#
# Usage:
#   ./scripts/demo-reset.sh          # reset all repos
#   ./scripts/demo-reset.sh --tag    # create/move demo-baseline tags (one-time setup)

DEMO_TAG="demo-baseline"

# Repo definitions: local_path github_owner/repo
REPOS=(
  "/Users/christianjensen/src/agentic-sdlc-demo/api|ChristianJensen/agentic-sdlc-api"
  "/Users/christianjensen/src/agentic-sdlc-demo/frontend|ChristianJensen/agentic-sdlc-frontend"
  "/Users/christianjensen/src/agentic-sdlc-demo/tasks-control-plane|ChristianJensen/tasks-control-plane"
)

log() { printf "\033[1;34m==> %s\033[0m\n" "$1"; }
warn() { printf "\033[1;33m  ! %s\033[0m\n" "$1"; }
err() { printf "\033[1;31m  ✗ %s\033[0m\n" "$1"; }
ok() { printf "\033[1;32m  ✓ %s\033[0m\n" "$1"; }

create_tags() {
  log "Tagging current state as '${DEMO_TAG}' in all repos"
  for entry in "${REPOS[@]}"; do
    local_path="${entry%%|*}"
    repo_name="${entry##*/}"

    if [[ ! -d "$local_path/.git" ]]; then
      err "$repo_name: not a git repo at $local_path"
      continue
    fi

    pushd "$local_path" > /dev/null
    git tag -f "$DEMO_TAG"
    git push origin "$DEMO_TAG" --force
    ok "$repo_name: tagged $(git rev-parse --short HEAD) as $DEMO_TAG"
    popd > /dev/null
  done
  log "All repos tagged. You can now run ./scripts/demo-reset.sh to reset."
}

close_demo_prs() {
  local gh_repo="$1"
  log "Closing open PRs in $gh_repo"

  # Close PRs from agent/* and fix/* branches
  local prs
  prs=$(gh pr list --repo "$gh_repo" --state open --json number,headRefName \
    --jq '.[] | select(.headRefName | test("^(agent|fix)/")) | .number' 2>/dev/null || true)

  if [[ -z "$prs" ]]; then
    ok "No open agent/fix PRs to close"
    return
  fi

  while IFS= read -r pr_num; do
    gh pr close "$pr_num" --repo "$gh_repo" --delete-branch 2>/dev/null && \
      ok "Closed PR #$pr_num" || \
      warn "Failed to close PR #$pr_num"
  done <<< "$prs"
}

delete_agent_branches() {
  log "Cleaning up remote agent/fix branches"
  local branches
  branches=$(git branch -r --list 'origin/agent/*' 'origin/fix/*' 2>/dev/null || true)

  if [[ -z "$branches" ]]; then
    ok "No agent/fix branches to clean up"
    return
  fi

  while IFS= read -r branch; do
    branch="${branch#  }"  # trim leading spaces
    remote_branch="${branch#origin/}"
    git push origin --delete "$remote_branch" 2>/dev/null && \
      ok "Deleted branch $remote_branch" || \
      warn "Failed to delete $remote_branch"
  done <<< "$branches"
}

reset_repo() {
  local local_path="$1"
  local gh_repo="$2"
  local repo_name="${gh_repo##*/}"

  log "Resetting $repo_name"

  if [[ ! -d "$local_path/.git" ]]; then
    err "$repo_name: not a git repo at $local_path"
    return 1
  fi

  pushd "$local_path" > /dev/null

  # Verify tag exists
  if ! git rev-parse "$DEMO_TAG" >/dev/null 2>&1; then
    git fetch origin
    if ! git rev-parse "$DEMO_TAG" >/dev/null 2>&1; then
      err "$repo_name: tag '$DEMO_TAG' not found. Run with --tag first."
      popd > /dev/null
      return 1
    fi
  fi

  # Close PRs before deleting branches
  close_demo_prs "$gh_repo"

  # Delete remote agent/fix branches
  delete_agent_branches

  # Reset main to baseline
  git checkout main 2>/dev/null || git checkout -b main
  git fetch origin
  git reset --hard "$DEMO_TAG"
  git clean -fd
  git push origin main --force-with-lease
  ok "$repo_name: reset to $DEMO_TAG ($(git rev-parse --short HEAD))"

  # Clean up local agent/fix branches
  git branch --list 'agent/*' 'fix/*' | while IFS= read -r branch; do
    branch="${branch#  }"
    git branch -D "$branch" 2>/dev/null || true
  done

  popd > /dev/null
}

# --- Main ---

if [[ "${1:-}" == "--tag" ]]; then
  create_tags
  exit 0
fi

log "Demo Reset — resetting all repos to '$DEMO_TAG'"
echo ""

failed=0
for entry in "${REPOS[@]}"; do
  local_path="${entry%%|*}"
  gh_repo="${entry##*|}"

  if ! reset_repo "$local_path" "$gh_repo"; then
    failed=1
  fi
  echo ""
done

if [[ $failed -eq 0 ]]; then
  log "All repos reset successfully. Ready for demo!"
else
  err "Some repos failed to reset. Check output above."
  exit 1
fi
