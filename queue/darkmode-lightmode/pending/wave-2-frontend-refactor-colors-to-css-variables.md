---
status: pending
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: darkmode-lightmode
type: feature
depends-on:
  - wave-1-frontend-theme-infrastructure-and-toggle.md
---

## Description

Refactor all hardcoded color values in App.jsx and theme.js to use CSS custom properties, ensuring both dark and light themes render correctly across all UI elements.

## Why

Wave 1 created the theme infrastructure and toggle, but existing components still use hardcoded dark-mode colors via theme.js tokens and inline rgba() values. Without refactoring these to CSS custom properties (R14), switching to light mode would show dark-themed components on a light background — unreadable text, invisible borders, and broken visual hierarchy. This task completes the theming by making every UI element theme-aware (R6).

## Implementation Notes

**Modify: `src/theme.js`** (~25 lines)
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

## Contract References

None — this feature is entirely client-side. No API endpoints affected.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] All existing tests continue to pass (no regressions)
- [ ] All UI elements render correctly in both dark and light mode — no unreadable text, missing borders, or broken layouts (R6)
- [ ] Hardcoded color values in App.jsx are replaced with CSS custom properties (R14)
- [ ] theme.js tokens reference CSS custom properties where appropriate
- [ ] Task items, cards, inputs, modals, dialogs, and drawers are theme-aware
- [ ] Priority and category badges remain visually distinct in both themes
- [ ] No new runtime dependencies added (R8)
- [ ] On subsequent visits, the app loads with the previously selected theme (R4, R5 — verify end-to-end)
