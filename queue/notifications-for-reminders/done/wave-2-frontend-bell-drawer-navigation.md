---
task-id: bell-drawer-navigation
status: done
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: notifications-for-reminders
type: feature
estimated-lines: 380
depends-on:
  - due-dates-store
  - header-bell-badge
scenario-refs:
  - BDD-6
  - BDD-7
  - BDD-8
  - BDD-9
  - BDD-16
claimed-by: cloud-Christians-MacBook-Air-28757
claimed-at: 2026-04-21T19:51:02Z
claimed-on: Christians-MacBook-Air
cost-usd: 3.846795399999999
input-tokens: 78
output-tokens: 59895
duration-ms: 2155091
auth-mode: max-oauth
billed: false
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/120
pr-number: 120
---

## Description

Add a right-side `ReminderDrawer` component (mirroring the existing `HelpDrawer` pattern at App.jsx:107: 400px panel, backdrop, click-outside closes, Escape closes and restores focus to the bell trigger). Wire the bell's onClick/Enter/Space to toggle it. Populate the drawer with the same visible set the badge derives, ordered most overdue first, then due today, tiebroken by task creation order; cap at 50 items with a "+N more" footer when truncated. Each row shows title, "Due today" / "Overdue by N days" label, and the current status pill. Arrow Up/Down moves focus between rows; Enter activates. On activation: close the drawer, find the task card DOM node, call `scrollIntoView({behavior:'smooth', block:'center'})`, and move DOM focus to the card (use a ref-callback registry keyed by task ID, or whatever `focusedTaskId`/`focusRequestId` mechanism already exists on `SortableTaskItem` \u2014 the executing agent must confirm the exact prop names). If the target card is not currently rendered (hidden by an active filter), close the drawer and show an inline "This task is hidden by the current filter" message with a "Clear filter" button that clears the filter, then scrolls and focuses. No focus trap (menu semantics, not modal). Live re-derivation: if the user marks a task done from inside the drawer, the drawer updates live and the row disappears.

## Why

Delivers the navigate-to-what-needs-attention flow: the central user value of the feature. Independent of the badge-visibility slice (the bell component exposes a toggle hook) and of the form/card slices.

## Files to Modify

- `src/components/ReminderDrawer.jsx` (new) — Drawer component modelled on HelpDrawer (App.jsx:107); ordering, 50-cap + footer, keyboard nav, click-through handler
- `src/App.jsx` (edit) — Mount <ReminderDrawer /> near HelpDrawer at ~3167; wire open/close state; pass down a click-activation callback that knows about the current filter state and can clear it; register task-card refs on SortableTaskItem so drawer can scroll/focus them

## Reference Patterns

- `src/App.jsx:107-180` — HelpDrawer — right-side 400px panel, backdrop, Escape handler, focus return to trigger — exact pattern to mirror
- `src/App.jsx:3160-3200` — Where HelpDrawer is mounted (App.jsx:3167) — mount ReminderDrawer alongside it
- `src/App.jsx:598-750` — SortableTaskItem — existing focus ring styling to reuse and where a ref/focus hook must be wired; executing agent should locate the actual focusedTaskId / focusRequestId plumbing referenced in the spec, or establish a ref-callback registry if no such plumbing exists yet
- `tests/App.test.jsx:2446-2600` — HelpDrawer tests — conventions for drawer open/close/keyboard assertions with vitest
- `src/components/ReminderBell.jsx` — Bell component from header-bell-badge task — consume its toggle prop; DO NOT modify

## Test Plan

- `tests/reminder-drawer.test.jsx` (new) covers BDD-6, BDD-7, BDD-8, BDD-9, BDD-16

## Out of Scope

- Bell icon + badge rendering (owned by header-bell-badge)
- src/App.jsx DueDateDisplay internals at lines 542-597
- Mobile header (C6 — desktop only)
- No new runtime dependencies (C5) — do NOT add floating-ui, popover libraries, or focus-trap libraries
- contracts/tasks-api.json must remain unchanged (C2)
- Cross-tab live sync (deferred per A4)

## Verification

- npm test -- tests/reminder-drawer.test.jsx passes
- npm test passes overall
- npm run build passes
- Manual: open drawer, Arrow keys navigate, Enter scrolls + focuses correct card, Escape returns focus to bell, filter-hidden case shows inline message + Clear filter works
- Diff of frontend/package.json shows no new dependencies (C5)

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** the bell icon is visible
  **WHEN** the user clicks it or presses Enter/Space on it
  **THEN** a right-side drawer opens listing the matching tasks, ordered most overdue first then due today with task creation order as tiebreaker, capped at 50 items with a '+N more' footer when truncated, each item showing title, a 'Due today' or 'Overdue by N days' label, and the status pill _(implements BDD-6)_

- **GIVEN** the bell drawer is open
  **WHEN** the user presses Arrow Down or Arrow Up
  **THEN** focus moves between drawer items in order _(implements BDD-7)_

- **GIVEN** the bell drawer is open and the target task is currently rendered
  **WHEN** the user activates an item by click or Enter
  **THEN** the drawer closes, the main list scrolls the corresponding task into view, and DOM focus moves to that task card so the existing focus ring marks it _(implements BDD-8)_

- **GIVEN** the bell drawer is open
  **WHEN** the user presses Escape
  **THEN** the drawer closes and focus returns to the bell trigger button _(implements BDD-9)_

- **GIVEN** the bell drawer is open and the user activates an item whose target task is hidden by an active filter
  **WHEN** the activation fires
  **THEN** the drawer closes and an inline 'This task is hidden by the current filter' message appears with a 'Clear filter' action that clears the filter, scrolls the task into view, and moves focus to its card _(implements BDD-16)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant

## Implementation Notes

The spec references `focusedTaskId` + `focusRequestId` as existing plumbing, but a grep for these identifiers returned no matches. The executing agent must either (a) locate the actual prop names used by SortableTaskItem for programmatic focus, or (b) introduce a minimal ref-callback registry keyed by task ID so the drawer can `refs.get(taskId)?.focus()`. Keep the addition local to SortableTaskItem + the drawer; don't introduce a global state store. The "hidden by active filter" check is: look up the ref registry \u2014 if no node is registered for that task ID, the task is not rendered.
