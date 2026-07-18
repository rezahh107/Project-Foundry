# Foundation Architecture

## Validation pipeline

```text
required-file gate
→ strict JSON and schema validation
→ cross-document Program/Scope/dependency semantics
→ real-Git lifecycle provenance
→ deterministic rendered-view parity
→ deterministic workflow parity
```

Malformed canonical input never reaches semantic logic. Evidence-bearing lifecycle claims cannot pass solely because a submitted JSON object is internally consistent.

## Program, Scope and dispatch closure

```text
Work Package ↔ Task membership is closed
active Scope Task → included Work Package + exact Scope reference
Task dependency graph → acyclic
progressed Task → dependencies are current_main_verified
next_task_id → active Scope + dependency-ready dispatch target
```

`planning/NEXT_WORK.md` renders the canonical next Task identity separately from free-form action prose.

## Git-history attestation architecture

The repository separates three identities:

```text
validation commit
→ exact commit currently checked out and validated

verified subject
→ previously existing immutable commit described by the receipt

trusted Git context
→ event/ref identities plus actual commit ancestry
```

The receipt commit never contains its own SHA. First-parent history supplies the actual prior canonical Task state and the transition commit. `subject_sha` must equal the previous immutable subject commit and remain reachable on the required ancestry.

A practical main sequence is:

```text
M  implementation/merge subject exists
V  merge receipt records subject M
W  current-main verification receipt records subject V
L  later main commits preserve V/W as historical ancestry
```

For a transition first observed at current `HEAD`, the workflow event must corroborate it:

- PR branch validation: checked-out `HEAD` equals exact PR Head and the branch ref is explicit.
- Main transition: checked-out `HEAD` is a push to `refs/heads/main` and `github.event.before` equals the receipt subject.
- PR base, PR Head and synthetic merge identities remain distinct and cannot be substituted for current-main provenance.

## Workflow trust boundary

The workflow checks out the exact triggering Head with full history (`fetch-depth: 0`) because ancestry and first-parent state comparison are required. Permissions remain `contents: read`, action versions remain full immutable pins, and checkout credentials do not persist.

## Real-Git tests

The integration suite creates temporary repositories and real commits, branches and `--no-ff` merges. It proves non-self-referential post-Merge verification, trusted prior-state comparison, branch and Merge receipt validation, historical evidence preservation and deterministic forward progress from `PF-001` to `PF-002`.

## Current limitations

- The repository uses a bounded built-in validator for its checked-in schema vocabulary.
- Critical rendered views are generated; explanatory Markdown remains manually maintained.
- Dogfooding remains manual structured checkpoints pending `DEC-002`.
- A fresh PR-Inspector rereview is required on every repaired exact Head.
