---
status: in-progress
target-repo: frontend
wave: 1
priority: high
feature: task-status-workflow
type: feature
contracts:
  - contracts/tasks-api.json
---

# Add kanban board UI for task status workflow

## Description

Add a kanban board view with three columns (Todo, In Progress, Done) that displays tasks grouped by their `status` field. Each task card shows title and provides a way to change status. The kanban view replaces or augments the current list view.

## Why

The task-status-workflow feature needs a visual way to see tasks by status. A kanban board is the standard UX for this pattern and was chosen in the feature spec.

## Implementation Notes

**Files to modify:**
- `src/App.jsx` (~1237 lines) — all components live here
- `src/theme.js` (~57 lines) — add kanban-specific theme tokens if needed

**What to add:**
- A `KanbanBoard` component with 3 columns: Todo, In Progress, Done
- Each column renders task cards filtered by `status`
- Task cards display title, description preview, and a status change control (dropdown or buttons)
- Status change calls `PATCH /tasks/{taskId}` with `{ "status": "<new>" }`
- Fetch tasks using `GET /tasks` — the response now includes `status` field

**Patterns to follow:**
- Inline style objects using `theme` tokens (no CSS modules or Tailwind)
- `useState` + `useEffect` for state management
- `fetch()` with `API_URL` base for API calls
- Component functions defined in the same file (e.g., `function KanbanColumn({ ... })`)
- Icons from `lucide-react`

**Theme conventions (from `theme.js`):**
- Use `theme.colors.*` for colors
- Use `theme.card` base style for cards
- Use `theme.shadows.*` for glows/shadows
- Add status-specific colors to theme if needed (e.g., todo=slate, in-progress=cyan, done=green)

**Test patterns (from `tests/App.test.jsx`):**
- Mock `fetch` via `vi.stubGlobal('fetch', vi.fn(...))`
- Use `@testing-library/react` for rendering and assertions
- Test that kanban columns render with correct tasks
- Test that status change triggers API call

## Contract References

- `GET /tasks` — returns array of `Task` objects with `status` field
- `PATCH /tasks/{taskId}` — update status via `{ "status": "<new>" }`
- `TaskStatus` enum: `[todo, in-progress, done]`
- `Task` schema: `id`, `title`, `description`, `status`, `createdAt`, `updatedAt`

## Acceptance Criteria

- [ ] Kanban board renders 3 columns labeled "Todo", "In Progress", "Done"
- [ ] Tasks appear in the correct column based on their `status`
- [ ] Each task card displays the task title
- [ ] Users can change a task's status from the UI (e.g., dropdown or button)
- [ ] Changing status calls `PATCH /tasks/{taskId}` with the new status
- [ ] After status change, task moves to the correct column
- [ ] Empty columns show a placeholder/empty state
- [ ] New tasks created appear in the Todo column by default
- [ ] Theme tokens are used for styling (no hardcoded colors)
