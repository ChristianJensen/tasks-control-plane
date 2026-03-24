---
feature: darkmode
completed: 2026-03-24
tasks: 2
waves: 2
---

## Overview

End users of the tasks app want the ability to switch between dark and light themes for visual comfort, especially in varying lighting conditions. The current app theme is already dark-ish, but there is no light mode alternative. Dark mode toggling has become a baseline UX expectation for modern productivity tools — its absence feels like a gap.

## What Was Built

### Wave 1

- **frontend** — Add light theme palette to theme.js, theme state with localStorage persistence, sun/moon toggle button in header, and update all components to use dynamic theme so the entire UI switches between dark and light modes instantly.

### Wave 2

- **frontend** — Add comprehensive tests for the dark mode toggle covering all acceptance criteria: toggle rendering, theme switching, localStorage persistence, fallback behavior, icon states, and component rendering in both themes.

## Key Decisions

- **wave-1-frontend-theme-system-toggle-and-light-mode:** Modify `src/theme.js` and `src/App.jsx`.

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
- **wave-2-frontend-dark-mode-tests:** Modify `tests/App.test.jsx` (append to existing test file) and `tests/theme.test.js`. Follow existing test patterns with `vi.stubGlobal` for fetch mocking and `@testing-library/react`.

**tests/theme.test.js (~30 new lines):**
1. Test that `darkTheme` and `lightTheme` have identical shape (same keys at every level).
2. Test that `darkTheme` values match the original theme values exactly (R9 — no dark theme regression).
3. Test that `getTheme('dark')` returns darkTheme, `getTheme('light')` returns lightTheme.
4. Test that `getTheme('invalid')`, `getTheme('')`, `getTheme(null)` all return darkTheme (R14).

**tests/App.test.jsx (~120 new lines):**

1. **Toggle button rendering** (~10 lines): Verify toggle button is present in rendered app with appropriate aria-label. Verify it is a `<button>` element (R11).

2. **Theme toggle switches mode** (~15 lines): Click toggle → verify visual indicators change (e.g., body background changes, icon changes from Sun to Moon or vice versa). Click again → verify it switches back.

3. **Default is dark mode** (~10 lines): On first render (no localStorage), verify dark theme is active.

4. **Icon shows target theme** (~15 lines): In dark mode, verify Sun icon is shown (target = light). In light mode, verify Moon icon is shown (target = dark). R2.

5. **localStorage persistence** (~15 lines): Click toggle to light mode. Verify `localStorage.setItem` was called with 'light'. Re-render app. Verify light mode is restored from localStorage.

6. **localStorage unavailable** (~15 lines): Mock localStorage to throw on access. Render app. Verify dark mode is default and no errors thrown. R12.

7. **Invalid localStorage value** (~10 lines): Set localStorage theme value to 'invalid'. Render app. Verify dark mode is used. R14.

8. **Components render in light mode** (~15 lines): Toggle to light mode. Verify key components are visible and functional — task list renders, can interact with tasks. Verify no crashes.

9. **No API calls on toggle** (~10 lines): Toggle theme back and forth. Verify no additional fetch calls were made (theme is client-side only). R7.

10. **Aria attributes** (~10 lines): Verify toggle button has descriptive aria-label that changes with theme state.

Follow existing test patterns:
- Use `render(<App />)` with fetch mocked to return task data
- Use `screen.getByRole`, `screen.getByText`, `screen.queryByText`
- Use `fireEvent.click`
- Use `waitFor` for async assertions
- Mock localStorage via `vi.spyOn(Storage.prototype, 'getItem')` etc.

## Contracts Affected

(No contracts referenced)

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

