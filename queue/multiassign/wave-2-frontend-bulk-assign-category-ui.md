---
status: pending
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: multiassign
type: feature
depends-on:
  - wave-2-frontend-display-category-on-task-cards.md
---

## Description

Add 'Assign Category' action to the existing multi-select toolbar alongside 'Delete'. Implement a category picker dropdown/modal with Work, Personal, Errands, and None options. Integrate with POST /tasks/batch-update-category API. Refresh task list after assignment.

## Why

Core user-facing feature. R5 (toolbar action), R6 (category picker), AC7-AC9. Reuses existing multi-select mode from batch-delete feature.

## Implementation Notes

Modify `src/App.jsx`. (1) Find the existing selection toolbar (added by multidelete feature) that shows when tasks are selected. Add an 'Assign Category' button next to the existing 'Delete selected' button. Use a lucide-react icon (e.g., `Tag` or `FolderOpen`). (2) Add state: `const [showCategoryPicker, setShowCategoryPicker] = useState(false)`. (3) Create `CategoryPicker` inline component (~40 lines): a dropdown or small modal showing four options — Work, Personal, Errands, None (to clear). Each option has the category color from theme. Clicking an option triggers the API call. (4) API call: `POST ${API_URL}/tasks/batch-update-category` with `{ ids: [...selectedIds], category: selectedCategory }` and `X-User-Id` header. (5) On success: re-fetch tasks, clear selection, close picker, show toast (reuse existing toast component from multidelete). Handle notFound silently. (6) On error: show error state. (7) Close picker on backdrop click or Escape. (8) Add tests in `tests/App.test.jsx`: 'Assign Category' button appears when tasks selected (AC7), category picker shows 4 options (AC8), selecting category calls batch API with correct payload, task list refreshes after assignment (AC9), picker closes after selection, error handling.

## Contract References

POST /tasks/batch-update-category — requestBody { ids, category }, 200 response { updated, notFound }, 400 response. X-User-Id header required.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Contract-compliant: calls POST /tasks/batch-update-category with correct payload
- [ ] Multi-select toolbar shows 'Assign Category' action when tasks are selected (AC7)
- [ ] Category picker shows Work, Personal, Errands, and None options (AC8)
- [ ] After bulk assign, task list refreshes and shows updated categories (AC9)
- [ ] Sends X-User-Id header with batch request
- [ ] Picker closes after category selection
- [ ] Error state shown on API failure
- [ ] Reuses existing multi-select mode (checkboxes) from batch-delete feature (R5)
