---
status: blocked
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: darkmode
type: feature
claimed-by: agent-Christians-MacBook-Air-75067
claimed-at: 2026-03-25T00:52:00Z
claimed-on: Christians-MacBook-Air
pr-url: ""
pr-number: ""
cost-usd: 0
input-tokens: 23
output-tokens: 9845
duration-ms: 164074
---

## Description

Define light and dark CSS custom property sets, refactor theme.js and all hardcoded colors to use CSS variables, and add FOUC prevention inline script in index.html.

## Why

This is the foundation for dark mode. All existing colors must be expressed as CSS custom properties toggled via a `data-theme` attribute so that switching themes is a single attribute change. Without this refactoring, no theme toggle can work. The FOUC prevention script must be in the HTML template (not React) to apply the theme before first paint.

## Implementation Notes

Modify `src/index.css`: Define two sets of CSS custom properties — `:root, [data-theme="light"]` for light theme and `[data-theme="dark"]` for dark theme. Variables should cover: background colors (page bg, card bg, input bg), text colors (primary, secondary, muted), border colors, accent colors (cyan, fuchsia, rose, amber), shadows/glows, selection colors, and scrollbar colors. The dark theme should use the CURRENT color values (the app is already dark-themed), so the dark set is a visual no-op. The light theme needs new values — light backgrounds (#f8fafc, #ffffff), dark text (#0f172a, #334155), adjusted accent colors for light backgrounds, and all must meet WCAG AA contrast ratios (4.5:1 normal text, 3:1 large text).

Modify `src/theme.js`: Change all hardcoded color values to CSS `var(--variable-name)` references. For example, `slateDark: 'var(--color-bg-primary)'`, `cyan400: 'var(--color-accent-cyan)'`. This automatically cascades to all components using `theme.colors.xxx`, `theme.card`, `theme.glows`, `theme.priorityColors`, and `theme.categoryColors`. The `card` object's background, border should also use variables.

Modify `src/App.jsx`: Replace any remaining hardcoded color values (hex codes like `#020617`, `#0f172a`, rgba values) in inline styles that don't go through theme.js with CSS variable references or theme token references. Search for all `#` hex and `rgba(` patterns in inline styles. Also replace hardcoded colors in the HelpDrawer backdrop/panel styles.

Modify `src/index.css`: Replace hardcoded colors in `::selection`, `::-webkit-scrollbar-*` rules with CSS variables.

Modify `index.html`: Add a synchronous inline `<script>` in `<head>` BEFORE any other scripts. The script reads `localStorage.getItem('theme')`, falls back to `window.matchMedia('(prefers-color-scheme: dark)').matches`, defaults to 'light', and sets `document.documentElement.setAttribute('data-theme', theme)`. Must be synchronous to prevent FOUC.

Edge cases: E3 (FOUC on slow connections) — the inline script runs synchronously before paint. The dark theme values match current colors exactly, so existing appearance is preserved. A1/A2 — all components must use variables, no hardcoded colors left.

No new runtime dependencies (R7). Use lucide-react Sun/Moon icons (already a dependency) — import them in this task even though the toggle button comes in wave 2, OR defer the import.

## Contract References

None — frontend-only feature, no API changes (R8).

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Light and dark CSS variable sets are defined in index.css via `data-theme` attribute
- [ ] theme.js exports CSS var() references instead of hardcoded colors
- [ ] No hardcoded hex colors (#xxx) or rgba() values remain in App.jsx inline styles (all use theme tokens or CSS variables)
- [ ] No hardcoded colors remain in index.css rules (all use CSS variables)
- [ ] FOUC prevention inline script exists in index.html <head> before other scripts
- [ ] FOUC script reads localStorage('theme'), falls back to prefers-color-scheme, defaults to 'light'
- [ ] Dark theme uses current color values (visual no-op for existing dark appearance)
- [ ] Light theme meets WCAG AA contrast ratios (4.5:1 normal text, 3:1 large text)
- [ ] All existing functionality continues to work (no visual regressions in dark theme)
- [ ] No new runtime dependencies added
- [ ] Tests verify CSS variable definitions exist for both themes
- [ ] Tests verify FOUC prevention script logic (localStorage priority, OS fallback, default)
