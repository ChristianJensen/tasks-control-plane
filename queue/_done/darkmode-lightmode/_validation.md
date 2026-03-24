# Decomposition Validation: darkmode-lightmode

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | frontend | theme-infrastructure-and-toggle | high | 250 |
| 2 | frontend | refactor-colors-to-css-variables | high | 250 |

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

- **Frontend-only feature: No API changes or contract changes needed. Theme preference is stored in localStorage (client-side only, P1), never transmitted to the server.**
- **Two waves instead of one: Wave 1 builds the theme infrastructure (CSS variables, blocking script, toggle component) as a working vertical slice. Wave 2 refactors all hardcoded colors to use CSS variables — this is a large mechanical change that depends on the variable definitions from wave 1. Combining both into one wave would exceed the 400-line per-repo limit.**
- **Accent colors kept as-is: Cyan, fuchsia, rose, and amber accent colors work well on both dark and light backgrounds. Only structural colors (backgrounds, text, borders, overlays) need theme variants, which significantly reduces the refactoring scope.**
- **theme.js updated to reference CSS vars: Rather than creating a parallel system, theme.js values are updated to use var() references. This maintains backward compatibility with all existing components that import theme tokens while making them theme-aware automatically.**
- **Blocking script approach for flash prevention (E1): A synchronous script in <head> reads localStorage and sets data-theme before any rendering occurs. This is the standard technique and avoids React hydration timing issues.**
