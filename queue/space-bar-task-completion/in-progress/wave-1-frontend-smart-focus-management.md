---
task-id: smart-focus-management
status: in-progress
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: space-bar-task-completion
type: feature
claimed-by: cloud-Christians-MacBook-Air-21641
claimed-at: 2026-04-08T14:05:15Z
claimed-on: Christians-MacBook-Air
---

## Description

Implement focus movement to next incomplete task after space bar completion

## Why

Enables seamless workflow by automatically advancing focus to the next actionable task, respecting the user's current filtered view context

## Implementation Notes

Extend existing navigateFocus function to handle post-completion focus movement. After successful task completion, scan current filtered/sorted task list for next incomplete task. Handle edge case where completed task was the last incomplete task in view (focus stays). Work with existing filteredTasks state and current sort/filter parameters.

## Contract References

No direct API interaction - uses existing task list state and completion status from basic space bar handler

## Acceptance Criteria

### Behaviors

- **GIVEN** a user completes a task with space bar and there are more incomplete tasks in the current view
  **WHEN** the task completion finishes
  **THEN** keyboard focus automatically moves to the next incomplete task in the current filtered/sorted list

- **GIVEN** a user completes the last incomplete task in their current filtered view with space bar
  **WHEN** the task completion finishes
  **THEN** keyboard focus remains on the same task that was just completed

- **GIVEN** a user has tasks filtered by category and completes one with space bar
  **WHEN** the task completion finishes
  **THEN** focus moves to the next incomplete task within the same category filter

### Invariants

- [ ] Tests pass
- [ ] Respects current filtering and sorting
- [ ] Integrates with existing keyboard navigation
