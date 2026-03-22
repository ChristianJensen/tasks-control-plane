---
feature: sorting-improvements
completed: 2026-03-22
tasks: 2
waves: 2
---

## Overview

End users managing task lists have no UI control over sort order. The backend API already supports sorting by `createdAt`, `title`, and `status` with ascending/descending order, but the frontend does not expose these controls. Users are stuck with the default order and cannot organize their view to find or prioritize tasks efficiently.

## What Was Built

### Wave 1

- **frontend** — Polish the existing sort dropdown to match the feature spec: update option labels, add invalid URL param validation with graceful fallback, add AbortController for request cancellation on rapid sort switching, and add a loading indicator during sort re-fetch.

### Wave 2

- **frontend** — Add comprehensive tests for the sort dropdown polish: invalid URL param fallback, request cancellation, loading indicator, updated labels, and sort+filter combinations.

## Key Decisions

- **wave-1-frontend-sort-dropdown-polish:** Modify `src/App.jsx`. Key changes:

1. **Update SORT_OPTIONS labels** (~5 lines): Change 'Newest' to 'Newest first', 'Oldest' to 'Oldest first', 'Title A-Z' to 'Title A–Z', 'Title Z-A' to 'Title Z–A'. These labels must match the spec exactly.

2. **Invalid URL param validation** (~15 lines): In the `useState` initializers for `sortField` and `sortOrder` (lines 912-919), validate that the URL param value is one of the allowed enum values (`createdAt`, `title`, `status` for sort; `asc`, `desc` for order). If invalid, fall back to defaults ('createdAt' and 'desc'). Extract valid values from SORT_OPTIONS to keep it DRY.

3. **AbortController for race conditions** (~20 lines): In `fetchTasks`, use an AbortController to cancel in-flight requests when sort/filter changes trigger a new fetch. Store the controller via `useRef`. Before each fetch, abort the previous one. In the catch block, ignore `AbortError`. This addresses edge case E3.

4. **Loading indicator** (~20 lines): Add `const [loading, setLoading] = useState(false)` state. Set loading=true at start of fetchTasks, false on completion/error. Show existing loading pattern (or simple opacity/spinner) on the task list during re-fetch. Update dropdown selection immediately (optimistic UI per UX1).

Edge cases addressed:
- E1: Empty task list — dropdown remains visible and functional (already works)
- E2: Identical titles — API handles tiebreaker (no frontend change needed)
- E3: Race conditions — AbortController cancels stale requests
- A1: Invalid URL params — graceful fallback to defaults
- UX1: Loading state during sort change
- UX2: Accessible label 'Sort tasks' already exists (line 1477)
- **wave-2-frontend-sort-dropdown-tests:** Modify `tests/App.test.jsx`. Append tests to the existing 'Sort dropdown' describe block. Follow existing test patterns: `vi.stubGlobal('fetch', mockFetch)`, `render(<App />)`, `@testing-library/react` queries.

New test cases (~100 lines):

1. **Updated labels** (~15 lines): Verify dropdown options show 'Newest first', 'Oldest first', 'Title A–Z', 'Title Z–A', 'Status'. Update any existing tests that reference old labels ('Newest', 'Oldest').

2. **Invalid URL param fallback** (~20 lines): Set `window.history.replaceState({}, '', '/?sort=invalid&order=xyz')` before render. Verify dropdown shows 'Newest first' as selected. Verify fetch is called with `sort=createdAt&order=desc`.

3. **Partial invalid URL params** (~15 lines): Test `sort=title&order=invalid` falls back order to 'desc' but keeps sort as 'title'. Test `sort=invalid&order=asc` falls back sort to 'createdAt' but keeps order as 'asc'.

4. **Loading state** (~15 lines): Verify loading indicator appears during fetch and disappears after completion. Can use a delayed mock fetch to observe the loading state.

5. **Sort with category filter** (~15 lines): Set a category filter, then change sort. Verify both params are sent in the API call. Verify sort state is preserved when changing category filter.

6. **Request cancellation** (~20 lines): Rapidly change sort selection multiple times. Verify only the last selection's params are used in the final fetch. If possible, verify AbortController.abort() is called.

Also update any existing tests that reference old label text ('Newest' → 'Newest first', etc.).

## Contracts Affected

(No contracts referenced)

## Retrospective Notes

(No retrospective entries)
