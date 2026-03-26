---
feature: task-descriptions
completed: 2026-03-26
tasks: 4
waves: 2
total-cost-usd: 2.2386
total-tokens: 31863
---

## Overview

End users of the task tracker can currently only give tasks a short title. Titles alone don't provide enough context — users need a place to capture details, steps, or notes about a task so they can understand what needs to be done without relying on memory. The API contract already defines an optional `description` field (max 2000 characters) on tasks, but neither the API implementation nor the frontend supports it. This feature closes that gap.

## What Was Built

### Wave 1

- **api** — Add description field to task creation, update, and retrieval endpoints
- **frontend** — Add optional description textarea to the task creation form

### Wave 2

- **frontend** — Add expandable inline detail panel with accordion behavior to display task descriptions
- **frontend** — Add inline description editing with save/cancel, loading state, character counter, unsaved changes confirmation, and error handling

## Key Decisions

- **wave-1-api-add-description-field:** Modify `src/app.js`:

1. **POST /tasks** (line ~200): Extract `description` from `req.body`. Validate: if provided, must be a string with `length <= 2000` — return 400 otherwise. Add `description: description !== undefined ? (typeof description === 'string' ? description : '') : null` to the task object (line ~218-227). Empty string `""` is valid and clears the description.

2. **PATCH /tasks/:id** (line ~243): Extract `description` from `req.body` (add to destructuring on line 248). If `description !== undefined`, validate max 2000 chars — return 400 if exceeded. Set `task.description = description`. Allow empty string to clear.

3. **taskWithCount()** already spreads `...task`, so description passes through automatically in all GET responses.

4. **Validation pattern**: Follow the existing pattern for comment text validation (line 361-363) — `if (description !== undefined && typeof description === 'string' && description.length > 2000) return 400`.

Edge cases:
- `description: null` on POST sets description to null (no description)
- `description: ""` on PATCH clears the description
- `description` omitted entirely on POST defaults to null
- Description at exactly 2000 chars succeeds; 2001 chars returns 400
- **wave-1-frontend-add-description-to-creation-form:** Modify `src/App.jsx`:

1. **State**: Add `const [description, setDescription] = useState('')` near existing `title`, `dueDate`, `priority` state declarations (~line 910-920).

2. **Form textarea** (~20 lines): Below the existing form row (after the button at ~line 1495), add a new row with a `<textarea>` for description. Style consistently with `darkInputStyle`. Add `placeholder="// optional description..."`, `maxLength={2000}`, `rows={3}`. Add visible label `"Description"` using a `<label>` element.

3. **Character counter** (~15 lines): Below the textarea, conditionally render a character counter when `description.length >= 1600`. Show `${description.length}/2000`. Style: normal color when < 2000, red/warning (`theme.colors.rose500`) at 2000. Use `fontSize: '0.75em'`.

4. **Submit handler** (line ~1147): Update the `body` object in `addTask` to include `...(description.trim() ? { description: description.trim() } : {})`. After successful creation, add `setDescription('')` to the reset block (line ~1154-1156).

5. **Textarea enforces limit**: The `maxLength={2000}` HTML attribute handles paste and typing. The character counter provides visual feedback.

Modify `tests/App.test.jsx`: Add tests (~40 lines):
- Description textarea renders in the creation form with 'Description' label
- Submitting form with description sends it in POST body
- Submitting form without description omits description from POST body
- Character counter appears at 1600+ characters
- Character counter shows warning style at 2000 characters
- Description field clears after successful submission
- **wave-2-frontend-expandable-detail-panel:** Modify `src/App.jsx`:

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
- **wave-2-frontend-inline-description-editing:** Modify `src/App.jsx`:

1. **State**: Add `const [editingDescriptionId, setEditingDescriptionId] = useState(null)` and `const [editingDescriptionText, setEditingDescriptionText] = useState('')` and `const [savingDescription, setSavingDescription] = useState(false)` and `const [descriptionError, setDescriptionError] = useState(null)` near existing state.

2. **Edit handler** (~5 lines): `startEditDescription(task)` — sets `editingDescriptionId` to task.id, `editingDescriptionText` to `task.description || ''`, clears error.

3. **Save handler** (~20 lines): `saveDescription(taskId)` — sets `savingDescription=true`, calls `PATCH ${API_URL}/tasks/${taskId}` with `{ description: editingDescriptionText }` and `X-User-Id` header. On success: update local state, exit edit mode, clear saving state. On 404: show inline error "This task no longer exists", collapse detail panel after brief delay (R13, E3). On other error: show inline error below textarea. Set `savingDescription=false` on completion.

4. **Cancel handler** (~3 lines): `cancelEditDescription()` — clears editing state.

5. **Unsaved changes guard** (~15 lines): Modify `toggleDetailPanel` — before collapsing or switching panels, check if `editingDescriptionId` is set and text has changed from original. If so, show `window.confirm('You have unsaved changes. Discard?')`. If user cancels, abort the toggle. Same check when clicking a different task row.

6. **Detail panel edit mode** (~50 lines): When `editingDescriptionId === task.id`:
   - Render `<textarea>` with `value={editingDescriptionText}`, `onChange`, `maxLength={2000}`, `aria-label="Description"`
   - Character counter: show when `editingDescriptionText.length >= 1600`, red at 2000 (reuse pattern from creation form)
   - Save button: shows "Saving..." when `savingDescription`, `disabled={savingDescription}` (R14)
   - Cancel button: calls `cancelEditDescription()`
   - Error message: `{descriptionError && <p style={{color: rose500}}>{descriptionError}</p>}` below textarea
   When not editing: show description text with an Edit button that calls `startEditDescription(task)`

7. **Description textarea label**: Add visible "Description" label above the textarea when in edit mode (R15).

Modify `tests/App.test.jsx` (~70 lines):
- Edit button appears in detail panel, clicking it shows textarea with current description
- Save button calls PATCH with description and X-User-Id header
- Save button shows loading state and is disabled during API call
- Cancel button exits edit mode without saving
- Character counter appears at 1600+ characters during editing
- Saving description for a deleted task (404) shows inline error
- Save failure shows inline error message below textarea
- Unsaved changes prompt confirmation when clicking another task
- Description textarea has a visible 'Description' label

## Contracts Affected

(No contracts referenced)

## Cost Summary

**Total: $2.2386** (31,863 tokens, 739s)

| Wave | Task | Cost | Tokens |
|------|------|------|--------|
| W1 | wave-1-api-add-description-field | $0.4776 | 6,419 |
| W1 | wave-1-frontend-add-description-to-creation-form | $0.5236 | 6,428 |
| W2 | wave-2-frontend-inline-description-editing | $1.2374 | 19,016 |

## Retrospective Notes

(No retrospective entries)
