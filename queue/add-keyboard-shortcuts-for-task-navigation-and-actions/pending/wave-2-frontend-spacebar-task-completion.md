---
task-id: spacebar-task-completion
status: pending
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: add-keyboard-shortcuts-for-task-navigation-and-actions
type: feature
---

## Description

Implement spacebar key to mark focused task as complete via API, with optimistic updates, error handling, and focus advancement.

## Why

Enables users to efficiently complete tasks using keyboard shortcuts, integrating with the existing API while providing smooth user experience through optimistic updates.

## Implementation Notes

Add spacebar event handler to focused tasks. Use existing PATCH /tasks/{taskId} API with {status: 'done'} and X-User-Id header. Implement optimistic UI updates with revert on API failure. Show loading indicator during API calls and disable spacebar to prevent duplicate requests. After successful completion, advance focus to next available task (or previous if completing last task). Handle API errors with user-friendly messages and retry capability.

## Contract References

Uses PATCH /tasks/{taskId} endpoint with status field and X-User-Id header for task completion.

## Acceptance Criteria

### Behaviors

- **GIVEN** a task has keyboard focus and is not completed
  **WHEN** the user presses the spacebar
  **THEN** the task status changes to done and the UI updates immediately to show completed styling

- **GIVEN** a task is marked complete via spacebar
  **WHEN** the API call succeeds
  **THEN** focus automatically advances to the next task in the list

- **GIVEN** the last task in the list is marked complete via spacebar
  **WHEN** the API call succeeds and it was the only remaining task
  **THEN** focus remains on the completed task

- **GIVEN** the last task in the list is marked complete via spacebar
  **WHEN** the API call succeeds and other tasks remain
  **THEN** focus moves to the previous task in the list

- **GIVEN** a task completion API call fails due to network or server error
  **WHEN** the error response is received
  **THEN** the task reverts to its original status, an error message is displayed, and focus remains on the task for retry

- **GIVEN** a task completion API call is in progress
  **WHEN** the user presses spacebar on the same or different tasks
  **THEN** the spacebar action is disabled and shows a loading indicator until the API call completes

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
- [ ] X-User-Id header included in API calls
