---
status: ready
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: darkmode-lightmode
type: feature
---

## Description

Create the CSS custom properties theme system, blocking initialization script, and theme toggle component with localStorage persistence.

## Why

This is the foundation for dark/light mode. Without CSS custom properties as the single source of truth for colors (R7, R13), a blocking init script to prevent flash of wrong theme (R5, E1), and a toggle mechanism (R2), none of the theming work can function. This task builds the complete theme infrastructure and user-facing toggle.

## Implementation Notes

**New file: `src/theme.css`** (~70 lines)
- Define CSS custom properties under `[data-theme="dark"]` and `[data-theme="light"]` selectors on `:root`/`html`.
- Dark palette maps existing colors: `--bg-primary: #020617`, `--bg-secondary: #0f172a`, `--bg-tertiary: #1e293b`, `--bg-surface: rgba(15,23,42,0.6)`, `--text-primary: #ecfeff`, `--text-secondary: #94a3b8`, `--text-muted: #64748b`, `--border-primary: rgba(6,182,212,0.3)`, `--border-subtle: rgba(6,182,212,0.15)`, `--overlay-bg: rgba(2,6,23,0.6)`, `--scrollbar-track: #0f172a`, `--scrollbar-thumb: #164e63`, `--selection-bg: #164e63`, `--selection-color: #ecfeff`.
- Light palette: derive from dark — `--bg-primary: #f8fafc`, `--bg-secondary: #ffffff`, `--bg-tertiary: #f1f5f9`, `--bg-surface: rgba(255,255,255,0.8)`, `--text-primary: #0f172a`, `--text-secondary: #475569`, `--text-muted: #94a3b8`, `--border-primary: rgba(6,182,212,0.4)`, `--border-subtle: #e2e8f0`, `--overlay-bg: rgba(0,0,0,0.4)`, etc.
- Accent colors (cyan, fuchsia, rose, amber) stay the same across themes — they already have good contrast on both dark and light backgrounds.
- Add `html { transition: background-color 0.2s ease, color 0.2s ease; }` and `* { transition: background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease; }` for smooth theme transitions (R10).

**Modify: `index.html`** (~10 lines)
- Add a blocking `<script>` in `<head>` before any other scripts:
```js
(function() {
  try {
    var t = localStorage.getItem('theme');
    if (t !== 'dark' && t !== 'light') t = 'dark';
    document.documentElement.setAttribute('data-theme', t);
  } catch(e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
```
- This prevents flash of wrong theme (R5, E1) and handles localStorage unavailability (R11, E2).

**Modify: `src/index.css`** (~10 lines)
- Replace hardcoded colors in `::selection`, `::-webkit-scrollbar-track`, `::-webkit-scrollbar-thumb`, and `::-webkit-scrollbar-thumb:hover` with CSS custom properties from theme.css.

**Modify: `src/main.jsx`** (~1 line)
- Import `./theme.css` before `./index.css` so variables are available.

**Modify: `src/App.jsx`** (~60 lines)
- Import `Sun` and `Moon` icons from `lucide-react`.
- Add `useTheme` hook or inline state: reads current theme from `document.documentElement.getAttribute('data-theme')`, provides `toggleTheme()` function that flips `data-theme` attribute and writes to localStorage. Validates stored value (R11, E2).
- Create `ThemeToggle` inline component: renders Sun icon when in dark mode (indicating 'switch to light'), Moon icon when in light mode. Minimum 44x44px tap target (R15). `title` attribute for tooltip (R9): 'Switch to light mode' / 'Switch to dark mode'. Place in header near existing help button.
- Re-render on toggle via useState that tracks current theme string.

**Tests** (~80 lines in `tests/App.test.jsx`)
- App loads with dark mode by default (data-theme='dark' or equivalent).
- Toggle button renders with correct icon (Sun for dark mode).
- Clicking toggle switches theme state.
- localStorage is written on toggle.
- Invalid localStorage value falls back to dark mode.
- Missing localStorage falls back to dark mode.
- Tooltip text changes based on current theme.
- Toggle button has minimum 44x44px styling (check inline styles).

Edge cases: E1 (flash prevention via blocking script — test index.html manually), E2 (invalid localStorage — test in unit tests).

## Contract References

None — this feature is entirely client-side. No API endpoints affected.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] A dedicated theme.css file exists with CSS custom properties for both dark and light themes (R7, R13)
- [ ] Theme is applied via `data-theme` attribute on `<html>` element (R12)
- [ ] App loads in dark mode by default when no theme preference is stored (R1)
- [ ] Blocking script in index.html prevents flash of wrong theme (R5, E1)
- [ ] Invalid or missing localStorage values gracefully fall back to dark mode (R11, E2)
- [ ] Toggle button (sun/moon icon) is visible in the header (R2)
- [ ] Clicking toggle switches theme without page reload (R3)
- [ ] Theme preference is saved to localStorage on toggle (R4)
- [ ] Toggle includes tooltip indicating the action (R9)
- [ ] Toggle button has at least 44x44px tap target (R15)
- [ ] Theme transitions smoothly via CSS transition ~200ms (R10)
- [ ] index.css uses CSS custom properties instead of hardcoded colors
- [ ] No new runtime dependencies added (R8)
