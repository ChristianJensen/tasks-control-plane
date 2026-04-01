<!-- STATUS NOTE: The parent directory (pending/, ready/, in-progress/, done/,
     blocked/, paused/, cancelled/) is authoritative for task status.
     The status field below is kept in sync for human readability.
     When directory and frontmatter diverge, the directory wins. -->
---
status: ready
execution: ""
model: ""
target-repo: api
wave: 1
priority: high
feature: <feature-name>
type: feature
budget: ""
claimed-by: ""
claimed-at: ""
claimed-on: ""
pr-url: ""
pr-number: ""
cost-usd: ""
input-tokens: ""
output-tokens: ""
duration-ms: ""
contracts:
  - contracts/tasks-api.json
depends-on:
  # - wave-1-api-add-field.md
---

## Description

_What needs to be built or changed._

## Why

_How this task connects to the parent feature._

## Implementation Notes

_Architectural guidance, constraints, edge cases._

## Contract References

_Relevant sections of the OpenAPI spec — endpoints, request/response shapes._

## Acceptance Criteria

### Behaviors

- **GIVEN** _precondition describing initial state_
  **WHEN** _action the user or system takes_
  **THEN** _observable outcome_

### Invariants

- [ ] Tests pass (`npm test`)
- [ ] Contract-compliant
