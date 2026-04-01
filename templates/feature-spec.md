<!-- LIFECYCLE NOTE: The parent directory (draft/, active/, completed/, cancelled/)
     is authoritative for feature lifecycle phase. The lifecycle field below is
     kept in sync for human readability. When directory and frontmatter diverge,
     the directory wins. Paused and replanning are sub-states within active/. -->
---
lifecycle: draft
execution: supervised
model: ""
priority: medium
total-budget: ""
total-cost-usd: ""
total-tokens: ""
epic: ""
epic-title: ""
version: 1
paused-at: ""
paused-by: ""
pause-reason: ""
created-at: ""
completed-at: ""
deployed-at: ""
deployed-env: ""
---

# Feature Spec: [Feature Name]

## Sources

| # | Type | File | Contributor | Date |
|---|------|------|-------------|------|
| 1 | [audio/wireframe/notes/conversation] | [path] | [who] | [when] |

## Problem Statement

_What problem does this solve? Who feels the pain?_

## User Journey

_Step-by-step happy path: what does the user do, and what happens at each step? Each step becomes a GIVEN/WHEN/THEN behavioral scenario in downstream task specs. Be concrete about observable outcomes._

1. User does X → System responds with Y
2. ...

_Error paths and edge cases (these also become behavioral scenarios):_

1. User does X incorrectly → System responds with Z

## Requirements

| # | Requirement | Source(s) | Confidence | Notes |
|---|-------------|-----------|------------|-------|
| R1 | | S1, S2 | High/Med/Low | |

## Conflicts Detected

| Sources | Conflict | Resolution |
|---------|----------|------------|
| S1 vs S3 | | [resolved/needs-input] |

## Open Questions

- [ ] Question 1 — _asked to [who]_

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Out of Scope

- Item 1

## Refinement Log

### Round 1: Assumptions
_What does this spec assume but not explicitly state?_

| # | Assumption | Challenged? | Resolution |
|---|-----------|-------------|------------|
| A1 | | Yes/No | |

### Round 2: Edge Cases
_Stress-test the spec with edge cases. Reference the edge case library at `retrospectives/edge-case-library.md`._

| # | Edge Case | Addressed By | Resolution |
|---|----------|-------------|------------|
| E1 | | [requirement #] | |

### Round 3: Scope Boundaries
_Propose adjacent features and confirm whether they are in or out of scope._

| # | Adjacent Feature | In/Out | Rationale |
|---|-----------------|--------|-----------|
| B1 | | In/Out | |

### Round 4: Architecture Review
_Challenge architectural implications: new services, API changes, scalability, dependencies, breaking changes._

| # | Implication | Impact Area | Resolution |
|---|------------|-------------|------------|
| AR1 | | [infra/API/perf/deps] | |

**Architecture diagrams consulted:** <!-- list files from architecture/ reviewed during this round -->
**Diagrams requiring update after ship:** <!-- none, or list diagrams that need changes -->

### Round 5: PII / Compliance Review
_Identify PII and sensitive data elements. Document retention, access, and deletion requirements. If no PII is involved, add an explicit N/A entry._

| # | Data Element | Classification | Handling Requirement |
|---|-------------|---------------|---------------------|
| P1 | | [PII/sensitive/internal/public/N/A] | |

### Round 6: UX & Interaction Review
_Challenge interaction design, accessibility, and visual consistency. For non-UI features, add an explicit N/A entry._

| # | Concern | Category | Resolution |
|---|---------|----------|------------|
| UX1 | | [states/responsive/a11y/consistency] | |

## Readiness Checklist

- [ ] All High-confidence requirements have acceptance criteria
- [ ] No unresolved conflicts remain
- [ ] Open questions are non-blocking or have owners
- [ ] At least 3 assumptions explicitly challenged and resolved
- [ ] At least 3 edge cases explicitly addressed
- [ ] Out of Scope section reviewed via scope boundary probe
- [ ] At least 2 architectural implications reviewed
- [ ] PII and sensitive data elements identified with handling requirements (or explicit N/A)
- [ ] At least 2 UX/interaction concerns reviewed (or explicit N/A for non-UI features)
