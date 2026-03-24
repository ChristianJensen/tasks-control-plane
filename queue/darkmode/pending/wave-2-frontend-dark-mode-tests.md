---
status: pending
execution: autonomous
target-repo: frontend
wave: 2
priority: high
feature: darkmode
type: feature
depends-on:
  - wave-1-frontend-theme-system-toggle-and-light-mode.md
---

## Description

Add comprehensive tests for the dark mode toggle covering all acceptance criteria: toggle rendering, theme switching, localStorage persistence, fallback behavior, icon states, and component rendering in both themes.

## Why

Validates that the dark mode toggle works correctly across all requirements and edge cases. Tests ensure no regressions when future features are added and verify the localStorage persistence and fallback behavior.

## Implementation Notes

Modify `tests/App.test.jsx` (append to existing test file) and `tests/theme.test.js`. Follow existing test patterns with `vi.stubGlobal` for fetch mocking and `@testing-library/react`.

**tests/theme.test.js (~30 new lines):**
1. Test that `darkTheme` and `lightTheme` have identical shape (same keys at every level).
2. Test that `darkTheme` values match the original theme values exactly (R9 — no dark theme regression).
3. Test that `getTheme('dark')` returns darkTheme, `getTheme('light')` returns lightTheme.
4. Test that `getTheme('invalid')`, `getTheme('')`, `getTheme(null)` all return darkTheme (R14).

**tests/App.test.jsx (~120 new lines):**

1. **Toggle button rendering** (~10 lines): Verify toggle button is present in rendered app with appropriate aria-label. Verify it is a `<button>` element (R11).

2. **Theme toggle switches mode** (~15 lines): Click toggle → verify visual indicators change (e.g., body background changes, icon changes from Sun to Moon or vice versa). Click again → verify it switches back.

3. **Default is dark mode** (~10 lines): On first render (no localStorage), verify dark theme is active.

4. **Icon shows target theme** (~15 lines): In dark mode, verify Sun icon is shown (target = light). In light mode, verify Moon icon is shown (target = dark). R2.

5. **localStorage persistence** (~15 lines): Click toggle to light mode. Verify `localStorage.setItem` was called with 'light'. Re-render app. Verify light mode is restored from localStorage.

6. **localStorage unavailable** (~15 lines): Mock localStorage to throw on access. Render app. Verify dark mode is default and no errors thrown. R12.

7. **Invalid localStorage value** (~10 lines): Set localStorage theme value to 'invalid'. Render app. Verify dark mode is used. R14.

8. **Components render in light mode** (~15 lines): Toggle to light mode. Verify key components are visible and functional — task list renders, can interact with tasks. Verify no crashes.

9. **No API calls on toggle** (~10 lines): Toggle theme back and forth. Verify no additional fetch calls were made (theme is client-side only). R7.

10. **Aria attributes** (~10 lines): Verify toggle button has descriptive aria-label that changes with theme state.

Follow existing test patterns:
- Use `render(<App />)` with fetch mocked to return task data
- Use `screen.getByRole`, `screen.getByText`, `screen.queryByText`
- Use `fireEvent.click`
- Use `waitFor` for async assertions
- Mock localStorage via `vi.spyOn(Storage.prototype, 'getItem')` etc.

## Contract References

No contract references — frontend-only tests with no API changes.

## Acceptance Criteria

- [ ] All existing tests continue to pass (`npx vitest run`)
- [ ] New theme token tests verify darkTheme/lightTheme shape parity and darkTheme value preservation (R9)
- [ ] New toggle tests verify button rendering, semantic <button> element (R11), and aria attributes
- [ ] Tests verify dark mode is default when no localStorage value exists (R1)
- [ ] Tests verify toggle icon shows target theme (sun in dark, moon in light) (R2)
- [ ] Tests verify instant theme switch on toggle click (R3)
- [ ] Tests verify localStorage persistence and restoration (R4)
- [ ] Tests verify graceful fallback when localStorage is unavailable (R12)
- [ ] Tests verify invalid localStorage values default to dark (R14)
- [ ] Tests verify no API calls are made during theme toggling (R7)
- [ ] Tests verify components render without errors in both themes (R6)
