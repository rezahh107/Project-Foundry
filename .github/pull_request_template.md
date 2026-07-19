## North Star and scope

- North Star: `PF-NORTH-STAR-001`
- Program:
- Work package:
- Task:
- Scope baseline:

## What changed


## Why this method

- Decision record:
- Alternatives considered:
- AI operability impact:
- Owner usability impact:

## Evidence and validation

- [ ] `python scripts/render_views.py --check --root .`
- [ ] `python scripts/validate_repository.py --root .`
- [ ] `python -m unittest discover -s tests -v`
- [ ] Canonical documents pass structural schemas before semantic checks
- [ ] Generated views exactly match canonical state
- [ ] No completion claim exceeds evidence
- [ ] Exact triggering SHA is checked out and asserted in CI
- [ ] All workflow actions use verified full commit pins
- [ ] Checkout credential persistence is disabled

## Dogfooding checkpoint

- Observation created or `not_applicable` with reason:
- Candidate lesson:
- Promotion requested: yes / no

## Protected actions

- [ ] No Merge, Release, Deployment, destructive action, secret change, or repository-policy change is performed without explicit owner authority.
