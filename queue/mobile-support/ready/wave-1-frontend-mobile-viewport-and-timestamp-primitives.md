---
task-id: mobile-viewport-and-timestamp-primitives
status: ready
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: mobile-support
type: feature
estimated-lines: 220
scenario-refs:
  - BDD-8
  - BDD-10
  - BDD-12
---

## Description

Introduce a shared `useIsMobile` hook that returns true when viewport width is &lt; 768px (listening to matchMedia changes for rotation/resize) and a `RelativeTimestamp` component that renders a relative label on mobile and, on long-press (~500ms), reveals the absolute timestamp in a small popover. Timestamp element scopes `user-select: none` and `-webkit-touch-callout: none` to itself so the OS copy/share callout does not appear; tap falls through to the parent card. Desktop rendering of the timestamp component is unchanged (hover-tooltip or inline text — whichever matches current desktop).

## Why

Every Wave 2 mobile surface needs a consistent way to detect the mobile breakpoint (R1, BDD-8, BDD-10) and to render list-view timestamps with long-press-to-reveal absolute time (R14, BDD-12, E1). Building these once prevents divergent breakpoint logic and duplicated long-press handlers across task list, history, and analytics surfaces.

## Files to Modify

- `src/hooks/useIsMobile.js` (new) — matchMedia-based hook, SSR-safe, returns boolean; updates on change
- `src/components/RelativeTimestamp.jsx` (new) — Renders relative label; on mobile adds long-press handler that shows an absolute-timestamp popover; suppresses native callout on the element only
- `src/components/RelativeTimestamp.module.css` (new) — Scope user-select:none and -webkit-touch-callout:none to the timestamp element

## Reference Patterns

- `src/App.jsx` — framework conventions — component style, CSS/styling approach, existing timestamp rendering to mirror on desktop
- `src/theme.js` — existing theme/token source to align any new styles with

## Test Plan

- `tests/useIsMobile.test.jsx` (new) covers BDD-8, BDD-10
- `tests/RelativeTimestamp.test.jsx` (new) covers BDD-12

## Out of Scope

- src/AnalyticsPage.jsx — Wave 2 analytics task owns mobile analytics changes
- contracts/tasks-api.json — R17 forbids contract changes
- Any batch-select UI — deferred by Round 1 A1, not in this feature

## Verification

- npm test -- tests/useIsMobile.test.jsx tests/RelativeTimestamp.test.jsx passes
- npm run build passes
- npm test passes (full suite)

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** a user opens the app at viewport width ≥ 768px
  **WHEN** any screen renders and the viewport hook is consulted
  **THEN** the hook reports non-mobile and the existing desktop layout is used unchanged _(implements BDD-8)_

- **GIVEN** a user rotates the phone and the viewport width changes
  **WHEN** the new width crosses the 768px boundary
  **THEN** the viewport hook re-reports the updated mobile/desktop state so consumers can reflow _(implements BDD-10)_

- **GIVEN** a user is on a mobile list view showing a relative timestamp
  **WHEN** the user long-presses the relative timestamp
  **THEN** a small popover reveals the absolute timestamp and the browser's native text-selection/copy-share menu does not appear _(implements BDD-12)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
