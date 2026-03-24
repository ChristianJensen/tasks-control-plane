# Decomposition Validation: darkmode

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | frontend | theme-toggle-and-reactive-theme | high | 180 |
| 2 | frontend | theme-toggle-tests | normal | 150 |

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

- **Frontend-only: R7 explicitly states no API changes, so only the frontend repo is affected. No contract_diff needed.**
- **2 waves: Wave 1 is the implementation (reactive theme + toggle + persistence), Wave 2 is comprehensive tests. This matches the established pattern from helpcontent and spacegap features.**
- **Single wave-1 task instead of splitting CSS refactor and toggle: The theme infrastructure (darkTheme, lightTheme, getTheme, data-theme CSS selectors) already exists in theme.js and index.css. The main work is making App.jsx reactive — splitting this would create artificial boundaries since it's all in one file.**
- **Wave-1 estimated at 180 lines (medium-large): Most changes are moving module-level constants inside the component (~40 lines), adding state/effects (~40 lines), the toggle button (~15 lines), and adjusting theme prop passing (~20 lines). The remaining ~65 lines cover light-mode-specific adjustments to background elements and colorScheme.**
- **Wave-2 tests are autonomous execution: Test-only changes following established patterns with clear acceptance criteria.**
- **No theme.js structural changes needed: The file already exports darkTheme, lightTheme, and getTheme(). The existing default export of darkTheme can remain for backward compatibility, though App.jsx will switch to using getTheme().**
