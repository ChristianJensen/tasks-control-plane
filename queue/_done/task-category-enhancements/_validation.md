# Decomposition Validation: task-category-enhancements

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | api | add-category-sort-logic | high | 120 |
| 2 | frontend | add-category-sort-option | high | 70 |

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

- **2 waves instead of 3: This is a small, focused feature extending an existing pattern. Wave 1 delivers the API sort logic (must deploy first per AR1), wave 2 adds the frontend option. No polish wave needed — the UI change is minimal (adding options to an existing dropdown) and accessibility is inherited.**
- **Contract already at v0.9.0: The contract was updated during feature spec creation (from v0.8.0 referenced in S3). The sort enum already includes 'category' with full documentation. No further contract changes needed — the decomposition carries the current contract forward as-is.**
- **Single task per repo: Each repo's changes are small enough (API ~120 lines, frontend ~70 lines) to fit in one task. Splitting further would create artificial boundaries within cohesive changes.**
- **API task is medium (120 lines) not small: While the production code changes are ~20 lines, thorough test coverage for all sort combinations, null handling, filter composition, and enum sync (AR2) pushes this to medium. The tests are the bulk of the work.**
- **Frontend depends on API task: Explicit dependency because the frontend must not ship sort=category before the API supports it (AR1). The frontend tests mock fetch, but the feature requires API-first deployment.**
