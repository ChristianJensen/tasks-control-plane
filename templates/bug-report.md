---
lifecycle: draft         # echoes directory — draft | active | paused | cancelled | replanning | completed
type: bug
version: 1
severity: critical       # critical | high | medium | low
affected-repos:
  - api                  # api | frontend | both
reported-by: ""          # human | agent:<task-file-path>
paused-at: ""
paused-by: ""
pause-reason: ""
---

# Bug Report: <Short Title>

## Observed Behavior

_What actually happens — include error messages, status codes, unexpected output._

## Expected Behavior

_What should happen instead._

## Reproduction Steps

1. _Step to trigger the bug_
2. _..._
3. _..._

## Environment

- **Repo/Branch:** _e.g., api/main_
- **Endpoint/Component:** _e.g., POST /tasks or TaskList component_
- **Trigger Frequency:** _always | intermittent | rare_

## Evidence

_Screenshots, logs, or other supporting files._

<!-- If evidence exists, list as:
- `evidence/screenshot-1.png` — Description of what it shows
- `evidence/error.log` — Description of the relevant log entries
-->

No attachments provided.

## Diagnostic Reasoning

### Root Cause Analysis

_Why the bug occurs — reference specific files, functions, and logic._

### Affected Code Paths

| Repo | File | Function/Line | Issue |
|------|------|---------------|-------|
| _api_ | _src/..._ | _functionName_ | _description_ |

### Fix Strategy

_Proposed approach to resolve the bug._

## Scope Assessment

- [ ] Single-task fix (one repo, <50 lines)
- [ ] Multi-task fix (needs decomposition into waves)

_If multi-task, briefly describe why and what the waves would cover._

## Acceptance Criteria

- [ ] Bug no longer reproduces following the reproduction steps
- [ ] Regression test added covering the failure case
- [ ] No existing tests broken
- [ ] _Additional criteria specific to this bug_
