---
task-id: card-due-date-display
status: in-progress
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: notifications-for-reminders
type: feature
estimated-lines: 140
depends-on:
  - due-dates-store
scenario-refs:
  - BDD-3
  - BDD-4
  - BDD-13
  - BDD-14
claimed-by: cloud-Christians-MacBook-Air-88687
claimed-at: 2026-04-20T17:09:31Z
claimed-on: Christians-MacBook-Air
---

## Description

Update the call site of the existing `DueDateDisplay` in `SortableTaskItem` (App.jsx ~747) so it renders using the effective due date: `task.dueDate ?? localDueDateMap[task.id]`. The existing component already handles fuchsia "today" and rose "Overdue by N days" styling \u2014 do not modify the component's presentation logic. If the effective date is absent, render nothing (unchanged). Orphan `localStorage` entries (task IDs no longer returned by the API) render nothing because the card for that ID doesn't exist \u2014 no errors thrown. When the user clears browser storage, cards render without locally-stored labels and the app continues to function.

## Why

Surfaces the due date on every task card without introducing a second label or new styling \u2014 satisfies UX1 (reuse existing DueDateDisplay as the single due-date surface). Independent of form input and bell surfaces; multiple agents can work in parallel.

## Files to Modify

- `src/App.jsx:740-760` (edit) — Resolve effective dueDate via useDueDate(task.id) and pass to DueDateDisplay; do not modify the DueDateDisplay component internals at lines 542-597

## Reference Patterns

- `src/App.jsx:542-597` — DueDateDisplay internals — DO NOT modify, just feed an effective due date in
- `src/App.jsx:598-750` — SortableTaskItem shape — where DueDateDisplay is already rendered at ~747
- `src/hooks/useDueDates.js` — Store hook (from due-dates-store task) — DO NOT modify

## Test Plan

- `tests/card-due-date-display.test.jsx` (new) covers BDD-3, BDD-4, BDD-13, BDD-14

## Out of Scope

- src/App.jsx DueDateDisplay component internals at lines 542-597 (must remain unchanged — UX1 explicitly reuses it as-is)
- Create/edit form (owned by due-date-form-input)
- Bell + badge (owned by header-bell-badge)
- Drawer (owned by bell-drawer-navigation)
- Active orphan cleanup (deferred per A1)

## Verification

- npm test -- tests/card-due-date-display.test.jsx passes
- npm test passes overall
- npm run build passes
- Manual: seed localStorage with dueDate:{id} for today and yesterday, reload, verify fuchsia + rose styling on the right cards

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** a non-terminal-status task whose effective due date equals today
  **WHEN** the app loads
  **THEN** its card renders in fuchsia via the existing DueDateDisplay component _(implements BDD-3)_

- **GIVEN** a non-terminal-status task whose effective due date is earlier than today
  **WHEN** the app loads
  **THEN** its card renders in rose and shows 'Overdue by N days' _(implements BDD-4)_

- **GIVEN** a localStorage due-date entry exists for a task ID that is no longer returned by the API
  **WHEN** the app loads
  **THEN** the orphaned entry is ignored when rendering cards and no errors are thrown _(implements BDD-13)_

- **GIVEN** the user has cleared browser storage
  **WHEN** they reload the app
  **THEN** all tasks render without locally-stored due-date labels and the app functions normally _(implements BDD-14)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
