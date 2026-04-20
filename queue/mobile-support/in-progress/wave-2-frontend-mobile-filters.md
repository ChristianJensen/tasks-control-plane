---
task-id: mobile-filters
status: in-progress
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: mobile-support
type: feature
estimated-lines: 280
depends-on:
  - mobile-viewport-and-timestamp-primitives
  - mobile-ui-primitives
scenario-refs:
  - BDD-2
  - BDD-17
  - BDD-10
claimed-by: cloud-Christians-MacBook-Air-66295
claimed-at: 2026-04-20T06:54:57Z
claimed-on: Christians-MacBook-Air
---

## Description

On mobile, collapse the existing status and category filter controls into a single "Filters" button in the list header. Tapping it opens a BottomSheet containing checkboxes for status and category, plus an "Apply" action. Applying closes the sheet, re-renders the list filtered, and the Filters button shows an active-filter indicator (e.g., badge/dot or count) whenever at least one filter is set. Filter state is preserved across rotation/resize (BDD-10) — implementation uses the same filter state source as desktop. Add the filtered-empty state: when active filters yield zero matches, show "No tasks match these filters" with a "Clear filters" action that resets filter state. Desktop filter UI remains unchanged.

## Why

Implements R10 and BDD-2 (collapsed filters, bottom sheet, active indicator), BDD-17 (filtered-empty), and the rotation-preserves-filters half of BDD-10. Owning filters as an independent slice keeps this orthogonal to the list-rendering and detail-view tasks.

## Files to Modify

- `src/App.jsx` (edit) — On mobile, replace inline filter controls in the list header with a 'Filters' button that opens MobileFilters; feed and receive filter state from the same source desktop uses; render filtered-empty state
- `src/components/mobile/MobileFilters.jsx` (new) — 'Filters' button + BottomSheet contents (status/category checkboxes + Apply); emits active-filter indicator
- `src/components/mobile/MobileFilters.module.css` (new) — Filters button styling, active indicator, 44×44px checkbox rows

## Reference Patterns

- `src/App.jsx` — existing desktop filter state and handlers — reuse state source, DO NOT modify desktop branch
- `src/components/mobile/BottomSheet.jsx` — Wave 1 primitive — consume, DO NOT modify
- `src/hooks/useIsMobile.js` — Wave 1 hook — consume, DO NOT modify

## Test Plan

- `tests/mobile-filters.test.jsx` (new) covers BDD-2, BDD-10, BDD-17

## Out of Scope

- Zero-tasks (unfiltered) empty state — owned by mobile-task-list task
- src/AnalyticsPage.jsx — owned by mobile-analytics task
- contracts/tasks-api.json — R17 forbids contract changes
- Sort controls redesign — not required by this feature; reuse existing

## Verification

- npm test -- tests/mobile-filters.test.jsx passes
- npm test passes (full suite)
- npm run build passes

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** the user is on the mobile task list
  **WHEN** the user taps the 'Filters' button, selects a status in the bottom sheet that opens, and taps 'Apply'
  **THEN** the bottom sheet closes, the list re-renders filtered to show only matching tasks, and the Filters button indicates an active filter _(implements BDD-2)_

- **GIVEN** the user has active filters and no tasks match them on mobile
  **WHEN** the list renders
  **THEN** the system shows a 'No tasks match these filters' message with a 'Clear filters' action that clears the filters _(implements BDD-17)_

- **GIVEN** a user is on the mobile list with active filters
  **WHEN** the user rotates the device without crossing 768px
  **THEN** the layout reflows and the active filters are preserved _(implements BDD-10)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
