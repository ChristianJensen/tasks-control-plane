---
task-id: due-date-form-input
status: done
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: notifications-for-reminders
type: feature
estimated-lines: 220
depends-on:
  - due-dates-store
scenario-refs:
  - BDD-1
  - BDD-2
  - BDD-15
claimed-by: cloud-Christians-MacBook-Air-77071
claimed-at: 2026-04-20T16:48:18Z
claimed-on: Christians-MacBook-Air
cost-usd: 2.953232699999999
input-tokens: 83
output-tokens: 44765
duration-ms: 824865
auth-mode: max-oauth
billed: false
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/116
pr-number: 116
---

## Description

Add an optional due-date field (`<input type="date">`, `YYYY-MM-DD`) to both the create-task form and the edit-task form in `App.jsx`. On submit/save, after the existing API call succeeds, call the due-dates store: `setDueDate(taskId, value)` when a date is entered, `clearDueDate(taskId)` when the user clears it. Past dates are accepted with no validation error. Storage failure is handled by the store (surfaces a toast); the form submission itself must still complete successfully.

## Why

Delivers the primary user entry point for the feature \u2014 users can't be reminded about a task until they can give it a due date. Vertical slice: UI input \u2192 store \u2192 localStorage. No dependency on card rendering or bell surfaces.

## Files to Modify

- `src/App.jsx` (edit) — Add <input type='date'> to create-task form block and edit-task form block; wire onSubmit to call useDueDates setDueDate/clearDueDate after the existing API success

## Reference Patterns

- `src/App.jsx:542-597` — DueDateDisplay — YYYY-MM-DD format convention this feature reuses
- `src/App.jsx` — Existing create-task and edit-task form shape — match its field layout, validation, and post-submit flow; DO NOT modify its API payload
- `src/hooks/useDueDates.js` — Store hook consumed here (from due-dates-store task) — DO NOT modify

## Test Plan

- `tests/due-date-form.test.jsx` (new) covers BDD-1, BDD-2, BDD-15

## Out of Scope

- src/App.jsx DueDateDisplay component itself (owned by card-due-date-display)
- Bell icon and badge rendering (owned by header-bell-badge)
- Drawer UI (owned by bell-drawer-navigation)
- OpenAPI contract — contracts/tasks-api.json must remain unchanged (C2)
- Validation of past dates (R11: explicitly allowed)

## Verification

- npm test -- tests/due-date-form.test.jsx passes
- npm test passes overall
- npm run build passes
- Manual: create a task with due date, reload, verify localStorage key dueDate:{id} exists with the YYYY-MM-DD value

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** a user viewing the task create form
  **WHEN** they enter a title, pick a due date, and submit
  **THEN** the task is created via the existing API and the chosen due date is persisted under dueDate:{newTaskId} and mirrored into the in-memory due-dates map _(implements BDD-1)_

- **GIVEN** a task with no due date
  **WHEN** the user opens the edit form, picks a due date, and saves
  **THEN** the due date is written to localStorage and the map for that task ID, and subsequent reads of the map return it _(implements BDD-2)_

- **GIVEN** a task has a locally-stored due date
  **WHEN** the user edits the task and clears the due date field
  **THEN** the corresponding localStorage key and map entry are removed _(implements BDD-15)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
