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

## CI evidence boundary

The required PR job explicitly checks out the PR Head SHA, prints expected and actual SHAs, and fails closed on mismatch. Synthetic merge validation is not presented as exact-Head evidence.

## Current limitations

- The repository uses a bounded built-in validator for the checked-in schema vocabulary rather than a third-party JSON Schema runtime.
- Critical rendered views are generated; other explanatory Markdown remains manually maintained.
- Dogfooding remains manual structured checkpoints pending `DEC-002`.
- Independent PR-Inspector rereview is required on every repaired exact Head.
