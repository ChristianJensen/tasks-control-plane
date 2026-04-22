---
task-id: confetti-mobile-integration
status: in-progress
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: confetti-on-the-last-task-complete
type: feature
estimated-lines: 140
depends-on:
  - confetti-shared-helpers
scenario-refs:
  - BDD-3
  - BDD-15
claimed-by: cloud-Christians-MacBook-Air-2054
claimed-at: 2026-04-22T13:59:30Z
claimed-on: Christians-MacBook-Air
---

## Description

Wire the confetti celebration into the mobile task detail surface (`MobileTaskDetail.jsx`). Mirror the desktop semantics exactly: in the status-change PATCH success handler, compute prev/next open count over the full unfiltered active-list task set at response-apply time, capture activeListId at dispatch, and invoke `fireConfetti()` only when the response resolves the task to `status === 'done'` (body authoritative, 204 falls back to request payload), `shouldCelebrate` returns true, and the originating list is still active. The burst must continue playing over the list screen if the user navigates back mid-burst — do NOT cancel or unmount the canvas on route/screen change (canvas-confetti attaches to document.body, per UX1).

## Why

Delivers R6 parity on the mobile surface (BDD-3) and handles the mobile-specific navigation-during-burst case (UX1, BDD-15). Same shared helpers as desktop ensure identical behavior and a single place to tweak defaults.

## Files to Modify

- `src/components/mobile/MobileTaskDetail.jsx` (edit) — in the status-change PATCH success handler, capture activeListId at dispatch, compute prev/next open counts at response-apply time, call fireConfetti() when shouldCelebrate returns true AND originating list is still active AND resolved status === 'done'; do NOT cancel confetti on unmount
- `tests/mobile/MobileTaskDetail.confetti.test.jsx` (new) — integration tests mocking fetch + canvas-confetti; cover BDD-3 and BDD-15

## Reference Patterns

- `src/components/mobile/MobileTaskDetail.jsx` — locate the existing status-change PATCH handler on the mobile surface; hook into success path without altering request semantics
- `src/App.jsx` — framework conventions — mirror the desktop integration's snapshot-and-guard pattern from confetti-desktop-integration (read, do not modify in this task)
- `src/lib/confetti.js` — consume shouldCelebrate and fireConfetti produced by confetti-shared-helpers (Wave 1) — DO NOT modify

## Test Plan

- `tests/mobile/MobileTaskDetail.confetti.test.jsx` (new) covers BDD-3, BDD-15

## Out of Scope

- src/App.jsx — desktop surface is owned by confetti-desktop-integration
- src/lib/confetti.js — owned by confetti-shared-helpers (Wave 1); consume only
- Other files under src/components/mobile/ (FullScreenModal, BottomSheet, FAB, OverflowMenu) — no changes needed for this feature
- contracts/tasks-api.json — no contract change
- Adding aria-live, toast, sound, modal, or dismiss UI — forbidden by R10 and C2
- Per-surface origin override or DOM-rect anchoring — UX1 mandates identical origin to desktop

## Verification

- npm test passes (new tests in tests/mobile/MobileTaskDetail.confetti.test.jsx green; all existing mobile tests still green)
- npm run build passes
- Manual on a mobile viewport: with one open task, completing it in MobileTaskDetail triggers a ~2s burst identical to desktop
- Manual: trigger the burst and immediately navigate back — particles continue falling over the list screen without error

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** the user has exactly one open task on the mobile task detail surface
  **WHEN** they mark it done and the PATCH returns 2xx
  **THEN** a confetti burst renders identically to the desktop surface (particleCount 100, spread 70, origin y 0.8, ~2s) _(implements BDD-3)_

- **GIVEN** a confetti burst is currently playing on the mobile task detail surface
  **WHEN** the user navigates back to the list before the ~2s animation completes
  **THEN** the burst continues playing over the new screen without crashing or leaking — no cancel on unmount _(implements BDD-15)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
