---
lifecycle: draft
version: 1
paused-at: ""
paused-by: ""
pause-reason: ""
deployed-at: ""
deployed-env: ""
---

# Feature Spec: Task Audit Log

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| S1 | conversation | Claude Code session | Christian Jensen | 2026-03-19 |

## Problem Statement

There is no way to see what happened to a task over time. When a task's status changes, the previous state is lost — you can only see the current snapshot. Users need a history trail to understand when and by whom status transitions occurred.

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | Record an audit entry whenever a task's status changes | S1 | High | Captures oldStatus → newStatus |
| R2 | Record an initial audit entry when a task is created | S1 | High | oldStatus: null, newStatus: "todo" |
| R3 | Each audit entry records who made the change via X-User-Id | S1 | High | Reuses existing header convention |
| R4 | Audit entries are accessed via GET /tasks/{taskId}/audit | S1 | High | Nested under task, returns newest first |
| R5 | Return all audit entries (no pagination) | S1 | High | Status-only logs stay small (~10 entries max) |
| R6 | Each audit entry includes old and new status values | S1 | High | Makes history self-contained |
| R7 | No-op status updates (same status) do not create an audit entry | S1 | High | Keeps log clean |
| R8 | Audit entries are cascade-deleted when a task is deleted | S1 | High | Consistent with comment cascade behavior |

## Conflicts Detected

_None._

## Open Questions

_None — all questions resolved during interview._

## Acceptance Criteria

- [ ] POST /tasks creates a task AND an audit entry with `oldStatus: null`, `newStatus: "todo"`, and the caller's X-User-Id as `userId`
- [ ] PATCH /tasks/{id} with a status change creates an audit entry with old and new status values
- [ ] PATCH /tasks/{id} with the same status (no-op) does NOT create an audit entry
- [ ] PATCH /tasks/{id} changing only title/description (no status change) does NOT create an audit entry
- [ ] GET /tasks/{taskId}/audit returns all audit entries for that task, newest first
- [ ] Each audit entry contains: id, taskId, oldStatus (nullable), newStatus, userId, createdAt
- [ ] DELETE /tasks/{id} cascade-deletes all associated audit entries
- [ ] GET /tasks/{taskId}/audit returns 404 if the task does not exist
- [ ] GET /tasks/{taskId}/audit returns an empty array for a task with no status changes (edge case: should not happen since creation logs)

## Out of Scope

- Field change tracking (title/description edits)
- Global activity feed across tasks
- Undo / revert functionality based on audit log
- Frontend UI for audit history (API-only for now)

## Refinement Log

### Round 1: Assumptions

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | Audit entries cascade-delete with the task | Yes | Confirmed — consistent with comments behavior |
| A2 | No pagination needed | Yes | Confirmed — status-only changes cap at ~10 entries per task |
| A3 | Both old and new status values are recorded | Yes | Confirmed — makes log self-contained |

### Round 2: Edge Cases

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | No-op status update (set to current value) | R7 | Skip audit entry — no change occurred |
| E2 | Task creation (no "old" status exists) | R2 | Log with oldStatus: null, newStatus: "todo" |
| E3 | Task deleted — what happens to audit? | R8 | Cascade delete, consistent with comments |

### Round 3: Scope Boundaries

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | Field change tracking (title/description) | Out | Increases complexity; status tracking covers the core need |
| B2 | Global activity feed | Out | Separate feature; audit log is per-task |
| B3 | Undo / revert | Out | Audit is read-only history, not a state machine |
| B4 | Frontend audit UI | Out | API-only in this iteration; UI can be a follow-up feature |

## Readiness Checklist

- [x] All High-confidence requirements have acceptance criteria
- [x] No unresolved conflicts remain
- [x] Open questions are non-blocking or have owners
- [x] At least 3 assumptions explicitly challenged and resolved
- [x] At least 3 edge cases explicitly addressed
- [x] Out of Scope section reviewed via scope boundary probe
