<!-- LIFECYCLE NOTE: Bug reports live in bugs/<phase>/ (draft, active, completed,
     cancelled). The parent directory is authoritative for lifecycle phase.
     The lifecycle field below is kept in sync for human readability.
     When directory and frontmatter diverge, the directory wins. -->
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

`GET /tasks` throws an unhandled `TypeError: Cannot read properties of undefined (reading 'id')` inside the `taskWithCount` helper at `src/app.js:34:30`. The error propagates up to the route handler at line 109 and returns a 500 to all callers. Task listing and creation are fully unavailable. 47 errors were recorded in the 15 minutes preceding the alert.

Full stack trace:
```
TypeError: Cannot read properties of undefined (reading 'id')
    at taskWithCount (src/app.js:34:30)
    at GET /tasks (src/app.js:109:25)
```

## Expected Behavior

`GET /tasks` returns a 200 with an array of task objects. `taskWithCount` should safely enrich each task row without throwing.

## Reproduction Steps

1. Ensure the `tasks` table contains at least one row (or trigger the condition that produces an `undefined` element — see Root Cause Analysis below).
2. Send `GET /tasks` to the API.
3. Observe a 500 response with the TypeError above.

## Environment

- **Repo/Branch:** api/main
- **Endpoint/Component:** `GET /tasks` → `taskWithCount` helper (`src/app.js`)
- **Trigger Frequency:** Always (100% failure rate — all 47 observed requests failed)

## Evidence

```
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

The error occurs at **`src/app.js:34`, column 30** inside the `taskWithCount` helper, which is called from the `GET /tasks` route handler at **line 109**. The expression at col 30 reads `.id` off a value that is `undefined`.

`taskWithCount` is a mapping function — called once per task in a list — that enriches a raw DB row with derived data (most likely a comment count or related aggregate). The route handler maps the DB result set through this function at line 109.

The crash indicates that at least one element in that array is `undefined`. The most likely causes, in order of probability:

1. **[MOST LIKELY] A database query or JOIN introduced by a recent feature now returns a sparse/null row under certain conditions.** The `multiassign` feature added a `category` column and a `batch-update-category` endpoint; if a LEFT JOIN was added to the main `SELECT` query for tasks (e.g., to fetch category-related data), it could produce a row where the task object itself is `undefined` or `null` when no matching join row exists. The ORM or raw query result is then spread into an array containing `undefined` elements.

2. **A helper like `rows.find()` is being called and the return value (which can be `undefined` when nothing matches) is passed directly into `taskWithCount`** instead of being guarded.

3. **The `taskWithCount` function itself receives a task object but destructures a nested property that can be `undefined`** — e.g., it accesses `task.someRelation.id` and `task.someRelation` is not always populated.

Because the error is 100% reproducible (not intermittent), hypothesis 1 is most likely: every call to `GET /tasks` hits the same broken query path.

**[REQUIRES HUMAN REVIEW]** — the exact DB query and `taskWithCount` implementation in `src/app.js` must be read to confirm which of the above applies.

### Affected Code Paths

| Repo | File | Function/Line | Issue |
|------|------|---------------|-------|
| api | `src/app.js` | `taskWithCount` / line 34 | Accesses `.id` on a value that is `undefined` |
| api | `src/app.js` | `GET /tasks` handler / line 109 | Calls `taskWithCount` without guarding against `undefined` elements in the mapped array |

### Fix Strategy

**Immediate mitigation (unblock users fast):**
Add a null/undefined guard inside `taskWithCount` (or at the call site in the `GET /tasks` handler) so that `undefined` elements are filtered or handled gracefully before `.id` is accessed. This stops the 500s even before the root cause is addressed.

```js
// Example guard at the call site (line ~109):
const results = tasks.filter(Boolean).map(taskWithCount);
```

**Root cause fix:**
1. Read `src/app.js` lines 25–45 (`taskWithCount` definition) and lines 95–120 (`GET /tasks` handler) to identify exactly what produces `undefined`.
2. If a JOIN query is the source: ensure the query uses `WHERE` or `HAVING` clauses that prevent null/undefined task rows, or handle null rows returned from a LEFT JOIN.
3. If `find()` / similar is the source: add an explicit check before passing the result to `taskWithCount`.
4. Add a regression test: seed the DB state that triggers the `undefined` element (e.g., a task with no joined row) and assert `GET /tasks` returns 200.

## Scope Assessment

- [x] Single-task fix (one repo, <50 lines)

The fix is localized to `src/app.js` in the `api` repo. A null guard at the call site is 1–3 lines; fixing the query is likely <20 lines. A single task is sufficient.

## Acceptance Criteria

- [ ] `GET /tasks` returns 200 for all users — no more TypeError crashes
- [ ] `taskWithCount` does not throw when called with `undefined` or when the task list contains `undefined` elements
- [ ] Regression test added: a request to `GET /tasks` under the condition that triggered the bug returns a valid task array (not a 500)
- [ ] No existing tests broken
- [ ] Root cause (the code path producing `undefined`) is fixed, not just suppressed with a filter
