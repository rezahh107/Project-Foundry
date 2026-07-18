# Validation Diagnostic Ownership

Each invalid-state class has one primary diagnostic owner. Structural validation establishes safe data shape; cross-document semantics owns repository-specific graph, lifecycle, dispatch, and evidence meaning.

| Invariant | Primary owner | Public diagnostic |
|---|---|---|
| JSON syntax, types, required fields, shape and `schema_version` | `STRUCTURAL_SCHEMA` | `PFV-101`, `PFV-110`–`PFV-116` |
| Canonical project and North Star identity | `CROSS_DOCUMENT_SEMANTICS` | `PFV-010`–`PFV-012` |
| Work Package ↔ Task closure | `CROSS_DOCUMENT_SEMANTICS` | `PFV-029`–`PFV-031` |
| Dependency graph acyclicity | `CROSS_DOCUMENT_SEMANTICS` | `PFV-032` |
| Dependency satisfaction before progression | `CROSS_DOCUMENT_SEMANTICS` | `PFV-033` |
| Lifecycle transition legality and status agreement | `CROSS_DOCUMENT_SEMANTICS` | `PFV-034` |
| Scope Task → included Work Package and exact Scope reference | `CROSS_DOCUMENT_SEMANTICS` | `PFV-044`, `PFV-045` |
| Next-task dispatch eligibility | `CROSS_DOCUMENT_SEMANTICS` | `PFV-046` |
| Current-main evidence validity and agreement | `CROSS_DOCUMENT_SEMANTICS` | `PFV-082` |
| Completed and blocked progress closure | `CROSS_DOCUMENT_SEMANTICS` | `PFV-083` |
| Decision Intelligence process rules | `CROSS_DOCUMENT_SEMANTICS` | `PFV-060`–`PFV-069` |
| Dogfooding authority and promotion rules | `CROSS_DOCUMENT_SEMANTICS` | `PFV-070`–`PFV-073` |
| Deterministic workflow projection | workflow parity gate | `PFV-136` |

A dependency is satisfied only at `current_main_verified`. `blocked`, `invalidated`, and `superseded` are explicitly unsatisfied.

## Structured evidence contract

Task, current-state, and transition `evidence_refs` may structurally carry objects or legacy strings. Semantic validation rejects strings for evidence-bearing lifecycle states. A current-main record must contain exactly:

```json
{
  "verification_type": "current_main",
  "repository": "rezahh107/Project-Foundry",
  "ref": "refs/heads/main",
  "commit_sha": "<40 lowercase hexadecimal characters>"
}
```

The commit must equal trusted `PROJECT_FOUNDRY_CURRENT_MAIN_SHA`. An arbitrary string, PR Head, synthetic merge SHA, or stale `main` SHA is not current-main evidence.

## Test layers

1. Structural tests assert `PFV-1xx` for syntax and carrier safety.
2. Semantic end-to-end tests invoke the complete validator and real CLI and assert stable `PFV-0xx` diagnostics without traceback.
3. Direct semantic tests are defensive coverage only, not public CLI contracts.
