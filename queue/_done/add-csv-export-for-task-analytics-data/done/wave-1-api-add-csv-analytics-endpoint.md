---
task-id: add-csv-analytics-endpoint
status: done
execution: supervised
target-repo: api
wave: 1
priority: high
feature: add-csv-export-for-task-analytics-data
type: feature
claimed-by: agent-Christians-MacBook-Air-8711
claimed-at: 2026-03-30T14:58:37Z
claimed-on: Christians-MacBook-Air
cost-usd: 0.4313248499999999
input-tokens: 20
output-tokens: 4727
duration-ms: 121501
pr-url: https://github.com/ChristianJensen/agentic-sdlc-api/pull/29
pr-number: 29
---

## Description

Add GET /tasks/analytics/csv endpoint that returns task status counts in CSV format for spreadsheet import.

## Why

Provides the core API functionality for CSV export that the frontend will consume. Users can download analytics data as CSV files for external analysis.

## Implementation Notes

Add endpoint after existing /tasks/analytics route in src/app.js. Reuse existing analytics logic from GET /tasks/analytics but format as CSV. Use native string concatenation for CSV generation - no external dependencies needed. Set Content-Type: text/csv and Content-Disposition header with filename task-analytics-YYYY-MM-DD.csv. Handle same error cases as JSON endpoint (none currently - analytics always returns 200). Add response caching with 5-minute TTL using a simple in-memory cache with timestamps to handle volume scaling.

## Contract References

New /tasks/analytics/csv endpoint in contract returns text/csv with Status,Count format matching countsByStatus from existing TaskAnalytics schema.

## Acceptance Criteria

- [ ] Tests pass (npm test)
- [ ] Contract-compliant
- [ ] GET /tasks/analytics/csv returns 200 with Content-Type: text/csv
- [ ] CSV format: Status,Count headers with todo, in-progress, done rows
- [ ] Content-Disposition header sets filename to task-analytics-YYYY-MM-DD.csv with current date
- [ ] CSV data matches task counts from existing /tasks/analytics endpoint
- [ ] Response cached with 5-minute TTL to handle volume scaling
- [ ] Always includes all three status rows even when counts are zero
- [ ] CSV generation uses native string concatenation without external dependencies
