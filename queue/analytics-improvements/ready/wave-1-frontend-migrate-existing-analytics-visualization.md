---
task-id: migrate-existing-analytics-visualization
status: ready
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: analytics-improvements
type: feature
depends-on:
  - create-analytics-page-foundation
---

## Description

Move all existing analytics data displays (task counts by status, daily completions chart, average time metrics) from sidebar to the new analytics page in expanded layout

## Why

Preserves current functionality while expanding the display space available for analytics data

## Implementation Notes

Extract analytics display logic from AnalyticsSidebar component into reusable components for the new page. Implement task counts by status, daily completions for last 7 days, and average time in status metrics. Use existing data structure from /tasks/analytics response. Ensure responsive layout that takes advantage of full page space. Create tests for each analytics section component.

## Contract References

TaskAnalytics.countsByStatus (todo, in-progress, done counts), TaskAnalytics.completedPerDay (last 7 days array), TaskAnalytics.avgTimeInStatus (todo and inProgress averages in hours)

## Acceptance Criteria

- [ ] Tests pass (npm test)
- [ ] Contract-compliant
- [ ] Task counts by status displayed on analytics page
- [ ] Daily completions chart for last 7 days displayed
- [ ] Average time in status metrics displayed
- [ ] All data displays use expanded page layout effectively
- [ ] Analytics visualizations match existing design patterns
- [ ] Data displays handle null/empty values gracefully
- [ ] Components are responsive and work on different screen sizes
