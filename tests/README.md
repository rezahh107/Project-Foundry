# Validation and Mutation Test Corpus

The Foundation suite covers structural safety, Program/Scope closure, dependency graph and dispatch, lifecycle transitions, evidence-carrier diagnostics, real Git provenance, historical evidence preservation, Decision Intelligence, Dogfooding and workflow hardening.

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
python -m unittest -v tests.test_git_provenance
python -m unittest -v tests.test_semantics_workflow.SemanticReferenceTests
python -m unittest -v tests.test_semantics_workflow.DecisionIntelligenceTests
python -m unittest -v tests.test_semantics_workflow.DogfoodingTests
python -m unittest -v tests.test_semantics_workflow.WorkflowHardeningTests
python -m unittest discover -s tests -v
python -m compileall -q scripts tests
```

## Real-Git integration contract

`tests.test_git_provenance` creates temporary Git repositories with actual commits, feature branches, `--no-ff` Merge commits, receipt commits and later main commits. It verifies:

- a receipt cannot embed or precompute its own commit SHA;
- PR base, PR Head, synthetic merge and unrelated SHAs cannot substitute for current-main provenance;
- submitted `last_transition.from` must match the actual prior canonical status in first-parent history;
- branch-validation, Merge and current-main receipts use distinct trust contexts;
- a Merge subject followed by a Merge receipt and a current-main verification receipt is constructible;
- historical evidence remains valid after later main commits;
- verified completion of `PF-001` makes `PF-002` dispatch-eligible.

Every invalid semantic case must exit non-zero through the real CLI, emit the intended stable diagnostic, omit `PFV-199`, and emit no traceback.
