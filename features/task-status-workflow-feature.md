---
lifecycle: active
version: 1
paused-at: ""
paused-by: ""
pause-reason: ""
---

# Feature Spec: Task Status Workflow

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| 1 | conversation | (planning session) | Christian Jensen | 2026-03-17 |

## Problem Statement

The Tasks app has no task CRUD or status management. Users cannot create tasks, track their progress, or visualize work status. This feature adds a 3-state status workflow (`todo`, `in-progress`, `done`) with full task CRUD and a kanban board UI.

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | Tasks have a `status` field with values: `todo`, `in-progress`, `done` | S1 | High | Enum enforced in API |
| R2 | Status transitions are free-form (any status → any status) | S1 | High | No state-machine enforcement |
| R3 | `POST /tasks` creates a task; `status` defaults to `todo` if omitted | S1 | High | `title` required, `description` optional |
| R4 | `GET /tasks` lists tasks with optional `?status=` filter (comma-separated) | S1 | High | e.g. `?status=todo,in-progress` |
| R5 | `GET /tasks/{taskId}` returns a single task | S1 | High | |
| R6 | `PATCH /tasks/{taskId}` updates task fields including status | S1 | High | Partial update semantics |
| R7 | `DELETE /tasks/{taskId}` deletes a task and cascades to its comments | S1 | High | |
| R8 | No-op status update returns 200 OK (idempotent) | S1 | High | Setting status to current value is fine |
| R9 | No ownership — any user can change any task's status | S1 | High | |
| R10 | Frontend displays a kanban board with columns: Todo, In Progress, Done | S1 | High | |

## Conflicts Detected

_None — single-source feature._

## Open Questions

_None — all decisions resolved during interview._

## Acceptance Criteria

- [ ] `POST /tasks` with `{ "title": "My task" }` creates a task with `status: "todo"`
- [ ] `POST /tasks` with `{ "title": "X", "status": "in-progress" }` creates with that status
- [ ] `POST /tasks` with invalid status returns 400
- [ ] `GET /tasks` returns all tasks
- [ ] `GET /tasks?status=todo` returns only todo tasks
- [ ] `GET /tasks?status=todo,done` returns tasks matching either status
- [ ] `GET /tasks/{taskId}` returns 404 for nonexistent task
- [ ] `PATCH /tasks/{taskId}` with `{ "status": "done" }` updates status and returns 200
- [ ] `PATCH /tasks/{taskId}` setting same status returns 200 (no-op is OK)
- [ ] `DELETE /tasks/{taskId}` removes the task and all its comments
- [ ] `DELETE /tasks/{taskId}` returns 404 for nonexistent task
- [ ] Frontend renders 3 kanban columns: Todo, In Progress, Done
- [ ] Tasks appear in the correct column based on status
- [ ] Users can change task status from the UI

## Out of Scope

- Drag-and-drop between kanban columns
- Status change history / audit log
- Due dates
- Priorities
- Task assignees / ownership

## Refinement Log

### Round 1: Assumptions

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | Task `title` is required, `description` is optional | Yes | Confirmed — title is the minimum viable task |
| A2 | Task IDs are server-generated integers | Yes | Confirmed — consistent with existing Comment schema |
| A3 | No pagination on `GET /tasks` for v1 | Yes | Accepted — keep simple; pagination is a future enhancement |
| A4 | `updatedAt` auto-updates on any PATCH | Yes | Confirmed — server manages timestamps |

### Round 2: Edge Cases

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | Creating a task with empty title | R3 | 400 Bad Request — title has minLength: 1 |
| E2 | PATCH with no fields | R6 | 400 Bad Request — at least one field required |
| E3 | Filtering with invalid status value | R4 | 400 Bad Request — must be valid enum values |
| E4 | Deleting a task that has comments | R7 | Cascade delete — comments removed first |
| E5 | GET single task after deletion | R5 | 404 Not Found |

### Round 3: Scope Boundaries

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | Drag-and-drop kanban | Out | Adds complexity; ship basic status changes first |
| B2 | Task assignment / ownership | Out | No user management yet |
| B3 | Status transition rules | Out | Free-form transitions are simpler and sufficient |
| B4 | Pagination / sorting | Out | Not needed at current scale |
| B5 | Bulk status update | Out | Single-task updates are sufficient for v1 |

## Readiness Checklist

- [x] All High-confidence requirements have acceptance criteria
- [x] No unresolved conflicts remain
- [x] Open questions are non-blocking or have owners
- [x] At least 3 assumptions explicitly challenged and resolved
- [x] At least 3 edge cases explicitly addressed
- [x] Out of Scope section reviewed via scope boundary probe
