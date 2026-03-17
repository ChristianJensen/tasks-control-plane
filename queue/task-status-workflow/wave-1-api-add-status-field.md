---
status: in-progress
target-repo: api
wave: 1
priority: high
feature: task-status-workflow
type: feature
contracts:
  - contracts/tasks-api.json
---

# Add status field, description, updatedAt, and status filter to Tasks API

## Description

Add a `status` enum field (`todo`, `in-progress`, `done`) to the task model with a default of `todo`. Add `description` (optional string, max 2000 chars) and `updatedAt` (auto-managed timestamp) fields. Add `?status=` comma-separated query parameter filtering to `GET /tasks`. Validate status values on `POST` and `PATCH`.

## Why

The task-status-workflow feature requires tasks to have a workflow status for kanban visualization. The API currently uses a boolean `completed` field — this adds a richer status model alongside it.

## Implementation Notes

**Files to modify:**
- `src/app.js` (~300 lines) — all routes and models are here

**What to change:**
- Add `VALID_STATUSES = ['todo', 'in-progress', 'done']` constant (line ~5 area)
- In `POST /tasks` handler (line ~76): add `status` field defaulting to `'todo'`, add `description` field, add `updatedAt: new Date().toISOString()`. Validate status against enum if provided.
- In `PATCH /tasks/:id` handler (line ~109): support updating `status` and `description`. Update `updatedAt` on any change. Validate status enum.
- In `GET /tasks` handler (line ~50): add `status` query param parsing — split by comma, validate each value, filter tasks matching any listed status.
- In `taskWithCount()` helper (line ~25): include `description`, `status`, and `updatedAt` in output (they're already on the object, just ensure they flow through).

**Patterns to follow:**
- Inline validation style: `if (status !== undefined && !VALID_STATUSES.includes(status)) return res.status(400).json({ error: '...' })`
- Same `Map`-based in-memory storage
- Return enriched task via `taskWithCount()`

## Contract References

- `POST /tasks` — request body gains optional `status` and `description`; response includes `status`, `description`, `updatedAt`
- `PATCH /tasks/{taskId}` — request body gains optional `status` and `description`; response includes `status`, `description`, `updatedAt`
- `GET /tasks` — gains `?status=` query parameter
- `GET /tasks/{taskId}` — response includes `status`, `description`, `updatedAt`
- `TaskStatus` enum: `[todo, in-progress, done]`

## Acceptance Criteria

- [ ] `POST /tasks` with `{ "title": "My task" }` creates a task with `status: "todo"` and `updatedAt` set
- [ ] `POST /tasks` with `{ "title": "X", "status": "in-progress" }` creates with that status
- [ ] `POST /tasks` with `{ "title": "X", "status": "invalid" }` returns 400
- [ ] `POST /tasks` with `{ "title": "X", "description": "Some details" }` stores description
- [ ] `GET /tasks` returns tasks with `status`, `description`, and `updatedAt` fields
- [ ] `GET /tasks?status=todo` returns only todo tasks
- [ ] `GET /tasks?status=todo,done` returns tasks matching either status
- [ ] `GET /tasks?status=invalid` returns 400
- [ ] `PATCH /tasks/:id` with `{ "status": "done" }` updates status, updates `updatedAt`
- [ ] `PATCH /tasks/:id` setting same status returns 200 (no-op is OK, `updatedAt` still updates)
- [ ] `PATCH /tasks/:id` with `{ "description": "Updated" }` updates description
- [ ] `DELETE /tasks/:id` still cascades comments (existing behavior preserved)
