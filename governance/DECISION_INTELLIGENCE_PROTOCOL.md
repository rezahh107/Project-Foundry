# Decision Intelligence Protocol

## Purpose

Select implementation methods through explicit evidence, constraints, comparison, and learning rather than first-idea bias.

## Decision classes

### `D1_LIGHTWEIGHT`

Small, low-cost, reversible. Use a short comparison and record the rationale.

### `D2_STRUCTURED`

Meaningful but reversible. Identify multiple feasible options, criteria, risks, and a bounded validation plan.

### `D3_HIGH_CONSEQUENCE`

Expensive, foundational, difficult to reverse, or safety-sensitive. Use current authoritative research, hard constraints, weighted comparison, uncertainty analysis, and a prototype or spike when needed.

## Required pipeline

```text
Decision question
→ classify
→ discover feasible options
→ apply hard constraints
→ define criteria and weights
→ compare evidence and uncertainty
→ run bounded spike if necessary
→ recommend
→ authorize
→ implement
→ measure outcome
→ reconsider when triggers occur
```

## Mandatory criteria

For `D2_STRUCTURED` and `D3_HIGH_CONSEQUENCE`, explicitly evaluate:

- `technical_fitness`;
- `ai_operability`;
- `owner_usability`;
- `transparency`;
- `evidence_and_validation_quality`;
- `maintainability`;
- `reversibility`;
- `implementation_cost`;
- `future_automation_fit`;
- `security_and_safety_fit` with profile-appropriate weight.

Weights are decision-specific. Hard constraints are applied before scoring.

## AI operability

A method scores well when an AI technical operator can:

- understand its state without hidden context;
- execute it with available tools;
- validate results deterministically;
- recover from failure;
- continue in a new session;
- render a simple owner explanation;
- produce a precise downstream implementation contract.

## Research rules

Use current primary or authoritative sources for unstable, specialized, or high-impact decisions. Separate facts, assumptions, inferences, and recommendations. Do not fabricate alternatives or evidence.

## Decision record

Every D2/D3 decision must be registered in `decisions/decision-registry.v1.json`. Architectural decisions also receive an ADR.
