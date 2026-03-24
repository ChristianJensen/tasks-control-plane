# Decomposition Validation: darkmode

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | frontend | theme-system-toggle-and-light-mode | high | 250 |
| 2 | frontend | dark-mode-tests | high | 150 |

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

- **Only the frontend repo needs changes — R7 explicitly states no API contract modifications, so no api tasks or contract_diff.**
- **Two waves instead of three: Wave 1 combines theme tokens + toggle + component theming because they are tightly coupled (you cannot test a toggle without themed components, and the theme tokens are meaningless without the toggle). Wave 2 is tests. This matches the pattern of past frontend-only features (helpcontent, spacegap).**
- **Wave 1 task is sized at ~250 lines (large): ~50 lines new in theme.js, ~55 lines new in App.jsx (state, helpers, toggle button, useEffect), and ~100 lines of changes converting static theme references to dynamic activeTheme. The changed lines are mostly mechanical find-and-replace (theme → activeTheme) but are necessary to make the feature work. Cannot be split further because the toggle, theme state, and component theming are a single atomic unit — none work without the others.**
- **Wave 2 tests are autonomous execution: test-only changes with no production code impact, following the established pattern from past features.**
- **The approach uses dual theme objects (darkTheme/lightTheme) rather than CSS custom properties because the codebase uses inline style objects exclusively — introducing CSS variables would be a larger architectural change that conflicts with R10 (no new patterns/dependencies) and existing conventions.**
- **localStorage helpers use try/catch wrapping to handle R12 (unavailable localStorage) and R14 (invalid values) — both default to dark mode silently.**
