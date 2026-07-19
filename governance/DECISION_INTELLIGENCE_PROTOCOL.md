# Decision Intelligence Protocol

## Purpose

Select consequential implementation methods through evidence, constraints, comparison, and learning rather than first-idea bias.

## Decision classes

- `D1_LIGHTWEIGHT`: small, low-cost, reversible.
- `D2_STRUCTURED`: meaningful but reversible.
- `D3_HIGH_CONSEQUENCE`: foundational, expensive, difficult to reverse, or safety-sensitive.

## Required pipeline

```text
Decision question
→ classify
→ discover feasible options
→ apply hard constraints
→ define criteria and weights
→ compare evidence and uncertainty
→ run bounded spike when necessary
→ recommend
→ authorize
→ implement
→ measure outcome
```

For D2 and D3 decisions, `ai_operability` and `owner_usability` are mandatory criteria. Preserve `DEC-002` as `research_required` until its alternatives are actually researched and compared.
