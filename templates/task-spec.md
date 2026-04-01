> **DEPRECATED:** Use `task-queue-item.md` for all new tasks. This template is retained for reference only.

# Task Spec: [Task Name]

**Repo:** [api/frontend]
**Parent Feature:** [link to feature spec]
**Wave:** [N] — [wave description] (task [M] of [total])
**Size:** [small/medium/large]
**Priority:** [critical/high/normal/low]
**Risk Notes:** [what could go wrong]

## What

_Clear description of what needs to be built/changed._

## Why

_How this task connects to the parent feature._

## Contract Dependencies

| Contract | Field/Endpoint | Status |
|----------|---------------|--------|
| tasks-api.json | [specific change] | [added/unchanged] |

## Implementation Notes

_Architectural guidance, constraints, edge cases._

## Dependencies

| Blocked By | Reason | Status |
|------------|--------|--------|
| [repo#N or 'None'] | [why this must complete first] | [open/resolved] |

## Acceptance Criteria

- [ ] Tests pass
- [ ] Contract-compliant
- [ ] [Task-specific criteria]

## Definition of Done

- [ ] Code written with tests
- [ ] PR created referencing control plane task file
- [ ] PR merged, task marked `done`
