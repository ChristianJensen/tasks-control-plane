# Decomposition Validation: analytics

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | api | analytics-endpoint | high | 200 |
| 2 | frontend | analytics-sidebar | high | 300 |

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

- **Two waves instead of three: the feature is straightforward — one API endpoint and one frontend sidebar. Wave 1 is the API foundation, wave 2 is the frontend feature. No polish wave needed since all states (loading, error, empty) are built into wave 2.**
- **Single API task: the GET /tasks/analytics endpoint is one route handler with three aggregation computations. Splitting into multiple tasks would create artificial boundaries within a single route handler. At ~200 lines (route + tests), it fits comfortably in one task.**
- **Single frontend task: the sidebar is text-only (R7), no charts, no complex interactions. Toggle + fetch + three text sections + tests fits within ~300 lines. Splitting would create tasks that are too small and interdependent.**
- **No cross-repo depends_on: the frontend task is in wave 2 and the API task is in wave 1, so wave sequencing handles the dependency. The frontend codes against the contract, not the API task file.**
- **Contract unchanged: the contract already includes the /tasks/analytics endpoint and TaskAnalytics schema at version 0.10.0, so contract_diff preserves the existing content with no modifications needed.**
