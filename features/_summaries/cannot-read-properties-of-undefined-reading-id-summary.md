---
feature: cannot-read-properties-of-undefined-reading-id
completed: 2026-03-27
tasks: 1
waves: 1
total-cost-usd: 1.2012
total-tokens: 24490
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

## Contracts Affected

- contracts/tasks-api.json

## Cost Summary

**Total: $1.2012** (24,490 tokens, 489s)

| Wave | Task | Cost | Tokens |
|------|------|------|--------|
| W1 | wave-1-api-fix-taskwithcount-undefined-crash | $1.2012 | 24,490 |

## Retrospective Notes

(No retrospective entries)
