---
task-id: add-pie-chart-and-finalize-migration
status: done
execution: supervised
target-repo: frontend
wave: 1
priority: high
feature: analytics-improvements
type: feature
depends-on:
claimed-by: agent-Christians-MacBook-Air-93924
claimed-at: 2026-03-28T18:27:28Z
claimed-on: Christians-MacBook-Air
cost-usd: 2.5187381999999996
input-tokens: 80
output-tokens: 31809
duration-ms: 700269
pr-url: https://github.com/ChristianJensen/agentic-sdlc-frontend/pull/68
pr-number: 68
---

## Description

Add Chart.js library, implement pie chart for completed tasks by category, update analytics button to navigate to page instead of opening sidebar, and remove old sidebar code

## Why

Completes the migration by adding the new pie chart visualization and fully replacing the sidebar with page navigation

## Implementation Notes

Install Chart.js library. Create pie chart component using completedTasksByCategory data (work, personal, errands, uncategorized). Handle empty state when no completed tasks exist. Update analytics button onClick to navigate to /analytics route instead of toggling sidebar. Add button disabled state during navigation. Completely remove AnalyticsSidebar component and related state (analyticsOpen, setAnalyticsOpen, fetchAnalytics). Create comprehensive tests for pie chart component and navigation behavior.

## Contract References

TaskAnalytics.completedTasksByCategory (work, personal, errands, uncategorized counts for pie chart visualization)

## Acceptance Criteria

- [ ] Tests pass (npm test)
- [ ] Contract-compliant
- [ ] Chart.js library installed and configured
- [ ] Pie chart shows completed tasks by category breakdown
- [ ] Pie chart shows helpful empty state when no completed tasks exist
- [ ] Analytics button navigates to /analytics instead of opening sidebar
- [ ] Analytics button is disabled during navigation to prevent duplicate clicks
- [ ] Old AnalyticsSidebar component completely removed
- [ ] All analytics-related sidebar state removed (analyticsOpen, etc)
- [ ] Pie chart follows existing color scheme and design patterns
- [ ] Pie chart is accessible with proper ARIA labels
