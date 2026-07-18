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
    issue_codes, mutate_jsoon, run_cli, run_subprocess_cli, write_json, read_json,
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
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn(case["expected"], result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                finally:
                    temporary.cleanup()

    def test_malformed_and_non_finite_json_are_controlled(self) -> None:
        cases = ["{broken", "NaN", "Infinity", "-Infinity"]
        for replacement in cases:
            with self.subTest(replacement=replacement):
                temporary, target = copy_repo()
                try:
                    path = target / "decisions/decision-registry.v1.json"
                    if replacement == "{broken":
                        path.write_text(replacement, encoding="utf-8")
                    else:
                        text = path.read_text(encoding="utf-8")
                        text = re.sub(r'"ai_operability"\s*:\s*25', f'"ai_operability": {replacement}', text, count=1)
                        path.write_text(text, encoding="utf-8")
                    self.assertIn("PFV-101", issue_codes(target))
                    result = run_cli(target)
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("PFV-101", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                finally:
                    temporary.cleanup()


class RendererStructuralGateTests(unittest.TestCase):
    def _assert_renderer_rejects(self, mutation: Callable[[Path], None], expected: str) -> None:
        temporary, target = copy_repo()
        try:
            before = {path: (target / path).read_bytes() for path in CRITICAL_VIEWS}
            mutation(target)
            for mode in ["--check", "--write"]:
                with self.subTest(mode=mode):
                    result = run_cli(target, "scripts/render_views.py", mode)
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn(expected, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual(before, {path: (target / path).read_bytes() for path in CRITICAL_VIEWS})
        finally:
            temporary.cleanup()

    def test_renderer_cli_rejects_structural_and_reference_failures(self) -> None:
        cases: list[tuple[str, Callable[[Path], None], str]] = [
            ("north_star_null", lambda root: mutate_json(root, "governance/project-constitution.v1.json", lambda doc: doc.__setitem__("north_star", None)), "PFV-100"),
            ("operating_profile_null", lambda root: mutate_json(root, "governance/project-constitution.v1.json", lambda doc: doc.__setitem__("operating_profile", None)), "PFV-110"),
            ("unknown_wp_task", lambda root: mutate_json(root, "planning/execution-program.v1.json", lambda doc: doc["work_packages"][0]["task_ids"].append("PF-404")), "PFV-029"),
            ("unknown_current", lambda root: mutate_json(root, "planning/current-state.v1.json", lambda doc: doc.__setitem__("current_task_id", "PF-404")), "PFV-059"),
            ("top_array", lambda root: write_json(root, "planning/current-state.v1.json", []), "PFV-110"),
            ("malformed", lambda root: (root / "planning/current-state.v1.json").write_text("{bad", encoding="utf-8"), "PFV-101"),
            ("nan", lambda root: (root / "decisions/decision-registry.v1.json").write_text(re.sub(r'"ai_operability"\s*:\s*25', '"ai_operability": NaN', (root / "decisions/decision-registry.v1.json").read_text(encoding="utf-8"), count=1), encoding="utf-8"), "PFV-101"),
            ("infinity", lambda root: (root / "decisions/decision-registry.v1.json").write_text(re.sub(r'"ai_operability"\s*:\s*25', '"ai_operability": Infinity', (root / "decisions/decision-registry.v1.json").read_text(encoding="utf-8"), count=1), encoding="utf-8"), "PFV-101"),
            ("missing_file", lambda root: (root / "planning/current-state.v1.json").unlink(), "PFV-010"),
        ]
        for name, mutation, expected in cases:
            with self.subTest(case=name):
                self._assert_renderer_rejects(mutation, expected)


