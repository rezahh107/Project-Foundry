from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from typing import Any

from scripts.render_views import check_views, write_views
from scripts.validate_repository import main as validator_main
from scripts.validate_repository import validate

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests/fixtures/structural_mutations.json"


def copy_repo() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory()
    target = Path(temporary.name) / "repo"
    shutil.copytree(REPO_ROOT, target)
    return temporary, target


def set_path(document: Any, path: list[Any], value: Any) -> None:
    cursor = document
    for segment in path[:-1]:
        cursor = cursor[segment]
    cursor[path[-1]] = value


def delete_path(document: Any, path: list[Any]) -> None:
    cursor = document
    for segment in path[:-1]:
        cursor = cursor[segment]
    del cursor[path[-1]]


def apply_json_case(root: Path, case: dict[str, Any]) -> None:
    path = root / case["file"]
    document = json.loads(path.read_text(encoding="utf-8"))
    if "replace_document" in case:
        document = case["replace_document"]
    elif "delete_path" in case:
        delete_path(document, case["delete_path"])
    else:
        set_path(document, case["path"], case["value"])
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def issue_codes(root: Path) -> set[str]:
    return {issue.code for issue in validate(root)}


def run_cli(root: Path) -> subprocess.CompletedProcess[str]:
    """Run the real CLI entry point in a separate process and capture its exit code."""
    if hasattr(os, "fork"):
        read_fd, write_fd = os.pipe()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            pid = os.fork()
        if pid == 0:
            try:
                os.close(read_fd)
                os.dup2(write_fd, 1)
                os.dup2(write_fd, 2)
                os.close(write_fd)
                os.chdir(root)
                code = validator_main(["--root", "."])
            except BaseException as exc:
                print(f"Traceback substitute: {type(exc).__name__}: {exc}", file=sys.stderr)
                code = 99
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(code)
        os.close(write_fd)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(read_fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        os.close(read_fd)
        _, status = os.waitpid(pid, 0)
        returncode = os.waitstatus_to_exitcode(status)
        output = b"".join(chunks).decode("utf-8", errors="replace")
        return subprocess.CompletedProcess(
            [],
            returncode,
            stdout=output if returncode == 0 else "",
            stderr=output if returncode != 0 else "",
        )
    return subprocess.run(
        [sys.executable, "scripts/validate_repository.py", "--root", "."],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )


class ValidRepositoryTests(unittest.TestCase):
    def test_repository_foundation_is_valid(self) -> None:
        self.assertEqual([], validate(REPO_ROOT))

    def test_cli_passes_for_valid_repository(self) -> None:
        result = run_cli(REPO_ROOT)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("validation: PASS", result.stdout)

    def test_render_check_passes_and_write_is_idempotent(self) -> None:
        temporary, target = copy_repo()
        self.addCleanup(temporary.cleanup)
        self.assertEqual([], check_views(target))
        before = {
            path: (target / path).read_bytes()
            for path in ["PROJECT_CHARTER.md", "SYSTEM_MAP.md", "planning/NEXT_WORK.md"]
        }
        write_views(target)
        after = {path: (target / path).read_bytes() for path in before}
        self.assertEqual(before, after)


class StructuralMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_table_driven_structural_mutations_return_stable_diagnostics(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["name"]):
                temporary, target = copy_repo()
                try:
                    apply_json_case(target, case)
                    self.assertIn(case["expected"], issue_codes(target))
                finally:
                    temporary.cleanup()

    def test_table_driven_structural_mutations_fail_at_cli_boundary(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["name"]):
                temporary, target = copy_repo()
                try:
                    apply_json_case(target, case)
                    result = run_cli(target)
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn(case["expected"], result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                finally:
                    temporary.cleanup()

    def test_non_finite_numbers_are_rejected_without_traceback(self) -> None:
        for token in ["NaN", "Infinity", "-Infinity"]:
            with self.subTest(token=token):
                temporary, target = copy_repo()
                try:
                    path = target / "decisions/decision-registry.v1.json"
                    text = path.read_text(encoding="utf-8")
                    text = text.replace('"ai_operability": 20', f'"ai_operability": {token}', 1)
                    path.write_text(text, encoding="utf-8")
                    self.assertIn("PFV-101", issue_codes(target))
                    result = run_cli(target)
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("PFV-101", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                finally:
                    temporary.cleanup()


class RenderedParityTests(unittest.TestCase):
    def assert_drift(self, relative: str, mutate, expected_code: str) -> None:
        temporary, target = copy_repo()
        self.addCleanup(temporary.cleanup)
        path = target / relative
        path.write_text(mutate(path.read_text(encoding="utf-8")), encoding="utf-8")
        self.assertIn(expected_code, issue_codes(target))
        result = run_cli(target)
        self.assertNotEqual(0, result.returncode)
        self.assertIn(expected_code, result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_charter_north_star_id_drift(self) -> None:
        self.assert_drift(
            "PROJECT_CHARTER.md",
            lambda text: text.replace("PF-NORTH-STAR-001", "PF-NORTH-STAR-STALE", 1),
            "PFV-120",
        )

    def test_charter_north_star_statement_drift(self) -> None:
        self.assert_drift(
            "PROJECT_CHARTER.md",
            lambda text: text.replace("Build a repository-native", "Build an unrelated"),
            "PFV-120",
        )

    def test_charter_unrelated_id_does_not_mask_wrong_value(self) -> None:
        self.assert_drift(
            "PROJECT_CHARTER.md",
            lambda text: text.replace(
                "**ID:** `PF-NORTH-STAR-001`",
                "**ID:** `WRONG-ID`\n\nUnrelated note: `PF-NORTH-STAR-001`",
            ),
            "PFV-120",
        )

    def test_system_map_work_package_omission(self) -> None:
        self.assert_drift(
            "SYSTEM_MAP.md",
            lambda text: text.replace("- `WP-05` — **Foundry Kernel**", "- omitted work package"),
            "PFV-121",
        )

    def test_next_work_stale_current_task(self) -> None:
        self.assert_drift(
            "planning/NEXT_WORK.md",
            lambda text: text.replace("`PF-001`", "`PF-002`", 1),
            "PFV-122",
        )

    def test_next_work_stale_lifecycle(self) -> None:
        self.assert_drift(
            "planning/NEXT_WORK.md",
            lambda text: text.replace("`implementation_submitted`", "`complete`", 1),
            "PFV-122",
        )

    def test_next_work_stale_scope(self) -> None:
        self.assert_drift(
            "planning/NEXT_WORK.md",
            lambda text: text.replace("PF-SCOPE-001@0.1.0", "PF-SCOPE-STALE@9.9.9", 1),
            "PFV-122",
        )

    def test_next_work_contradictory_next_action(self) -> None:
        self.assert_drift(
            "planning/NEXT_WORK.md",
            lambda text: text.replace(
                "Review and merge the foundation pull request",
                "Skip review and start the Foundry Kernel",
            ),
            "PFV-122",
        )


class WorkflowHardeningTests(unittest.TestCase):
    def assert_workflow_issue(self, mutate, expected_code: str) -> None:
        temporary, target = copy_repo()
        self.addCleanup(temporary.cleanup)
        path = target / ".github/workflows/foundation-validation.yml"
        path.write_text(mutate(path.read_text(encoding="utf-8")), encoding="utf-8")
        self.assertIn(expected_code, issue_codes(target))

    def test_mutable_action_reference_is_rejected(self) -> None:
        self.assert_workflow_issue(
            lambda text: text.replace(
                "actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10",
                "actions/checkout@v6",
            ),
            "PFV-130",
        )

    def test_persisted_credentials_are_rejected(self) -> None:
        self.assert_workflow_issue(
            lambda text: text.replace("persist-credentials: false", "persist-credentials: true"),
            "PFV-131",
        )

    def test_non_exact_checkout_ref_is_rejected(self) -> None:
        self.assert_workflow_issue(
            lambda text: text.replace(
                "ref: ${{ github.event.pull_request.head.sha || github.sha }}",
                "ref: ${{ github.ref }}",
            ),
            "PFV-132",
        )

    def test_weakened_identity_assertion_is_rejected(self) -> None:
        self.assert_workflow_issue(
            lambda text: text.replace(
                'test "$actual_sha" = "$EXPECTED_SHA"',
                'echo "$actual_sha" "$EXPECTED_SHA"',
            ),
            "PFV-133",
        )


if __name__ == "__main__":
    unittest.main()
