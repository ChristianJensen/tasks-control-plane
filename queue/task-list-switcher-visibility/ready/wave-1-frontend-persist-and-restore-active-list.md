---
task-id: persist-and-restore-active-list
status: ready
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: task-list-switcher-visibility
type: feature
scenario-refs:
  - BDD-5
  - BDD-9
  - BDD-10
---

## Description

User's last-selected list is restored automatically when they reopen the app in a new session. If the persisted list no longer exists on the server, the app falls back to the first available list and overwrites the stale persisted selection. If task lists are still loading when the user clicks the switcher, the dropdown opens in a loading state and populates when lists arrive.

## Why

Delivers durable per-user experience across sessions (R5, R7) and graceful handling of the loading window, so users never see an empty/unselected state.

## Implementation Notes

On app init, read {listId, name} from localStorage and render the header optimistically with the persisted name before /task-lists resolves. After fetch resolves: if persisted listId is still present in server response, keep it; otherwise fall back to first returned list and overwrite localStorage. Dropdown loading state: when open and lists haven't resolved yet, render a skeleton/spinner row and swap to options on arrival.

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** a user has previously selected a specific list in an earlier session
  **WHEN** they reopen the app
  **THEN** that list is loaded and shown in the header automatically, with no empty or unselected state displayed _(implements BDD-5)_

- **GIVEN** the user's persisted last-used list no longer exists on the server
  **WHEN** the app loads
  **THEN** the app falls back to the first available list, the header updates to that list's name, and the stale persisted selection is overwritten _(implements BDD-9)_

- **GIVEN** the task lists are still loading
  **WHEN** the user clicks the switcher
  **THEN** the dropdown opens in a loading state and populates once the lists have loaded _(implements BDD-10)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
