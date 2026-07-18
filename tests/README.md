# Validation and Mutation Test Corpus

The Foundation repair is verified through these groups:

- structural canonical-input mutations;
- renderer structural/reference/strict-JSON boundaries;
- cross-file semantic references and lifecycle rules;
- Decision Intelligence status-dependent invariants;
- Dogfooding promotion controls;
- deterministic workflow bypass mutations;
- direct, in-process CLI, and subprocess CLI boundaries.

Diagnostic ownership is normative in `docs/VALIDATION_DIAGNOSTIC_OWNERSHIP.md`.

## Layer contract

- Structural tests invoke the complete validator and assert `PFV-1xx` for syntax, types, required properties, object shape, schema-version identity, and structurally owned lifecycle-carrier fields.
- Semantic end-to-end tests use structurally valid documents, invoke the complete validator and CLI, and assert the exact `PFV-0xx` domain diagnostic with non-zero exit, no `PFV-199`, and no traceback.
- Direct `validate_semantics(...)` tests are permitted only for explicitly labelled defensive branches that cannot be reached through structurally valid canonical documents.

Run the complete suite with:

```bash
python scripts/render_views.py --check --root .
python scripts/validate_repository.py --root .
python -m unittest -v tests.test_semantics_workflow.SemanticReferenceTests
python -m unittest -v tests.test_semantics_workflow.DecisionIntelligenceTests
python -m unittest -v tests.test_semantics_workflow.DogfoodingTests
python -m unittest -v tests.test_semantics_workflow.WorkflowHardeningTests
python -m unittest discover -s tests -v
python -m compileall -q scripts tests
```

A GitHub Actions success is exact-Head evidence only when the workflow's expected and actual SHA values are identical and no required test step is skipped.
