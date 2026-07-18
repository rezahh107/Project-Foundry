# Progress and Scope Control Protocol

## Purpose

Prevent the current Task from replacing the complete objective and prevent implementation, branch validation, Merge or current-main verification from being overstated.

## Always-visible hierarchy

```text
North Star → Program → Work Package → Task → Current operation
```

## Canonical carriers

- Constitution: `governance/project-constitution.v1.json`
- Program: `planning/execution-program.v1.json`
- Active Scope: `planning/scope-baseline.v1.json`
- Current Progress: `planning/current-state.v1.json`

Critical views are deterministic projections of canonical state. Canonical state changes first; manual edits to generated views are invalid.

## Program and Scope Gate

1. Work Package and Task membership is bidirectionally closed.
2. The dependency graph is acyclic.
3. A dependency is satisfied only at `current_main_verified`.
4. Progressed Tasks require all dependencies to be satisfied.
5. Active-Scope Tasks belong to included Work Packages and carry the exact Scope reference.
6. `next_task_id` is the current unfinished Task or a dependency-ready in-Scope successor.

`PFV-031`–`PFV-033` and `PFV-044`–`PFV-046` own these invariants.

## Lifecycle Gate

The submitted lifecycle edge must be legal and internally consistent:

```text
last_transition.to == current_task_status == Task.status
```

The submitted `last_transition.from` is not historical authority. When Git history is available, the validator derives the actual prior state from first-parent canonical history. A mismatch is `PFV-035`.

## Git-history Evidence Gate

Evidence-bearing states use a non-self-referential receipt:

```text
subject commit S exists first
→ receipt/transition commit R records subject_sha = S
→ validator derives R and the actual prior state from Git history
```

The receipt must bind repository, ref, exact subject SHA, transition source and transition target.

### Branch validation

- The validation commit is the exact observed PR Head.
- The subject is its previous branch commit.
- The branch ref is explicit and cannot be `main`.
- PR base and synthetic merge identities cannot substitute for branch evidence.

### Merge

- The subject is a real commit on `main` ancestry immediately before the Merge receipt transition.
- Mergeability, PR Head and synthetic merge SHAs are not Merge evidence.

### Current-main verification

- The subject is a previously existing `merged` receipt commit.
- A later verification receipt records `merged → current_main_verified`.
- The verification commit never embeds its own SHA.
- Historical subject and receipt commits remain valid after later main commits while they remain ancestors of current `main`.

`PFV-084` owns branch/Merge receipt trust. `PFV-085` owns current-main attestation trust. `PFV-082` remains limited to equality of Task/state/transition evidence carriers.

## Workflow trust

The exact workflow keeps these identities separate:

- `github.sha`: validation commit;
- `github.event.before`: previous main commit for a main push;
- `github.event.pull_request.head.sha`: exact PR Head;
- `github.event.pull_request.base.sha`: reviewed PR base;
- `github.event.pull_request.merge_commit_sha`: synthetic merge identity, never completion evidence.

Full history is fetched because first-parent state and ancestry must be verified. Permissions remain read-only and checkout credentials do not persist.

## Progress collections

`completed_task_ids` exactly matches `current_main_verified` Tasks. `blocked_task_ids` exactly matches blocked Tasks. A Task cannot be simultaneously blocked and completed.

## Update rule

After each milestone or transition:

1. update canonical state;
2. regenerate views;
3. commit the subject state before authoring any receipt that refers to it;
4. run structural, semantic, Git-provenance, rendering, workflow and mutation validation;
5. publish only evidence-supported claims.
