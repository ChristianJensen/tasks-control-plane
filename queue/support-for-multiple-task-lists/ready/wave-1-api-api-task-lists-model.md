---
task-id: api-task-lists-model
status: ready
execution: autonomous
target-repo: api
wave: 1
priority: high
feature: support-for-multiple-task-lists
type: feature
scenario-refs:
  - BDD-9
---

## Description

Add task lists data model and extend tasks to belong to lists

## Why

Foundation for all task list functionality - tasks need to be scoped to lists before any UI features can work

## Implementation Notes

Add TaskList model with id, name, createdAt, updatedAt. Add listId foreign key to Task model with cascade delete. Create default task list during user initialization. Update existing task queries to scope by listId.

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** a new user opens the app
  **WHEN** they have no existing task lists
  **THEN** a default task list is automatically created _(implements BDD-9)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
