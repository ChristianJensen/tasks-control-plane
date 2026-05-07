---
title: "Share a Task"
lifecycle: active
execution: supervised
model: ""
priority: medium
dimensions: [assumptions, edges, scope, arch, pii, ux]
total-budget: ""
total-cost-usd: ""
total-tokens: ""
epic: ""
epic-title: ""
version: 1
loop: ""
paused-at: ""
paused-by: ""
pause-reason: ""
created-at: ""
completed-at: ""
deployed-at: ""
deployed-env: ""
---
# Share a Task

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| 1 | conversation | interview transcript (planner) | user | draft |

## Problem Statement

Users sometimes need to show a task to someone who doesn't use the app — a collaborator, a friend, a vendor — without forcing them to sign up or log in. Today there's no way to do that: tasks are only viewable from inside the app, and IDs are sequential integers, so no shareable URL exists that can be safely sent to an outsider. Users want a lightweight, copy-paste link that opens a clean read-only view of a single task.

## User Stories

### US-1: As a task owner, I want to copy a public link to a task so that I can share it with someone who doesn't have an account

Status: pending
Repos: api, frontend
PR-api:
PR-frontend:

**Scenarios:**
- **BDD-1** **GIVEN** a task exists and has no share token yet **WHEN** the user opens the task detail view and clicks "Share" **THEN** the API generates a 22-character URL-safe base64 share token, persists it on the task, and returns it so the frontend can display the public URL in a popover with a "Copy link" button
- **BDD-2** **GIVEN** a task already has a share token from a previous share action **WHEN** the user clicks "Share" again on the same task **THEN** the existing token is reused (no new token generated) and the same public URL is shown
- **BDD-3** **GIVEN** the share popover is open with a generated link **WHEN** the user clicks "Copy link" **THEN** the URL is copied to the clipboard and a brief confirmation ("Copied") is shown
- **BDD-4** **GIVEN** a task with no share token yet **WHEN** the user clicks "Share" **THEN** the popover opens immediately with a placeholder URL field and a disabled "Copy link" button, and once the API responds the real URL is rendered and "Copy link" becomes enabled
- **BDD-5** **GIVEN** the token-generation request fails (network error or 5xx) **WHEN** the response is received **THEN** the popover shows an inline error message ("Couldn't create share link") with a retry affordance, and no URL is shown or copyable

**Notes:** First story owns shared infra: adds the nullable, unique-indexed `shareToken` column to the `tasks` table, the `POST /tasks/{taskId}/share` endpoint that lazily generates/returns the token, and the OpenAPI updates the frontend will consume. The api repo is declared first so the contract is merged before the frontend agent reads it.

### US-2: As a link recipient, I want to open a shared link and see the task so that I can read it without signing in

Status: pending
Repos: api, frontend
PR-api:
PR-frontend:

**Scenarios:**
- **BDD-6** **GIVEN** a valid share token exists for a task **WHEN** an unauthenticated visitor requests the public task endpoint with that token (no `X-User-Id` header required) **THEN** the API returns a minimal payload containing only the task's title, description, and status
- **BDD-7** **GIVEN** a valid share token **WHEN** an unauthenticated visitor opens `/shared/{token}` in the frontend **THEN** they see a minimal read-only page showing the task title as the heading, the description below, a status badge (To do / In progress / Done), and a small "Shared task" header — with no edit controls, no comments, no history, and no navigation to other tasks
- **BDD-8** **GIVEN** a token that does not match any task (unknown, malformed, or belonged to a since-deleted task) **WHEN** an unauthenticated visitor requests the public task endpoint or opens `/shared/{token}` **THEN** the API returns 404 and the frontend shows a generic "This link is no longer available" page that does not distinguish between never-existed and deleted

**Notes:** The api repo is declared first so the `GET /public/tasks/{token}` response shape is fixed in the OpenAPI contract before the frontend renders against it.

## Constraints

| # | Category | Requirement | Verification |
|---|----------|-------------|--------------|
| C1 | Security | Share tokens must be 22-character URL-safe base64 (≥128 bits of entropy) and stored in a unique-indexed `shareToken` column on `tasks`; lookups are by token only and never enumerate IDs | Code review of token generator; DB migration review; integration test asserts unknown/malformed tokens return 404 |
| C2 | Privacy/PII | Public task endpoint returns only `title`, `description`, `status` — no owner identity, timestamps, comments, history, category, or `X-User-Id` echo | Contract test against `/public/tasks/{token}` payload shape; OpenAPI schema restricts response fields |
| C3 | Privacy | Public endpoint must not require or accept the `X-User-Id` header; unauthenticated requests succeed when token is valid | Integration test: request without `X-User-Id` returns 200 with valid token, 404 with invalid token |
| C4 | Privacy | 404 response for unknown, malformed, and deleted-task tokens must be indistinguishable (same status, same body) to prevent enumeration of which tokens previously existed | Integration test compares responses across the three cases |
| C5 | Accessibility/Responsive | Public `/shared/{token}` page must render usably at ≥320px viewport width with no horizontal scroll; title, status badge, and description reflow cleanly | Manual check at 320px, 375px, and desktop widths; visual regression snapshot |
| C6 | UX | Share popover must distinguish loading, ready, and error states (see BDD-4, BDD-5); "Copy link" is disabled until a valid URL is present | Component test covers all three popover states |

## Out of Scope

- Manual revocation of share links (rotating or deleting a token while keeping the task)
- Link expiry (time-based or view-count-based)
- A "manage shared links" list or any per-share metadata (view counts, last accessed, etc.)
- Sharing from the task list row (trigger lives only in the task detail view)
- Exposing comments, status history, category, timestamps, or any other field beyond title/description/status on the public page
- Social/OG preview metadata for the shared URL
- Sharing with authenticated users inside the app (collaborator/permissions model)
- Any export, email, or OS share-sheet integration

## Implementation Log

_Implementation learnings (Decisions, Discoveries, Spec gaps) live in the sibling file `share-a-task-feature-impl-log.md`, appended by `post-agent.sh` after each PR merge. Read that file before claiming a downstream story-repo._

## Readiness Checklist

- [x] Problem statement is concrete and user-facing
- [x] At least one user story defined
- [x] Each user story declares Status, Repos, and ≥1 BDD-N scenario
- [x] BDD-N IDs are sequential and unique across the spec
- [x] Constraints section addresses NFRs (or explicit `N/A` row with rationale)
- [x] Out of Scope section is explicit (no empty placeholder)
