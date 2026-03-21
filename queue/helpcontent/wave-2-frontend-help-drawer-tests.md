---
status: ready
execution: autonomous
target-repo: frontend
wave: 2
priority: high
feature: helpcontent
type: feature
depends-on:
  - wave-1-frontend-help-drawer-component.md
---

## Description

Add comprehensive tests for the HelpDrawer component covering all acceptance criteria: rendering, toggle behavior, close mechanisms, keyboard accessibility, focus management, and non-interference with app state.

## Why

Ensures all acceptance criteria and edge cases are verified with automated tests. The HelpDrawer must work correctly across all interaction modes (click, keyboard, backdrop) and must not interfere with existing app functionality.

## Implementation Notes

Add tests in tests/App.test.jsx (append to existing test file, following existing patterns with vi.stubGlobal for fetch mocking and @testing-library/react).

Test cases to add (~180 lines):

1. **Help button rendering** — verify HelpCircle button is present in rendered app, has aria-label="Help".

2. **Drawer toggle** — click help button → drawer appears with help content. Click again → drawer disappears.

3. **Help content sections** — verify all 7 section headings are rendered: Creating Tasks, Viewing & Filtering Tasks, Updating Tasks, Deleting Tasks, Categories, Comments, Status Workflow.

4. **Close via X button** — open drawer, click close button, verify drawer is removed from DOM.

5. **Close via backdrop click** — open drawer, click the backdrop overlay, verify drawer closes.

6. **Close via Escape key** — open drawer, fire Escape keydown event, verify drawer closes.

7. **No API calls on open/close** — open and close drawer, verify no fetch calls were made during the interaction (check fetch mock call count before/after).

8. **Focus management** — open drawer, verify focus moves to close button (or first focusable element). Close drawer, verify focus returns to help button.

9. **Aria attributes** — verify help button has aria-expanded="false" initially, aria-expanded="true" when drawer is open.

10. **Does not affect edit state** — if possible with existing test patterns, start editing a task, open help drawer, close it, verify edit is still in progress.

Follow existing test patterns:
- Use `render(<App />)` with fetch mocked to return task data
- Use `screen.getByRole`, `screen.getByText`, `screen.queryByText`
- Use `fireEvent.click`, `fireEvent.keyDown`
- Use `waitFor` for async assertions

## Contract References

None — no API calls involved.

## Acceptance Criteria

- [ ] All new tests pass (`npx vitest run`)
- [ ] Existing tests continue to pass (no regressions)
- [ ] Tests cover: help button rendering with aria attributes
- [ ] Tests cover: drawer open/close toggle via help button
- [ ] Tests cover: all 7 help content sections rendered
- [ ] Tests cover: close via X button
- [ ] Tests cover: close via backdrop click
- [ ] Tests cover: close via Escape key
- [ ] Tests cover: no API calls made when opening/closing drawer
- [ ] Tests cover: focus management (focus into drawer on open, return on close)
