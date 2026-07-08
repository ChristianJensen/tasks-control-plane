---
title: "Grouping Task Lists"
lifecycle: active
execution: supervised
model: ""
priority: medium
dimensions: [assumptions, edges, ux]
total-budget: ""
total-cost-usd: ""
total-tokens: ""
epic: TASK-5
epic-title: ""
version: 1
loop: ""
paused-at: ""
paused-by: ""
pause-reason: ""
created-at: ""
completed-at: ""
deployed-at: ""
deployed-env: ""
---
# Grouping Task Lists

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| 1 | PRD | TASK-5 (v1) | pasted | 2026-07-08 |

## Problem Statement

Users viewing the task list see a single flat list regardless of how many tasks they have or what those tasks are about. As the list grows, it becomes hard to visually separate work from personal from errands, and users lose the sense of "what's on my plate in each area." Tasks already have a `category` field (work / personal / errands / uncategorized), but that structure isn't reflected in how the list is presented — users have to scan the whole list to mentally group things themselves.

We want the task list to be visually organized by category so users can quickly see what's in each area of their life, and collapse categories they aren't focused on right now.

## User Stories

### US-1: As a user viewing my task list, I want tasks grouped visually by category so that I can quickly see what's on my plate in each area

Status: pending
Repos: frontend
PR-frontend:

**Scenarios:**
- **BDD-1** **GIVEN** I have tasks across multiple categories (work, personal, errands, and some uncategorized) **WHEN** I load the task list page **THEN** tasks are rendered under group headers in the fixed order Work → Personal → Errands → Uncategorized, with each header showing the category name and a count (e.g. "Work (5)")
- **BDD-2** **GIVEN** I have zero tasks in the "Errands" category **WHEN** I load the task list **THEN** the "Errands" group header is not rendered at all
- **BDD-3** **GIVEN** I have applied a sort (e.g. by title) and/or a status filter **WHEN** the list renders with grouping on **THEN** the sort is applied within each group and the status filter is applied globally before grouping; sorting by `category` is not offered as an option while grouping is on
- **BDD-4** **GIVEN** I am viewing the task list **WHEN** I edit a task's category (directly or via bulk category update) **THEN** the task moves to its new group immediately on re-render (optimistic, matching the existing task-list pattern for other field edits — server rejection reverts via the existing rollback behavior), the source group's count decrements, and the destination group's count increments — even if the destination group is currently collapsed (in which case the task is not visible but the count reflects it)
- **BDD-5** **GIVEN** I have zero tasks total **WHEN** I load the task list **THEN** the existing empty state is shown and no group headers are rendered
- **BDD-6** **GIVEN** a status filter is active and only some tasks in each category match **WHEN** the list renders **THEN** each visible group header's count reflects only the filtered tasks (e.g. "Work (2)" when 2 of 5 work tasks match the filter), consistent with "filter globally, then group"

**Notes:** First story — owns all frontend scaffolding for the grouping component, the group-header disclosure widget, and the localStorage persistence hook used in US-2. Grouping is purely client-side off the existing `category` field on `Task` in the `/tasks` response; no API changes. When grouping is on, the "sort by category" option in the sort control should be hidden or disabled since the group order already imposes a category ordering.

**Category value shape (important):** The API's `TaskCategory` enum is `'work' | 'personal' | 'errands'`, and `Task.category` is `TaskCategory | null`. There is no `'uncategorized'` string value — tasks with no category have `category === null`. The frontend synthesizes the "Uncategorized" header label for the `null` bucket. Additionally, defensively normalize category values to lowercase before bucketing, because the API has observed case inconsistency across endpoints (`POST /tasks` returns lowercase; `POST /tasks/batch-update-category` tests use capitalized values like `'Work'`). Investigating/fixing that API inconsistency is out of scope for this feature.

### US-2: As a user, I want to collapse and expand category groups and have that state remembered so that I can focus on the areas I care about right now

Status: pending
Repos: frontend
PR-frontend:

**Scenarios:**
- **BDD-7** **GIVEN** I am visiting the task list for the first time (no prior collapse state stored) **WHEN** the list renders **THEN** all groups are expanded by default
- **BDD-8** **GIVEN** I am viewing the task list with all groups expanded **WHEN** I click a group header (e.g. "Work (5)") **THEN** only that group collapses, its tasks are hidden, its header count still reads "(5)", its visible expand/collapse affordance (chevron) updates to reflect the collapsed state, and other groups remain expanded
- **BDD-9** **GIVEN** I have collapsed the "Work" group **WHEN** I reload the page **THEN** the "Work" group is still collapsed and other groups retain their prior expanded/collapsed state, restored from localStorage
- **BDD-10** **GIVEN** localStorage is unavailable (private mode / disabled / quota exceeded) or contains a corrupted value for the collapse state **WHEN** the list renders **THEN** the app silently falls back to the default (all expanded), logs a diagnostic message to the console, and continues to function; toggling still works for the current session (in-memory only when unavailable; overwrites the corrupted value when writable)
- **BDD-11** **GIVEN** I navigate to the task list using only the keyboard **WHEN** I focus a group header and press Enter or Space **THEN** the group toggles between collapsed and expanded, the header exposes `aria-expanded` reflecting the new state and `aria-controls` pointing at the group's task container, the visible chevron affordance rotates/swaps to match, and focus remains visibly on the header
- **BDD-12** **GIVEN** I have collapsed the "Work" group and then delete the last remaining Work task **WHEN** the list re-renders **THEN** the "Work" header disappears (per BDD-2) but its collapsed-state entry remains in localStorage; **AND WHEN** I later create a new task with category "work" **THEN** the "Work" group reappears in its previously collapsed state

## Constraints

| # | Category | Requirement | Verification |
|---|----------|-------------|--------------|
| C1 | Accessibility | Group headers are implemented as disclosure widgets meeting the inherited accessibility baseline: operable via keyboard (Enter/Space toggle, Tab reachable), correct ARIA (`aria-expanded`, `aria-controls`), a visible focus indicator, **and a visible expand/collapse affordance (e.g. chevron icon) that visually reflects the current state** — collapsed-vs-expanded must not be conveyed by `aria-expanded` alone. | Automated a11y test (axe or equivalent) on the task list page, a keyboard-only interaction test covering BDD-11, and a visual/DOM assertion that the chevron affordance changes with state (BDD-8, BDD-11). |
| C2 | Compatibility | Grouping is purely client-side off the existing `category` field on `Task` (values `'work' \| 'personal' \| 'errands' \| null`); no changes to the `/tasks` API contract or any other endpoint. | Contract diff against `contracts/tasks-api.json` shows zero changes; no new network calls introduced by this feature. |
| C3 | Operational | localStorage failures (unavailable, quota, corrupted value) must never break the task list; the UI degrades to in-memory defaults and logs a diagnostic. | Unit tests that stub `localStorage` to throw on read/write and to return malformed JSON, asserting the list still renders with all groups expanded (BDD-10). |
| C4 | Testing | Every BDD-N scenario in this spec has a corresponding named test in the frontend test suite referencing its BDD ID, per the inherited testing baseline. | `relay verify` coverage gate; test names include the BDD-N identifiers. |
| C5 | Security | No new user input is sent to the server; the only new persisted data is a UI-only collapse-state object in localStorage, which must be parsed defensively (schema-validated, corrupted values discarded) per the inherited security baseline. | Unit test feeds hand-crafted malformed JSON into the localStorage key and asserts the app resets to defaults without throwing. |
| C6 | Robustness | The grouping component normalizes category values to lowercase before bucketing, to tolerate observed case inconsistency across API endpoints (lowercase from `POST /tasks`, capitalized from `POST /tasks/batch-update-category`). Any unknown category string after normalization is bucketed under Uncategorized rather than crashing. | Unit test feeds a task list containing mixed-case (`'Work'`, `'work'`, `'WORK'`), unknown (`'foo'`), and `null` categories, and asserts all end up in the correct bucket (mixed-case → Work; unknown and null → Uncategorized). |
| C7 | Performance | No performance guarantees beyond typical list sizes (~hundreds of tasks). Virtualization / windowing of long groups is out of scope for v1; the implementation should not do anything actively pathological (e.g. O(n²) grouping), but no benchmarks are required. | Code review; no dedicated perf test. |

## Out of Scope

- User-defined groups or lists (creating named groups like "Q4 planning" and assigning tasks to them) — this feature is visual grouping only, off the existing `category` enum.
- Grouping by any field other than `category` (e.g. status, createdAt bucket, custom).
- A "Group by …" on/off toggle — grouping is always on in v1.
- "Expand all" / "Collapse all" affordances.
- Server-side persistence of collapse state (no user-preferences API, no sync across devices/browsers) — localStorage only.
- Cross-tab synchronization via the `storage` event — each open tab manages its own collapse state; last-write-wins on reload is acceptable.
- Any "N groups collapsed" summary indicator — collapsed header counts are the only signal.
- Drag-and-drop between groups to reassign category.
- Animation/transition when a task moves between groups on category change — v1 re-renders without a dedicated animation.
- Special-casing the single-populated-group scenario (no "hide the header when only one group is populated" behavior — the header renders normally).
- Cleanup of stale localStorage collapse entries when a group becomes empty — the entry is retained so the group reappears in its remembered state if a task in that category returns later.
- Virtualization / windowing of long groups (see C7).
- Investigating or fixing the observed API case inconsistency in category values across endpoints — the frontend normalizes defensively (see C6), but any server-side fix is a separate task.
- Any backend/API changes.

## Implementation Log

_Implementation learnings (Decisions, Discoveries, Spec gaps) live in the sibling file `grouping-task-lists-feature-impl-log.md`, appended by `post-agent.sh` after each PR merge. Read that file before claiming a downstream story-repo._

## Readiness Checklist

- [x] Problem statement is concrete and user-facing
- [x] At least one user story defined
- [x] Each user story declares Status, Repos, and ≥1 BDD-N scenario
- [x] BDD-N IDs are sequential and unique across the spec
- [x] Constraints section addresses NFRs (or explicit `N/A` row with rationale)
- [x] Out of Scope section is explicit (no empty placeholder)
