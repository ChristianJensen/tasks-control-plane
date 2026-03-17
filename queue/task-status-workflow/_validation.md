# Validation: task-status-workflow

## Checklist

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

## Task Summary

| Wave | Repo | Task | Est. Lines | Size |
|------|------|------|-----------|------|
| 1 | api | Add status field + filter | ~150 | medium |
| 1 | frontend | Kanban board UI | ~250 | large |

## Edge Case Mapping

| Edge Case | Mapped To |
|-----------|-----------|
| E1: Empty title | Existing API validation (unchanged) |
| E2: PATCH with no fields | Existing API behavior (unchanged) |
| E3: Invalid status filter | API task AC: `GET /tasks?status=invalid` returns 400 |
| E4: Deleting task with comments | Existing cascade delete (API task AC confirms preserved) |
| E5: GET after deletion | Existing 404 behavior (unchanged) |

## Decisions

- **Why 1 wave instead of 2+:** The API already has full task CRUD — we're adding fields and a filter, not building from scratch. The frontend kanban is self-contained UI. Both are under 400 lines and have no dependencies on each other beyond the contract.
- **Why the frontend task is large, not medium:** The kanban board is a new UI paradigm (3 columns + cards + status controls) — it touches rendering, state, API calls, and theme tokens. However it cannot be split further since the columns and cards are one logical unit.
- **Existing `completed` boolean:** The API currently uses `completed: boolean`. The new `status` field coexists with it — no migration needed. The feature spec's scope doesn't include removing `completed`.
