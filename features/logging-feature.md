---
lifecycle: completed
version: 1
paused-at: ""
paused-by: ""
pause-reason: ""
deployed-at: ""
deployed-env: ""
---
# Feature Spec: Task Status Transition Log

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| S1 | conversation | Planner interview | User | 2026-03-19 |
| S2 | refinement | Planner refinement rounds 1–3 | User + Planner | 2026-03-19 |

## Problem Statement

When a task's status changes (e.g., todo → in-progress → done), there is no record of who made the change or when it happened. Users and teams have no visibility into the workflow history of a task, making it hard to understand how work progressed or who moved it forward. This feature adds an immutable audit trail of status transitions, exposed via API and visible in the frontend task detail view.

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | Record every task status transition with old status, new status, who changed it (X-User-Id), and timestamp | S1 | High | |
| R2 | Provide a `GET /tasks/{taskId}/history` endpoint returning the ordered list of status transitions | S1 | High | |
| R3 | Display the status transition history on the task detail view in the frontend | S1 | High | |
| R4 | The history log is immutable — no update or delete operations | S1 | High | |
| R5 | Only status changes are tracked — title, description, create, and delete events are out of scope | S1 | High | |
| R6 | A no-op status update (setting status to its current value) should NOT create a history entry | S1 | Med | Implied by existing PATCH behavior: "Setting status to its current value is a no-op" |
| R7 | `PATCH /tasks/{taskId}` now requires the `X-User-Id` header (breaking change) | S2 | High | Needed to identify who changed the status; enforced immediately with 400 on missing header |
| R8 | Task creation does NOT generate a history entry — history only tracks changes via PATCH | S2 | High | The task's createdAt already records when it was born |
| R9 | Mixed PATCH requests (status + title/description) create a history entry for the status change; other field changes are irrelevant to history | S2 | High | |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| None | No conflicts detected | resolved |

## Open Questions

- [x] Should history entries be paginated, or is returning the full list acceptable? — **Resolved: full list, no pagination for v1** (S2, Round 1)
- [x] Should the history endpoint return entries newest-first or oldest-first? — **Resolved: oldest-first (ascending changedAt) for natural timeline reading** (S2, Round 2)

## Acceptance Criteria

- [ ] When a task's status is changed via `PATCH /tasks/{taskId}`, a history entry is persisted with: taskId, oldStatus, newStatus, changedBy (from X-User-Id), and changedAt timestamp
- [ ] `GET /tasks/{taskId}/history` returns an array of status transition entries ordered by changedAt ascending (oldest first)
- [ ] `GET /tasks/{taskId}/history` returns 404 if the task does not exist
- [ ] `GET /tasks/{taskId}/history` returns an empty array `[]` if the task exists but has no status transitions
- [ ] No-op status updates (same status) do not create history entries
- [ ] There are no endpoints to update or delete history entries
- [ ] The frontend task detail view displays the list of status transitions showing: old status, new status, who changed it, and when
- [ ] History entries are cascade-deleted when the parent task is deleted
- [ ] `PATCH /tasks/{taskId}` requires the `X-User-Id` header; requests without it return 400
- [ ] A PATCH that changes both title/description and status still creates a history entry for the status change
- [ ] Concurrent status changes both succeed (last write wins) and each creates its own history entry

## Out of Scope

- Tracking title or description changes
- Tracking task creation or deletion events
- Editing or deleting history entries
- Filtering or searching history across tasks (global audit log)
- Notifications or webhooks on status change
- Status transition validation / workflow enforcement (e.g., preventing done → todo)
- Computed duration fields (time spent in each status)
- Pagination of history entries (acceptable for v1)

## Refinement Log

### Round 1: Assumptions

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | The X-User-Id header (already used for comments) identifies who changed the status | **Yes** | X-User-Id is NOT currently required on PATCH — only on comment endpoints. **Decision: make X-User-Id required on PATCH (breaking change).** Requests without it return 400. Enforced immediately, no grace period. (R7) |
| A2 | History entries are cascade-deleted when the parent task is deleted | **Yes** | Confirmed: cascade delete is acceptable. Audit evidence does not need to survive task deletion. Consistent with existing comment cascade behavior. |
| A3 | The API returns the full history list without pagination | **Yes** | Confirmed: no pagination for v1. Tasks rarely have hundreds of transitions. No hard cap needed. |
| A4 | Task creation does NOT generate a history entry (initial status assignment is not a "transition") | **Yes** | Confirmed: history only tracks changes via PATCH. The task's createdAt already records birth. Creating a task with status 'in-progress' does not generate a null → in-progress entry. (R8) |

### Round 2: Edge Cases

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | No-op status update (PATCH with same status) | R6 | No history entry created |
| E2 | Task is deleted — what happens to history? | A2 | Cascade delete, same as comments |
| E3 | GET history for non-existent task | AC line 3 | Return 404 |
| E4 | Task has no status transitions yet | AC line 4 | Return empty array `[]` |
| E5 | Concurrent PATCH requests change status simultaneously | AC line 11 | Both succeed (last write wins), each creates its own history entry with its own timestamp. No optimistic locking. |
| E6 | Mixed PATCH (title + status change in one request) | R9, AC line 10 | History entry created for the status change; title change is irrelevant to history |
| E7 | PATCH without X-User-Id header | R7, AC line 9 | Return 400 immediately. No grace period — breaking change enforced from deployment. |

### Round 3: Scope Boundaries

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | Track all field changes (title, description) | Out | User explicitly scoped to status transitions only |
| B2 | Global activity feed across all tasks | Out | User scoped to per-task history |
| B3 | Notifications on status change | Out | Separate concern, not requested |
| B4 | Task creation/deletion audit events | Out | User explicitly scoped to status transitions only |
| B5 | Undo status change | Out | History is immutable |
| B6 | Status transition validation / workflow rules | Out | This feature logs transitions, does not enforce which are valid. Any status → any status remains allowed. |
| B7 | Computed duration fields (time in each status) | Out | Consumers can compute durations client-side from timestamps. Keeps API simple. |
| B8 | Global history endpoint (GET /history) | Out | Only per-task history. Global audit is a separate feature. |

## Readiness Checklist

- [x] All High-confidence requirements have acceptance criteria
- [x] No unresolved conflicts remain
- [x] Open questions are non-blocking or have owners
- [x] At least 3 assumptions explicitly challenged and resolved
- [x] At least 3 edge cases explicitly addressed
- [x] Out of Scope section reviewed via scope boundary probe
