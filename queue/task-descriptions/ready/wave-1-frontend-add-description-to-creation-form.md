---
status: ready
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: task-descriptions
type: feature
---

## Description

Add optional description textarea to the task creation form

## Why

Users need a way to add a description when creating a task. This adds the textarea to the existing creation form and sends the description in the POST request.

## Implementation Notes

Modify `src/App.jsx`:

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

## Contract References

POST /tasks requestBody: `description` (string, maxLength 2000, optional).

## Acceptance Criteria

- [ ] Tests pass (`npx vitest run`)
- [ ] Contract-compliant
- [ ] Frontend creation form shows an optional description textarea with visible 'Description' label
- [ ] Description is plain text only — no rich text rendering
- [ ] Description textarea enforces 2000-character limit via maxLength attribute
- [ ] Character counter appears when description exceeds 1,600 characters
- [ ] Character counter turns red/warning at 2,000 characters
- [ ] Submitting form with description sends it in POST /tasks body
- [ ] Submitting form without description omits it from the request
- [ ] Description field clears after successful task creation
