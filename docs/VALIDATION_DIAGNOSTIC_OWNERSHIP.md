# Validation Diagnostic Ownership

Each invalid-state class has one primary diagnostic owner. Structural validation establishes safe carrier shape; cross-document and Git-history semantics own repository identity, lifecycle provenance, dispatch, and evidence truth.

| Invariant | Primary owner | Public diagnostic |
|---|---|---|
| JSON syntax, types, required fields, object shape and `schema_version` | `STRUCTURAL_SCHEMA` | `PFV-101`, `PFV-110`–`PFV-116` |
| Canonical project and North Star identity | `CROSS_DOCUMENT_SEMANTICS` | `PFV-010`–`PFV-012` |
| Work Package ↔ Task closure | `CROSS_DOCUMENT_SEMANTICS` | `PFV-029`–`PFV-031` |
| Dependency graph and dependency readiness | `CROSS_DOCUMENT_SEMANTICS` | `PFV-032`, `PFV-033` |
| Submitted status/transition internal agreement | `CROSS_DOCUMENT_SEMANTICS` | `PFV-034` |
| Submitted transition versus trusted first-parent prior state | `GIT_HISTORY_SEMANTICS` | `PFV-035` |
| Scope and next-task dispatch closure | `CROSS_DOCUMENT_SEMANTICS` | `PFV-044`–`PFV-046` |
| Task/state/transition evidence carrier equality | `CROSS_DOCUMENT_SEMANTICS` | `PFV-082` |
| Completed and blocked progress closure | `CROSS_DOCUMENT_SEMANTICS` | `PFV-083` |
| Branch-validation or merge evidence malformed, self-asserted or outside trusted Git context | `GIT_HISTORY_SEMANTICS` | `PFV-084` |
| Current-main attestation self-referential, non-ancestral or outside trusted main context | `GIT_HISTORY_SEMANTICS` | `PFV-085` |
| Decision Intelligence rules | `CROSS_DOCUMENT_SEMANTICS` | `PFV-060`–`PFV-069` |
| Dogfooding authority and promotion | `CROSS_DOCUMENT_SEMANTICS` | `PFV-070`–`PFV-073` |
| Deterministic workflow projection | workflow parity gate | `PFV-136` |

## Non-self-referential receipt

Evidence-bearing lifecycle states use one structured `git_history_attestation` receipt containing:

```text
verification_type
subject_kind
repository
ref
subject_sha
transition_from
transition_to
```

`subject_sha` identifies the immutable commit immediately preceding the receipt transition. It must never equal the commit that contains the receipt. The validator derives the receipt/transition commit and the actual prior status from first-parent Git history.

## Trust boundary

- `git rev-parse HEAD` and `github.sha` identify the **validation commit**.
- `github.event.pull_request.head.sha` identifies the exact checked-out PR Head; it is not current-main evidence.
- `github.event.pull_request.base.sha` identifies the reviewed PR base; it is not post-Merge verification evidence.
- `github.event.pull_request.merge_commit_sha` is treated as synthetic and never qualifies as a real Merge or current-main subject.
- `github.event.before` is trusted only as the previous main commit for a push to `refs/heads/main`.
- `subject_sha` must exist, be reachable from the validated history, match the transition predecessor, and remain on the required branch ancestry.

## Lifecycle-specific meaning

- `validated_on_branch`: the receipt commit is the exact observed PR Head; the subject is its previous branch commit and the ref is the exact PR branch.
- `merged`: the subject is a real commit on main ancestry immediately before the Merge receipt transition.
- `current_main_verified`: the subject is the previously existing `merged` receipt commit; a later verification receipt commit records the transition without embedding its own SHA.
- Later main commits preserve historical evidence while the subject and transition remain ancestors of current `main`.

Structural shape alone never proves Git provenance. An arbitrary environment variable, free-form model assertion, PR Head or synthetic merge SHA is insufficient.
