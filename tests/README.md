# Validation and Mutation Test Corpus

The Foundation suite covers structural safety, deterministic views, Program and Scope closure, dependency and dispatch rules, lifecycle transitions, Merge boundaries, transitive evidence chains, Decision Intelligence, Dogfooding, workflow hardening, and CLI boundaries.

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

## RR7 real-Git coverage

`tests.test_git_provenance` creates actual temporary Git repositories and verifies:

- exact branch-validation receipts;
- invalid branch-receipt laundering through later status commits;
- latest-Head-only multi-commit pushes;
- actual two-parent integration-commit push validation;
- branch-state preservation at the integration boundary;
- explicit squash/rebase rejection;
- direct-push and synthetic-merge rejection;
- hosted PR/merge identity binding;
- predecessor-receipt SHA-256 chaining;
- invalid Merge-receipt laundering;
- valid end-to-end progression through `current_main_verified`;
- historical-chain preservation after later unrelated commits;
- `PF-001` completion making `PF-002` dispatch-eligible.

Each invalid case must exit non-zero, emit its stable diagnostic, omit `PFV-199`, and emit no traceback.
