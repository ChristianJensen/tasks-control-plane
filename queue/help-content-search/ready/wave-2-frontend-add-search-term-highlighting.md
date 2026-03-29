---
task-id: add-search-term-highlighting
status: ready
execution: autonomous
target-repo: frontend
wave: 2
priority: high
feature: help-content-search
type: feature
---

## Description

Highlight matching search terms in yellow/cyan within help section titles and content text. Add X button to search box for clearing search.

## Why

Provides visual feedback showing users exactly where their search terms appear in the help content, making it easier to scan results and find relevant information quickly.

## Implementation Notes

Create text highlighting utility function that safely escapes user input and wraps matching terms in styled spans. Modify help section rendering to use highlighted text when search is active. Add X button to search input with click handler to clear search. Ensure highlighting preserves existing text structure and handles edge cases like overlapping matches.

## Contract References

No API contract changes needed - frontend-only text processing and DOM manipulation.

## Acceptance Criteria

- [ ] Tests pass (`npm test`)
- [ ] Search terms highlighted in yellow/cyan in both titles and content
- [ ] X button appears in search box when text is present
- [ ] X button clears search and shows all sections when clicked
- [ ] Text highlighting safely escapes user input to prevent XSS
- [ ] Highlighting preserves existing content formatting
- [ ] Multiple matches in same text are all highlighted
- [ ] Highlighting works with special characters and Unicode
- [ ] No highlighting artifacts when search is cleared
