# Validation and Mutation Test Corpus

The Foundation suite covers structural safety, rendered-view boundaries, Program and Scope closure, dependency graph and readiness, next-task dispatch, lifecycle transitions, exact-main evidence, completed/blocked closure, Decision Intelligence, Dogfooding, workflow bypasses, and direct/in-process/subprocess CLI boundaries.

Diagnostic ownership is normative in `docs/VALIDATION_DIAGNOSTIC_OWNERSHIP.md`.

## Required commands

```bash
python scripts/render_views.py --check --root .
python scripts/validate_repository.py --root .
python -m unittest -v tests.test_program_scope_closure.ProgramMembershipClosureTests
python -m unittest -v tests.test_program_scope_closure.ScopeMembershipClosureTests
python -m unittest -v tests.test_program_scope_closure.RendererTaskSetCompletenessTests
python -m unittest -v tests.test_dependency_lifecycle.DependencyGraphAcyclicityTests
python -m unittest -v tests.test_dependency_lifecycle.DependencySatisfactionTests
python -m unittest -v tests.test_dependency_lifecycle.NextTaskDispatchTests
python -m unittest -v tests.test_dependency_lifecycle.LifecycleTransitionTests
python -m unittest -v tests.test_dependency_lifecycle.ExactMainEvidenceTests
python -m unittest -v tests.test_dependency_lifecycle.ProgressCollectionClosureTests
python -m unittest -v tests.test_dependency_lifecycle.NextWorkDispatchRenderingTests
python -m unittest -v tests.test_semantics_workflow.SemanticReferenceTests
python -m unittest -v tests.test_semantics_workflow.DecisionIntelligenceTests
python -m unittest -v tests.test_semantics_workflow.DogfoodingTests
python -m unittest -v tests.test_semantics_workflow.WorkflowHardeningTests
python -m unittest discover -s tests -v
python -m compileall -q scripts tests
```

Semantic invalid cases must exit non-zero through the real CLI, emit the intended stable diagnostic, omit `PFV-199`, and emit no traceback. Exact-main positive tests supply `PROJECT_FOUNDRY_CURRENT_MAIN_SHA`; a model-authored free-form claim is never sufficient.
