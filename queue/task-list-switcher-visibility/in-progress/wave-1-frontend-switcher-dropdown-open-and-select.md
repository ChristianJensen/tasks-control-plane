---
task-id: switcher-dropdown-open-and-select
status: in-progress
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: task-list-switcher-visibility
type: feature
scenario-refs:
  - BDD-3
  - BDD-4
  - BDD-7
  - BDD-11
claimed-by: cloud-Christians-MacBook-Air-56806
claimed-at: 2026-04-16T17:31:47Z
claimed-on: Christians-MacBook-Air
---

## Description

User can click the list name in the header to open a dropdown listing all their task lists (active one marked as selected), click a different list to switch (header updates, tasks re-fetch, selection is persisted), and close the dropdown by clicking outside. Single-list users see the dropdown work with one option that is a no-op on click.

## Why

Delivers the core switching interaction (R2, R3, R4, R5). This is the headline capability of the feature — one-click list switching from the header.

## Implementation Notes

Render dropdown as a listbox below the header selector. Each option gets data-testid="task-list-option-{id}". Mark active option via aria-selected and a visual indicator. On option click: update active listId, close dropdown, trigger tasks re-fetch scoped by listId, persist {listId, name} to localStorage. Single-list no-op: if clicked option equals active listId, just close (no fetch). Use a click-outside handler to close without changing state.

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** the user is viewing a task list
  **WHEN** they click the list name in the header
  **THEN** a dropdown opens below it listing all of their task lists, with the currently active list marked as selected _(implements BDD-3)_

- **GIVEN** the switcher dropdown is open
  **WHEN** the user clicks a different list
  **THEN** the dropdown closes, the header updates to show the newly selected list's name, the task area displays only tasks from that list, and the selection is persisted for future sessions _(implements BDD-4)_

- **GIVEN** the user has only one task list
  **WHEN** they open the switcher dropdown
  **THEN** the dropdown shows just that single list marked as selected, and clicking it closes the dropdown without triggering a task re-fetch _(implements BDD-7)_

- **GIVEN** the switcher dropdown is open
  **WHEN** the user clicks outside the dropdown
  **THEN** the dropdown closes and the active list is unchanged _(implements BDD-11)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
