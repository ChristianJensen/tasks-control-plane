---
lifecycle: active
version: 1
paused-at: ""
paused-by: ""
pause-reason: ""
---

# Feature Spec: Delete Comments

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| 1 | conversation | Claude Code interview | PM | 2026-03-17 |

## Problem Statement

Users who author comments on tasks have no way to remove them. A mistyped or irrelevant comment stays visible forever, cluttering task discussions. Authors need a simple way to permanently delete their own comments.

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | API exposes `DELETE /tasks/{taskId}/comments/{commentId}` returning 204 on success | S1 | High | Hard delete — row removed from DB |
| R2 | Only the comment author can delete their own comment | S1 | High | Returns 403 if non-author attempts |
| R3 | Deleting a non-existent or already-deleted comment returns 404 | S1 | High | Not idempotent |
| R4 | Frontend shows a delete button/icon only on comments authored by the current user | S1 | High | |
| R5 | Frontend shows a confirmation dialog before sending the delete request | S1 | High | "Are you sure?" modal |
| R6 | After successful delete the comment is removed from the UI without a full page reload | S1 | High | Optimistic or refetch |
| R7 | Comments are a flat list — no cascading delete behavior needed | S1 | High | |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| — | None | — |

## Open Questions

_(none — all decisions resolved during interview)_

## Acceptance Criteria

- [ ] `DELETE /tasks/{taskId}/comments/{commentId}` returns 204 and removes the comment from the database
- [ ] Request from a non-author returns 403 Forbidden; comment is unchanged
- [ ] Request for a non-existent comment returns 404 Not Found
- [ ] Delete button is visible only on the current user's own comments
- [ ] Clicking delete shows a confirmation dialog; cancelling does nothing
- [ ] Confirming delete removes the comment from the UI without a full page reload
- [ ] Deleting the last comment on a task leaves the comment list empty (no ghost entries)

## Out of Scope

- Editing comments
- Bulk delete (selecting and deleting multiple comments at once)
- Delete audit log (who deleted what and when)
- Soft delete / restore capability
- Threaded replies / cascading delete
- Time-limited delete windows

## Refinement Log

### Round 1: Assumptions

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | Comments are a flat list, not threaded | Yes | Confirmed — no replies, no cascading needed |
| A2 | No time limit on when a comment can be deleted | Yes | Confirmed — author can delete at any time |
| A3 | Delete is permanent (hard delete) | Yes | Confirmed — no soft delete or restore |

### Round 2: Edge Cases

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | Double-delete (comment already gone) | R3 | Returns 404 |
| E2 | Non-author attempts delete | R2 | Returns 403; UI hides button for non-authors |
| E3 | Deleting the last comment on a task | AC #7 | Comment list shows empty, no ghost entries |

### Round 3: Scope Boundaries

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | Edit comments | Out | Separate feature, different UX and API surface |
| B2 | Bulk delete | Out | No current need; adds complexity |
| B3 | Delete audit log | Out | No compliance requirement driving this |

## Readiness Checklist

- [x] All High-confidence requirements have acceptance criteria
- [x] No unresolved conflicts remain
- [x] Open questions are non-blocking or have owners
- [x] At least 3 assumptions explicitly challenged and resolved
- [x] At least 3 edge cases explicitly addressed
- [x] Out of Scope section reviewed via scope boundary probe
