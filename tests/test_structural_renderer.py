from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import Any, Callable

from scripts.render_views import check_views, write_views
from scripts.render_workflow import render_foundation_workflow
from scripts.validate_repository import validate
from scripts.validation_semantics import load_and_validate_structures, validate_semantics
from tests.support import (
    REPO_ROOT, STRUCTURAL_FIXTURES, CRITICAL_VIEWS, apply_json_case, copy_repo,
    issue_codes, mutate_json, run_cli, run_subprocess_cli, write_json, read_json,
)

class ValidRepositoryTests(unittest.TestCase):
    def test_repository_and_real_cli_are_valid(self) -> None:
        self.assertEqual([], validate(REPO_ROOT))
        result = run_cli(REPO_ROOT)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("validation: PASS", result.stdout)

    def test_real_subprocess_cli_boundaries(self) -> None:
        valid = run_subprocess_cli(REPO_ROOT, "scripts/validate_repository.py")
        self.assertEqual(0, valid.returncode, valid.stderr)
        temporary, target = copy_repo()
        try:
            (target / "planning/current-state.v1.json").write_text("{bad", encoding="utf-8")
            invalid = run_subprocess_cli(target, "scripts/render_views.py", "--check")
            self.assertNotEqual(0, invalid.returncode)
            self.assertIn("PFV-101", invalid.stderr)
            self.assertNotIn("Traceback", invalid.stderr)
        finally:
            temporary.cleanup()

    def test_renderers_are_idempotent_and_workflow_is_exact(self) -> None:
        temporary, target = copy_repo()
        self.addCleanup(temporary.cleanup)
        self.assertEqual([], check_views(target))
        before = {path: (target / path).read_bytes() for path in CRITICAL_VIEWS}
        write_views(target)
        self.assertEqual(before, {path: (target / path).read_bytes() for path in CRITICAL_VIEWS})
        self.assertEqual(
            render_foundation_workflow(),
            (target / ".github/workflows/foundation-validation.yml").read_text(encoding="utf-8"),
        )


class StructuralMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = json.loads(STRUCTURAL_FIXTURES.read_text(encoding="utf-8"))

    def test_structural_fixture_corpus_through_validate_and_cli(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["name"]):
                temporary, target = copy_repo()
                try:
                    apply_json_case(target, case)
                    self.assertIn(case["expected"], issue_codes(target))
                    result = run_cli(target)
                    self.assertNotEqual(0, resu[¶»§q«^u¼¬ÊË^