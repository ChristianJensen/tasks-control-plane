---
feature: multiassign
completed: 2026-03-21
tasks: 4
waves: 2
---

## Overview

Users need a way to organize their tasks by category (work, personal, errands). Currently tasks have no categorization, making it hard to focus on a specific area. When many tasks need the same category, assigning them one-by-one is tedious. Users need to select multiple tasks and bulk assign a category in one action.

## What Was Built

### Wave 1

- **api** — Add nullable `category` enum field (work, personal, errands) to the Task model. Include category in task creation (defaults to null), in all task responses (GET list, GET single), and accept it in PATCH /tasks/{taskId} with validation. Invalid category values return 400.
- **api** — Add POST /tasks/batch-update-category endpoint that accepts an array of task IDs and a category value (including null to clear), updates matching tasks, and returns { updated, notFound } with partial success semantics. Requires X-User-Id header.

### Wave 2

- **frontend** — Add 'Assign Category' action to the existing multi-select toolbar alongside 'Delete'. Implement a category picker dropdown/modal with Work, Personal, Errands, and None options. Integrate with POST /tasks/batch-update-category API. Refresh task list after assignment.
- **frontend** — Display the assigned category on each task card/row as a visual badge. Add category color tokens to the theme. Show category in both the task list view and task detail view.

## Key Decisions

- **wave-1-api-add-category-field-and-patch-support:** Modify `src/app.js`. (1) Define `VALID_CATEGORIES = ['work', 'personal', 'errands']` constant near existing validation constants. (2) In task creation (POST /tasks), add `category: null` to new task objects. (3) In PATCH /tasks/:id, accept `category` in the request body. If provided and not null, validate against VALID_CATEGORIES — return 400 for invalid values. If `null`, set category to null (clear). Include category in the update logic. (4) Ensure `taskWithCount()` or equivalent passes through the category field in responses. (5) Add tests in `tests/tasks.test.js`: create task has category:null, PATCH sets category, PATCH clears category with null, PATCH rejects invalid category, GET returns category.
- **wave-1-api-batch-update-category-endpoint:** Modify `src/app.js`. (1) Add route BEFORE `/tasks/:id` routes (same placement strategy as batch-delete). (2) Validate X-User-Id header — return 400 if missing (A3 refinement). (3) Validate request body: `ids` must be non-empty array of integers, max 50 items — return 400 otherwise. Also reject non-integer values. (4) Validate `category`: must be a valid category string or null — return 400 for invalid values (reject entire request per E2). (5) Deduplicate IDs with `[...new Set(ids)]`. (6) Iterate each unique ID: if task exists, update category and updatedAt, add to `updated` array; if not found, add to `notFound` array. (7) Return 200 with `{ updated, notFound }`. Consider extracting shared batch validation logic from batch-delete into a helper to prevent divergence (AR2). Add tests in `tests/tasks.test.js`: happy path, partial success, all not found (E1), invalid category rejects entire request (E2), missing X-User-Id returns 400, empty array returns 400, >50 IDs returns 400, duplicate IDs are deduped, null category clears, task deleted mid-batch appears in notFound (E3).
- **wave-2-frontend-bulk-assign-category-ui:** Modify `src/App.jsx`. (1) Find the existing selection toolbar (added by multidelete feature) that shows when tasks are selected. Add an 'Assign Category' button next to the existing 'Delete selected' button. Use a lucide-react icon (e.g., `Tag` or `FolderOpen`). (2) Add state: `const [showCategoryPicker, setShowCategoryPicker] = useState(false)`. (3) Create `CategoryPicker` inline component (~40 lines): a dropdown or small modal showing four options — Work, Personal, Errands, None (to clear). Each option has the category color from theme. Clicking an option triggers the API call. (4) API call: `POST ${API_URL}/tasks/batch-update-category` with `{ ids: [...selectedIds], category: selectedCategory }` and `X-User-Id` header. (5) On success: re-fetch tasks, clear selection, close picker, show toast (reuse existing toast component from multidelete). Handle notFound silently. (6) On error: show error state. (7) Close picker on backdrop click or Escape. (8) Add tests in `tests/App.test.jsx`: 'Assign Category' button appears when tasks selected (AC7), category picker shows 4 options (AC8), selecting category calls batch API with correct payload, task list refreshes after assignment (AC9), picker closes after selection, error handling.
- **wave-2-frontend-display-category-on-task-cards:** Modify `src/App.jsx` and `src/theme.js`. (1) In `theme.js`, add category color map (similar to priority colors) — e.g., `categoryColors: { work: '#...', personal: '#...', errands: '#...' }` with labels. (2) In `App.jsx`, create a `CategoryBadge` inline component (~15 lines) that renders a small colored pill/badge with the category label. Returns null if category is null. Follow the PriorityBadge pattern. (3) Add CategoryBadge to the TaskItem component in the task list, near existing badges. (4) Add CategoryBadge to the task detail view. (5) Add tests in `tests/App.test.jsx`: task with category shows badge, task without category shows no badge, all three category values render correctly. Add theme tests in `tests/theme.test.js` for new tokens.

## Contracts Affected

(No contracts referenced)

## Retrospective Notes

(No retrospective entries)
