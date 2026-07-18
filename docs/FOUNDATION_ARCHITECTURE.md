# Foundation Architecture

## Control plane

The initial foundation is intentionally small but complete enough to preserve the whole project:

```text
Constitution
→ Progress and Scope
→ Decision Intelligence
→ Dogfooding
→ deterministic validation
```

## Why this precedes the Foundry Kernel

The Kernel is one future work package. The repository must first preserve the full program so that Kernel design cannot replace the product objective.

## Validation boundary

The current validator proves structural and cross-file consistency. It does not prove that every architectural recommendation is semantically optimal. Semantic decisions remain evidence-bound Decision Intelligence records.

## Current limitations

- Markdown projections are manually maintained.
- JSON Schema files are descriptive; the zero-dependency validator enforces the initial subset directly.
- Dogfooding uses manual checkpoints pending `DEC-002`.
- The foundation is not active on `main` until Merge and exact-main verification.
