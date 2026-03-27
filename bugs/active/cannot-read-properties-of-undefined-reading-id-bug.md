---
lifecycle: active
type: bug
version: 1
severity: critical
affected-repos:
  - api
reported-by: telemetry
paused-at: ""
paused-by: ""
pause-reason: ""
---

# Bug Report: TypeError in taskWithCount Crashes GET /tasks for All Users

## Observed Behavior

Every request to `GET /tasks` returns a 500 Internal Server Error:

```
TypeError: Cannot read properties of undefined (reading 'id')
    at taskWithCount (src/app.js:34:30)
    at GET /tasks (src/app.js:109:25)
```

Task listing is completely unavailable. 47 errors observed in the last 15 minutes affecting all users.

## Expected Behavior

`GET /tasks` should return a 200 response with a JSON array of task objects. The `taskWithCount` helper should only ever receive valid task objects.

## Reproduction Steps

1. Start the API server (`npm start`)
2. Send `GET /tasks` (any query string, including none)
3. Observe 500 response with the `TypeError` above

## Environment

- **Repo/Branch:** api/main
- **Endpoint/Component:** `GET /tasks` → `taskWithCount` helper
- **Trigger Frequency:** Always — every request to `GET /tasks` fails

## Evidence

Telemetry payload from monitoring system:

```json
{
  "error_message": "TypeError: Cannot read properties of undefined (reading id)",
  "file": "src/app.js",
  "service": "api",
  "severity": "critical",
  "stack_trace": "TypeError: Cannot read properties of undefined (reading id)\n    at taskWithCount (src/app.js:34:30)\n    at GET /tasks (src/app.js:109:25)",
  "user_impact": "Task creation and listing failing for all users — 47 errors in last 15 minutes"
}
```

No attachments provided.

## Diagnostic Reasoning

### Root Cause Analysis

The `taskWithCount` helper (defined at `src/app.js:33–42`) receives `undefined` as its `task` argument and crashes at line 34 when it attempts to access `task.id`. The call site is `src/app.js:109`:

```js
res.json(result.map(taskWithCount));
```

`result` is an array derived at line 71 from `[...tasks.values()]` — the full in-memory tasks Map — which is subsequently filtered (by `category` and/or `search` query params) and sorted. One or more of these intermediate operations produces `undefined` entries that survive into the final `result` array.

**Most likely root cause:** A filter or sort step introduced by the multiassign feature's category-filter logic uses `.map()` where `.filter()` is required, or uses a predicate that implicitly returns `undefined` for non-matching elements (JavaScript `Array.map` does not remove elements — it replaces them with `undefined` if the mapping function has no explicit return). A sort comparator bug is a secondary candidate.

**Secondary issue identified:** The contract-defined `status` query parameter (comma-separated, e.g. `?status=todo,in-progress`) is not destructured from `req.query` at line 59. This means the status filter is silently ignored; while not the crash cause, it represents a broken contract implementation.

### Affected Code Paths

| Repo | File | Function/Line | Issue |
|------|------|---------------|-------|
| api | `src/app.js` | `taskWithCount` / line 34 | Accesses `task.id` but `task` is `undefined` |
| api | `src/app.js` | `GET /tasks` handler / line 109 | `result.map(taskWithCount)` — `result` contains `undefined` entries |
| api | `src/app.js` | `GET /tasks` handler / line 71 | `[...tasks.values()]` is the source array; corruption occurs in subsequent filter/sort chain |
| api | `src/app.js` | `GET /tasks` handler / line 59 | `status` query param not destructured — contract filter silently broken (secondary) |

### Fix Strategy

Three layers of fix are required — do **not** use `.filter(Boolean)` alone as a substitution for the root cause fix:

1. **Root cause fix (required):** Identify the filter/sort step that introduces `undefined` into the `result` array. Replace any `.map()`-based filtering with `.filter()`, and fix any sort comparator that can corrupt array entries. Read `taskWithCount` (lines 33–42) and the full `GET /tasks` handler (lines 57–110) to trace the exact transformation chain.

2. **Defensive guard (also required):** Add `.filter(Boolean)` before `.map(taskWithCount)` at line 109 as defense-in-depth, so `taskWithCount` never receives `undefined` even if a future regression reintroduces the issue:
   ```js
   res.json(result.filter(Boolean).map(taskWithCount));
   ```

3. **Harden `taskWithCount`:** Add an early guard at the top of the function:
   ```js
   const taskWithCount = (task) => {
     if (!task) return null;
     // ... existing logic
   };
   ```

4. **Fix the status filter:** Destructure `status` from `req.query` at line 59 and implement the comma-separated filter per contract spec.

**Test file:** `tests/tasks.test.js` — append to existing file using existing patterns (`supertest`, `app._resetStore()` in `beforeEach`).

## Scope Assessment

- [x] Single-task fix (one repo, <50 lines)
- [ ] Multi-task fix (needs decomposition into waves)

The crash is contained to `src/app.js` in the api repo. All fix layers (root cause, guard, hardening, status filter) fit within a single task.

## Acceptance Criteria

- [ ] `GET /tasks` returns 200 with a valid task array (no 500 errors)
- [ ] `GET /tasks` returns 200 when the tasks store is empty
- [ ] `GET /tasks?category=work` returns only work-category tasks (no undefined entries in the filtered array)
- [ ] `GET /tasks?status=todo,in-progress` correctly filters by multiple statuses per contract spec
- [ ] `taskWithCount` never throws when passed a valid task object
- [ ] Regression test added: verify `GET /tasks` returns 200 and an array (not a 500) covering the crash scenario
- [ ] No existing tests broken
