---
task-id: main-interface-clean-redesign
status: blocked
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: new-look-and-feel
type: feature
scenario-refs:
  - BDD-1
  - BDD-2
claimed-by: cloud-Christians-MacBook-Air-47063
claimed-at: 2026-04-14T22:42:47Z
claimed-on: Christians-MacBook-Air
cost-usd: 0
input-tokens: 0
output-tokens: 0
duration-ms: 452
---

## Description

Transform main task list interface from cyberpunk/neon aesthetic to clean professional design matching reference site. Update task cards, navigation header, and core layout styling while maintaining all existing functionality.

## Why

Addresses the primary user complaint about 'nerdy' appearance by redesigning the most visible part of the application that users interact with daily.

## Implementation Notes

Update CSS variables in src/index.css light theme section to use clean, professional colors. Modify task card styling in src/App.jsx to remove neon glows, reduce border radius, use subtle shadows. Simplify header navigation styling. Remove terminal/monospace fonts in favor of modern sans-serif. Focus on light theme transformation - other themes can remain functional but not fully redesigned.

## Contract References

No API contract changes needed - this is purely visual styling updates to existing frontend components.

## Acceptance Criteria

### Behaviors

- **GIVEN** user opens the application
  **WHEN** the page loads
  **THEN** the interface displays with clean, professional styling instead of nerdy appearance _(implements BDD-1)_

- **GIVEN** user is viewing the task list
  **WHEN** tasks are displayed
  **THEN** all task cards and UI components show modern, clean visual design _(implements BDD-2)_

### Invariants

- [ ] Tests pass
- [ ] All existing functionality preserved
- [ ] Mobile responsive on task list
