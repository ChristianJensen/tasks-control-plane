---
task-id: api-tasks-scoped-to-lists
status: done
execution: supervised
target-repo: api
wave: 2
priority: high
feature: support-for-multiple-task-lists
type: feature
scenario-refs:
  - BDD-4
  - BDD-8
claimed-by: cloud-Christians-MacBook-Air-67503
claimed-at: 2026-04-16T09:01:10Z
claimed-on: Christians-MacBook-Air
cost-usd: 0.6850311000000001
input-tokens: 21
output-tokens: 6916
duration-ms: 122967
pr-url: https://github.com/ChristianJensen/agentic-sdlc-api/pull/31
pr-number: 31
---

## Description

Tasks are created within and filtered by the current task list

## Why

Core behavior ensuring tasks belong to specific lists and existing functionality works within list context

## Implementation Notes

Add listId parameter to GET /tasks endpoint. Modify POST /tasks to accept listId. Update all task queries to filter by listId. Ensure existing sorting/filtering works within list scope.

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
