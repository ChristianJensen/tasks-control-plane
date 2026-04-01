# Refinement Protocol

**Purpose:** Guide for the Planner Agent or human running the Feature Definition to stress-test the spec through 6 structured rounds of challenge.

---

## Overview

The refinement protocol transforms a single-pass Feature Spec into a battle-tested specification. Each round targets a different class of gap:

1. **Assumptions** — what the spec takes for granted
2. **Edge Cases** — how the spec behaves under stress
3. **Scope Boundaries** — what's adjacent but excluded
4. **Architecture Review** — what the feature implies for infrastructure and system design
5. **PII / Compliance Review** — what data the feature handles and the regulatory implications
6. **UX & Interaction Review** — how the feature looks, feels, and behaves for users

In crawl mode, a human runs all 6 rounds manually. The Planner Agent prompts with questions but the human decides how deep to go. The Refinement Log in the Feature Spec serves as a record that the spec was stress-tested.

---

## Round 1: Assumptions

**Goal:** Surface hidden assumptions that, if wrong, would invalidate the spec.

**Prompt pattern:**
> "This spec assumes [X]. What happens if [X] is not true?"

**Examples of good challenges:**
- "This assumes tasks always have exactly one assignee. What if a task is unassigned?"
- "This assumes the API response fits in a single page. What if there are 10,000 results?"
- "This assumes users have already authenticated. What's the behavior for anonymous users?"

**Process:**
1. Read each requirement and identify what it takes for granted
2. List at least 3 assumptions
3. For each, ask: "What happens if this assumption is wrong?"
4. Record the challenge and resolution in the Refinement Log

**Done when:** At least 3 assumptions have been explicitly challenged and resolved.

---

## Round 2: Edge Cases

**Goal:** Find inputs, states, or sequences that break the happy path.

**Prompt pattern:**
> "What happens when [boundary condition]?"

**Examples of good challenges:**
- "What happens when the due date is in the past?"
- "What happens when two users edit the same task simultaneously?"
- "What happens when the network drops mid-save?"
- "What if the input contains emoji, RTL text, or 10,000 characters?"

**Process:**
1. Reference `retrospectives/edge-case-library.md` for patterns from past failures
2. For each requirement, identify at least one edge case
3. Verify each edge case maps to an acceptance criterion
4. Record in the Refinement Log

**Done when:** At least 3 edge cases have been explicitly addressed with acceptance criteria or out-of-scope decisions.

---

## Round 3: Scope Boundaries

**Goal:** Confirm what's out of scope by probing adjacent features.

**Prompt pattern:**
> "A user might also expect [adjacent feature]. Is that in or out?"

**Examples of good challenges:**
- "If we add due dates, users will expect recurring due dates. In or out?"
- "If we add a date picker, users will expect timezone support. In or out?"
- "If we show overdue indicators, users will expect notification emails. In or out?"

**Process:**
1. For each in-scope feature, brainstorm 2-3 adjacent features
2. Explicitly confirm each as in or out of scope with rationale
3. Update the Out of Scope section with any newly identified exclusions
4. Record in the Refinement Log

**Done when:** Out of Scope section has been reviewed and expanded via boundary probing.

---

## Round 4: Architecture Review

**Goal:** Surface architectural implications before decomposition begins — new services, API changes, dependencies, scalability risks, breaking changes, and performance impacts.

**Prompt pattern:**
> "This feature implies [architectural change]. What is the impact on [system concern]?"

**Examples of good challenges:**
- "This feature requires a new background job queue. What infrastructure changes are needed and who operates it?"
- "This adds a new foreign key relationship between orders and shipments. What happens to query performance at 10x current volume?"
- "This introduces a dependency on Service X. What happens when Service X is down or slow?"
- "This changes the API response shape for /tasks. Is this a breaking change for existing clients?"

**Process:**
1. For each requirement, identify implied infrastructure, service, or API changes
2. List at least 2 architectural implications
3. For each, ask: "What is the impact on reliability, performance, or maintainability?"
4. Record the challenge and resolution in the Refinement Log

**Done when:** At least 2 architectural implications have been explicitly challenged and resolved (or deferred to decomposition with rationale).

---

## Round 5: PII / Compliance Review

**Goal:** Identify data handling concerns including PII fields, data retention requirements, regulatory implications (GDPR/CCPA), audit logging needs, consent flows, and data access controls.

**Prompt pattern:**
> "This feature handles [data element]. What are the compliance implications for [concern area]?"

**Examples of good challenges:**
- "This stores user email addresses in a new table. What is the retention policy and how does a GDPR deletion request propagate here?"
- "This displays user activity history. Does this require explicit consent and is the data subject access request (DSAR) flow updated?"
- "This logs request payloads for debugging. Could those payloads contain PII that must be masked or excluded?"
- "This introduces a new admin endpoint that returns user data. What access controls and audit logging are required?"

**Process:**
1. For each requirement, identify data elements that are created, stored, transmitted, or displayed
2. Classify each data element: PII, sensitive, internal, or public
3. For any PII or sensitive data, ask: "What are the retention, access, audit, and deletion requirements?"
4. If no PII or sensitive data is involved, record an explicit N/A entry with rationale
5. Record the challenge and resolution in the Refinement Log

**Done when:** At least 1 entry exists — either PII/sensitive data with handling requirements documented, or an explicit N/A with rationale confirming no PII is involved.

---

## Round 6: UX & Interaction Review

**Goal:** Surface interaction design gaps, accessibility requirements, and visual consistency concerns before decomposition — when design changes are cheap.

**Prompt pattern:**
> "This feature involves [UI element]. What happens in [state/context]?"

**Examples of good challenges:**
- "This feature adds a task list. What does the user see when the list is empty? When it's loading? When a network error occurs?"
- "This date picker needs to work on mobile. Is the native date picker acceptable or do we need a custom component?"
- "This form has validation errors. Can a keyboard-only user reach and understand every error message?"
- "This feature introduces a new card component. The design system already has a card — can we reuse it or does this need a new variant?"

**Process:**
1. For each UI-facing requirement, identify interaction states (loading, empty, error, success)
2. Check responsive behavior: is mobile/tablet support needed or is desktop-only acceptable?
3. Verify accessibility baseline: keyboard navigation, screen reader labels, color contrast
4. Check visual consistency: does this reuse existing design system patterns or introduce new ones?
5. Record in the Refinement Log

**Done when:** At least 2 UX/interaction concerns have been explicitly addressed — or an explicit N/A with rationale for non-UI features.

---

## Readiness Gate

After all 6 rounds, verify the Readiness Checklist in the Feature Spec:

- [ ] All High-confidence requirements have acceptance criteria
- [ ] No unresolved conflicts remain
- [ ] Open questions are non-blocking or have owners
- [ ] At least 3 assumptions explicitly challenged and resolved
- [ ] At least 3 edge cases explicitly addressed
- [ ] Out of Scope section reviewed via scope boundary probe
- [ ] At least 2 architectural implications reviewed
- [ ] PII and sensitive data elements identified with handling requirements (or explicit N/A)
- [ ] At least 2 UX/interaction concerns reviewed (or explicit N/A for non-UI features)

The spec is ready for Architect Decomposition only when all checklist items pass.
