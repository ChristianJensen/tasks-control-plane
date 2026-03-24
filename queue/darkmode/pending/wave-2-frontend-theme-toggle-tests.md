---
status: pending
execution: autonomous
target-repo: frontend
wave: 2
priority: normal
feature: darkmode
type: feature
depends-on:
  - wave-1-frontend-theme-toggle-and-reactive-theme.md
---

## Description

Add comprehensive tests for theme toggle functionality covering all acceptance criteria

## Why

Validates the dark/light mode toggle implementation works correctly across all scenarios including persistence, accessibility, edge cases, and visual correctness in both themes.

## Implementation Notes

Modify `tests/App.test.jsx` (append to existing file, following existing patterns with `vi.stubGlobal` for fetch mocking and `@testing-library/react`).

Setup considerations:
- Mock `localStorage` using `vi.stubGlobal` or a simple mock object with `getItem`/`setItem`/`removeItem`.
- Mock `document.documentElement.setAttribute` and `getAttribute` as needed.
- The existing test setup uses jsdom which supports `data-*` attributes.

Test cases to add (~180 lines):

1. **Toggle button rendering** (~10 lines): Verify a button with aria-label containing 'Switch to' is present in the rendered app.

2. **Toggle switches theme** (~15 lines): Click toggle → verify aria-label changes from 'Switch to light mode' to 'Switch to dark mode' (or vice versa). Verify `data-theme` attribute on `<html>` changes.

3. **Correct icons** (~15 lines): In dark mode, verify Sun icon is shown. Click toggle. Verify Moon icon is shown. (Test via aria-label or icon presence.)

4. **localStorage persistence** (~20 lines): Click toggle to switch to light mode. Verify `localStorage.setItem` was called with 'theme' and 'light'. Simulate re-render with localStorage returning 'light' — verify app starts in light mode.

5. **Default to dark mode** (~10 lines): With no localStorage value, verify app renders in dark mode. Verify toggle aria-label says 'Switch to light mode'.

6. **localStorage unavailable** (~20 lines): Mock localStorage.setItem to throw. Click toggle. Verify no error is thrown. Verify theme still switches visually (in-memory).

7. **Accessibility attributes** (~15 lines): Verify toggle button has aria-label. Verify aria-label updates when theme changes. Verify button has title attribute matching aria-label.

8. **No API calls on toggle** (~10 lines): Track fetch mock call count before toggle. Click toggle. Verify no additional fetch calls were made.

9. **Theme applied to components** (~20 lines): Render app in light mode (set localStorage to 'light'). Verify key UI elements use light theme colors (spot-check a few style values or class names).

10. **Toggle does not interfere with existing features** (~15 lines): Open app, toggle theme, verify task list still renders, verify help button still works.

11. **WCAG contrast note** (~10 lines): Verify light theme text colors exist and differ from dark theme (basic sanity check on theme object).

Add theme utility tests in `tests/theme.test.js` (~20 lines):
- `getTheme('dark')` returns darkTheme
- `getTheme('light')` returns lightTheme
- `getTheme(undefined)` returns darkTheme (default)
- Both themes have all required keys

Follow existing test patterns: `render(<App />)`, `screen.getByRole`, `screen.getByLabelText`, `fireEvent.click`, `waitFor`.

## Contract References

None — frontend-only feature, no API contract involved.

## Acceptance Criteria

- [ ] All existing tests continue to pass (`npx vitest run`)
- [ ] New tests cover: toggle rendering, theme switching, correct icons, localStorage persistence, dark mode default, localStorage unavailable fallback, accessibility attributes, no API calls on toggle, theme applied to components, non-interference with existing features
- [ ] Theme utility tests cover getTheme for dark, light, and undefined inputs
- [ ] Tests follow existing patterns (vi.stubGlobal, @testing-library/react, fireEvent)
