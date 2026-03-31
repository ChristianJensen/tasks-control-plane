---
task-id: basic-contact-panel
status: in-progress
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: i-want-to-add-contact-details
type: feature
claimed-by: agent-Christians-MacBook-Air-2125
claimed-at: 2026-03-31T21:55:27Z
claimed-on: Christians-MacBook-Air
cost-usd: 1.1054541000000002
input-tokens: 56
output-tokens: 13131
duration-ms: 283675
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/81
pr-number: 81
---

## Description

User can open and view contact details panel with basic functionality

## Why

Delivers core user value - ability to access contact information. Provides foundation for enhanced UX features.

## Implementation Notes

Create ContactPanel component following existing HelpDrawer pattern. Add Contact Us button to App.jsx header. Display email/phone from environment variables VITE_CONTACT_EMAIL and VITE_CONTACT_PHONE. Basic open/close with X button only. Use same styling patterns as HelpDrawer (right slide-out, backdrop, z-index 300-301). Handle missing config with fallback message.

## Contract References

No API changes required - frontend-only feature.

## Acceptance Criteria

### Behaviors

- **GIVEN** a user is on any page in the application
  **WHEN** they look at the global navigation
  **THEN** they see a Contact Us button

- **GIVEN** a user clicks the Contact Us button
  **WHEN** the contact panel opens
  **THEN** they see a slide-out panel from the right side with email and phone information

- **GIVEN** a user views contact information in the panel
  **WHEN** they click the email address
  **THEN** their default email client opens with a new message to the support email

- **GIVEN** a user views contact information in the panel
  **WHEN** they click the phone number on a mobile device
  **THEN** their phone dialer opens ready to call the support number

- **GIVEN** a user has the contact panel open
  **WHEN** they click the X button in the panel
  **THEN** the panel closes and slides out to the right

- **GIVEN** contact configuration is missing or invalid
  **WHEN** a user opens the contact panel
  **THEN** they see a Contact information unavailable message

### Invariants

- [ ] Tests pass
- [ ] Contact info loads from environment variables
- [ ] Email and phone are clickable links
