---
task-id: space-key-focus-to-new-task-input
status: done
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: fix-space-key-focus-management
type: feature
scenario-refs:
  - BDD-1
  - BDD-2
  - BDD-3
claimed-by: cloud-Christians-MacBook-Air-34467
claimed-at: 2026-04-14T10:42:06Z
claimed-on: Christians-MacBook-Air
cost-usd: 1.0251961499999998
input-tokens: 43
output-tokens: 16440
duration-ms: 516151
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/89
pr-number: 89
---

## Description

Fix space key focus management to move focus to new task input textbox after task completion

## Why

When users complete a task via spacebar, focus currently jumps to an unpredictable location instead of moving to a logical next action. This disrupts keyboard workflow for accessibility and efficiency users.

## Implementation Notes

Modify the existing handleSpaceComplete function in App.jsx to set focus on the new task input textbox after marking a task complete. The task input should be identifiable via a ref or data-testid. Need to integrate with existing focusedTaskId/navigateFocus system. Preserve existing behavior for tasks with subtasks (spacebar ignored). Estimated ~120 lines including comprehensive test coverage for all scenarios.

## Contract References

No API changes required - this is purely a frontend focus management fix.

## Acceptance Criteria

### Behaviors

- **GIVEN** user has keyboard focus on an active task
  **WHEN** user presses spacebar
  **THEN** task is marked complete AND focus moves to new task input textbox _(implements BDD-1)_

- **GIVEN** user has focus on new task input textbox after spacebar completion
  **WHEN** user types and presses Enter
  **THEN** new task is created successfully _(implements BDD-2)_

- **GIVEN** user has keyboard focus on a task with subtasks
  **WHEN** user presses spacebar
  **THEN** task completion is ignored AND focus remains on current task _(implements BDD-3)_

### Invariants

- [ ] Tests pass (npm test)
- [ ] Existing click-to-complete focus behavior unchanged
- [ ] Focus management integrates with existing keyboard navigation system
- [ ] Input textbox receives proper focus indicators when focused via this mechanism
