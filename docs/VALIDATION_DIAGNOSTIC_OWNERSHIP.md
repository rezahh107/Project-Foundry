# Validation Diagnostic Ownership

Each invalid-state class has one primary diagnostic owner. The complete validator runs the structural gate first and enters semantic validation only when every canonical document is structurally safe.

| Invariant | Primary owner | Public diagnostic | Rationale |
|---|---|---|---|
| JSON syntax, non-object roots, finite numbers | `STRUCTURAL_SCHEMA` | `PFV-101`, `PFV-110` | Semantic code cannot safely consume malformed JSON. |
| Required properties and allowed object shape | `STRUCTURAL_SCHEMA` | `PFV-111`, `PFV-115` | Establishes safe access and deterministic carrier shape. |
| `schema_version` identity | `STRUCTURAL_SCHEMA` | `PFV-112` | Selects the schema contract itself. |
| Canonical `project_id` | `CROSS_DOCUMENT_SEMANTICS` | `PFV-010` | Repository-specific identity, not generic JSON shape. |
| Canonical North Star identity | `CROSS_DOCUMENT_SEMANTICS` | `PFV-011` | Repository authority invariant. |
| Cross-document `north_star_id` binding | `CROSS_DOCUMENT_SEMANTICS` | `PFV-012` | Agreement across canonical carriers. |
| Execution-task status vocabulary | `CROSS_DOCUMENT_SEMANTICS` | `PFV-023` | Domain lifecycle vocabulary for task records. |
| Current-state/transition carrier status shape | `STRUCTURAL_SCHEMA` | `PFV-112` | These fields gate safe interpretation of the current lifecycle carrier. |
| Decision status vocabulary | `CROSS_DOCUMENT_SEMANTICS` | `PFV-061` | Status-dependent Decision Intelligence rules depend on this domain value. |
| Non-empty task acceptance criteria | `CROSS_DOCUMENT_SEMANTICS` | `PFV-026` | Readiness/completeness rule rather than array shape. |
| Reference existence and linkage consistency | `CROSS_DOCUMENT_SEMANTICS` | `PFV-020`–`PFV-059` | Requires multiple canonical documents. |
| Lifecycle/evidence sufficiency | `CROSS_DOCUMENT_SEMANTICS` | `PFV-027`, `PFV-028`, `PFV-057` | Meaning depends on state and evidence together. |
| Decision Intelligence process rules | `CROSS_DOCUMENT_SEMANTICS` | `PFV-060`–`PFV-069` | Status-dependent domain process. |
| Dogfooding authority and promotion rules | `CROSS_DOCUMENT_SEMANTICS` | `PFV-070`–`PFV-073` | Cross-record authority/evidence behavior. |
| Deterministic workflow projection | `STRUCTURAL_SCHEMA` equivalent workflow gate | `PFV-136` | Exact-byte workflow contract, not regex evidence. |

## Test layers

1. **Structural tests** mutate syntax, type, required fields, shape, schema versions, and structurally owned current-state status fields. They invoke the complete validator and expect `PFV-1xx`.
2. **Semantic end-to-end tests** keep documents structurally valid, invoke the complete validator and CLI, and expect domain `PFV-0xx`.
3. **Direct semantic unit tests** are reserved for defensive code paths that cannot be reached through structurally valid canonical documents. They must be labelled as defensive coverage and are not public CLI contracts.

Changing ownership requires a coordinated schema, semantic, test and documentation change. Validation order must not determine the public diagnostic for an invariant.
