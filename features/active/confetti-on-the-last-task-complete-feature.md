---
title: "Confetti on last task complete"
lifecycle: active
execution: supervised
model: ""
priority: medium
dimensions:
  - assumptions
  - edges
  - ux
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
# Confetti on last task complete

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| 1 | conversation | interview transcript (planner chat) | user + planner | draft session |

## Problem Statement

Clearing your task list is a small but genuinely satisfying moment, and today the product gives it no acknowledgement. When a user marks their last open task as done, the UI simply shows an empty list — identical to the state they'd see if they'd never had tasks at all. We want to reward that "cleared my plate" moment with a lightweight, delightful visual celebration that doesn't interrupt the user's flow. This is a frontend-only enhancement; no backend or API changes.

## User Journey

Happy path:

1. User has 2 open tasks (status `todo` or `in-progress`) visible in the task list.
2. User marks task #1 as `done` → list updates, no celebration (1 open task remains).
3. User marks task #2 (the last open task) as `done` → PATCH succeeds, the task moves to done, and a single ~2-second canvas-confetti burst plays from the center-bottom of the viewport. The confetti canvas is non-interactive (`pointer-events: none`) and auto-clears when the animation ends. No modal, text, sound, or dismiss control.
4. User continues working unimpeded — the confetti never blocks clicks, keyboard focus, or scrolling.

Error paths and edge cases (also captured as BDD scenarios below):

1. User completes the last task *in a filtered view* but other open tasks exist → no confetti (open count is computed over all tasks, not the filtered view).
2. User has `prefers-reduced-motion` set → PATCH still succeeds, but no confetti renders.
3. PATCH to set status=done fails → no confetti.
4. User loads the page and already has zero open tasks → no confetti (only session-originated 1→0 transitions trigger).
5. User deletes the last open task (rather than completing it) → no confetti (deletion is not a completion).
6. User marks the last task done (confetti fires), flips it back to `todo`, then marks it done again → confetti fires again (every genuine 1→0 transition celebrates).

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | Fire a canvas-confetti burst when a successful status-change PATCH causes the count of open tasks (`status !== 'done'`) to transition from 1 to 0. | S1 | High | Transition-based, not state-based. |
| R2 | "Open task count" is computed over the full unfiltered task set (filters in the UI do not affect the trigger). | S1 | High | |
| R3 | Only status changes to `done` may trigger confetti; deletions, batch deletes, and other mutations must not. | S1 | High | |
| R4 | Confetti must not fire on initial page load, tab refocus, navigation, or any non-mutation render — only on a PATCH-induced transition in the current session. | S1 | High | |
| R5 | Confetti must only fire after the PATCH response confirms success (HTTP 200). Optimistic UI showing 0 open tasks briefly must not trigger. | S1 | High | |
| R6 | The confetti trigger must work from both the desktop surface (`App.jsx`) and the mobile task detail surface (`MobileTaskDetail.jsx`). | S1 | High | |
| R7 | Introduce a shared pure helper `shouldCelebrate(prevOpenCount, nextOpenCount, cause)` that returns true iff `prevOpenCount === 1 && nextOpenCount === 0 && cause === 'status-change-to-done'`. | S1 | High | Testable in isolation. |
| R8 | Introduce a shared `fireConfetti()` wrapper that invokes canvas-confetti and no-ops when `window.matchMedia('(prefers-reduced-motion: reduce)').matches` is true. | S1 | High | Centralizes the a11y gate so call sites cannot forget it. |
| R9 | Use canvas-confetti defaults: `particleCount: 100`, `spread: 70`, `origin: { y: 0.8 }`, default colors, default ~2s lifetime. | S1 | High | Single place to tweak later. |
| R10 | The confetti canvas must be non-blocking: `pointer-events: none`, no focus trap, no modal, no accompanying text or sound, no dismiss UI. It auto-clears when the animation completes. | S1 | High | |
| R11 | Add `canvas-confetti` as a frontend dependency. | S1 | High | No backend/API change. |
| R12 | Flip-flop behavior: if a user re-opens and re-completes the last task, confetti fires again on each genuine 1→0 transition. | S1 | High | No per-task "already celebrated" memoization. |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| — | None | Single-source spec; no conflicts. |

## Open Questions

- [ ] None blocking. Brand colors for the confetti palette could be revisited later, but the default palette is acceptable for v1.

## Acceptance Criteria

- [ ] Marking the last open task as done via desktop UI plays a single ~2s confetti burst.
- [ ] Marking the last open task as done via mobile task detail UI plays a single ~2s confetti burst.
- [ ] Completing a task that is not the last open task never plays confetti.
- [ ] Deleting the last open task never plays confetti.
- [ ] Confetti never plays on initial load when the list is already empty.
- [ ] Confetti never plays when the PATCH fails.
- [ ] When `prefers-reduced-motion: reduce` is set, no confetti renders (PATCH still succeeds normally).
- [ ] The confetti canvas does not block pointer events, keyboard focus, or scrolling.
- [ ] `shouldCelebrate` and `fireConfetti` are exported from a single shared module and covered by unit tests.
- [ ] Open count is computed over all tasks (not filtered views).
- [ ] Flip-flop (done → todo → done) on the last task re-fires the burst.

## Behavioral Scenarios

### Happy Path

- **BDD-1:** **GIVEN** the user has exactly one open task (`status !== 'done'`) and `prefers-reduced-motion` is not set **WHEN** they mark that task as `done` and the PATCH returns 2xx **THEN** a single canvas-confetti burst renders (particleCount 100, spread 70, origin y 0.8) for ~2s and then auto-clears.
- **BDD-2:** **GIVEN** the user has two open tasks **WHEN** they mark the first as `done` **THEN** no confetti renders (one open task remains).
- **BDD-3:** **GIVEN** the user has exactly one open task **WHEN** they mark it done on the mobile task detail surface and the PATCH returns 2xx **THEN** a confetti burst renders identically to the desktop surface.

### Edge Cases

- **BDD-4:** **GIVEN** the user has a status filter active showing only `todo` and has one `todo` task plus one `in-progress` task (two open tasks total) **WHEN** they mark the `todo` task as `done` **THEN** no confetti renders, because one `in-progress` open task remains in the unfiltered set.
- **BDD-5:** **GIVEN** the user has `prefers-reduced-motion: reduce` set and exactly one open task **WHEN** they mark it done **THEN** the PATCH succeeds and no confetti renders.
- **BDD-6:** **GIVEN** the user has exactly one open task **WHEN** they mark it done but the PATCH returns a non-2xx status **THEN** no confetti renders.
- **BDD-7:** **GIVEN** the user loads the page and already has zero open tasks **WHEN** the initial render completes **THEN** no confetti renders.
- **BDD-8:** **GIVEN** the user has exactly one open task **WHEN** they delete it (rather than completing it) **THEN** no confetti renders.
- **BDD-9:** **GIVEN** the user marked the last task done (confetti fired) **WHEN** they flip it back to `todo` and then mark it `done` again with a successful PATCH **THEN** confetti fires a second time.
- **BDD-10:** **GIVEN** a confetti burst is currently playing **WHEN** the user clicks on a task card or other UI element underneath the canvas **THEN** the click reaches the element normally (the canvas does not intercept pointer events).
- **BDD-11:** **GIVEN** the user is viewing List A with exactly one open task **WHEN** they mark it done, switch to List B (which has five open tasks) before the PATCH response arrives, and the PATCH then returns 2xx **THEN** no confetti renders, because the originating list is no longer the active view.
- **BDD-12:** **GIVEN** the user has exactly one open task **WHEN** they PATCH `status: 'done'` and the server returns 2xx but the response body normalizes the status to `in-progress` **THEN** no confetti renders, because the server response is authoritative.
- **BDD-13:** **GIVEN** the user has exactly two open tasks **WHEN** they rapidly fire two status-change PATCHes (one per task) and both return 2xx, in either response order **THEN** confetti fires exactly once, on whichever response applies the 1→0 transition.
- **BDD-14:** **GIVEN** the user has exactly one open task **WHEN** they mark it done and the server returns 204 No Content (empty body) **THEN** confetti fires, using the request payload's `status: 'done'` as the authoritative fallback.
- **BDD-15:** **GIVEN** a confetti burst is currently playing on the mobile task detail surface **WHEN** the user navigates back to the list before the ~2s animation completes **THEN** the burst continues playing over the new screen without crashing or leaking.

## Constraints

| # | Category | Requirement | Verification |
|---|----------|-------------|--------------|
| C1 | Accessibility | Must honor `prefers-reduced-motion: reduce` by rendering no animation. | Unit test of `fireConfetti()` with a mocked `matchMedia`; manual check with OS-level setting. |
| C2 | Accessibility | Must not trap focus, steal focus, or announce anything to screen readers. The confetti is purely decorative. | Manual keyboard-navigation check; DOM inspection confirms no `aria-live` region added. |
| C3 | Performance | Burst must not block the main thread such that the post-PATCH UI update is visibly delayed. Canvas-confetti's default renderer is acceptable. | Spot check on a mid-range device; no measurable lag in the PATCH-to-render cycle. |
| C4 | Compatibility | Must render correctly on both desktop and mobile surfaces (the app's two existing render paths). | BDD-1 and BDD-3 exercised in tests. |
| C5 | Operational | No new backend calls, no telemetry, no persistence. | Code review confirms frontend-only change. |

## Out of Scope

- Any backend/API change (no "cleared list" signal from the server).
- Accompanying text, modal, toast, sound, or dismiss UI.
- Per-category or per-filter celebrations ("you cleared all work tasks!").
- "Streak" tracking, daily-completion awards, or any persistence of celebration state.
- Brand-customized confetti colors for v1 (defaults are acceptable; revisitable later).
- Celebrations for actions other than status→done (e.g. deletion, batch operations).
- Changes to the analytics endpoint or event telemetry.

## Refinement Log

### Round 1: Assumptions
_What does this spec assume but not explicitly state?_

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | Only a direct status-picker click can trigger confetti; other completion entry points (keyboard shortcut, drag-to-done, undo/redo) are implicitly covered or implicitly excluded. | Yes | Any single-task status PATCH whose response lands on `status='done'` counts, regardless of UI entry point (status control, keyboard, drag, undo/redo). Bulk / multi-task status changes remain out of scope. R7's `cause='status-change-to-done'` covers all single-task paths. |
| A2 | There is a single global task list, so "open task count" is unambiguous. | Yes | The app has multiple task lists. Open-count is scoped to the **active task list**. `prevOpenCount` is tracked per active list. List-switching is never a trigger (it is not a mutation, analogous to page load in R4). Filters still do not affect the trigger (R2 stands), because filters are transient views onto the same bucket while lists are separate buckets. |
| A3 | Local React state before/after the PATCH is a reliable source for the 1→0 transition. | Yes | Local state is authoritative. `prevOpenCount` is captured at PATCH-dispatch time from pre-optimistic state; `nextOpenCount` is captured after the success response is applied. Server-pushed transitions (websocket/poll/other tab) never fire confetti. Concurrent local PATCHes each evaluate their own snapshot pair independently, so the PATCH that actually completes the drain to zero is the one that fires. |
| A4 | Deletion is the only non-completion way an open task can disappear from the count. | Yes | Guard is a **positive whitelist**: `shouldCelebrate` fires only when `cause === 'status-change-to-done'`. Deletion, bulk delete, move-to-another-list, list-deletion, archive, and any future terminal status (e.g. `cancelled`) never pass that cause and therefore never fire. "Open" is fixed as `status !== 'done'` for v1; introducing a new terminal status requires an intentional revisit of this definition. |
| A5 | A single confetti burst per transition is safe and there is no risk of stacked or double-fired bursts. | Yes | Stacking is allowed — a rapid flip-flop (done → todo → done within the burst window) fires a second overlapping burst, matching R12/BDD-9 intent. To prevent accidental double-fires, `fireConfetti` must be invoked **imperatively in the PATCH-success callback**, never from a `useEffect` watching open-count (which would re-run under StrictMode and on unrelated renders). Desktop and mobile share the same `fireConfetti` wrapper and thus canvas-confetti's single global canvas. |
| A6 | A 200 response with the client-requested `status: 'done'` payload is sufficient proof that the task is now done. | Yes | The **server response is authoritative**. Accept any 2xx (not just 200), so 204 No Content is supported. If the response body includes the task, its `status` field decides; if the body is empty, fall back to the request payload. If the server normalizes the status to something other than `done` (e.g., a workflow rule forces `in-progress`), no confetti fires. |

### Round 2: Edge Cases
_Stress-test the spec with edge cases. Reference the edge case library at `retrospectives/edge-case-library.md`._

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | PATCH success response lands after the user has switched active list (or unmounted the surface that dispatched it). Per A2 open-count is per-list, so naively firing would celebrate a list the user is no longer viewing — e.g. List A drains to 0 while the user is now looking at List B with 5 open tasks. | R1, R4, A2, A3 | Capture `activeListId` alongside `prevOpenCount` at PATCH dispatch time. In the success handler, fire confetti only if the originating `activeListId` still matches the current active list; otherwise silently drop the celebration (never queue, buffer, or replay). Unmount is handled by the same gate — if the surface is gone, the callback no-ops. Extends R4's "current session" to "current view." |
| E2 | `canvas-confetti` fails to load or throws at runtime (chunk 404 after deploy, content blocker, extension patching `HTMLCanvasElement`, canvas/WebGL context exhaustion). The PATCH has already succeeded server-side, so a decorative failure must not make a genuine completion look failed. | R8, R10, C5 | `fireConfetti()` wraps the `confetti()` call in `try/catch`, logs via `console.warn` on failure, and never throws. It is invoked fire-and-forget (not awaited) from the PATCH success handler **after** the state update that marks the task done, so a throw cannot interrupt the UI transition. No user-visible error, no toast, no retry. No error-tracking integration in v1 (avoids a telemetry/PII question). Lazy-loading the module is a deferred perf optimization, not required for correctness. |
| E3 | Concurrent PATCHes from rapid-fire completion (double-click, keyboard-repeat, multi-select shortcut) on the last two open tasks. If `prevOpenCount` is captured at dispatch time — as A3 literally states — both PATCHes snapshot `prev=2`, so neither response sees `prev===1` and **no confetti fires even though the user genuinely cleared the list**. Response reordering exhibits the same bug. Also covers idempotent retry of a timed-out-but-succeeded PATCH. | R1, R5, R7, A3 | Correct A3: capture `prevOpenCount` at **response-apply time** (inside the state updater that processes the 2xx), not at dispatch time. Read current open-count, apply the mutation, compute `nextOpenCount`, then evaluate `shouldCelebrate(prev, next, cause)`. Whichever response performs the actual 1→0 transition fires confetti, regardless of PATCH ordering or arrival order. Preserves R7's `prev===1 && next===0` contract unchanged. Idempotent retry naturally no-ops: on the retry, `prev` is already 0, so the guard fails. |

### Round 3: Scope Boundaries
_Propose adjacent features and confirm whether they are in or out of scope._

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | | | |

### Round 4: Architecture Review
_Challenge architectural implications: new services, API changes, scalability, dependencies, breaking changes._

| # | Implication | Impact Area | Resolution |
|---|------------|-------------|------------|
| AR1 | | | |

**Architecture diagrams consulted:** <!-- list files from architecture/ reviewed during this round -->
**Diagrams requiring update after ship:** <!-- none, or list diagrams that need changes -->

### Round 5: PII / Compliance Review
_Identify PII and sensitive data elements. Document retention, access, and deletion requirements. If no PII is involved, add an explicit N/A entry._

| # | Data Element | Classification | Handling Requirement |
|---|-------------|---------------|---------------------|
| P1 | | | |

### Round 6: UX & Interaction Review
_Challenge interaction design, accessibility, and visual consistency. For non-UI features, add an explicit N/A entry._

| # | Concern | Category | Resolution |
|---|---------|----------|------------|
| UX1 | Confetti origin and mid-burst navigation on mobile. `origin: { y: 0.8 }` is viewport-relative and mobile users may navigate away (e.g. back out of `MobileTaskDetail`) while particles are still falling; also, canvas-confetti's full-viewport canvas overlaps any bottom nav / safe-area insets. | responsive | Keep `origin: { y: 0.8 }` unchanged on both surfaces for R6 parity — no per-card anchoring, no per-surface override (reading DOM rects across two surfaces is scope creep for a 2s decorative burst). Mid-burst navigation is **explicitly allowed to play out**: canvas-confetti attaches its canvas to `document.body`, so the burst finishes over the next screen; do not cancel on unmount or route change. Bottom-nav / safe-area overlap is a non-issue because R10 already mandates `pointer-events: none` — nothing is obscured functionally. Documented here so a reviewer doesn't mistake play-through for a bug. |
| UX2 | Screen-reader parity and focus management. A sighted user gets a ~2s celebration; an SR user gets nothing (C2 forbids `aria-live`). Also, when the last task is completed via keyboard, focus is on a status control in a row that just disappeared. | a11y | **No `aria-live` announcement** — C2 stands. The confetti is explicitly decorative; SR parity is "also nothing," not "spoken message." Adding an announcement would turn a decorative flourish into a functional a11y surface and raise scope (wording, i18n, interaction with the empty-state text). If the app's existing empty-state UI isn't announced properly, that's a pre-existing bug filed separately. **Focus-after-empty is explicitly out of scope** — it's a pre-existing list-level concern that predates this feature; entangling the confetti helper with focus logic on two surfaces would violate the "lightweight flourish" framing. C1 (reduced-motion) and C2 (no focus trap, no announcement, no focus steal) remain the complete a11y contract for this feature. |
| UX3 | Visual consistency and reuse. `canvas-confetti` (R11) and `fireConfetti()` (R8) are new — is there an existing animation library, reduced-motion utility, toast/notification system, or completion micro-interaction they should reuse or coexist with? | consistency | Verified against the frontend repo: **no existing animation library** (no framer-motion, react-spring, lottie), **no existing reduced-motion utility** (only `matchMedia` usage is `prefers-color-scheme` in `index.html`), **no toast/notification system**, **no CSS keyframes or transitions**, **no competing completion micro-interaction**. Greenfield on all axes: `canvas-confetti` introduces a new dependency category with no redundancy concern, and `fireConfetti()`'s inline `window.matchMedia('(prefers-reduced-motion: reduce)')` check **establishes the app's canonical reduced-motion gate** — future animation features must import from the same shared module rather than re-rolling the check. Noted here so the next motion feature doesn't duplicate the idiom. |

## Readiness Checklist

- [ ] All High-confidence requirements have acceptance criteria
- [x] No unresolved conflicts remain
- [ ] Open questions are non-blocking or have owners
- [x] At least 3 assumptions explicitly challenged and resolved
- [x] At least 3 edge cases explicitly addressed
- [ ] Out of Scope section reviewed via scope boundary probe
- [ ] At least 2 architectural implications reviewed
- [ ] PII and sensitive data elements identified with handling requirements (or explicit N/A)
- [x] At least 2 UX/interaction concerns reviewed (or explicit N/A for non-UI features)
- [ ] Non-functional constraints identified (or explicit N/A with rationale)
- [x] All User Journey steps and edge cases have corresponding BDD-N scenarios
