#!/usr/bin/env bash
set -euo pipefail

# relay version [bump [patch|minor|major] [--commit] [--tag] [--push]]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"

VERSION_FILE="$RELAY_DIR/VERSION"

if [ ! -f "$VERSION_FILE" ]; then
  log_err "VERSION file not found at $VERSION_FILE"
  exit 1
fi

CURRENT=$(cat "$VERSION_FILE" | tr -d '[:space:]')

# No subcommand — just print version
if [ $# -eq 0 ]; then
  echo "$CURRENT"
  exit 0
fi

SUBCMD="${1:-}"
shift

if [ "$SUBCMD" != "bump" ]; then
  echo -e "${RED}Unknown version subcommand: ${SUBCMD}${NC}"
  echo "Usage: relay version [bump [patch|minor|major] [--commit] [--tag] [--push]]"
  exit 1
fi

# Parse bump arguments
SEGMENT="patch"
DO_COMMIT=false
DO_TAG=false
DO_PUSH=false

while [ $# -gt 0 ]; do
  case "$1" in
    patch|minor|major) SEGMENT="$1" ;;
    --commit) DO_COMMIT=true ;;
    --tag)    DO_TAG=true ;;
    --push)   DO_PUSH=true ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      echo "Usage: relay version bump [patch|minor|major] [--commit] [--tag] [--push]"
      exit 1
      ;;
  esac
  shift
done

# Parse semver
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

case "$SEGMENT" in
  major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
  patch) PATCH=$((PATCH + 1)) ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"

# Write
echo "$NEW_VERSION" > "$VERSION_FILE"
log_ok "Bumped version: ${CURRENT} → ${NEW_VERSION}"

if [ "$DO_COMMIT" = true ]; then
  git -C "$RELAY_DIR" add -A
  git -C "$RELAY_DIR" commit -m "chore: relay v${NEW_VERSION}"
  log_ok "Committed all changes as relay v${NEW_VERSION}"
fi

if [ "$DO_TAG" = true ]; then
  git -C "$RELAY_DIR" tag "v${NEW_VERSION}"
  log_ok "Tagged v${NEW_VERSION}"
fi

if [ "$DO_PUSH" = true ]; then
  if [ "$DO_COMMIT" != true ]; then
    echo -e "${RED}Error: --push requires --commit${NC}"
    exit 1
  fi
  git -C "$RELAY_DIR" push
  if [ "$DO_TAG" = true ]; then
    git -C "$RELAY_DIR" push origin "v${NEW_VERSION}"
  fi
  log_ok "Pushed to remote"
fi
