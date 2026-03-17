---
status: done
target-repo: api
wave: 1
priority: high
feature: delete-comments
type: feature
contracts:
  - contracts/tasks-api.json
---

## Description

Add a `DELETE /tasks/:id/comments/:commentId` endpoint with author-ownership enforcement. This requires:

1. Adding an `authorId` field to comments (stored on creation from the `X-User-Id` header)
2. Modifying `POST /tasks/:id/comments` to read `X-User-Id` and store it as `authorId`
3. Adding the DELETE endpoint that validates ownership before deleting

## Why

Users need to remove their own comments. The ownership check prevents users from deleting each other's comments. The `authorId` field is the minimal auth mechanism needed since the app has no user system.

## Implementation Notes

**Files to modify:**
- `src/app.js` (~286 lines) — all routes live here

**Follow the existing subtask DELETE pattern** (lines 245–255 of `app.js`):
1. Parse `taskId` and `commentId` from params (convert to `Number`)
2. Validate task exists → 404
3. Validate comment exists AND `comment.taskId === taskId` → 404
4. Validate `req.get('X-User-Id') === comment.authorId` → 403
5. `comments.delete(commentId)`
6. `res.status(204).end()`

**Modify POST /tasks/:id/comments** (lines 177–193 of `app.js`):
- Read `authorId` from `req.get('X-User-Id')` header
- Store `authorId` on the comment object
- Return `authorId` in the response

**Modify GET /tasks/:id/comments** response:
- Include `authorId` in each returned comment (it's already stored, just ensure it's returned)

**Error response format** — the existing codebase uses `{ error: "message" }`. The contract schema uses `{ message: "..." }`. Match the existing codebase pattern (`error` key) for consistency; update the contract later if needed.

**Estimated size:** ~30 lines of production code + ~60 lines of tests = ~90 lines total (small-medium).

## Contract References

- `DELETE /tasks/{taskId}/comments/{commentId}` — 204 on success, 403 if not author, 404 if not found
- `POST /tasks/{taskId}/comments` — now requires `X-User-Id` header, returns `authorId` in response
- `X-User-Id` header parameter — identifies the calling user
- `Comment` schema — includes `authorId` field

## Acceptance Criteria

- [ ] Tests pass (`npm test`)
- [ ] Contract-compliant
- [ ] `POST /tasks/:id/comments` with `X-User-Id` header stores `authorId` on the comment
- [ ] `POST /tasks/:id/comments` without `X-User-Id` defaults `authorId` to `"anonymous"`
- [ ] `GET /tasks/:id/comments` returns `authorId` for each comment
- [ ] `DELETE /tasks/:id/comments/:commentId` with matching `X-User-Id` returns 204 and removes the comment
- [ ] `DELETE /tasks/:id/comments/:commentId` with non-matching `X-User-Id` returns 403 and leaves the comment unchanged
- [ ] `DELETE /tasks/:id/comments/:commentId` for non-existent task returns 404
- [ ] `DELETE /tasks/:id/comments/:commentId` for non-existent comment returns 404
- [ ] Deleting the last comment on a task leaves the list empty (no ghost entries)
