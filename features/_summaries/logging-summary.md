---
feature: logging
completed: 2026-03-21
tasks: 3
waves: 2
---

## Overview

When a task's status changes (e.g., todo → in-progress → done), there is no record of who made the change or when it happened. Users and teams have no visibility into the workflow history of a task, making it hard to understand how work progressed or who moved it forward. This feature adds an immutable audit trail of status transitions, exposed via API and visible in the frontend task detail view.

## What Was Built

### Wave 1

- **api** — Add in-memory statusHistory store with auto-incrementing IDs. Require X-User-Id header on PATCH /tasks/{taskId} (return 400 if missing). On PATCH status change, record a StatusTransition entry (skip if no-op same-status). Add GET /tasks/{taskId}/history endpoint returning entries sorted by changedAt ascending. Update DELETE /tasks/{taskId} to cascade-delete history entries. Expose store via _resetStore() for tests.
- **frontend** — Add the X-User-Id header to all PATCH /tasks/{taskId} fetch calls in the frontend. This is required because the API now mandates X-User-Id on PATCH (breaking change R7). Without this, all task updates from the UI will fail with 400.

### Wave 2

- **frontend** — Fetch and display the status transition history on the task detail view. Add a new section below comments (or in an appropriate location) showing a timeline of status changes with old status, new status, who changed it, and when.

## Key Decisions

- **wave-1-api-wave-1-api-status-history-endpoints:** Modify src/app.js: (1) Add `const statusHistory = new Map()` and `let historyIdCounter = 1` next to existing stores. (2) In the PATCH /tasks/:id handler, add validation for X-User-Id header at the top (before existing validation) — return 400 if missing. After the existing status update logic, check if `status` was provided AND differs from the current status; if so, push a new entry to statusHistory. (3) Add GET /tasks/:id/history route — check task exists (404), then filter and sort entries. (4) In DELETE /tasks/:id, add a loop to delete statusHistory entries for that taskId (same pattern as comments cascade). (5) Update _resetStore() to clear statusHistory and reset counter. Follow the existing patterns in app.js for Map-based storage (see comments store). No new files needed.
- **wave-1-frontend-wave-1-frontend-patch-userid-header:** Modify src/App.jsx: Find all fetch calls to `${API_URL}/tasks/${...}` with method PATCH. The frontend already sends X-User-Id for comment requests — follow the same pattern. The hardcoded user ID value used for comments should be reused here. Likely 2-4 fetch call sites need updating. Each needs `'X-User-Id': '<same-hardcoded-value>'` added to the headers object. Update tests in tests/App.test.jsx to include the header in mocked PATCH requests and verify it is sent.
- **wave-2-frontend-wave-2-frontend-history-display:** Modify src/App.jsx: (1) Add state for history data (e.g., `taskHistory` useState). (2) Fetch GET /tasks/{taskId}/history when the task detail view is opened (same useEffect pattern as comments). (3) Add a StatusHistory display component (inline in App.jsx, following existing patterns). Show each entry as a row/card with: oldStatus → newStatus, changedBy, and formatted changedAt (use existing formatTimestamp utility). (4) Style using inline style objects with theme tokens — follow existing component styling patterns. (5) Handle empty state (no transitions yet — show a subtle message or nothing). (6) Add tests: mock the history fetch, verify rendering of entries, verify empty state, verify 404 handling.

## Contracts Affected

(No contracts referenced)

## Retrospective Notes

(No retrospective entries)
