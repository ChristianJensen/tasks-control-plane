---
status: done
target-repo: frontend
wave: 2
priority: high
feature: multidelete
type: feature
depends-on:
  - wave-1-api-batch-delete-endpoint.md
claimed-by: agent-06-36-06-7A-C3-F6-58877
claimed-at: 2026-03-21T02:03:53Z
claimed-on: 06-36-06-7A-C3-F6
---

## Description

Add select mode toggle with task checkboxes, select-all checkbox, 'Delete selected' button, confirmation dialog, batch delete API integration, toast/snackbar feedback, and selection state management that clears on filter/sort changes.

## Why

This is the complete frontend experience for multi-delete. It depends on the batch-delete API endpoint from wave 1 being available.

## Implementation Notes

Modify `src/App.jsx` (~1237 lines). All components are inline in this single file. Changes: (1) **State**: Add `const [selectMode, setSelectMode] = useState(false)` and `const [selectedIds, setSelectedIds] = useState(new Set())` near existing state declarations. Add `const [toast, setToast] = useState(null)` for toast messages. Add `const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)` for the confirmation dialog. (2) **Select mode toggle**: Add a button (e.g., using lucide-react `CheckSquare` icon) near the existing toolbar/filter area that toggles `selectMode`. When toggling off, clear `selectedIds`. (3) **Clear selection on filter/sort change**: In the existing filter and sort `onChange` handlers (or via a `useEffect` that watches filter/sort state), call `setSelectedIds(new Set())`. (4) **Task checkboxes**: In the TaskItem component, when `selectMode` is true, render a checkbox before the task title. Checkbox checked state: `selectedIds.has(task.id)`. On change: toggle the ID in the Set. (5) **Select all checkbox**: Above the task list, when `selectMode` is true, render a 'select all' checkbox. Checked when `selectedIds.size === filteredTasks.length && filteredTasks.length > 0`. Indeterminate when some but not all selected. On change: select all visible task IDs or clear all. (6) **Delete selected button**: Always visible when `selectMode` is true, disabled when `selectedIds.size === 0`. Shows count: 'Delete selected (N)'. (7) **Confirmation dialog**: A modal/overlay component (inline, ~40 lines) showing 'Delete N tasks? This will permanently delete the selected tasks and all their comments and history.' with Cancel and Delete buttons. (8) **Batch delete call**: `POST ${API_URL}/tasks/batch-delete` with `{ ids: [...selectedIds] }`. On success: re-fetch tasks, clear selection, exit select mode, show toast. Handle notFound silently (R14). On error: show error state. (9) **Toast component**: A small auto-dismiss component (~30 lines) positioned fixed bottom-center. Shows message like '5 tasks deleted'. Auto-dismisses after 3 seconds via `setTimeout`. Style with theme tokens. (10) **Tests** in `tests/App.test.jsx`: Test select mode toggle shows/hides checkboxes. Test individual selection. Test select all/deselect all. Test delete button disabled state. Test confirmation dialog appears. Test batch delete API call and response handling. Test toast appears after deletion. Test selection clears on filter change.

## Contract References

POST /tasks/batch-delete — sends `{ ids: integer[] }`, receives `{ deleted: integer[], notFound: integer[] }` with status 200. Status 400 for validation errors.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Contract-compliant with POST /tasks/batch-delete
- [ ] Select mode toggle shows checkboxes on each task row when active (AC6)
- [ ] Select all checkbox selects/deselects all visible tasks (AC7)
- [ ] Delete selected button is always visible in select mode but disabled until ≥1 task selected (AC8)
- [ ] Clicking Delete selected shows confirmation dialog with count and cascade warning (AC9)
- [ ] After confirmed deletion, task list refreshes and selection state resets (AC10)
- [ ] Changing filters or sort order clears all task selections (AC12, R15)
- [ ] After successful batch delete, a toast shows 'N tasks deleted' (AC13)
- [ ] notFound items in response are silently ignored — no error shown to user (R14)
- [ ] Select mode is ephemeral — lost on navigation/refresh (R9)
- [ ] Toast auto-dismisses after a few seconds
