from __future__ import annotations

import unittest

from scripts.validate_repository import validate
from tests.support import REPO_ROOT, run_cli


class DirectValidatorApiTests(unittest.TestCase):
    def test_direct_validator_is_clean(self) -> None:
        issues = validate(REPO_ROOT)
        self.assertEqual([], issues, [f"{issue.code}: {issue.message}" for issue in issues])


class InProcessCliTests(unittest.TestCase):
    def test_in_process_cli_is_clean(self) -> None:
        result = run_cli(REPO_ROOT)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("validation: PASS", result.stdout)
