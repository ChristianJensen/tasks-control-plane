---
status: pending
execution: autonomous
target-repo: frontend
wave: 2
priority: normal
feature: darkmode
type: feature
depends-on:
  - wave-1-frontend-theme-toggle-and-application.md
---

## Description

Add comprehensive tests for the dark/light mode toggle covering all acceptance criteria: theme tokens, toggle behavior, localStorage persistence, flash prevention, accessibility, and visual consistency.

## Why

Validates that the entire theme system works correctly across all edge cases and acceptance criteria. Tests ensure regressions are caught if future features modify theme-related code.

## Implementation Notes

**tests/theme.test.js (~50 lines added):**
1. Test that `darkTheme` and `lightTheme` have identical keys/structure
2. Test that `getTheme('dark')` returns darkTheme and `getTheme('light')` returns lightTheme
3. Test that darkTheme values match the original theme values exactly (AC1 regression)
4. Test that light theme colors differ from dark theme colors (sanity check)

**tests/App.test.jsx (~150 lines added):**
Append to existing test file following existing patterns (vi.stubGlobal for fetch, @testing-library/react).

1. **Toggle button rendering** (~15 lines): Verify sun icon button present in header with aria-label 'Switch to light mode' (default dark mode).

2. **Toggle to light mode** (~20 lines): Click sun icon → verify moon icon appears, aria-label changes to 'Switch to dark mode'.

3. **Toggle back to dark mode** (~15 lines): Click moon icon → verify sun icon returns, aria-label changes back.

4. **localStorage persistence** (~20 lines): Toggle to light mode → verify `localStorage.setItem` called with ('theme', 'light'). Toggle back → verify called with ('theme', 'dark').

5. **localStorage read on mount** (~20 lines): Set `localStorage.getItem` to return 'light' → render App → verify moon icon shown (light mode active).

6. **Default dark mode** (~10 lines): No localStorage value → render App → verify sun icon shown (dark mode default).

7. **localStorage unavailable** (~15 lines): Mock localStorage to throw on access → render App → verify dark mode active, no console errors.

8. **Accessibility - aria-label updates** (~15 lines): Verify aria-label toggles between 'Switch to light mode' and 'Switch to dark mode' on each click.

9. **data-theme attribute** (~15 lines): Toggle theme → verify `document.documentElement.getAttribute('data-theme')` updates to 'light' then back to 'dark'.

10. **No API calls on theme toggle** (~10 lines): Toggle theme multiple times → verify no additional fetch calls made (R8 — frontend only).

Follow existing test patterns: `render(<App />)`, `screen.getByRole`, `screen.getByLabelText`, `fireEvent.click`, `waitFor`.

**Note on flash prevention testing:** The blocking inline script in index.html runs before React and cannot be easily tested in jsdom. Document this limitation. The data-theme attribute test (case 9) validates the React-side behavior.

## Contract References

None — frontend-only change with no API contract impact (R8).

## Acceptance Criteria

- [ ] All existing tests still pass (`npx vitest run`)
- [ ] New theme token tests validate dark/light theme structure parity
- [ ] New theme token tests validate dark theme matches original values (AC1)
- [ ] Toggle behavior tests cover sun→moon→sun cycle (AC3, AC4)
- [ ] localStorage persistence tests verify read and write (AC5, AC6)
- [ ] localStorage unavailable test confirms graceful fallback to dark mode (AC11)
- [ ] Accessibility tests verify dynamic aria-label updates (AC10)
- [ ] data-theme attribute test verifies DOM updates on toggle
- [ ] No API calls made during theme toggle operations (R8)
