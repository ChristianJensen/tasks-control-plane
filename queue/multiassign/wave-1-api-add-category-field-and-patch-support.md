---
status: done
execution: supervised
target-repo: api
wave: 1
priority: high
feature: multiassign
type: feature
claimed-by: agent-06-36-06-7A-C3-F6-44581
claimed-at: 2026-03-21T16:05:14Z
claimed-on: 06-36-06-7A-C3-F6
---

## Description

Add nullable `category` enum field (work, personal, errands) to the Task model. Include category in task creation (defaults to null), in all task responses (GET list, GET single), and accept it in PATCH /tasks/{taskId} with validation. Invalid category values return 400.

## Why

Foundation for all category features. R1 (category field), R2 (single-task assignment via PATCH), R8 (defaults to null at creation), AC1-AC3, AC10.

## Implementation Notes

Modify `src/app.js`. (1) Define `VALID_CATEGORIES = ['work', 'personal', 'errands']` constant near existing validation constants. (2) In task creation (POST /tasks), add `category: null` to new task objects. (3) In PATCH /tasks/:id, accept `category` in the request body. If provided and not null, validate against VALID_CATEGORIES — return 400 for invalid values. If `null`, set category to null (clear). Include category in the update logic. (4) Ensure `taskWithCount()` or equivalent passes through the category field in responses. (5) Add tests in `tests/tasks.test.js`: create task has category:null, PATCH sets category, PATCH clears category with null, PATCH rejects invalid category, GET returns category.

## Contract References

components/schemas/Task (category field), components/schemas/TaskCategory enum, PATCH /tasks/{taskId} requestBody (category property), POST /tasks requestBody (no category — defaults null).

## Acceptance Criteria

- [ ] Tests pass (`npm test`)
- [ ] Contract-compliant: Task responses include `category` field (null by default)
- [ ] POST /tasks creates tasks with category: null (AC10)
- [ ] PATCH /tasks/{taskId} accepts category and persists it (AC2)
- [ ] PATCH /tasks/{taskId} accepts category: null to clear (AC3)
- [ ] PATCH /tasks/{taskId} returns 400 for invalid category values (E2 edge case)
- [ ] GET /tasks and GET /tasks/{taskId} include category in response (AC1)
