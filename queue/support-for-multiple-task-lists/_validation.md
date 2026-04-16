# Decomposition Validation: support-for-multiple-task-lists

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | api | api-task-lists-model | high | 150 |
| 2 | api | api-task-lists-crud | high | 200 |
| 2 | api | api-tasks-scoped-to-lists | high | 100 |
| 2 | frontend | frontend-task-list-navigation | high | 180 |
| 2 | frontend | frontend-task-list-management | high | 220 |
| 2 | frontend | frontend-tasks-within-lists | high | 120 |

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
- [ ] Every Wave 2+ task is named as a user story (user-can-X, user-sees-Y)
- [ ] Every behavioral scenario (GIVEN/WHEN/THEN) traces to a feature spec User Journey step
- [ ] Every feature BDD-N scenario is covered by at least one task's scenario-refs
