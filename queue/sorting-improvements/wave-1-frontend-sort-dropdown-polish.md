---
status: done
execution: autonomous
target-repo: frontend
wave: 1
priority: high
feature: sorting-improvements
type: feature
claimed-by: agent-Mac-56076
claimed-at: 2026-03-22T00:36:35Z
claimed-on: Mac
---

## Description

Polish the existing sort dropdown to match the feature spec: update option labels, add invalid URL param validation with graceful fallback, add AbortController for request cancellation on rapid sort switching, and add a loading indicator during sort re-fetch.

## Why

The sort dropdown already exists with core functionality (SORT_OPTIONS, URL param sync, re-fetch), but several spec requirements and edge cases are not yet addressed: labels don't match spec exactly, invalid URL params aren't validated, rapid sort switching can cause race conditions, and there's no loading feedback during re-fetch.

## Implementation Notes

Modify `src/App.jsx`. Key changes:

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

## Contract References

GET /tasks query params: sort (enum: createdAt, title, status, default: createdAt), order (enum: asc, desc, default: desc). No contract changes needed — frontend is aligning to existing API contract.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Sort dropdown contains exactly five options with labels: 'Newest first', 'Oldest first', 'Title A–Z', 'Title Z–A', 'Status'
- [ ] Default selection is 'Newest first' when no URL params are present
- [ ] Selecting an option triggers a re-fetch with correct sort and order query params
- [ ] Browser URL updates with sort/order params on selection without page reload
- [ ] Page load with valid sort/order URL params restores correct dropdown selection and fetches accordingly
- [ ] Page load with invalid sort/order URL params gracefully falls back to 'Newest first' defaults (A1)
- [ ] Rapid sort switching cancels in-flight requests; only the most recent response is applied (E3)
- [ ] Loading indicator is shown during sort re-fetch; dropdown updates immediately (UX1)
- [ ] Sort works correctly when combined with existing status, category, and search filters (R7)
- [ ] Sort dropdown has aria-label='Sort tasks' for screen reader accessibility (UX2)
- [ ] Active sort option is visually indicated in the dropdown (R8)
