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
    return f'''name: Foundation validation

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
    steps:
      - name: Check out exact triggering head
        uses: actions/checkout@{CHECKOUT_PIN} # v6.0.3
        with:
          ref: {EXPECTED_SHA_EXPRESSION}
          persist-credentials: false
          fetch-depth: 1

      - name: Verify exact checkout identity
        shell: bash
        env:
          EXPECTED_SHA: {EXPECTED_SHA_EXPRESSION}
          EVENT_NAME: ${{{{ github.event_name }}}}
          TRIGGER_REF: ${{{{ github.ref }}}}
        run: |
          set -euo pipefail
          actual_sha="$(git rev-parse HEAD)"
          printf 'event_name=%s\\ntrigger_ref=%s\\nexpected_sha=%s\\nactual_sha=%s\\n' \\
            "$EVENT_NAME" "$TRIGGER_REF" "$EXPECTED_SHA" "$actual_sha"
          test "$actual_sha" = "$EXPECTED_SHA"

      - name: Set up Python
        uses: actions/setup-python@{SETUP_PYTHON_PIN} # v6 verified upstream commit
        with:
          python-version: "3.12"

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

      - name: Test deterministic renderers and workflow
        run: python -m unittest -v tests.test_structural_renderer.ValidRepositoryTests.test_renderers_are_idempotent_and_workflow_is_exact

      - name: Test structural mutation corpus
        run: python -m unittest -v tests.test_structural_renderer.StructuralMutationTests

      - name: Test renderer structural gate
        run: python -m unittest -v tests.test_structural_renderer.RendererStructuralGateTests

      - name: Test semantic reference corpus
        run: python -m unittest -v tests.test_semantics_workflow.SemanticReferenceTests

      - name: Test Decision Intelligence gate
        run: python -m unittest -v tests.test_semantics_workflow.DecisionIntelligenceTests

      - name: Test Dogfooding controls
        run: python -m unittest -v tests.test_semantics_workflow.DogfoodingTests

      - name: Test workflow bypass corpus
        run: python -m unittest -v tests.test_semantics_workflow.WorkflowHardeningTests

      - name: Compile validation code
        run: python -m compileall -q scripts tests
'''


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
