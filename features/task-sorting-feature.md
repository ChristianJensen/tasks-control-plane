---
lifecycle: active
version: 1
paused-at: ""
paused-by: ""
pause-reason: ""
---

# Feature Spec: Task Sorting

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| S1 | conversation | — | Christian Jensen | 2026-03-17 |

## Problem Statement

Tasks are returned in an undefined order from the API, and the frontend has no way for users to control how tasks are arranged. As the task list grows, users need to quickly find relevant tasks by sorting on meaningful fields — newest first, alphabetically, or by workflow status.

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | API accepts `sort` query param on `GET /tasks` with values: `createdAt`, `title`, `status` | S1 | High | |
| R2 | API accepts `order` query param with values: `asc`, `desc` | S1 | High | |
| R3 | Default sort is `createdAt` descending when no params provided | S1 | High | Matches current implicit behavior |
| R4 | Invalid `sort` or `order` values return 400 with descriptive error | S1 | High | |
| R5 | Status sort uses workflow order: todo=0, in-progress=1, done=2 | S1 | High | Ascending = unfinished first |
| R6 | Tiebreaker for equal sort values is `createdAt` descending | S1 | High | Ensures stable, predictable ordering |
| R7 | Frontend displays a sort dropdown control (e.g., "Sort by: Newest") | S1 | High | |
| R8 | Sort dropdown options: Newest, Oldest, Title A-Z, Title Z-A, Status | S1 | High | Each maps to sort+order combo |
| R9 | Sort applies within each Kanban column (not just flat list) | S1 | High | |
| R10 | Sort preference persists via URL query params (?sort=...&order=...) | S1 | High | Shareable and bookmarkable |

## Conflicts Detected

_None._

## Open Questions

_None — all scoping questions resolved during interview._

## Acceptance Criteria

- [ ] `GET /tasks?sort=createdAt&order=desc` returns tasks sorted by creation date, newest first
- [ ] `GET /tasks?sort=title&order=asc` returns tasks sorted alphabetically A-Z
- [ ] `GET /tasks?sort=status&order=asc` returns tasks in order: todo, in-progress, done
- [ ] `GET /tasks` with no sort params defaults to `createdAt` desc
- [ ] `GET /tasks?sort=invalid` returns 400 with error message listing valid values
- [ ] `GET /tasks?sort=createdAt&order=invalid` returns 400 with error message
- [ ] Tasks with identical sort values are sub-sorted by `createdAt` desc
- [ ] Sort params combine with existing `status` filter (e.g., `?status=todo&sort=title&order=asc`)
- [ ] Frontend sort dropdown is visible and functional
- [ ] Selecting a sort option updates the URL query params
- [ ] Page reload preserves the selected sort via URL params
- [ ] Kanban board sorts cards within each column according to the selected sort

## Out of Scope

- Pagination / infinite scroll
- Full-text search
- Multi-field / compound sorting (e.g., sort by status then by title)
- Saved or named sort presets
- Drag-and-drop manual ordering
- Server-side sort for comments

## Refinement Log

### Round 1: Assumptions

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | Sort applies globally across all views | Yes | Sort applies within each Kanban column, not just flat list |
| A2 | Sort preference resets on reload | Yes | Persists via URL query params — shareable and bookmarkable |
| A3 | Status sort order is arbitrary | Yes | Uses workflow order: todo → in-progress → done |

### Round 2: Edge Cases

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | Two tasks have same title — which comes first? | R6 | Tiebreaker is createdAt descending |
| E2 | Invalid sort param in URL | R4 | API returns 400 with valid values listed |
| E3 | Sort + status filter combined | AC #8 | Both params work together — filter first, then sort |

### Round 3: Scope Boundaries

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | Pagination | Out | Separate concern; can layer on later without changing sort API |
| B2 | Full-text search | Out | Different query mechanism entirely |
| B3 | Multi-field compound sort | Out | Adds API complexity; single-field covers primary use cases |
| B4 | Saved sort presets | Out | Requires user preferences storage; overkill for now |

## Readiness Checklist

- [x] All High-confidence requirements have acceptance criteria
- [x] No unresolved conflicts remain
- [x] Open questions are non-blocking or have owners
- [x] At least 3 assumptions explicitly challenged and resolved
- [x] At least 3 edge cases explicitly addressed
- [x] Out of Scope section reviewed via scope boundary probe
