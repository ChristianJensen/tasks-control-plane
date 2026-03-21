---
status: ready
execution: supervised
target-repo: api
wave: 1
priority: high
feature: multiassign
type: feature
depends-on:
  - wave-1-api-add-category-field-and-patch-support.md
---

## Description

Add POST /tasks/batch-update-category endpoint that accepts an array of task IDs and a category value (including null to clear), updates matching tasks, and returns { updated, notFound } with partial success semantics. Requires X-User-Id header.

## Why

Core bulk operation endpoint. R3 (batch endpoint), R4 (limits and partial success), AC4-AC6. Mirrors batch-delete pattern for consistency.

## Implementation Notes

Modify `src/app.js`. (1) Add route BEFORE `/tasks/:id` routes (same placement strategy as batch-delete). (2) Validate X-User-Id header — return 400 if missing (A3 refinement). (3) Validate request body: `ids` must be non-empty array of integers, max 50 items — return 400 otherwise. Also reject non-integer values. (4) Validate `category`: must be a valid category string or null — return 400 for invalid values (reject entire request per E2). (5) Deduplicate IDs with `[...new Set(ids)]`. (6) Iterate each unique ID: if task exists, update category and updatedAt, add to `updated` array; if not found, add to `notFound` array. (7) Return 200 with `{ updated, notFound }`. Consider extracting shared batch validation logic from batch-delete into a helper to prevent divergence (AR2). Add tests in `tests/tasks.test.js`: happy path, partial success, all not found (E1), invalid category rejects entire request (E2), missing X-User-Id returns 400, empty array returns 400, >50 IDs returns 400, duplicate IDs are deduped, null category clears, task deleted mid-batch appears in notFound (E3).

## Contract References

POST /tasks/batch-update-category — full endpoint definition including parameters (X-User-Id), requestBody schema, 200 response (BatchUpdateCategoryResult), 400 response.

## Acceptance Criteria

- [ ] Tests pass (`npm test`)
- [ ] Contract-compliant: POST /tasks/batch-update-category returns { updated, notFound }
- [ ] Accepts { ids: [int], category: string|null } and updates matching tasks (AC4)
- [ ] Returns { updated: [int], notFound: [int] } with partial success (AC5)
- [ ] Validates 1-50 IDs, returns 400 for violations (AC6)
- [ ] Returns 400 if X-User-Id header is missing (A3)
- [ ] Invalid category value rejects entire request with 400 (E2)
- [ ] All IDs not found returns 200 with empty updated array (E1)
- [ ] Duplicate IDs are deduplicated before processing
- [ ] Idempotent: re-assigning same category counts as updated (A1)
