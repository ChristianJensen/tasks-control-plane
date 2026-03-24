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

Define CSS custom properties on :root for all theme colors (dark theme values), add [data-theme="light"] overrides with a light color palette, refactor theme.js to export var() references instead of hardcoded hex values, add a flash-prevention inline script to index.html <head>, and update index.css hardcoded colors to use CSS variables.

## Why

This is the foundation for dark/light mode switching. By converting all hardcoded color values to CSS custom properties and defining both dark and light palettes, the entire UI can switch themes by toggling a single data attribute on the root element. The flash-prevention script ensures users see their preferred theme immediately on load (R6). This task addresses R1 (CSS variables), R2 (light palette), R6 (no flash), and R7 (dark default).

## Implementation Notes

**Key insight:** theme.js currently exports hardcoded hex values (e.g., `slate800: '#1e293b'`). Change these to CSS variable references (e.g., `slate800: 'var(--color-slate800)'`). Since App.jsx already uses `theme.colors.X` in inline styles (~120 references), this change is transparent — no App.jsx color reference changes needed for theme.colors usage.

**Files to modify:**

1. **src/index.css** (~60 lines added): Add `:root { }` block with CSS custom properties for all colors in theme.js (`--color-slateDark`, `--color-slate900`, `--color-slate800`, `--color-slate700`, `--color-slate600`, `--color-slate500`, `--color-cyan400`, `--color-cyan500`, `--color-cyan600`, `--color-cyan900`, `--color-fuchsia400`, `--color-fuchsia500`, `--color-rose500`, `--color-amber400`, `--color-amber500`, `--color-cyanLight`). Also add variables for glows (`--glow-cyan`, `--glow-fuchsia`, etc.), card styles (`--card-bg`, `--card-border`), priority colors, and category colors. Add `[data-theme="light"]` selector overriding all variables with light palette values. Update existing hardcoded colors in scrollbar/selection styles to use variables.

2. **src/theme.js** (~30 lines changed): Replace every hex value with its `var(--color-X)` equivalent. Replace rgba values in glows and card with `var(--glow-X)` and `var(--card-X)`. Structure stays identical.

3. **index.html** (~8 lines added): Add inline `<script>` in `<head>` before any other scripts: reads `localStorage.getItem('theme')`, if value is 'light' sets `document.documentElement.setAttribute('data-theme', 'light')`. Wrapped in try/catch for localStorage unavailability (E2). Default is dark (no attribute needed) per R7.

**Light theme palette guidance:** Use light backgrounds (white/#f8fafc/#f1f5f9), dark text (#0f172a/#1e293b), keep accent colors (cyan, fuchsia) but slightly darker for contrast on light backgrounds. Card backgrounds should be white or near-white with subtle borders.

**Edge cases:**
- E2: localStorage unavailable → try/catch in inline script, falls back to dark (no data-theme attribute)
- Existing functionality must not break — since theme.js exports the same structure, all existing code continues to work

## Contract References

No API contract changes. This is a frontend-only change. API contract stays at v0.9.0.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] All color values in theme.js are defined as CSS custom properties on the :root element
- [ ] A `[data-theme="light"]` selector in index.css defines light theme overrides for all CSS variables
- [ ] theme.js exports var() CSS variable references instead of hardcoded hex values
- [ ] An inline script in index.html <head> reads localStorage and sets data-theme attribute before body renders
- [ ] Default theme is dark when no localStorage value exists (no data-theme attribute = dark)
- [ ] Graceful fallback to dark theme when localStorage is unavailable (try/catch)
- [ ] index.css scrollbar and selection styles use CSS variables instead of hardcoded hex values
- [ ] Existing app renders identically (no visual regression) since CSS variable values match original hex values
