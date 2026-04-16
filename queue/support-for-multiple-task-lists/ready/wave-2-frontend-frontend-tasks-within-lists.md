---
task-id: frontend-tasks-within-lists
status: ready
execution: autonomous
target-repo: frontend
wave: 2
priority: high
feature: support-for-multiple-task-lists
type: feature
scenario-refs:
  - BDD-4
  - BDD-8
---

## Description

Task creation and display works within the current task list context

## Why

Ensures existing task functionality operates correctly within the new list-based organization

## Implementation Notes

Update task creation to send current listId. Modify task fetching to filter by current list. Ensure all existing task operations (edit, delete, status changes) work within list context. Update task display to show only current list's tasks.

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** a user creates a new task
  **WHEN** they are viewing a specific task list
  **THEN** the task is added to that list only _(implements BDD-4)_

- **GIVEN** a user is viewing a task list with multiple tasks
  **WHEN** they apply a filter or sort
  **THEN** only tasks from that list are affected by the filter or sort _(implements BDD-8)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
