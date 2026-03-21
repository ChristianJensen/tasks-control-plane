---
status: in-progress
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: multiassign
type: feature
claimed-by: agent-06-36-06-7A-C3-F6-54628
claimed-at: 2026-03-21T16:20:38Z
claimed-on: 06-36-06-7A-C3-F6
---

## Description

Display the assigned category on each task card/row as a visual badge. Add category color tokens to the theme. Show category in both the task list view and task detail view.

## Why

Users need to see which category is assigned to each task. R7 (display category), AC11 (visual display). Foundation for the bulk assign UI which needs users to see the result of their actions.

## Implementation Notes

Modify `src/App.jsx` and `src/theme.js`. (1) In `theme.js`, add category color map (similar to priority colors) — e.g., `categoryColors: { work: '#...', personal: '#...', errands: '#...' }` with labels. (2) In `App.jsx`, create a `CategoryBadge` inline component (~15 lines) that renders a small colored pill/badge with the category label. Returns null if category is null. Follow the PriorityBadge pattern. (3) Add CategoryBadge to the TaskItem component in the task list, near existing badges. (4) Add CategoryBadge to the task detail view. (5) Add tests in `tests/App.test.jsx`: task with category shows badge, task without category shows no badge, all three category values render correctly. Add theme tests in `tests/theme.test.js` for new tokens.

## Contract References

components/schemas/Task (category field — nullable enum), components/schemas/TaskCategory (work, personal, errands).

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Contract-compliant: reads category from task response
- [ ] Task card/row displays category badge when category is set (AC11)
- [ ] No badge shown when category is null
- [ ] All three categories (work, personal, errands) have distinct visual treatment
- [ ] Category badge visible in both list view and detail view
