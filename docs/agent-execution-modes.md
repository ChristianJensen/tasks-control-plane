# Agent Execution Modes

Relay supports two ways to run implementer agents: **local** (on your machine) and **cloud** (on GitHub Actions). Both use the same Git-native task queue and branch-claim protocol — the only difference is where the agent process runs.

## Architecture Overview

```
queue/                    ← shared task queue (both modes read from here)
    ├── feature-a/
    │   ├── ready/
    │   │   ├── wave-1-api-*.md
    │   │   └── wave-1-frontend-*.md
    │   ├── pending/
    │   │   └── wave-2-*.md
    │   ├── in-progress/
    │   ├── done/
    │   └── _validation.md
    └── feature-b/
        └── ...

Directory = coordination state. Agent claiming: git mv ready/task.md in-progress/task.md

Local mode:  local-agent.sh polls queue/*/ready/ → claims branch → runs claude locally
Cloud mode:  dispatch-agents.yml → repository_dispatch → agent-runner.yml → cloud-agent.sh
```

## Local Mode

Run agents on your own machine using a Claude Max subscription or API key.

### Scripts

| Script | Purpose |
|--------|---------|
| `local-agent.sh` | Reads service catalog, launches watchers for all repos, polls queue, claims tasks, runs Claude |

### Quick Start

```bash
# Single agent per repo (default)
./scripts/local-agent.sh

# 2 parallel agents per repo, 15s poll interval
./scripts/local-agent.sh --agents-per-repo 2 --poll 15
```

### How It Works

1. **Poll loop** — `local-agent.sh` runs continuously, pulling the control plane every N seconds to scan `queue/*/ready/` for claimable tasks
2. **Stale claim recovery** — before scanning, it checks for abandoned `agent/*` branches (no commit in 5 min, no open PR) and moves their tasks back to `ready/`
3. **Claim** — moves task file from `ready/` to `in-progress/` via `git mv`, creates a branch from `origin/main`, pushes an empty claim commit. First push wins (atomic lock)
4. **Execute** — runs `claude -p` with the task prompt, streaming output to your terminal
5. **Report** — on success moves the task to `done/`, on failure moves it to `blocked/` and appends a retro stub

### Single vs Multi-Agent

| Mode | Mechanism | When to use |
|------|-----------|-------------|
| Single (`num-agents=1`) | Runs directly in the repo checkout | Simple, reliable, good for demos |
| Multi (`num-agents>1`) | Creates git worktrees per slot | Parallel work on independent tasks |

Multi-agent mode creates worktrees at `<repo>/.worktrees/agent-<slot>/` and cleans them up on exit.

### Requirements

- `git`, `gh` (authenticated), `claude` CLI
- `ANTHROPIC_API_KEY` env var (or Claude Max subscription for local `claude` CLI)
- All code repos cloned locally (paths configured in `.relay/service-catalog.md`)

---

## Cloud Mode

Run agents on GitHub Actions runners, triggered automatically when tasks land in the queue.

### Scripts & Workflows

| File | Repo | Purpose |
|------|------|---------|
| `.github/workflows/dispatch-agents.yml` | control plane | Fires `repository_dispatch` on queue changes |
| `scripts/dispatch-agents.py` | control plane | Scans queue, sends dispatch events per repo |
| `.github/workflows/agent-runner.yml` | each code repo | Receives dispatch, runs `cloud-agent.sh` |
| `scripts/cloud-agent.sh` | control plane | Standalone agent — clones repos, claims, executes, exits |

### Trigger Flow

```
1. Push to queue/**  (or manual workflow_dispatch)
       │
2. dispatch-agents.yml runs dispatch-agents.py
       │
3. dispatch-agents.py scans queue → counts ready tasks per repo
       │
4. Fires repository_dispatch to target code repos
       │  (with instance count matrix for parallelism)
       │
5. agent-runner.yml receives event → runs N parallel cloud-agent.sh jobs
       │
6. Each cloud-agent.sh:
       ├── Clones control plane + code repo into temp workspace
       ├── Scans queue (or uses --task for targeted run)
       ├── Claims first available task via branch push
       ├── Runs claude -p with task prompt
       ├── Updates task status (done/blocked)
       └── Writes GitHub Actions job summary
```

### Quick Start (Manual)

```bash
# Run locally against a specific repo (useful for testing)
./scripts/cloud-agent.sh --repo api

# Target a specific task file
./scripts/cloud-agent.sh --repo api --task "feature-a/wave-1-api-create-endpoints.md"

# Custom timeout (default: 15 minutes)
./scripts/cloud-agent.sh --repo frontend --max-duration 20
```

### CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--repo` | (required) | Target repo short name (from `.relay/service-catalog.md`) |
| `--relay-url` | (set by bootstrap) | Override control plane clone URL |
| `--repo-url` | (set by bootstrap) | Override code repo clone URL |
| `--task` | (none) | Skip queue scan, target a specific task file (relative to `queue/`) |
| `--max-duration` | `15` | Timeout in minutes; kills agent and cleans up branch on expiry |

### Security

- **Path traversal protection** — `--task` values are resolved with `realpath` and validated against the queue directory. Attempts like `--task "../../etc/passwd"` are rejected
- **Code injection prevention** — task paths are passed to Python via `sys.argv`, not string interpolation
- **Rebase conflict recovery** — `push_relay()` calls `rebase --abort` on failed pulls to prevent dirty git state
- **Zombie branch cleanup** — timed-out agent branches are deleted from the remote

### Observability

When running on GitHub Actions, `cloud-agent.sh` provides:

- **Log grouping** — each phase (preflight, workspace setup, queue scan, prompt building, agent execution, status update) is wrapped in collapsible `::group::` blocks
- **Annotations** — key events appear as notices, warnings, or errors in the Actions UI:
  - `::notice::` — task claimed, task completed, no ready tasks
  - `::warning::` — API key missing, claim failed, control plane push failed
  - `::error::` — agent timeout, agent failure
- **Job summary** — a markdown table with task name, branch, duration, exit code, PR URL, and agent ID
- **Webhook notifications** — optional Slack/Discord alerts on claim, success, and failure (set `SLACK_WEBHOOK_URL` or `DISCORD_WEBHOOK_URL` env vars)

### Required Secrets (GitHub Actions)

| Secret | Where | Purpose |
|--------|-------|---------|
| `DISPATCH_PAT` | control plane | PAT with `contents:write` on all code repos (for `repository_dispatch`) |
| `ANTHROPIC_API_KEY` | each code repo | Claude API key for agent execution |
| `RELAY_PAT` | each code repo | PAT for cloning/pushing to control plane |
| `SLACK_WEBHOOK_URL` | (optional) | Slack incoming webhook for notifications |
| `DISCORD_WEBHOOK_URL` | (optional) | Discord webhook for notifications |

---

## Comparison

| | Local | Cloud |
|---|---|---|
| **Where it runs** | Your machine | GitHub Actions runners |
| **Trigger** | Manual (`local-agent.sh`) | Auto on queue push, or manual `workflow_dispatch` |
| **Lifecycle** | Long-running poll loop | One-shot per task |
| **Parallelism** | Worktrees (multi-agent mode) | Matrix strategy (N parallel jobs) |
| **Cost** | Claude Max subscription or API key | API key + GitHub Actions minutes |
| **Observability** | Terminal output with colors | GHA log groups, annotations, job summary, webhooks |
| **Best for** | Development, demos, debugging | CI/CD, unattended execution, team workflows |
| **Stale recovery** | Built-in (5-min threshold) | Timeout kills + branch cleanup |
| **Retro logging** | Auto-appends to `retro-log.md` | Not yet (planned) |

### When to Use Which

- **Developing/debugging the process itself** — local mode. You can see agent output in real-time and iterate
- **Demo for stakeholders** — local mode with `local-agent.sh`. The colored terminal output makes the process visible
- **Unattended task execution** — cloud mode. Push tasks to the queue and agents run automatically
- **Team with multiple contributors** — cloud mode. No local setup required beyond pushing to the control plane
