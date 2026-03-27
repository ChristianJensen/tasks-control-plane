# Decomposition Validation: cannot-read-properties-of-undefined-reading-id

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | api | fix-taskwithcount-undefined-crash | critical | 40 |

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

- **Single wave, single task: This is a critical bug scoped entirely to src/app.js in the api repo. The bug report's own scope assessment confirms it is a single-task fix (<50 lines). No contract changes needed — the API contract already defines the correct behavior (200 with task array).**
- **No contract_diff: The bug is a runtime crash in existing code, not a missing or incorrect API contract. The contract correctly specifies GET /tasks returns 200 with an array of Task objects.**
- **Task includes both root cause fix AND defensive hardening: Rather than just adding a .filter(Boolean) band-aid, the task requires the agent to identify and fix the actual source of undefined elements, plus add defense-in-depth guards.**
- **Execution mode is supervised: Inherited from feature-level setting (no feature-level mode set, defaulting to supervised per instructions).**
