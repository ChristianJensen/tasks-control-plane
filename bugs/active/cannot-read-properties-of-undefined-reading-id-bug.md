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

`GET /tasks` throws an unhandled `TypeError: Cannot read properties of undefined (reading 'id')` inside the `taskWithCount` helper at `src/app.js:34:30`. The error propagates to the route handler at line 109 and returns a 500 to all callers. Task listing is fully unavailable. 47 errors were recorded in the 15 minutes preceding the alert.

Full stack trace:
```
TypeError: Cannot read properties of undefined (reading 'id')
    at taskWithCount (src/app.js:34:30)
    at GET /tasks (src/app.js:109:25)
```

## Expected Behavior

`GET /tasks` returns a 200 with a JSON array of task objects. `taskWithCount` should safely enrich each task row without throwing.

## Reproduction Steps

1. Ensure the API is running with its current `main` branch code.
2. Send `GET /tasks` (any authenticated request).
3. Observe a 500 response with the TypeError above.

## Environment

- **Repo/Branch:** api/main
- **Endpoint/Component:** `GET /tasks` → `taskWithCount` helper (`src/app.js`)
- **Trigger Frequency:** Always (100% failure rate — all 47 observed requests failed)

## Evidence

Telemetry payload:
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

No additional attachments provided.

## Diagnostic Reasoning

### Root Cause Analysis

The error occurs at **`src/app.js:34`, column 30** inside `taskWithCount`, which is a mapping helper called once per task element. It accesses `.id` on a value that is `undefined` at that column position. The route handler at **line 109** maps a result array through `taskWithCount` — at least one element in that array is `undefined`.

Because the failure rate is 100% (not intermittent), the `undefined` element is produced deterministically on every `GET /tasks` call under the current server state.

Most likely causes, in order of probability:

1. **[MOST LIKELY] A query or in-memory lookup introduced by a recent change returns `undefined` for certain elements.** The `multiassign` feature (completed 2026-03-21) added a `category` field and a `batch-update-category` endpoint. If that change introduced a JOIN or a secondary lookup on the tasks collection, it could produce a row where the task object is `undefined`/`null` when no matching data exists. The array passed to `.map(taskWithCount)` then contains `undefined` elements.

2. **A `find()` / `get()` call whose result (which can be `undefined`) is being passed directly into `taskWithCount`** — e.g., `tasks.get(someId)` returns `undefined` for a missing key and that value lands in the mapped array.

3. **`taskWithCount` accesses a nested property** — e.g., `task.someRelation.id` — and `task.someRelation` is `undefined` for tasks that lack the relation.

**[REQUIRES HUMAN REVIEW]** — the exact implementation of `taskWithCount` (lines ~25–45) and the `GET /tasks` handler (lines ~95–120) in `src/app.js` must be read to confirm which hypothesis applies and where the fix should land.

### Affected Code Paths

| Repo | File | Function/Line | Issue |
|------|------|---------------|-------|
| api | `src/app.js` | `taskWithCount` / line 34 | Accesses `.id` on a value that is `undefined` |
| api | `src/app.js` | `GET /tasks` handler / line 109 | Calls `taskWithCount` via `.map()` without guarding against `undefined` elements |

### Fix Strategy

**Immediate mitigation (unblock users):**
Add a null/undefined guard at the call site so `undefined` elements are filtered before `taskWithCount` is invoked:

```js
// Line ~109 — guard before mapping:
const results = rawTasks.filter(Boolean).map(taskWithCount);
```

This stops the 500s immediately. It is a mitigation, not a root-cause fix.

**Root cause fix:**
1. Read `src/app.js` lines 25–45 (`taskWithCount` definition) and lines 95–120 (`GET /tasks` handler) to identify exactly what produces `undefined`.
2. If a JOIN/lookup is the source: ensure the query or lookup never returns `undefined` rows, or handle null join results explicitly.
3. If a `find()`/`get()` call is the source: add an explicit guard before passing the result to `taskWithCount`.
4. Add a regression test: exercise the condition that produces the `undefined` element and assert `GET /tasks` returns 200 with a valid array.

## Scope Assessment

- [x] Single-task fix (one repo, <50 lines)

The fix is localized to `src/app.js` in the `api` repo. A null guard at the call site is 1–3 lines; fixing the upstream query/lookup is likely <20 lines. A single task is sufficient.

## Acceptance Criteria

- [ ] `GET /tasks` returns 200 for all users — no more TypeError crashes
- [ ] `taskWithCount` does not throw when the task list contains `undefined` elements
- [ ] Root cause (the code path that produces `undefined`) is fixed, not merely suppressed by a `.filter(Boolean)` guard
- [ ] Regression test added: a request to `GET /tasks` under the condition that triggered the bug returns a valid task array (not a 500)
- [ ] No existing tests broken
