---
task-id: header-shows-active-list-name
status: done
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: task-list-switcher-visibility
type: feature
scenario-refs:
  - BDD-1
  - BDD-2
claimed-by: cloud-Christians-MacBook-Air-96460
claimed-at: 2026-04-16T18:39:09Z
claimed-on: Christians-MacBook-Air
cost-usd: 2.2643751
input-tokens: 49
output-tokens: 59785
duration-ms: 1455218
auth-mode: max-oauth
billed: false
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/105
pr-number: 105
---

## Description

User can see the name of the currently active task list displayed at all times in the app header, and the task area below shows only tasks belonging to that list. On cold start with no persisted selection, the first list returned by the server becomes the active list.

## Why

Delivers the core "which list am I looking at?" visibility requirement (R1, R6). Establishes the active-list state shape and header render surface that subsequent slices build on, but is itself a complete, shippable user story.

## Implementation Notes

Add a header region rendering the active list's name with data-testid="task-list-selector". Wire active-list state to the tasks fetch so it includes listId as a query param. On mount: if no persisted selection, fetch /task-lists and adopt the first returned list as active. Element should be the clickable selector (behavior for clicking arrives in the dropdown task) — for this slice, rendering + first-list bootstrap is enough.

## Contract References



## Acceptance Criteria

### Behaviors

- **GIVEN** the user has loaded the app with an active task list
  **WHEN** the task view renders
  **THEN** the header displays the name of the active list and the task area shows only tasks belonging to that list _(implements BDD-1)_

- **GIVEN** the user is viewing a task list
  **WHEN** they look at the header without interacting
  **THEN** the active list's name is readable at a glance (no modal or interaction required) _(implements BDD-2)_

### Invariants

- [ ] Tests pass
- [ ] Contract-compliant
