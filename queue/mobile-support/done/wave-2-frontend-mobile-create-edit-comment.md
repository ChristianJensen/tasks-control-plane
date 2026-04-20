---
task-id: mobile-create-edit-comment
status: done
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
  - BDD-5
  - BDD-6
  - BDD-14
  - BDD-20
  - BDD-22
claimed-by: cloud-Christians-MacBook-Air-58257
claimed-at: 2026-04-20T06:10:59Z
claimed-on: Christians-MacBook-Air
cost-usd: 3.7225572
input-tokens: 76
output-tokens: 50752
duration-ms: 1631899
auth-mode: max-oauth
billed: false
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/111
pr-number: 111
---

## Description

On mobile, present the existing create-task, edit-task, and add-comment flows as full-screen modals (FullScreenModal primitive) with a sticky header containing Cancel and Save actions. Touch-sized inputs, no hover-only affordances. The sticky header remains reachable when the on-screen keyboard opens, and the focused input is scrolled into view (not hidden behind the keyboard). Save uses the tap-once helper so rapid second taps do not create duplicate tasks/comments. The FAB on the list opens the create modal; on the detail view, "Add comment" and "Edit" open their respective modals. Each modal registers as a browser history entry so the OS/browser back gesture behaves identically to tapping Cancel (inheriting any unsaved-changes handling desktop already does). On Save success, the modal closes and the new task/comment is visible on the underlying surface. Desktop forms remain unchanged.

## Why

Implements R7, R8 (FAB-opens-create), BDD-5 (add comment), BDD-6 (FAB create), BDD-14 (keyboard + sticky header), BDD-20 (rapid-tap on Save/FAB), and BDD-22 (back gesture = Cancel). Grouping the three modal flows into one task is efficient because they all reuse the same FullScreenModal primitive, share sticky-header/keyboard behavior, and share tap-once wiring on Save.

## Files to Modify

- `src/App.jsx` (edit) — On mobile, route create-task, edit-task, and add-comment triggers to open MobileCreateTaskModal / MobileEditTaskModal / MobileAddCommentModal; wire FAB on list to create; leave desktop form flows unchanged
- `src/components/mobile/MobileCreateTaskModal.jsx` (new) — FullScreenModal wrapping the create-task form with sticky Cancel/Save header and tap-once Save
- `src/components/mobile/MobileEditTaskModal.jsx` (new) — FullScreenModal wrapping the edit-task form with sticky Cancel/Save header and tap-once Save
- `src/components/mobile/MobileAddCommentModal.jsx` (new) — FullScreenModal wrapping the comment form with sticky Cancel/Save header and tap-once Save
- `src/components/mobile/mobileForms.module.css` (new) — Touch-sized inputs, sticky-header layout, keyboard-safe body scrolling

## Reference Patterns

- `src/App.jsx` — existing desktop create/edit/comment form handlers and unsaved-changes logic — reuse, DO NOT modify desktop branch
- `src/components/mobile/FullScreenModal.jsx` — Wave 1 primitive — consume, DO NOT modify
- `src/components/mobile/FloatingActionButton.jsx` — Wave 1 primitive — consume, DO NOT modify
- `src/hooks/useTapOnce.js` — Wave 1 helper — consume, DO NOT modify

## Test Plan

- `tests/mobile-create-edit-comment.test.jsx` (new) covers BDD-5, BDD-6, BDD-14, BDD-20, BDD-22

## Out of Scope

- Desktop form layouts — unchanged (R1, R18)
- Mobile task detail rendering — owned by mobile-task-detail task
- src/AnalyticsPage.jsx — owned by mobile-analytics task
- Server-side validation changes — R17 forbids contract/backend changes
- Mobile-specific error/retry/input preservation on failure — E3 explicitly inherits desktop behavior

## Verification

- npm test -- tests/mobile-create-edit-comment.test.jsx passes
- npm test passes (full suite)
- npm run build passes

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** the user is on the mobile task detail view
  **WHEN** the user taps 'Add comment', types text in the full-screen modal that opens, and taps 'Save' in the sticky header
  **THEN** the modal closes and the new comment appears in the detail view _(implements BDD-5)_

- **GIVEN** the user is on the mobile task list
  **WHEN** the user taps the floating action button, fills in a title in the full-screen create modal, and taps 'Save' in the sticky header
  **THEN** the modal closes and the new task appears in the list _(implements BDD-6)_

- **GIVEN** a user has a full-screen create/edit/comment modal open on mobile
  **WHEN** the on-screen keyboard opens while typing
  **THEN** the sticky Save/Cancel header remains reachable and the focused input is not hidden behind the keyboard _(implements BDD-14)_

- **GIVEN** the user taps the FAB or Save in a full-screen modal on mobile
  **WHEN** the first tap is registered
  **THEN** the control is disabled until the resulting modal transition or network response completes so a rapid second tap produces no additional action _(implements BDD-20)_

- **GIVEN** the user has a full-screen create/edit/comment modal open on mobile
  **WHEN** the user triggers the OS/browser back gesture
  **THEN** the system behaves identically to tapping Cancel (including any unsaved-changes handling inherited from desktop) and does not exit the app _(implements BDD-22)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
