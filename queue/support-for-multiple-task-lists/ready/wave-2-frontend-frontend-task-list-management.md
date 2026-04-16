---
task-id: frontend-task-list-management
status: ready
execution: autonomous
target-repo: frontend
wave: 2
priority: high
feature: support-for-multiple-task-lists
type: feature
scenario-refs:
  - BDD-5
  - BDD-6
  - BDD-7
  - BDD-10
  - BDD-11
---

## Description

User can create, rename, and delete task lists from the UI

## Why

Enables users to manage their task list organization without technical knowledge

## Implementation Notes

Add create list modal/form. Add rename functionality (inline editing or modal). Add delete confirmation dialog with cascade warning. Handle validation errors and display user-friendly messages. Prevent deletion of last list with clear error message.

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** a user wants to create a new task list
  **WHEN** they provide a name
  **THEN** the list is created and becomes the active list _(implements BDD-5)_

- **GIVEN** a user wants to rename a task list
  **WHEN** they provide a new name
  **THEN** the list name is updated _(implements BDD-6)_

- **GIVEN** a user deletes a task list
  **WHEN** the list contains tasks
  **THEN** both the list and all its tasks are permanently deleted _(implements BDD-7)_

- **GIVEN** a user tries to delete their only remaining task list
  **WHEN** they attempt deletion
  **THEN** the operation is prevented and an error is shown _(implements BDD-10)_

- **GIVEN** a user tries to create a task list
  **WHEN** they provide an empty name
  **THEN** a validation error is displayed _(implements BDD-11)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
