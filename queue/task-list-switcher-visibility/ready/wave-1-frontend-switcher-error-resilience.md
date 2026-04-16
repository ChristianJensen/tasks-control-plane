---
task-id: switcher-error-resilience
status: ready
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: task-list-switcher-visibility
type: feature
scenario-refs:
  - BDD-8
  - BDD-13
---

## Description

When the /task-lists fetch fails on initial load, the header shows a safe fallback label (e.g. "Tasks") and the dropdown, when opened, shows an error state with a retry affordance. When the user selects a different list and the subsequent task fetch fails, the header still reflects the newly selected list and the task area shows an error state with retry — the switch is not reverted.

## Why

Delivers non-blocking failure behavior (from edge cases 2 and 6 of the User Journey). Ensures the feature degrades gracefully and users' intentional switch actions are respected even when backend calls fail.

## Implementation Notes

Track a separate error state for /task-lists fetch. On error: header renders fallback label ("Tasks") unless a cached listId+name from localStorage is present. Dropdown, when opened while in error state, shows an error message and a Retry button that re-issues the fetch. Separately, task-fetch errors after a switch must not mutate the active listId — only surface an error in the task area with retry.

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** the request to load the user's task lists fails on initial load
  **WHEN** the user opens the switcher
  **THEN** the header shows a safe fallback label and the dropdown shows an error state with a retry affordance _(implements BDD-8)_

- **GIVEN** the user selects a different list from the dropdown
  **WHEN** the subsequent task fetch fails
  **THEN** the header still reflects the newly selected list and the task area shows an error state with a retry option (the switch is not reverted) _(implements BDD-13)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
