# Decomposition Validation: darkmode

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | frontend | theme-toggle-and-reactive-theme | high | 120 |
| 2 | frontend | theme-toggle-tests | normal | 200 |

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

- **Frontend-only: R7 explicitly states no backend or API changes. The api repo is not touched. contract_diff is null.**
- **Existing infrastructure leveraged: theme.js already has darkTheme/lightTheme/getTheme(), index.html already has FOUC-prevention script, index.css already has data-theme selectors. This significantly reduces Wave 1 scope — the main work is making App.jsx reactive and adding the toggle button.**
- **2 waves instead of 3: Wave 1 covers all implementation (toggle + reactive theme), Wave 2 covers tests. The implementation is small enough (~120 lines) to be a single task because the heavy infrastructure (dual theme objects, FOUC script, CSS selectors) already exists.**
- **Wave 1 is one task not two: Splitting 'make theme reactive' from 'add toggle button' would create two tiny tasks (~60 lines each) with a tight dependency. A single ~120-line task is cleaner and still well under the 400-line limit.**
- **Tests are autonomous execution: Wave 2 is test-only, following the heuristic that test-only changes use autonomous execution mode.**
- **No CSS custom properties migration needed: The existing approach of swapping theme objects in JS (darkTheme vs lightTheme) works with the inline-style architecture. CSS custom properties would be a larger refactor with no clear benefit for this feature.**
