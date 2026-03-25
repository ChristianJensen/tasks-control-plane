---
feature: darkmode
completed: 2026-03-25
tasks: 2
waves: 2
---

## Overview

All users of the task management app need a dark mode option to reduce eye strain in low-light environments and to respect OS-level theme preferences. Dark mode is an expected baseline feature for modern web apps and its absence signals a lack of UI polish. This is a frontend-only feature — no backend or API changes are required.

## What Was Built

### Wave 1

- **frontend** — Define light and dark CSS custom property sets, refactor theme.js and all hardcoded colors to use CSS variables, and add FOUC prevention inline script in index.html.

### Wave 2

- **frontend** — Add a theme toggle button in the header with sun/moon icons, localStorage persistence with graceful degradation, live OS preference detection via matchMedia, and full keyboard/screen-reader accessibility.

## Key Decisions

- **wave-1-frontend-css-variables-and-theme-infrastructure:** Modify `src/index.css`: Define two sets of CSS custom properties — `:root, [data-theme="light"]` for light theme and `[data-theme="dark"]` for dark theme. Variables should cover: background colors (page bg, card bg, input bg), text colors (primary, secondary, muted), border colors, accent colors (cyan, fuchsia, rose, amber), shadows/glows, selection colors, and scrollbar colors. The dark theme should use the CURRENT color values (the app is already dark-themed), so the dark set is a visual no-op. The light theme needs new values — light backgrounds (#f8fafc, #ffffff), dark text (#0f172a, #334155), adjusted accent colors for light backgrounds, and all must meet WCAG AA contrast ratios (4.5:1 normal text, 3:1 large text).

Modify `src/theme.js`: Change all hardcoded color values to CSS `var(--variable-name)` references. For example, `slateDark: 'var(--color-bg-primary)'`, `cyan400: 'var(--color-accent-cyan)'`. This automatically cascades to all components using `theme.colors.xxx`, `theme.card`, `theme.glows`, `theme.priorityColors`, and `theme.categoryColors`. The `card` object's background, border should also use variables.

Modify `src/App.jsx`: Replace any remaining hardcoded color values (hex codes like `#020617`, `#0f172a`, rgba values) in inline styles that don't go through theme.js with CSS variable references or theme token references. Search for all `#` hex and `rgba(` patterns in inline styles. Also replace hardcoded colors in the HelpDrawer backdrop/panel styles.

Modify `src/index.css`: Replace hardcoded colors in `::selection`, `::-webkit-scrollbar-*` rules with CSS variables.

Modify `index.html`: Add a synchronous inline `<script>` in `<head>` BEFORE any other scripts. The script reads `localStorage.getItem('theme')`, falls back to `window.matchMedia('(prefers-color-scheme: dark)').matches`, defaults to 'light', and sets `document.documentElement.setAttribute('data-theme', theme)`. Must be synchronous to prevent FOUC.

Edge cases: E3 (FOUC on slow connections) — the inline script runs synchronously before paint. The dark theme values match current colors exactly, so existing appearance is preserved. A1/A2 — all components must use variables, no hardcoded colors left.

No new runtime dependencies (R7). Use lucide-react Sun/Moon icons (already a dependency) — import them in this task even though the toggle button comes in wave 2, OR defer the import.
- **wave-2-frontend-theme-toggle-and-persistence:** Modify `src/App.jsx`:

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

## Contracts Affected

(No contracts referenced)

## Cost Summary

(No cost data recorded)

## Retrospective Notes

### 2026-03-24 — Agent blocked: wave-1-frontend-theme-tokens-and-initialization.md

**Signal:** status:blocked
**Root Cause:** [TODO]
**Task File:** queue/darkmode/ready/wave-1-frontend-theme-tokens-and-initialization.md

**What happened:**
Agent failed with exit code 1. [TODO: describe what went wrong]

**What would have prevented it:**
[TODO]

**Upstream fix applied:**
[TODO]

### 2026-03-24 — Agent blocked: wave-1-frontend-theme-tokens-and-initialization.md

**Signal:** status:blocked
**Root Cause:** [TODO]
**Task File:** queue/darkmode/ready/wave-1-frontend-theme-tokens-and-initialization.md

**What happened:**
Agent failed with exit code 1. [TODO: describe what went wrong]

**What would have prevented it:**
[TODO]

**Upstream fix applied:**
[TODO]

### 2026-03-24 — Agent blocked: wave-1-frontend-theme-toggle-and-reactive-theme.md

**Signal:** status:blocked
**Root Cause:** [TODO]
**Task File:** queue/darkmode/ready/wave-1-frontend-theme-toggle-and-reactive-theme.md

**What happened:**
Agent failed with exit code 1. [TODO: describe what went wrong]

**What would have prevented it:**
[TODO]

**Upstream fix applied:**
[TODO]

### 2026-03-24 — Agent blocked: wave-1-frontend-theme-toggle-and-reactive-theme.md

**Signal:** status:blocked
**Root Cause:** [TODO]
**Task File:** queue/darkmode/ready/wave-1-frontend-theme-toggle-and-reactive-theme.md

**What happened:**
Agent failed with exit code 1. [TODO: describe what went wrong]

**What would have prevented it:**
[TODO]

**Upstream fix applied:**
[TODO]

### 2026-03-24 — Agent blocked: wave-1-frontend-theme-toggle-and-reactive-theme.md

**Signal:** status:blocked
**Root Cause:** [TODO]
**Task File:** queue/darkmode/ready/wave-1-frontend-theme-toggle-and-reactive-theme.md

**What happened:**
Agent failed with exit code 1. [TODO: describe what went wrong]

**What would have prevented it:**
[TODO]

**Upstream fix applied:**
[TODO]

