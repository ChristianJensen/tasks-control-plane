---
task-id: contact-panel-interactions
status: pending
execution: supervised
target-repo: frontend
wave: 2
priority: medium
feature: i-want-to-add-contact-details
type: feature
---

## Description

User can interact with contact panel using keyboard and backdrop, with smooth animations

## Why

Enhances user experience with standard interaction patterns and visual polish. Completes the core user journey.

## Implementation Notes

Extend ContactPanel with ESC key handler, backdrop click to close, slide animations using CSS transitions. Add click debouncing to Contact Us button during animations. Follow existing HelpDrawer patterns for keyboard event handling. Disable button during animation transitions. Auto-close panel on navigation (useEffect with location change).

## Contract References

No API changes required - frontend interaction enhancements.

## Acceptance Criteria

### Behaviors

- **GIVEN** a user has the contact panel open
  **WHEN** they press the ESC key
  **THEN** the panel closes and slides out smoothly to the right

- **GIVEN** a user has the contact panel open
  **WHEN** they click the backdrop area behind the panel
  **THEN** the panel closes and slides out smoothly to the right

- **GIVEN** a user clicks the Contact Us button
  **WHEN** the panel is animating in
  **THEN** additional clicks are ignored until the animation completes

- **GIVEN** a user has the contact panel open
  **WHEN** they navigate to a different page
  **THEN** the panel automatically closes

- **GIVEN** a user opens or closes the contact panel
  **WHEN** the panel state changes
  **THEN** the panel slides in and out smoothly with animation

### Invariants

- [ ] Tests pass
- [ ] Animations are smooth and performant
- [ ] Button is properly debounced
