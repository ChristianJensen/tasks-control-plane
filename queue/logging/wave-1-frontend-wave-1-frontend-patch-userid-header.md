---
status: in-progress
target-repo: frontend
wave: 1
priority: high
feature: logging
type: feature
claimed-by: agent-Christians-MacBook-Air-32392
claimed-at: 2026-03-19T16:07:46Z
claimed-on: Christians-MacBook-Air
---

## Description

Add the X-User-Id header to all PATCH /tasks/{taskId} fetch calls in the frontend. This is required because the API now mandates X-User-Id on PATCH (breaking change R7). Without this, all task updates from the UI will fail with 400.

## Why

The API breaking change (X-User-Id required on PATCH) ships in wave 1. The frontend must adapt simultaneously or task status changes, title edits, and description edits will all break.

## Implementation Notes

Modify src/App.jsx: Find all fetch calls to `${API_URL}/tasks/${...}` with method PATCH. The frontend already sends X-User-Id for comment requests — follow the same pattern. The hardcoded user ID value used for comments should be reused here. Likely 2-4 fetch call sites need updating. Each needs `'X-User-Id': '<same-hardcoded-value>'` added to the headers object. Update tests in tests/App.test.jsx to include the header in mocked PATCH requests and verify it is sent.

## Contract References

PATCH /tasks/{taskId} — X-User-Id header now required (components/parameters/XUserId). 400 response if missing.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] All PATCH /tasks/{taskId} fetch calls include the X-User-Id header
- [ ] The X-User-Id value matches the existing hardcoded value used for comment requests
- [ ] Existing task update functionality (status change, title edit, description edit) continues to work
