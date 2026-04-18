---
title: "Task List Category Labels"
lifecycle: draft
execution: autonomous
model: ""
priority: medium
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
# Task List Category Labels

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| S1 | conversation | interview transcript (planner session) | Product + Planner | this session |
| S2 | code reference | `frontend/tests/App.test.jsx` (existing `category-badge-{id}` tests) | Frontend repo | this session |
| S3 | contract | `contracts/tasks-api.json` (`TaskCategory` enum, `Task.category` field) | API repo | this session |

## Problem Statement

Task list users currently have no at-a-glance visual indicator of a task's category when scanning the list. The existing UI exposes category editing via clickable pills (set/unset) and filtering via a filter bar, but when simply scanning tasks to find context ("which of these are work items vs. errands?"), users have to look at the pill row or the filter state to figure it out. We need a passive, read-only visual label on each task row that communicates its category instantly through color and text, so users can triage and scan their list faster without needing to interact with the category controls.

## User Journey

_Happy path:_

1. User opens the task list page → System renders the list of tasks as usual.
2. For each task that has a category assigned (`work`, `personal`, or `errands`), the system displays a small colored badge next to the task title showing the capitalized category name (e.g., "Work"). The badge background color matches the existing category color tokens used elsewhere in the app (the settable category pills).
3. For each task with no category (`category: null`), no badge is rendered — the task row shows only the title.
4. User visually scans the list and can identify each task's category instantly from the badge color and text without interacting with any control.
5. User changes a task's category using the existing settable category pills (out of scope for this feature but relevant to the journey) → The badge updates to reflect the new category on the next render. If category is cleared to null, the badge disappears.

_Error paths and edge cases:_

1. Task has no category (`null`) → No badge rendered (not an error, but the explicit empty state).
2. Task has a category value not in the enum (defensive) → No badge rendered; UI does not crash.
3. Task title is very long and row is narrow → Badge remains visible (does not get pushed off-screen or clipped invisibly); title truncates or wraps before the badge is sacrificed.
4. Task category is updated via existing pill controls → Badge re-renders to match without a full page reload.

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | Each task row in the task list shall display a read-only colored badge showing its category when `task.category` is exactly one of the valid enum values (`"work"`, `"personal"`, or `"errands"`). | S1, S2, Round 2 refinement (E2, E3) | High | Matches existing `category-badge-{id}` test expectations. |
| R2 | When `task.category` is `null`, `undefined`, or any value not strictly equal to a valid enum value, no badge shall be rendered for that task. | S1, S2, Round 2 refinement (E2, E3) | High | Covers loading states, schema drift, and contract violations. |
| R3 | The badge shall display the capitalized category name as text (e.g., `work` → "Work"). | S1 | High | |
| R4 | The badge background color shall match the existing category color tokens used by the settable category pills, ensuring visual consistency across the task row. | S1 | High | Reuse CSS tokens; do not introduce new colors. |
| R5 | The badge shall be positioned inline, to the right of the task title. | S1 | High | |
| R6 | The badge shall be non-interactive (no click handlers, no hover menus). Editing category remains via the existing pill controls. | S1 | High | Scope guardrail. |
| R7 | The badge shall have an accessible `data-testid="category-badge-{taskId}"` attribute to support existing and future tests. | S2 | High | Aligns with tests already in `App.test.jsx`. |
| R8 | The badge shall have sufficient color contrast for text readability (WCAG AA for small text). | S1 (UX norm) | Med | Implementer to verify contrast against chosen tokens. |
| R9 | The badge shall update reactively when the task's category changes via other controls (e.g., settable pills, bulk assign). | S1 | High | Standard React re-render; no extra fetching required. |
| R10 | Feature is frontend-only; no API or contract changes. | S1, S3 | High | `Task.category` already exists in contract. |
| R11 | The badge shall be a pure derived view of `task.category` at render time, with no independent **stateful** caching (no `useState`, no `useRef` holding category value, no debouncing of updates). Standard referentially-transparent memoization primitives (`React.memo`, React compiler optimizations) are permitted. Task deletion, restoration, optimistic rollback, rapid category changes, and concurrent updates from other tabs/devices are handled entirely by the parent task row's existing lifecycle. | Round 1 refinement (A1, A2); clarified in Round 4 (I2) | High | Prevents stale-state bugs without blocking legitimate perf tools. |
| R12 | This feature is purely additive: it shall not modify, hide, or replace the existing settable category pills, category filter bar, bulk-assign category picker, or analytics category usage. | Round 1 refinement (A3) | High | Scope guardrail against conflating the read-only badge with existing editing controls. |
| R13 | When a category PATCH fails and the parent row rolls back optimistic state, the badge shall inherit that rollback via normal re-render. The badge shall not display its own error state (no red border, no error icon, no tooltip). Transient flashing through intermediate values during failed requests is acceptable. | Round 2 refinement (E1) | High | Error signaling is owned by the existing pill controls, not the badge. |
| R14 | The badge shall be implemented as a standalone React component (e.g., `CategoryBadge`) to support future reuse without refactoring. Category-to-color and category-to-label mappings may remain local to the component; they shall not be extracted into a shared tokens/constants module until a second consumer requires them. | Round 4 refinement (I1) | High | Balances reusability against premature generalization; respects R12's "purely additive" guardrail by avoiding refactors of existing pill code. |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| — | No conflicts detected between sources. | N/A |

## Open Questions

- [ ] None blocking. Implementer may choose exact badge padding/font-size to match existing pill visual language — treated as implementation detail.

## Acceptance Criteria

- [ ] A task with `category: "work"` renders a badge with `data-testid="category-badge-{id}"` containing the text "Work" next to its title.
- [ ] A task with `category: "personal"` renders a badge containing "Personal".
- [ ] A task with `category: "errands"` renders a badge containing "Errands".
- [ ] A task with `category: null` renders no `category-badge-{id}` element.
- [ ] A task with `category: undefined` (e.g., during loading or partial data) renders no `category-badge-{id}` element.
- [ ] A task with a malformed `category` value — empty string, wrong case (e.g., `"Work"`), non-string type, array, or object — renders no `category-badge-{id}` element and does not crash the UI.
- [ ] The render guard uses strict equality against the known enum values (`"work"`, `"personal"`, `"errands"`), not a truthy check.
- [ ] The badge background color matches the category color tokens already used by the settable category pills (consistency check).
- [ ] The badge is positioned inline to the right of the task title.
- [ ] The badge is not clickable — clicking it does not trigger category editing or any other action.
- [ ] When a task's category is changed via existing controls (settable pill or bulk assign), the badge re-renders to match the new value without a page reload.
- [ ] When a task's category is cleared to null via existing controls, the badge disappears.
- [ ] When a category PATCH fails and the row rolls back, the badge naturally reverts with the row — no badge-specific error state (no red border, no error icon, no tooltip) is rendered.
- [ ] The badge holds no independent **stateful** caching (no `useState`, no `useRef` for category, no debouncing); `React.memo` / compiler memoization are permitted.
- [ ] The badge is implemented as a standalone React component (e.g., `CategoryBadge.jsx`), not as an inline render helper buried in a larger component.
- [ ] The existing settable category pills, category filter bar, bulk-assign picker, and analytics category usage are unchanged by this feature.
- [ ] No API contract changes; no new endpoints called; no new fields consumed.
- [ ] Badge text meets WCAG AA contrast against its background color.
- [ ] Existing tests referencing `category-badge-{id}` pass.

## Behavioral Scenarios

### Happy Path

- **BDD-1:** **GIVEN** the task list contains a task with `category: "work"` **WHEN** the user views the task list **THEN** a badge with `data-testid="category-badge-{id}"` displaying the text "Work" appears inline next to that task's title, styled with the work-category color token.
- **BDD-2:** **GIVEN** the task list contains a task with `category: "personal"` **WHEN** the user views the task list **THEN** a badge displaying "Personal" appears next to that task's title with the personal-category color token.
- **BDD-3:** **GIVEN** the task list contains a task with `category: "errands"` **WHEN** the user views the task list **THEN** a badge displaying "Errands" appears next to that task's title with the errands-category color token.
- **BDD-4:** **GIVEN** a task with `category: null` is displayed in the list **WHEN** the user views the task list **THEN** no `category-badge-{id}` element is rendered for that task.
- **BDD-5:** **GIVEN** a task currently shows a "Work" badge **WHEN** the user changes its category to "Personal" via the existing settable pill controls **THEN** the badge updates to display "Personal" with the personal-category color without a page reload.
- **BDD-6:** **GIVEN** a task currently shows a "Work" badge **WHEN** the user clears the category via the existing pill controls **THEN** the badge is removed from the row.

### Edge Cases

- **BDD-7:** **GIVEN** a task row in a narrow viewport whose title text is long **WHEN** the user views the row **THEN** the badge remains visible (the title truncates or wraps rather than the badge being clipped off-screen).
- **BDD-8:** **GIVEN** a task whose `category` value is malformed — e.g., an empty string, wrong case (`"Work"` instead of `"work"`), a number, an array, or an object — **WHEN** the list renders **THEN** no badge is rendered for that task and the UI does not error or crash. The render guard uses strict equality against the known enum values, not a truthy check.
- **BDD-9:** **GIVEN** the user clicks directly on a category badge **WHEN** the click event fires **THEN** no category edit action, navigation, or other side effect occurs (badge is purely decorative).
- **BDD-10:** **GIVEN** a task is removed from the list (via deletion or optimistic rollback) **WHEN** the parent row unmounts or re-renders **THEN** the badge follows the row's lifecycle naturally — it has no independent state to clean up.
- **BDD-11:** **GIVEN** the user rapidly toggles a task's category through the existing pill controls (e.g., Work → Personal → None → Work) **WHEN** each state update propagates **THEN** the badge at any given render reflects the current value of `task.category`, with no debouncing or intermediate badge state.
- **BDD-12:** **GIVEN** a user clicks a category pill triggering an optimistic update **AND** the PATCH request subsequently fails (network error, 500, or 409) **WHEN** the parent row rolls back `task.category` to its previous value **THEN** the badge re-renders naturally to reflect the rolled-back value, with no badge-specific error state (no red border, no error icon, no tooltip). Transient flashing through the optimistic value is acceptable.
- **BDD-13:** **GIVEN** the task list page is loading and tasks have not yet arrived (or have partial data with `category: undefined`) **WHEN** the list renders during this window **THEN** no badge is rendered for tasks lacking a valid category value. No skeleton, shimmer, or placeholder is rendered in place of the badge.

## Out of Scope

- Editing category via the badge itself (editing remains via existing settable pills).
- Introducing new categories beyond the existing `work`/`personal`/`errands` enum.
- Backend/API changes of any kind (the `Task.category` field already exists).
- User-defined labels or tags (many-to-many tagging system).
- Icons inside the badge (text-only in this iteration).
- Badge appearance on pages other than the main task list (e.g., analytics, detail views) — unless trivially rendered by shared components.
- Filter-by-clicking-badge interaction.
- Color customization / user-selected category colors.
- Modifying, hiding, or replacing any existing category-related UI (settable pills, filter bar, bulk-assign picker, analytics). The badge is purely additive.
- Animations, fade transitions, undo toasts, or placeholder elements when a badge appears or disappears.
- Stateful local caching, debouncing, or memoization-with-state specific to the badge. `React.memo` and compiler-level memoization are permitted; `useState`/`useRef` for category value are not.
- Badge-specific error UI (red border, error icon, error tooltip, etc.) when category PATCH requests fail. Error signaling is owned by the existing pill controls.
- Skeleton or shimmer placeholders for the badge during loading states. Loading-state presentation is owned by the task row's existing skeleton (if any).
- Dev-mode logging or telemetry for malformed `category` values. Schema validation is owned elsewhere (API layer / type definitions).
- Extraction of category-to-color or category-to-label mappings into a shared tokens/constants module. Mappings remain local to the badge component until a second consumer requires them.
- Virtualization, pagination, or other task-list scalability optimizations. If performance regressions emerge at high task counts (e.g., 1,000+), optimization is owned by the task list component, not this feature.

## Refinement Log

### Round 1: Assumptions

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | **Deletion behavior:** When a task is deleted (or optimistically deleted and rolled back), the badge needs no special cleanup or state handling — it just disappears/reappears with the parent row. | Yes | **Confirmed.** The badge holds no independent state; it is a pure derived view of `task.category`. Deletion, restoration, and rollback are handled by the parent task row's existing lifecycle. Captured in **R11** and **BDD-10**. |
| A2 | **Edge states (empty / maximum / concurrent):** The badge needs no debouncing, caching, or special handling for rapid category toggling, pagination, virtualization, or cross-tab updates — it simply reflects whatever `task.category` the parent row renders. | Yes | **Confirmed.** Kept simple: no local state, no debouncing, no caching. Badge reflects current `task.category` at render time. Captured in **R11** and **BDD-11**. |
| A3 | **Interaction with existing features:** The badge is purely additive alongside the existing settable category pills, filter bar, bulk-assign picker, and category analytics — it does not replace, hide, or modify any of them, even though the settable pill row already visually indicates the current category. | Yes | **Confirmed.** Both coexist. Settable pills serve editing; badge serves scanning. Redundancy is intentional and serves different UX tasks. Captured in **R12**, a new acceptance criterion, and a new Out of Scope bullet locking down existing category-related UI as untouched. |

### Round 2: Edge Cases

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | **Race condition — PATCH failure with optimistic rollback:** User clicks a category pill, optimistic update flashes the badge to the new value, PATCH fails, row rolls back. What does the badge show, and does it need a badge-specific error state? | R13, BDD-12, new Out of Scope bullet, new acceptance criterion | **Confirmed inherit-from-parent.** Badge follows the parent row's rollback via normal re-render. No badge-specific error UI (no red border, no icon, no tooltip). Transient flashing through optimistic value is acceptable. Error signaling is owned by the existing pill controls. |
| E2 | **Boundary — initial load / partial data:** During loading before tasks arrive, `task.category` may be `undefined` or the row may not yet exist. Should the badge render a skeleton/shimmer/placeholder? | R1 (tightened), R2 (tightened), BDD-13, new acceptance criterion, new Out of Scope bullet | **Confirmed follow-parent.** `undefined` treated the same as `null` → no badge. No skeleton, shimmer, or placeholder rendered in place of the badge. Loading-state presentation owned by the task row's existing skeleton (if any). Tightened R1/R2 to use strict enum equality. |
| E3 | **Error state — malformed category value from API:** API returns an unexpected value (empty string, wrong case like `"Work"`, numbers, arrays, objects). A naive `if (task.category)` truthy check would try to render broken badges for some of these. | R1 (tightened), R2 (tightened), BDD-8 (tightened), new acceptance criteria | **Confirmed strict-equality guard.** Render only when `task.category` is strictly equal to one of `"work"`, `"personal"`, `"errands"`. All other values (empty string, wrong case, non-string types, etc.) render no badge and do not crash. No dev-mode logging — schema validation is owned elsewhere. |

### Round 3: Scope Boundaries

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|

### Round 4: Architecture Review

| # | Implication | Impact Area | Resolution |
|---|------------|-------------|------------|
| I1 | **Component placement & code organization:** The badge lives in the frontend codebase; it can be an inline helper in `App.jsx`, a standalone component, or a fully generalized shared component with extracted color tokens. Choice affects future reusability vs. risk of premature generalization and scope creep into existing pill code. | Frontend code organization; R7 (test-id encapsulation); R12 (purely-additive guardrail) | **Confirmed standalone component, local mappings.** Badge is implemented as a standalone `CategoryBadge` React component to support future reuse without refactoring. Category-to-color and category-to-label mappings remain local to the component; no shared tokens/constants module extraction until a second consumer needs it. Captured in **R14**, new acceptance criterion, new Out of Scope bullet. |
| I2 | **Scalability at 10x current volume:** At 1,000–5,000 tasks per list, per-row badge rendering cost is nontrivial in aggregate. R11 as originally worded forbade all caching/memoization, which could be over-interpreted to block `React.memo` or React compiler optimizations that are legitimate perf tools. | Rendering performance at high task counts; R11 wording | **Confirmed defer, clarify R11.** Badge render cost is trivial (one `<span>` + text); dominant perf concern at scale is the list itself (virtualization), which is upstream of this feature. Softened **R11** to forbid only *stateful* caching (`useState`, `useRef` for category, debouncing) while permitting `React.memo` and compiler memoization. Added Out of Scope bullet noting that list virtualization/pagination is owned by the task list component, not this feature. |

**Architecture diagrams consulted:** None. This feature is a frontend-only, purely-additive presentational component with no changes to data flow, API surface, service topology, or infrastructure. No diagram was required for review.

**Diagrams requiring update after ship:** None. The feature introduces no new services, no new data flows, no new integration points, and no changes to existing architectural boundaries.

### Round 5: PII / Compliance Review

| # | Data Element | Classification | Handling Requirement |
|---|-------------|---------------|---------------------|
| P1 | `task.category` (values `"work"`, `"personal"`, `"errands"`, or `null`) — the only data element this feature renders. | **internal** (per `contracts/tasks-api.json`: `TaskCategory` and `Task.category` both carry `x-data-classification: internal`). | **N/A — no new handling requirements.** Rationale: (a) The category is a fixed 3-item enum with no free-text, no user identifiers, and no sensitive semantic payload. (b) The badge introduces zero new data exposure: the same value is already visible to the same authenticated user via existing settable pills, filter bar, bulk-assign picker, and analytics pie chart. The badge is a secondary visual presentation of data the user is already authorized to see. (c) Per R11, R13, and Out of Scope bullets, the badge has no logging, telemetry, persistence, network calls, or dev-mode warnings. No authentication, authorization, cross-user, or cross-tenant concerns apply. No new requirements, ACs, or BDD scenarios are required. |

### Round 6: UX & Interaction Review

| # | Concern | Category | Resolution |
|---|---------|----------|------------|

## Readiness Checklist

- [ ] All High-confidence requirements have acceptance criteria
- [ ] No unresolved conflicts remain
- [ ] Open questions are non-blocking or have owners
- [x] At least 3 assumptions explicitly challenged and resolved
- [x] At least 3 edge cases explicitly addressed
- [ ] Out of Scope section reviewed via scope boundary probe
- [x] At least 2 architectural implications reviewed
- [x] PII and sensitive data elements identified with handling requirements (or explicit N/A)
- [ ] At least 2 UX/interaction concerns reviewed (or explicit N/A for non-UI features)
- [x] All User Journey steps and edge cases have corresponding BDD-N scenarios
