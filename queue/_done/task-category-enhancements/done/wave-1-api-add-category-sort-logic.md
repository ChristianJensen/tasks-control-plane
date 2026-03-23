---
status: done
execution: autonomous
target-repo: api
wave: 1
priority: high
feature: task-category-enhancements
type: feature
---

## Description

Add `sort=category` support to GET /tasks endpoint. Implement a CATEGORY_ORDER constant mapping (errands=0, personal=1, work=2) co-located with existing sort logic. Sort tasks by this fixed mapping with null/uncategorized tasks sorting last in ascending order and first in descending order. Use createdAt desc as tiebreaker for equal category values. Extend existing sort validation to accept 'category' as a valid sort value (invalid values still return 400).

## Why

This is the foundational backend change that enables the entire feature. The API must support category sorting before the frontend can offer it as an option. Follows the same deployment pattern as multiassign (API wave 1, frontend wave 2).

## Implementation Notes

Modify `src/app.js` (~300 lines). Key changes:

1. **CATEGORY_ORDER constant** (~3 lines): Define `const CATEGORY_ORDER = { errands: 0, personal: 1, work: 2 }` near the existing STATUS_ORDER constant (used by status sort). This follows the same pattern.

2. **Extend sort logic in GET /tasks** (~15 lines): In the existing sort handler (look for where `sort` query param is processed and `STATUS_ORDER` is used), add a `case 'category':` branch. Use `CATEGORY_ORDER[task.category]` for comparison. Handle nulls: assign a sentinel value (e.g., `Infinity` for ASC, `-Infinity` for DESC) so nulls sort last/first respectively. Apply createdAt desc tiebreaker (same pattern as existing sort fields).

3. **Validation** (~2 lines): The sort param validation should already accept any value in the enum. Verify 'category' is included in the valid sort values array. If validation uses a hardcoded list, add 'category' to it.

4. **Add test for CATEGORY_ORDER ↔ enum sync** (~5 lines): A test that validates every value in the category enum has a mapping in CATEGORY_ORDER (per AR2 architectural implication).

Add tests in `tests/tasks.test.js` (~80 lines):
- `sort=category&order=asc` returns errands → personal → work → null
- `sort=category&order=desc` returns null → work → personal → errands
- Same-category tasks sub-sorted by createdAt desc
- `sort=category&status=todo` correctly filters and sorts
- All tasks uncategorized (null) → effectively sorted by tiebreaker (E1)
- Single category after filter → tiebreaker applies (E3)
- Invalid sort value still returns 400
- CATEGORY_ORDER covers all enum values (AR2)

## Contract References

GET /tasks `sort` query parameter: enum includes 'category'. Sort description: 'Category sort uses alphabetical order: errands=0, personal=1, work=2. Null categories sort last (asc) or first (desc).' Order parameter: 'Tiebreaker for equal values is createdAt desc.'

## Acceptance Criteria

- [ ] Tests pass (`npm test`)
- [ ] Contract-compliant
- [ ] `GET /tasks?sort=category&order=asc` returns tasks ordered: errands → personal → work → null
- [ ] `GET /tasks?sort=category&order=desc` returns tasks ordered: null → work → personal → errands
- [ ] Tasks with the same category are sub-sorted by createdAt desc
- [ ] `GET /tasks?sort=category&status=todo` correctly filters and sorts
- [ ] Invalid sort values still return 400
- [ ] CATEGORY_ORDER constant covers all TaskCategory enum values (AR2 sync test)
- [ ] All-null categories degrade gracefully to tiebreaker sort (E1)
- [ ] Single category after filter uses tiebreaker (E3)
