---
status: in-progress
target-repo: frontend
wave: 1
priority: high
feature: delete-comments
type: feature
contracts:
  - contracts/tasks-api.json
---

## Description

Add a delete button to comments authored by the current user, with a confirmation dialog. Wire up the `DELETE /tasks/{taskId}/comments/{commentId}` API call and refresh the comment list on success.

## Why

Users need a way to remove their own comments from task discussions. The confirmation dialog prevents accidental deletions.

## Implementation Notes

**Files to modify:**
- `src/App.jsx` (~1,195 lines) — monolithic component with all UI and state

**User identity:**
- Generate a stable `userId` (e.g., `localStorage.getItem('userId') || crypto.randomUUID()`, stored on first visit)
- Send as `X-User-Id` header on all comment API calls (POST and DELETE)
- Compare `comment.authorId` with local `userId` to show/hide the delete button

**Add `deleteComment(taskId, commentId)` function** — follow the existing `deleteTask` pattern (lines 791–794 of App.jsx):
```javascript
const deleteComment = async (taskId, commentId) => {
  await fetch(`${API_URL}/tasks/${taskId}/comments/${commentId}`, {
    method: 'DELETE',
    headers: { 'X-User-Id': userId },
  });
  fetchComments(taskId);
};
```

**Update `addComment`** (lines 735–751) to send `X-User-Id` header on POST.

**Update `fetchComments`** — no changes needed (authorId will be in the response automatically).

**Add delete button to comment rendering in both components:**
1. `SortableTaskItem` — comment list at lines 351–366
2. `CompletedTaskItem` — comment list at lines 565–570

Button styling: follow existing delete button pattern (Trash2 icon from lucide-react, rose color, visible on hover). Size it smaller than the task delete button since it's inline with comment text.

**Confirmation dialog:**
- No existing confirmation dialog pattern in the app. Use `window.confirm()` for simplicity — it's a standard browser dialog and matches the feature spec requirement without adding a custom modal component.
- Guard the delete call: `if (window.confirm('Delete this comment?')) deleteComment(taskId, commentId)`

**Error handling:**
- On 403: show error in `commentsErrors` state — "You can only delete your own comments"
- On 404: silently refetch (comment was already gone)

**Estimated size:** ~50 lines production code + ~80 lines tests = ~130 lines total (medium).

## Contract References

- `DELETE /tasks/{taskId}/comments/{commentId}` — 204 on success, 403 if not author, 404 if not found
- `X-User-Id` header — sent on POST (create) and DELETE calls
- `Comment` schema — `authorId` field used to determine delete button visibility

## Acceptance Criteria

- [ ] Tests pass (`npm test`)
- [ ] Contract-compliant
- [ ] A stable `userId` is generated and persisted in localStorage
- [ ] `X-User-Id` header is sent on POST /comments and DELETE /comments calls
- [ ] Delete button (Trash2 icon) appears only on comments where `comment.authorId === userId`
- [ ] Delete button does NOT appear on other users' comments
- [ ] Clicking delete shows a `window.confirm()` dialog; cancelling does nothing
- [ ] Confirming delete calls `DELETE /tasks/{taskId}/comments/{commentId}` and removes the comment from the UI
- [ ] After delete, the comment list refreshes without a full page reload
- [ ] Deleting the last comment leaves an empty comment list (no ghost entries)
- [ ] A 403 response shows an error message to the user
- [ ] Delete button appears in both incomplete task comments (SortableTaskItem) and completed task comments (CompletedTaskItem)
