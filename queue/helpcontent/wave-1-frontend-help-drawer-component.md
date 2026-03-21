---
status: in-progress
execution: autonomous
target-repo: frontend
wave: 1
priority: high
feature: helpcontent
type: feature
claimed-by: agent-06-36-06-7A-C3-F6-20379
claimed-at: 2026-03-21T14:58:30Z
claimed-on: 06-36-06-7A-C3-F6
---

## Description

Build HelpDrawer component with help content, help button in header, and all interactive behavior (open/close toggle, backdrop click, Escape key, focus trapping, responsive layout).

## Why

This is the entire user-facing feature: a slide-out drawer with static help content covering all 7 feature areas, accessible via a help button in the app header. It must be keyboard-accessible with focus trapping (WAI-ARIA), responsive (400px desktop, full-width mobile), and must not affect application state when opened/closed.

## Implementation Notes

Modify src/App.jsx (all components live in this single file). Changes:

1. **Import** `HelpCircle` and `X` icons from `lucide-react` (already a dependency).

2. **Help content data** — define a `HELP_SECTIONS` constant array with 7 objects, each having a `title` and `content` string. Sections: Creating Tasks, Viewing & Filtering Tasks, Updating Tasks, Deleting Tasks, Categories, Comments, Status Workflow. Content describes capabilities and how to use them based on the existing app features. (~40 lines)

3. **State** — add `const [helpOpen, setHelpOpen] = useState(false)` near existing state declarations.

4. **HelpDrawer component** (~100 lines) — inline function component in App.jsx:
   - Renders nothing if `!helpOpen`.
   - Backdrop overlay: fixed position, semi-transparent black, covers viewport, onClick calls `setHelpOpen(false)`.
   - Drawer panel: fixed position, right:0, top:0, height:100%, width:400px (desktop), 100% width below 768px breakpoint (use `window.innerWidth` or CSS max-width). Background uses `theme.colors.bg` or similar dark theme token. Styled with inline style objects following existing patterns.
   - Close button (X icon) in drawer header.
   - Scrollable content area rendering each section from HELP_SECTIONS with heading and paragraph.
   - **Escape key**: `useEffect` with `keydown` listener when `helpOpen` is true.
   - **Focus trapping**: `useEffect` that queries focusable elements inside drawer, intercepts Tab/Shift+Tab to cycle within drawer. On open, focus the close button. On close, return focus to help button (use `useRef` on help button).
   - Style with inline style objects using theme tokens (colors, shadows) — no CSS modules.

5. **Help button** (~15 lines) — add a `HelpCircle` icon button in the app header/toolbar area (find the header JSX, add button near existing toolbar controls). `onClick` toggles `setHelpOpen(prev => !prev)`. Attach a `ref` for focus return. Add `aria-label="Help"` and `aria-expanded={helpOpen}`.

6. **Render HelpDrawer** at root level in the App component's return JSX, as a sibling to main content (not nested inside task list or detail views). Pass `helpOpen` and `setHelpOpen` as props or use closure.

Edge cases addressed:
- E1: Escape closes drawer (keydown listener)
- E2: Opening drawer during task edit does not affect edit state (drawer is a sibling component with independent boolean state, no shared state mutations)
- E3: Focus trapping and focus return (useEffect + useRef)

## Contract References

None — this is a frontend-only feature with no API calls (R13, R14). No contract changes required.

## Acceptance Criteria

- [ ] A help icon button (HelpCircle) is visible in the app header/toolbar on all views
- [ ] Clicking the help button opens a slide-out drawer from the right side
- [ ] The drawer contains help content organized into 7 feature sections: Creating Tasks, Viewing & Filtering Tasks, Updating Tasks, Deleting Tasks, Categories, Comments, Status Workflow
- [ ] Each section includes a heading and descriptive text explaining the capability and how to use it
- [ ] The drawer can be closed by clicking a close (X) button
- [ ] The drawer can be closed by clicking outside the drawer (backdrop click)
- [ ] The drawer can be closed by pressing the Escape key
- [ ] Clicking the help button while the drawer is open closes it (toggle behavior)
- [ ] Opening and closing the drawer does not affect application state (no data changes, no API calls)
- [ ] Opening the drawer while editing a task does not discard or affect the in-progress edit
- [ ] The drawer is accessible via keyboard (aria-label, aria-expanded on help button)
- [ ] Focus is trapped inside the drawer while open (Tab cycles through drawer content only)
- [ ] Focus returns to the help button when the drawer is closed
- [ ] The drawer is responsive: fixed width (~400px) on desktop, full-width overlay on small screens
- [ ] Drawer component is rendered at app root level as sibling to main content
- [ ] Uses inline style objects with theme tokens — follows existing styling conventions
- [ ] Tests pass (`npx vitest run`)
