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

Add comprehensive tests for the dark/light mode toggle covering all acceptance criteria: rendering, toggle behavior, localStorage persistence, edge cases, and non-regression of existing features.

## Why

Ensures the theme toggle works correctly across all scenarios and edge cases, and that existing functionality is not broken by the theme refactoring.

## Implementation Notes

Modify `tests/App.test.jsx` (append to existing file). Follow existing test patterns: `vi.stubGlobal('fetch', mockFetch)`, `render(<App />)`, `@testing-library/react` queries.

Also update `tests/theme.test.js` if needed for any theme.js changes.

**Test cases (~150 lines total):**

1. **Toggle button rendering** (~10 lines): Verify theme toggle button is present with `aria-label="Toggle theme"`. Verify it renders in the header area.

2. **Default dark mode** (~15 lines): Clear localStorage, render app, verify `document.documentElement.getAttribute('data-theme')` is 'dark'. Verify the initial icon is Sun (indicating "click for light").

3. **Toggle to light mode** (~15 lines): Click toggle button, verify `data-theme` changes to 'light'. Verify icon changes to Moon.

4. **Toggle back to dark** (~10 lines): Click toggle twice, verify returns to dark mode.

5. **localStorage persistence** (~15 lines): Click toggle to light, verify `localStorage.getItem('theme-preference')` is 'light'. Click again, verify it's 'dark'.

6. **Saved preference applied on load** (~15 lines): Set `localStorage.setItem('theme-preference', 'light')` before render. Verify app loads in light mode (`data-theme` is 'light').

7. **Invalid localStorage fallback (E1)** (~15 lines): Set `localStorage.setItem('theme-preference', 'blue')` before render. Verify app defaults to dark mode.

8. **localStorage unavailable (E3)** (~20 lines): Mock localStorage to throw on getItem/setItem. Render app. Verify defaults to dark. Click toggle — verify it switches without throwing. Verify no error displayed.

9. **No localStorage = default dark** (~10 lines): Ensure no 'theme-preference' key exists. Render app. Verify dark mode.

10. **Existing features work in light mode** (~20 lines): Toggle to light mode. Add a task. Verify task appears. Toggle status. Verify it works. This is a basic regression check.

11. **Theme toggle does not trigger API calls** (~10 lines): Record fetch call count before toggle. Click toggle. Verify no additional fetch calls were made.

Follow existing patterns:
- Use `render(<App />)` with fetch mocked to return task data
- Use `screen.getByRole`, `screen.getByLabelText`, `screen.getByText`
- Use `fireEvent.click` for toggle interactions
- Use `waitFor` for async assertions
- Mock localStorage where needed using `vi.spyOn(Storage.prototype, ...)`

## Contract References

None — frontend-only feature, no API contract involvement.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Toggle button rendering is tested
- [ ] Default dark mode on fresh load is tested
- [ ] Toggle switching between dark and light is tested
- [ ] localStorage persistence of preference is tested
- [ ] Saved preference applied on load is tested
- [ ] Invalid localStorage value fallback to dark is tested (E1)
- [ ] localStorage unavailable graceful degradation is tested (E3)
- [ ] Basic regression test confirms existing features work in light mode
- [ ] Theme toggle does not trigger unnecessary API calls
