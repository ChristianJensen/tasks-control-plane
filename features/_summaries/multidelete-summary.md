---
feature: multidelete
completed: 2026-03-21
tasks: 2
waves: 2
---

## Overview

Users currently have to delete tasks one at a time, which is tedious when cleaning up multiple completed or obsolete tasks. There is no way to select and remove several tasks in a single action, leading to repetitive clicks and a slow workflow for bulk task management.

## What Was Built

### Wave 1

- **api** — Add POST /tasks/batch-delete endpoint with input validation, deduplication, cascade deletion of comments/subtasks/auditEntries/statusHistory, and position compaction. Returns { deleted, notFound } response.

### Wave 2

- **frontend** — Add select mode toggle with task checkboxes, select-all checkbox, 'Delete selected' button, confirmation dialog, batch delete API integration, toast/snackbar feedback, and selection state management that clears on filter/sort changes.

## Key Decisions

- **wave-1-api-batch-delete-endpoint:** Modify `src/app.js`. Add the new route BEFORE the `/tasks/:id` routes (Express matches routes in order and `/tasks/batch-delete` must not be caught by `/tasks/:id`). Implementation steps: (1) Validate request body: `ids` must be a non-empty array of integers with max 50 items — return 400 otherwise. Also reject non-integer values (strings, null, etc.) with 400. (2) Deduplicate IDs using `[...new Set(ids)]`. (3) Iterate each unique ID: if task exists in the `tasks` Map, delete it and cascade-delete from `comments`, `subtasks`, `auditEntries`, and `statusHistory` Maps (same pattern as existing `DELETE /tasks/:id` at line 348-374). Also compact positions for each deleted task. Add ID to `deleted` array. If task not found, add to `notFound` array. (4) Return 200 with `{ deleted, notFound }`. Consider extracting the cascade-delete logic from the existing single-delete route into a helper function to avoid duplication — both routes should use the same logic. Tests go in `tests/tasks.test.js` (append to existing file).
- **wave-2-frontend-select-mode-batch-delete-ui:** Modify `src/App.jsx` (~1237 lines). All components are inline in this single file. Changes: (1) **State**: Add `const [selectMode, setSelectMode] = useState(false)` and `const [selectedIds, setSelectedIds] = useState(new Set())` near existing state declarations. Add `const [toast, setToast] = useState(null)` for toast messages. Add `const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)` for the confirmation dialog. (2) **Select mode toggle**: Add a button (e.g., using lucide-react `CheckSquare` icon) near the existing toolbar/filter area that toggles `selectMode`. When toggling off, clear `selectedIds`. (3) **Clear selection on filter/sort change**: In the existing filter and sort `onChange` handlers (or via a `useEffect` that watches filter/sort state), call `setSelectedIds(new Set())`. (4) **Task checkboxes**: In the TaskItem component, when `selectMode` is true, render a checkbox before the task title. Checkbox checked state: `selectedIds.has(task.id)`. On change: toggle the ID in the Set. (5) **Select all checkbox**: Above the task list, when `selectMode` is true, render a 'select all' checkbox. Checked when `selectedIds.size === filteredTasks.length && filteredTasks.length > 0`. Indeterminate when some but not all selected. On change: select all visible task IDs or clear all. (6) **Delete selected button**: Always visible when `selectMode` is true, disabled when `selectedIds.size === 0`. Shows count: 'Delete selected (N)'. (7) **Confirmation dialog**: A modal/overlay component (inline, ~40 lines) showing 'Delete N tasks? This will permanently delete the selected tasks and all their comments and history.' with Cancel and Delete buttons. (8) **Batch delete call**: `POST ${API_URL}/tasks/batch-delete` with `{ ids: [...selectedIds] }`. On success: re-fetch tasks, clear selection, exit select mode, show toast. Handle notFound silently (R14). On error: show error state. (9) **Toast component**: A small auto-dismiss component (~30 lines) positioned fixed bottom-center. Shows message like '5 tasks deleted'. Auto-dismisses after 3 seconds via `setTimeout`. Style with theme tokens. (10) **Tests** in `tests/App.test.jsx`: Test select mode toggle shows/hides checkboxes. Test individual selection. Test select all/deselect all. Test delete button disabled state. Test confirmation dialog appears. Test batch delete API call and response handling. Test toast appears after deletion. Test selection clears on filter change.

## Contracts Affected

(No contracts referenced)

## Retrospective Notes

(No retrospective entries)
