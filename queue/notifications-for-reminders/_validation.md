# Decomposition Validation: notifications-for-reminders

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | frontend | due-dates-store | high | 180 |
| 2 | frontend | due-date-form-input | high | 220 |
| 2 | frontend | card-due-date-display | high | 140 |
| 2 | frontend | header-bell-badge | high | 260 |
| 2 | frontend | bell-drawer-navigation | high | 380 |

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
