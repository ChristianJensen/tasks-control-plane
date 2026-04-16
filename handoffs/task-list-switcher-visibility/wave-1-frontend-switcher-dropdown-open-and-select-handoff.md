---
task: wave-1-frontend-switcher-dropdown-open-and-select.md
feature: task-list-switcher-visibility
branch: agent/task-list-switcher-visibility-w1-switcher-dropdown-open-and-select
status: done
timestamp: 2026-04-16T17:39:24Z
agent: cloud-Christians-MacBook-Air-56806
---
## Session Summary
**Task:** User can click the list name in the header to open a dropdown listing all their task lists (active one marked as selected), click a different list to switch (header updates, tasks re-fetch, selection is persisted), and close the dropdown by clicking outside. Single-list users see the dropdown work with one option that is a no-op on click.  |  **Status:** done  |  **Exit:** 0

## Cost
**Cost:** $0.9323  |  **Tokens:** 2,513 in / 15,605 out  |  **Duration:** 419s

## What Was Done
853f9e7 feat(task-list-switcher): dropdown open/select with click-outside close (BDD-3, BDD-4, BDD-7, BDD-11)

## Files Changed
src/App.jsx
tests/task-list-switcher-dropdown.test.jsx

## PR Status
PR #102 (OPEN): https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/102

## What's Next
No tasks were blocked on this one.

## Resume Prompt
```
You are resuming work on branch agent/task-list-switcher-visibility-w1-switcher-dropdown-open-and-select for task wave-1-frontend-switcher-dropdown-open-and-select.md.

---
task-id: switcher-dropdown-open-and-select
status: done
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
cost-usd: 0.9322854000000002
input-tokens: 2513
output-tokens: 15605
duration-ms: 418827
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/102
pr-number: 102
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


Previous session: done. Commits:
853f9e7 feat(task-list-switcher): dropdown open/select with click-outside close (BDD-3, BDD-4, BDD-7, BDD-11)

Continue from where the previous agent left off.
```
