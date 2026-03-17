---
status: ready
target-repo: api
wave: 1
priority: high
feature: task-sorting
type: feature
contracts:
  - contracts/tasks-api.json
---

## Description

Add `sort` and `order` query parameters to `GET /tasks`. Supported sort fields: `createdAt`, `title`, `status`. Supported order values: `asc`, `desc`. Default: `createdAt` descending.

## Why

Users need to control task ordering. The API currently returns tasks sorted by position only. This adds server-side sorting that the frontend sort dropdown will consume.

## Implementation Notes

**File to modify:** `src/app.js` (~300 lines)

- Add `VALID_SORT_FIELDS = ['createdAt', 'title', 'status']` and `VALID_ORDER = ['asc', 'desc']` constants near the existing `VALID_STATUSES` constant.
- In the `GET /tasks` handler, validate `sort` and `order` query params using the same inline pattern as the status filter validation. Return 400 with descriptive error listing valid values.
- Replace the call to `sortedTasks()` with a new sort implementation:
  - `createdAt` — compare `task.createdAt` timestamps
  - `title` — case-insensitive string comparison (`localeCompare`)
  - `status` — map to workflow order: `{ todo: 0, 'in-progress': 1, done: 2 }`
  - Apply `order` direction (flip comparison for `desc`)
  - Tiebreaker: when primary sort values are equal, sub-sort by `createdAt` descending
- When no sort params are provided, default to `createdAt` descending (not position). This is a behavioral change from the current `sortedTasks()` default.
- Ensure sort works alongside existing filters (`status`, `category`, `search`) — filter first, then sort.

**Test file:** `tests/tasks.test.js` (~493 lines)

Add a new `describe('GET /tasks sorting')` block covering:
- Default sort (no params) returns newest first
- Each sort field with asc/desc
- Status sort uses workflow order
- Tiebreaker behavior
- Invalid sort/order params return 400
- Sort combined with status filter

## Contract References

`GET /tasks` — new `sort` query param (enum: `createdAt`, `title`, `status`, default: `createdAt`) and `order` query param (enum: `asc`, `desc`, default: `desc`). See contract v0.4.0.

## Acceptance Criteria

- [ ] Tests pass (`npm test`)
- [ ] Contract-compliant
- [ ] `GET /tasks?sort=createdAt&order=desc` returns tasks sorted newest first
- [ ] `GET /tasks?sort=title&order=asc` returns tasks sorted alphabetically A-Z
- [ ] `GET /tasks?sort=status&order=asc` returns tasks in order: todo, in-progress, done
- [ ] `GET /tasks` with no sort params defaults to createdAt desc
- [ ] `GET /tasks?sort=invalid` returns 400 with error listing valid sort fields
- [ ] `GET /tasks?order=invalid` returns 400 with error listing valid order values
- [ ] Tiebreaker: tasks with equal sort values sub-sorted by createdAt desc
- [ ] Sort works alongside existing status, category, and search filters
