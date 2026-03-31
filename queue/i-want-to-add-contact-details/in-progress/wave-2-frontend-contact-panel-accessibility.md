---
task-id: contact-panel-accessibility
status: in-progress
execution: supervised
target-repo: frontend
wave: 2
priority: medium
feature: i-want-to-add-contact-details
type: feature
claimed-by: agent-Christians-MacBook-Air-21475
claimed-at: 2026-03-31T22:15:42Z
claimed-on: Christians-MacBook-Air
cost-usd: 0.9445062
input-tokens: 38
output-tokens: 14968
duration-ms: 356883
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/82
pr-number: 82
---

## Description

Contact panel is fully accessible and handles overlay conflicts gracefully

## Why

Ensures inclusive user experience and robust operation alongside existing application features.

## Implementation Notes

Add proper focus management (focus panel on open, return to button on close), ARIA labels and roles following HelpDrawer pattern. Implement focus trap within panel. Add logic to close existing overlays (help drawer, category picker, etc.) when contact panel opens. Use proper z-index values that don't conflict with existing overlays. Add screen reader announcements for panel state changes.

## Contract References

No API changes required - accessibility and integration improvements.

## Acceptance Criteria

### Behaviors

- **GIVEN** a user opens the contact panel using keyboard
  **WHEN** the panel appears
  **THEN** focus moves to the first interactive element in the panel and screen readers announce the panel

- **GIVEN** a user has the contact panel open
  **WHEN** they use Tab key to navigate
  **THEN** focus stays trapped within the panel elements

- **GIVEN** a user closes the contact panel
  **WHEN** the panel disappears
  **THEN** focus returns to the Contact Us button

- **GIVEN** a user has the help drawer open
  **WHEN** they click Contact Us
  **THEN** the help drawer closes and the contact panel opens without conflicts

- **GIVEN** a user has the contact panel open
  **WHEN** the panel is displayed
  **THEN** it appears above other UI elements without visual conflicts

### Invariants

- [ ] Tests pass
- [ ] Focus management works correctly
- [ ] ARIA labels are present
- [ ] No overlay z-index conflicts
