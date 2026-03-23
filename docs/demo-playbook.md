# Demo Playbook: 3 Execution Modes

## Prerequisites

- All repos at `demo-baseline` tag (run `./scripts/demo-reset.sh` if needed)
- API server running locally
- Frontend dev server running locally
- `gh` CLI authenticated

## Reset

```bash
./scripts/demo-reset.sh
```

---

## Demo Flow

### 1. Show the App (~2 min)

Walk through the task tracker: create a task, set priority, assign a category, drag to reorder, add a comment, check the status history. Establish that this is a real, working app.

### 2. Feature 1: Dark Mode → Autonomous (~5 min)

**The pitch**: "This is a low-risk, well-known pattern. No API changes, no data model changes. We'll let the AI handle this completely unattended."

**Run `relay spec`** and provide:
- **Idea**: Dark mode / theme toggle for the task tracker
- **Slug**: `dark-mode`
- **Execution mode**: `autonomous`
- **Scope**: CSS custom properties for color tokens, toggle in header (sun/moon), persist to localStorage, respect prefers-color-scheme
- **Repos**: Frontend only
- **Contract impact**: None

**Then**:
```bash
relay slice dark-mode
relay agents
```

Show the agent claim the task, implement it, and auto-merge. While it works, explain: "No human in the loop. It picks up the task, writes the code, CI passes, it ships."

### 3. Feature 2: Task Analytics Dashboard → Supervised (~5 min)

**The pitch**: "This involves creative judgment — which metrics to show, how to lay out charts. The AI does the work, but we want a human to review before it ships."

**Run `relay spec`** and provide:
- **Idea**: Analytics dashboard showing task completion trends and category/priority breakdowns
- **Slug**: `analytics-dashboard`
- **Execution mode**: `supervised`
- **Scope**: New dashboard view, charts for completion rate over time, tasks by category, priority distribution. All from existing endpoints (GET /tasks, GET /tasks/{id}/history). No new API needed.
- **Repos**: Frontend only
- **Contract impact**: None

**Then**:
```bash
relay slice analytics-dashboard
relay agents
```

Agent implements and creates a PR. Walk through the PR review: "The agent made layout and visualization choices. A human reviews to make sure it looks right and the data tells the right story."

### 4. Feature 3: Recurring Tasks → Guided (~5 min)

**The pitch**: "This one changes the data model, requires API contract updates, and has real edge cases. A developer should drive this with AI assistance."

**Run `relay spec`** and provide:
- **Idea**: Recurring tasks with scheduling — when you complete a recurring task, the next occurrence is auto-created
- **Slug**: `recurring-tasks`
- **Execution mode**: `guided`
- **Scope**: New fields (recurrenceRule, nextOccurrence), API contract changes, backend auto-creation logic, frontend recurrence picker. Edge cases: timezone handling, what "complete" means for recurring tasks, supported patterns (daily/weekly/monthly).
- **Repos**: API + Frontend
- **Contract impact**: Yes — new fields in task schema

**Then**:
```bash
relay slice recurring-tasks
relay start
```

The human claims the task and works interactively with the AI agent. Show the collaborative experience — human makes architecture decisions, AI implements.

### 5. Wrap Up (~2 min)

```bash
relay status-report
```

Show all 3 features with their different execution modes. Highlight the decision framework: risk and complexity determine who's in the loop.

---

## Key Talking Points

| Question | Answer |
|----------|--------|
| "How do you decide which mode?" | Risk, complexity, and judgment required. Pure UI → autonomous. Creative output → supervised. Schema changes + edge cases → guided. |
| "Can a human pick up any task?" | Yes. `relay start` lets a human claim any ready task regardless of mode. The mode controls whether *agents* auto-claim, not whether humans can. |
| "What if the autonomous agent ships something bad?" | CI is still the gate. If tests fail, it doesn't merge. And you can always change a feature's mode if you realize it needs more oversight. |
| "Is this just for greenfield?" | No. Works for bug fixes too — `type: bug` in the task file, `fix/` branch prefix. Same mode selection applies. |

## Timing

| Section | Duration |
|---------|----------|
| Show app | ~2 min |
| Dark Mode (autonomous) | ~5 min |
| Analytics Dashboard (supervised) | ~5 min |
| Recurring Tasks (guided) | ~5 min |
| Wrap up | ~2 min |
| **Total** | **~19 min** |

Agent execution time is variable. For a tighter demo, you can pre-run the autonomous feature and start the demo showing "here's what shipped while I was getting coffee."
