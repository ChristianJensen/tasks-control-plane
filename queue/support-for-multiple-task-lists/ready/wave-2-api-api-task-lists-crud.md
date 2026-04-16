---
task-id: api-task-lists-crud
status: ready
execution: supervised
target-repo: api
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

User can create, rename, and delete task lists

## Why

Enables users to organize tasks into separate lists for different contexts

## Implementation Notes

POST /task-lists, PATCH /task-lists/:id, DELETE /task-lists/:id endpoints. Validate against deleting last list. Cascade delete tasks when list is deleted. Return appropriate error messages.

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
