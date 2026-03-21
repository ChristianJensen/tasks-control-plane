---
status: ready
target-repo: api
wave: 1
priority: high
feature: multidelete
type: feature
---

## Description

Add POST /tasks/batch-delete endpoint with input validation, deduplication, cascade deletion of comments/subtasks/auditEntries/statusHistory, and position compaction. Returns { deleted, notFound } response.

## Why

This is the foundational API endpoint that the frontend batch delete UI will call. Without it, multi-delete is impossible. Must exist before frontend work begins.

## Implementation Notes

Modify `src/app.js`. Add the new route BEFORE the `/tasks/:id` routes (Express matches routes in order and `/tasks/batch-delete` must not be caught by `/tasks/:id`). Implementation steps: (1) Validate request body: `ids` must be a non-empty array of integers with max 50 items — return 400 otherwise. Also reject non-integer values (strings, null, etc.) with 400. (2) Deduplicate IDs using `[...new Set(ids)]`. (3) Iterate each unique ID: if task exists in the `tasks` Map, delete it and cascade-delete from `comments`, `subtasks`, `auditEntries`, and `statusHistory` Maps (same pattern as existing `DELETE /tasks/:id` at line 348-374). Also compact positions for each deleted task. Add ID to `deleted` array. If task not found, add to `notFound` array. (4) Return 200 with `{ deleted, notFound }`. Consider extracting the cascade-delete logic from the existing single-delete route into a helper function to avoid duplication — both routes should use the same logic. Tests go in `tests/tasks.test.js` (append to existing file).

## Contract References

POST /tasks/batch-delete — request schema requires `ids` array (integer[], minItems: 1, maxItems: 50). Response 200: BatchDeleteResult schema `{ deleted: integer[], notFound: integer[] }`. Response 400: Error schema for validation failures.

## Acceptance Criteria

- [ ] Tests pass (`npm test`)
- [ ] Contract-compliant with POST /tasks/batch-delete
- [ ] `POST /tasks/batch-delete` with `{ ids: [1, 2, 3] }` returns `{ deleted: [1, 2], notFound: [3] }` with status 200 (AC1)
- [ ] Request with more than 50 IDs returns 400 error (AC2)
- [ ] Request with empty array returns 400 error (AC3)
- [ ] Request with all not-found IDs returns 200 with empty `deleted` array (AC4)
- [ ] Deleted tasks have their comments, subtasks, audit entries, and status history cascade-deleted (AC5)
- [ ] Duplicate IDs in request are deduplicated — each task deleted at most once (AC11)
- [ ] Non-integer values in IDs array (e.g., strings, null) return 400 (E6)
- [ ] Positions are compacted after batch deletion (consistent with single delete behavior)
- [ ] Request with missing `ids` field returns 400
- [ ] Request with `ids: [1,1,1]` for existing task 1 returns `{ deleted: [1], notFound: [] }`
