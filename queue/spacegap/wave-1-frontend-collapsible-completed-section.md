---
status: done
execution: autonomous
target-repo: frontend
wave: 1
priority: high
feature: spacegap
type: feature
claimed-by: agent-Mac-89053
claimed-at: 2026-03-22T05:55:41Z
claimed-on: Mac
---

## Description

Fix the spacing gap between active and completed task sections, restyle the completed section header with a 'Completed (N)' label, add a chevron collapse/expand toggle, and handle all edge cases (0 active, 0 completed, both empty).

## Why

The large vertical gap between active and completed tasks makes the interface feel disjointed. Adding consistent spacing, a clear section divider with count, and a collapse toggle addresses all six requirements (R1-R6) in a single cohesive change.

## Implementation Notes

Modify `src/App.jsx`.

1. **Import icons**: Add `ChevronDown` and `ChevronRight` from `lucide-react` (already a dependency).

2. **State**: Add `const [completedExpanded, setCompletedExpanded] = useState(true)` near existing state declarations. No persistence needed — defaults to expanded on each page visit (R6).

3. **Fix spacing (R1, R2)**: In the completed section header (currently around line 1735), change `marginTop: 24` to match the gap between individual task items. Inspect the task item spacing (likely 8px or similar from the list item margins) and use the same value. Remove `minHeight: 300` from the incomplete tasks container if it contributes to the gap, or adjust it appropriately.

4. **Restyle section header (R3, R5)**: Replace the current `// Completed` text with `Completed (N)` where N is `completedTasks.length`. Add a subtle top border or horizontal rule as the visual divider (replacing or augmenting the current cyan bottom border). Use existing theme tokens for colors.

5. **Add collapse toggle (R4)**: Wrap the header in a clickable element. Show `ChevronDown` when expanded, `ChevronRight` when collapsed. `onClick` toggles `completedExpanded`. Style the chevron inline next to the 'Completed (N)' text. Add `cursor: pointer` and appropriate hover state.

6. **Conditional render of task items**: Wrap the completed tasks `<ul>` in a conditional: only render when `completedExpanded` is true. The header with count always renders (when completedTasks.length > 0).

7. **Edge cases**:
   - E1 (0 active tasks): Completed section renders at top — ensure no extra marginTop when incompleteTasks.length === 0.
   - E2 (0 completed tasks): Don't render the divider/header at all (already conditional on completedTasks.length > 0, verify no orphaned spacing).
   - E3 (both empty): Verify no orphaned section elements or spacing appear.

Estimated ~80 lines of changes across the file.

## Contract References

No contract changes. This is a frontend-only CSS/layout and client-side state change.

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] The vertical gap between active and completed sections matches the gap between individual task items
- [ ] No layout regressions — tasks render correctly with no overlap
- [ ] Fix works with 0, 1, and many active or completed tasks
- [ ] A visual divider with 'Completed (N)' header appears between active and done sections
- [ ] Clicking the chevron collapses the completed section, hiding task items but showing header with count
- [ ] Clicking the chevron again expands the section to reveal completed tasks
- [ ] Section defaults to expanded on page load (no persistence)
- [ ] When 0 active tasks exist, the completed section renders at top with no extra gap
- [ ] When 0 completed tasks exist, no trailing gap or orphaned divider appears
- [ ] When both sections are empty, no orphaned spacing or section elements appear
