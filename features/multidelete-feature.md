---
lifecycle: replanning
version: 2
paused-at: 2026-03-21T01:28:35Z
paused-by: christianjensen
pause-reason: ""
deployed-at: ""
deployed-env: ""
---

# Feature Spec: Multi-Delete Tasks

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| S1 | conversation | (interview session) | Christian Jensen | 2026-03-21 |

## Problem Statement

Users currently have to delete tasks one at a time, which is tedious when cleaning up multiple completed or obsolete tasks. There is no way to select and remove several tasks in a single action, leading to repetitive clicks and a slow workflow for bulk task management.

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | New batch delete API endpoint `POST /tasks/batch-delete` that accepts an array of task IDs and deletes them in one request | S1 | High | POST chosen over DELETE for broad HTTP client compatibility |
| R2 | The API must handle partial success: valid tasks are deleted even if some IDs are not found | S1 | High | |
| R3 | The API response must report which IDs were deleted and which were not found: `{ deleted: [...], notFound: [...] }` | S1 | High | |
| R4 | Maximum of 50 task IDs per batch delete request | S1 | High | Returns 400 if exceeded |
| R5 | Request with empty IDs array returns 400 error | S1 | High | |
| R6 | Deletion cascades to associated comments and status history (same as single delete) | S1 | High | Matches existing `DELETE /tasks/{taskId}` behavior |
| R7 | Always returns HTTP 200 for valid requests, even if all IDs are not found | S1 | High | The `notFound` array communicates missing IDs |
| R8 | No authentication required (no `X-User-Id` header) — matches existing single delete | S1 | High | |
| R9 | Frontend: "select mode" toggle that enables task selection via checkboxes | S1 | High | Ephemeral — lost on navigation/refresh |
| R10 | Frontend: "select all" checkbox that selects all currently visible/filtered tasks | S1 | High | |
| R11 | Frontend: individual task checkboxes for granular selection | S1 | High | |
| R12 | Frontend: confirmation dialog before batch deletion showing count of selected tasks and warning that comments and history will be permanently deleted | S1 | High | |
| R13 | Frontend: calls the new batch delete endpoint and handles the response (success, partial success, errors) | S1 | High | |
| R14 | Frontend: silently succeeds for tasks already deleted by another user (notFound items) — no error shown | S1 | High | End result is the same: task is gone |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| (none) | No conflicts detected | N/A |

## Open Questions

(none at this time)

## Acceptance Criteria

- [ ] AC1: `POST /tasks/batch-delete` accepts `{ ids: [1, 2, 3] }` and returns `{ deleted: [1, 2], notFound: [3] }` with status 200
- [ ] AC2: Request with more than 50 IDs returns 400 error
- [ ] AC3: Request with empty array returns 400 error
- [ ] AC4: Request with all not-found IDs returns 200 with empty `deleted` array
- [ ] AC5: Deleted tasks have their comments and status history cascade-deleted
- [ ] AC6: Frontend shows a "select mode" toggle; when active, checkboxes appear on each task row
- [ ] AC7: Frontend "select all" checkbox selects/deselects all visible tasks
- [ ] AC8: A "Delete selected" button appears when at least one task is selected
- [ ] AC9: Clicking "Delete selected" shows a confirmation dialog with count and cascade warning
- [ ] AC10: After confirmed deletion, the task list refreshes and selection state resets
- [ ] AC11: Duplicate IDs in request are deduplicated (each task deleted at most once)

## Out of Scope

- Multi-delete for comments
- Soft delete / undo / trash functionality
- Bulk status update or other bulk operations
- Keyboard shortcuts for selection (Shift+click, Ctrl+click)
- Persisted select mode or selection state across navigation

## Refinement Log

### Round 1: Assumptions
_What does this spec assume but not explicitly state?_

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | No authentication/authorization required for batch delete (matches single delete) | Yes | Confirmed — no `X-User-Id` needed, anyone can delete any task |
| A2 | HTTP method is `DELETE` with a request body | Yes | Changed to `POST /tasks/batch-delete` for broader HTTP client/proxy compatibility |
| A3 | Select mode is ephemeral — not persisted across navigation or refresh | Yes | Confirmed — selection resets on navigate/refresh |

### Round 2: Edge Cases
_Stress-test the spec with edge cases._

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | Another user deletes a selected task before batch request is sent (race condition) | R2, R3, R14 | Silently succeeds — task appears in `notFound` but end result is the same (task is gone) |
| E2 | User filters by status, selects all, but a task's status changes before delete request | R2 | API deletes by ID regardless of status — acceptable, keep simple |
| E3 | All IDs in request are not found | R7, AC4 | Returns HTTP 200 with `{ deleted: [], notFound: [...] }` — consistent with partial success model |

### Round 3: Scope Boundaries
_Propose adjacent features and confirm whether they are in or out of scope._

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | Bulk status update (mark multiple tasks done/todo) | Out | Separate feature; select mode UI could be reused later |
| B2 | Undo/trash for deleted tasks | Out | Adds significant complexity (soft delete, retention, UI); not needed now |
| B3 | Keyboard shortcuts for selection (Shift+click, Ctrl+click) | Out | Nice-to-have UX enhancement; not required for MVP |

### Round 4: Architecture Review
_Challenge architectural implications._

| # | Implication | Impact Area | Resolution |
|---|------------|-------------|------------|
| AR1 | New `POST /tasks/batch-delete` endpoint added to API contract | API | Version bump to 0.6.0; new endpoint, request/response schemas added |
| AR2 | Cascade deletion of comments and history for multiple tasks in one request | perf/DB | Should use a database transaction to ensure atomicity per task; acceptable at 50-task limit |

### Round 5: PII / Compliance Review
_Identify PII and sensitive data elements._

| # | Data Element | Classification | Handling Requirement |
|---|-------------|---------------|---------------------|
| P1 | Task IDs in request/response | internal | No PII — integer identifiers only. N/A for compliance. |

## Readiness Checklist

- [x] All High-confidence requirements have acceptance criteria
- [x] No unresolved conflicts remain
- [x] Open questions are non-blocking or have owners
- [x] At least 3 assumptions explicitly challenged and resolved
- [x] At least 3 edge cases explicitly addressed
- [x] Out of Scope section reviewed via scope boundary probe
- [x] At least 2 architectural implications reviewed
- [x] PII and sensitive data elements identified with handling requirements (or explicit N/A)
