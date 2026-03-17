# Validation Checklist: task-sorting

## Decomposition Validation

- [x] Each task can be implemented independently within its repo
- [x] Cross-repo tasks coordinate only via contracts
- [x] No task estimated >400 lines without split justification
- [x] All tasks have appropriate priority set
- [x] Each edge case from the Feature Spec maps to at least one task's acceptance criteria
- [x] Contract changes are sufficient for all tasks
- [x] No circular dependencies
- [x] Critical-priority tasks have no unresolved dependencies
- [x] Tasks are grouped into waves, each wave <400 lines per repo
- [x] Wave ordering respects cross-wave dependencies

## Edge Case Coverage

| Edge Case (from spec) | Task | Acceptance Criterion |
|----------------------|------|---------------------|
| E1: Same title tiebreaker | API sort endpoint | Tiebreaker: tasks with equal sort values sub-sorted by createdAt desc |
| E2: Invalid sort param | API sort endpoint | Returns 400 with valid values listed |
| E3: Sort + status filter combined | API sort endpoint | Sort works alongside existing filters |

## Task Summary

| Wave | Repo | Task | Size | Est. Lines |
|------|------|------|------|-----------|
| 1 | api | wave-1-api-sort-endpoint.md | medium | ~120 |
| 1 | frontend | wave-1-frontend-sort-dropdown.md | medium | ~160 |

**Total:** 2 tasks, 1 wave, 2 repos

## Decisions

- **Why 1 wave instead of 2:** Both tasks are medium-sized and implement against the shared contract independently. The frontend mocks API responses in tests, so it doesn't need the API deployed first. One wave enables parallel agent execution.
- **Why no separate "sort within Kanban columns" task:** The client-side column sort is ~10 lines of code tightly coupled to the dropdown state. Splitting it would create a task too small to stand alone.
