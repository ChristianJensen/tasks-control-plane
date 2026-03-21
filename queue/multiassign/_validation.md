# Decomposition Validation: multiassign

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | api | add-category-field-and-patch-support | high | 80 |
| 1 | api | batch-update-category-endpoint | high | 130 |
| 2 | frontend | display-category-on-task-cards | high | 90 |
| 2 | frontend | bulk-assign-category-ui | high | 160 |

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

- **2 waves instead of 3: The feature is small enough that wave 1 (API foundation) and wave 2 (frontend features) cover everything. No polish wave needed — category display and bulk assign are tightly coupled and belong in the same wave.**
- **API split into 2 tasks: The category field addition (PATCH support) is a prerequisite for the batch endpoint. Separating them keeps each task focused and under 200 lines. The batch endpoint task can reuse validation patterns established in the first task.**
- **Frontend split into 2 tasks: Display (CategoryBadge) is a prerequisite for the bulk assign UI — users need to see categories before bulk assigning makes sense. The display task is small (~90 lines) and the bulk assign task is medium (~160 lines), both well under the 400-line limit.**
- **All tasks use 'supervised' execution: No auth/security/payment concerns (X-User-Id is a simple header, not real auth). No database migrations (in-memory store). Default supervised mode is appropriate for all tasks.**
- **Wave 2 frontend tasks have no cross-repo depends_on: Frontend coordinates with API via the shared contract, not via task dependencies. Wave ordering ensures API is built first.**
