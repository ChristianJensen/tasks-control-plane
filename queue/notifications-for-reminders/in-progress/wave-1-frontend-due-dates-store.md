---
task-id: due-dates-store
status: in-progress
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: notifications-for-reminders
type: feature
estimated-lines: 180
scenario-refs:
  - BDD-17
claimed-by: cloud-Christians-MacBook-Air-74415
claimed-at: 2026-04-20T16:43:31Z
claimed-on: Christians-MacBook-Air
---

## Description

Create a small client-side due-dates store: a React hook backed by an in-memory `Map<taskId, 'YYYY-MM-DD'>` that cold-loads once at mount from all `dueDate:{taskId}` keys in `localStorage`, and exposes `setDueDate(taskId, date)`, `clearDueDate(taskId)`, and `getDueDate(taskId)` with write-through to `localStorage`. Writes that throw (quota, private mode) must not crash — they surface a non-blocking toast ("Couldn't save due date locally — task was created without a reminder") and leave the in-memory map untouched so state stays consistent. Also provide a tiny toast primitive (auto-dismiss) reused across the feature. No enumeration of `localStorage` after mount (per AR2/R15). No cross-tab `storage` listener (deferred per A4).

## Why

Every other slice (form, card, bell, drawer) reads from the same in-memory map and must react live to writes. Centralising read/write/failure-toast logic here means each Wave 2 slice is thin and the write-failure BDD is implemented exactly once.

## Files to Modify

- `src/hooks/useDueDates.js` (new) — React hook: cold-load localStorage dueDate:* into Map, expose set/clear/get with write-through + failure toast
- `src/components/Toast.jsx` (new) — Minimal non-blocking toast primitive + provider (auto-dismiss after ~4s); reused across feature
- `src/App.jsx:3160-3200` (edit) — Mount DueDatesProvider + ToastProvider near root so all downstream slices consume the same store and toast surface

## Reference Patterns

- `src/App.jsx:107-180` — HelpDrawer component — framework conventions for self-contained components, styling, state management in this codebase
- `src/hooks` — Existing hooks directory — follow naming and file-layout conventions
- `tests/App.test.jsx:2446-2600` — HelpDrawer tests — framework conventions for vitest + testing-library setup, localStorage mocking patterns

## Test Plan

- `tests/useDueDates.test.jsx` (new) covers BDD-17

## Out of Scope

- src/App.jsx create/edit forms (owned by due-date-form-input)
- src/App.jsx DueDateDisplay rendering (owned by card-due-date-display)
- Bell icon, badge, drawer UI (owned by header-bell-badge and bell-drawer-navigation)
- Cross-tab storage event listener (deferred per A4)
- Orphan cleanup for deleted-elsewhere task IDs (read-time filter only — owned by header-bell-badge)

## Verification

- npm test -- tests/useDueDates.test.jsx passes
- npm test passes overall (no regressions in existing App tests)
- npm run build passes
- Manual: disable localStorage in DevTools, verify toast appears on setDueDate and app does not crash

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** a user has created a task and the follow-up localStorage write for the due date throws (quota exceeded / storage disabled)
  **WHEN** the store attempts to persist the due date
  **THEN** the task still exists, the in-memory map is not updated, and a non-blocking toast reads 'Couldn't save due date locally — task was created without a reminder' _(implements BDD-17)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant

## Implementation Notes

The hook should return a stable object and trigger re-renders of consumers on set/clear. A simple approach: internal `useState` holding a plain object snapshot of the map, with the Map kept in a ref for O(1) lookup. Export a `useDueDate(taskId)` selector hook so components only re-render when their own entry changes (optional optimisation).
