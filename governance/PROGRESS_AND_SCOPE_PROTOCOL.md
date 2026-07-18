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

## Program Closure Gate

Before the Program is accepted:

1. every Work Package-listed Task must exist;
2. every listed Task must declare the containing Work Package;
3. every canonical Task must appear exactly once in its declared Work Package membership list;
4. duplicate Work Package and Task identities remain separately diagnosed;
5. no renderer may treat an orphaned Task as an acceptable hidden record.

`PFV-031` is the semantic owner for reverse Task-membership closure.

## Scope Gate

Before work begins:

1. identify the exact task;
2. confirm it belongs to the active Scope baseline;
3. confirm the Task's Work Package is included in the active Scope;
4. confirm every included Task carries exactly `<scope_id>@<scope_version>`;
5. confirm the active context Work Package matches the current Task and active Scope;
6. confirm dependencies;
7. list explicit exclusions;
8. reject silent Scope expansion;
9. create a versioned Scope change when necessary.

Tasks outside active Scope may retain `future_scope`. They must not be promoted into `included_task_ids` or active state without an explicit versioned Scope change.

`PFV-044` owns Scope Task/Work Package closure. `PFV-045` owns exact Scope-reference compatibility.

## Progress Gate

Implementation, branch validation, Merge, and current-main verification remain separate. Completion requires exact current-main evidence.

## Update rule

After every meaningful milestone, redirection, blocker, Merge, or invalidation:

1. update canonical state;
2. regenerate critical views;
3. run structural, semantic, parity, workflow, and test validation;
4. publish only evidence-supported lifecycle claims.
