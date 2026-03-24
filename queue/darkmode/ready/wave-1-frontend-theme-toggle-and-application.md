---
status: ready
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: darkmode
type: feature
depends-on:
  - wave-1-frontend-theme-tokens-and-initialization.md
---

## Description

Add theme state management, sun/moon toggle button in header, localStorage persistence, and apply theme-aware styling to all components in App.jsx.

## Why

This is the core user-facing feature — the toggle button and the visual theme switch across the entire UI. It wires together the theme tokens from task 1 with React state, localStorage, and the 133 theme references in App.jsx.

## Implementation Notes

**App.jsx changes (~250 lines):**

1. **Import icons** (~1 line): Add `Sun, Moon` to the lucide-react import.

2. **Import theme functions** (~2 lines): Change `import { theme }` to `import { getTheme, darkTheme, lightTheme }` from theme.js.

3. **Theme state and hook** (~25 lines): Create a `useTheme` custom hook (inline in App.jsx) that:
   - Reads initial theme from `document.documentElement.getAttribute('data-theme')` (syncs with the blocking script from task 1)
   - Returns `[theme, themeMode, toggleTheme]` where `theme` is the full theme object, `themeMode` is 'dark'|'light', and `toggleTheme` is the toggle function
   - `toggleTheme`: flips mode, updates `document.documentElement.setAttribute('data-theme', newMode)`, saves to localStorage (wrapped in try/catch for R11), and updates state
   - Uses `useState` and a stable `useCallback` for the toggle

4. **Toggle button in header** (~15 lines): In the header/navbar area (find existing header JSX with the HelpCircle button), add a theme toggle button:
   - Show `Sun` icon when dark mode active, `Moon` icon when light mode active (R2)
   - `onClick={toggleTheme}`
   - `aria-label={themeMode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}` (R9, AC10)
   - Style consistently with existing header buttons
   - Icon swaps instantly (no animation per spec), background transitions smoothly

5. **Replace static theme references** (~200 lines): The current code uses `theme.colors.X`, `theme.glows.X`, `theme.card.X` etc. in 133 places. Replace the static `theme` import usage with the dynamic `theme` object from `useTheme()`. The key approach:
   - At the top of the App component, call `const [theme, themeMode, toggleTheme] = useTheme()`
   - Pass `theme` down to inline components that need it (or they can access it via closure since they're defined inside App)
   - Since all components are defined inline in App.jsx, they already have closure access to variables in App's scope
   - The theme object has the same shape, so `theme.colors.slate900` etc. just works — it returns different values based on mode

6. **CSS transition classes** (~5 lines): Add inline transition styles to major containers: `transition: 'background-color 250ms ease, color 250ms ease, border-color 250ms ease'` on the main app wrapper, cards, and header (R5, AC8).

**Edge cases:** E3 (third-party content stays as-is — only app-owned elements themed). Transparent PNGs handled case-by-case if encountered.

**Key risk:** The 133 theme references should mostly just work since the theme object shape is preserved. The main effort is ensuring the dynamic theme object flows to all component closures correctly and that hardcoded color values (if any exist outside theme references) are also updated.

## Contract References

None — frontend-only change with no API contract impact (R8).

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Dark mode renders identically to current app appearance (AC1)
- [ ] Light mode provides readable, visually coherent theme across all UI elements (AC2, AC9)
- [ ] Sun icon visible in header when dark mode active; clicking switches to light mode (AC3)
- [ ] Moon icon visible in header when light mode active; clicking switches to dark mode (AC4)
- [ ] Theme preference saved to localStorage on toggle (AC5)
- [ ] Theme preference survives browser refresh (AC5)
- [ ] First-time visitors see dark mode (AC6)
- [ ] No flash of wrong theme on page load — blocking script sets data-theme before React mounts (AC7)
- [ ] Color transitions are smooth (~200-300ms), icon swaps instantly (AC8)
- [ ] Toggle button has dynamic aria-label that updates with theme state (AC10, R9)
- [ ] If localStorage is unavailable, app defaults to dark mode with no console errors (AC11)
