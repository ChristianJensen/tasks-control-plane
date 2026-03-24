# Decomposition Validation: darkmode

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | frontend | theme-tokens-and-initialization | high | 120 |
| 1 | frontend | theme-toggle-and-application | high | 250 |
| 2 | frontend | theme-tests | normal | 200 |

## Validation Checklist

- [ ] Each task can be implemented independently within its repo
- [ ] Cross-repo tasks coordinate only via contracts
- [ ] No task estimated >400 lines without split justification
- [ ] All tasks have appropriate priority set
- [ ] Each edge case from the Feature Spec maps to at least one task's acceptance criteria
- [ ] Contract changes are sufficient for all tasks
- [ ] No circular dependencies
- [ ] Tasks are grouped into waves, each wave <400 lines per repo

## Decisions

- **Only frontend repo affected — R8 explicitly states no API contract changes needed. contract_diff is null.**
- **Two waves instead of three: Wave 1 covers all implementation (tokens + toggle), Wave 2 covers tests. The feature is small enough that a third 'polish' wave is unnecessary. This matches the pattern from past features (helpcontent, spacegap, sorting-improvements all used 2 waves).**
- **Wave 1 split into two tasks with a dependency: theme-tokens-and-initialization must land first because theme-toggle-and-application imports from the restructured theme.js and relies on the data-theme attribute set by the blocking script. Without this ordering, the toggle task would need to do both infrastructure and UI work in one large task.**
- **theme-toggle-and-application is large (250 lines) because all 133 theme references in the single-file App.jsx must be updated to use dynamic theme objects. This cannot be split further since all components are in one file and share the same theme closure — partial migration would leave the app in an inconsistent state.**
- **Tests task set to 'autonomous' execution per heuristic (test-only changes). Wave 1 tasks inherit feature default 'supervised' since they modify production UI code.**
- **The blocking inline script approach in index.html (not a React solution) is critical for R7/AC7 — it runs before any JS bundle loads, preventing flash of wrong theme. This is a Vite-compatible pattern that works with the existing build setup.**
- **Light theme derived from existing dark palette per R6 — implementation agent discovers exact values, but guidance provided for WCAG AA compliance (R10). Key: keep accent colors (cyan, fuchsia, amber) and adjust backgrounds/text for contrast.**
