---
lifecycle: draft
execution: autonomous
priority: medium
epic: TASK-5
epic-title: Q1 - Task Tracker Enhancements
version: 1
paused-at: ""
paused-by: ""
pause-reason: ""
created-at: "2026-03-23"
completed-at: ""
deployed-at: ""
deployed-env: ""
---
# Feature Spec: Task Category Sort

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| S1 | conversation | Phase 1 interview | User + Planner | 2026-03-23 |
| S2 | spec | features/completed/multiassign-feature.md | — | 2026-03-21 |
| S3 | contract | contracts/tasks-api.json v0.8.0 | — | 2026-03-21 |

## Problem Statement

Users can assign categories (work, personal, errands) to tasks, but cannot sort the task list by category. This means the categorization effort provides no organizational benefit when viewing tasks — users can't group their view by category to focus on one type of work at a time.

## User Journey

1. User opens the task list view → sees tasks sorted by the current default (createdAt desc)
2. User clicks the sort control dropdown → sees options: Created At, Title, Status, **Category** (new)
3. User selects "Category" as the sort field → the task list re-orders alphabetically by category (errands → personal → work), with uncategorized (null) tasks grouped at the end
4. User toggles sort direction to descending → uncategorized tasks appear first, followed by work → personal → errands
5. User applies a status filter while sorted by category → the filtered results remain sorted by category
6. User navigates away and returns → sort preference is not persisted (matches existing sort behavior)

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | Add `category` to the `sort` query parameter enum on `GET /tasks` | S1, S3 | High | Extends existing sort enum: createdAt, title, status → add category |
| R2 | Category sort uses alphabetical order: errands=0, personal=1, work=2 | S1 | High | No workflow progression; alphabetical is predictable |
| R3 | Null/uncategorized tasks sort last in ascending order, first in descending | S1 | High | SQL: NULLS LAST for ASC, NULLS FIRST for DESC |
| R4 | Tiebreaker for equal category values is createdAt desc | S3 | High | Matches existing tiebreaker convention from contract |
| R5 | Add "Category" option to frontend sort dropdown | S1 | High | Follow existing sort UI pattern exactly |
| R6 | Update API contract (tasks-api.json) to include category in sort enum | S1, S3 | High | Bump contract version |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| — | No conflicts detected | — |

## Open Questions

_None — all questions resolved during interview._

## Acceptance Criteria

- [ ] `GET /tasks?sort=category&order=asc` returns tasks ordered: errands → personal → work → null
- [ ] `GET /tasks?sort=category&order=desc` returns tasks ordered: null → work → personal → errands
- [ ] Tasks with the same category are sub-sorted by createdAt desc
- [ ] `GET /tasks?sort=category&status=todo` correctly filters and sorts
- [ ] Invalid sort values still return 400
- [ ] Frontend sort dropdown includes "Category" option
- [ ] Selecting "Category" in the dropdown triggers API call with `sort=category`
- [ ] Contract version is bumped and `category` is added to sort enum

## Out of Scope

- Custom/user-defined categories
- Multiple categories per task
- Category management UI
- Persisting sort preferences across sessions
- Filtering by category (already exists)

## Refinement Log

### Round 1: Assumptions
_What does this spec assume but not explicitly state?_

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | Existing category filter composes cleanly with category sort | Yes | Confirmed — filter and sort are independent query params; same pattern as status filter + status sort |
| A2 | Category sort order should use a fixed mapping (errands=0, personal=1, work=2) not raw SQL alphabetical | Yes | Confirmed — fixed mapping matches status sort pattern, is explicit, and won't break if new categories are added |
| A3 | Frontend sort dropdown is a simple select that only needs a new option added | Yes | Confirmed — no new UI component needed, follows existing pattern |

### Round 2: Edge Cases
_Stress-test the spec with edge cases._

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | All tasks are uncategorized (null) — sort by category is effectively a no-op | R3, R4 | All tasks sort by tiebreaker (createdAt desc). No special handling needed. |
| E2 | Task category changes while list is sorted by category | R5 | Frontend re-fetches task list after mutation (existing pattern). Task appears in new position. |
| E3 | Sort by category combined with category filter (single category) — sort is meaningless | R1, R4 | Valid but no-op; all results share same category, tiebreaker applies. No special case needed. |

### Round 3: Scope Boundaries
_Propose adjacent features and confirm whether they are in or out of scope._

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | Multi-field sorting (e.g., category then status) | Out | Current API supports single sort field; multi-sort requires new query param design and significant complexity |
| B2 | Visual grouping headers when sorted by category | Out | No precedent in existing sort fields (status sort has no group headers); would introduce inconsistent UI pattern |
| B3 | Persisting sort preference across sessions | Out | Requires local storage or user preferences API; separate concern from sort functionality |

### Round 4: Architecture Review
_Challenge architectural implications._

| # | Implication | Impact Area | Resolution |
|---|------------|-------------|------------|
| AR1 | Contract change (adding sort enum value) requires coordinated deployment — frontend must not ship before API | API/infra | Non-breaking change; API ships wave 1, frontend ships wave 2 (matches multiassign pattern) |
| AR2 | Fixed category sort mapping must stay in sync with TaskCategory enum | API/deps | Use a single CATEGORY_ORDER constant co-located with enum; add test that validates all enum values have sort mappings |

**Architecture diagrams consulted:** none — no architectural changes, only extending existing sort pattern
**Diagrams requiring update after ship:** none

### Round 5: PII / Compliance Review
_Identify PII and sensitive data elements._

| # | Data Element | Classification | Handling Requirement |
|---|-------------|---------------|---------------------|
| P1 | N/A | N/A | No new data created, stored, or transmitted. Feature adds a sort option to an existing query parameter. The category field is already classified as `internal` in the contract schema. |

### Round 6: UX & Interaction Review
_Challenge interaction design, accessibility, and visual consistency._

| # | Concern | Category | Resolution |
|---|---------|----------|------------|
| UX1 | Sort dropdown label for the new option | consistency | Use "Category" to match existing labels (Created At, Title, Status). No tooltip needed. |
| UX2 | Keyboard navigation and screen reader support | a11y | New option inherits existing dropdown accessibility. No additional a11y work required — "Category" is descriptive enough for screen readers. |

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
