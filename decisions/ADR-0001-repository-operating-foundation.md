# ADR-0001: Use repository-native canonical state with rendered human views

- Status: Accepted for foundation candidate
- Decision ID: `DEC-001`
- North Star: `PF-NORTH-STAR-001`

## Context

The owner may return after several days and forget the original objective. Models may also over-focus on the current technical subproblem. Chat memory is not a reliable project authority.

## Decision

Use versioned JSON files inside the repository as canonical state. Generate or maintain concise Markdown views for the owner and precise technical contracts for agents.

## Consequences

### Positive

- The North Star and full program remain discoverable.
- Progress and Scope can be validated across sessions.
- Owner and agent views can remain aligned.
- Repository evidence, not chat memory, becomes project truth.

### Negative

- Canonical and rendered files must be updated together.
- Validators and fixtures are required to prevent drift.

## Reconsideration triggers

- Canonical state becomes too fragmented to maintain.
- A database-backed runtime becomes necessary.
- Multiple concurrent writers require stronger transaction semantics.
