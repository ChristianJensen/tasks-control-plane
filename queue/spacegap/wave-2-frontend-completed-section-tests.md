---
status: ready
execution: autonomous
target-repo: frontend
wave: 2
priority: normal
feature: spacegap
type: feature
depends-on:
  - wave-1-frontend-collapsible-completed-section.md
---

## Description

Add comprehensive tests for the collapsible completed section covering spacing, collapse/expand behavior, count display, and all edge cases.

## Why

Ensures all acceptance criteria from the feature spec are verified with automated tests, preventing regressions in spacing, toggle behavior, and edge case handling.

## Implementation Notes

Modify `tests/App.test.jsx` (append to existing file, following existing patterns with `vi.stubGlobal` for fetch mocking and `@testing-library/react`).

Test cases to add (~120 lines):

1. **Completed section header with count** (~15 lines): Create tasks with mixed statuses. Verify 'Completed (N)' text appears with correct count. Use mock fetch returning tasks with status 'done'.

2. **Collapse toggle** (~20 lines): Verify chevron icon is present. Click it — completed tasks disappear, header with count remains visible. Click again — completed tasks reappear.

3. **Default expanded state** (~10 lines): On render, completed tasks are visible (not collapsed).

4. **Zero active tasks** (~15 lines): Mock fetch with only 'done' tasks. Verify completed section renders at top without extra gap (check no empty active section adds spacing).

5. **Zero completed tasks** (~15 lines): Mock fetch with only 'todo'/'in-progress' tasks. Verify no 'Completed' header or divider renders. Verify no orphaned spacing elements.

6. **Both sections empty** (~10 lines): Mock fetch returning empty array. Verify no section headers or spacing elements appear.

7. **Count updates** (~15 lines): If possible with existing test patterns, verify count in header matches actual number of completed tasks after a status change.

8. **Collapsed state hides tasks but shows header** (~15 lines): Collapse the section. Verify individual completed task titles are not visible. Verify 'Completed (N)' is still visible.

Follow existing test patterns:
- Use `render(<App />)` with fetch mocked to return task data
- Use `screen.getByText`, `screen.queryByText`, `screen.getByRole`
- Use `fireEvent.click` for toggle interactions
- Use `waitFor` for async assertions

## Contract References

No contract changes.

## Acceptance Criteria

- [ ] All new tests pass (`npx vitest run`)
- [ ] Existing tests still pass (no regressions)
- [ ] Tests cover: section header with count, collapse toggle, default expanded state, 0 active tasks, 0 completed tasks, both empty, collapsed state shows header but hides tasks
