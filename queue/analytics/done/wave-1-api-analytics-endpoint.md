---
status: done
execution: supervised
target-repo: api
wave: 1
priority: high
feature: analytics
type: feature
claimed-by: agent-Christians-MacBook-Air-88821
claimed-at: 2026-03-26T10:58:20Z
claimed-on: Christians-MacBook-Air
cost-usd: 0.5521812
input-tokens: 23
output-tokens: 9087
duration-ms: 156867
pr-url: https://github.com/ChristianJensen/agentic-sdlc-api/pull/26
pr-number: 26
---

## Description

Add GET /tasks/analytics endpoint that computes and returns aggregate task metrics: counts by status, daily completions for the last 7 days, and average time spent in each status.

## Why

This is the backend foundation for the analytics sidebar. The frontend needs this single endpoint to fetch all analytics data in one request (R1, R6).

## Implementation Notes

Modify `src/app.js`. Add the route BEFORE `/tasks/:id` routes (same pattern as batch-delete and batch-update-category) to avoid Express path parameter conflicts.

**Important model detail:** Tasks in-memory use `completed: boolean` (not a `status` string field). Map to contract statuses: `completed === false` → 'todo', `completed === true` → 'done'. The in-progress count will be 0 in the current model since the app only tracks todo/done states. This is correct — the contract allows it.

**countsByStatus** (~10 lines): Iterate `tasks` Map, count by derived status. Initialize `{ todo: 0, 'in-progress': 0, done: 0 }` and increment.

**completedPerDay** (~20 lines): Build an array of the last 7 days (today and 6 prior days) as YYYY-MM-DD strings. For each day, count statusHistory entries where `newStatus === 'done'` and `changedAt` falls on that date. Return array ordered oldest to newest.

**avgTimeInStatus** (~30 lines): For each task, get its statusHistory entries sorted by changedAt ascending. For the first transition, the duration in `oldStatus` is `changedAt - task.createdAt`. For subsequent transitions, duration in `oldStatus` is `changedAt - previousTransition.changedAt`. Only count completed transitions (per A3 — tasks that have moved OUT of a status). Accumulate durations by status, then divide by count. Return hours (milliseconds / 3600000). Return `null` if no transitions exist for a status.

Add tests in a new file `tests/analytics.test.js` using supertest (follow existing test patterns with `app._resetStore()` in `beforeEach`).

Test cases (~120 lines):
- Empty state: no tasks → countsByStatus all 0, completedPerDay all 0 counts, avgTimeInStatus both null (E1)
- Tasks exist, no transitions → counts correct, completedPerDay all 0, avgTimeInStatus both null (E2)
- Tasks with transitions → correct daily completion counts, correct averages
- 7-day window: completions older than 7 days excluded
- Multiple transitions per task computed correctly
- Deleted tasks excluded (cascade delete removes history, confirmed by A1)
- Response shape matches contract schema

## Contract References

GET /tasks/analytics → 200 response: TaskAnalytics schema with countsByStatus (object with todo/in-progress/done integers), completedPerDay (array of {date, count} for 7 days), avgTimeInStatus (object with todo/inProgress as number|null in hours).

## Acceptance Criteria

- [ ] Tests pass (`npm test`)
- [ ] Contract-compliant: response matches TaskAnalytics schema exactly
- [ ] GET /tasks/analytics returns 200 with correct countsByStatus reflecting all tasks
- [ ] completedPerDay returns exactly 7 entries ordered oldest to newest
- [ ] avgTimeInStatus returns hours as numbers or null when no transitions exist
- [ ] Empty state: all counts 0, averages null (E1)
- [ ] No transitions state: counts correct, averages null (E2)
- [ ] Only completed transitions counted for averages (A3)
- [ ] Endpoint responds without errors for typical dataset sizes (E3)
