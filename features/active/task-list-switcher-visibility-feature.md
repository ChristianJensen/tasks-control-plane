---
title: "Visible current task list name and list switcher"
lifecycle: active
execution: supervised
model: ""
priority: medium
total-budget: ""
total-cost-usd: ""
total-tokens: ""
epic: ""
epic-title: ""
version: 1
paused-at: ""
paused-by: ""
pause-reason: ""
created-at: ""
completed-at: ""
deployed-at: ""
deployed-env: ""
---
<!-- LIFECYCLE NOTE: The parent directory (draft/, active/, completed/, cancelled/)
     is authoritative for feature lifecycle phase. The lifecycle field below is
     kept in sync for human readability. When directory and frontmatter diverge,
     the directory wins. Paused and replanning are sub-states within active/. -->
# Visible current task list name and list switcher

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| S1 | conversation | interview transcript (planner session) | product owner | this session |
| S2 | existing tests | `frontend/tests/task-list-navigation.test.jsx` | codebase | pre-existing |
| S3 | existing tests | `frontend/tests/task-list-management.test.jsx` | codebase | pre-existing |
| S4 | existing tests | `frontend/tests/tasks-within-lists.test.jsx` | codebase | pre-existing |

## Problem Statement

End users of the tasks app work across multiple task lists (e.g. Personal, Work, Errands), but today the UI gives them no persistent indication of which list they are currently viewing and no quick way to switch between lists. A "manage lists" modal already exists (opened via the tasks button), but it is oriented toward create / rename / delete operations — it does not support switching the active list, and it is not visible at a glance. Users cannot answer "which list am I looking at?" without opening a modal, and switching context requires extra clicks that do not exist yet at all.

This feature makes the active list name always visible in the app header and turns it into a lightweight dropdown switcher so users can change lists in one click without going through the management modal.

## User Journey

### Happy path

1. User loads the app → The header displays the name of the currently active task list (e.g. "Personal") as a clickable selector element, and the task area below shows only the tasks belonging to that list.
2. User wants to confirm which list they are viewing → They glance at the header and read the list name without any interaction.
3. User wants to switch to a different list → They click the list name in the header → A dropdown menu opens below it, showing all of their task lists with the current one marked as selected.
4. User clicks another list (e.g. "Work") in the dropdown → The dropdown closes, the header updates to show "Work", the task area re-fetches and displays only tasks from the Work list, and this selection is persisted so the same list loads next time the user opens the app.
5. User returns to the app later (new session) → The last-used list is loaded automatically and displayed in the header; the user never sees an "empty" or "unselected" state.
6. User wants to create, rename, or delete a list → That is still handled by the existing "manage lists" modal (unchanged by this feature); the header switcher and the management modal coexist.

### Error paths and edge cases

1. User has only one task list → The header still shows that list's name; opening the dropdown shows just that single list (marked as selected). Clicking it is a no-op (dropdown closes, no re-fetch).
2. The `/task-lists` fetch fails on initial load → The header shows a non-blocking fallback label (e.g. "Tasks") and the dropdown, when opened, shows an error state with a retry affordance. Tasks may still load if a cached last-used listId exists in localStorage.
3. The user's last-used list (from localStorage) no longer exists on the server → The app falls back to the first list returned by the server, updates the header accordingly, and overwrites the stale localStorage entry.
4. User clicks the header selector while the list of lists is still loading → The dropdown opens in a loading state (skeleton or spinner) and populates when the fetch resolves.
5. User opens the dropdown then clicks outside it (or presses Escape) → The dropdown closes with no list change.
6. User switches list, but the subsequent task fetch fails → The header reflects the newly selected list (optimistically), the task area shows an error state with retry, and the switch is not reverted (the user intentionally chose this list).
7. A list is renamed inside the existing management modal → When the modal closes, the header selector reflects the new name without requiring a page reload.
8. The currently active list is deleted inside the existing management modal → The app switches to another available list (e.g. the first remaining list), updates the header, and re-fetches tasks.

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | The app header displays the name of the currently active task list at all times while the user is on a task view. | S1, S2 | High | Always-visible; no modal required to see it. |
| R2 | Clicking the displayed list name opens a dropdown/listbox showing all of the user's task lists. | S1, S2 | High | Implemented as a lightweight popover, not a modal. |
| R3 | The dropdown marks the currently active list as selected. | S2 | High | Visual affordance (checkmark, highlight, or aria-selected). |
| R4 | Selecting a different list from the dropdown closes the dropdown, updates the header, and loads tasks from that list only. | S1, S2, S4 | High | Task fetch must be scoped via `listId` query param. |
| R5 | The user's most recently selected list is persisted across sessions and restored on next app load. | S2 | High | Persist both `listId` and list name in localStorage so header can render before fetch resolves. |
| R6 | If no last-used list exists (new user or cleared storage), the app selects the first list returned by the server as the active list. | S2 | High | Deterministic default; never leave header empty. |
| R7 | If the last-used listId no longer exists on the server, the app falls back to the first available list and updates localStorage. | S1 | High | Stale-reference recovery. |
| R8 | The switcher element exposes a stable test hook `data-testid="task-list-selector"` and each option exposes `data-testid="task-list-option-{id}"`. | S2 | High | Required by existing test fixtures. |
| R9 | The existing "manage lists" modal (create / rename / delete) continues to work unchanged and is accessible from the same place it is today. | S1 | High | This feature adds a switcher; it does not remove or rework the modal. |
| R10 | Renaming or deleting a list inside the management modal is reflected in the header switcher without a page reload. | S1 | Med | Must share state / re-fetch lists after modal closes. |
| R11 | The switcher is keyboard accessible: it can be opened with Enter/Space, options navigated with Arrow keys, selected with Enter, and dismissed with Escape. | S1 | Med | Standard listbox/combobox a11y pattern. |
| R12 | The header selector and dropdown visually fit the existing header styling and do not regress responsive layout. | S1 | Med | No header redesign in scope; must be consistent with current theme. |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| S1 vs existing modal-based "manage lists" UX | Should switching happen inside the existing modal or in a new header dropdown? | Resolved (S1): new header dropdown. The modal remains for CRUD (create/rename/delete); switching is a header-level, one-click action. |

## Open Questions

- [ ] Q1 — Should the `/task-lists` endpoint already exist in the API, or must it be added as part of this feature? Existing frontend tests mock it, but the live API contract (`contracts/tasks-api.json`) does not expose it. — _needs product/tech owner input_
- [ ] Q2 — Does `GET /tasks?listId=X` already exist on the API, or does this feature need to add a `listId` filter to the list endpoint? Same situation as Q1. — _needs product/tech owner input_
- [ ] Q3 — For users with many lists (e.g. 20+), should the dropdown be scrollable, searchable, or paginated? — _non-blocking; default: scrollable with max-height_
- [ ] Q4 — Should the header name be truncated (with tooltip) for long list names, or wrap? — _non-blocking; default: truncate with title attribute_

## Acceptance Criteria

- [ ] AC1: The header displays the active list's name at all times on the task view.
- [ ] AC2: Clicking the header list name opens a dropdown listing all of the user's task lists, with the active list marked as selected.
- [ ] AC3: Selecting a different list from the dropdown updates the header, closes the dropdown, and causes the task area to display only tasks from the selected list.
- [ ] AC4: The last-selected list is persisted and automatically restored on the next app load (same session or new session).
- [ ] AC5: On first-ever load (no persisted selection), the first list returned by the server becomes the active list and is displayed in the header.
- [ ] AC6: If the persisted list no longer exists on the server, the app falls back to the first available list and updates persisted state.
- [ ] AC7: Renaming a list via the existing management modal updates the header display without a page reload.
- [ ] AC8: Deleting the currently active list via the existing management modal causes the app to switch to another available list automatically, updating the header and task area.
- [ ] AC9: The switcher exposes `data-testid="task-list-selector"` and each option `data-testid="task-list-option-{id}"`, and the dropdown is an accessible listbox.
- [ ] AC10: The switcher is operable by keyboard (Enter/Space to open, Arrows to navigate, Enter to select, Escape to close) and has visible focus indicators.
- [ ] AC11: Clicking outside the open dropdown closes it without changing the active list.
- [ ] AC12: The existing "manage lists" modal continues to function as before for create / rename / delete.

## Behavioral Scenarios

### Happy Path

- **BDD-1:** **GIVEN** the user has loaded the app with an active task list **WHEN** the task view renders **THEN** the header displays the name of the active list and the task area shows only tasks belonging to that list.
- **BDD-2:** **GIVEN** the user is viewing a task list **WHEN** they look at the header without interacting **THEN** the active list's name is readable at a glance.
- **BDD-3:** **GIVEN** the user is viewing a task list **WHEN** they click the list name in the header **THEN** a dropdown opens below it listing all of their task lists, with the currently active list marked as selected.
- **BDD-4:** **GIVEN** the switcher dropdown is open **WHEN** the user clicks a different list **THEN** the dropdown closes, the header updates to show the newly selected list's name, the task area displays only tasks from that list, and the selection is persisted for future sessions.
- **BDD-5:** **GIVEN** a user has previously selected a specific list in an earlier session **WHEN** they reopen the app **THEN** that list is loaded and shown in the header automatically, with no empty or unselected state displayed.
- **BDD-6:** **GIVEN** the header switcher is present **WHEN** the user opens the existing "manage lists" entry point **THEN** the management modal opens and functions as before, independently of the header switcher.

### Edge Cases

- **BDD-7:** **GIVEN** the user has only one task list **WHEN** they open the switcher dropdown **THEN** the dropdown shows just that single list marked as selected, and clicking it closes the dropdown without triggering a task re-fetch.
- **BDD-8:** **GIVEN** the request to load the user's task lists fails on initial load **WHEN** the user opens the switcher **THEN** the header shows a safe fallback label and the dropdown shows an error state with a retry affordance.
- **BDD-9:** **GIVEN** the user's persisted last-used list no longer exists on the server **WHEN** the app loads **THEN** the app falls back to the first available list, the header updates to that list's name, and the stale persisted selection is overwritten.
- **BDD-10:** **GIVEN** the task lists are still loading **WHEN** the user clicks the switcher **THEN** the dropdown opens in a loading state and populates once the lists have loaded.
- **BDD-11:** **GIVEN** the switcher dropdown is open **WHEN** the user clicks outside the dropdown **THEN** the dropdown closes and the active list is unchanged.
- **BDD-12:** **GIVEN** the switcher dropdown is open **WHEN** the user presses Escape **THEN** the dropdown closes and the active list is unchanged.
- **BDD-13:** **GIVEN** the user selects a different list from the dropdown **WHEN** the subsequent task fetch fails **THEN** the header still reflects the newly selected list and the task area shows an error state with a retry option (the switch is not reverted).
- **BDD-14:** **GIVEN** the user renames the currently active list inside the management modal **WHEN** the modal closes **THEN** the header switcher displays the new name without a page reload.
- **BDD-15:** **GIVEN** the user deletes the currently active list inside the management modal **WHEN** the deletion succeeds **THEN** the app switches to another available list, the header updates, and the task area re-fetches tasks for the new active list.
- **BDD-16:** **GIVEN** the switcher has keyboard focus **WHEN** the user presses Enter or Space **THEN** the dropdown opens.
- **BDD-17:** **GIVEN** the switcher dropdown is open **WHEN** the user presses ArrowDown or ArrowUp **THEN** keyboard focus moves to the next or previous list option with a visible focus indicator.
- **BDD-18:** **GIVEN** a list option has keyboard focus inside the open dropdown **WHEN** the user presses Enter **THEN** that list becomes the active list and the dropdown closes.

## Out of Scope

- Creating, renaming, or deleting task lists (handled by the existing "manage lists" modal).
- Reordering task lists.
- Sharing task lists between users / multi-user collaboration features.
- Redesigning the app header beyond adding the selector.
- Changing how tasks themselves are rendered, filtered, sorted, or categorized within a list.
- Adding a "recent lists" section, pinning, or favoriting of lists.
- Mobile-specific gesture-driven switching (swipe between lists).
- Search / filter inside the list switcher dropdown (deferred; default is a scrollable list).
- Introducing or modifying the `/task-lists` or `listId`-scoped `/tasks` API endpoints if they do not already exist (see Q1/Q2 — may need a separate backend feature).

## Refinement Log

### Round 1: Assumptions

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | | | |

### Round 2: Edge Cases

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | | | |

### Round 3: Scope Boundaries

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | | | |

### Round 4: Architecture Review

| # | Implication | Impact Area | Resolution |
|---|------------|-------------|------------|
| AR1 | | | |

**Architecture diagrams consulted:**
**Diagrams requiring update after ship:**

### Round 5: PII / Compliance Review

| # | Data Element | Classification | Handling Requirement |
|---|-------------|---------------|---------------------|
| P1 | | | |

### Round 6: UX & Interaction Review

| # | Concern | Category | Resolution |
|---|---------|----------|------------|
| UX1 | | | |

## Readiness Checklist

- [ ] All High-confidence requirements have acceptance criteria
- [ ] No unresolved conflicts remain
- [ ] Open questions are non-blocking or have owners
- [ ] At least 3 assumptions explicitly challenged and resolved
- [ ] At least 3 edge cases explicitly addressed
- [ ] Out of Scope section reviewed via scope boundary probe
- [ ] At least 2 architectural implications reviewed
- [ ] PII and sensitive data elements identified with handling requirements (or explicit N/A)
- [ ] At least 2 UX/interaction concerns reviewed (or explicit N/A for non-UI features)
- [x] All User Journey steps and edge cases have corresponding BDD-N scenarios
