# Edge Case Library

Accumulated edge cases from past failures, referenced by the Planner Agent during Refinement Round 2.

## How to Use

During Feature Definition Refinement Round 2, scan this library for edge case patterns relevant to the current feature. Each category contains common failure modes discovered from real agent failures.

## Categories

### Input Validation
- Empty strings where non-empty expected
- Extremely long input (>10,000 characters)
- Special characters: emoji, RTL text, HTML/script tags, null bytes
- Unicode edge cases (combining characters, zero-width spaces)

### Dates and Times
- Dates in the past
- Timezone boundaries and DST transitions
- Midnight edge cases (00:00 vs 24:00)
- Leap years, month boundaries
- Invalid date formats

### Concurrent Operations
- Two users editing the same resource simultaneously
- Race conditions between create and delete
- Stale data from cached reads

### Network and Infrastructure
- Network timeout mid-operation
- Partial failure in multi-step operations
- API rate limiting
- Large payload sizes

### Data Boundaries
- Empty collections (zero items)
- Single item in a collection
- Maximum pagination limits
- Null vs undefined vs empty string

### Authorization
- Expired tokens mid-operation
- Permission changes during active session
- Cross-tenant data access

---

_Add new edge cases here as they are discovered from retrospective entries._
