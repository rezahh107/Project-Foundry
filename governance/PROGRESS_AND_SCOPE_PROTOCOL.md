# Progress and Scope Control Protocol

## Purpose

Prevent the current task from replacing the complete project objective and prevent progress from being overstated.

## Always-visible hierarchy

```text
North Star → Program → Work Package → Task → Current operation
```

Every active state must carry this context path.

## Canonical carriers

- Complete program: `planning/execution-program.v1.json`
- Active scope: `planning/scope-baseline.v1.json`
- Current progress: `planning/current-state.v1.json`
- Owner projection: `planning/NEXT_WORK.md`

## Scope Gate

Before work begins:

1. identify the exact task;
2. confirm it belongs to the active scope baseline;
3. confirm dependencies;
4. list explicit exclusions;
5. reject silent scope expansion;
6. create a versioned scope change when necessary.

## Progress Gate

Use distinct lifecycle states. `complete` is valid only after exact current-main verification with evidence.

## Update rule

After every meaningful milestone, redirection, blocker, Merge, or invalidation, update canonical state and then update the rendered owner view.

## Owner view

The owner view must answer, simply:

- What is the full destination?
- Where are we now?
- What is inside the current scope?
- What is actually finished?
- What is the one next action?
