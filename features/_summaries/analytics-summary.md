---
feature: analytics
completed: 2026-03-26
tasks: 2
waves: 2
total-cost-usd: 1.5853
total-tokens: 21883
---

## Overview

All end users of the task tracker currently have no visibility into their productivity patterns or task distribution. Without analytics, users cannot see how tasks are distributed across statuses, how many tasks are being completed over time, or how long tasks typically spend in each workflow stage. This feature adds a lightweight analytics sidebar to the existing task list view, giving users at-a-glance metrics without leaving their workflow.

## What Was Built

### Wave 1

- **api** — Add GET /tasks/analytics endpoint that computes and returns aggregate task metrics: counts by status, daily completions for the last 7 days, and average time spent in each status.

### Wave 2

- **frontend** — Add an analytics sidebar to the task list view with a toggle button, fetching data from GET /tasks/analytics and displaying three metric sections: task counts by status, daily completions, and average time in status.

## Key Decisions

- **wave-1-api-analytics-endpoint:** Modify `src/app.js`. Add the route BEFORE `/tasks/:id` routes (same pattern as batch-delete and batch-update-category) to avoid Express path parameter conflicts.

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
- **wave-2-frontend-analytics-sidebar:** Modify `src/App.jsx` (all components live in this single file, ~1237 lines).

**1. State** (~5 lines): Add `const [analyticsOpen, setAnalyticsOpen] = useState(false)` and `const [analyticsData, setAnalyticsData] = useState(null)` and `const [analyticsLoading, setAnalyticsLoading] = useState(false)` and `const [analyticsError, setAnalyticsError] = useState(null)` near existing state declarations. Toggle defaults to closed (A2 — not persisted across page loads).

**2. Fetch logic** (~20 lines): Add a `fetchAnalytics` function that calls `GET ${API_URL}/tasks/analytics`. Set loading=true at start, handle success (set data, clear error) and error (set error message, clear data) in try/catch, set loading=false in finally. Call fetchAnalytics when `analyticsOpen` becomes true via useEffect.

**3. Toggle button** (~10 lines): Add an icon button (use `BarChart3` or `BarChart2` from lucide-react) in the task list header/toolbar area. `onClick` toggles `analyticsOpen`. Add `aria-label='Toggle analytics'`. Style consistent with existing toolbar buttons.

**4. AnalyticsSidebar component** (~80 lines): Inline function component. Renders a fixed-width right-hand panel (300px per AR2) using CSS flex layout. The task list flexes to fill remaining space — wrap the main content area in a flex container if not already.

  - **Loading state** (UX1): Show 'Loading...' text or spinner inside sidebar while fetching.
  - **Error state** (UX2): Show 'Failed to load analytics' message with a 'Retry' button that re-calls fetchAnalytics. Do NOT close sidebar on error.
  - **Empty state** (E1): Show '0' for counts, 'No data yet' for averages.
  - **Section 1 — Task count by status** (R3): Display todo, in-progress, done counts as labeled rows.
  - **Section 2 — Completed per day** (R4): Display each of the 7 days with date and count as simple text rows.
  - **Section 3 — Average time in status** (R5): Display average hours for todo and in-progress. Show 'No data yet' when null (E2). Format hours to 1 decimal place.

**5. Layout integration** (~10 lines): When sidebar is open, wrap the task list and sidebar in a flex row. Task list should not lose state (scroll position, selections) when sidebar toggles — use CSS display/flex, not conditional rendering of the task list itself.

**No charting libraries** (R7). Text and numbers only. Style with inline style objects using theme tokens from `theme.js`.

Add tests in `tests/App.test.jsx` (~100 lines), following existing patterns with `vi.stubGlobal('fetch', mockFetch)` and `@testing-library/react`:
- Toggle button renders and opens/closes sidebar
- Analytics data displays correctly when fetched
- Loading state shown while fetching
- Error state with retry button shown on fetch failure
- Retry button re-fetches data
- Empty state: '0' counts and 'No data yet' for null averages
- Toggling sidebar does not cause task list to lose state
- No charting library DOM elements present
- Sidebar shows all three metric sections with correct labels

## Contracts Affected

(No contracts referenced)

## Cost Summary

**Total: $1.5853** (21,883 tokens, 551s)

| Wave | Task | Cost | Tokens |
|------|------|------|--------|
| W1 | wave-1-api-analytics-endpoint | $0.5522 | 9,110 |
| W2 | wave-2-frontend-analytics-sidebar | $1.0331 | 12,773 |

## Retrospective Notes

(No retrospective entries)
