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

# Bug Report: TypeError in taskWithCount — undefined task passed from GET /tasks

## Observed Behavior

`GET /tasks` throws an unhandled `TypeError` and returns a 500, breaking task
listing for all users. The error is raised inside `taskWithCount` when it tries
to read `.id` off an `undefined` value:

```
TypeError: Cannot read properties of undefined (reading 'id')
    at taskWithCount (src/app.js:34:30)
    at GET /tasks (src/app.js:109:25)
```

47 errors recorded in the last 15 minutes at time of alert. Task creation is
also reported as failing — most likely a UI cascade: when the list endpoint
returns 500, the frontend enters an error state that prevents users from
interacting with the app at all.

## Expected Behavior

`GET /tasks` should return 200 with a JSON array of task objects. `taskWithCount`
should only ever receive a valid task object; `undefined` should never reach it.

## Reproduction Steps

1. Start the API server (`npm start`)
2. Create at least one task via `POST /tasks`
3. Call `GET /tasks` (optionally with `?sort=category`)
4. Observe 500 response with `TypeError: Cannot read properties of undefined (reading 'id')`

_Note: the bug may only manifest with specific data states (e.g., a task deleted
concurrently, or a query that exercises the newly added category sort path). If
the simple reproduction above does not trigger it consistently, try
`GET /tasks?sort=category` first._

## Environment

- **Repo/Branch:** api/main
- **Endpoint/Component:** `GET /tasks` → `taskWithCount` helper (`src/app.js`)
- **Trigger Frequency:** always (47 errors / 15 min at alert time — not intermittent)

## Evidence

Telemetry payload from automated monitoring system:

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

No additional attachments.

## Diagnostic Reasoning

### Root Cause Analysis

`taskWithCount(task)` is a helper that enriches a task with computed fields
(`commentCount`, `subtaskCount`, `completedSubtaskCount`). At line 34, column
30, it accesses `task.id` (or a destructuring of `task` that reads `.id`). If
`task` is `undefined`, this line throws.

The most recently merged API change is **task-category-enhancements wave 1**
(`queue/_done/task-category-enhancements/done/wave-1-api-add-category-sort-logic.md`),
which added `sort=category` support to `GET /tasks`. The implementation:

1. Added a `CATEGORY_ORDER` constant near `STATUS_ORDER`
2. Added a `case 'category':` branch inside the existing sort handler
3. Extended sort-param validation to accept `'category'`

The category sort branch is the most probable introduction point of this
regression. The likely failure mode is one of two patterns:

**Pattern A (most likely) — ID-based sort then Map re-lookup:**
The sort comparator was implemented by sorting an array of task IDs (keys) and
then re-fetching each task via `tasks.get(id)`. If any ID in the sorted array
no longer exists in the Map (e.g., deleted between iteration and re-fetch), or
if the sort was applied to a copy of keys that got out of sync, `tasks.get(id)`
returns `undefined`, which is then passed directly to `taskWithCount`.

```js
// Hypothetical implementation that would trigger the bug:
const sortedIds = Array.from(tasks.keys()).sort((a, b) => {
  const ta = tasks.get(a);
  const tb = tasks.get(b);
  const ca = ta.category ? CATEGORY_ORDER[ta.category] : Infinity;
  const cb = tb.category ? CATEGORY_ORDER[tb.category] : Infinity;
  return ca - cb;
});
// If any id was deleted after the sort, tasks.get(id) returns undefined here:
const result = sortedIds.map(id => taskWithCount(tasks.get(id)));  // ← crash
```

**Pattern B (alternative) — off-by-one in null sentinel logic:**
The null-category sentinel logic (`Infinity` / `-Infinity`) might have
introduced a code path where the sort callback itself returns a mutated or
corrupted array element (e.g., a conditional branch returning `undefined`
instead of a task object before the `.map(taskWithCount)` call).

In either case, the fix is to ensure `taskWithCount` is never called with a
non-task value. A guard inside `taskWithCount` would mask the symptom; the real
fix is to eliminate the upstream source of `undefined`.

### Affected Code Paths

| Repo | File | Function/Line | Issue |
|------|------|---------------|-------|
| api | `src/app.js` | `taskWithCount` / line 34 | Accesses `task.id` when `task` is `undefined` — no defensive guard |
| api | `src/app.js` | `GET /tasks` handler / line 109 | Passes potentially-undefined value to `taskWithCount`; likely introduced by `case 'category':` sort branch added in task-category-enhancements wave 1 |

### Fix Strategy

1. **Open `src/app.js`** and locate the `case 'category':` sort block added by
   the task-category-enhancements PR (near `STATUS_ORDER` and the existing sort
   switch/if-chain).

2. **Identify how tasks are fetched after sorting.** If the implementation
   sorts task IDs and re-fetches with `tasks.get(id)`, change it to sort
   `Array.from(tasks.values())` directly (no re-lookup needed). Example:

   ```js
   case 'category': {
     const order = req.query.order === 'desc' ? -1 : 1;
     taskList.sort((a, b) => {
       const ca = a.category != null ? CATEGORY_ORDER[a.category] : Infinity;
       const cb = b.category != null ? CATEGORY_ORDER[b.category] : Infinity;
       if (ca !== cb) return order * (ca - cb);
       return new Date(b.createdAt) - new Date(a.createdAt); // tiebreaker
     });
     break;
   }
   ```

   where `taskList` is already `Array.from(tasks.values())` — the same array
   that is later mapped through `taskWithCount`.

3. **Add a regression test** in `tests/tasks.test.js`: create a task, delete
   it, then call `GET /tasks?sort=category` and assert 200 (verifies no
   stale-ID re-lookup path).

4. **Optionally add a guard** in `taskWithCount` as a belt-and-suspenders
   defence:

   ```js
   function taskWithCount(task) {
     if (!task) throw new Error('taskWithCount called with undefined task');
     // ... existing logic
   }
   ```

   This converts a silent `TypeError` into a loud, named error for future
   debugging, but does not prevent the crash — the upstream fix (step 2) is
   required.

## Scope Assessment

- [x] Single-task fix (one repo, <50 lines)

The fix is isolated to `src/app.js`: correct the category sort block and add
one regression test. Estimated ~10–20 lines changed.

## Acceptance Criteria

- [ ] `GET /tasks` returns 200 for all existing requests (no `?sort=category`
  param needed to reproduce the fix)
- [ ] `GET /tasks?sort=category&order=asc` returns correct ordering without error
- [ ] `GET /tasks?sort=category&order=desc` returns correct ordering without error
- [ ] Regression test added: call `GET /tasks?sort=category` after a task
  delete and assert 200 with correct remaining tasks
- [ ] All existing tests in `tests/tasks.test.js` continue to pass (`npm test`)
- [ ] No `undefined` value can reach `taskWithCount` via any sort path
