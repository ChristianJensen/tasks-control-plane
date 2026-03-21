---
status: in-progress
target-repo: frontend
wave: 2
priority: high
feature: logging
type: feature
claimed-by: agent-06-36-06-7A-C3-F6-74709
claimed-at: 2026-03-21T00:30:18Z
claimed-on: 06-36-06-7A-C3-F6
---

## Description

Fetch and display the status transition history on the task detail view. Add a new section below comments (or in an appropriate location) showing a timeline of status changes with old status, new status, who changed it, and when.

## Why

This completes the user-facing feature — users can now see the audit trail of status transitions directly in the task detail view (R3).

## Implementation Notes

Modify src/App.jsx: (1) Add state for history data (e.g., `taskHistory` useState). (2) Fetch GET /tasks/{taskId}/history when the task detail view is opened (same useEffect pattern as comments). (3) Add a StatusHistory display component (inline in App.jsx, following existing patterns). Show each entry as a row/card with: oldStatus → newStatus, changedBy, and formatted changedAt (use existing formatTimestamp utility). (4) Style using inline style objects with theme tokens — follow existing component styling patterns. (5) Handle empty state (no transitions yet — show a subtle message or nothing). (6) Add tests: mock the history fetch, verify rendering of entries, verify empty state, verify 404 handling.

## Contract References

GET /tasks/{taskId}/history — returns StatusTransition[] ordered by changedAt ascending. StatusTransition schema: id, taskId, oldStatus, newStatus, changedBy, changedAt.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Task detail view fetches GET /tasks/{taskId}/history when opened
- [ ] Each status transition displays: old status, new status, who changed it (changedBy), and when (changedAt formatted)
- [ ] Transitions are displayed in chronological order (oldest first)
- [ ] Empty history state is handled gracefully (empty array from API)
- [ ] Styling uses inline style objects with theme tokens, consistent with existing components
