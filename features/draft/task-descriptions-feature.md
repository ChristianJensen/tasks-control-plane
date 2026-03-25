---
lifecycle: draft
execution: supervised
priority: medium
budget: ""
total-budget: ""
total-cost-usd: ""
total-tokens: ""
epic: TASK-5
epic-title: Q1 - Task Tracker Enhancements
version: 1
paused-at: ""
paused-by: ""
pause-reason: ""
created-at: "2026-03-25"
completed-at: ""
deployed-at: ""
deployed-env: ""
---
# Feature Spec: Task Descriptions

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| S1 | conversation | (interview) | Christian Jensen | 2026-03-25 |
| S2 | contract | contracts/tasks-api.json | — | — |

## Problem Statement

End users of the task tracker can currently only give tasks a short title. Titles alone don't provide enough context — users need a place to capture details, steps, or notes about a task so they can understand what needs to be done without relying on memory. The API contract already defines an optional `description` field (max 2000 characters) on tasks, but neither the API implementation nor the frontend supports it. This feature closes that gap.

## User Journey

1. User opens the task tracker and sees the task list (descriptions are not shown inline).
2. User clicks "Add Task" and sees the creation form with a title field and an optional description textarea below it.
3. User enters a title and optionally types a description (plain text, up to 2000 characters).
4. User submits the form — the new task appears in the task list showing only the title.
5. User clicks on an existing task row to expand an inline detail panel.
6. The detail panel shows the task's description (or an empty/placeholder state if no description was provided).
7. User clicks an edit control within the detail panel to modify the description.
8. User edits the description text and saves — the panel updates immediately with the new text.
9. User collapses the detail panel and returns to the compact task list view.

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | API accepts, stores, and returns the `description` field on task creation (POST /tasks) | S1, S2 | High | Field already defined in contract — optional, max 2000 chars |
| R2 | API accepts, stores, and returns the `description` field on task update (PATCH /tasks/{taskId}) | S1, S2 | High | Field already defined in contract |
| R3 | API returns `description` in GET /tasks and GET /tasks/{taskId} responses | S2 | High | Already in Task schema |
| R4 | Frontend creation form includes an optional description textarea below the title | S1 | High | Plain text only |
| R5 | Frontend displays description in an expandable/collapsible detail panel when a task row is clicked | S1 | High | Not shown inline in the task list |
| R6 | Frontend allows editing the description from the detail panel | S1 | High | Saves via PATCH endpoint |
| R7 | Description is plain text only — no markdown or rich text rendering | S1 | High | Keeps scope small |
| R8 | Description field enforces a 2000-character maximum on both API and frontend | S2 | High | Contract constraint |
| R9 | Only one task detail panel can be expanded at a time (accordion behavior) | S1 | High | Collapsing previous panel when a new one is opened |
| R10 | Editing description happens inline in the detail panel, not in a modal | S1 | High | Edit button turns text into textarea with save/cancel |
| R11 | Unsaved description changes prompt a confirmation before discarding | S1 | High | Triggered when clicking another task or collapsing panel |
| R12 | Character counter shown when description exceeds 80% of limit (1,600+ chars) | S1 | High | Turns red/warning at 2000 chars |
| R13 | Graceful handling of 404 when saving a description for a deleted task | S1 | High | Show inline error, collapse panel |
| R14 | Save button shows loading state during API call, disabled to prevent double-clicks | S1 | High | "Saving..." text, inline error on failure |
| R15 | Detail panel follows standard accordion accessibility patterns | S1 | High | aria-expanded, aria-controls, keyboard nav, labeled textarea |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| (none) | — | — |

## Open Questions

(none)

## Acceptance Criteria

- [ ] POST /tasks with a `description` field stores and returns the description
- [ ] POST /tasks without a `description` field succeeds (field is optional)
- [ ] PATCH /tasks/{taskId} with a `description` field updates and returns the new description
- [ ] PATCH /tasks/{taskId} with `description: ""` clears the description
- [ ] GET /tasks returns `description` for each task
- [ ] GET /tasks/{taskId} returns `description`
- [ ] API rejects descriptions exceeding 2000 characters with a 400 error
- [ ] Frontend creation form shows an optional description textarea
- [ ] Frontend task list does not show descriptions inline
- [ ] Clicking a task row expands an inline detail panel showing the description
- [ ] Detail panel shows a placeholder/empty state when no description exists
- [ ] User can edit and save a description from the detail panel
- [ ] Description textarea enforces 2000-character limit with visual feedback
- [ ] Collapsing the detail panel returns to the compact list view
- [ ] Only one detail panel is expanded at a time (accordion behavior)
- [ ] Unsaved description changes prompt a confirmation dialog before discarding
- [ ] Character counter appears when description exceeds 1,600 characters
- [ ] Character counter turns red/warning at 2,000 characters
- [ ] Pasting text that exceeds 2,000 characters is handled by the character limit (no special paste logic)
- [ ] Saving a description for a deleted task shows a graceful inline error (404 handling)
- [ ] Save button shows loading state and is disabled during API call
- [ ] Save failure shows inline error message below the textarea
- [ ] Task row is focusable and toggleable via Enter/Space keys
- [ ] Detail panel uses aria-expanded and aria-controls attributes
- [ ] Description textarea has a visible "Description" label

## Out of Scope

- Markdown or rich text rendering
- Description search (search remains title-only)
- Description shown inline in the task list
- Description preview/truncation in the task list
- Description in quick-add / keyboard shortcut flows

## Refinement Log

### Round 1: Assumptions
_What does this spec assume but not explicitly state?_

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | Sending `description: ""` clears the description (equivalent to no description) | Yes | Confirmed — empty string clears; API stores as null/empty, frontend shows placeholder state |
| A2 | Only one task detail panel can be expanded at a time | Yes | Confirmed — accordion-style, expanding one collapses the other |
| A3 | Description editing happens inline in the detail panel, not in a modal | Yes | Confirmed — edit button in panel converts text to textarea with save/cancel buttons |

### Round 2: Edge Cases
_Stress-test the spec with edge cases._

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | User clicks another task row while editing description (unsaved changes) | R11 | Show confirmation prompt before discarding unsaved changes |
| E2 | Description at or near 2000-character limit — user needs feedback | R12 | Conditional character counter appears at 80% (1,600+ chars), turns red at limit |
| E3 | Task deleted while detail panel is open — save returns 404 | R13 | Show inline error "This task no longer exists", collapse panel gracefully |

### Round 3: Scope Boundaries
_Propose adjacent features and confirm whether they are in or out of scope._

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | Description preview/truncation in task list | Out | Agreed descriptions stay hidden in list; can be a fast follow-up |
| B2 | Description in quick-add / keyboard shortcut flows | Out | Quick-add is about speed; users can add descriptions after creation via detail panel |
| B3 | Paste handling for text exceeding 2000 chars | In | Handled naturally by character limit enforcement — no special paste logic needed |

### Round 4: Architecture Review
_Challenge architectural implications._

| # | Implication | Impact Area | Resolution |
|---|------------|-------------|------------|
| AR1 | Database needs a new nullable `description` column on tasks table | infra | Additive migration — nullable TEXT/VARCHAR(2000) column, no impact on existing data |
| AR2 | API contract already defines description field — no contract changes needed | API | Implementation catches up to existing contract v0.9.0; no version bump, no breaking changes |

**Architecture diagrams consulted:** none
**Diagrams requiring update after ship:** none

### Round 5: PII / Compliance Review
_Identify PII and sensitive data elements._

| # | Data Element | Classification | Handling Requirement |
|---|-------------|---------------|---------------------|
| P1 | Task description (free-form text) | internal | N/A — same classification as task title. No special PII handling, retention, or access controls beyond existing app behavior. Users could enter personal info but this is inherent to any free-text field. |

### Round 6: UX & Interaction Review
_Challenge interaction design, accessibility, and visual consistency._

| # | Concern | Category | Resolution |
|---|---------|----------|------------|
| UX1 | Save button loading state and error handling during API call | states | Save button shows "Saving..." and is disabled during request; inline error message below textarea on failure |
| UX2 | Accordion accessibility — keyboard navigation and screen reader support | a11y | Task row focusable via Tab, toggled via Enter/Space; aria-expanded and aria-controls on trigger; visible "Description" label on textarea; save/cancel buttons keyboard-accessible |

## Readiness Checklist

- [x] All High-confidence requirements have acceptance criteria
- [x] No unresolved conflicts remain
- [x] Open questions are non-blocking or have owners
- [x] At least 3 assumptions explicitly challenged and resolved
- [x] At least 3 edge cases explicitly addressed
- [x] Out of Scope section reviewed via scope boundary probe
- [x] At least 2 architectural implications reviewed
- [x] PII and sensitive data elements identified with handling requirements (or explicit N/A)
- [x] At least 2 UX/interaction concerns reviewed (or explicit N/A for non-UI features)
