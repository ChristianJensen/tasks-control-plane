---
status: in-progress
execution: supervised
target-repo: api
wave: 1
priority: critical
feature: cannot-read-properties-of-undefined-reading-id
type: bug
claimed-by: agent-Christians-MacBook-Air-54381
claimed-at: 2026-03-27T17:31:39Z
claimed-on: Christians-MacBook-Air
---

## Description

Fix TypeError in taskWithCount that crashes GET /tasks for all users. The function at src/app.js:34 accesses `.id` on a value that is `undefined`, causing a 500 response on every request to GET /tasks.

## Why

GET /tasks is completely unavailable — 47 errors in 15 minutes affecting all users. This is a critical outage requiring immediate fix.

## Implementation Notes

Modify `src/app.js`. The crash is at line 34 inside `taskWithCount(task)` where `task.id` is accessed but `task` is `undefined`. Called from line 109: `res.json(result.map(taskWithCount))`.

**Investigation steps (must be done by the implementing agent):**
1. Read `taskWithCount` (lines 33-42) and the `GET /tasks` handler (lines 57-110)
2. Determine WHY `undefined` elements appear in the `result` array. The array comes from `[...tasks.values()]` at line 71, then filtered by `category` and `search`, then sorted. Investigate whether:
   - A filter step uses `.map()` where `.filter()` is required (map returns `undefined` for non-matching elements)
   - A sort comparator has a subtle bug that corrupts the array
   - A recent feature (e.g., multiassign's category-filter logic) introduced the issue
3. Also check if the `status` query parameter from the contract (comma-separated status filter) is not destructured from `req.query` at line 59 — the contract defines it but current code may silently ignore it or produce undefined rows

**Fix strategy (all four layers required):**
1. **Root cause fix (required):** Identify the filter/sort step that introduces `undefined` into `result`. Replace any `.map()`-based filtering with `.filter()`, fix any sort comparator that corrupts array entries. Do NOT use `.filter(Boolean)` alone as a substitute.
2. **Defensive guard (also required):** Add `.filter(Boolean)` before `.map(taskWithCount)` at line 109 as defense-in-depth:
   ```js
   res.json(result.filter(Boolean).map(taskWithCount));
   ```
3. **Harden `taskWithCount`:** Add early guard at the top of the function:
   ```js
   const taskWithCount = (task) => {
     if (!task) return null;
     // ... existing logic
   };
   ```
4. **Fix the status filter:** Destructure `status` from `req.query` at line 59 and implement the comma-separated filter per contract spec (`?status=todo,in-progress` should filter by multiple statuses).

**Test file:** `tests/tasks.test.js` — append to existing file using existing patterns (`supertest`, `app._resetStore()` in `beforeEach`).

## Contract References

GET /tasks (listTasks) — the `status` query parameter accepts comma-separated values (e.g. `todo,in-progress`). Response must be a 200 with an array of Task objects. The contract also defines a 400 response for invalid status filter values.

## Acceptance Criteria

- [ ] GET /tasks returns 200 with a valid task array (no 500 errors)
- [ ] GET /tasks returns 200 when the tasks store is empty
- [ ] GET /tasks?category=work returns only work-category tasks (no undefined entries in the filtered array)
- [ ] GET /tasks?status=todo,in-progress correctly filters by multiple statuses per contract spec
- [ ] taskWithCount never throws when passed a valid task object
- [ ] Regression test added: verify GET /tasks returns 200 and an array (not a 500) covering the crash scenario
- [ ] No existing tests broken
- [ ] Tests pass (npm test)
