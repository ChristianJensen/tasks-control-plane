---
feature: darkmode-lightmode
completed: 2026-03-24
tasks: 2
waves: 2
---

## Overview

End users of the task management app currently have a fixed dark-ish theme with no ability to switch to a light theme. Dark mode is a baseline expectation for modern web apps, but so is user choice. Users in bright environments or those who simply prefer light backgrounds have no option, creating a perceived quality gap. This feature adds a manual toggle so users can switch between dark mode (default) and light mode, with their preference persisted across sessions.

## What Was Built

### Wave 1

- **frontend** — Create the CSS custom properties theme system, blocking initialization script, and theme toggle component with localStorage persistence.

### Wave 2

- **frontend** — Refactor all hardcoded color values in App.jsx and theme.js to use CSS custom properties, ensuring both dark and light themes render correctly across all UI elements.

## Key Decisions

- **wave-1-frontend-theme-infrastructure-and-toggle:** **New file: `src/theme.css`** (~70 lines)
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
- **wave-2-frontend-refactor-colors-to-css-variables:** **Modify: `src/theme.js`** (~25 lines)
- Update theme token values to reference CSS custom properties using a helper or direct strings. Since inline styles can use `var()`, change values like:
  - `colors.slateDark` → `'var(--bg-primary)'`
  - `colors.slate900` → `'var(--bg-secondary)'`
  - `colors.slate800` → `'var(--bg-tertiary)'`
  - `colors.slate700` → `'var(--border-color)'`
  - `colors.slate600` → `'var(--text-muted)'`
  - `colors.slate500` → `'var(--text-secondary)'`
  - `colors.cyanLight` → `'var(--text-primary)'`
- Keep accent colors (cyan400, fuchsia400, rose500, amber400, etc.) as-is — they work on both themes.
- Update `card.background` → `'var(--bg-surface)'`, `card.border` → `'1px solid var(--border-primary)'`.
- Update `glows` to use CSS vars where backgrounds are referenced.

**Modify: `src/App.jsx`** (~120 lines of changes)
- Replace hardcoded rgba() values for backgrounds, borders, and overlays with CSS custom properties:
  - `rgba(2,6,23,0.6)` (dark overlay) → `var(--overlay-bg)`
  - `rgba(2,6,23,0.7)` and `rgba(2,6,23,0.8)` → `var(--overlay-bg-heavy)`
  - `rgba(15,23,42,0.6)` and `rgba(15,23,42,0.4)` (card bg) → `var(--bg-surface)`
  - `rgba(30,41,59,0.4)` (surface) → `var(--bg-surface-hover)`
  - `rgba(6,182,212,0.3)` (cyan border) → `var(--border-primary)` — this is already in theme.css from wave 1
  - `rgba(6,182,212,0.15)` (subtle border) → `var(--border-subtle)`
  - `rgba(6,182,212,0.2)` and `rgba(6,182,212,0.5)` → `var(--border-primary)` / `var(--border-hover)`
  - `'#fff'` for text → `var(--text-primary)`
  - `rgba(100,116,139,0.4)` → `var(--border-muted)`
- Fix the HelpDrawer overlay and panel colors.
- Fix confirmation dialog, toast, and modal backgrounds.
- Fix input field backgrounds and borders.
- Fix hover states to use theme-aware colors.
- Note: Priority badge colors, category badge colors, and accent glows (fuchsia, cyan) stay hardcoded — they're accent colors that work on both themes.

**Potentially add to `src/theme.css`** (~15 lines)
- Add any additional CSS custom properties discovered during refactoring (e.g., `--bg-surface-hover`, `--overlay-bg-heavy`, `--border-hover`, `--border-muted`, `--input-bg`).

**Tests** (~80 lines in `tests/App.test.jsx` and `tests/theme.test.js`)
- All existing tests still pass (refactoring should not change behavior in dark mode).
- Task items render correctly in both themes (no hardcoded dark-only colors remain in key elements).
- Card backgrounds use CSS variables.
- Input fields are readable in light mode.
- Modals/dialogs have correct backgrounds in both themes.
- HelpDrawer renders correctly in light mode.
- Theme.js tokens resolve to CSS variable references.
- Priority and category badges remain visually distinct in both themes.

Edge cases: Verify all UI elements from R6 — backgrounds, text, borders, buttons, inputs, cards, modals.

## Contracts Affected

(No contracts referenced)

## Retrospective Notes

(No retrospective entries)
