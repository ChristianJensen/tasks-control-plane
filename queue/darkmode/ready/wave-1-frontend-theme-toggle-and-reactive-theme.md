---
status: ready
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: darkmode
type: feature
---

## Description

Make App.jsx reactive to theme mode and add sun/moon toggle button to header

## Why

The existing theme infrastructure (dual theme objects in theme.js, FOUC-prevention script in index.html, data-theme CSS selectors) is already in place but App.jsx hardcodes the dark theme import. This task makes the theme reactive and adds the user-facing toggle control, delivering the complete dark/light mode feature.

## Implementation Notes

Modify `src/App.jsx` (~1237 lines). Key changes:

1. **Import Sun/Moon icons** (~1 line): Add `Sun, Moon` to the existing lucide-react import.

2. **Import getTheme** (~1 line): Change `import theme from './theme.js'` to `import { getTheme } from './theme.js'`.

3. **Theme state** (~5 lines): Add `const [themeMode, setThemeMode] = useState(() => { try { return document.documentElement.getAttribute('data-theme') || 'dark'; } catch(e) { return 'dark'; } })`. Derive theme object: `const theme = getTheme(themeMode)`.

4. **Toggle function** (~12 lines): Create `toggleTheme` function that: flips themeMode state, updates `document.documentElement.setAttribute('data-theme', newMode)`, writes to localStorage with try/catch fallback (E3: localStorage unavailable → in-memory only, no error shown).

5. **Toggle button in header** (~25 lines): Add a button next to the existing Help button (line ~1346 area, in the `marginLeft: 'auto'` flex container). Show Sun icon when themeMode === 'dark' (click for light), Moon icon when themeMode === 'light' (click for dark). Add `aria-label` that says 'Switch to light mode' or 'Switch to dark mode' based on current state. Add `title` attribute matching aria-label for tooltip. Style following existing Help button pattern.

6. **Verify light theme rendering**: Since all inline styles already reference `theme.colors.*`, `theme.glows.*`, etc., and `theme` is now derived from state, all components automatically get the correct theme values when mode changes. Check for any hardcoded color values in JSX that bypass the theme object (e.g., the `rgba(6,182,212,...)` values in card borders around lines 1313, 1352) and replace with theme references where feasible.

Edge cases:
- E1 (FOUC): Already handled by existing inline script in index.html — state initializer reads from `data-theme` attribute which is set before React renders.
- E2 (cleared browser data): Falls back to dark mode (no stored preference → attribute defaults to 'dark').
- E3 (localStorage unavailable): try/catch in toggle function, falls back to in-memory state only.

Files to modify: `src/App.jsx`
Files to read (reference only): `src/theme.js`, `index.html`, `src/index.css`

## Contract References

None — R7 confirms no backend or API contract changes required.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] A theme toggle (sun/moon icon) is visible in the app header next to the Help button
- [ ] Toggle icon shows Sun in dark mode (switch to light) and Moon in light mode (switch to dark)
- [ ] Toggle has an accessible aria-label/tooltip (e.g., 'Switch to light mode')
- [ ] Clicking the toggle switches between dark and light mode instantly — no page reload
- [ ] The selected theme persists across browser sessions via localStorage
- [ ] New users (no localStorage value) see dark mode by default
- [ ] All existing UI components and pages render correctly in both dark and light themes
- [ ] No flash of wrong theme on page load (theme applied before first paint via existing inline script)
- [ ] If localStorage is unavailable, toggle still works for the session (in-memory fallback, no error shown)
- [ ] No hardcoded color values bypass the theme object in component inline styles (audit and fix any found)
