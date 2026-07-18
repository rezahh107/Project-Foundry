#!/usr/bin/env python3
"""Render the hardened Foundation validation workflow deterministically."""
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts.validation_core import CHECKOUT_PIN, EXPECTED_SHA_EXPRESSION, SETUP_PYTHON_PIN
except ModuleNotFoundError:
    from validation_core import CHECKOUT_PIN, EXPECTED_SHA_EXPRESSION, SETUP_PYTHON_PIN

WORKFLOW_PATH = ".github/workflows/foundation-validation.yml"


def render_foundation_workflow() -> str:
    return fr"""name: Foundation validation

on:
  pull_request:
  push:
    branches:
      - main

permissions:
  contents: read

jobs:
  validate-exact-head:
    name: Validate exact triggering head
    runs-on: ubuntu-latest
    env:
      PROJECT_FOUNDRY_EVENT_NAME: ${{{{ github.event_name }}}}
      PROJECT_FOUNDRY_EXPECTED_HEAD_SHA: ${{{{ github.event.pull_request.head.sha || github.sha }}}}
      PROJECT_FOUNDRY_GITHUB_REF: ${{{{ github.ref }}}}
      PROJECT_FOUNDRY_PR_HEAD_SHA: ${{{{ github.event.pull_request.head.sha || '' }}}}
      PROJECT_FOUNDRY_PR_BASE_SHA: ${{{{ github.event.pull_request.base.sha || '' }}}}
      PROJECT_FOUNDRY_PR_HEAD_REF: ${{{{ github.event.pull_request.head.ref || '' }}}}
      PROJECT_FOUNDRY_SYNTHETIC_MERGE_SHA: ${{{{ github.event.pull_request.merge_commit_sha || '' }}}}
      PROJECT_FOUNDRY_PUSH_BEFORE_SHA: ${{{{ github.event.before || '' }}}}
    steps:
      - name: Check out exact triggering head
        uses: actions/checkout@{CHECKOUT_PIN} # v6.0.3
        with:
          ref: {EXPECTED_SHA_EXPRESSION}
          persist-credentials: false
          fetch-depth: 0

      - name: Verify exact checkout identity
        shell: bash
        env:
          EXPECTED_SHA: {EXPECTED_SHA_EXPRESSION}
          EVENT_NAME: ${{{{ github.event_name }}}}
          TRIGGER_REF: ${{{{ github.ref }}}}
        run: |
          set -euo pipefail
          actual_sha="$(git rev-parse HEAD)"
          printf 'event_name=%s\ntrigger_ref=%s\nexpected_sha=%s\nactual_sha=%s\npr_base_sha=%s\npush_before_sha=%s\n' \
            "$EVENT_NAME" "$TRIGGER_REF" "$EXPECTED_SHA" "$actual_sha" \
            "$PROJECT_FOUNDRY_PR_BASE_SHA" "$PROJECT_FOUNDRY_PUSH_BEFORE_SHA"
          test "$actual_sha" = "$EXPECTED_SHA"

      - name: Set up Python
        uses: actions/setup-python@{SETUP_PYTHON_PIN} # v6 verified upstream commit
        with:
          python-version: "3.12"

      - name: Run rendered view check
        run: python scripts/render_views.py --check --root .

      - name: Run deterministic repository validation
        run: python scripts/validate_repository.py --root .

      - name: Test direct validator API
        run: python -m unittest -v tests.test_valid_api.DirectValidatorApiTests

      - name: Test in-process CLI boundary
        run: python -m unittest -v tests.test_valid_api.InProcessCliTests

      - name: Test subprocess validator boundary
        run: python -m unittest -v tests.test_valid_api.SubprocessValidatorTests

      - name: Test malformed renderer subprocess boundary
        run: python -m unittest -v tests.test_valid_api.SubprocessRendererFailureTests

      - name: Test generated view parity
        run: python -m unittest -v tests.test_valid_api.DeterministicViewCheckTests

      - name: Test idempotent view writes
        run: python -m unittest -v tests.test_valid_api.DeterministicViewWriteTests

      - name: Test deterministic workflow parity
        run: python -m unittest -v tests.test_valid_api.DeterministicWorkflowParityTests

      - name: Test structural mutation corpus
        run: python -m unittest -v tests.test_structural_renderer.StructuralMutationTests

      - name: Test renderer structural gate
        run: python -m unittest -v tests.test_structural_renderer.RendererStructuralGateTests

      - name: Test Program membership closure
        run: python -m unittest -v tests.test_program_scope_closure.ProgramMembershipClosureTests

      - name: Test Scope membership closure
        run: python -m unittest -v tests.test_program_scope_closure.ScopeMembershipClosureTests

      - name: Test renderer Task-set completeness
        run: python -m unittest -v tests.test_program_scope_closure.RendererTaskSetCompletenessTests

      - name: Test dependency graph acyclicity
        run: python -m unittest -v tests.test_dependency_lifecycle.DependencyGraphAcyclicityTests

      - name: Test dependency satisfaction
        run: python -m unittest -v tests.test_dependency_lifecycle.DependencySatisfactionTests

      - name: Test next-task dispatch safety
        run: python -m unittest -v tests.test_dependency_lifecycle.NextTaskDispatchTests

      - name: Test lifecycle transition legality
        run: python -m unittest -v tests.test_dependency_lifecycle.LifecycleTransitionTests

      - name: Test evidence carrier diagnostics
        run: python -m unittest -v tests.test_dependency_lifecycle.ExactMainEvidenceTests

      - name: Test completed and blocked closure
        run: python -m unittest -v tests.test_dependency_lifecycle.ProgressCollectionClosureTests

      - name: Test next-work dispatch rendering
        run: python -m unittest -v tests.test_dependency_lifecycle.NextWorkDispatchRenderingTests

      - name: Test real Git provenance and forward progress
        run: python -m unittest -v tests.test_git_provenance

      - name: Test semantic reference corpus
        run: python -m unittest -v tests.test_semantics_workflow.SemanticReferenceTests

      - name: Test Decision Intelligence gate
        run: python -m unittest -v tests.test_semantics_workflow.DecisionIntelligenceTests

      - name: Test Dogfooding controls
        run: python -m unittest -v tests.test_semantics_workflow.DogfoodingTests

      - name: Test workflow bypass corpus
        run: python -m unittest -v tests.test_semantics_workflow.WorkflowHardeningTests

      - name: Run complete unit suite
        run: python -m unittest discover -s tests -v

      - name: Compile validation code
        run: python -m compileall -q scripts tests
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    path = root / WORKFLOW_PATH
    expected = render_foundation_workflow()
    if args.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(expected, encoding="utf-8", newline="\n")
        temporary.replace(path)
        print("Foundation workflow: UPDATED")
        return 0
    try:
        actual = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"PFV-001: workflow cannot be read: {exc}")
        return 1
    if actual != expected:
        print("PFV-136: foundation workflow drifted from hardened deterministic projection")
        return 1
    print("Foundation workflow: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
