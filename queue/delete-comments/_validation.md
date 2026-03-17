# Decomposition Validation: delete-comments

## Checklist

- [x] Each task can be implemented independently within its repo
- [x] Cross-repo tasks coordinate only via contracts
- [x] No task estimated >400 lines without split justification
- [x] All tasks have appropriate priority set
- [x] Each edge case from Feature Spec maps to at least one task's acceptance criteria
- [x] Contract changes are sufficient for all tasks
- [x] No circular dependencies
- [x] Critical-priority tasks have no unresolved dependencies
- [x] Tasks are grouped into waves, each wave <400 lines per repo
- [x] Wave ordering respects cross-wave dependencies

## Edge Case Mapping

| Edge Case | Task | Acceptance Criterion |
|-----------|------|---------------------|
| E1: Double-delete | API task | "non-existent comment returns 404" |
| E2: Non-author attempts delete | API task (403 check) + Frontend task (button hidden) | Both tasks have specific AC |
| E3: Deleting last comment | API task + Frontend task | Both have "empty list" AC |

## Wave Summary

| Wave | Repo | Task | Est. Lines | Size |
|------|------|------|------------|------|
| 1 | api | delete-comment-endpoint | ~90 | small-medium |
| 1 | frontend | delete-comment-ui | ~130 | medium |

**Total wave 1:** ~90 lines (api) + ~130 lines (frontend) — well under 400 per repo.

## Status
All tasks created with `status: ready`. Single wave — both tasks can run in parallel against the shared contract.

## Decisions

- **Why single wave instead of two:** The feature is small enough that both API endpoint and frontend UI fit in wave 1. The frontend can implement against the contract without waiting for the API to be merged — they coordinate via `contracts/tasks-api.json`.
- **Why `X-User-Id` header instead of proper auth:** The app has no authentication system. A header-based identity is the minimal mechanism needed to implement ownership checks without adding a full auth stack. This can be upgraded to JWT/session auth later.
- **Why `window.confirm()` instead of a custom modal:** No confirmation dialog pattern exists in the frontend. A browser-native confirm is sufficient for the feature spec requirement and avoids adding a modal component for a single use case.
