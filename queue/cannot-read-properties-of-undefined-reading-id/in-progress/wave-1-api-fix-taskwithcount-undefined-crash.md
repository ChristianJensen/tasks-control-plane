---
status: in-progress
execution: supervised
target-repo: api
wave: 1
priority: critical
feature: cannot-read-properties-of-undefined-reading-id
type: feature
contracts:
  - contracts/tasks-api.json
claimed-by: agent-Christians-MacBook-Air-54381
claimed-at: 2026-03-27T15:54:32Z
claimed-on: Christians-MacBook-Air
cost-usd: 1.2012110999999996
input-tokens: 37
output-tokens: 24453
duration-ms: 489081
pr-url: https://github.com/ChristianJensen/agentic-sdlc-api/pull/27
pr-number: 27
---

## Description

Fix TypeError in taskWithCount that crashes GET /tasks for all users. The function at src/app.js:34 accesses `.id` on a value that is `undefined`, causing a 500 response on every request to GET /tasks.

## Why

This is a critical production bug — GET /tasks returns 500 for all users, making task listing and creation fully unavailable. 47 errors were recorded in 15 minutes.

## Implementation Notes

Modify `src/app.js`. The crash is at line 34 inside `taskWithCount(task)` where `task.id` is accessed but `task` is `undefined`. Called from line 109: `res.json(result.map(taskWithCount))`.

**Investigation steps (must be done by the implementing agent):**
1. Read `taskWithCount` (lines 33-42) and the `GET /tasks` handler (lines 57-110)
2. Determine WHY `undefined` elements appear in the `result` array. The array comes from `[...tasks.values()]` at line 71, then filtered by `category` and `search`, then sorted. Investigate whether:
   - A task in the `tasks` Map is stored as `undefined` (check all `.set()` calls)
   - A filter or map operation introduces `undefined` values
   - The sort comparator has a subtle bug that corrupts the array
   - A recent feature (e.g., multiassign's category filter) introduced the issue
3. Also check if the `status` query parameter from the contract (comma-separated status filter) has a broken implementation that produces undefined rows — the contract defines it but the current code at line 59 does NOT destructure `status` from `req.query`

**Fix strategy:**
1. **Root cause fix (required):** Fix the code path that produces `undefined` elements — do NOT just suppress with `.filter(Boolean)`
2. **Defensive guard (also required):** Add `.filter(Boolean)` before `.map(taskWithCount)` at line 109 as defense-in-depth, so `taskWithCount` never receives `undefined` even if a future bug reintroduces the issue
3. **Harden `taskWithCount`:** Add an early return or guard at the top of `taskWithCount` for `undefined`/`null` input

**Test file:** `tests/tasks.test.js` (append to existing file). Use existing patterns: `supertest`, `app._resetStore()` in `beforeEach`.

## Contract References

GET /tasks (operationId: listTasks) — must return 200 with array of Task objects. See paths./tasks.get in contracts/tasks-api.json.

## Acceptance Criteria

- [ ] GET /tasks returns 200 for all users — no more TypeError crashes
- [ ] taskWithCount does not throw when called with undefined or when the task list contains undefined elements
- [ ] Regression test added: a request to GET /tasks under the condition that triggered the bug returns a valid task array (not a 500)
- [ ] Root cause (the code path producing undefined) is fixed, not just suppressed with a filter
- [ ] Defensive guard added at the call site (filter(Boolean) or equivalent) as defense-in-depth
- [ ] No existing tests broken
- [ ] Tests pass (npm test)
