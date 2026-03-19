---
status: ready
target-repo: api
wave: 1
priority: high
feature: task-audit-log
type: feature
claimed-by: ""
claimed-at: ""
claimed-on: ""
contracts:
  - contracts/tasks-api.json
---

## Description

Add an in-memory audit log that records task status changes. This includes:

1. A new `auditEntries` Map store with auto-incrementing IDs
2. An audit entry created on task creation (oldStatus: null, newStatus: "todo")
3. An audit entry created on task status change via PATCH (old → new status, skipping no-ops)
4. A `GET /tasks/:id/audit` endpoint returning entries newest-first
5. Cascade deletion of audit entries when a task is deleted
6. Reset of audit store in `_resetStore()`

## Why

Users have no visibility into what happened to a task over time. The audit log provides a history trail of status transitions with user attribution.

## Implementation Notes

**Important: Status mapping.** The current codebase uses `completed: boolean` internally, not the contract's `status: TaskStatus` enum. Map as follows:
- `completed: false` → `"todo"`
- `completed: true` → `"done"`

The contract defines `"in-progress"` but the current implementation has no in-progress state. The audit log should work with the actual values present (`"todo"` / `"done"`).

**Store setup** (follow existing pattern in `src/app.js`):
```js
const auditEntries = new Map();
let nextAuditEntryId = 1;
```

**User attribution:** Read `X-User-Id` from `req.headers['x-user-id']`. The header is already used for comments. For `POST /tasks` and `PATCH /tasks/:id`, extract this header for the audit entry's `userId` field. If the header is missing, use `"anonymous"`.

**Creation audit (POST /tasks):** After creating the task and before sending the response, create an audit entry:
```js
{ id, taskId: task.id, oldStatus: null, newStatus: "todo", userId, createdAt }
```

**Status change audit (PATCH /tasks/:id):** When `completed` changes, create an audit entry with the mapped old and new status values. Skip if old === new (no-op).

**GET /tasks/:id/audit:** Filter `auditEntries` by `taskId`, sort by `createdAt` descending. Return 404 if task doesn't exist.

**Cascade delete (DELETE /tasks/:id):** Add loop to delete audit entries (same pattern as comments/subtasks cascade).

**Key files to modify:**
- `src/app.js` (~319 lines) — add store, modify POST/PATCH/DELETE routes, add GET /audit route
- `tests/tasks.test.js` (~493 lines) — or create `tests/audit.test.js` for audit-specific tests

## Contract References

- **New endpoint:** `GET /tasks/{taskId}/audit` → returns `AuditEntry[]` (newest first)
- **Schema:** `AuditEntry { id, taskId, oldStatus (nullable), newStatus, userId, createdAt }`
- **Modified:** `POST /tasks` now accepts `X-User-Id` header for audit attribution
- **Modified:** `PATCH /tasks/{taskId}` now accepts `X-User-Id` header; status changes create audit entries
- **Modified:** `DELETE /tasks/{taskId}` now cascade-deletes audit entries

## Acceptance Criteria

- [ ] Tests pass (`npm test`)
- [ ] Contract-compliant
- [ ] POST /tasks creates a task AND an audit entry with `oldStatus: null`, `newStatus: "todo"`, and the caller's X-User-Id as `userId`
- [ ] PATCH /tasks/:id changing `completed` creates an audit entry with mapped old/new status values
- [ ] PATCH /tasks/:id with same `completed` value does NOT create an audit entry
- [ ] PATCH /tasks/:id changing only title (no completed change) does NOT create an audit entry
- [ ] GET /tasks/:id/audit returns all audit entries for that task, ordered by createdAt descending
- [ ] GET /tasks/:id/audit returns 404 if task does not exist
- [ ] GET /tasks/:id/audit returns an empty array for a task with only a creation entry that was somehow removed (defensive)
- [ ] DELETE /tasks/:id cascade-deletes all associated audit entries
- [ ] Each audit entry contains: `id`, `taskId`, `oldStatus` (nullable), `newStatus`, `userId`, `createdAt`
- [ ] `_resetStore()` clears `auditEntries` and resets `nextAuditEntryId`
