# AGENTS.md Template

Use this template in any repo to configure agent behavior for Relay.

```markdown
# AGENTS.md

## Agent Roles

### Implementer Agent
- **Scope:** This repository only
- **Governed by:** CLAUDE.md (Layer 1 constitution)
- **Task discovery:** Scan `queue/*/ready/wave-*.md` in the control plane for tasks matching this repo's name
- **Task lifecycle:** Watcher claims task (`git mv ready/task.md in-progress/task.md`) → agent implements with TDD → creates PR referencing the control plane task file
- **Sub-task discovery:** If you find work not covered by an existing task, create a new queue task file in the control plane

### Architect Agent
- **Scope:** Cross-repo (reads contracts/, creates queue task files)
- **Input:** Feature Spec from `features/draft/` or `features/active/`
- **Output:** Updated contracts + queue task files in `queue/<feature>/pending/` and `queue/<feature>/ready/`

## Constraints

- Never modify files outside this repo
- Always run tests before creating a PR
- Follow the API contract in contracts/
- Commit after each completed task
- PR body must reference the control plane queue task file(s) being implemented
```
