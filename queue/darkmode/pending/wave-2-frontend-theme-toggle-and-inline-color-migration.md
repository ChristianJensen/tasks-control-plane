---
status: pending
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: darkmode
type: feature
depends-on:
  - wave-1-frontend-css-variables-and-light-theme.md
---

## Description

Add a sun/moon theme toggle icon button to the header, implement localStorage-backed theme switching, replace inline rgba() dark-background values in App.jsx with CSS variable references, and ensure all views render correctly in both themes.

## Why

This task delivers the user-facing theme toggle feature (R3, R4, R5) and migrates the remaining hardcoded inline rgba() background colors in App.jsx to CSS variables so they respond to theme changes (R8). Without this migration, ~25 inline dark backgrounds (rgba(2,6,23,...), rgba(15,23,42,...), rgba(30,41,59,...)) would remain dark even in light mode.

## Implementation Notes

**Files to modify:**

1. **src/App.jsx** (~150 lines changed):
   - **Import:** Add `Sun`, `Moon` from `lucide-react` (already a dependency).
   - **Theme state:** Add `const [isDark, setIsDark] = useState(() => { try { return localStorage.getItem('theme') !== 'light'; } catch { return true; } })`. Read initial value from localStorage with try/catch fallback.
   - **Toggle function:** `const toggleTheme = () => { const next = isDark ? 'light' : 'dark'; document.documentElement.setAttribute('data-theme', next); try { localStorage.setItem('theme', next); } catch {} setIsDark(!isDark); }`
   - **Toggle button:** Add to header/navbar area (near existing HelpCircle button). Show `Sun` icon when in dark mode (click to switch to light), `Moon` icon when in light mode (click to switch to dark). Add `aria-label` ('Switch to light mode' / 'Switch to dark mode'). Style following existing icon button patterns.
   - **Inline rgba() migration:** Replace hardcoded dark rgba backgrounds with CSS variable references. Add new CSS variables to index.css for these: `--bg-overlay` (for rgba(2,6,23,0.6-0.85)), `--bg-card` (for rgba(15,23,42,0.3-0.95)), `--bg-surface` (for rgba(30,41,59,0.4-0.6)), `--bg-input` (for input/textarea backgrounds). Group similar rgba values into a few semantic variables. Update corresponding `[data-theme="light"]` overrides in index.css.
   - **Accent rgba values** (cyan, fuchsia, rose with alpha) can remain as-is — they work as highlights on both dark and light backgrounds.

2. **src/index.css** (~20 lines added): Add the new semantic background CSS variables to `:root` and `[data-theme="light"]`.

3. **tests/App.test.jsx** (~80 lines added): Test cases:
   - Toggle button renders in header with sun icon (dark mode default)
   - Clicking toggle switches icon to moon (light mode)
   - Clicking toggle sets data-theme="light" on documentElement
   - Clicking toggle again removes/changes data-theme back to dark
   - localStorage.setItem is called with correct theme value on toggle
   - On initial render with localStorage theme=light, moon icon is shown
   - Toggle works gracefully when localStorage throws (mock localStorage.getItem to throw)
   - aria-label updates based on current theme

**Edge cases:**
- E1: Flash of wrong theme → handled by wave-1 inline script
- E2: localStorage unavailable → try/catch around getItem/setItem, toggle still works for session
- R8: All views correct in both themes → inline rgba migration ensures backgrounds switch

**UX2 convention:** Icon shows the mode you'll switch TO — sun in dark mode, moon in light mode (GitHub convention).

## Contract References

No API contract changes. Frontend-only feature.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] A sun/moon toggle icon is visible in the header/navbar
- [ ] Toggle icon shows sun when in dark mode, moon when in light mode (UX2 convention)
- [ ] Clicking the toggle switches the theme instantly with no page reload
- [ ] data-theme attribute is set on document.documentElement when toggling
- [ ] Theme preference is persisted in localStorage under key 'theme' with values 'dark'/'light'
- [ ] On page load with localStorage theme=light, app renders in light mode with moon icon
- [ ] Default theme is dark when no localStorage value exists
- [ ] Graceful fallback when localStorage is unavailable — toggle works for session but doesn't persist
- [ ] All inline rgba() dark-background values in App.jsx are replaced with CSS variable references
- [ ] All pages/components render correctly in both dark and light themes (no broken contrast or invisible elements)
- [ ] Toggle button has appropriate aria-label that updates based on current theme
