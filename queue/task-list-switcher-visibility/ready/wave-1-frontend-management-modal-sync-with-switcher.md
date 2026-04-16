---
task-id: management-modal-sync-with-switcher
status: in-progress
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: task-list-switcher-visibility
type: feature
scenario-refs:
  - BDD-6
  - BDD-14
  - BDD-15
claimed-by: cloud-Christians-MacBook-Air-78679
claimed-at: 2026-04-16T18:08:02Z
claimed-on: Christians-MacBook-Air
---

## Description

The existing "manage lists" modal continues to work unchanged for create/rename/delete. When a list is renamed in the modal, the header switcher reflects the new name without a page reload. When the currently active list is deleted in the modal, the app automatically switches to another available list, updates the header, and re-fetches tasks for the new active list.

## Why

Ensures the new header switcher stays consistent with the existing management modal's CRUD operations (R9, R10). Without this, the header could show stale names or dangling references to deleted lists.

## Implementation Notes

Share the task-lists state (or re-fetch on modal close) so the header picks up renames/deletes. On rename: header re-reads the active list's name from the refreshed list. On delete-of-active: pick the first remaining list as new active, update header, persist to localStorage, re-fetch tasks. The existing modal code path should not be rewritten — just hook into its close/success events.

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** the header switcher is present
  **WHEN** the user opens the existing "manage lists" entry point
  **THEN** the management modal opens and functions as before, independently of the header switcher _(implements BDD-6)_

- **GIVEN** the user renames the currently active list inside the management modal
  **WHEN** the modal closes
  **THEN** the header switcher displays the new name without a page reload _(implements BDD-14)_

- **GIVEN** the user deletes the currently active list inside the management modal
  **WHEN** the deletion succeeds
  **THEN** the app switches to another available list, the header updates, and the task area re-fetches tasks for the new active list _(implements BDD-15)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
