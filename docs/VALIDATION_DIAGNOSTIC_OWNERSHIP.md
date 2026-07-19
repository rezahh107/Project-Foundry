# Validation Diagnostic Ownership

Each invalid-state class has one primary owner. Structural validation protects carrier safety. Semantic validation owns repository-specific lifecycle, provenance, dependency, Scope, and evidence meaning.

| Invariant | Primary owner | Public diagnostic |
|---|---|---|
| JSON syntax, types, required fields, shape, and `schema_version` | `STRUCTURAL_SCHEMA` | `PFV-101`, `PFV-110`–`PFV-116` |
| Canonical project and North Star identity | `CROSS_DOCUMENT_SEMANTICS` | `PFV-010`–`PFV-012` |
| Work Package ↔ Task closure | `CROSS_DOCUMENT_SEMANTICS` | `PFV-029`–`PFV-031` |
| Dependency graph and dependency satisfaction | `CROSS_DOCUMENT_SEMANTICS` | `PFV-032`, `PFV-033` |
| Submitted lifecycle edge and current-state agreement | `CROSS_DOCUMENT_SEMANTICS` | `PFV-034` |
| Submitted transition source versus trusted prior canonical status | `GIT_HISTORY_PROVENANCE` | `PFV-035` |
| Integration parent structure, supported merge method, branch-state preservation, and exact main-push boundary | `INTEGRATION_BOUNDARY` | `PFV-036` |
| First immutable appearance of every Task, with one exact repository-bootstrap exception | `TASK_ORIGIN_PROVENANCE` | `PFV-037` |
| Scope closure and next-task dispatch | `CROSS_DOCUMENT_SEMANTICS` | `PFV-044`–`PFV-046` |
| Current Task/state/transition receipt-carrier equality | `CROSS_DOCUMENT_SEMANTICS` | `PFV-082` |
| Completed and blocked progress closure | `CROSS_DOCUMENT_SEMANTICS` | `PFV-083` |
| Current branch-validation receipt shape and PR context | `BRANCH_PROVENANCE` | `PFV-084` |
| Current-main receipt shape and exact main-push context | `CURRENT_MAIN_PROVENANCE` | `PFV-085` |
| Required predecessor receipt, receipt digest, historical exact-SHA CI, and transitive evidence-chain validity | `TRANSITIVE_EVIDENCE_CHAIN` | `PFV-086` |
| Hosted Merge identity and Merge-receipt binding | `HOSTED_MERGE_TRUTH` | `PFV-087` |
| Decision Intelligence process rules | `CROSS_DOCUMENT_SEMANTICS` | `PFV-060`–`PFV-069` |
| Dogfooding authority and promotion rules | `CROSS_DOCUMENT_SEMANTICS` | `PFV-070`–`PFV-073` |
| Deterministic workflow projection | `WORKFLOW_PARITY_GATE` | `PFV-136` |

## Supported integration policy

Only a GitHub-hosted two-parent merge commit is supported. Its authoritative identities are:

```text
first parent  = previous main
second parent = exact merged PR Head
merge commit  = resulting main integration SHA
```

The canonical lifecycle files in the merge commit must be byte-identical to the second parent. Squash and rebase integrations are rejected with `PFV-036` because their one-parent Git shape cannot independently preserve and identify the merged PR lineage under this protocol.

The repository genesis merge is documented in `docs/BOOTSTRAP_COMPATIBILITY.md`. Its exception is bound to exact immutable identities and cannot be reused for later Tasks or integrations.

## Receipt v2 contract

Evidence-bearing transitions use one `git-history-attestation.v2` object. The receipt binds repository, exact ref, subject commit, transition edge, PR number, PR Head, integration commit, merge method, and the SHA-256 digest of its required predecessor receipt.

A status string is never evidence. The validator reconstructs the historical transition timeline, revalidates every predecessor receipt, and requires successful exact-SHA workflow evidence for historical evidence-bearing commits. A later green commit cannot launder an invalid earlier receipt.

## Hosted evidence boundary

`scripts/collect_hosted_provenance.py` reads public, read-only GitHub REST data without repository credentials. It writes a temporary evidence envelope under `RUNNER_TEMP`, outside the repository. Production hosted evidence is accepted only inside GitHub Actions, from that external runner-temporary path, with exact repository and schema identities. Test fixtures require `PROJECT_FOUNDRY_TEST_MODE=1`.

## Test layers

1. Structural tests assert `PFV-1xx` for carrier safety.
2. Semantic tests assert stable repository-domain diagnostics.
3. Real-Git tests create commits, branches, two-parent merges, multi-commit pushes, and receipt chains.
4. Hosted-evidence fixtures test PR identity, workflow conclusions, direct-push rejection, and supported merge boundaries.
