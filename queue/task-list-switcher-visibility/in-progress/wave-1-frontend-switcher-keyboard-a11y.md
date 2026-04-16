---
task-id: switcher-keyboard-a11y
status: in-progress
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: task-list-switcher-visibility
type: feature
scenario-refs:
  - BDD-12
  - BDD-16
  - BDD-17
  - BDD-18
claimed-by: cloud-Christians-MacBook-Air-66798
claimed-at: 2026-04-16T17:53:27Z
claimed-on: Christians-MacBook-Air
---

## Description

The switcher is fully operable by keyboard: when focused, Enter or Space opens the dropdown; ArrowDown/ArrowUp move focus between options with a visible focus indicator; Enter on a focused option selects that list and closes the dropdown; Escape closes the dropdown without changing the active list.

## Why

Delivers the keyboard accessibility requirement (R11, AC10) so the switcher meets standard listbox/combobox a11y expectations and is usable by keyboard-only users.

## Implementation Notes

Implement standard listbox keyboard model: trigger button handles Enter/Space to open; open dropdown traps Arrow keys to move aria-activedescendant (or roving tabindex) between options; Enter on focused option triggers the same selection path used by click; Escape closes. Ensure :focus-visible styles are applied to both trigger and focused option. Selection logic should reuse the same handler as click-to-select so behavior stays consistent.

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** the switcher dropdown is open
  **WHEN** the user presses Escape
  **THEN** the dropdown closes and the active list is unchanged _(implements BDD-12)_

- **GIVEN** the switcher has keyboard focus
  **WHEN** the user presses Enter or Space
  **THEN** the dropdown opens _(implements BDD-16)_

- **GIVEN** the switcher dropdown is open
  **WHEN** the user presses ArrowDown or ArrowUp
  **THEN** keyboard focus moves to the next or previous list option with a visible focus indicator _(implements BDD-17)_

- **GIVEN** a list option has keyboard focus inside the open dropdown
  **WHEN** the user presses Enter
  **THEN** that list becomes the active list and the dropdown closes _(implements BDD-18)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
