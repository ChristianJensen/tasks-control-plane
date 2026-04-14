---
task-id: basic-space-bar-completion
status: done
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: space-bar-task-completion
type: feature
claimed-by: cloud-Christians-MacBook-Air-47076
claimed-at: 2026-04-14T19:59:07Z
claimed-on: Christians-MacBook-Air
cost-usd: 0.810183
input-tokens: 96
output-tokens: 11001
duration-ms: 370212
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/91
pr-number: 91
---

## Description

Implement core space bar handler for todo→done task transitions with API integration

## Why

Enables the fundamental feature behavior of using space bar to complete tasks, providing the foundation for the keyboard-driven workflow

## Implementation Notes

Add space bar keydown handler in SortableTaskItem component. Check task status is 'todo', call existing toggleTask handler. Integrate with existing focus system (focusedTaskId state). Use existing PATCH /tasks/{taskId} API with completed: true and X-User-Id header. Handle only focused tasks to prevent conflicts with text inputs.

## Contract References

Uses existing PATCH /tasks/{taskId} endpoint with status field and X-User-Id header for task completion

## Acceptance Criteria

### Behaviors

- **GIVEN** a user has a 'todo' task focused with keyboard navigation
  **WHEN** they press the space bar
  **THEN** the task status changes to 'done' and the UI updates to show completion

- **GIVEN** a user has a 'done' task focused with keyboard navigation
  **WHEN** they press the space bar
  **THEN** the task status remains 'done' and no change occurs

- **GIVEN** a user presses space bar when no task has keyboard focus
  **WHEN** they press the space bar
  **THEN** no task completion occurs and space bar is ignored

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
- [ ] Uses existing API infrastructure
