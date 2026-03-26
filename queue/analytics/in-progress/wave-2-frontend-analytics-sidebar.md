---
status: in-progress
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: analytics
type: feature
claimed-by: agent-Christians-MacBook-Air-88934
claimed-at: 2026-03-26T11:09:53Z
claimed-on: Christians-MacBook-Air
cost-usd: 1.0330960499999997
input-tokens: 41
output-tokens: 12732
duration-ms: 394214
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/62
pr-number: 62
---

## Description

Add an analytics sidebar to the task list view with a toggle button, fetching data from GET /tasks/analytics and displaying three metric sections: task counts by status, daily completions, and average time in status.

## Why

This is the user-facing feature that gives users at-a-glance productivity metrics without leaving the task list view (R2-R7). Depends on the API endpoint from wave 1.

## Implementation Notes

Modify `src/App.jsx` (all components live in this single file, ~1237 lines).

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

## Contract References

GET /tasks/analytics → 200 response: TaskAnalytics schema. countsByStatus has todo/in-progress/done integers. completedPerDay is array of {date: 'YYYY-MM-DD', count: integer} with 7 entries oldest-to-newest. avgTimeInStatus has todo/inProgress as number (hours) or null.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Contract-compliant: correctly parses TaskAnalytics response
- [ ] Toggle button shows/hides the analytics sidebar (R2)
- [ ] Sidebar displays task count by status section (R3)
- [ ] Sidebar displays tasks completed per day for last 7 days (R4)
- [ ] Sidebar displays average time in each status (R5)
- [ ] Analytics data reflects all tasks — no per-user filtering (R6)
- [ ] Sidebar is text/number-based with no charting library dependencies (R7)
- [ ] Toggling sidebar does not cause task list to lose state
- [ ] Loading state: sidebar shows loading indicator while data is fetched (UX1)
- [ ] Error state: sidebar shows error message with retry button on API failure (UX2)
- [ ] Empty state: '0' for counts, 'No data yet' for null averages (E1, E2)
- [ ] Sidebar toggle state not persisted across page loads — defaults to closed (A2)
