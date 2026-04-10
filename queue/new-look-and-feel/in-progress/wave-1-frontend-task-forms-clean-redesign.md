---
task-id: task-forms-clean-redesign
status: in-progress
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: new-look-and-feel
type: feature
scenario-refs:
  - BDD-3
claimed-by: cloud-Christians-MacBook-Air-70639
claimed-at: 2026-04-10T22:46:42Z
claimed-on: Christians-MacBook-Air
---

## Description

Redesign task creation and editing forms with clean, professional styling. Update input fields, buttons, dropdowns, and form layout to match reference site aesthetic while preserving all form functionality.

## Why

Task forms are a key user interaction point and currently use the cyberpunk styling that users find unappealing. Clean form design improves user experience for task creation and editing.

## Implementation Notes

Update form styling in src/App.jsx for task creation inputs, priority dropdowns, category selectors, and edit forms. Replace neon borders and glows with subtle, professional styling. Update button designs to use clean, modern appearance. Ensure form validation and functionality remains intact. Focus on inline editing forms, modals, and input styling.

## Contract References

No API contract changes - all form endpoints and request/response formats remain unchanged.

## Acceptance Criteria

### Behaviors

- **GIVEN** user clicks to create a new task
  **WHEN** the create form opens
  **THEN** the form displays with improved visual design while maintaining all functionality _(implements BDD-3)_

### Invariants

- [ ] Tests pass
- [ ] All form functionality preserved
- [ ] Form validation works correctly
- [ ] Mobile responsive forms
