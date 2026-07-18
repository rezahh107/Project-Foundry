# ADR-0001: Repository-native canonical state with deterministic rendered views

- Status: Accepted for foundation candidate
- Decision ID: `DEC-001`
- North Star: `PF-NORTH-STAR-001`

## Context

Chat memory is not reliable project authority. Separate hand-maintained Markdown copies can silently drift from canonical state.

## Decision

Use versioned JSON as canonical state. Generate `PROJECT_CHARTER.md`, `SYSTEM_MAP.md`, and `planning/NEXT_WORK.md` through one deterministic renderer. Validate canonical structure before cross-file semantics and compare generated views byte-for-byte.

## Consequences

- North Star, Program, Scope, status, and next action cannot silently diverge in critical views.
- Agents must update JSON first and regenerate views.
- Structural schemas and adversarial mutation tests become part of the foundation contract.

## Reconsideration triggers

- Multiple concurrent writers require transaction semantics.
- State fragmentation becomes unmanageable.
- A database-backed runtime becomes necessary.
