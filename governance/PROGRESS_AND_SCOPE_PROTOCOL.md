# Progress and Scope Control Protocol

## Purpose

Prevent the current task from replacing the complete objective and prevent progress or completion from being overstated.

## Always-visible hierarchy

```text
North Star → Program → Work Package → Task → Current operation
```

## Canonical carriers

- Constitution: `governance/project-constitution.v1.json`
- Complete Program: `planning/execution-program.v1.json`
- Active Scope: `planning/scope-baseline.v1.json`
- Current Progress: `planning/current-state.v1.json`

## Deterministic projections

`PROJECT_CHARTER.md`, `SYSTEM_MAP.md`, and `planning/NEXT_WORK.md` are generated from canonical state. Canonical state changes first; manual edits to generated views are invalid.

## Program Closure Gate

1. Every Work Package-listed Task exists and declares the containing Work Package.
2. Every canonical Task appears exactly once in its declared Work Package.
3. The dependency graph is acyclic.
4. A dependency is satisfied only at `current_main_verified`.
5. `eligible`, `active`, `implementation_submitted`, and later execution states require satisfied dependencies.
6. `blocked`, `invalidated`, and `superseded` dependencies are unsatisfied, not successful.

`PFV-031`, `PFV-032`, and `PFV-033` own these invariants.

## Scope and Dispatch Gate

1. Every included Task belongs to an included Work Package.
2. Every included Task carries the exact active Scope reference.
3. Active context agrees with the current Task and active Scope.
4. `next_task_id` is in active Scope and is either the current unfinished Task or a dependency-ready successor.
5. A future Task cannot become next without a versioned Scope change.
6. `NEXT_WORK.md` renders next Task ID, title, and the separate free-form action.

`PFV-044`, `PFV-045`, and `PFV-046` own these invariants.

## Progress and Evidence Gate

1. Lifecycle transitions follow the explicit allowed graph.
2. `last_transition.to == current_task_status == Task.status`.
3. Evidence-bearing states require matching Task, state, and transition evidence.
4. `current_main_verified` requires a structured record bound to this repository, `refs/heads/main`, and the trusted exact current-main SHA.
5. `completed_task_ids` exactly matches `current_main_verified` Tasks.
6. `blocked_task_ids` exactly matches blocked Tasks; each blocked Task has blocker information.
7. A Task cannot be both completed and blocked.
8. `complete` is not a substitute for `current_main_verified`.

`PFV-034`, `PFV-082`, and `PFV-083` own these invariants.

## Update rule

After every milestone, redirection, blocker, Merge, or invalidation:

1. update canonical state;
2. regenerate critical views;
3. run structural, semantic, parity, workflow, focused mutation, full-suite, and compile validation;
4. publish only evidence-supported lifecycle claims.
