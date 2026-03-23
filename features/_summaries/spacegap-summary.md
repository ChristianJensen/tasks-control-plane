---
feature: spacegap
completed: 2026-03-23
tasks: 2
waves: 2
---

## Overview

End users see a large, disproportionate gap between the active tasks list (todo / in-progress) and the completed tasks list (done) on the task list page. This wasted vertical space makes the interface feel disjointed and reduces scannability, forcing users to scroll more than necessary.

## What Was Built

### Wave 1

- **frontend** — Fix the spacing gap between active and completed task sections, restyle the completed section header with a 'Completed (N)' label, add a chevron collapse/expand toggle, and handle all edge cases (0 active, 0 completed, both empty).

### Wave 2

- **frontend** — Add comprehensive tests for the collapsible completed section covering spacing, collapse/expand behavior, count display, and all edge cases.

## Key Decisions

- **wave-1-frontend-collapsible-completed-section:** Modify `src/App.jsx`.

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
- **wave-2-frontend-completed-section-tests:** Modify `tests/App.test.jsx` (append to existing file, following existing patterns with `vi.stubGlobal` for fetch mocking and `@testing-library/react`).

Test cases to add (~120 lines):

1. **Completed section header with count** (~15 lines): Create tasks with mixed statuses. Verify 'Completed (N)' text appears with correct count. Use mock fetch returning tasks with status 'done'.

2. **Collapse toggle** (~20 lines): Verify chevron icon is present. Click it — completed tasks disappear, header with count remains visible. Click again — completed tasks reappear.

3. **Default expanded state** (~10 lines): On render, completed tasks are visible (not collapsed).

4. **Zero active tasks** (~15 lines): Mock fetch with only 'done' tasks. Verify completed section renders at top without extra gap (check no empty active section adds spacing).

5. **Zero completed tasks** (~15 lines): Mock fetch with only 'todo'/'in-progress' tasks. Verify no 'Completed' header or divider renders. Verify no orphaned spacing elements.

6. **Both sections empty** (~10 lines): Mock fetch returning empty array. Verify no section headers or spacing elements appear.

7. **Count updates** (~15 lines): If possible with existing test patterns, verify count in header matches actual number of completed tasks after a status change.

8. **Collapsed state hides tasks but shows header** (~15 lines): Collapse the section. Verify individual completed task titles are not visible. Verify 'Completed (N)' is still visible.

Follow existing test patterns:
- Use `render(<App />)` with fetch mocked to return task data
- Use `screen.getByText`, `screen.queryByText`, `screen.getByRole`
- Use `fireEvent.click` for toggle interactions
- Use `waitFor` for async assertions

## Contracts Affected

(No contracts referenced)

## Retrospective Notes

(No retrospective entries)
