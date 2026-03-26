---
lifecycle: draft
execution: supervised
priority: medium
budget: ""
total-budget: ""
total-cost-usd: ""
total-tokens: ""
epic: TASK-5
epic-title: Q1 - Task Tracker Enhancements
version: 1
paused-at: ""
paused-by: ""
pause-reason: ""
created-at: "2026-03-26"
completed-at: ""
deployed-at: ""
deployed-env: ""
---
# Feature Spec: Task Analytics Sidebar

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| 1 | conversation | (interview) | Christian Jensen | 2026-03-26 |

## Problem Statement

All end users of the task tracker currently have no visibility into their productivity patterns or task distribution. Without analytics, users cannot see how tasks are distributed across statuses, how many tasks are being completed over time, or how long tasks typically spend in each workflow stage. This feature adds a lightweight analytics sidebar to the existing task list view, giving users at-a-glance metrics without leaving their workflow.

## User Journey

1. User opens the task list view and sees a toggle button (e.g., "Analytics" icon/button) in the UI.
2. User clicks the toggle button to open the analytics sidebar.
3. The sidebar slides in (right-hand panel) alongside the task list, displaying three metric sections stacked vertically:
   a. **Task count by status** — shows counts for todo, in-progress, and done.
   b. **Tasks completed (last 7 days)** — shows a daily breakdown of tasks marked done in the past 7 days.
   c. **Average time in each status** — shows how long tasks typically remain in todo and in-progress before transitioning.
4. All metrics reflect all tasks in the system (no per-user filtering).
5. User can click the toggle button again to hide the sidebar and return to the full-width task list.

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | Add a `GET /tasks/analytics` API endpoint that returns aggregate metrics (task counts by status, completions per day for last 7 days, average time in each status) | S1 | High | Single endpoint, server-side aggregation |
| R2 | Display a toggle button in the task list view to show/hide the analytics sidebar | S1 | High | |
| R3 | Analytics sidebar shows task count by status (todo, in-progress, done) | S1 | High | Text/numbers only, no charts |
| R4 | Analytics sidebar shows tasks completed per day for the last 7 days | S1 | High | Fixed 7-day window |
| R5 | Analytics sidebar shows average time spent in each status (todo, in-progress) | S1 | High | Derived from status history transitions |
| R6 | Analytics data reflects all tasks in the system, not filtered by user | S1 | High | |
| R7 | Sidebar is text/number-based — no charting libraries | S1 | High | Keep it simple |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| (none) | | |

## Open Questions

- [ ] None currently blocking.

## Acceptance Criteria

- [ ] `GET /tasks/analytics` returns a JSON payload with task counts by status, daily completions for the last 7 days, and average time per status
- [ ] The task list view includes a toggle button that shows/hides the analytics sidebar
- [ ] The analytics sidebar displays all three metric sections with correct data
- [ ] The sidebar is text/number-based with no charting library dependencies
- [ ] Toggling the sidebar does not cause the task list to lose state (scroll position, selections, etc.)
- [ ] The analytics endpoint responds in a reasonable time (<500ms) for typical dataset sizes
- [ ] Empty state: sidebar shows "0" for counts and "No data yet" for averages when no tasks exist
- [ ] Error state: sidebar shows error message with retry button when API call fails
- [ ] Loading state: sidebar shows loading indicator while data is being fetched

## Out of Scope

- Per-user filtering of analytics
- Date range picker or custom time windows
- Charts or data visualizations
- Export or download of analytics data
- Real-time/live-updating analytics (standard page-load fetch is sufficient)
- Category-based analytics breakdowns
- Auto-refresh / live-updating sidebar

## Refinement Log

### Round 1: Assumptions
_What does this spec assume but not explicitly state?_

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | Deleted tasks are excluded from analytics (cascade delete removes history) | Yes | Confirmed — deleted tasks and their history are gone; no soft-delete needed |
| A2 | Sidebar toggle state is not persisted across page loads (defaults to closed) | Yes | Confirmed — no localStorage or user preferences for v1 |
| A3 | "Average time in status" only counts completed transitions (task moved out of that status), not tasks still sitting in a status | Yes | Confirmed — only completed transitions, avoids skew from newly created tasks |

### Round 2: Edge Cases
_Stress-test the spec with edge cases._

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | No tasks exist — all metrics are empty | R3, R4, R5 | Show "0" for counts, "No data yet" for averages; sidebar renders gracefully |
| E2 | Tasks exist but no status transitions recorded (all tasks in initial "todo" state) | R5 | Show "N/A" or "No transitions yet" for average time metrics |
| E3 | Large dataset (thousands of tasks/transitions) causes slow aggregation | R1 | Compute on the fly for v1 with <500ms target; optimize with caching later if needed |

### Round 3: Scope Boundaries
_Propose adjacent features and confirm whether they are in or out of scope._

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | Category-based analytics (breakdown by work/personal/errands) | Out | Keep v1 simple; can add grouping in follow-up |
| B2 | Per-user analytics (filter by X-User-Id) | Out | Interview confirmed all-tasks view; no user filtering for v1 |
| B3 | Auto-refresh / live-updating analytics | Out | Standard fetch-on-open is sufficient; avoids websocket/polling complexity |

### Round 4: Architecture Review
_Challenge architectural implications._

| # | Implication | Impact Area | Resolution |
|---|------------|-------------|------------|
| AR1 | New `GET /tasks/analytics` endpoint added to API contract | API | Single endpoint returning all three metrics in one payload; reduces round-trips. Contract version bumped to 0.10.0 |
| AR2 | Frontend sidebar modifies task list layout | UI/perf | Fixed-width sidebar (300px) with CSS flex layout; task list flexes to fill remaining space. No layout breakage |

**Architecture diagrams consulted:** None available
**Diagrams requiring update after ship:** None

### Round 5: PII / Compliance Review
_Identify PII and sensitive data elements._

| # | Data Element | Classification | Handling Requirement |
|---|-------------|---------------|---------------------|
| P1 | Task counts by status | internal | N/A — aggregate counts, no PII |
| P2 | Daily completion counts | internal | N/A — aggregate counts, no PII |
| P3 | Average time in status | internal | N/A — aggregate durations, no PII. changedBy used for computation only, never exposed in response |

### Round 6: UX & Interaction Review
_Challenge interaction design, accessibility, and visual consistency._

| # | Concern | Category | Resolution |
|---|---------|----------|------------|
| UX1 | Loading state when sidebar opens and data is being fetched | states | Show a loading indicator (spinner or "Loading..." text) inside the sidebar while the API call is in flight |
| UX2 | Error state when analytics API call fails | states | Show "Failed to load analytics. Retry" message with a retry button inside the sidebar; do not close the sidebar on error |

## Readiness Checklist

- [x] All High-confidence requirements have acceptance criteria
- [x] No unresolved conflicts remain
- [x] Open questions are non-blocking or have owners
- [x] At least 3 assumptions explicitly challenged and resolved
- [x] At least 3 edge cases explicitly addressed
- [x] Out of Scope section reviewed via scope boundary probe
- [x] At least 2 architectural implications reviewed
- [x] PII and sensitive data elements identified with handling requirements (or explicit N/A)
- [x] At least 2 UX/interaction concerns reviewed (or explicit N/A for non-UI features)
