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

Make the theme reactive via state, add sun/moon toggle button to header, persist preference to localStorage, and set data-theme attribute on <html> for CSS selectors.

## Why

This is the core implementation of the dark/light mode feature. The theme infrastructure (both palettes, getTheme, data-theme CSS selectors) already exists but is statically wired to dark mode. This task makes it dynamic and user-controllable.

## Implementation Notes

Modify `src/App.jsx` and minimally `src/theme.js`.

**1. Theme state and initialization (~20 lines)**
- Import `getTheme` from `./theme.js` instead of default `theme`.
- Import `Sun` and `Moon` from `lucide-react`.
- Add `themeMode` state initialized from localStorage with fallback to 'dark':
  ```
  const [themeMode, setThemeMode] = useState(() => {
    try {
      const saved = localStorage.getItem('theme-preference');
      return saved === 'light' ? 'light' : 'dark'; // E1: invalid values fall back to dark
    } catch { return 'dark'; } // E3: localStorage unavailable
  });
  ```
- Derive `const theme = getTheme(themeMode);`

**2. Side effects (~15 lines)**
- `useEffect` to set `document.documentElement.setAttribute('data-theme', themeMode)` and persist to localStorage (wrapped in try/catch for E3).

**3. Toggle function (~5 lines)**
- `toggleTheme` function: flips themeMode between 'dark' and 'light'.

**4. Toggle button in header (~15 lines)**
- Add sun/moon icon button next to the existing help button in the header area (near line 1346).
- Show Sun icon in dark mode (click to switch to light), Moon icon in light mode (click to switch to dark) — matches GitHub/VS Code convention per UX2.
- Style consistently with existing help button.
- Add `aria-label="Toggle theme"`.

**5. Move theme-dependent module-level constants inside App (~40 lines)**
- `PRIORITY_COLORS`, `CATEGORY_COLORS`, `cardStyle`, `darkInputStyle`, `taskBtnStyle` are defined at module scope using `theme`. These must move inside the App component (or be derived from the reactive `theme` variable) so they update when theme changes.
- Use `useMemo` for `cardStyle`, `darkInputStyle`, `taskBtnStyle` to avoid re-creating every render.
- `PRIORITY_COLORS` and `CATEGORY_COLORS` can be simple derived `const` inside the component.

**6. Pass theme to child components (~20 lines)**
- `HelpDrawer`, `CategoryPicker`, and task item components reference `theme` from module scope. Pass `theme` as a prop or ensure they access the reactive variable via closure.
- Check `SortableTaskItem`, `CompletedTaskItem`, `TaskItem` — if defined inside App they get closure access; if outside, need `theme` prop.

**7. Update colorScheme for date input (~2 lines)**
- The date input has hardcoded `colorScheme: 'dark'`. Change to `colorScheme: themeMode`.

**8. Light mode background adjustments (~10 lines)**
- Background glow orbs and grid overlay use hardcoded rgba values. For light mode, these should be subtler or adjusted. Can conditionally adjust opacity or hide them in light mode.

**Edge cases:**
- E1: Invalid localStorage value → treated as 'dark' (the `saved === 'light'` check handles this)
- E2: Flash of wrong theme on load → accepted per spec, no inline script needed
- E3: localStorage unavailable → toggle works for session, no error shown

## Contract References

None — R7 confirms this is a frontend-only feature with no API changes.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] A sun/moon toggle button is visible in the app header/navbar
- [ ] Clicking the toggle switches between dark and light themes instantly (no reload)
- [ ] The dark theme matches the current app appearance (no visual regression)
- [ ] The light theme provides appropriate contrast and readability
- [ ] Theme preference is persisted in localStorage under key 'theme-preference'
- [ ] On fresh load with no saved preference, the app defaults to dark mode
- [ ] On fresh load with a saved 'light' preference, the app loads in light mode
- [ ] Invalid localStorage values (e.g. 'blue') fall back to dark mode (E1)
- [ ] If localStorage is unavailable, toggle works for current session without error (E3)
- [ ] All existing features (task CRUD, filters, sorting, comments, status history, drag-reorder, help drawer) work correctly in both themes
- [ ] data-theme attribute on <html> is set to 'dark' or 'light' matching current mode
- [ ] Icon shows Sun in dark mode (switch to light) and Moon in light mode (switch to dark) per UX2
