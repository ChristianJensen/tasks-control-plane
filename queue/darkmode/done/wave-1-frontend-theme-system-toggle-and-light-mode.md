---
status: done
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: darkmode
type: feature
claimed-by: agent-Christians-MacBook-Air-93588
claimed-at: 2026-03-24T17:58:34Z
claimed-on: Christians-MacBook-Air
---

## Description

Add light theme palette to theme.js, theme state with localStorage persistence, sun/moon toggle button in header, and update all components to use dynamic theme so the entire UI switches between dark and light modes instantly.

## Why

This is the core of the dark mode toggle feature. Without the light theme tokens, dynamic theme state, toggle UI, and component-level theming, no other part of the feature can function. All requirements (R1-R4, R8-R12, R14) depend on this foundation.

## Implementation Notes

Modify `src/theme.js` and `src/App.jsx`.

**theme.js (~50 new lines):**
1. Rename the existing `theme` export to `darkTheme` (keep all values identical — R9).
2. Create `lightTheme` with the same shape: light backgrounds (whites/grays), dark text, adjusted glows/borders/card styles for light context. Derive from existing dark palette (R8). No Figma — use sensible light-mode counterparts.
3. Export both `darkTheme` and `lightTheme` named exports. Keep `export default darkTheme` for backward compatibility during migration.
4. Export a `getTheme(mode)` helper: returns `darkTheme` if mode === 'dark', `lightTheme` if mode === 'light', `darkTheme` otherwise (R14 — invalid values default to dark).

**App.jsx — Theme state + localStorage (~40 new lines):**
1. Import `Sun, Moon` from `lucide-react` (already a dependency — R10).
2. Add localStorage helper functions at module level:
   - `getStoredTheme()`: wraps localStorage.getItem in try/catch (R12 — graceful fallback). Returns 'dark' if unavailable, missing, or invalid value (R14). Only accepts 'dark' or 'light'.
   - `storeTheme(mode)`: wraps localStorage.setItem in try/catch (R12).
3. Add state: `const [themeMode, setThemeMode] = useState(getStoredTheme)`.
4. Derive: `const activeTheme = themeMode === 'light' ? lightTheme : darkTheme`.
5. Add toggle handler: `toggleTheme` flips mode, calls storeTheme, updates state.
6. Add `useEffect` to persist on change (or persist inline in toggle handler).

**App.jsx — Toggle button (~15 new lines):**
1. Add a `<button>` element (R11 — semantic button) in the app header, near existing toolbar controls (help button area).
2. Icon: Show `Sun` icon when themeMode === 'dark' (target = light), `Moon` when themeMode === 'light' (target = dark) (R2).
3. Add `aria-label` for accessibility (e.g., 'Switch to light mode' / 'Switch to dark mode').
4. onClick calls `toggleTheme`.
5. Style inline using activeTheme tokens.

**App.jsx — Dynamic theme references (~100 changed lines, not new lines):**
1. Replace module-level `theme` references with `activeTheme` throughout the App component and all inline child components. There are ~120 references to `theme.colors.*`, `theme.glows.*`, `theme.card.*`, etc.
2. For inline components that receive theme via closure (they're all defined inside App or receive it as context), ensure `activeTheme` is in scope.
3. Update `PRIORITY_COLORS` and `CATEGORY_COLORS` constants — these reference `theme.priorityColors` and `theme.categoryColors` at module level. Either move them inside the component or derive them from activeTheme.
4. Update `cardStyle` which also uses `theme.card` at module level — make it derived from activeTheme.
5. Update `index.css` body background to use a CSS variable set by JS, or set `document.body.style.backgroundColor` in a useEffect keyed on themeMode.

**R5 (nice-to-have — flash prevention):**
If straightforward, add a small blocking `<script>` in `index.html` that reads localStorage and sets a `data-theme` attribute on `<html>` before React hydrates. Use this to set body background color via CSS. This prevents flash of wrong theme.

**Edge cases:**
- E1 (flash of wrong theme): Addressed by blocking script if feasible, otherwise acceptable per R5.
- E2 (third-party widgets): Only app-owned components themed (R13). dnd-kit renders no visible chrome.
- E3 (corrupted localStorage): getStoredTheme guards against invalid values (R14).

## Contract References

No contract changes. R7 explicitly states frontend-only, no API modifications.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] A theme toggle button is visible in the app header with sun/moon icon
- [ ] Clicking the toggle switches between dark and light themes instantly (no page reload) — R1, R3
- [ ] Dark mode is the default for first-time visitors — R1
- [ ] Theme preference is persisted in localStorage and restored on subsequent visits — R4
- [ ] Toggle icon shows target theme: sun icon in dark mode, moon icon in light mode — R2
- [ ] All app-owned components (task list, task detail, comments, filters, sorting, empty states, modals, help drawer) render correctly in both themes — R6
- [ ] Toggle is a semantic <button> element (keyboard accessible via Tab/Enter/Space) — R11
- [ ] No new npm dependencies added — R10
- [ ] Existing dark theme colors are unchanged (darkTheme export identical to original theme) — R9
- [ ] If localStorage is unavailable, app defaults to dark theme without errors — R12
- [ ] If localStorage contains an invalid value (not 'dark' or 'light'), app defaults to dark theme — R14
- [ ] Light theme palette has readable contrast for all text and interactive elements — R8
- [ ] No changes to the API contract or backend — R7
- [ ] Third-party widget styling (dnd-kit) is not required to change — R13
