---
lifecycle: active
version: 4
paused-at: 2026-03-21T13:34:19Z
paused-by: christianjensen
pause-reason: ""
deployed-at: ""
deployed-env: ""
---
# Feature Spec: Bulk Assign Category

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| S1 | conversation | features/multiassign-feature.md | Christian Jensen | 2026-03-21 |

## Problem Statement

Users need a way to organize their tasks by category (work, personal, errands). Currently tasks have no categorization, making it hard to focus on a specific area. When many tasks need the same category, assigning them one-by-one is tedious. Users need to select multiple tasks and bulk assign a category in one action.

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | Add a `category` field to the Task model. Nullable enum: `work`, `personal`, `errands`. | S1 | High | New field, defaults to null |
| R2 | Single-task category assignment via existing PATCH `/tasks/{taskId}` endpoint (add `category` to the request body). | S1 | High | Extends existing endpoint |
| R3 | New `POST /tasks/batch-update-category` endpoint accepts an array of task IDs and a category value (including null to clear). | S1 | High | Follows batch-delete pattern |
| R4 | Batch endpoint enforces same limits as batch-delete: 1–50 IDs, deduplication, partial success (valid tasks updated, notFound returned). | S1 | High | Consistency with existing patterns |
| R5 | Frontend reuses existing multi-select mode (checkboxes) and adds an "Assign Category" action to the selection toolbar alongside "Delete". | S1 | High | Consistent UX pattern |
| R6 | Category picker UI presents four options: Work, Personal, Errands, and None (to clear). | S1 | High | |
| R7 | Task list displays the assigned category on each task card/row. | S1 | Med | Visual treatment TBD |
| R8 | Category is optional at task creation — defaults to null. | S1 | High | No friction at creation time |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| — | No conflicts detected | — |

## Open Questions

- [ ] Q1: Visual treatment for category display on task cards (badge color, icon, label style) — _asked to design/frontend_

## Acceptance Criteria

- [ ] AC1: Task schema includes nullable `category` field with enum values `work`, `personal`, `errands`
- [ ] AC2: PATCH `/tasks/{taskId}` accepts `category` in request body and persists it
- [ ] AC3: PATCH `/tasks/{taskId}` accepts `category: null` to clear the category
- [ ] AC4: POST `/tasks/batch-update-category` accepts `{ ids: [int], category: string|null }` and updates all matching tasks
- [ ] AC5: Batch endpoint returns `{ updated: [int], notFound: [int] }` with partial success semantics
- [ ] AC6: Batch endpoint validates 1–50 IDs and returns 400 for violations
- [ ] AC7: Frontend multi-select toolbar shows "Assign Category" action when tasks are selected
- [ ] AC8: Category picker dropdown/modal shows Work, Personal, Errands, and None options
- [ ] AC9: After bulk assign, task list refreshes and shows updated categories
- [ ] AC10: New tasks default to no category (null)
- [ ] AC11: Task card/row displays the assigned category visually

## Out of Scope

- Filtering or sorting tasks by category
- User-defined/custom categories
- Multiple categories per task
- Category management UI (add/edit/delete categories)

## Replan v2

**Trigger:** Agent crashed due to laptop reboot — no requirements change.
**Completed work:** None (no tasks were started before crash).
**Spec changes:** None — all requirements, acceptance criteria, and scope unchanged.
**Action:** Re-running refinement rounds that were never completed in v1.

## Replan v3

**Trigger:** Resuming — no requirements change. Refinement rounds were never completed in v1 or v2.
**Completed work:** None.
**Spec changes:** None — all requirements, acceptance criteria, and scope unchanged.
**Action:** Completing all five refinement rounds.

## Replan v4

**Trigger:** Resuming — no requirements change. Refinement rounds 3–5 were never completed in prior versions.
**Completed work:** None.
**Spec changes:** None — all requirements, acceptance criteria, and scope unchanged.
**Action:** Completing remaining refinement rounds (3: Scope Boundaries, 4: Architecture, 5: PII/Compliance).

## Refinement Log

### Round 1: Assumptions
_What does this spec assume but not explicitly state?_

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | Batch category update is idempotent — re-assigning the same category counts as "updated" | Yes | Confirmed. Tasks appear in `updated` array regardless of prior category value. No special no-op handling. |
| A2 | Category is a simple nullable enum column on the tasks table, not a separate table with FK | Yes | Confirmed. Single column, cascade-deletes with the task row. Separate table deferred to custom-categories scope. |
| A3 | Batch-update-category endpoint does not require `X-User-Id` | Yes | Reversed. Require `X-User-Id` for consistency with other mutating endpoints and future audit capability. Validate presence (400 if missing). |

### Round 2: Edge Cases
_Stress-test the spec with edge cases._

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | All IDs in batch request are not found | R4, AC5 | Return 200 with `{ updated: [], notFound: [...] }` — matches batch-delete pattern. Valid request, empty result. |
| E2 | Invalid category value in batch request (e.g., "urgent") | R3, AC6 | Reject entire request with 400. Category validation is request-level, not per-task. No tasks updated. |
| E3 | Task deleted by another user while batch-update is in flight | R4, AC5, AC9 | Deleted task appears in `notFound` array. Remaining tasks updated normally. Frontend refresh (AC9) reflects deletion. No special handling needed. |

### Round 3: Scope Boundaries
_Propose adjacent features and confirm whether they are in or out of scope._

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | Filter/sort tasks by category | Out | Complete shippable unit without it. Adds query params, filter UI, URL state. Natural follow-up feature. |
| B2 | Category field in task creation form | Out | R8 defaults to null. Users can assign post-creation via PATCH or bulk assign. Keeps create flow simple. |
| B3 | Category-based visual grouping (sections by category) | Out | Depends on filter/sort (B1). Current spec shows label on card (R7/AC11) which is sufficient. Significant frontend complexity. |

### Round 4: Architecture Review
_Challenge architectural implications._

| # | Implication | Impact Area | Resolution |
|---|------------|-------------|------------|
| AR1 | Adding `category` column to tasks table requires DB migration | infra | N/A — no database currently exists. Column will be part of initial schema or in-memory store. No migration needed. |
| AR2 | Batch-update-category must mirror batch-delete pattern (validation, partial success, X-User-Id) | API | Low risk. Reuse same validation logic (1–50 IDs, dedup, 400 on violations). Response shape mirrors batch-delete (`updated`/`notFound` vs `deleted`/`notFound`). Shared utility recommended to prevent pattern divergence. |

### Round 5: PII / Compliance Review
_Identify PII and sensitive data elements._

| # | Data Element | Classification | Handling Requirement |
|---|-------------|---------------|---------------------|
| P1 | `category` field (nullable enum: work/personal/errands) | Internal | No PII. Fixed enum, not user-generated content. Deleted with task row. No special retention or access controls. |
| P2 | All existing Task fields (id, title, description, status, createdAt, updatedAt) | Internal | No PII in current context (no real user accounts). Classified via `x-data-classification` in API contract. |
| P3 | N/A — no PII introduced by this feature | N/A | This feature adds only a fixed enum field. No personal data collected, stored, or transmitted. |

## Readiness Checklist

- [x] All High-confidence requirements have acceptance criteria
- [x] No unresolved conflicts remain
- [x] Open questions are non-blocking or have owners
- [x] At least 3 assumptions explicitly challenged and resolved
- [x] At least 3 edge cases explicitly addressed
- [x] Out of Scope section reviewed via scope boundary probe
- [x] At least 2 architectural implications reviewed
- [x] PII and sensitive data elements identified with handling requirements (or explicit N/A)
