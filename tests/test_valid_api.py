from __future__ import annotations

import unittest

from scripts.validate_repository import validate
from tests.support import (
    REPO_ROOT,
    copy_repo,
    current_validation_env,
    run_cli,
    run_subprocess_cli,
)


class DirectValidatorApiTests(unittest.TestCase):
    def test_direct_validator_is_clean(self) -> None:
        issues = validate(REPO_ROOT)
        self.assertEqual([], issues, [f"{issue.code}: {issue.message}" for issue in issues])


class InProcessCliTests(unittest.TestCase):
    def test_in_process_cli_is_clean(self) -> None:
        result = run_cli(REPO_ROOT, env=current_validation_env())
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("validation: PASS", result.stdout)


class SubprocessValidatorTests(unittest.TestCase):
    def test_subprocess_validator_is_clean(self) -> None:
        result = run_subprocess_cli(
            REPO_ROOT,
            "scripts/validate_repository.py",
            env=current_validation_env(),
        )
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


class DeterministicViewCheckTests(unittest.TestCase):
    def test_generated_views_are_current(self) -> None:
        from scripts.render_views import check_views

        temporary, target = copy_repo()
        try:
            self.assertEqual([], check_views(target))
        finally:
            temporary.cleanup()


class DeterministicViewWriteTests(unittest.TestCase):
    def test_view_write_is_idempotent(self) -> None:
        from scripts.render_views import write_views
        from tests.support import CRITICAL_VIEWS

        temporary, target = copy_repo()
        try:
            before = {path: (target / path).read_bytes() for path in CRITICAL_VIEWS}
            write_views(target)
            after = {path: (target / path).read_bytes() for path in CRITICAL_VIEWS}
            self.assertEqual(before, after)
        finally:
            temporary.cleanup()


class DeterministicWorkflowParityTests(unittest.TestCase):
    def test_workflow_matches_renderer_exactly(self) -> None:
        from scripts.render_workflow import render_foundation_workflow

        actual = (REPO_ROOT / ".github/workflows/foundation-validation.yml").read_text(encoding="utf-8")
        self.assertEqual(render_foundation_workflow(), actual)
