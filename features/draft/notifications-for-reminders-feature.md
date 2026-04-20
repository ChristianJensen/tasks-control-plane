---
title: "Notifications for Reminders"
lifecycle: draft
execution: supervised
model: ""
priority: medium
dimensions: [assumptions, edges, scope, arch, ux]
total-budget: ""
total-cost-usd: ""
total-tokens: ""
epic: TASK-5
epic-title: Q1 - Task Tracker Enhancements
version: 1
paused-at: ""
paused-by: ""
pause-reason: ""
created-at: ""
completed-at: ""
deployed-at: ""
deployed-env: ""
---
# Notifications for Reminders

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| 1 | conversation | interview transcript (this spec) | Planner + User | 2025 |

## Problem Statement

Users currently have no way to be reminded about tasks that need attention on a given day. When they open the task tracker, there is no visible signal that a task is due today or is overdue — they have to scan the full list and remember which ones matter. This makes it easy to miss time-sensitive work. V1 solves this with a minimal, in-app, browser-only reminder: tasks can be given an optional due date, and when the app is opened, a bell icon with a badge count surfaces the items that are due today or overdue.

## User Journey

### Happy path

1. User creates or edits a task and picks an optional due date via a native date input (`YYYY-MM-DD`). → The date is persisted locally to `localStorage` under a per-task key (`dueDate:{taskId}`) and mirrored into the in-memory due-dates map.
2. User reopens the app on or after that date. → On load, the frontend reads all tasks, joins them with the in-memory due-dates map (cold-loaded once from `localStorage`), and computes the set of non-terminal-status tasks where effective `dueDate <= today` (user's local timezone).
3. If that set is non-empty, a bell icon appears in the desktop header with a badge showing the count (capped visually at "99+"). → If the count is zero, the bell is hidden entirely. Mobile header integration is deferred in v1.
4. User sees the due date rendered directly on task cards in the main list via the existing `DueDateDisplay` component. → Cards with effective `dueDate === today` render in fuchsia; cards with effective `dueDate < today` render in rose and show "Overdue by N days".
5. User clicks the bell. → A right-side drawer opens (same pattern as Help/Contact) listing the matching tasks, ordered most overdue first, then due today, with task creation order as a tiebreaker, up to 50 items with a "+N more" footer if truncated. Each item shows the task title, a "Due today" or "Overdue by N days" label, and the current status pill.
6. User clicks an item in the drawer. → The drawer closes, the main list scrolls the target task into view, and DOM focus moves to that task card (the existing focus ring serves as the highlight). If the task is hidden by an active filter, an inline "This task is hidden by the current filter" message with a one-click "Clear filter" action appears instead.
7. User marks a task as done (or changes its due date to a future date, or clears it). → The badge count and drawer contents re-derive live within the tab; the task disappears from the reminder surface. If count reaches zero, the bell hides.

### Error / edge paths

1. User opens the app with no non-terminal tasks whose effective `dueDate <= today`. → Bell icon is not rendered. No drawer, no empty state to click.
2. User clears browser storage (or opens the app in a different browser / device). → All locally stored due dates are lost; tasks appear without due-date labels; bell is hidden until the user re-enters dates. This is an accepted v1 tradeoff.
3. User has a `localStorage` entry for a task ID that no longer exists on the server (deleted elsewhere). → The orphaned entry is ignored when computing the badge and drawer. Cleanup is best-effort, not guaranteed in v1.
4. User sets a due date in the past. → Allowed. The task is treated as overdue immediately.
5. User sets a due date on a task in a terminal status (e.g. `done`). → The task does not appear in the bell or badge (terminal-status tasks are excluded regardless of due date).
6. User leaves the app open across midnight, or the device clock / timezone changes. → Badge is computed from `new Date()` at app load (plus live intra-tab mutations) and is not recomputed on a timer in v1; the user sees the updated count on the next page load or manual refresh.
7. User clicks a drawer item whose target task is hidden by an active filter. → Drawer closes and an inline "This task is hidden by the current filter" message is shown with a "Clear filter" action that then scrolls and focuses the card. The bell itself never filters its own contents.
8. The `localStorage` write for a due date fails after successful task creation (quota exceeded, storage disabled mid-session). → The in-memory map is not updated either and a non-blocking toast appears: "Couldn't save due date locally — task was created without a reminder." Task creation never blocks on storage.
9. A second tab edits due dates concurrently. → Each tab owns its in-memory map and writes through per-task keys; the other tab sees the change on next reload. Cross-tab `storage`-event listening is deferred.

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | Tasks have an optional due date, as a calendar date (`YYYY-MM-DD`) with no time component | S1 | High | Matches user statement: "not specific to the minute or hour" |
| R2 | Due dates are stored client-side in `localStorage`, keyed by task ID (one key per task, e.g. `dueDate:{taskId}`, per A4); no API contract change in v1 | S1 | High | Explicit user decision: "can we do a first version only client side?" / "keep simple for now" |
| R3 | Due date input is available in both the create-task form and the edit-task form, via a native `<input type="date">` | S1 | High | |
| R4 | Task cards in the main list display the due date by reusing the existing `DueDateDisplay` component: fuchsia styling for "due today" and rose styling for "overdue" ("Overdue by N days"). The v1 effective due date per task is `task.dueDate ?? localDueDateMap[task.id]` — a single label, not a second one | S1 | High | Per UX1: reuse existing palette + slot; "amber" from the original draft is dropped for consistency with the in-app theme |
| R5 | A bell icon is rendered in the desktop app header with a badge showing the count of non-done tasks where effective `dueDate <= today` (local timezone); mobile header integration is deferred | S1 | High | Per UX1 |
| R6 | When the count is zero, the bell icon is not rendered at all | S1 | High | Simplest empty state |
| R7 | Clicking the bell opens a side drawer (same pattern as Help/Contact: right-side 400px panel with backdrop) listing the matching tasks, ordered most overdue first, then due today, with task creation order as tiebreaker | S1 | High | Per UX3: replaces the original "anchored dropdown" — reuses an existing UI pattern so no new popover primitive is introduced |
| R8 | Each drawer item shows task title, a "Due today" or "Overdue by N days" label, and the current status pill | S1 | High | |
| R9 | Clicking a drawer item closes the drawer, scrolls the target task into view (`scrollIntoView({ behavior: 'smooth', block: 'center' })`), and moves DOM focus to that task card (reusing the existing `focusedTaskId` + `focusRequestId` plumbing); the existing focus ring serves as the visual highlight. If the target task is not currently rendered (hidden by an active filter per E4), the drawer closes and an inline message "This task is hidden by the current filter" appears with a one-click "Clear filter" action that then performs the scroll + focus | S1 | High | Per UX2, UX3, E4 |
| R10 | Tasks in terminal/non-actionable statuses (today: `done`; future additions like `archived` or `cancelled` would also qualify) are excluded from the bell badge and drawer regardless of due date | S1 | High | Per A3 |
| R11 | Past due dates are accepted without validation error | S1 | High | |
| R12 | Badge and drawer contents are recomputed on app load and re-derived live within the current tab on any mutation to tasks or the due-dates map; no "read/unread" or "dismissed" state is persisted; cross-tab changes are picked up on reload | S1 | High | Per A4, E3 |
| R13 | Bell and drawer keyboard semantics: Enter/Space on the bell toggles the drawer; Escape closes and returns focus to the bell trigger; click-outside closes; inside the drawer, Arrow Up/Down moves between items and Enter activates. No focus trap. Badge carries an accessible label (e.g. "3 tasks due or overdue") | S1 | High | Per UX2, C3 |
| R14 | Badge displayed value is capped at "99+" (true count used internally for ordering/logic); drawer renders the top 50 items per R7 ordering with a subtle "+N more" footer when truncated; no pagination controls in v1 | S1 | High | Per A2 |
| R15 | Due-date reads during rendering go through an in-memory `Map<taskId, dueDate>` loaded once at app mount from `dueDate:*` keys; writes update the map and `localStorage` (write-through). No repeated enumeration of `localStorage` after mount | S1 | High | Per AR2 |
| R16 | No new runtime dependencies are added for this feature; existing header, drawer, focus-ring, and state patterns are reused | S1 | High | Per AR3, UX3 |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| — | No conflicts; single-source interview | n/a |

## Open Questions

- [x] None blocking. All decisions confirmed through 6 rounds of refinement (assumptions, edges, scope, arch, PII skip, UX).

## Acceptance Criteria

- [ ] A user can set a due date on a new task from the create form.
- [ ] A user can set, change, or clear a due date on an existing task from the edit form.
- [ ] Due dates persist across page reloads in the same browser.
- [ ] Task cards display the due date (via the existing `DueDateDisplay` component) when one is set — either server-side `task.dueDate` or the locally-stored override.
- [ ] Task cards with an effective due date equal to today are rendered in fuchsia.
- [ ] Task cards with an effective due date earlier than today are rendered in rose and show "Overdue by N days".
- [ ] The bell icon and badge appear in the desktop header if and only if there is at least one non-terminal-status task with effective `dueDate <= today`; the badge displays up to "99+".
- [ ] The badge count matches the number of non-terminal-status tasks with effective `dueDate <= today`.
- [ ] The badge has an accessible label (e.g. "3 tasks due or overdue").
- [ ] Clicking the bell opens a right-side drawer (same pattern as Help/Contact) listing those tasks, most overdue first, capped at 50 with "+N more" footer when truncated.
- [ ] Enter/Space on the bell toggles the drawer; Escape closes it and returns focus to the bell trigger; click-outside closes it.
- [ ] Inside the drawer, Arrow Up/Down navigates items and Enter activates the focused item.
- [ ] Terminal-status tasks (e.g. `done`) never appear in the bell or badge, even if their due date is today or earlier.
- [ ] Clicking or activating a drawer item closes the drawer, scrolls the target task into view, and moves DOM focus to the task card so the existing focus ring indicates the target.
- [ ] If the target task is hidden by an active filter, an inline "This task is hidden by the current filter" message appears with a working "Clear filter" action.
- [ ] Clearing browser storage removes all due dates without breaking the app (tasks still render normally, bell hides).
- [ ] If `localStorage.setItem` throws during a due-date write, the app does not crash and surfaces a non-blocking toast; task creation/edit itself still succeeds.
- [ ] Badge and drawer re-derive live within the current tab on any mutation to tasks or the due-dates map (no frozen snapshot while the drawer is open).
- [ ] Due-date reads at render time go through an in-memory map; no repeated enumeration of `localStorage` after app mount.
- [ ] No new runtime dependencies are added to the frontend for this feature.
- [ ] No changes to the `Task` schema or the `/tasks` API contract ship in v1.

## Behavioral Scenarios

### Happy Path

- **BDD-1:** **GIVEN** a user viewing the task create form **WHEN** they enter a title, pick a due date, and submit **THEN** the task is created via the existing API and the chosen due date is persisted under `dueDate:{newTaskId}` and mirrored into the in-memory due-dates map.
- **BDD-2:** **GIVEN** a task with no due date **WHEN** the user opens the edit form, picks a due date, and saves **THEN** the due date is written to `localStorage` and the map for that task ID, and the task card updates to show the due-date label via the existing `DueDateDisplay`.
- **BDD-3:** **GIVEN** a non-terminal-status task whose effective due date equals today **WHEN** the app loads **THEN** its card renders in fuchsia via the existing `DueDateDisplay` component.
- **BDD-4:** **GIVEN** a non-terminal-status task whose effective due date is earlier than today **WHEN** the app loads **THEN** its card renders in rose and shows "Overdue by N days".
- **BDD-5:** **GIVEN** the user has at least one non-terminal-status task with effective `dueDate <= today` **WHEN** the app loads on desktop **THEN** the bell icon is rendered in the header with a badge showing the count (capped visually at "99+") and an accessible label such as "3 tasks due or overdue".
- **BDD-6:** **GIVEN** the bell icon is visible **WHEN** the user clicks it (or presses Enter/Space on it) **THEN** a right-side drawer opens listing the matching tasks, ordered most overdue first, then due today, with task creation order as tiebreaker, capped at 50 items with a "+N more" footer when truncated, each item showing title, a "Due today"/"Overdue by N days" label, and the status pill.
- **BDD-7:** **GIVEN** the bell drawer is open **WHEN** the user presses Arrow Down or Arrow Up **THEN** focus moves between drawer items in order.
- **BDD-8:** **GIVEN** the bell drawer is open and the target task is currently rendered **WHEN** the user activates an item (click or Enter) **THEN** the drawer closes, the main list scrolls the corresponding task into view, and DOM focus moves to that task card so the existing focus ring marks it.
- **BDD-9:** **GIVEN** the bell drawer is open **WHEN** the user presses Escape **THEN** the drawer closes and focus returns to the bell trigger button.
- **BDD-10:** **GIVEN** a task is in the bell drawer **WHEN** the user marks it done (from the main list or from inside the open drawer) **THEN** the drawer and badge re-derive immediately in the current tab: the task disappears and the badge count decreases by one; if the count reaches zero, the bell hides.

### Edge Cases

- **BDD-11:** **GIVEN** no non-terminal-status tasks have effective `dueDate <= today` **WHEN** the app loads **THEN** the bell icon is not rendered at all (no empty drawer, no zero badge).
- **BDD-12:** **GIVEN** a task whose status is terminal (e.g. `done`) and whose due date is today or earlier **WHEN** the app loads **THEN** the task is not included in the badge count and does not appear in the drawer, regardless of its due date.
- **BDD-13:** **GIVEN** a `localStorage` due-date entry exists for a task ID that is no longer returned by the API **WHEN** the app loads **THEN** the orphaned entry is ignored when computing the badge and drawer, and no errors are thrown.
- **BDD-14:** **GIVEN** the user clears browser storage **WHEN** they reload the app **THEN** all tasks render without locally-stored due-date labels, the bell is hidden unless server-side `task.dueDate` values still qualify, and the app functions normally.
- **BDD-15:** **GIVEN** a task has a locally-stored due date and appears in the bell **WHEN** the user edits the task and clears the due date field **THEN** the corresponding `localStorage` key and map entry are removed, the card no longer shows a due-date label, and the badge count decreases by one.
- **BDD-16:** **GIVEN** the bell drawer is open and the user activates an item whose target task is hidden by an active filter **WHEN** the activation fires **THEN** the drawer closes and an inline "This task is hidden by the current filter" message appears with a "Clear filter" action that clears the filter, scrolls the task into view, and moves focus to its card.
- **BDD-17:** **GIVEN** a task creation succeeds but the follow-up `localStorage.setItem` throws **WHEN** the write fails **THEN** the app surfaces a non-blocking toast ("Couldn't save due date locally — task was created without a reminder") and the task still exists; the user can set the due date again from the edit form.
- **BDD-18:** **GIVEN** two tabs are open on the same browser **WHEN** tab A adds a due date and tab B reloads **THEN** tab B sees the new due date; without a reload, tab B's badge and drawer remain stale.
- **BDD-19:** **GIVEN** the app is open across midnight, or the device clock or timezone changes while the app stays open **WHEN** no page load or mutation occurs **THEN** the badge and drawer continue to reflect `today` as it was at the last recompute; they update on the next page load or intra-tab mutation, not on a timer.

## Constraints

| # | Category | Requirement | Verification |
|---|----------|-------------|--------------|
| C1 | Performance | Badge and drawer computation runs in O(n) over the loaded task list and must not add perceptible latency to app load (< 50ms for typical task counts; holds at 10x task volume per AR2) | Manual profiling with realistic task list sizes |
| C2 | Compatibility | No changes to the OpenAPI contract; api repo is not modified in v1 | Diff of `contracts/tasks-api.json` is empty |
| C3 | Accessibility | Bell icon is keyboard-focusable; drawer is operable via keyboard per R13 (Enter/Space to toggle, Escape to close with focus return, Arrow keys to navigate items, Enter to activate); badge count is announced to screen readers via accessible label (e.g., "3 tasks due or overdue"); on item activation, DOM focus moves to the target task card | Manual a11y check with keyboard + screen reader |
| C4 | Operational | Feature degrades gracefully when `localStorage` is unavailable or disabled (e.g., private browsing with storage blocked): tasks render, bell stays hidden if no server-side due dates qualify, no thrown errors; failed writes surface a non-blocking toast rather than crashing | Manual test with storage disabled |
| C5 | Dependencies | No new frontend runtime dependencies are introduced by this feature; existing header, side-drawer (Help/Contact pattern), focus-ring, and `focusedTaskId` plumbing are reused | Diff of `frontend/package.json` shows no additions |
| C6 | Scope | Bell + badge + drawer are desktop-only in v1; the mobile header is not modified (deferred) | Manual check that mobile render path is unchanged |

## Out of Scope

- Browser push notifications, email, or SMS reminders.
- Server-side storage of due dates (deferred to v2; will require API contract change and a one-time client→server import per AR1).
- Cross-device / cross-browser syncing of due dates.
- Time-of-day precision (hour / minute level due times).
- Snoozing, dismissing, or marking reminders as read (B1).
- Multi-select / bulk actions from the bell drawer, e.g. "mark all done" or "push all to tomorrow" (B2).
- Due-date filtering or sorting on the main task list, e.g. "Due this week" chip, "Sort by due date", or a dedicated "Overdue" view (B3).
- Recurring tasks or repeating reminders.
- Reminder lead time (e.g., "remind me 2 days before").
- Notification history / past reminders log.
- Real-time badge updates while the app is open across midnight or when the device clock/timezone changes (v1 recomputes on page load and intra-tab mutations only).
- Automatic cleanup of orphaned `localStorage` entries when tasks are deleted elsewhere.
- Cross-tab live sync via the `storage` event (per A4; other tabs update on reload).
- Mobile header integration of the bell + drawer — v1 is desktop-only (per UX1); mobile task cards still pick up the reused `DueDateDisplay` labels for free, but the bell surface itself is deferred.
- Live-region / screen-reader announcements on every badge recompute (focus-moves-to-card in R9 is considered sufficient feedback in v1).

## Refinement Log

### Round 1: Assumptions

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | When a task is deleted in this browser, its `localStorage` due-date entry is silently left orphaned rather than actively cleaned up | Yes | Hold as-is for v1 per "keep simple" — no active cleanup on same-browser delete. Read-time filter (BDD-10) remains the sole safety net; orphaned entries are ignored when computing the badge and dropdown. Automatic cleanup stays explicitly out of scope. |
| A2 | The bell badge count and dropdown length are unbounded — any number of matching tasks renders verbatim | Yes | Adjusted. Badge caps displayed value at "99+" (true count still used internally for ordering/logic). Dropdown renders the top 50 items (most overdue first per R7 ordering), with a subtle "+N more" footer shown when truncated. No pagination controls in v1. Keeps header layout stable and bounds render cost under the <50ms budget in C1. |
| A3 | The exclusion rule is literally "status === done"; all other statuses are eligible for the bell | Yes | Adjusted in principle, not in observable behavior. Current task tracker has statuses `todo`, `in-progress`, `done` — `done` is the only terminal one, so the implementation today is identical. Rephrase R10 as "exclude terminal/non-actionable statuses" so future additions (e.g. `archived`, `cancelled`) don't silently start appearing in the reminder bell. Add a test that asserts the rule against the terminal-status set rather than the string `"done"`. |
| A4 | Multi-tab concurrent edits Just Work via `localStorage` | Yes | Accept staleness in v1 — consistent with R12 and edge-path 6 (recomputation happens on load, not on timers or events). A second tab will see outdated badges/labels until the user reloads; document as a known limitation alongside the midnight-rollover gap. To prevent silent clobber, lock the storage schema to **one `localStorage` key per task ID** (e.g. `dueDate:{taskId}`) rather than a single JSON blob, so writes from different tabs cannot overwrite each other's unrelated edits. Listening for cross-tab `storage` events is explicitly deferred. |

### Round 2: Edge Cases

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | Device clock is wrong, user changes their clock, or user crosses timezones between sessions — `today` is computed from an untrusted/shifting local clock | R5, R12 | Trust `new Date()` at page-load time unconditionally in v1. No UTC normalization, no stored timezone, no sanity check. A task with `dueDate = 2025-03-15` becomes "due today" whenever the device's local date reads 2025-03-15, matching native all-day-event semantics. Document alongside the existing midnight-rollover gap (edge path 6) as an accepted limitation: clock or timezone changes take effect on the next page load. Consistent with the device-local, no-sync posture of R2. |
| E2 | Task is created via API successfully, but the follow-up `localStorage` write for the due date fails (quota exceeded, private browsing, storage disabled mid-session) or the tab is closed before the write completes | R2, R3, C4 | Best-effort write after API success. If `setItem` throws, swallow the error at the data layer and surface a non-blocking toast: "Couldn't save due date locally — task was created without a reminder." Task creation itself never blocks on storage (aligns with C4 graceful-degradation). User recovery path is the edit form. The tab-closed-before-write case is unavoidable under any client-only scheme and is accepted per R2. No temp-key / reconciliation machinery in v1. |
| E3 | Within a single session, the badge or open dropdown drifts from truth after a mutation (user clears a due date, marks a task done from the main list, or marks a task done from inside the open dropdown itself) | R10, R12, BDD-6, BDD-12 | Immediate in-tab reactivity. Badge and dropdown contents are derived state over `(tasks, dueDatesMap)`; any mutation to either re-renders the bell in the current tab. The dropdown updates live while open — no frozen snapshot — so an item the user just completed disappears immediately. Cross-tab updates still require a reload (consistent with A4's deferral of `storage` events). Add one line to the spec making intra-tab reactivity explicit. |
| E4 | User clicks a dropdown item whose target task is not currently rendered in the main list because an active filter (status, search) hides it — R9's "scroll to and highlight" has no DOM node to target | R7, R9, BDD-5 | The bell deliberately ignores list filters (surfacing hidden-but-overdue items is the point of the feature — do not make the bell filter-aware). On click, if the target task is rendered, scroll + highlight as specified. If it is not rendered, close the dropdown and show a dismissible inline message: "This task is hidden by the current filter." with a one-click "Clear filter" action that then scrolls and highlights. No silent no-op, no auto-clearing of the user's filter. Update R9 to make this conditional behavior explicit. |

### Round 3: Scope Boundaries

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | Snooze / dismiss reminders (temporarily silence an overdue task without marking it done or changing its due date) | Out | Introduces persistent per-reminder state that contradicts R12's stateless recompute-on-load model, adds a second `localStorage` schema and conflict paths with due-date edits, and the existing affordances (push the due date, mark done) already cover the underlying need. Defer to v2 pending real user demand. |
| B2 | Multi-select / bulk actions from the bell dropdown (e.g., "mark all done", "push all to tomorrow") | Out | Shifts the dropdown from a glance-and-navigate surface to a triage workbench, requires bulk API semantics we don't have (conflicts with R2/C2 no-contract-change), and design decisions (one date for all? relative shift?) we haven't validated. Single-item click-through path is sufficient for v1. |
| B3 | Due-date filter / sort on the main task list (e.g., "Due this week" chip, "Sort by due date", dedicated "Overdue" view) | Out | The bell + dropdown already delivers the "what needs attention" path called out in the Problem Statement. List-level slicing is a broader affordance that touches existing list UI beyond the additive bell component, conflicting with the minimal-footprint v1 posture. Natural v2 once due dates prove adoption. |

### Round 4: Architecture Review

| # | Implication | Impact Area | Resolution |
|---|------------|-------------|------------|
| AR1 | Client-only `localStorage` storage creates a parallel data store with no referential integrity to the server, and defers a migration problem to v2 ("will require migration or re-entry" in Out of Scope) without specifying how v1 data is recovered | API | Ship client-only as specified per user direction ("simple for now"). Lock the forward-migration contract in now: v2 will add a nullable `dueDate` field to the `Task` API (additive, non-breaking) and ship a one-time import-on-load that reads `dueDate:{taskId}` keys, POSTs them to the server, and deletes the local keys on success. The per-task-ID key schema (A4) is preserved unchanged precisely to make this import straightforward. Users on other browsers/devices still lose their v1 data — accepted tradeoff, consistent with R2. |
| AR2 | Naive `localStorage` access on every render / mutation does not scale: synchronous `Object.keys(localStorage)` scans and per-key `getItem` calls become main-thread-blocking at 10x task volume (~1,000 tasks), and E3's intra-tab reactivity risks repeated storage I/O on every edit | perf | Specify the access pattern in v1: on app mount, load all `dueDate:*` keys once into an in-memory `Map<taskId, dueDate>`. All subsequent reads (badge derivation, dropdown, card labels) run against the map. Writes update the map *and* `setItem` to `localStorage` (write-through). No repeated enumeration of `localStorage` after mount. Keeps C1's <50ms budget defensible at 10x, and makes A4's one-key-per-task schema a clean input to the cold load. No index key (avoids a second source of truth). |
| AR3 | The feature implies several non-trivial UI primitives — header bell slot, anchored dropdown with focus trap and keyboard nav (C3), cross-component scroll-to-and-highlight — that could silently pull in new runtime dependencies (floating-ui, popover libraries, state stores) during implementation | deps | Add a constraint: no new runtime dependencies for this feature. Reuse existing header, menu/popover, and state patterns already in the frontend. The dropdown has a fixed anchor, no collision-detection needs, and ≤50 items (A2), so a minimal inline implementation is sufficient. If during build the engineer determines a11y compliance (C3) genuinely requires a library, that reopens the spec rather than slipping into a PR silently. Integration details (how the bell signals the list to scroll/highlight) remain an implementation choice. |

**Architecture diagrams consulted:** None — v1 is frontend-only with no new services, no API contract change (C2), and no new runtime dependencies (AR3); existing frontend component and storage diagrams (if any) are unaffected at the structural level.
**Diagrams requiring update after ship:** None for v1. When v2 moves `dueDate` to the server per AR1, the `Task` schema diagram and any data-flow diagram showing client/server persistence boundaries will need to be updated to reflect the new server-side field and the one-time client→server import path.
### Round 5: PII / Compliance Review

_Skipped per dimension selection — no new PII is introduced; `dueDate` is a non-identifying timestamp stored only in the user's own browser._

| # | Data Element | Classification | Handling Requirement |
|---|-------------|---------------|---------------------|
| P1 | N/A | N/A | No PII dimension selected; see rationale above |

### Round 6: UX & Interaction Review

| # | Concern | Category | Resolution |
|---|---------|----------|------------|
| UX1 | Visual coexistence with the existing server-side `task.dueDate` — the app already renders a `DueDateDisplay` with a `Calendar` icon, fuchsia "today" and rose "overdue" treatments on task cards (desktop and mobile paths) — and the spec proposed a second, amber-for-today label on top of it | consistency | Simplify: reuse the **existing** `DueDateDisplay` slot as the single due-date surface on cards. At render time, join `task.dueDate ?? localDueDateMap[task.id]` and feed that into the existing component. Drop R4's "amber" — today stays fuchsia, overdue stays rose, matching the in-app palette. Do not introduce a second label. Bell is **desktop-only** in v1; mobile header integration is explicitly deferred to a later iteration (add to Out of Scope). Benefit: zero new card-level primitives, and the v2 server migration (AR1) becomes a data-source swap rather than a component swap. |
| UX2 | Keyboard and screen-reader semantics for the bell + its panel are only partially covered by C3 — open/close keys, item navigation, and what happens after "scroll to and highlight" (R9) for non-sighted users are unspecified | a11y | Reuse the existing `HelpDrawer` keyboard pattern already in `App.jsx`: **Enter/Space** toggles the bell, **Escape** closes and returns focus to the bell trigger, click-outside closes. Inside the panel, **Arrow Up/Down** moves between items, **Enter** activates. On item activation, **move DOM focus to the target task card** by reusing the existing `focusedTaskId` + `focusRequestId` plumbing on `SortableTaskItem` — this replaces a bespoke visual-only highlight and gives keyboard and screen-reader users the same "landed on the right task" signal as sighted users, with no new live regions. No focus trap (panel is a menu, not a modal). No announcement on badge recomputes in v1. |
| UX3 | The spec's anchored header dropdown, badge, and "scroll to and highlight" animation are three net-new UI primitives with no precedent in the codebase — existing header affordances (Help, Contact) use a side-drawer pattern, and there is no scroll-to-task or pulse-highlight animation anywhere today; this risks violating AR3 ("reuse existing patterns, no new deps") | consistency | Replace the anchored dropdown with the **existing side-drawer pattern** used by Help and Contact (right-side 400px panel, backdrop, Escape-to-close, focus restored to trigger). The bell becomes another header button whose open state is a drawer listing the matching tasks per R7/R8 ordering. For R9, on item click: close the drawer, call `element.scrollIntoView({ behavior: 'smooth', block: 'center' })`, and move focus to the card — the **existing focus ring** (`var(--color-focus-ring)` + `var(--glow-cyan-focus)` already applied to focused cards in `SortableTaskItem`) serves as the "highlight." No new animation, no popover/anchoring logic, no collision handling. The only genuinely new visual primitive in v1 is the numeric badge overlaid on the bell icon. Supersedes R7's "dropdown" language — update wording at implementation time. |

## Readiness Checklist

- [x] All High-confidence requirements have acceptance criteria
- [x] No unresolved conflicts remain
- [x] Open questions are non-blocking or have owners
- [x] At least 3 assumptions explicitly challenged and resolved
- [x] At least 3 edge cases explicitly addressed
- [x] Out of Scope section reviewed via scope boundary probe
- [x] At least 2 architectural implications reviewed
- [ ] PII and sensitive data elements identified with handling requirements (or explicit N/A)
- [x] At least 2 UX/interaction concerns reviewed (or explicit N/A for non-UI features)
- [ ] Non-functional constraints identified (or explicit N/A with rationale)
- [x] All User Journey steps and edge cases have corresponding BDD-N scenarios
