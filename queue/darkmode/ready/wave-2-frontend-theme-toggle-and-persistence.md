---
status: ready
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: darkmode
type: feature
depends-on:
  - wave-1-frontend-css-variables-and-theme-infrastructure.md
---

## Description

Add a theme toggle button in the header with sun/moon icons, localStorage persistence with graceful degradation, live OS preference detection via matchMedia, and full keyboard/screen-reader accessibility.

## Why

This task delivers the user-facing dark mode feature. Users need a discoverable toggle to switch themes, their preference must persist across sessions, and the app must respect OS-level theme preferences when no manual choice has been made.

## Implementation Notes

Modify `src/App.jsx`:

1. **Import icons**: Add `Sun` and `Moon` from `lucide-react` (already a dependency, just add to existing import).

2. **Theme state and helpers** (~30 lines): Add a `useTheme` custom hook or inline state management. State: `const [currentTheme, setCurrentTheme] = useState(() => { ... })`. Initializer reads from `document.documentElement.getAttribute('data-theme')` (already set by FOUC script from wave 1). Helper function `toggleTheme()`: flips between 'light' and 'dark', sets `data-theme` attribute on `document.documentElement`, saves to localStorage with try/catch for graceful degradation (R11, E1). Track whether user has manually chosen via a ref or separate state (`hasManualPreference`).

3. **OS preference listener** (~15 lines): `useEffect` that adds a `matchMedia('(prefers-color-scheme: dark)')` change listener. On change, if NO manual localStorage preference exists, update theme to match OS. Manual choice always wins (R9, E2). Clean up listener on unmount.

4. **ThemeToggle component** (~30 lines): A `<button>` element (not div/span) placed in the app header/toolbar area, top-right near existing help button. Shows `Sun` icon when in dark mode (indicating 'switch to light'), `Moon` icon when in light mode (indicating 'switch to dark'). Dynamic `aria-label`: 'Switch to dark mode' / 'Switch to light mode' (R10, UX2). Add `title` attribute for tooltip on hover (R12). Same sizing as other header action buttons. Keyboard accessible natively via `<button>` element (Enter/Space activation). Style with theme tokens, consistent with existing header buttons.

5. **localStorage graceful degradation** (E1, R11): Wrap all `localStorage.getItem` and `localStorage.setItem` calls in try/catch. If localStorage is unavailable, toggle works in-memory for the current session. On reload without localStorage, falls back to OS preference then to light.

6. **Wire into header**: Place the toggle button in the header area near the help button. Ensure it doesn't disrupt existing layout.

Edge cases addressed:
- E1: localStorage disabled — try/catch, in-memory fallback
- E2: OS preference changes while app open — matchMedia listener, manual choice wins
- R9: Live OS changes update theme when no manual preference saved
- R10/UX2: Button element with dynamic aria-label
- R11: Graceful degradation
- R12: Tooltip on hover, top-right placement

Tests to add in `tests/App.test.jsx` (~100 lines):
- Toggle button renders in header with correct icon (Moon in light mode)
- Clicking toggle switches theme (data-theme attribute changes)
- aria-label updates dynamically ('Switch to dark mode' ↔ 'Switch to light mode')
- Icon switches between Sun and Moon based on theme
- Theme preference persists to localStorage on toggle
- OS preference is respected when no localStorage value exists (mock matchMedia)
- Manual toggle overrides OS preference
- Live OS preference change updates theme when no manual preference (mock matchMedia change event)
- Live OS preference change does NOT override manual choice
- Graceful degradation when localStorage throws (mock localStorage to throw)
- Toggle is keyboard accessible (button element, responds to click events)
- No API calls made during theme toggle (fetch mock not called)

## Contract References

None — frontend-only feature, no API changes (R8).

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Toggle button is visible in header area with sun/moon icon
- [ ] Clicking toggle instantly switches all UI colors between light and dark
- [ ] Moon icon shown in light mode, Sun icon shown in dark mode
- [ ] Theme preference saved to localStorage under key 'theme' with value 'light' or 'dark'
- [ ] Theme restored from localStorage on page reload (no flash)
- [ ] OS prefers-color-scheme respected when no localStorage preference exists
- [ ] Live OS preference changes update theme when no manual preference is saved
- [ ] Manual toggle overrides and persists over OS preference
- [ ] Toggle is a <button> with dynamic aria-label ('Switch to dark mode' / 'Switch to light mode')
- [ ] Toggle is keyboard-accessible (focusable, Enter/Space activates)
- [ ] Tooltip shown on hover (title attribute)
- [ ] Graceful degradation when localStorage unavailable (toggle works in-memory, falls back to OS preference on reload)
- [ ] No new runtime dependencies added
- [ ] No API calls triggered by theme toggle
