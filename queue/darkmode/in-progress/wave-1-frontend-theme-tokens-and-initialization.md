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

Restructure theme.js to support dark and light color palettes, add flash-prevention script to index.html, and update index.css for theme-awareness.

## Why

Foundation for the entire dark/light mode system. The current theme.js exports a single flat dark-only object used in 133 places across App.jsx. This task creates the dual-theme token system and prevents the flash of wrong theme on load (R7), which must be solved at the HTML level before React mounts.

## Implementation Notes

**theme.js (~60 lines changed):**
1. Define `darkTheme` and `lightTheme` objects with the same shape as the current `theme` export. The dark theme preserves all current values exactly (AC1). The light theme provides complementary colors meeting WCAG AA contrast ratios (R10) — e.g., light backgrounds (white/#f8fafc), dark text (#0f172a/#1e293b), adjusted glows and card styles.
2. Export a `getTheme(mode)` function that returns the appropriate theme object.
3. Keep the default `export const theme = darkTheme` for backward compatibility during this wave — wave-1 task 2 will switch to dynamic usage.
4. Export `darkTheme` and `lightTheme` as named exports for tests.

**Light theme color guidance:** Background: #f8fafc (slate-50), card bg: rgba(255,255,255,0.8), text: #0f172a (slate-900), borders: rgba(6,182,212,0.2), keep cyan/fuchsia/amber accent colors but adjust for light background contrast. Glows should be subtler on light backgrounds.

**index.html (~15 lines added):**
Add a blocking inline `<script>` in `<head>` BEFORE the Vite module script:
```js
(function() {
  try {
    var theme = localStorage.getItem('theme');
    if (theme === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
    } else {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  } catch(e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
```
This handles R7 (no flash), R4 (dark default), and R11 (localStorage unavailable fallback).

**index.css (~20 lines changed):**
1. Refactor hardcoded dark colors in scrollbar/selection styles to use CSS custom properties or `[data-theme]` selectors.
2. Add `[data-theme='light']` variants for scrollbar track, thumb, and selection colors.
3. Add base transition rule: `html { transition: background-color 250ms ease, color 250ms ease; }` (R5).

**Edge cases:** E1 (flash prevention via blocking script), E2 (falls back to dark on cleared data), R11 (try/catch handles localStorage unavailability).

## Contract References

None — frontend-only change with no API contract impact (R8).

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Dark theme object is identical to current theme export (AC1)
- [ ] Light theme provides all the same keys as dark theme
- [ ] Light theme text colors meet WCAG AA 4.5:1 contrast ratio against light backgrounds (AC2, R10)
- [ ] getTheme('dark') returns dark theme, getTheme('light') returns light theme
- [ ] index.html contains blocking inline script that reads localStorage and sets data-theme attribute
- [ ] If localStorage has no theme value, data-theme is set to 'dark' (AC6, R4)
- [ ] If localStorage is unavailable (try/catch), data-theme defaults to 'dark' (AC11, R11)
- [ ] index.css scrollbar and selection styles work in both themes
- [ ] CSS transition rule is present for smooth theme switching (AC8, R5)
