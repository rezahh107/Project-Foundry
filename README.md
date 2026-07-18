# Project Foundry

Project Foundry is a repository-native, self-hosting pipeline that turns raw ideas into governed project specifications, initialized repositories, execution programs, task queues, and just-in-time implementation prompts.

> **North Star — `PF-NORTH-STAR-001`:** preserve and execute the complete idea-to-implementation journey so that a current task, tool, model, or architectural detail can never replace or erase the project's full objective.

## What this repository must eventually do

```text
Raw idea
→ idea maturation
→ project specifications
→ repository identity proposal
→ repository binding and foundation
→ execution program
→ task decomposition
→ serial and parallel planning
→ just-in-time implementation prompt
→ implementation evidence
→ completion verification
→ continuity and next work
```

## Foundation operating model

This repository starts with four cross-cutting foundations:

1. **Project Constitution and AI Operating Profile** — who decides what, what counts as truth, and how the owner and models interact.
2. **Progress and Scope Control** — keeps the North Star, complete program, active scope, current task, and next action visible at the same time.
3. **Decision Intelligence** — requires important implementation choices to be researched, compared, weighted, and recorded before execution.
4. **Self-Hosting and Dogfooding** — observes the construction of Project Foundry itself and turns validated lessons into future pipelines, protocols, validators, fixtures, or UX rules.

## Source-of-truth order

Machine-readable state is canonical. Markdown is a human-oriented projection.

1. `governance/project-constitution.v1.json`
2. `planning/execution-program.v1.json`
3. `planning/scope-baseline.v1.json`
4. `planning/current-state.v1.json`
5. `decisions/decision-registry.v1.json`
6. `dogfooding/dogfooding-registry.v1.json`
7. Rendered views such as `PROJECT_CHARTER.md`, `SYSTEM_MAP.md`, and `planning/NEXT_WORK.md`

## Read this first

- Owner view: [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) → [`SYSTEM_MAP.md`](SYSTEM_MAP.md) → [`planning/NEXT_WORK.md`](planning/NEXT_WORK.md)
- Agent view: [`AGENTS.md`](AGENTS.md) and the canonical JSON files above
- Validation: `python scripts/validate_repository.py --root .`

## Current status

The first governed foundation is implemented as a candidate change. It is not `complete` until it is merged and revalidated on the exact current `main` commit.
