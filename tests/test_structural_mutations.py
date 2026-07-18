from __future__ import annotations

import json
import re
import unittest

from tests.support import (
    STRUCTURAL_FIXTURES,
    apply_json_case,
    copy_repo,
    issue_codes,
    run_cli,
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
        for replacement in ["{broken", "NaN", "Infinity", "-Infinity"]:
            with self.subTest(replacement=replacement):
                temporary, target = copy_repo()
                try:
                    path = target / "decisions/decision-registry.v1.json"
                    if replacement == "{broken":
                        path.write_text(replacement, encoding="utf-8")
                    else:
                        text = path.read_text(encoding="utf-8")
                        text = re.sub(
                            r'"ai_operability"\s*:\s*25',
                            f'"ai_operability": {replacement}',
                            text,
                            count=1,
                        )
                        path.write_text(text, encoding="utf-8")
                    self.assertIn("PFV-101", issue_codes(target))
                    result = run_cli(target)
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("PFV-101", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                finally:
                    temporary.cleanup()
