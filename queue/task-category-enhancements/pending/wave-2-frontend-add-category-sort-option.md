---
status: pending
execution: autonomous
target-repo: frontend
wave: 2
priority: high
feature: task-category-enhancements
type: feature
depends-on:
  - wave-1-api-add-category-sort-logic.md
---

## Description

Add 'Category' option to the frontend sort dropdown and wire it to send `sort=category` to the API. Add tests for the new sort option.

## Why

With the API supporting category sort (wave 1), the frontend needs to expose this option so users can actually sort their task list by category. This completes the user-facing feature.

## Implementation Notes

Modify `src/App.jsx` (~1237 lines). Key changes:

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

## Contract References

GET /tasks `sort` query parameter: enum `['createdAt', 'title', 'status', 'category']`. Category sort uses alphabetical order: errands=0, personal=1, work=2.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Contract-compliant
- [ ] Frontend sort dropdown includes 'Category' options (A–Z and Z–A)
- [ ] Selecting Category sort triggers API call with `sort=category`
- [ ] Sort by category composes correctly with status filter
- [ ] URL param `sort=category` is recognized as valid (no fallback)
- [ ] Keyboard navigation and screen reader support inherited from existing dropdown (UX2)
