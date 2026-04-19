---
task-id: mobile-analytics
status: in-progress
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: mobile-support
type: feature
estimated-lines: 220
depends-on:
  - mobile-viewport-and-timestamp-primitives
  - mobile-ui-primitives
scenario-refs:
  - BDD-7
  - BDD-9
  - BDD-8
claimed-by: cloud-Christians-MacBook-Air-43125
claimed-at: 2026-04-19T22:40:16Z
claimed-on: Christians-MacBook-Air
---

## Description

On mobile (&lt; 768px), render the analytics page as a single vertically stacked column where each chart (counts by status, 7-day completions, avg time in status, completed tasks by category) is full-width using the existing charting library's responsive sizing. Move the CSV export action from its current visible position into a "⋮" OverflowMenu in the page header; the overflow menu item triggers the same CSV export handler the desktop uses. Down to 360px, charts must not cause horizontal scroll on the primary content. At ≥ 768px the existing analytics layout renders unchanged.

## Why

Implements R11, R12, BDD-7 (stacked full-width charts + CSV in overflow) and the analytics portion of BDD-9 (no horizontal scroll ≥ 360px) and BDD-8 (desktop unchanged ≥ 768px). Analytics is a self-contained surface in its own file, making this a clean parallelizable slice.

## Files to Modify

- `src/AnalyticsPage.jsx` (edit) — Branch on useIsMobile to render stacked full-width charts on mobile and move CSV export into an OverflowMenu in the header; leave desktop layout path unchanged
- `src/AnalyticsPage.mobile.module.css` (new) — Stacked chart container styles, full-width constraints, 360px safe rendering

## Reference Patterns

- `src/AnalyticsPage.jsx` — existing desktop analytics structure and CSV export handler — reuse handler, DO NOT alter desktop branch
- `src/components/mobile/OverflowMenu.jsx` — Wave 1 primitive — consume, DO NOT modify
- `src/hooks/useIsMobile.js` — Wave 1 hook — consume, DO NOT modify
- `tests/AnalyticsPage.test.jsx` — existing test patterns for this page — DO NOT modify

## Test Plan

- `tests/mobile-analytics.test.jsx` (new) covers BDD-7, BDD-8, BDD-9

## Out of Scope

- Task list, detail, filters, create/edit — owned by other Wave 2 tasks
- Alternative chart representations (e.g., sparklines) — explicitly out of scope in feature spec
- contracts/tasks-api.json — R17 forbids contract changes

## Verification

- npm test -- tests/mobile-analytics.test.jsx passes
- npm test -- tests/AnalyticsPage.test.jsx passes (existing desktop tests unchanged)
- npm test passes (full suite)
- npm run build passes

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** the user is on the mobile analytics screen
  **WHEN** the screen renders
  **THEN** all charts (counts by status, 7-day completions, avg time in status, completed tasks by category) stack vertically, each full-width, and the CSV export action is accessible from a '⋮' overflow menu in the header _(implements BDD-7)_

- **GIVEN** a user is on the analytics screen at a viewport width between 360px and 767px
  **WHEN** the screen renders
  **THEN** charts and controls display without horizontal scroll on primary content and without clipped controls _(implements BDD-9)_

- **GIVEN** a user opens the analytics screen at viewport width ≥ 768px
  **WHEN** the screen renders
  **THEN** the existing desktop analytics layout is used unchanged _(implements BDD-8)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
