---
title: "Gamification v1 — Your Progress card"
lifecycle: active
execution: supervised
model: ""
priority: medium
dimensions: [assumptions, edges, scope, ux]
total-budget: ""
total-cost-usd: ""
total-tokens: ""
epic: ""
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
# Gamification v1 — Your Progress card

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| 1 | conversation | interview transcript | planner + user | this session |
| 2 | PRD | PRD (v1) | pasted | 2026-07-03 |

## Problem Statement

Users completing tasks in the app have no visible sense of progress or
accomplishment. The product intent is for users to eventually compete on
task completion, but there is no user-visible signal today that
completion is being measured at all. For this first iteration — while
the system is still effectively single-user — users need a lightweight
"look how much you've done" surface that establishes the gamification
hook without pretending to be a multi-user leaderboard yet.

## User Stories

### US-1: As a task-app user, I want to see how many tasks I have completed so that I feel a sense of progress when I open the analytics view

Status: in-progress
Repos: frontend
PR-frontend:

**Scenarios:**
- **BDD-1** **GIVEN** the analytics endpoint reports `countsByStatus.done` equal to 12 **WHEN** the user navigates to `/analytics` **THEN** a "Your Progress" card is rendered at the top of the page displaying the number `12` and the label `tasks completed`
- **BDD-2** **GIVEN** the analytics endpoint reports `countsByStatus.done` equal to 0 (no tasks completed yet) **WHEN** the user navigates to `/analytics` **THEN** the "Your Progress" card renders with the number `0` and the label `tasks completed` (no separate empty state, no hidden card)
- **BDD-3** **GIVEN** a task is in `done` status and the user views the analytics page **WHEN** that task transitions back to `todo` (via the existing update flow) and the analytics page is re-fetched **THEN** the "Your Progress" number decrements by 1, because the count reflects tasks currently in done status, not lifetime completions
- **BDD-4** **GIVEN** the user is viewing `/analytics` at a mobile viewport width (< 768px) **WHEN** the page renders **THEN** the "Your Progress" card appears above the existing analytics content and the previously covered mobile layout scenarios (existing BDD-7/8/9 in `tests/mobile-analytics.test.jsx`) continue to pass unchanged for the charts below it
- **BDD-5** **GIVEN** the analytics endpoint request fails **WHEN** the user navigates to `/analytics` **THEN** the "Your Progress" card follows the same error-handling pattern already used by `AnalyticsPage.jsx` (no crash, existing error surface shown) and does not render a stale or fabricated number
- **BDD-6** **GIVEN** a task is currently in `done` status and contributes to the "Your Progress" count **WHEN** that task is deleted (via the existing delete flow) and the analytics page is re-fetched **THEN** the "Your Progress" number decrements by 1, matching the current-`done` semantics (the count is not a lifetime completion tally)
- **BDD-7** **GIVEN** the analytics endpoint reports `countsByStatus.done` equal to `1234567` **WHEN** the user navigates to `/analytics` **THEN** the "Your Progress" card renders the number formatted via the browser locale (e.g. `1,234,567` in `en-US`) using `Number.prototype.toLocaleString()`, with no upper cap or truncation
- **BDD-8** **GIVEN** the analytics fetch initiated by `AnalyticsPage.jsx` is still pending **WHEN** the page is in its loading state **THEN** the "Your Progress" card does not render (no flash of `0`, no separate loading state); the card appears together with the rest of the page content once the fetch resolves successfully
- **BDD-9** **GIVEN** the analytics endpoint returns a successful response whose `countsByStatus.done` is missing, `undefined`, `null`, `NaN`, negative, or a non-integer number **WHEN** the "Your Progress" card renders **THEN** the value is normalized to a non-negative integer (`Number.isFinite(n) && n >= 0 ? Math.floor(n) : 0`) and the card renders that normalized number with the label `tasks completed` (no error surface, no hidden card)

**Notes:** Frontend-only slice and the only story in this feature — it
owns all scaffolding, though there is no shared infra to bundle (no new
DB tables, no new libraries, no new endpoints). The `/tasks/analytics`
endpoint already returns `countsByStatus.done`; no api-side changes, no
new endpoints, no contract changes. The card is added to the existing
`src/AnalyticsPage.jsx` and must render inside the same fetch/loading
lifecycle already in place there — it shares the page's pending gate
rather than owning its own loading state. The card is a semantic region
with an accessible heading ("Your Progress") and an accessible label
associating the large number with "tasks completed" for screen readers.

Value normalization is a single guard applied to `countsByStatus.done`:
missing/undefined/`null`/`NaN`/negative/non-integer all collapse to a
non-negative integer via `Number.isFinite(n) && n >= 0 ? Math.floor(n) : 0`.
The rendered number is formatted for display with
`Number.prototype.toLocaleString()` (browser locale, no cap).

The label is always the plural string `tasks completed`, including when
the count is `1` — there is no singular branch. Copy is hard-coded
English for v1 (see i18n Constraint).

Staleness contract: the card reflects the last successful
`/tasks/analytics` fetch. It does not subscribe to task mutations; if a
task is completed, reopened, or deleted in another tab or view, the
card will not update until the analytics page re-fetches (navigation or
existing refresh path).

Extend the existing `tests/AnalyticsPage.test.jsx` and
`tests/mobile-analytics.test.jsx` rather than creating parallel test
files, so the card is covered by the same responsive and rendering
guarantees as the rest of the page.

## Constraints

| # | Category | Requirement | Verification |
|---|----------|-------------|--------------|
| C1 | Accessibility | Card exposes a semantic heading ("Your Progress") and the numeric value is programmatically associated with its "tasks completed" label so screen readers announce the pair; card is reachable and readable in the existing keyboard tab order of the analytics page. | Component test asserts heading role + accessible name for the count; manual axe / keyboard pass on `/analytics`. |
| C2 | Compatibility | Card must not regress existing mobile analytics layout scenarios (currently covered by BDD-7/8/9 in `tests/mobile-analytics.test.jsx`). | Existing mobile-analytics tests continue to pass; a new mobile-layout assertion is added covering the card's placement above the charts. |
| C3 | Testing | Follows the repo TDD + naming conventions inherited from the global testing baseline; each new BDD-N here has a matching test referencing the BDD ID in its name or description, colocated with the existing `AnalyticsPage` tests. | `npm test` in frontend; grep for BDD-1..BDD-9 in test descriptions. |
| C4 | Security | No new inputs, endpoints, secrets, or auth surface introduced; reuses the existing unauthenticated `/tasks/analytics` fetch already performed by `AnalyticsPage.jsx`. Inherits the global security baseline (input validation, dependency scanning) with no feature-specific additions. | Diff review confirms zero new network calls and zero new user inputs. |
| C5 | API design | No changes to the API contract. The feature consumes `TaskAnalytics.countsByStatus.done` from the existing `/tasks/analytics` response as-is. | `contracts/tasks-api.json` unchanged in this feature's PR. |
| C6 | Architecture | Frontend-only slice: no api-repo PR is opened for this feature, no new endpoints are added, and zero new network calls are introduced (the count is read from the existing analytics fetch already performed by `AnalyticsPage.jsx`). Any implementer proposal to add a dedicated progress endpoint (e.g. `/tasks/progress`) must be escalated as an ADR-level question rather than adopted silently. | PR diff touches only the `frontend` repo; grep confirms no new `fetch(`/`axios` call sites; api repo has no PR opened under this feature. |
| C7 | UX / Visual prominence | The count is the most visually prominent element in the card — its rendered font size is larger than the surrounding body text on the analytics page — and the "tasks completed" label sits directly beneath it and is programmatically associated with the number. Exact size/token is left to the implementer within that rule. | Component test asserts the count element's computed font-size exceeds the label's; visual review at desktop and mobile widths. |
| C8 | i18n | Inherits the global i18n baseline. For v1 the strings "Your Progress" and "tasks completed" are hard-coded English (no i18n layer exists in the app today); when an i18n layer is introduced these two strings are on the migration list. The label is always plural ("tasks completed") — there is no singular branch, so no plural-rule handling is required at migration time. | Grep for the two literal strings in the frontend source lists exactly the card's usage; migration checklist (future) references this row. |
| C9 | Motion / reduced-motion | v1 ships with no animation on the count. Any future enhancement that animates the count (e.g. count-up on change, pulse on increment) must respect `prefers-reduced-motion: reduce` and render the final value immediately for users with that preference. | Documented as a review checklist item for any future PR that introduces motion to this component; no test required at v1 since no animation is shipped. |

## Out of Scope

- Multi-user leaderboard / ranking against other users (deferred to a
  later iteration once real multi-user support lands).
- Points / XP system beyond the raw completed-task count.
- Badges or achievements (e.g. "First 10 tasks!", "Work category
  master").
- Streaks (e.g. "3 days in a row").
- Levels or tiers (e.g. "Novice / Pro / Expert" labels).
- Completion celebrations — no confetti, toast, modal, sound, or
  animation when a task moves to done.
- A new "progress over time" chart. The existing `completedPerDay` chart
  on the analytics page stays as-is and is not restyled by this
  feature.
- Any new API endpoints, contract changes, or new fields on
  `TaskAnalytics`. The count is read from the existing
  `countsByStatus.done`.
- "Lifetime completions" semantics. The number shown reflects tasks
  currently in `done` status; un-completing or deleting a done task
  decrements it. A separate lifetime metric can be added when
  multi-user competition arrives.
- Per-user filtering of the count. While the system is effectively
  single-user, `countsByStatus.done` is treated as "the current user's
  count"; correct per-`X-User-Id` scoping is a concern for the
  multi-user iteration, not this one.
- Placement of the "Your Progress" card anywhere other than `/analytics`
  (e.g. the home page, the tasks page, or a global header). Broader
  surfacing of the gamification hook is reconsidered when the
  multi-user leaderboard iteration lands.
- Live updates / real-time subscription. The card reflects the last
  successful `/tasks/analytics` fetch and does not observe task
  mutations; users see updates on the next page re-fetch.
- Telemetry / instrumentation of the card (render events, count-change
  events, hook-effectiveness metrics). There is no telemetry pipeline
  in the app today; measuring the hook is deferred to a future
  dedicated instrumentation feature that can cover the whole analytics
  page (and the eventual leaderboard) uniformly.
- Animation of the count (count-up on change, pulse on increment,
  etc.). v1 renders a static number; the reduced-motion constraint
  (C9) governs any future animated version.
- Singular-form label copy. The label is always "tasks completed" even
  when the count is `1`; no grammatical branching is introduced.

## Implementation Log

_Implementation learnings (Decisions, Discoveries, Spec gaps) live in the sibling file `gamification-feature-impl-log.md`, appended by `post-agent.sh` after each PR merge. Read that file before claiming a downstream story-repo._

## Readiness Checklist

- [x] Problem statement is concrete and user-facing
- [x] At least one user story defined
- [x] Each user story declares Status, Repos, and ≥1 BDD-N scenario
- [x] BDD-N IDs are sequential and unique across the spec
- [x] Constraints section addresses NFRs (or explicit `N/A` row with rationale)
- [x] Out of Scope section is explicit (no empty placeholder)
