---
lifecycle: completed
execution: autonomous
priority: high
epic: TASK-5
version: 1
paused-at: ""
paused-by: ""
pause-reason: ""
created-at: "2026-03-22"
completed-at: 2026-03-22T00:53:11Z
deployed-at: ""
deployed-env: ""
---
# Feature Spec: Sorting Improvements

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| S1 | conversation | Planner interview | End user | 2026-03-22 |
| S2 | contract | contracts/tasks-api.json | — | 2026-03-22 |

## Problem Statement

End users managing task lists have no UI control over sort order. The backend API already supports sorting by `createdAt`, `title`, and `status` with ascending/descending order, but the frontend does not expose these controls. Users are stuck with the default order and cannot organize their view to find or prioritize tasks efficiently.

## User Journey

1. User opens the task list page → tasks load in default sort order (newest first: `sort=createdAt&order=desc`)
2. User sees a sort dropdown in the task list toolbar → the dropdown displays the currently active sort option ("Newest first" by default)
3. User clicks the sort dropdown → a menu appears with five options:
   - Newest first (default)
   - Oldest first
   - Title A–Z
   - Title Z–A
   - Status
4. User selects "Title A–Z" → the task list re-fetches from the API with `?sort=title&order=asc` and re-renders in alphabetical order
5. The dropdown label updates to show "Title A–Z" as the active sort
6. The browser URL updates to include `?sort=title&order=asc` (without full page reload)
7. User copies the URL and shares it with a colleague → colleague opens the link → the page loads with "Title A–Z" sort pre-selected and tasks displayed in that order
8. User refreshes the page → sort state is preserved from URL parameters; tasks reload in the same order

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | Add a sort dropdown to the task list using the existing dropdown component | S1 | High | Reuse existing dropdown component |
| R2 | Dropdown options: "Newest first", "Oldest first", "Title A–Z", "Title Z–A", "Status" | S1 | High | Five options mapping to API sort/order params |
| R3 | Default sort is "Newest first" (`sort=createdAt&order=desc`) | S1, S2 | High | Matches API default |
| R4 | Selecting a sort option re-fetches tasks from `GET /tasks` with appropriate `sort` and `order` query params | S1, S2 | High | Frontend-only; no API changes |
| R5 | Sort selection persists in the browser URL as query parameters (`?sort=...&order=...`) | S1 | High | Enables bookmarking and sharing |
| R6 | On page load, read sort/order from URL params and apply them to the dropdown and API call | S1 | High | URL is source of truth for sort state |
| R7 | Sort dropdown works alongside existing filters (status filter, category) without conflict | S2 | High | Params are additive on the API |
| R8 | Dropdown visually indicates the currently active sort option | S1 | High | Standard UX pattern |

## Sort Option Mapping

| Label | `sort` param | `order` param |
|-------|-------------|---------------|
| Newest first | `createdAt` | `desc` |
| Oldest first | `createdAt` | `asc` |
| Title A–Z | `title` | `asc` |
| Title Z–A | `title` | `desc` |
| Status | `status` | `asc` |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| — | No conflicts detected | — |

## Open Questions

- (none — all questions resolved during interview)

## Acceptance Criteria

- [ ] Sort dropdown is visible in the task list toolbar using the existing dropdown component
- [ ] Dropdown contains exactly five options: Newest first, Oldest first, Title A–Z, Title Z–A, Status
- [ ] Default selection is "Newest first" when no URL params are present
- [ ] Selecting an option triggers a re-fetch with correct `sort` and `order` query params
- [ ] Browser URL updates with sort/order params on selection (no page reload)
- [ ] Page load with sort/order URL params restores the correct dropdown selection and fetches accordingly
- [ ] Sort works correctly when combined with existing status and category filters
- [ ] The active sort option is visually indicated in the dropdown

## Out of Scope

- Backend/API changes (sorting is already implemented)
- Multi-column sort (sort by two fields simultaneously)
- Custom sort orders or user-defined sort preferences
- Drag-and-drop manual reordering
- Saved/persistent sort preferences (localStorage or user profile) — URL persistence is sufficient
- Clickable column header sorting — dropdown pattern is used instead
- Sort by future fields (e.g., due date) — implementation should be extensible but new options are out of scope
- Kanban board view sorting — sort applies to list view only

## Refinement Log

### Round 1: Assumptions
_What does this spec assume but not explicitly state?_

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | Invalid URL sort params silently fall back to default ("Newest first") | Yes | Confirmed — no error shown, graceful fallback |
| A2 | Sort dropdown only applies to list view, not Kanban board view | Yes | Confirmed — Kanban columns are grouped by status, sort is list-view only |
| A3 | Changing filters preserves the current sort selection (sort and filters are independent) | Yes | Confirmed — sort and filter state are independent of each other |

### Round 2: Edge Cases
_Stress-test the spec with edge cases._

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | Empty task list (no tasks match filters) — sort dropdown has no visible effect | R1, R8 | Dropdown remains visible and functional; existing empty state displays normally |
| E2 | Identical titles when sorting by title — sub-sort order unclear | R4 | API tiebreaker handles this (`createdAt desc`); frontend trusts API response order |
| E3 | Rapid sort switching — race condition between API responses | R4 | Frontend cancels in-flight requests; only the most recent selection's response is applied |

### Round 3: Scope Boundaries
_Propose adjacent features and confirm whether they are in or out of scope._

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | Saved/persistent sort preferences (localStorage or user profile) | Out | URL persistence covers sharing and bookmarking; preference conflicts add complexity |
| B2 | Clickable column header sorting with arrow indicators | Out | Dropdown pattern is simpler and has an existing component; table-style sorting is a different paradigm |
| B3 | Sort by future fields (e.g., due date) | Out | Not yet available; implementation should be extensible (config array) so adding options later is easy |

### Round 4: Architecture Review
_Challenge architectural implications._

| # | Implication | Impact Area | Resolution |
|---|------------|-------------|------------|
| AR1 | URL state management pattern for sort/order params must integrate with existing filter params | Frontend architecture | Follow existing URL param pattern in the frontend; if none exists, establish one using framework built-ins (e.g., `useSearchParams`). Merge sort params with filter params, don't replace. |
| AR2 | No new dependencies or services needed | deps/infra | Confirmed — reuses existing dropdown component, existing API endpoint, browser-native URL APIs. Minor dropdown enhancement may be needed if active-selection display isn't supported. |

### Round 5: PII / Compliance Review
_Identify PII and sensitive data elements._

| # | Data Element | Classification | Handling Requirement |
|---|-------------|---------------|---------------------|
| P1 | N/A — no PII involved | N/A | Sort feature only passes enum query params (`sort`, `order`) with predefined values. No user data created, stored, or transmitted beyond existing task data. URL params contain no personal information. |

### Round 6: UX & Interaction Review
_Challenge interaction design, accessibility, and visual consistency._

| # | Concern | Category | Resolution |
|---|---------|----------|------------|
| UX1 | Loading state during sort change — list may appear stuck on old order | states | Show existing loading indicator during re-fetch; update dropdown selection immediately (optimistic UI for dropdown, loading state for list) |
| UX2 | Keyboard navigation and screen reader support for sort dropdown | a11y | Reuse existing dropdown component's accessibility features; add accessible label "Sort tasks" for screen readers |

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
