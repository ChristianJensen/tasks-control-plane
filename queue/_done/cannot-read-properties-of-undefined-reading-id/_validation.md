# Decomposition Validation: cannot-read-properties-of-undefined-reading-id

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | api | fix-taskwithcount-undefined-crash | critical | 45 |

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

- **Single wave, single task: the bug report's own scope assessment confirms this is a single-task fix (<50 lines) contained entirely in src/app.js in the api repo. No frontend changes required.**
- **No contract diff: the contract already correctly defines the status filter and GET /tasks response shape. The fix is purely an implementation correctness issue — bringing the code into compliance with the existing contract.**
- **Priority set to critical (not high): the bug causes a complete outage of GET /tasks affecting all users, matching the critical severity threshold in the bug workflow reference.**
- **All four fix layers included in one task: root cause fix, defensive filter(Boolean) guard, taskWithCount hardening, and status filter implementation are all <50 lines combined and logically belong together. Splitting them would create artificial dependencies and unnecessary overhead.**
