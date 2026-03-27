---
feature: cannot-read-properties-of-undefined-reading-id
completed: 2026-03-27
tasks: 1
waves: 1
total-cost-usd: 0.6575
total-tokens: 8407
---

## Overview

(No spec content available)

## What Was Built

### Wave 1

- **api** — Fix TypeError in taskWithCount that crashes GET /tasks for all users. The function at src/app.js:34 accesses `.id` on a value that is `undefined`, causing a 500 response on every request to GET /tasks.

## Key Decisions

- **wave-1-api-fix-taskwithcount-undefined-crash:** Modify `src/app.js`. The crash is at line 34 inside `taskWithCount(task)` where `task.id` is accessed but `task` is `undefined`. Called from line 109: `res.json(result.map(taskWithCount))`.

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

## Contracts Affected

(No contracts referenced)

## Cost Summary

**Total: $0.6575** (8,407 tokens, 193s)

| Wave | Task | Cost | Tokens |
|------|------|------|--------|
| W1 | wave-1-api-fix-taskwithcount-undefined-crash | $0.6575 | 8,407 |

## Retrospective Notes

(No retrospective entries)
