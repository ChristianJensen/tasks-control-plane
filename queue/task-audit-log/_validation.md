# Validation Checklist: task-audit-log

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

## Edge Case Mapping

| Edge Case | Mapped To |
|-----------|-----------|
| E1: No-op status update | AC: "same completed value does NOT create an audit entry" |
| E2: Task creation (null old status) | AC: "oldStatus: null, newStatus: todo" |
| E3: Task deleted — cascade | AC: "cascade-deletes all associated audit entries" |

## Sizing Estimate

| Task | Repo | Wave | Est. Lines |
|------|------|------|------------|
| wave-1-api-audit-endpoints | api | 1 | ~190 (40 app + 150 test) |
| **Total** | | | **~190** |

## Decisions

- **Why single wave, single task:** The entire feature lives in `src/app.js` (store + 3 route modifications + 1 new route). Splitting into separate "model" and "endpoint" tasks would be artificial since everything is in one file. Tests are tightly coupled to the routes.
- **Why API-only:** Frontend UI for audit history is explicitly out of scope per the feature spec. Only the API repo is affected.
- **Why high priority (not critical):** The feature is new functionality with no existing broken behavior. High ensures it's picked up promptly but doesn't jump ahead of any bugfixes.
