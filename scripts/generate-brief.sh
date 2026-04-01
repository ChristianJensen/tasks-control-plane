#!/usr/bin/env bash
set -euo pipefail

# generate-brief.sh — Generates a repo manifest (navigational index) for a repo
# by auto-detecting its structure, entry points, dependencies, and test setup.
#
# Usage:
#   ./scripts/generate-brief.sh [--cp-dir <path>] <repo-short-name> <repo-local-path>
#
# Output: repos/<repo-short-name>/repo-manifest.md
#
# Everything is auto-detected — no manual TODOs. The manifest is a machine-generated
# structural index that tells planning agents where to look, not what the code does.

# ── Parse --cp-dir first ──────────────────────────────────────
POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-dir)
      export CP_DIR="$2"
      shift 2
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Source shared library
source "$SCRIPT_DIR/_lib.sh"

# Validate CP_DIR
if [ -z "${CP_DIR:-}" ]; then
  echo -e "${RED:-}Error: CP_DIR not set. Use --cp-dir or run from a control plane.${NC:-}" >&2
  exit 1
fi

if [ ${#POSITIONAL[@]} -lt 2 ]; then
  echo "Usage: $0 [--cp-dir <path>] <repo-short-name> <repo-local-path>"
  echo ""
  echo "Example: $0 --cp-dir ~/src/my-cp api ~/src/myapp/api"
  exit 1
fi

REPO_SHORT="${POSITIONAL[0]}"
REPO_PATH="${POSITIONAL[1]}"

if [ ! -d "$REPO_PATH" ]; then
  echo "Error: Directory not found: $REPO_PATH"
  exit 1
fi

OUTPUT_DIR="$CP_DIR/repos/$REPO_SHORT"
OUTPUT_FILE="$OUTPUT_DIR/repo-manifest.md"

mkdir -p "$OUTPUT_DIR"

# ── Generate directory tree (depth 3, source dirs only) ──

TREE=$(cd "$REPO_PATH" && find . -maxdepth 3 \
  -type d \
  -not -path '*/.git' \
  -not -path '*/.git/*' \
  -not -path '*/node_modules' \
  -not -path '*/node_modules/*' \
  -not -path '*/dist' \
  -not -path '*/dist/*' \
  -not -path '*/build' \
  -not -path '*/build/*' \
  -not -path '*/__pycache__' \
  -not -path '*/__pycache__/*' \
  -not -path '*/.next' \
  -not -path '*/.next/*' \
  -not -path '*/coverage' \
  -not -path '*/coverage/*' \
  -not -path '*/.venv' \
  -not -path '*/.venv/*' \
  -not -path '*/.claude' \
  -not -path '*/.claude/*' \
  -not -path '*/.superpowers' \
  -not -path '*/.superpowers/*' \
  -not -path '*/.relay' \
  -not -path '*/.relay/*' \
  -not -path '*/.yaks' \
  -not -path '*/.yaks/*' \
  -not -path '*/.turbo' \
  -not -path '*/.turbo/*' \
  -not -path '*/.cache' \
  -not -path '*/.cache/*' \
  -not -path '*/.parcel-cache' \
  -not -path '*/.parcel-cache/*' \
  | sort)

# ── Detect entry points ──

ENTRY_POINTS=""
for candidate in \
  "src/main.ts" "src/index.ts" "src/app.ts" "src/server.ts" \
  "src/main.js" "src/index.js" "src/app.js" "src/server.js" \
  "src/main.tsx" "src/index.tsx" "src/App.tsx" \
  "src/main.jsx" "src/index.jsx" "src/App.jsx" \
  "app.py" "main.py" "manage.py" "src/app.py" "src/main.py" \
  "main.go" "cmd/main.go" "cmd/server/main.go" \
  "src/main.rs" "src/lib.rs" \
  "lib/main.rb" "config.ru" "app.rb" \
  "lib/application.ex" "lib/app.ex" \
  "Program.cs" "Startup.cs" "src/Program.cs" "src/Startup.cs"; do
  if [ -f "$REPO_PATH/$candidate" ]; then
    ENTRY_POINTS="${ENTRY_POINTS}- \`${candidate}\`\n"
  fi
done

# Detect route/handler directories
for dir_candidate in \
  "src/routes" "src/handlers" "src/controllers" "src/api" \
  "src/pages" "src/app" "pages" "app" \
  "routes" "handlers" "controllers" "api"; do
  if [ -d "$REPO_PATH/$dir_candidate" ]; then
    ENTRY_POINTS="${ENTRY_POINTS}- \`${dir_candidate}/\` (routes/handlers)\n"
  fi
done

# ── Detect config files ──

CONFIG_FILES=""
for cfg in \
  "package.json" "tsconfig.json" "tsconfig.base.json" \
  "pyproject.toml" "setup.py" "setup.cfg" "poetry.lock" \
  "go.mod" "Cargo.toml" "Gemfile" "mix.exs" \
  ".env.example" ".env.sample" \
  "Dockerfile" "docker-compose.yml" "docker-compose.yaml" \
  "Makefile" "justfile" \
  "vite.config.ts" "vite.config.js" "next.config.js" "next.config.mjs" "next.config.ts" \
  "webpack.config.js" "rollup.config.js" \
  "tailwind.config.js" "tailwind.config.ts" \
  ".eslintrc.js" ".eslintrc.json" "eslint.config.js" "eslint.config.mjs" \
  "prisma/schema.prisma" "drizzle.config.ts" \
  "alembic.ini" "knexfile.js" "knexfile.ts" \
  "*.csproj" "*.sln"; do
  # Handle glob patterns
  if [[ "$cfg" == *"*"* ]]; then
    for match in "$REPO_PATH"/$cfg; do
      if [ -f "$match" ]; then
        CONFIG_FILES="${CONFIG_FILES}- \`$(basename "$match")\`\n"
      fi
    done
  elif [ -f "$REPO_PATH/$cfg" ]; then
    CONFIG_FILES="${CONFIG_FILES}- \`${cfg}\`\n"
  fi
done

# ── Detect key dependencies ──

KEY_DEPS=""
if [ -f "$REPO_PATH/package.json" ]; then
  KEY_DEPS=$(python3 -c "
import json, sys
try:
    pkg = json.load(open('$REPO_PATH/package.json'))
    deps = list(pkg.get('dependencies', {}).keys()) + list(pkg.get('devDependencies', {}).keys())
    known = ['react', 'next', 'vue', 'nuxt', 'svelte', 'angular', 'express', 'fastify', 'hono', 'koa',
             'nestjs', '@nestjs/core', 'prisma', '@prisma/client', 'drizzle-orm', 'knex', 'sequelize', 'typeorm',
             'tailwindcss', 'styled-components', '@emotion/react', 'chakra-ui', '@chakra-ui/react',
             'redux', '@reduxjs/toolkit', 'zustand', 'jotai', 'recoil', 'mobx',
             'jest', 'vitest', 'mocha', 'cypress', 'playwright', '@playwright/test',
             'typescript', 'zod', 'yup', 'joi', 'trpc', '@trpc/server',
             'graphql', 'apollo-server', '@apollo/server',
             'socket.io', 'ws', 'redis', 'ioredis', 'bull', 'bullmq',
             'mongoose', 'mongodb', 'pg', 'mysql2', 'better-sqlite3']
    found = [d for d in deps if d in known]
    if found:
        print('\n'.join(f'- \`{d}\`' for d in sorted(set(found))))
except Exception:
    pass
" 2>/dev/null || true)
elif [ -f "$REPO_PATH/pyproject.toml" ]; then
  KEY_DEPS=$(python3 -c "
import sys, re
content = open('$REPO_PATH/pyproject.toml').read()
known = ['django', 'flask', 'fastapi', 'starlette', 'uvicorn', 'gunicorn',
         'sqlalchemy', 'alembic', 'tortoise-orm', 'peewee', 'prisma',
         'pydantic', 'marshmallow', 'celery', 'redis', 'httpx', 'requests',
         'pytest', 'unittest', 'hypothesis',
         'pandas', 'numpy', 'polars']
deps_section = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
if deps_section:
    deps_text = deps_section.group(1)
    found = [k for k in known if k in deps_text.lower()]
    if found:
        print('\n'.join(f'- \`{d}\`' for d in sorted(set(found))))
" 2>/dev/null || true)
elif [ -f "$REPO_PATH/go.mod" ]; then
  KEY_DEPS=$(grep -E '^\s+(github\.com|golang\.org)' "$REPO_PATH/go.mod" 2>/dev/null | \
    head -15 | sed 's/^[[:space:]]*/- `/' | sed 's/ .*$/`/' || true)
fi

# ── Detect test framework and run command ──

TEST_FRAMEWORK="Unknown"
TEST_COMMAND=""
if [ -f "$REPO_PATH/package.json" ]; then
  if grep -q '"vitest"' "$REPO_PATH/package.json" 2>/dev/null; then
    TEST_FRAMEWORK="Vitest"
  elif grep -q '"jest"' "$REPO_PATH/package.json" 2>/dev/null; then
    TEST_FRAMEWORK="Jest"
  elif grep -q '"mocha"' "$REPO_PATH/package.json" 2>/dev/null; then
    TEST_FRAMEWORK="Mocha"
  elif grep -q '"playwright"' "$REPO_PATH/package.json" 2>/dev/null || \
       grep -q '"@playwright/test"' "$REPO_PATH/package.json" 2>/dev/null; then
    TEST_FRAMEWORK="Playwright"
  elif grep -q '"cypress"' "$REPO_PATH/package.json" 2>/dev/null; then
    TEST_FRAMEWORK="Cypress"
  fi
  TEST_COMMAND=$(python3 -c "
import json
pkg = json.load(open('$REPO_PATH/package.json'))
scripts = pkg.get('scripts', {})
for key in ['test', 'test:unit', 'test:all']:
    if key in scripts:
        print(f'npm run {key}')
        break
" 2>/dev/null || true)
elif [ -f "$REPO_PATH/pytest.ini" ] || [ -f "$REPO_PATH/pyproject.toml" ] || [ -f "$REPO_PATH/setup.cfg" ]; then
  if grep -q "pytest" "$REPO_PATH/pyproject.toml" 2>/dev/null || \
     [ -f "$REPO_PATH/pytest.ini" ]; then
    TEST_FRAMEWORK="pytest"
    TEST_COMMAND="pytest"
  fi
elif [ -f "$REPO_PATH/go.mod" ]; then
  TEST_FRAMEWORK="go test"
  TEST_COMMAND="go test ./..."
fi

# Detect test directories
TEST_DIRS=""
for test_dir in "tests" "test" "__tests__" "spec" "src/__tests__" "src/test" "e2e" "integration"; do
  if [ -d "$REPO_PATH/$test_dir" ]; then
    TEST_DIRS="${TEST_DIRS}- \`${test_dir}/\`\n"
  fi
done

# ── Generate key source files with line counts (exclude tests, cap at 30) ──

KEY_FILES=""
FILE_COUNT=0
while IFS= read -r entry; do
  file=$(echo "$entry" | cut -d'|' -f2)
  lines=$(echo "$entry" | cut -d'|' -f1)
  KEY_FILES="${KEY_FILES}| \`${file}\` | ~${lines} |\n"
  FILE_COUNT=$((FILE_COUNT + 1))
  if [ "$FILE_COUNT" -ge 30 ]; then
    break
  fi
done <<< "$(cd "$REPO_PATH" && find . -maxdepth 4 \
  -not -path '*/node_modules/*' \
  -not -path '*/.git/*' \
  -not -path '*/dist/*' \
  -not -path '*/build/*' \
  -not -path '*/__pycache__/*' \
  -not -path '*/.next/*' \
  -not -path '*/coverage/*' \
  -not -path '*/.venv/*' \
  -not -path '*/.claude/*' \
  -not -path '*/.superpowers/*' \
  -not -path '*/.relay/*' \
  -not -path '*/.yaks/*' \
  -not -path '*/tests/*' \
  -not -path '*/test/*' \
  -not -path '*/__tests__/*' \
  -not -path '*/spec/*' \
  -not -path '*/e2e/*' \
  -not -name '*.test.*' \
  -not -name '*.spec.*' \
  -not -name '*_test.*' \
  -not -name '*_test.go' \
  -type f \
  \( -name '*.ts' -o -name '*.js' -o -name '*.tsx' -o -name '*.jsx' \
     -o -name '*.py' -o -name '*.go' -o -name '*.rs' -o -name '*.java' \
     -o -name '*.rb' -o -name '*.ex' -o -name '*.exs' -o -name '*.cs' \) \
  -exec sh -c 'for f; do l=$(wc -l < "$f" | tr -d " "); if [ "$l" -gt 30 ]; then echo "${l}|${f}"; fi; done' _ {} + \
  | sort -t'|' -k1 -nr)"

# ── Write the manifest ──

{
  echo "# Repo Manifest: ${REPO_SHORT}"
  echo ""
  echo "> Auto-generated navigational index for planning agents. Not documentation — just enough to know where to look next."
  echo ""
  echo "## Directory Tree"
  echo ""
  echo '```'
  echo "$TREE"
  echo '```'

  if [ -n "$ENTRY_POINTS" ]; then
    echo ""
    echo "## Entry Points"
    echo ""
    echo -e "$ENTRY_POINTS"
  fi

  if [ -n "$CONFIG_FILES" ]; then
    echo ""
    echo "## Config Files"
    echo ""
    echo -e "$CONFIG_FILES"
  fi

  if [ -n "$KEY_DEPS" ]; then
    echo ""
    echo "## Key Dependencies"
    echo ""
    echo "$KEY_DEPS"
  fi

  if [ "$TEST_FRAMEWORK" != "Unknown" ] || [ -n "$TEST_COMMAND" ] || [ -n "$TEST_DIRS" ]; then
    echo ""
    echo "## Test Setup"
    echo ""
    if [ "$TEST_FRAMEWORK" != "Unknown" ]; then
      echo "- **Framework:** ${TEST_FRAMEWORK}"
    fi
    if [ -n "$TEST_COMMAND" ]; then
      echo "- **Run command:** \`${TEST_COMMAND}\`"
    fi
    if [ -n "$TEST_DIRS" ]; then
      echo -e "- **Test directories:**\n$(echo -e "$TEST_DIRS" | sed 's/^/  /')"
    fi
  fi

  if [ -n "$KEY_FILES" ]; then
    echo ""
    echo "## Key Files"
    echo ""
    echo "| File | Lines |"
    echo "|------|-------|"
    echo -e "$KEY_FILES"
  fi

  echo "---"
  echo ""
  echo "_Auto-generated by \`relay generate-brief\`. No manual editing needed._"
} > "$OUTPUT_FILE"

echo "Manifest generated: $OUTPUT_FILE"
