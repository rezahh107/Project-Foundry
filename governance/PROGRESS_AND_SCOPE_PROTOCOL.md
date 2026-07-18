# Progress and Scope Control Protocol

## Purpose

Prevent the current task from replacing the complete project objective and prevent progress from being overstated.

## Always-visible hierarchy

```text
North Star → Program → Work Package → Task → Current operation
```

Every active state must carry this context path.

## Canonical carriers

- Constitution: `governance/project-constitution.v1.json`
- Complete program: `planning/execution-program.v1.json`
- Active Scope: `planning/scope-baseline.v1.json`
- Current Progress: `planning/current-state.v1.json`

## Deterministic projections

These critical views are generated from canonical state through `scripts/render_views.py`:

- `PROJECT_CHARTER.md`
- `SYSTEM_MAP.md`
- `planning/NEXT_WORK.md`

Canonical state must be updated first. Manual edits to generated views are invalid. The validator compares expected and committed bytes and emits stable `PFV-120` through `PFV-122` diagnostics on drift.

## Scope Gate

Before work begins:

1. identify the exact task;
2. confirm it belongs to the active Scope baseline;
3. confirm dependencies;
4. list explicit exclusions;
5. reject silent Scope expansion;
6. create a versioned Scope change when necessary.

## Progress Gate

Implementation, branch validation, Merge, and current-main verification remain separate. Completion requires exact current-main evidence.

## Update rule

After every meaningful milestone, redirection, blocker, Merge, or invalidation:

1. update canonical state;
2. regenerate critical views;
3. run structural, semantic, parity, workflow, and test validation;
4. publish only evidence-supported lifecycle claims.
