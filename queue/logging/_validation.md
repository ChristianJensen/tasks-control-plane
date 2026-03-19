# Decomposition Validation: logging

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | api | wave-1-api-status-history-endpoints | high | 200 |
| 1 | frontend | wave-1-frontend-patch-userid-header | high | 40 |
| 2 | frontend | wave-2-frontend-history-display | high | 180 |

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

- **2 waves instead of 3: The feature is compact enough that foundation (wave 1) covers all API work plus the breaking-change frontend fix, and wave 2 covers the UI display. No polish wave is needed — the feature is straightforward with no pagination, search, or complex UX to refine.**
- **API work is a single task (~200 lines): The history store, PATCH validation, recording logic, GET endpoint, and cascade delete are tightly coupled in a single-file Express app (app.js). Splitting them would create artificial dependencies since they all modify the same file and share the same in-memory Map. Tests are included in this estimate.**
- **Frontend wave-1 task is small (~40 lines): Adding X-User-Id to PATCH calls is a mechanical change (2-4 call sites + test updates). It must be wave 1 because the API breaking change deploys simultaneously.**
- **Frontend history display is wave 2 (~180 lines): The UI component depends on the API endpoint existing (wave 1). It includes fetch logic, a display component, styling, empty state handling, and tests — all within the single App.jsx file following existing patterns.**
- **Contract is unchanged from the spec: The provided contract already includes all needed changes (history endpoint, StatusTransition schema, X-User-Id on PATCH, cascade delete description). No diff needed.**
