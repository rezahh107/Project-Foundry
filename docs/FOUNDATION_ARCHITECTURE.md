# Foundation Architecture

## Validation pipeline

```text
Required-file gate
→ strict JSON parsing
→ declared-schema structural validation
→ cross-file semantic validation
→ deterministic rendered-view parity
→ workflow identity and supply-chain validation
```

Malformed canonical input never reaches semantic business logic. Critical owner views are generated from canonical JSON through one renderer and compared byte-for-byte during validation.

## Program and Scope closure

Semantic validation establishes explicit graph-closure preconditions before rendering:

```text
every Work Package membership → known Task with matching declaration
every Task → exactly one membership in its declared Work Package

every active Scope Task → included Work Package
every active Scope Task → exact active Scope reference
active context Work Package → current Task declaration and active Scope
```

`SYSTEM_MAP.md` may iterate Work Package membership lists only because `PFV-031` prevents canonical Tasks from becoming orphaned. `planning/NEXT_WORK.md` may iterate `included_task_ids` only because `PFV-044` and `PFV-045` prevent cross-Work-Package Scope expansion and stale Scope references.

## CI evidence boundary

The required PR job explicitly checks out the PR Head SHA, prints expected and actual SHAs, and fails closed on mismatch. Synthetic merge validation is not presented as exact-Head evidence.

## Current limitations

- The repository uses a bounded built-in validator for the checked-in schema vocabulary rather than a third-party JSON Schema runtime.
- Critical rendered views are generated; other explanatory Markdown remains manually maintained.
- Dogfooding remains manual structured checkpoints pending `DEC-002`.
- Independent PR-Inspector rereview is required on every repaired exact Head.
