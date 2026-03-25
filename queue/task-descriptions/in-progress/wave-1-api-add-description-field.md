---
status: in-progress
execution: supervised
target-repo: api
wave: 1
priority: high
feature: task-descriptions
type: feature
claimed-by: agent-Christians-MacBook-Air-81007
claimed-at: 2026-03-25T17:43:07Z
claimed-on: Christians-MacBook-Air
---

## Description

Add description field to task creation, update, and retrieval endpoints

## Why

The API contract already defines an optional description field (max 2000 chars) on tasks, but the implementation doesn't support it yet. This task closes the gap so the frontend can store and retrieve task descriptions.

## Implementation Notes

Modify `src/app.js`:

1. **POST /tasks** (line ~200): Extract `description` from `req.body`. Validate: if provided, must be a string with `length <= 2000` — return 400 otherwise. Add `description: description !== undefined ? (typeof description === 'string' ? description : '') : null` to the task object (line ~218-227). Empty string `""` is valid and clears the description.

2. **PATCH /tasks/:id** (line ~243): Extract `description` from `req.body` (add to destructuring on line 248). If `description !== undefined`, validate max 2000 chars — return 400 if exceeded. Set `task.description = description`. Allow empty string to clear.

3. **taskWithCount()** already spreads `...task`, so description passes through automatically in all GET responses.

4. **Validation pattern**: Follow the existing pattern for comment text validation (line 361-363) — `if (description !== undefined && typeof description === 'string' && description.length > 2000) return 400`.

Edge cases:
- `description: null` on POST sets description to null (no description)
- `description: ""` on PATCH clears the description
- `description` omitted entirely on POST defaults to null
- Description at exactly 2000 chars succeeds; 2001 chars returns 400

## Contract References

POST /tasks requestBody: `description` (string, maxLength 2000, optional). PATCH /tasks/{taskId} requestBody: `description` (string, maxLength 2000). Task schema: `description` (string, optional). No contract changes needed — implementation catches up to existing contract v0.9.0.

## Acceptance Criteria

- [ ] Tests pass (`npm test`)
- [ ] Contract-compliant
- [ ] POST /tasks with a `description` field stores and returns the description
- [ ] POST /tasks without a `description` field succeeds with description as null
- [ ] PATCH /tasks/{taskId} with a `description` field updates and returns the new description
- [ ] PATCH /tasks/{taskId} with `description: ""` clears the description
- [ ] GET /tasks returns `description` for each task
- [ ] GET /tasks/{taskId} returns `description`
- [ ] API rejects descriptions exceeding 2000 characters with a 400 error
- [ ] Description at exactly 2000 characters is accepted
