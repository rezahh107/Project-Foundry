from __future__ import annotations

import unittest

from scripts.validate_repository import validate
from tests.support import REPO_ROOT, copy_repo, run_cli, run_subprocess_cli


class DirectValidatorApiTests(unittest.TestCase):
    def test_direct_validator_is_clean(self) -> None:
        issues = validate(REPO_ROOT)
        self.assertEqual([], issues, [f"{issue.code}: {issue.message}" for issue in issues])


class InProcessCliTests(unittest.TestCase):
    def test_in_process_cli_is_clean(self) -> None:
        result = run_cli(REPO_ROOT)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("validation: PASS", result.stdout)


class SubprocessValidatorTests(unittest.TestCase):
    def test_subprocess_validator_is_clean(self) -> None:
        result = run_subprocess_cli(REPO_ROOT, "scripts/validate_repository.py")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("validation: PASS", result.stdout)


class SubprocessRendererFailureTests(unittest.TestCase):
    def test_malformed_renderer_cli_is_controlled(self) -> None:
        temporary, target = copy_repo()
        try:
            (target / "planning/current-state.v1.json").write_text("{bad", encoding="utf-8")
            result = run_subprocess_cli(target, "scripts/render_views.py", "--check")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("PFV-101", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
        finally:
            temporary.cleanup()
