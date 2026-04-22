---
task-id: confetti-desktop-integration
status: done
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: confetti-on-the-last-task-complete
type: feature
estimated-lines: 320
depends-on:
  - confetti-shared-helpers
scenario-refs:
  - BDD-1
  - BDD-4
  - BDD-6
  - BDD-8
  - BDD-9
  - BDD-10
  - BDD-11
  - BDD-12
  - BDD-13
  - BDD-14
claimed-by: cloud-Christians-MacBook-Air-94915
claimed-at: 2026-04-22T10:07:54Z
claimed-on: Christians-MacBook-Air
cost-usd: 3.6303702000000007
input-tokens: 83
output-tokens: 58960
duration-ms: 5917798
auth-mode: max-oauth
billed: false
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/122
pr-number: 122
---

## Description

Wire the confetti celebration into the desktop surface (`App.jsx`). In the status-change PATCH success handler, compute `prevOpenCount` and `nextOpenCount` at response-apply time over the full unfiltered active-list task set (filters do not affect the trigger; list scope is the active list), capture `activeListId` at dispatch time, and invoke `fireConfetti()` only if (a) the PATCH returned 2xx, (b) the authoritative resulting status is `done` (response body wins; fall back to request payload when body is empty/204), (c) `shouldCelebrate(prev, next, 'status-change-to-done')` returns true, and (d) the originating `activeListId` still matches the current active list. The canvas must be non-blocking (canvas-confetti's default canvas is `pointer-events: none` and appended to document.body — verify no wrapper adds an interaction-blocking overlay). Deletion, batch delete, and non-status PATCHes never invoke the helper. No `useEffect` watching open-count — the call is imperative in the success callback.

## Why

Delivers the user-visible celebration on the desktop surface (R6) and implements nearly all edge cases: filtered views (R2, BDD-4), failed PATCH (BDD-6), deletion (BDD-8), flip-flop re-fire (R12, BDD-9), non-blocking canvas (R10, BDD-10), stale-after-list-switch (E1, BDD-11), server-normalized status (A6, BDD-12), rapid concurrent PATCHes (E3, BDD-13), and 204 No Content fallback (BDD-14).

## Files to Modify

- `src/App.jsx` (edit) — in the status-change PATCH success handler, snapshot activeListId at dispatch, compute prev/next open count over unfiltered active-list tasks at response-apply time, call fireConfetti() when shouldCelebrate returns true AND activeListId still matches AND authoritative resolved status === 'done'
- `tests/App.confetti.test.jsx` (new) — integration tests mocking fetch + canvas-confetti; cover BDD-1, 4, 6, 8, 9, 10, 11, 12, 13, 14 on the desktop surface

## Reference Patterns

- `src/App.jsx` — locate the existing status-change PATCH handler and state-update shape — hook into its success path without changing request semantics
- `src/lib/confetti.js` — consume shouldCelebrate and fireConfetti produced by confetti-shared-helpers (Wave 1) — DO NOT modify
- `tests/` — existing Vitest + React Testing Library patterns for App.jsx tests, including fetch mocking

## Test Plan

- `tests/App.confetti.test.jsx` (new) covers BDD-1, BDD-4, BDD-6, BDD-8, BDD-9, BDD-10, BDD-11, BDD-12, BDD-13, BDD-14

## Out of Scope

- src/components/mobile/MobileTaskDetail.jsx — mobile surface is owned by confetti-mobile-integration
- src/lib/confetti.js — owned by confetti-shared-helpers (Wave 1); consume only
- contracts/tasks-api.json — no contract change
- Any backend file under api/ — frontend-only feature (C5)
- Adding aria-live, toast, sound, modal, or dismiss UI — forbidden by R10 and C2
- Focus management after the last task completes — explicitly out of scope per UX2

## Verification

- npm test passes (new tests in tests/App.confetti.test.jsx green; all existing App.jsx tests still green)
- npm run build passes
- Manual: with two open tasks, completing one → no confetti; completing the second → confetti burst for ~2s that does not block clicks on underlying cards
- Manual: with OS-level reduced-motion enabled, completing the last open task — PATCH succeeds, no confetti renders
- Manual: delete the last open task — no confetti

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** the user has exactly one open task on the desktop surface and prefers-reduced-motion is not set
  **WHEN** they mark that task as done and the PATCH returns 2xx
  **THEN** a single canvas-confetti burst renders (particleCount 100, spread 70, origin y 0.8) and auto-clears _(implements BDD-1)_

- **GIVEN** a status filter is active showing only todo; the unfiltered set has one todo task and one in-progress task
  **WHEN** the user marks the todo task as done
  **THEN** no confetti renders because one in-progress open task remains in the unfiltered set _(implements BDD-4)_

- **GIVEN** the user has exactly one open task
  **WHEN** they mark it done but the PATCH returns a non-2xx status
  **THEN** no confetti renders _(implements BDD-6)_

- **GIVEN** the user has exactly one open task
  **WHEN** they delete it instead of completing it
  **THEN** no confetti renders _(implements BDD-8)_

- **GIVEN** the user marked the last task done and confetti fired
  **WHEN** they flip it back to todo and mark it done again with a successful PATCH
  **THEN** confetti fires a second time _(implements BDD-9)_

- **GIVEN** a confetti burst is currently playing
  **WHEN** the user clicks a task card underneath the canvas
  **THEN** the click reaches the card normally (canvas does not intercept pointer events) _(implements BDD-10)_

- **GIVEN** the user is viewing List A with exactly one open task
  **WHEN** they mark it done, switch to List B (five open tasks) before the response arrives, then the PATCH returns 2xx
  **THEN** no confetti renders because the originating list is no longer the active view _(implements BDD-11)_

- **GIVEN** the user has exactly one open task
  **WHEN** they PATCH status:'done' and the server returns 2xx with a body that normalizes status to 'in-progress'
  **THEN** no confetti renders — the server response is authoritative _(implements BDD-12)_

- **GIVEN** the user has exactly two open tasks
  **WHEN** they rapidly fire two status-change PATCHes (one per task) and both return 2xx in either order
  **THEN** confetti fires exactly once, on whichever response applies the 1→0 transition _(implements BDD-13)_

- **GIVEN** the user has exactly one open task
  **WHEN** they mark it done and the server returns 204 No Content (empty body)
  **THEN** confetti fires, using the request payload's status:'done' as the authoritative fallback _(implements BDD-14)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
