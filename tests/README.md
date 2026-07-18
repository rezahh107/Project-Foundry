# Validation and Mutation Test Corpus

The Foundation repair is verified through these groups:

- structural canonical-input mutations;
- renderer structural/reference/strict-JSON boundaries;
- cross-file semantic references and lifecycle rules;
- Decision Intelligence status-dependent invariants;
- Dogfooding promotion controls;
- deterministic workflow bypass mutations;
- direct, in-process CLI, and subprocess CLI boundaries.

Run the complete suite with:

```bash
python scripts/render_views.py --check --root .
python scripts/validate_repository.py --root .
python -m unittest discover -s tests -v
python -m compileall -q scripts tests
```

A GitHub Actions success is exact-Head evidence only when the workflow's expected and actual SHA values are identical.
