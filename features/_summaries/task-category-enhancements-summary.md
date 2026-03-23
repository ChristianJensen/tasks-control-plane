---
feature: task-category-enhancements
completed: 2026-03-23
tasks: 2
waves: 2
---

## Overview

Users can assign categories (work, personal, errands) to tasks, but cannot sort the task list by category. This means the categorization effort provides no organizational benefit when viewing tasks — users can't group their view by category to focus on one type of work at a time.

## What Was Built

### Wave 1

- **api** — Add `sort=category` support to GET /tasks endpoint. Implement a CATEGORY_ORDER constant mapping (errands=0, personal=1, work=2) co-located with existing sort logic. Sort tasks by this fixed mapping with null/uncategorized tasks sorting last in ascending order and first in descending order. Use createdAt desc as tiebreaker for equal category values. Extend existing sort validation to accept 'category' as a valid sort value (invalid values still return 400).

### Wave 2

- **frontend** — Add 'Category' option to the frontend sort dropdown and wire it to send `sort=category` to the API. Add tests for the new sort option.

## Key Decisions

- **wave-1-api-add-category-sort-logic:** Modify `src/app.js` (~300 lines). Key changes:

1. **CATEGORY_ORDER constant** (~3 lines): Define `const CATEGORY_ORDER = { errands: 0, personal: 1, work: 2 }` near the existing STATUS_ORDER constant (used by status sort). This follows the same pattern.

2. **Extend sort logic in GET /tasks** (~15 lines): In the existing sort handler (look for where `sort` query param is processed and `STATUS_ORDER` is used), add a `case 'category':` branch. Use `CATEGORY_ORDER[task.category]` for comparison. Handle nulls: assign a sentinel value (e.g., `Infinity` for ASC, `-Infinity` for DESC) so nulls sort last/first respectively. Apply createdAt desc tiebreaker (same pattern as existing sort fields).

3. **Validation** (~2 lines): The sort param validation should already accept any value in the enum. Verify 'category' is included in the valid sort values array. If validation uses a hardcoded list, add 'category' to it.

4. **Add test for CATEGORY_ORDER ↔ enum sync** (~5 lines): A test that validates every value in the category enum has a mapping in CATEGORY_ORDER (per AR2 architectural implication).

Add tests in `tests/tasks.test.js` (~80 lines):
- `sort=category&order=asc` returns errands → personal → work → null
- `sort=category&order=desc` returns null → work → personal → errands
- Same-category tasks sub-sorted by createdAt desc
- `sort=category&status=todo` correctly filters and sorts
- All tasks uncategorized (null) → effectively sorted by tiebreaker (E1)
- Single category after filter → tiebreaker applies (E3)
- Invalid sort value still returns 400
- CATEGORY_ORDER covers all enum values (AR2)
- **wave-2-frontend-add-category-sort-option:** Modify `src/App.jsx` (~1237 lines). Key changes:

1. **Add to SORT_OPTIONS** (~5 lines): Find the existing `SORT_OPTIONS` array/object that defines sort dropdown choices (contains entries for 'Newest first', 'Oldest first', 'Title A–Z', 'Title Z–A', 'Status'). Add two new entries following the existing pattern:
   - 'Category A–Z' → `{ sort: 'category', order: 'asc' }`
   - 'Category Z–A' → `{ sort: 'category', order: 'desc' }`
   Match exact naming convention of existing options.

2. **URL param validation** (~2 lines): The existing sort URL param validation (added in sorting-improvements feature) validates against allowed sort values. Ensure 'category' is in the allowed list. If the validation derives from SORT_OPTIONS, this is automatic. If hardcoded, add 'category'.

No new components needed — the existing sort dropdown, AbortController, and loading indicator all work with the new option automatically (A3 confirmed).

Add tests in `tests/App.test.jsx` (~50 lines):
- 'Category A–Z' and 'Category Z–A' options appear in sort dropdown
- Selecting 'Category A–Z' triggers fetch with `sort=category&order=asc`
- Selecting 'Category Z–A' triggers fetch with `sort=category&order=desc`
- Sort by category combined with status filter sends both params
- Selection clears any existing task selection (existing behavior)
- URL param `sort=category` is accepted as valid (no fallback to default)

## Contracts Affected

(No contracts referenced)

## Retrospective Notes

(No retrospective entries)
