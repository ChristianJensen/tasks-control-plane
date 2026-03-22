---
lifecycle: draft
execution: autonomous
priority: medium
epic: TASK-5
version: 1
paused-at: ""
paused-by: ""
pause-reason: ""
created-at: "2026-03-22"
completed-at: ""
deployed-at: ""
deployed-env: ""
---
# Feature Spec: Improve Spacing Between Active and Completed Task Sections

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| S1 | conversation | (interview) | christianjensen | 2026-03-22 |

## Problem Statement

End users see a large, disproportionate gap between the active tasks list (todo / in-progress) and the completed tasks list (done) on the task list page. This wasted vertical space makes the interface feel disjointed and reduces scannability, forcing users to scroll more than necessary.

## User Journey

1. User opens the task list page.
2. User sees active tasks (todo / in-progress) listed at the top of the page.
3. A visual divider with a "Completed (N)" header separates the active and completed sections, with consistent spacing matching the gap between individual task items.
4. User sees completed (done) tasks below the divider.
5. User clicks the collapse toggle (chevron icon) on the "Completed" header to hide completed tasks.
6. The completed section collapses, showing only the header with the count (e.g., "Completed (5)") and a right-pointing chevron.
7. User clicks the toggle again to expand and reveal completed tasks.

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | Reduce the vertical gap between the active tasks section and the completed tasks section | S1 | High | Frontend-only CSS/layout change |
| R2 | The new spacing between sections must match the spacing between individual task items | S1 | High | Ensures consistent visual rhythm |
| R3 | Add a visual divider/separator between the active and completed sections | S1 | High | Includes a "Completed" label |
| R4 | Add a collapsible toggle to the completed tasks section | S1 | High | Chevron icon, expands/collapses done tasks |
| R5 | Show completed task count in the section header (e.g., "Completed (5)") | S1 | High | Visible in both expanded and collapsed states |
| R6 | Default state is expanded on each page visit | S1 | High | No persistence of collapsed state |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| (none) | — | — |

## Open Questions

(none)

## Acceptance Criteria

- [ ] The vertical gap between the active tasks section and the completed tasks section is visually consistent with the gap between individual task items
- [ ] No layout regressions in the task list page (items still render correctly, no overlap)
- [ ] The fix applies regardless of how many active or completed tasks exist (0, 1, many)
- [ ] A visual divider with "Completed (N)" header appears between active and done sections
- [ ] Clicking the chevron collapses the completed section, hiding task items but showing the header with count
- [ ] Clicking the chevron again expands the section to reveal completed tasks
- [ ] The section defaults to expanded on page load
- [ ] When there are 0 active tasks, the completed section renders at the top with no extra gap
- [ ] When there are 0 completed tasks, no trailing gap or orphaned divider appears
- [ ] When both sections are empty, no orphaned spacing or section elements appear

## Out of Scope

- API changes
- Changing spacing between individual task items
- Responsive/mobile-specific layout changes (unless the fix naturally applies)
- Normalizing spacing across the entire task list (full audit)
- Persisting collapsed/expanded state across page visits

## Refinement Log

### Round 1: Assumptions

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | The large gap is caused by explicit CSS margin/padding | Yes | Unknown root cause; implementer must inspect DOM to identify source of gap before applying fix |
| A2 | Spacing between individual task items is already consistent and well-defined | Yes | Implementer should verify existing task item spacing is consistent and use it as reference value |
| A3 | The gap only appears in the main task list view | Yes | Confirmed — scoped to main task list view only |

### Round 2: Edge Cases

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | Zero active tasks (all tasks done) | R1, R2 | Completed section renders at top with no extra gap |
| E2 | Zero completed tasks | R3 | No trailing gap or orphaned divider when completed section is empty |
| E3 | Both sections empty (no tasks at all) | R1 | No orphaned spacing or section elements; implementer verifies no empty-state regressions |

### Round 3: Scope Boundaries

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | Visual divider/separator between sections | In | User wants clear visual separation between active and done tasks |
| B2 | Collapsible completed section | In | User wants ability to hide done tasks to save space |
| B3 | Full spacing audit across entire task list | Out | Keeps PR focused on the active-to-completed gap only |

### Round 4: Architecture Review

| # | Implication | Impact Area | Resolution |
|---|------------|-------------|------------|
| AR1 | Collapsible section introduces client-side state (expanded/collapsed) | deps | Use React useState; no API or localStorage persistence; defaults to expanded on page load |
| AR2 | New UI elements needed (divider, section header, chevron toggle) | deps | Reuse existing frontend UI patterns and icon library; no new dependencies |

### Round 5: PII / Compliance Review

| # | Data Element | Classification | Handling Requirement |
|---|-------------|---------------|---------------------|
| P1 | N/A | N/A | No new data created, stored, or transmitted. Feature only modifies CSS spacing and adds a client-side collapse toggle. |

### Round 6: UX & Interaction Review

| # | Concern | Category | Resolution |
|---|---------|----------|------------|
| UX1 | Collapse toggle affordance — user needs clear visual cue | consistency | Chevron icon (down when expanded, right when collapsed) next to "Completed" section header label |
| UX2 | Collapsed state indicator — user should know completed tasks exist when hidden | states | Show task count in header, e.g., "Completed (5)", visible in both expanded and collapsed states |

## Readiness Checklist

- [x] All High-confidence requirements have acceptance criteria
- [x] No unresolved conflicts remain
- [x] Open questions are non-blocking or have owners
- [x] At least 3 assumptions explicitly challenged and resolved
- [x] At least 3 edge cases explicitly addressed
- [x] Out of Scope section reviewed via scope boundary probe
- [x] At least 2 architectural implications reviewed
- [x] PII and sensitive data elements identified with handling requirements (or explicit N/A)
- [x] At least 2 UX/interaction concerns reviewed (or explicit N/A for non-UI features)
