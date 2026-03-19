---
status: ready
target-repo: api
wave: 1
priority: high
feature: logging
type: feature
---

## Description

Add in-memory statusHistory store with auto-incrementing IDs. Require X-User-Id header on PATCH /tasks/{taskId} (return 400 if missing). On PATCH status change, record a StatusTransition entry (skip if no-op same-status). Add GET /tasks/{taskId}/history endpoint returning entries sorted by changedAt ascending. Update DELETE /tasks/{taskId} to cascade-delete history entries. Expose store via _resetStore() for tests.

## Why

This is the core backend foundation — without the history store, recording logic, and retrieval endpoint, no other task can function. The X-User-Id breaking change on PATCH must ship simultaneously so the frontend can adapt in the same wave.

## Implementation Notes

Modify src/app.js: (1) Add `const statusHistory = new Map()` and `let historyIdCounter = 1` next to existing stores. (2) In the PATCH /tasks/:id handler, add validation for X-User-Id header at the top (before existing validation) — return 400 if missing. After the existing status update logic, check if `status` was provided AND differs from the current status; if so, push a new entry to statusHistory. (3) Add GET /tasks/:id/history route — check task exists (404), then filter and sort entries. (4) In DELETE /tasks/:id, add a loop to delete statusHistory entries for that taskId (same pattern as comments cascade). (5) Update _resetStore() to clear statusHistory and reset counter. Follow the existing patterns in app.js for Map-based storage (see comments store). No new files needed.

## Contract References

PATCH /tasks/{taskId} — new X-User-Id parameter, 400 response for missing header. GET /tasks/{taskId}/history — new endpoint, 200 returns StatusTransition[], 404 for missing task. DELETE /tasks/{taskId} — updated description mentioning history cascade. components/schemas/StatusTransition — id, taskId, oldStatus, newStatus, changedBy, changedAt.

## Acceptance Criteria

- [ ] Tests pass (`npm test`)
- [ ] Contract-compliant with tasks-api.json v0.5.0
- [ ] PATCH /tasks/{taskId} returns 400 when X-User-Id header is missing (E7)
- [ ] PATCH /tasks/{taskId} with status change creates a StatusTransition entry with correct oldStatus, newStatus, changedBy (from X-User-Id), and changedAt
- [ ] No-op status update (same status) does NOT create a history entry (E1, R6)
- [ ] Mixed PATCH (title + status change) creates a history entry for the status change only (E6, R9)
- [ ] PATCH that changes only title/description (no status field) does NOT create a history entry
- [ ] Task creation does NOT generate a history entry (R8)
- [ ] GET /tasks/{taskId}/history returns entries sorted by changedAt ascending (oldest first)
- [ ] GET /tasks/{taskId}/history returns 404 for non-existent task (E3)
- [ ] GET /tasks/{taskId}/history returns empty array [] for task with no transitions (E4)
- [ ] DELETE /tasks/{taskId} cascade-deletes all associated history entries (E2)
- [ ] Concurrent status changes each create their own history entry (E5)
- [ ] No update or delete endpoints exist for history entries (R4)
