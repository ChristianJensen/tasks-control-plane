# Decomposition Validation: helpcontent

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | frontend | help-drawer-component | high | 250 |
| 2 | frontend | help-drawer-tests | high | 200 |

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

- **No contract changes needed: R13 and R14 explicitly state this is a frontend-only feature with no API calls and no backend changes. The contract_diff is null.**
- **Only frontend repo affected: The API repo requires zero changes. All work is in src/App.jsx following the existing single-file architecture.**
- **Two waves instead of one: Wave 1 builds the complete component with all behavior. Wave 2 adds comprehensive tests. This keeps Wave 1 focused on implementation (~250 lines) and Wave 2 on verification (~200 lines), both well under the 400-line per-repo limit.**
- **Single implementation task (not split further): The HelpDrawer is a cohesive component — splitting the content data, the drawer UI, the keyboard handling, and the help button into separate tasks would create artificial boundaries in a single-file app where everything is tightly coupled. 250 estimated lines is within the large task limit.**
- **Tests in a separate wave: Tests depend on the component existing. Separating them into Wave 2 allows Wave 1 to be reviewed/merged first, and keeps each task independently reviewable.**
- **Execution mode is autonomous for both tasks: This is standard UI work with no auth, security, payment, database, or migration concerns. The feature default is autonomous.**
