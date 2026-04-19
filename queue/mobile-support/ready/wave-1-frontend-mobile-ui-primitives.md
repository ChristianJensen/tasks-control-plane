---
task-id: mobile-ui-primitives
status: ready
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: mobile-support
type: feature
estimated-lines: 380
scenario-refs:
  - BDD-14
  - BDD-18
  - BDD-19
  - BDD-20
  - BDD-22
---

## Description

Build the shared mobile UI primitives specified by UX2: (a) `BottomSheet` — slide-up sheet with tap-outside-to-dismiss, ≥44×44px controls, respects `env(safe-area-inset-bottom)`; (b) `FullScreenModal` — covers viewport with a sticky header slot for Cancel/Save actions that remains reachable when the on-screen keyboard opens (inputs scroll into view, header stays fixed), and registers itself as a browser history entry so OS/browser back gesture triggers the Cancel path; (c) `FloatingActionButton` — fixed bottom-right, respects safe-area-inset-bottom, hidden when a FullScreenModal is open or on-screen keyboard is visible; (d) `OverflowMenu` — "⋮" trigger opening a touch-friendly menu with ≥44×44px items; (e) a `useTapOnce` helper/hook that disables a control from first tap until a caller-signalled completion (navigation/network/transition) to prevent rapid duplicate taps. All primitives render null/no-op on desktop where appropriate so consumers can call them unconditionally when wrapped by `useIsMobile`.

## Why

R18 requires every surface to adopt these mobile patterns and UX2 mandates that each primitive is built once and reused (bottom sheet shared by Filters and status picker; full-screen modal shared by create/edit/comment; overflow menu shared by analytics export and any row actions). Covers safe-area (A4, BDD-18, BDD-19), keyboard-safe sticky header (BDD-14), rapid-tap disable (E2, BDD-20), and back-gesture-as-cancel for modals (UX4, BDD-22). Without this task, every Wave 2 surface would hand-roll divergent versions.

## Files to Modify

- `src/components/mobile/BottomSheet.jsx` (new) — Slide-up sheet with backdrop, tap-outside-to-dismiss, safe-area padding
- `src/components/mobile/FullScreenModal.jsx` (new) — Full-viewport modal with sticky header slot; pushes a history entry and maps popstate to onCancel
- `src/components/mobile/FloatingActionButton.jsx` (new) — Fixed bottom-right FAB; hides when modal open or keyboard visible; respects safe-area-inset-bottom
- `src/components/mobile/OverflowMenu.jsx` (new) — '⋮' trigger with touch-friendly menu items ≥44×44px
- `src/hooks/useTapOnce.js` (new) — Returns [disabled, wrap(handler)] where wrap disables until caller resolves a completion promise/signal
- `src/components/mobile/mobile.module.css` (new) — Shared mobile primitive styles, safe-area env() usage, 44×44px minimums

## Reference Patterns

- `src/App.jsx` — framework conventions — component composition style and state patterns used across the app
- `src/theme.js` — existing tokens/spacing to reuse where applicable
- `tests/ui-interactions-consistent-design.test.jsx` — existing interaction-test shape — DO NOT modify

## Test Plan

- `tests/mobile-primitives.test.jsx` (new) covers BDD-14, BDD-18, BDD-19, BDD-20, BDD-22

## Out of Scope

- src/App.jsx — Wave 2 surfaces consume these primitives; this task does not wire them into screens
- src/AnalyticsPage.jsx — Wave 2 analytics task owns overflow-menu wiring
- contracts/tasks-api.json — R17 forbids contract changes
- Any batch-select bottom action bar — deferred by Round 1 A1

## Verification

- npm test -- tests/mobile-primitives.test.jsx passes
- npm run build passes
- npm test passes (full suite)

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** a user has a full-screen create or edit modal open on mobile
  **WHEN** the on-screen keyboard opens while an input is focused
  **THEN** the sticky header Save/Cancel actions remain reachable and the focused input is not hidden behind the keyboard _(implements BDD-14)_

- **GIVEN** a user is on the mobile task list on a device with a bottom safe-area inset
  **WHEN** the list renders
  **THEN** the FAB is positioned above the safe-area inset and the last card's controls are not occluded _(implements BDD-18)_

- **GIVEN** a user has a full-screen modal open or the on-screen keyboard visible on mobile
  **WHEN** the view renders
  **THEN** the FAB is hidden or repositioned so it does not overlap modal content or the keyboard _(implements BDD-19)_

- **GIVEN** a user taps a primitive control wired with the tap-once helper on mobile
  **WHEN** the first tap is registered
  **THEN** the control is immediately disabled until the caller signals completion, so a rapid second tap produces no additional action _(implements BDD-20)_

- **GIVEN** a user has a full-screen modal open on mobile
  **WHEN** the user triggers the OS/browser back gesture
  **THEN** the modal closes via its Cancel path and the app is not exited _(implements BDD-22)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
