---
status: in-progress
execution: supervised
target-repo: frontend
wave: 2
priority: high
feature: task-descriptions
type: feature
depends-on:
  - wave-1-api-add-description-field.md
claimed-by: agent-Christians-MacBook-Air-3595
claimed-at: 2026-03-25T20:41:58Z
claimed-on: Christians-MacBook-Air
---

## Description

Add expandable inline detail panel with accordion behavior to display task descriptions

## Why

Users need to click a task row to see its description in an expandable panel. This implements the core detail panel UI with accordion behavior (only one open at a time) and full accessibility.

## Implementation Notes

Modify `src/App.jsx`:

1. **State**: Add `const [expandedDetailId, setExpandedDetailId] = useState(null)` near existing state (~line 908). This tracks which task's detail panel is open (null = none).

2. **Toggle handler** (~10 lines): Add `toggleDetailPanel(taskId)` function. If `expandedDetailId === taskId`, collapse (set null). Otherwise, expand the new one (accordion — auto-collapses previous).

3. **TaskItem changes** (~40 lines per TaskItem variant — there are two: active and completed): In both `TaskItem` (active, ~line 436) and `CompletedTaskItem` (~line 688), add:
   - Pass `expandedDetailId` and `toggleDetailPanel` via state/handlers props
   - Make the task row clickable: add `onClick` to the main task row `<div>` that calls `toggleDetailPanel(task.id)`. Ensure click doesn't conflict with existing checkbox/button clicks (use `e.stopPropagation()` on inner interactive elements or check `e.target`).
   - Add `role="button"`, `tabIndex={0}`, `onKeyDown` handler for Enter/Space to toggle
   - Add `aria-expanded={expandedDetailId === task.id}`, `aria-controls={`detail-panel-${task.id}`}`

4. **Detail panel component** (~50 lines): Below the task row (inside the `<li>`), conditionally render when `expandedDetailId === task.id`:
   - `<div id={`detail-panel-${task.id}`} role="region" aria-label="Task details">`
   - If `task.description`: render description text in a `<p>` with appropriate styling
   - If no description: render placeholder text like "No description provided" in muted/italic style
   - Style: indented, subtle background, border-top separator, padding 12px 16px

5. **Ensure existing interactive elements don't trigger panel toggle**: Add `e.stopPropagation()` to existing onClick handlers within TaskItem (checkbox, delete button, priority dropdown, category pill, notes button, subtasks button, drag handle).

Modify `tests/App.test.jsx` (~60 lines):
- Clicking a task row expands the detail panel showing the description
- Clicking the same task row collapses the detail panel
- Only one detail panel is expanded at a time (accordion)
- Detail panel shows placeholder when no description exists
- Task row is focusable and toggleable via Enter/Space keys
- Detail panel uses aria-expanded and aria-controls attributes
- Frontend task list does not show descriptions inline (only in panel)

## Contract References

Task schema: `description` (string, optional). GET /tasks returns description for each task.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Clicking a task row expands an inline detail panel showing the description
- [ ] Clicking the same task row collapses the detail panel
- [ ] Only one detail panel is expanded at a time (accordion behavior)
- [ ] Detail panel shows a placeholder/empty state when no description exists
- [ ] Collapsing the detail panel returns to the compact list view
- [ ] Frontend task list does not show descriptions inline
- [ ] Task row is focusable and toggleable via Enter/Space keys
- [ ] Detail panel uses aria-expanded and aria-controls attributes
- [ ] Existing task interactions (checkbox, delete, priority, notes, etc.) still work without triggering panel toggle
