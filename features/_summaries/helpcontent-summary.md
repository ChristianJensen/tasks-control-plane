---
feature: helpcontent
completed: 2026-03-21
tasks: 2
waves: 2
---

## Overview

End users of the task management app have no in-app way to discover what capabilities are available to them. Without guidance, users must explore the UI on their own to understand features like batch operations, categories, status workflows, and comments. This leads to underutilization of the system's capabilities. A help content drawer gives users a quick, always-accessible reference to understand what they can do and how to do it.

## What Was Built

### Wave 1

- **frontend** — Build HelpDrawer component with help content, help button in header, and all interactive behavior (open/close toggle, backdrop click, Escape key, focus trapping, responsive layout).

### Wave 2

- **frontend** — Add comprehensive tests for the HelpDrawer component covering all acceptance criteria: rendering, toggle behavior, close mechanisms, keyboard accessibility, focus management, and non-interference with app state.

## Key Decisions

- **wave-1-frontend-help-drawer-component:** Modify src/App.jsx (all components live in this single file). Changes:

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
- **wave-2-frontend-help-drawer-tests:** Add tests in tests/App.test.jsx (append to existing test file, following existing patterns with vi.stubGlobal for fetch mocking and @testing-library/react).

Test cases to add (~180 lines):

1. **Help button rendering** — verify HelpCircle button is present in rendered app, has aria-label="Help".

2. **Drawer toggle** — click help button → drawer appears with help content. Click again → drawer disappears.

3. **Help content sections** — verify all 7 section headings are rendered: Creating Tasks, Viewing & Filtering Tasks, Updating Tasks, Deleting Tasks, Categories, Comments, Status Workflow.

4. **Close via X button** — open drawer, click close button, verify drawer is removed from DOM.

5. **Close via backdrop click** — open drawer, click the backdrop overlay, verify drawer closes.

6. **Close via Escape key** — open drawer, fire Escape keydown event, verify drawer closes.

7. **No API calls on open/close** — open and close drawer, verify no fetch calls were made during the interaction (check fetch mock call count before/after).

8. **Focus management** — open drawer, verify focus moves to close button (or first focusable element). Close drawer, verify focus returns to help button.

9. **Aria attributes** — verify help button has aria-expanded="false" initially, aria-expanded="true" when drawer is open.

10. **Does not affect edit state** — if possible with existing test patterns, start editing a task, open help drawer, close it, verify edit is still in progress.

Follow existing test patterns:
- Use `render(<App />)` with fetch mocked to return task data
- Use `screen.getByRole`, `screen.getByText`, `screen.queryByText`
- Use `fireEvent.click`, `fireEvent.keyDown`
- Use `waitFor` for async assertions

## Contracts Affected

(No contracts referenced)

## Retrospective Notes

(No retrospective entries)
