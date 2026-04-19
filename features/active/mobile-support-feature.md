---
title: "Mobile Responsive Web Support"
lifecycle: active
execution: supervised
model: ""
priority: medium
dimensions:
  - assumptions
  - edges
  - ux
  - scope
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
# Mobile Responsive Web Support

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| 1 | conversation | interview transcript (planner) | user | interview session |

## Problem Statement

The task tracker web app is currently designed for desktop viewports. Users who open it on a phone browser encounter cramped layouts, small touch targets, hover-only affordances, and UI patterns (side panels, multi-column tables, wide charts) that do not adapt to narrow screens. This creates friction for anyone trying to review, update, or comment on tasks while away from their desk. We want the existing browser app to be fully usable on a phone, across every surface of the app, without building a separate native mobile app.

## User Journey

### Happy Path

The canonical flow is: a user opens the app on their phone, finds a task, updates its status, and adds a comment.

1. **User opens the app on a phone browser (viewport < 768px)** → System renders the mobile layout: a single-column, stacked list of task cards. Each card shows the task title (truncated to 2 lines with ellipsis), status, category, and a relative timestamp (e.g. "2h ago"). Descriptions are not shown in the list.
2. **User wants to narrow the list by status** → User taps the "Filters" button in the header → System opens a bottom sheet with checkboxes for status and category. User selects filters and taps "Apply" → Bottom sheet closes and the list re-renders with active filters indicated on the Filters button.
3. **User taps a task card** → System navigates to a full-screen task detail view (not a side panel). A back button in the header returns to the list. The detail view shows the full title, full description, status, category, absolute timestamps, and tabbed or collapsible sections for comments and history.
4. **User updates the task status** → User taps the status control → System presents status options in a touch-friendly control (e.g. bottom sheet or native select) → User picks a new status → System PATCHes the task and updates the detail view in place.
5. **User adds a comment** → User taps the comment input / "Add comment" affordance → System opens a full-screen form modal with a sticky header containing Cancel and Save actions. Input is sized for touch and avoids hover-only affordances → User types and taps Save → System POSTs the comment and returns to the detail view with the new comment visible.
6. **User returns to the list and creates a new task** → User taps the back button → System returns to the list. User taps the floating action button (FAB) in the bottom-right → System opens a full-screen create-task modal with the same sticky-header pattern → User fills in title and optional fields and taps Save → System creates the task and returns the user to the list with the new task visible.
7. **User batch-deletes a few tasks** → User long-presses a task card → System enters batch-select mode: selected count and batch actions (delete, assign category) appear in a sticky bottom action bar with large (≥44×44px) touch targets; each card now has a selection checkbox → User taps additional cards to select them and taps "Delete" in the bottom bar → System confirms and calls the batch-delete endpoint → Selected tasks disappear from the list and select mode exits.
8. **User checks analytics** → User navigates to the analytics screen → System renders charts stacked vertically, each full-width: counts by status, 7-day completions, avg time in status, completed tasks by category. The CSV export action is available via a "⋮" overflow menu in the header.

### Error Paths and Edge Cases

1. **User opens the app on a viewport narrower than 360px** → Layout still renders without horizontal scroll on primary content; minor visual compromises are acceptable but nothing becomes unusable or clipped.
2. **User rotates the phone between portrait and landscape** → Layout reflows without losing state (selected filters, open modal, scroll position within reason). If viewport crosses the 768px breakpoint (e.g. large phone in landscape), the desktop layout is used.
3. **User taps a relative timestamp on a list card** → Nothing happens (relative timestamps are not interactive on mobile list views). **User long-presses a relative timestamp** → System reveals the absolute timestamp (tooltip-equivalent).
4. **User tries to hover-reveal a row action on mobile** → No hover state exists on touch; all row actions are always visible as icon buttons, or collapsed behind a "⋮" overflow button on the row if the row would otherwise be too crowded.
5. **A task has a very long title (near 255 chars) or description (near 2000 chars)** → List cards truncate the title to 2 lines with ellipsis; descriptions are not shown in the list. Detail view shows the full content, wrapping normally, without horizontal overflow.
6. **User opens the app on the latest two major versions of mobile Safari (iOS) or Chrome (Android)** → Everything works. Older browsers are not a support target; behavior is undefined but we do not deliberately break them.
7. **User opens the app on a viewport ≥ 768px (tablet or desktop)** → Existing desktop layout is used unchanged. No separate tablet layout.
8. **User opens the on-screen keyboard while a full-screen modal is open** → Sticky header actions (Save/Cancel) remain reachable; input being edited is not hidden behind the keyboard.

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | At viewport widths `< 768px`, the app renders a mobile-optimized layout; at `≥ 768px`, the existing desktop layout is used unchanged. | S1 | High | No separate tablet breakpoint. |
| R2 | The mobile layout must be usable (no horizontal scroll on primary content, no clipped controls) down to a minimum viewport width of 360px. | S1 | High | |
| R3 | Support target: latest two major versions of mobile Safari (iOS) and Chrome (Android). | S1 | High | |
| R4 | Task list on mobile renders as a single-column stack of cards; each card shows title (truncated to 2 lines), status, category, and relative timestamp. Description is not shown in the list. | S1 | High | |
| R5 | Tapping a task card on mobile opens a full-screen task detail view (not a side panel), with a back button in the header. | S1 | High | |
| R6 | Task detail view on mobile shows full title, full description, absolute timestamps, and presents comments and history as tabs or collapsible sections rather than side-by-side. | S1 | High | Tabs vs. collapsible is an implementation detail. |
| R7 | Create and edit task flows on mobile open as full-screen modals with a sticky header containing Save and Cancel actions. | S1 | High | |
| R8 | A floating action button (FAB) in the bottom-right of the task list triggers new-task creation on mobile. | S1 | High | |
| R9 | Batch-select mode on mobile is entered by long-pressing a task card. Selection checkboxes appear on cards and a sticky bottom action bar shows selected count plus batch actions (delete, assign category). | S1 | High | |
| R10 | Status and category filters on mobile collapse into a single "Filters" button that opens a bottom sheet with checkboxes; active filters are indicated on the button. | S1 | High | |
| R11 | Analytics charts on mobile stack vertically, each full-width, using the charting library's responsive sizing. No alternative chart representations are built. | S1 | High | |
| R12 | The CSV export action on mobile analytics moves into a "⋮" overflow menu in the header. | S1 | High | |
| R13 | All interactive controls on mobile have a minimum touch target of 44×44 CSS pixels. | S1 | High | Matches iOS HIG / Material guidance. |
| R14 | Relative timestamps are used on mobile list views; absolute timestamps are used in detail views. Long-press on a relative timestamp reveals the absolute timestamp. | S1 | High | |
| R15 | Hover-only affordances (tooltips, row-hover action reveals, right-click menus) are replaced on mobile: tooltips become long-press, row actions are always visible (or collapsed behind a "⋮" overflow if crowded), and right-click menus become "⋮" overflow buttons. | S1 | High | |
| R16 | History and comments lists on mobile stack each entry's fields vertically with clear labels; no multi-column table rows. | S1 | High | |
| R17 | No API, schema, contract, or data-model changes are introduced by this feature. | S1 | High | Frontend-only scope. |
| R18 | Every existing app surface (task list, task detail, create/edit, batch actions, filters/sort, comments, history, analytics, CSV export) is covered by the responsive pass. | S1 | High | "All parts of the app." |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| — | No conflicts — single source (planner interview). | N/A |

## Open Questions

- [ ] None blocking. Specific visual treatments (exact spacing, typography scale, FAB icon, tab vs. accordion for detail sections) are left to implementation within the patterns established here.

## Acceptance Criteria

- [ ] On a viewport `< 768px`, the task list renders as a single column of stacked cards with title truncated to 2 lines, no description, and relative timestamps.
- [ ] On a viewport `< 768px`, tapping a task card navigates to a full-screen detail view with a back button; the detail view shows full title, full description, absolute timestamps, and tabbed/collapsible comments and history.
- [ ] On a viewport `< 768px`, the "New Task" action is a FAB in the bottom-right; create/edit forms open as full-screen modals with a sticky header containing Save and Cancel.
- [ ] On a viewport `< 768px`, long-pressing a task card enters batch-select mode; a sticky bottom action bar shows selected count and batch actions with ≥44×44px touch targets.
- [ ] On a viewport `< 768px`, filters collapse into a "Filters" button that opens a bottom sheet; active filters are indicated on the button.
- [ ] On a viewport `< 768px`, analytics charts stack vertically and each is full-width; CSV export is in a "⋮" overflow menu.
- [ ] On a viewport `< 768px`, history and comments render as vertically stacked entries with labeled fields (no multi-column table rows).
- [ ] All mobile layouts render without horizontal scroll on primary content and without clipped controls down to 360px viewport width.
- [ ] All interactive controls on mobile meet a ≥44×44 CSS px touch target.
- [ ] Long-pressing a relative timestamp on mobile reveals the absolute timestamp.
- [ ] At viewport `≥ 768px`, the existing desktop layout renders unchanged (visually and behaviorally equivalent to pre-feature).
- [ ] Manual verification passes on latest two major versions of mobile Safari (iOS) and Chrome (Android).
- [ ] No changes are made to API contracts, backend code, or data schemas.

## Behavioral Scenarios

### Happy Path

- **BDD-1:** **GIVEN** a user opens the app on a phone browser with viewport width `< 768px` **WHEN** the task list loads **THEN** the system renders a single-column stack of task cards, each showing the title truncated to 2 lines, status, category, and a relative timestamp, with no description shown.
- **BDD-2:** **GIVEN** the user is on the mobile task list **WHEN** the user taps the "Filters" button, selects a status in the bottom sheet that opens, and taps "Apply" **THEN** the bottom sheet closes, the list re-renders filtered to show only matching tasks, and the Filters button indicates an active filter.
- **BDD-3:** **GIVEN** the user is on the mobile task list **WHEN** the user taps a task card **THEN** the system navigates to a full-screen task detail view with a back button in the header, showing the full title, full description, absolute timestamps, and comments/history as tabs or collapsible sections.
- **BDD-4:** **GIVEN** the user is on the mobile task detail view **WHEN** the user taps the status control and picks a new status from the touch-friendly selector **THEN** the detail view updates in place to show the new status.
- **BDD-5:** **GIVEN** the user is on the mobile task detail view **WHEN** the user taps "Add comment", types text in the full-screen modal that opens, and taps "Save" in the sticky header **THEN** the modal closes and the new comment appears in the detail view.
- **BDD-6:** **GIVEN** the user is on the mobile task list **WHEN** the user taps the floating action button in the bottom-right, fills in a title in the full-screen create modal, and taps "Save" in the sticky header **THEN** the modal closes and the new task appears in the list.
- **BDD-7:** **GIVEN** the user is on the mobile analytics screen **WHEN** the screen renders **THEN** all charts (counts by status, 7-day completions, avg time in status, completed tasks by category) stack vertically, each full-width, and the CSV export action is accessible from a "⋮" overflow menu in the header.
- **BDD-8:** **GIVEN** a user opens the app at a viewport width `≥ 768px` **WHEN** any screen renders **THEN** the existing desktop layout is used unchanged.

### Edge Cases

- **BDD-9:** **GIVEN** a user is on a viewport width between 360px and 767px **WHEN** any screen renders **THEN** the mobile layout displays without horizontal scroll on primary content and without clipped controls.
- **BDD-10:** **GIVEN** a user rotates the phone between portrait and landscape **WHEN** the viewport changes without crossing 768px **THEN** the layout reflows, active filters and list scroll position are preserved, and if the new width crosses 768px the desktop layout is used.
- **BDD-11:** **GIVEN** a task has a 255-character title and a 2000-character description **WHEN** the task appears on the mobile list **THEN** the title is truncated to 2 lines with ellipsis and the description is not shown; **WHEN** the user opens the task detail **THEN** the full title and full description are shown and wrap without horizontal overflow.
- **BDD-12:** **GIVEN** a user is on a mobile list view with relative timestamps **WHEN** the user long-presses a relative timestamp **THEN** the system reveals the absolute timestamp in a small popover and the browser's native text-selection / copy-share menu does not appear.
- **BDD-13:** **GIVEN** a user is on any mobile screen with row-level actions **WHEN** the screen renders **THEN** all row actions are visible as icon buttons or collapsed behind a "⋮" overflow button on that row, never gated behind hover, and never positioned in the card's bottom-right quadrant where they would compete with the FAB.
- **BDD-14:** **GIVEN** a user has a full-screen create or edit modal open on mobile **WHEN** the on-screen keyboard opens **THEN** the sticky header Save/Cancel actions remain reachable and the focused input is not hidden behind the keyboard.
- **BDD-15:** **GIVEN** history and comments data for a task on mobile **WHEN** the detail view renders those sections **THEN** each entry is laid out as vertically stacked, clearly labeled fields rather than multi-column table rows.
- **BDD-16:** **GIVEN** the user has zero tasks on the mobile task list **WHEN** the list renders **THEN** the system shows a centered empty-state message with no separate in-body create CTA, and the FAB remains visible as the create affordance.
- **BDD-17:** **GIVEN** the user has active filters and no tasks match them on mobile **WHEN** the list renders **THEN** the system shows a "No tasks match these filters" message with a "Clear filters" action.
- **BDD-18:** **GIVEN** the user is on the mobile task list **WHEN** the list renders on a device with a bottom safe-area inset (e.g. iOS home indicator) **THEN** the FAB is positioned above the safe-area inset and the last card's controls are not occluded by the FAB.
- **BDD-19:** **GIVEN** the user has a full-screen modal open or the on-screen keyboard visible on mobile **WHEN** the view renders **THEN** the FAB is hidden or repositioned so it does not overlap the modal content or keyboard.
- **BDD-20:** **GIVEN** the user taps the FAB, Save, a task card, the status control, or Apply filters on mobile **WHEN** the first tap is registered **THEN** the control is immediately disabled until the resulting navigation, modal transition, or network response completes, so a rapid second tap produces no additional action.
- **BDD-21:** **GIVEN** the user is on the mobile full-screen task detail view **WHEN** the user triggers the OS/browser back gesture (iOS swipe-back or Android system back) **THEN** the system returns to the task list with prior scroll position preserved, identical to tapping the in-header back button, and does not exit the app.
- **BDD-22:** **GIVEN** the user has a full-screen create/edit/comment modal open on mobile **WHEN** the user triggers the OS/browser back gesture **THEN** the system behaves identically to tapping Cancel (including any unsaved-changes handling inherited from desktop) and does not exit the app.

## Out of Scope

- Native iOS or Android apps.
- Any API, contract, schema, or backend changes.
- Mobile-specific capabilities such as push notifications, offline sync, or mobile auth flows.
- A distinct tablet layout for viewports 768–1023px (tablets use the existing desktop layout). [B1]
- PWA / installable app: web app manifest, service worker, standalone display mode, offline shell, and install prompts. [B2]
- Mobile accessibility conformance work: WCAG 2.1 AA audit, VoiceOver/TalkBack pass, focus trapping in bottom sheets and full-screen modals, ARIA for FAB and overflow menus, color-contrast audit, reduce-motion support, and Dynamic Type / font-scaling support. Includes the mobile-introduced regressions around gesture-only long-press tooltips and modal focus management — all deferred to a dedicated a11y feature. [B3]
- Supporting browsers older than the latest two major versions of mobile Safari and Chrome.
- Alternative chart representations for small screens (e.g. sparklines instead of full charts).
- Redesigning the desktop layout or changing desktop behavior.
- Visual redesign / rebranding of the app beyond what is needed for responsive adaptation.
- Performance work beyond what naturally falls out of the responsive pass.
- Localization or RTL layout work.

## Refinement Log

### Round 1: Assumptions
_What does this spec assume but not explicitly state?_

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | Batch-select mode and a `POST /tasks/batch-delete` endpoint (plus batch assign-category) already exist on desktop, so mobile is just reskinning them — consistent with R17's "no API changes." | Yes | False assumption. Neither frontend batch-select UI nor the batch-delete/assign-category endpoints exist today. Mobile must track desktop feature parity, so batch operations are **deferred** out of this feature entirely and handled as a separate feature covering both surfaces. Remove batch-select from user journey step 7, R9, BDD-7, BDD-8, and the corresponding acceptance criterion. R17 (no API changes) is preserved. |
| A2 | Concurrency behavior when a task is deleted while its mobile full-screen detail view is open is a non-issue, even though the full-screen layout hides the list entirely (unlike desktop's side panel). | Yes | Out of scope for this feature. Mobile inherits whatever desktop does today on a 404 from PATCH/POST (generic error toast). Add an explicit one-line note in the spec: "Concurrency behavior (e.g. task deleted while detail view is open) is inherited from desktop and not altered by this responsive pass." No dedicated "task no longer exists" full-screen state. |
| A3 | The empty list state "just works" on mobile and needs no explicit treatment, even though the FAB may compete with an empty-state CTA and zero-tasks vs. filtered-empty are semantically distinct. | Yes | In scope. Add edge-case coverage distinguishing two cases: (a) **zero tasks** — show the same empty-state message desktop shows, centered, with **no separate in-body CTA** (the FAB already serves that purpose); (b) **filtered-empty** — show a distinct "No tasks match these filters" message with a "Clear filters" action. Add a corresponding BDD scenario and ensure both states render correctly down to 360px. |
| A4 | The FAB can be pinned to `bottom-right` without further specification and will never collide with iOS Safari's bottom chrome, the on-screen keyboard, toasts, or the last row of the list. | Yes | In scope. Add a requirement: the FAB respects `env(safe-area-inset-bottom)`; the task list has bottom padding equal to FAB height + safe-area inset so the last card's controls (including any per-row ⋮ overflow) are never occluded; the FAB is hidden or repositioned when a full-screen modal is open or the on-screen keyboard is visible. Add a matching edge case + BDD scenario. |
| A5 | Mid-flow crossings of the 768px breakpoint (e.g. rotating a large phone to landscape while a full-screen create-task modal is open and being typed into) are fully covered by BDD-12's "open modals and selected filters are preserved." | Yes | Out of scope. Only persisted/queryable state (active filters, selected task id, list scroll position within reason) is guaranteed across the breakpoint. Transient UI state — open modal contents, in-progress form input — **may be lost** when crossing 768px, and this is an accepted limitation of the responsive pass. No additional state-preservation work is specified. |


### Round 2: Edge Cases
_Stress-test the spec with edge cases. Reference the edge case library at `retrospectives/edge-case-library.md`._

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | Long-press on a relative timestamp collides with the browser's native text-selection / iOS callout gesture, so the user sees the copy/share menu instead of (or on top of) the absolute-timestamp tooltip. | R14, R15 | Scope `user-select: none` and `-webkit-touch-callout: none` to the relative-timestamp element only (not the rest of the card, so title/description text remains selectable). Bind a ~500ms long-press handler that shows a small popover with the absolute timestamp, dismissed on tap-outside or after a short timeout. Tap on the timestamp falls through to the card's tap target (opens detail), consistent with the rest of the card. |
| E2 | Rapid repeat taps on mobile controls (FAB, Save, Delete-confirm, task card, status control, Apply filters) cause stacked modals, duplicate POSTs, doubled history entries, or a second tap dismissing a modal that is still animating in. Touch UIs lack hover feedback, so users commonly double-tap when a first tap produces no immediate visual change. | R4, R5, R7, R8 | Codify a mobile-wide rule: any control that triggers navigation, opens a modal, or initiates a mutating network call is disabled (visually and functionally) from the moment it is tapped until the resulting transition or response completes. Applies to FAB, Save, Delete-confirm, card taps, status commits, and Apply filters. Add a matching requirement and BDD scenario. |
| E3 | A mutating action initiated from a full-screen mobile modal (POST comment, POST new task, PATCH status) fails due to slow cellular, offline, 5xx, or timeout. On mobile, losing thumb-typed input in a full-screen modal is more costly than on desktop, where the equivalent input lives in a side panel. | R7, R17 | Inherit desktop behavior entirely — no mobile-specific text preservation, loading indicators, or retry logic beyond what desktop already does. Consistent with Round 1 A2 ("concurrency / error behavior inherited from desktop") and R17 ("frontend-only, no backend changes"). Accepted limitation: full-screen modals on mobile may close and lose in-progress input on failure, same as desktop. Documented as a known scope boundary; not addressed by this feature. |

### Round 3: Scope Boundaries
_Propose adjacent features and confirm whether they are in or out of scope._

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | Dedicated tablet layout for viewports 768–1023px (hybrid two-column list/detail with touch-friendly targets) | Out | Preserves the single 768px breakpoint codified in R1. Tablet-in-landscape already gets desktop gracefully; tablet-in-portrait is a small slice of real usage. A third breakpoint roughly doubles design + QA surface and dilutes the phone-usability goal. Clean follow-up if demand emerges post-ship. |
| B2 | PWA / installable app (web app manifest, service worker, standalone display mode, offline shell, install prompt) | Out | Orthogonal to the "existing browser app fully usable on a phone" problem statement. Introduces service-worker caching strategy, cache invalidation on deploy, update prompts, and standalone-mode auth concerns that are not addressed by a responsive pass. Aligns with existing exclusions of native apps, offline sync, and push notifications. Layers cleanly on top of a responsive app later. |
| B3 | Mobile accessibility conformance — WCAG 2.1 AA audit, VoiceOver/TalkBack pass, focus trapping in bottom sheets and full-screen modals, ARIA for FAB and overflow menus, color-contrast audit, reduce-motion and Dynamic Type / font-scaling support | Out | Deferred to a dedicated accessibility feature covering desktop and mobile together. Includes the two mobile-introduced regressions (gesture-only long-press tooltips invisible to assistive tech; modal/bottom-sheet focus management) — both deferred with the rest of the a11y work rather than partially handled here. R13 (≥44×44px touch targets) remains the only a11y-adjacent requirement in this feature. |

### Round 4: Architecture Review
_Challenge architectural implications: new services, API changes, scalability, dependencies, breaking changes._

| # | Implication | Impact Area | Resolution |
|---|------------|-------------|------------|
| AR1 | | [infra/API/perf/deps] | |

**Architecture diagrams consulted:** <!-- list files from architecture/ reviewed during this round -->
**Diagrams requiring update after ship:** <!-- none, or list diagrams that need changes -->

### Round 5: PII / Compliance Review
_Identify PII and sensitive data elements. Document retention, access, and deletion requirements. If no PII is involved, add an explicit N/A entry._

| # | Data Element | Classification | Handling Requirement |
|---|-------------|---------------|---------------------|
| P1 | | [PII/sensitive/internal/public/N/A] | |

### Round 6: UX & Interaction Review
_Challenge interaction design, accessibility, and visual consistency. For non-UI features, add an explicit N/A entry._

| # | Concern | Category | Resolution |
|---|---------|----------|------------|
| UX1 | Spec describes success states on every screen but never specifies what the user sees while data is loading (list fetch, detail fetch, status PATCH, analytics charts). On mobile this is more visible than on desktop because cellular loads are slower and full-screen detail views hide the list entirely, so a slow load shows a blank screen rather than a side panel. | states | Inherit desktop loading behavior entirely — no mobile-specific skeletons, spinners, or placeholders introduced by this feature. Consistent with the spec's broader "responsive pass, not redesign" posture and with A2 (concurrency), E3 (mutation failures). Add a one-line note acknowledging that full-screen mobile views may show a blank screen during slow loads as an accepted limitation; a dedicated mobile-loading-polish feature is a clean follow-up if needed. |
| UX2 | The spec introduces several net-new UI primitives that likely don't exist in the current desktop-only codebase (bottom sheet for Filters, FAB, full-screen modal with sticky header, "⋮" overflow menu in headers and on rows). R18 guarantees each of these gets used on multiple surfaces, so without a consistency rule implementers will independently hand-roll or pick different libraries, producing divergent bottom sheets / FABs / modals across the app. | consistency | Each new mobile primitive — bottom sheet, FAB, full-screen modal with sticky header, and header/row "⋮" overflow menu — is implemented once as a shared component and reused across every mobile surface that needs it (filters + status picker share the bottom sheet; create + edit + comment share the full-screen modal; analytics export + row actions share the overflow menu). Exact styling and library choice remain implementation details, but the "build once, reuse" rule is specified here to prevent duplication. |
| UX3 | The FAB lives in the bottom-right (R8) and R15 allows a per-row "⋮" overflow button on each list card. As the user scrolls the list, every card's right-edge overflow button passes visually under the FAB, making it ambiguous near the bottom of the viewport whether a tap is hitting the FAB or the card's overflow control. A4 covered occlusion via bottom padding but not this visual/spatial competition during scroll. | responsive | On mobile list cards, per-row overflow/action controls are not placed in the bottom-right quadrant of the card. They sit in the card's top-right (next to the title) or inline with card metadata, so they never visually or spatially compete with the FAB during scroll. Preferred over a scroll-hiding FAB because it's a positioning rule rather than a new interaction behavior, is testable, and keeps the bottom-right region as the FAB's unambiguous affordance (matching mobile convention). |
| UX4 | Spec defines full-screen detail views (R5, in-header back button) and full-screen modals (R7, sticky Cancel) but never specifies how they interact with the OS/browser back gesture, which is a primary input on mobile (iOS swipe-back, Android system back). If these views aren't real history entries, swipe-back exits the app entirely from mid-flow — a common and confusing mobile-web bug. Invisible on desktop, so not answered by "inherit desktop behavior." | a11y | Full-screen detail views and full-screen modals are each represented as browser history entries. The OS/browser back gesture pops one level at a time: returning from a modal behaves identically to tapping Cancel (including any unsaved-changes handling inherited from desktop); returning from a detail view behaves identically to tapping the in-header back button (returns to list, preserves scroll). The back gesture must never exit the app from within a full-screen view. Composes correctly with deferred a11y work (B3): the same history plumbing serves assistive-tech back navigation. |

## Readiness Checklist

- [x] All High-confidence requirements have acceptance criteria
- [x] No unresolved conflicts remain
- [x] Open questions are non-blocking or have owners
- [ ] At least 3 assumptions explicitly challenged and resolved
- [ ] At least 3 edge cases explicitly addressed
- [ ] Out of Scope section reviewed via scope boundary probe
- [ ] At least 2 architectural implications reviewed
- [ ] PII and sensitive data elements identified with handling requirements (or explicit N/A)
- [x] At least 2 UX/interaction concerns reviewed (or explicit N/A for non-UI features)
- [x] All User Journey steps and edge cases have corresponding BDD-N scenarios
