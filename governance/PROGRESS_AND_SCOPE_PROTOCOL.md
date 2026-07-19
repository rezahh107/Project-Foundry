# Progress and Scope Control Protocol

## Purpose

Prevent the current task from replacing the complete objective and prevent progress, integration, Merge, or completion from being overstated.

## Always-visible hierarchy

```text
North Star → Program → Work Package → Task → Current operation
```

## Canonical carriers

- Constitution: `governance/project-constitution.v1.json`
- Complete Program: `planning/execution-program.v1.json`
- Active Scope: `planning/scope-baseline.v1.json`
- Current Progress: `planning/current-state.v1.json`

Critical Markdown views are deterministic projections. Canonical JSON changes first; manual edits to generated views are invalid.

## Program and Scope gates

1. Work Package and Task membership is bidirectionally closed.
2. The dependency graph is acyclic.
3. A dependency is satisfied only at `current_main_verified` with a valid transitive evidence chain.
4. Every included Task belongs to an included Work Package and carries the exact active Scope reference.
5. `next_task_id` must be in Scope and dependency-ready.
6. Scope changes require an explicit versioned rebaseline.

## Lifecycle

```text
implementation_submitted
→ validation_pending
→ validated_on_branch
→ merge_pending
→ actual hosted two-parent integration commit
→ merged
→ current_main_verified
```

Implementation submission, branch validation, merge readiness, actual integration, Merge receipt, and current-main verification are separate facts.

## Branch-validation gate

1. The exact PR Head carries the branch-validation receipt.
2. The receipt binds PR number, non-main branch ref, repository, subject SHA, and transition.
3. A historical branch receipt requires successful exact-SHA PR CI.
4. `merge_pending` must transitively prove the preceding branch receipt.
5. A multi-commit push cannot hide an invalid or untested branch receipt.

## Integration gate

1. Only a GitHub-hosted two-parent merge commit is supported.
2. Parent 1 is previous `main`; parent 2 is the exact merged PR Head.
3. The integration commit must preserve canonical lifecycle state from parent 2.
4. Parent 2 must be at `merge_pending` and have successful exact-SHA PR CI.
5. Hosted evidence must bind the exact PR, base `main`, PR Head, and resulting integration SHA.
6. The integration commit's own push-to-main workflow must pass.
7. Squash and rebase integrations fail closed with `PFV-036`.
8. Synthetic mergeability commits and direct pushes are not Merge evidence.

## Merge-receipt gate

1. A `merged` receipt is created after the integration commit.
2. It binds the integration SHA, PR identity, merge method, and predecessor branch-receipt digest.
3. It requires successful CI for the branch receipt, latest PR Head, and integration commit.
4. Hosted GitHub evidence must report the PR as actually merged through that exact integration SHA.
5. An ordinary main commit cannot self-declare itself as a Merge.

## Current-main gate

1. A `current_main_verified` receipt binds the valid Merge receipt and its digest.
2. The Merge receipt commit must have successful exact-SHA push CI.
3. Historical receipt chains are immutable and revalidated transitively.
4. Later unrelated main commits preserve valid history; they do not rewrite completed Tasks to newer SHAs.
5. A later green commit cannot conceal a malformed or failed predecessor.

## Evidence authority

A status string, model statement, arbitrary environment value, synthetic merge SHA, or mutable PR description is not evidence. Git history establishes commit topology; temporary read-only hosted evidence establishes PR Merge and workflow truth; canonical receipts bind the two.

## Diagnostics

- `PFV-034`: submitted current status or edge disagreement.
- `PFV-035`: submitted transition source disagrees with trusted prior canonical status.
- `PFV-036`: unsupported or inconsistent integration boundary.
- `PFV-082`: current Task/state/transition receipt carriers disagree.
- `PFV-084`: current branch receipt is malformed or untrusted.
- `PFV-085`: current-main receipt is malformed, self-referential, or lacks exact push context.
- `PFV-086`: predecessor receipt or historical exact-SHA CI chain is incomplete or invalid.
- `PFV-087`: Merge receipt is not bound to an actual hosted Merge.

## Update rule

After every milestone, blocker, validation, integration, Merge receipt, or current-main verification:

1. update canonical state;
2. regenerate critical views;
3. run structural, semantic, Git-provenance, hosted-evidence, parity, focused, full-suite, and compile validation;
4. publish only evidence-supported lifecycle claims.
