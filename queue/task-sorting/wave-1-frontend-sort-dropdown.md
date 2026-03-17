---
status: in-progress
target-repo: frontend
wave: 1
priority: high
feature: task-sorting
type: feature
contracts:
  - contracts/tasks-api.json
---

## Description

Add a sort dropdown control to the task list UI. The dropdown lets users pick a sort order (Newest, Oldest, Title A-Z, Title Z-A, Status). The selection is persisted in URL query params and passed to the API.

## Why

Users need a visual control to change task ordering. The API sort params (from the sibling API task) are useless without a frontend to drive them.

## Implementation Notes

**File to modify:** `src/App.jsx` (~1237 lines)

**Sort options mapping** — define near the existing `KANBAN_COLUMNS` constant:
```
SORT_OPTIONS = [
  { label: 'Newest', sort: 'createdAt', order: 'desc' },
  { label: 'Oldest', sort: 'createdAt', order: 'asc' },
  { label: 'Title A-Z', sort: 'title', order: 'asc' },
  { label: 'Title Z-A', sort: 'title', order: 'desc' },
  { label: 'Status', sort: 'status', order: 'asc' },
]
```

**URL query param persistence:**
- On mount, read `sort` and `order` from `window.location.search` (use `URLSearchParams`)
- When the user selects a sort option, update state AND `window.history.replaceState` to update the URL without a page reload
- Default to `createdAt`/`desc` if no params present

**API integration:**
- In `fetchTasks`, append `sort` and `order` to the existing `URLSearchParams` builder (follows the pattern already used for `search`)

**Dropdown UI:**
- Render a `<select>` styled to match the existing filter controls (inline styles, theme tokens)
- Place it next to the existing category filter pills and search input
- Show the currently active sort option

**Kanban column sorting:**
- In `KanbanBoard`, after filtering tasks by status for each column, apply the current sort within each column
- Reuse the same sort field/order from state — the API returns sorted data, but the Kanban grouping re-splits it, so apply client-side sort within columns using the same logic

**Test file:** `tests/App.test.jsx` (~1669 lines)

Add tests for:
- Sort dropdown renders with all options
- Selecting a sort option updates the URL query params
- `fetchTasks` sends sort/order params to the API
- Page load with sort params in URL pre-selects the correct option
- Kanban columns respect the selected sort order

## Contract References

`GET /tasks` — `sort` param (enum: `createdAt`, `title`, `status`) and `order` param (enum: `asc`, `desc`). See contract v0.4.0.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Contract-compliant
- [ ] Sort dropdown is visible in the UI toolbar
- [ ] Dropdown shows options: Newest, Oldest, Title A-Z, Title Z-A, Status
- [ ] Selecting a sort option triggers a new API call with sort/order params
- [ ] URL updates with ?sort=...&order=... on selection (replaceState, no page reload)
- [ ] Page reload with sort params in URL restores the correct dropdown selection
- [ ] Kanban board sorts cards within each column by the selected sort
- [ ] Default selection is "Newest" (createdAt desc) when no URL params present
