---
task-id: mobile-task-detail
status: ready
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: mobile-support
type: feature
estimated-lines: 380
depends-on:
  - mobile-viewport-and-timestamp-primitives
  - mobile-ui-primitives
scenario-refs:
  - BDD-3
  - BDD-4
  - BDD-11
  - BDD-15
  - BDD-21
  - BDD-20
---

## Description

On mobile, replace the desktop side-panel task detail with a full-screen detail view. Header contains a back button that returns to the list with prior scroll position preserved. Body shows full title (wrapping, no overflow), full description, absolute timestamps, and renders comments and history as tabs OR collapsible sections (implementer's choice) — NOT side-by-side. History and comments entries are laid out as vertically stacked, clearly labeled fields (no multi-column table rows). The status control on the detail view uses a touch-friendly selector (BottomSheet-based status picker reusing the Wave 1 BottomSheet primitive): tapping the status opens options, picking one PATCHes the task and updates the view in place. The detail view is registered as a browser history entry so the OS/browser back gesture behaves identically to tapping the in-header back button and does not exit the app. Tapping a card → opening detail uses the tap-once helper to prevent rapid double-navigation. Desktop side-panel behavior is unchanged.

## Why

Implements R5, R6, R16, BDD-3 (full-screen detail with back button), BDD-4 (touch status picker + in-place update), BDD-11 (full title/description wrap in detail), BDD-15 (stacked labeled history/comments), BDD-21 (OS back gesture = in-header back), and part of BDD-20 (rapid-tap disable on card tap and status commit). Comment-adding is handled in a separate slice to keep this task under the 400-line cap.

## Files to Modify

- `src/App.jsx` (edit) — On mobile, route card tap to open MobileTaskDetail full-screen instead of desktop side-panel; restore list scroll position on back; leave desktop branch unchanged
- `src/components/mobile/MobileTaskDetail.jsx` (new) — Full-screen detail view with back button, tabs/collapsible sections, stacked history/comments, status picker (reuses BottomSheet); registers history entry and maps popstate to back
- `src/components/mobile/MobileTaskDetail.module.css` (new) — Full-screen layout, wrapping long content, stacked-field styles for history/comments

## Reference Patterns

- `src/App.jsx` — existing desktop side-panel detail, history/comments rendering, status-update handler — reuse data/handlers, DO NOT modify desktop branch
- `src/components/mobile/BottomSheet.jsx` — Wave 1 primitive for status picker — consume, DO NOT modify
- `src/hooks/useTapOnce.js` — Wave 1 helper for rapid-tap disable — consume, DO NOT modify

## Test Plan

- `tests/mobile-task-detail.test.jsx` (new) covers BDD-3, BDD-4, BDD-11, BDD-15, BDD-20, BDD-21

## Out of Scope

- Add-comment full-screen modal — owned by mobile-create-edit-comment task
- Create/edit task modals — owned by mobile-create-edit-comment task
- src/AnalyticsPage.jsx — owned by mobile-analytics task
- contracts/tasks-api.json — R17 forbids contract changes

## Verification

- npm test -- tests/mobile-task-detail.test.jsx passes
- npm test passes (full suite)
- npm run build passes

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** the user is on the mobile task list
  **WHEN** the user taps a task card
  **THEN** the system navigates to a full-screen task detail view with a back button in the header, showing the full title, full description, absolute timestamps, and comments/history as tabs or collapsible sections _(implements BDD-3)_

- **GIVEN** the user is on the mobile task detail view
  **WHEN** the user taps the status control and picks a new status from the touch-friendly selector
  **THEN** the detail view updates in place to show the new status _(implements BDD-4)_

- **GIVEN** a task has a 255-character title and a 2000-character description
  **WHEN** the user opens the task detail on mobile
  **THEN** the full title and full description are shown and wrap without horizontal overflow _(implements BDD-11)_

- **GIVEN** history and comments data for a task on mobile
  **WHEN** the detail view renders those sections
  **THEN** each entry is laid out as vertically stacked, clearly labeled fields rather than multi-column table rows _(implements BDD-15)_

- **GIVEN** the user is on the mobile full-screen task detail view
  **WHEN** the user triggers the OS/browser back gesture
  **THEN** the system returns to the task list with prior scroll position preserved, identical to tapping the in-header back button, and does not exit the app _(implements BDD-21)_

- **GIVEN** the user taps a task card or the status control on mobile
  **WHEN** the first tap is registered
  **THEN** the control is disabled until the resulting navigation or network response completes so a rapid second tap produces no additional action _(implements BDD-20)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
