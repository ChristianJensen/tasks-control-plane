---
task-id: header-bell-badge
status: done
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: notifications-for-reminders
type: feature
estimated-lines: 260
depends-on:
  - due-dates-store
scenario-refs:
  - BDD-5
  - BDD-10
  - BDD-11
  - BDD-12
  - BDD-18
  - BDD-19
claimed-by: cloud-Christians-MacBook-Air-82923
claimed-at: 2026-04-20T17:02:26Z
claimed-on: Christians-MacBook-Air
cost-usd: 1.0576983500000001
input-tokens: 39
output-tokens: 18941
duration-ms: 403355
auth-mode: max-oauth
billed: false
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/117
pr-number: 117
---

## Description

Add a bell icon + numeric badge to the desktop app header (alongside existing Help/Contact buttons). Derive the visible set: non-terminal-status tasks (exclude `done`; implement against a terminal-status set, not the string literal, per A3) whose effective `dueDate <= today` in the user's local timezone via `new Date()` at render time. If the set is empty, render nothing (no bell, no zero badge). Otherwise render the bell with a badge showing the count, visually capped at "99+" (true count used for ordering by the drawer task). Badge carries an accessible label such as "3 tasks due or overdue" via `aria-label`. Orphaned `localStorage` entries for missing task IDs are ignored. Badge re-derives live within the tab on any mutation to the task list or due-dates map (no timers). Mobile header is not modified.

## Why

Delivers the at-a-glance signal: users immediately know when something needs attention. The bell is the entry point to the drawer but the badge-visibility + count logic is a standalone user story and can be shipped and tested independently of the drawer body.

## Files to Modify

- `src/components/ReminderBell.jsx` (new) — Bell icon + badge component; reads tasks + useDueDates, derives visible set, renders null when count is 0
- `src/App.jsx:3160-3200` (edit) — Mount <ReminderBell /> in the desktop header alongside the existing Help/Contact trigger buttons; do not modify mobile header

## Reference Patterns

- `src/App.jsx:107-180` — HelpDrawer trigger + button pattern in the header — visual convention for header affordances
- `src/App.jsx:3160-3200` — Desktop header wiring location where HelpDrawer is mounted (App.jsx:3167) — where ReminderBell should be placed
- `src/hooks/useDueDates.js` — Store hook (from due-dates-store task) — DO NOT modify
- `src/components/mobile` — Mobile components directory — confirms mobile header is separate and must NOT be touched (C6)

## Test Plan

- `tests/reminder-bell.test.jsx` (new) covers BDD-5, BDD-10, BDD-11, BDD-12, BDD-18, BDD-19

## Out of Scope

- Drawer body / keyboard nav / item click-through (owned by bell-drawer-navigation)
- Mobile header — must remain unchanged per C6
- src/App.jsx DueDateDisplay internals at lines 542-597
- Cross-tab storage event listener (deferred per A4)
- Timer-based midnight recompute (deferred per R12/BDD-19)
- Active orphan cleanup (deferred per A1 — read-time filter is sufficient)

## Verification

- npm test -- tests/reminder-bell.test.jsx passes
- npm test passes overall
- npm run build passes
- Manual: seed tasks with various statuses and due dates, verify bell visibility, count, '99+' cap, and aria-label

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** a user has at least one non-terminal-status task with effective dueDate <= today
  **WHEN** the app loads on desktop
  **THEN** the bell icon is rendered in the header with a badge showing the count (capped visually at '99+') and an accessible label such as '3 tasks due or overdue' _(implements BDD-5)_

- **GIVEN** a task is counted in the badge
  **WHEN** the user marks it done from the main list
  **THEN** the badge count decreases by one immediately in the current tab; if it reaches zero, the bell hides _(implements BDD-10)_

- **GIVEN** no non-terminal-status tasks have effective dueDate <= today
  **WHEN** the app loads
  **THEN** the bell icon is not rendered at all _(implements BDD-11)_

- **GIVEN** a task whose status is terminal (e.g. done) and whose due date is today or earlier
  **WHEN** the app loads
  **THEN** it is not included in the badge count, regardless of its due date _(implements BDD-12)_

- **GIVEN** two tabs are open on the same browser and tab A adds a due date
  **WHEN** tab B reloads
  **THEN** tab B's badge reflects the new due date; without a reload, tab B's badge remains stale _(implements BDD-18)_

- **GIVEN** the app is open across midnight or the device clock changes while the app stays open
  **WHEN** no page load or mutation occurs
  **THEN** the badge continues to reflect today as it was at the last recompute and updates on next page load or intra-tab mutation, not on a timer _(implements BDD-19)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant

## Implementation Notes

Bell component should accept a click handler prop so bell-drawer-navigation can wire open/close without this task owning the drawer. Terminal-status check: export a constant `TERMINAL_STATUSES = new Set(['done'])` so future statuses (archived/cancelled) slot in without code changes to the predicate.
