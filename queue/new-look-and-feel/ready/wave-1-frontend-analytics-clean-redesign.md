---
task-id: analytics-clean-redesign
status: ready
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: new-look-and-feel
type: feature
scenario-refs:
  - BDD-4
---

## Description

Transform analytics dashboard from cyberpunk aesthetic to clean, professional design. Update chart styling, card layouts, and data visualization to match reference site while maintaining Chart.js functionality.

## Why

Analytics dashboard currently uses neon colors and cyberpunk styling that detracts from professional data presentation. Clean design improves data readability and professional appearance.

## Implementation Notes

Update src/AnalyticsPage.jsx styling and Chart.js configuration to use clean, professional colors. Replace neon chart colors with subtle, professional palette. Update card layouts, headers, and data presentation styling. Ensure chart interactivity and data export functionality remains unchanged. Focus on clean typography and subtle visual hierarchy.

## Contract References

Uses existing /tasks/analytics and /tasks/analytics/csv endpoints - no API changes needed.

## Acceptance Criteria

### Behaviors

- **GIVEN** user navigates to analytics dashboard
  **WHEN** analytics load
  **THEN** charts and data visualizations display with clean, professional styling _(implements BDD-4)_

### Invariants

- [ ] Tests pass
- [ ] Chart.js functionality preserved
- [ ] CSV export works
- [ ] Data accuracy maintained
- [ ] Mobile responsive analytics
