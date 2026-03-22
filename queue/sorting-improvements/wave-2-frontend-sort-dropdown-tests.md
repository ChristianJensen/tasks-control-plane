---
status: in-progress
execution: autonomous
target-repo: frontend
wave: 2
priority: high
feature: sorting-improvements
type: feature
depends-on:
  - wave-1-frontend-sort-dropdown-polish.md
claimed-by: agent-Mac-60732
claimed-at: 2026-03-22T00:46:07Z
claimed-on: Mac
---

## Description

Add comprehensive tests for the sort dropdown polish: invalid URL param fallback, request cancellation, loading indicator, updated labels, and sort+filter combinations.

## Why

Wave 1 adds invalid param validation, AbortController cancellation, and loading state. These behaviors need test coverage to prevent regressions and verify edge cases E3 and A1.

## Implementation Notes

Modify `tests/App.test.jsx`. Append tests to the existing 'Sort dropdown' describe block. Follow existing test patterns: `vi.stubGlobal('fetch', mockFetch)`, `render(<App />)`, `@testing-library/react` queries.

New test cases (~100 lines):

1. **Updated labels** (~15 lines): Verify dropdown options show 'Newest first', 'Oldest first', 'Title A–Z', 'Title Z–A', 'Status'. Update any existing tests that reference old labels ('Newest', 'Oldest').

2. **Invalid URL param fallback** (~20 lines): Set `window.history.replaceState({}, '', '/?sort=invalid&order=xyz')` before render. Verify dropdown shows 'Newest first' as selected. Verify fetch is called with `sort=createdAt&order=desc`.

3. **Partial invalid URL params** (~15 lines): Test `sort=title&order=invalid` falls back order to 'desc' but keeps sort as 'title'. Test `sort=invalid&order=asc` falls back sort to 'createdAt' but keeps order as 'asc'.

4. **Loading state** (~15 lines): Verify loading indicator appears during fetch and disappears after completion. Can use a delayed mock fetch to observe the loading state.

5. **Sort with category filter** (~15 lines): Set a category filter, then change sort. Verify both params are sent in the API call. Verify sort state is preserved when changing category filter.

6. **Request cancellation** (~20 lines): Rapidly change sort selection multiple times. Verify only the last selection's params are used in the final fetch. If possible, verify AbortController.abort() is called.

Also update any existing tests that reference old label text ('Newest' → 'Newest first', etc.).

## Contract References

GET /tasks query params: sort (enum: createdAt, title, status), order (enum: asc, desc).

## Acceptance Criteria

- [ ] All tests pass (`npx vitest run`)
- [ ] Tests cover invalid URL param fallback to defaults (A1)
- [ ] Tests cover partial invalid URL params (one valid, one invalid)
- [ ] Tests cover loading state visibility during re-fetch (UX1)
- [ ] Tests cover sort combined with category filter (R7)
- [ ] Tests cover request cancellation on rapid sort switching (E3)
- [ ] Existing sort tests updated to use new label text
- [ ] No test regressions in existing test suite
