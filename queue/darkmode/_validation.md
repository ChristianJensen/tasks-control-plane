# Decomposition Validation: darkmode

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | frontend | css-variables-and-theme-infrastructure | high | 350 |
| 2 | frontend | theme-toggle-and-persistence | high | 250 |

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

- **Only frontend repo affected — the feature spec explicitly states no backend or API changes required (R8), so no contract diff is needed.**
- **Two waves instead of one: Wave 1 is the CSS variable foundation (refactoring all colors to CSS custom properties + FOUC script), which must be complete before Wave 2 (toggle button + persistence + OS preference) can work. The toggle has no effect without the CSS variable infrastructure.**
- **Wave 1 task is large (~350 lines) because it touches theme.js, index.css, index.html, AND App.jsx (replacing ~192 hardcoded color references). This cannot be split further because partial CSS variable migration would leave the app in a broken visual state — all colors must be variables for the theme toggle to work correctly.**
- **Wave 2 task is medium (~250 lines) covering the toggle component, localStorage persistence, OS preference detection, graceful degradation, and comprehensive tests. These are tightly coupled behaviors that belong together.**
- **The current app is already dark-themed (dark slate backgrounds, cyan/fuchsia accents), so the dark CSS variable set maps to current values (visual no-op). The light theme introduces new values. This de-risks wave 1 — if dark variables match exactly, existing tests should pass without changes.**
- **Tests are included in each task (per memory rule: never split tests into a separate wave). Wave 1 tests cover CSS variable definitions and FOUC script logic. Wave 2 tests cover toggle behavior, persistence, OS preference, and graceful degradation.**
