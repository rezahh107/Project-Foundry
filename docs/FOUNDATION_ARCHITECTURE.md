# Foundation Architecture

## Validation pipeline

```text
required-file gate
→ strict JSON and structural-schema validation
→ cross-document semantic validation
→ Git graph and lifecycle-history reconstruction
→ hosted Merge and exact-SHA CI evidence validation
→ transitive receipt-chain validation
→ deterministic rendered-view parity
→ deterministic workflow parity
```

Malformed canonical input never reaches semantic logic. Critical views remain generated from canonical JSON and compared byte-for-byte.

## Lifecycle provenance model

The system separates four identities:

```text
validation commit
verified subject commit
integration commit
hosted repository event
```

No commit contains or predicts its own SHA. Evidence points to an already existing immutable subject. Later commits preserve historical receipts rather than rewriting them.

## Branch validation

A `validated_on_branch` receipt is created on the exact PR Head and binds the PR number, branch ref, transition subject, and repository. Once historical, the exact receipt commit must have a successful `pull_request` workflow run. `merge_pending` is valid only when that predecessor receipt remains valid; a multi-commit latest-Head push cannot hide an untested receipt.

## Integration boundary

Only GitHub's two-parent merge-commit method is supported:

```text
parent 1: previous main
parent 2: exact merged PR Head
result:   actual integration commit on main
```

The validator inserts the second-parent branch lifecycle into the main timeline. This prevents old-main first-parent state from replacing the branch's `merge_pending` state.

The integration commit itself must pass push-to-main validation. It must preserve canonical lifecycle files from parent 2, integrate the active Task at `merge_pending`, match hosted PR Merge truth, and reference a PR Head with successful exact-SHA PR validation. Squash and rebase integrations are explicitly rejected with `PFV-036`.

## Merge and current-main receipts

A `merged` receipt binds the actual integration commit, exact merged PR number and Head, predecessor branch-receipt digest, successful PR-Head CI, integration-commit push CI, and hosted confirmation that the PR was merged through that exact SHA.

A `current_main_verified` receipt binds the valid Merge receipt and its digest. The Merge receipt commit must have successful push CI. Historical current-main receipts remain valid after unrelated later main commits while the complete immutable chain remains in ancestry.

## Hosted evidence collector

The workflow runs `scripts/collect_hosted_provenance.py` before repository validation. It uses anonymous read-only GitHub REST calls and no `GITHUB_TOKEN` or secret. Output is stored below `RUNNER_TEMP`, outside the repository, and contains only exact merge associations and exact-SHA workflow conclusions needed by validation.

## Program, Scope, dependency, and dispatch closure

Existing gates remain unchanged:

```text
Work Package ↔ Task membership is closed
active Scope Task → included Work Package + exact Scope reference
dependency graph → acyclic
progressed Task → every dependency is current_main_verified
next Task → active Scope + dependency-ready
```

A dependency unlocks only after the complete branch-validation → integration → Merge receipt → current-main receipt chain is valid.

## Current limitations

- Only two-parent GitHub merge commits are supported; squash and rebase are fail-closed.
- The repository uses a bounded built-in validator for its checked-in schema vocabulary.
- Dogfooding remains manual structured checkpoints pending `DEC-002`.
- A fresh PR-Inspector rereview is required on every repaired exact Head.
