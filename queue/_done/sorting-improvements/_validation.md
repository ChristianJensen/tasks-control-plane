# Decomposition Validation: sorting-improvements

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | frontend | sort-dropdown-polish | high | 60 |
| 2 | frontend | sort-dropdown-tests | high | 100 |

## Validation Checklist

- [ ] Each task can be implemented independently within its repo
- [ ] Cross-repo tasks coordinate only via contracts
- [ ] No task estimated >400 lines without split justification
- [ ] All tasks have appropriate priority set
- [ ] Each edge case from the Feature Spec maps to at least one task's acceptance criteria
- [ ] Contract changes are sufficient for all tasks
- [ ] No circular dependencies
- [ ] Tasks are grouped into waves, each wave <400 lines per repo

## Decisions

- **Frontend-only: No API tasks needed — the spec explicitly states backend sorting is already implemented and API changes are out of scope. The contract already defines sort/order query params on GET /tasks.**
- **No contract changes: The existing tasks-api.json already defines sort (enum: createdAt, title, status) and order (enum: asc, desc) params. contract_diff is null.**
- **Two waves instead of one: Wave 1 handles implementation polish (labels, validation, AbortController, loading state). Wave 2 adds comprehensive tests for the new behavior. This matches the established pattern from past features (helpcontent, logging).**
- **Small task sizes: The core sort feature is already implemented (SORT_OPTIONS, URL params, dropdown, re-fetch, basic tests all exist). Wave 1 is ~60 lines of refinement, Wave 2 is ~100 lines of additional tests. Both are well under the 400-line limit.**
- **Both tasks autonomous: No auth, security, payment, or schema migration work — this is standard UI feature polish and testing.**
