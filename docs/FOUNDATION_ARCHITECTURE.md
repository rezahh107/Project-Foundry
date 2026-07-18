# Foundation Architecture

## Validation pipeline

```text
Required-file gate
→ strict JSON parsing
→ declared-schema structural validation
→ cross-document semantic validation
→ deterministic rendered-view parity
→ workflow identity and supply-chain validation
```

Malformed canonical input never reaches semantic logic. Critical owner views are generated from canonical JSON and compared byte-for-byte.

## Program, Scope, dependency, and dispatch closure

Semantic validation establishes these preconditions before rendering:

```text
Work Package ↔ Task membership is bidirectionally closed
active Scope Task → included Work Package + exact Scope reference
Task dependency graph → acyclic
progressed Task → every dependency is current_main_verified
next_task_id → active Scope + dependency-ready dispatch target
```

`planning/NEXT_WORK.md` renders the canonical next Task ID and title separately from free-form `next_action`; prose cannot replace dispatch identity.

## Lifecycle and evidence boundary

The lifecycle uses an explicit transition graph. `last_transition.to`, `current_task_status`, and canonical Task status must agree. Evidence-bearing states require matching Task/state/transition records. `current_main_verified` additionally requires repository-bound, `refs/heads/main`-bound, 40-character SHA evidence equal to the trusted current-main SHA supplied by the execution environment.

Completed and blocked collections are bidirectionally closed against Task statuses. Blocked Tasks require explicit blocker information and cannot simultaneously be completed.

## CI evidence boundary

The PR job checks out the exact PR Head, asserts expected and actual SHAs, and supplies the PR base SHA as trusted current-main identity. Action pins, read-only permissions, and disabled checkout credential persistence remain deterministic workflow invariants.

## Current limitations

- The repository uses a bounded built-in validator for the checked-in schema vocabulary.
- Critical rendered views are generated; other explanatory Markdown remains manually maintained.
- Dogfooding remains manual structured checkpoints pending `DEC-002`.
- Independent PR-Inspector rereview is required on every repaired exact Head.
