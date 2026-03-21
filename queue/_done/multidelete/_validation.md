# Decomposition Validation: multidelete

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | api | batch-delete-endpoint | high | 250 |
| 2 | frontend | select-mode-batch-delete-ui | high | 350 |

## Validation Checklist

- [ ] Each task can be implemented independently within its repo
- [ ] Cross-repo tasks coordinate only via contracts
- [ ] No task estimated >400 lines without split justification
- [ ] All tasks have appropriate priority set
- [ ] Each edge case from the Feature Spec maps to at least one task's acceptance criteria
- [ ] Contract changes are sufficient for all tasks
- [ ] No circular dependencies
- [ ] Tasks are grouped into waves, each wave <400 lines per repo

## Decisions

- **Two waves instead of three: The feature is cleanly split into API (foundation) and frontend (feature). There is no polish wave needed — the toast component is small enough (~30 lines) to include in the frontend task, and the confirmation dialog is part of the core UX, not polish.**
- **Single API task: The batch-delete endpoint is a single route handler with validation, dedup, and cascade logic. Extracting a helper from the existing single-delete is part of the same change. Total estimated at ~250 lines (40 lines route + 20 lines helper refactor + 190 lines tests). Splitting would create artificial dependencies in the same file.**
- **Single frontend task at 350 lines: All UI components live in one file (App.jsx). Select mode state, checkboxes, select all, confirmation dialog, toast, and API call are tightly coupled — splitting would require one task to leave broken/incomplete UI. The 350-line estimate (150 lines implementation + 200 lines tests) stays under the 400-line limit.**
- **Contract unchanged: The contract already includes POST /tasks/batch-delete and BatchDeleteResult schema at v0.6.0. No contract diff needed — carrying forward as-is.**
- **Route ordering matters: POST /tasks/batch-delete must be defined BEFORE the /tasks/:id routes in Express to avoid the :id parameter matching 'batch-delete' as a task ID.**
