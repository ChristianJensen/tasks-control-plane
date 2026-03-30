# Decomposition Validation: theming

## Task Summary

| Wave | Repo | Task | Priority | Est. Lines |
|------|------|------|----------|------------|
| 1 | frontend | add-high-contrast-theme | high | 180 |
| 2 | frontend | add-tricentis-branded-theme | high | 120 |

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

- **Two waves instead of one: Wave 1 establishes the theme picker infrastructure with High Contrast (more complex due to accessibility requirements), Wave 2 adds Tricentis branding using the established patterns**
- **High Contrast task is larger (180 lines): Includes building the theme picker component, updating theme logic, and ensuring WCAG AAA compliance across all UI elements**
- **No API changes needed: Per R7, this is purely frontend theming using CSS variables and localStorage**
- **No dependencies between waves: Both tasks can work independently as they extend different parts of the existing theme system**
- **Tricentis task focuses on brand colors: Simpler implementation as it reuses the theme picker infrastructure from Wave 1**
