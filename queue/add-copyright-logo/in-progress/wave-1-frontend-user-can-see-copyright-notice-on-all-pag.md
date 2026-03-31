---
task-id: user-can-see-copyright-notice-on-all-pag
status: in-progress
execution: supervised
target-repo: frontend
wave: 1
priority: medium
feature: add-copyright-logo
type: feature
claimed-by: agent-Christians-MacBook-Air-26174
claimed-at: 2026-03-31T15:54:28Z
claimed-on: Christians-MacBook-Air
cost-usd: 1.3790752500000003
input-tokens: 957
output-tokens: 15599
duration-ms: 415465
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/79
pr-number: 79
---

## Description

Create Footer component with copyright notice "© [current year] RELAY. All rights reserved." and integrate it into the main App layout and AnalyticsPage to display on all pages of the application.

## Why

Users need to see copyright and branding information consistently across all pages for legal compliance and professional presentation.

## Implementation Notes

Create Footer.jsx component with dynamic year calculation using JavaScript Date object, styled with small font, muted color, center-aligned. Add component to both App.jsx and AnalyticsPage.jsx layouts. Handle edge cases: invalid Date values with fallback to 2024, conditional hiding in modals/overlays, singleton pattern to prevent duplicates. Use existing theme tokens for consistency. Include static HTML fallback for when JavaScript is disabled.

## Contract References

No API contract changes required - frontend-only implementation.

## Acceptance Criteria

- [ ] Footer component renders copyright text with current year
- [ ] Dynamic year updates using getFullYear() with error handling
- [ ] Static HTML fallback displays "© 2024 RELAY. All rights reserved." when JavaScript fails
- [ ] Footer appears at bottom of main task page (App.jsx)
- [ ] Footer appears at bottom of analytics page (AnalyticsPage.jsx)
- [ ] Text uses small font size, muted color, center alignment
- [ ] Footer uses existing theme tokens for visual consistency
- [ ] Footer is conditionally hidden in modal overlays (help drawer, category picker)
- [ ] Component prevents duplicate instances during navigation
- [ ] Tests cover all edge cases: invalid dates, modal hiding, theme integration
- [ ] Tests pass (`npm test`)
