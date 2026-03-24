# Decomposition Validation: darkmode

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | frontend | css-variables-and-light-theme | high | 200 |
| 2 | frontend | theme-toggle-and-inline-color-migration | high | 250 |

## Validation Checklist

- [ ] Each task can be implemented independently within its repo
- [ ] Cross-repo tasks coordinate only via contracts
- [ ] No task estimated >400 lines without split justification
- [ ] All tasks have appropriate priority set
- [ ] Each edge case from the Feature Spec maps to at least one task's acceptance criteria
- [ ] Contract changes are sufficient for all tasks
- [ ] No circular dependencies
- [ ] Tasks are grouped into waves, each wave <400 lines per repo
- [ ] All tasks use the feature's execution mode (no per-task overrides)
- [ ] Every task is a vertical slice (implementation + tests together, no test-only tasks)

## Decisions

- **No API changes needed — the feature spec confirms this is frontend-only (AR2). API contract stays at v0.9.0. No contract_diff.**
- **2 waves instead of 1: Wave 1 establishes the CSS variable infrastructure (foundation) without changing any visual behavior. Wave 2 adds the user-facing toggle and migrates remaining hardcoded colors. This separation ensures wave 1 can be validated as a no-visual-change refactoring before the toggle is added.**
- **theme.js refactoring strategy: Instead of updating ~120 theme.colors.X references in App.jsx, we change theme.js to export var() CSS variable references. Since App.jsx uses theme.colors.X in inline styles, the browser resolves var(--color-X) automatically. This makes the migration transparent — zero App.jsx changes needed for theme.colors usage.**
- **Inline rgba() migration deferred to wave 2: There are ~25 inline rgba() dark-background values in App.jsx (rgba(2,6,23,...), rgba(15,23,42,...), rgba(30,41,59,...)) that don't go through theme.js. These are migrated to semantic CSS variables in wave 2 alongside the toggle, since they only matter once theme switching is possible.**
- **Accent rgba values (cyan, fuchsia, rose with alpha) are NOT migrated — they work as highlights/glows on both dark and light backgrounds, keeping the scope manageable.**
- **Tests are included in every task (per memory feedback). Wave 1 tests validate theme structure and variable definitions. Wave 2 tests validate toggle behavior, localStorage persistence, icon state, and graceful fallback.**
