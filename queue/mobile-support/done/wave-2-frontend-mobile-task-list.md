---
task-id: mobile-task-list
status: done
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: mobile-support
type: feature
estimated-lines: 360
depends-on:
  - mobile-viewport-and-timestamp-primitives
  - mobile-ui-primitives
scenario-refs:
  - BDD-1
  - BDD-11
  - BDD-13
  - BDD-16
  - BDD-9
claimed-by: cloud-Christians-MacBook-Air-69244
claimed-at: 2026-04-20T07:07:22Z
claimed-on: Christians-MacBook-Air
cost-usd: 2.76662505
input-tokens: 77
output-tokens: 43413
duration-ms: 1033920
auth-mode: max-oauth
billed: false
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/114
pr-number: 114
---

## Description

At viewport &lt; 768px, render the task list as a single-column stack of cards. Each card shows title (truncated to 2 CSS lines with ellipsis), status, category, and a relative timestamp (via RelativeTimestamp). Descriptions are NOT shown in the list. Place a FAB in the bottom-right that opens the existing create-task flow (the modalized flow is built in the mobile-create-edit-comment task; here the FAB handler is wired to the existing create-task trigger so a minimum viable create-from-FAB works with whatever modal exists). Add bottom padding to the list equal to FAB height + safe-area inset so the last card's controls are never occluded. Any per-row overflow/action controls on a card are placed in the top-right, never in the bottom-right quadrant (UX3). Handle two empty states: zero tasks → centered empty-state message with no in-body CTA (FAB is the create affordance); filtered-empty is handled in the filters task. At ≥ 768px the existing desktop list renders unchanged.

## Why

Implements the core mobile list surface (R4, R8, BDD-1, BDD-6 entry point, BDD-11 truncation, BDD-16 empty state, UX3 row-action placement) and preserves desktop behavior (R1, BDD-8). The list is the user's first screen and anchors FAB + safe-area behavior on the primary surface.

## Files to Modify

- `src/App.jsx` (edit) — Branch on useIsMobile to render the mobile task-list view; add mobile card markup, FAB wiring, and zero-task empty state; leave desktop code path unchanged
- `src/components/mobile/MobileTaskList.jsx` (new) — Single-column stacked card list with truncation, relative timestamps, top-right overflow placement, FAB, zero-state message
- `src/components/mobile/MobileTaskList.module.css` (new) — 2-line clamp, card spacing, bottom padding = FAB + safe-area, 44×44px minimums

## Reference Patterns

- `src/App.jsx` — existing desktop task list rendering and data fetching — mirror data source, DO NOT modify desktop branch
- `src/components/mobile/FloatingActionButton.jsx` — FAB primitive from Wave 1 — consume, DO NOT modify
- `src/components/RelativeTimestamp.jsx` — timestamp primitive from Wave 1 — consume, DO NOT modify
- `src/hooks/useIsMobile.js` — viewport hook from Wave 1 — consume, DO NOT modify

## Test Plan

- `tests/mobile-task-list.test.jsx` (new) covers BDD-1, BDD-9, BDD-11, BDD-13, BDD-16

## Out of Scope

- src/AnalyticsPage.jsx — owned by mobile-analytics task
- Filters bottom-sheet markup — owned by mobile-filters task
- Full-screen task detail view — owned by mobile-task-detail task
- Full-screen create/edit modal internals — owned by mobile-create-edit-comment task
- contracts/tasks-api.json — R17 forbids contract changes
- Batch-select / long-press multi-select — deferred by Round 1 A1

## Verification

- npm test -- tests/mobile-task-list.test.jsx passes
- npm test passes (full suite, including existing desktop tests unchanged)
- npm run build passes

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** a user opens the app on a phone browser with viewport width < 768px
  **WHEN** the task list loads
  **THEN** the system renders a single-column stack of task cards, each showing the title truncated to 2 lines, status, category, and a relative timestamp, with no description shown _(implements BDD-1)_

- **GIVEN** a task has a 255-character title and a 2000-character description
  **WHEN** the task appears on the mobile list
  **THEN** the title is truncated to 2 lines with ellipsis and the description is not shown _(implements BDD-11)_

- **GIVEN** a user is on any mobile list card with row-level actions
  **WHEN** the card renders
  **THEN** all row actions are visible as icon buttons or collapsed behind a '⋮' overflow button and are never positioned in the card's bottom-right quadrant where they would compete with the FAB _(implements BDD-13)_

- **GIVEN** the user has zero tasks on the mobile task list
  **WHEN** the list renders
  **THEN** the system shows a centered empty-state message with no separate in-body create CTA and the FAB remains visible as the create affordance _(implements BDD-16)_

- **GIVEN** a user is on a viewport width between 360px and 767px
  **WHEN** the task list renders
  **THEN** the mobile layout displays without horizontal scroll on primary content and without clipped controls _(implements BDD-9)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
