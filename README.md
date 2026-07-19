# Project Foundry

Project Foundry is a repository-native, self-hosting pipeline that turns raw ideas into governed project specifications, prepared repositories, execution programs, task queues, and just-in-time implementation prompts.

> **North Star — `PF-NORTH-STAR-001`:** preserve the complete idea-to-implementation journey so that a current task, tool, model, or architectural detail can never replace or erase the project's full objective.

## Canonical state and generated views

Machine-readable JSON is canonical. These critical Markdown views are deterministic projections and must never be edited manually:

- `PROJECT_CHARTER.md`
- `SYSTEM_MAP.md`
- `planning/NEXT_WORK.md`

Regenerate and verify them with:

```bash
python scripts/render_views.py --write --root .
python scripts/render_views.py --check --root .
```

The repository validator first checks every canonical JSON document against its declared schema. Only structurally valid documents reach cross-file semantic checks.

## Validation

```bash
python scripts/render_views.py --check --root .
python scripts/validate_repository.py --root .
python -m unittest discover -s tests -v
```

The validator also enforces exact rendered-view parity, exact-Head CI identity, immutable action pins, disabled checkout credential persistence, lifecycle separation, Decision Intelligence requirements, and controlled Dogfooding promotion.

## Current lifecycle truth

The foundation remains a PR candidate. It is not complete until it is merged and the exact current `main` commit is revalidated with evidence.
