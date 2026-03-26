# Decomposition Validation: task-descriptions

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | api | add-description-field | high | 100 |
| 1 | frontend | add-description-to-creation-form | high | 100 |
| 2 | frontend | expandable-detail-panel | high | 200 |
| 2 | frontend | inline-description-editing | high | 200 |

## Validation Checklist

- [ ] Each task can be implemented independently within its repo
- [ ] Cross-repo tasks coordinate only via contracts
- [ ] No task estimated >400 lines without split justification
- [ ] All tasks have appropriate priority set
- [ ] Each edge case from the Feature Spec maps to at least one task's acceptance criteria
- [ ] Contract changes are sufficient for all tasks
- [ ] No circular dependencies
- [ ] Tasks are grouped into waves, each wave <400 lines per repo
- [ ] All tasks use the feature's execution mode (no per-task overrides)
- [ ] Every task is a vertical slice (implementation + tests together, no test-only tasks)

## Decisions

- **No contract changes needed: The OpenAPI contract v0.9.0 already defines the description field on Task schema, POST /tasks, and PATCH /tasks/{taskId}. The implementation catches up to the existing contract.**
- **2 waves instead of 3: Wave 1 covers API foundation + frontend creation form (both can run in parallel across repos). Wave 2 covers the detail panel and editing (both frontend tasks). There's no polish wave needed — all edge cases (character counter, 404 handling, unsaved changes, accessibility) are baked into wave 2 tasks.**
- **Wave 2 has two frontend tasks with a dependency: The detail panel task (expandable-detail-panel) must be done before the editing task (inline-description-editing) because editing happens inside the panel. Combined they're ~400 lines which fits the per-repo wave limit.**
- **API task is single and small (~100 lines): The API change is straightforward — add one field to POST and PATCH handlers plus validation. Splitting it further would create unnecessarily tiny tasks.**
- **Frontend creation form is wave 1 (not wave 2): Adding description to the creation form is independent of the detail panel and can ship with the API changes. Users can create tasks with descriptions immediately even before the detail panel exists.**
