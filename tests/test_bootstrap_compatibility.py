from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import validation_bootstrap as vb
from scripts.validation_core import ValidationIssue


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


class Repo:
    def __init__(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Foundry Test")
        git(self.root, "config", "user.email", "foundry@example.invalid")
        (self.root / "README.md").write_text("base\n", encoding="utf-8")
        self.base = self.commit("base")

    def close(self) -> None:
        self.temp.cleanup()

    def commit(self, message: str) -> str:
        git(self.root, "add", "-A")
        git(self.root, "commit", "--allow-empty", "-m", message)
        return git(self.root, "rev-parse", "HEAD")

    def write(self, tasks: list[dict], current_id: str, current_status: str, source: str) -> None:
        planning = self.root / "planning"
        planning.mkdir(exist_ok=True)
        (planning / "execution-program.v1.json").write_text(
            json.dumps({"tasks": tasks}) + "\n",
            encoding="utf-8",
        )
        (planning / "current-state.v1.json").write_text(
            json.dumps(
                {
                    "current_task_id": current_id,
                    "current_task_status": current_status,
                    "evidence_refs": [],
                    "last_transition": {
                        "from": source,
                        "to": current_status,
                        "evidence_refs": [],
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (planning / "scope-baseline.v1.json").write_text("{}\n", encoding="utf-8")


class BootstrapCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repo()

    def tearDown(self) -> None:
        self.repo.close()

    def test_planned_origin_passes(self) -> None:
        self.repo.write(
            [{"id": "T-1", "status": "planned", "evidence_refs": []}],
            "T-1",
            "planned",
            "planned",
        )
        self.repo.commit("introduce planned")
        self.assertEqual([], vb.validate_task_origins(self.repo.root))

    def test_advanced_origin_fails(self) -> None:
        self.repo.write(
            [{"id": "T-1", "status": "active", "evidence_refs": []}],
            "T-1",
            "active",
            "planned",
        )
        self.repo.commit("introduce active")
        issues = vb.validate_task_origins(self.repo.root)
        self.assertEqual(["PFV-037"], [issue.code for issue in issues])

    def test_bootstrap_exception_is_exact_and_not_reusable(self) -> None:
        self.repo.write(
            [{"id": "PF-001", "status": "implementation_submitted", "evidence_refs": []}],
            "PF-001",
            "implementation_submitted",
            "planned",
        )
        origin = self.repo.commit("bootstrap origin")
        with patch.multiple(
            vb,
            BOOTSTRAP_BASE_COMMIT=self.repo.base,
            BOOTSTRAP_ORIGIN_COMMIT=origin,
        ):
            self.assertEqual([], vb.validate_task_origins(self.repo.root))
            self.repo.write(
                [
                    {"id": "PF-001", "status": "implementation_submitted", "evidence_refs": []},
                    {"id": "PF-999", "status": "active", "evidence_refs": []},
                ],
                "PF-001",
                "implementation_submitted",
                "planned",
            )
            self.repo.commit("attempt bootstrap reuse")
            issues = vb.validate_task_origins(self.repo.root)
            self.assertEqual(1, len(issues))
            self.assertEqual("PFV-037", issues[0].code)
            self.assertIn("PF-999", issues[0].message)

    def test_exact_bootstrap_merge_suppresses_only_known_false_positive(self) -> None:
        git(self.repo.root, "checkout", "-b", "feature")
        self.repo.write(
            [{"id": "PF-001", "status": "implementation_submitted", "evidence_refs": []}],
            "PF-001",
            "implementation_submitted",
            "planned",
        )
        origin = self.repo.commit("bootstrap origin")
        (self.repo.root / "later.txt").write_text("later\n", encoding="utf-8")
        pr_head = self.repo.commit("bootstrap head")
        git(self.repo.root, "checkout", "main")
        git(self.repo.root, "merge", "--no-ff", "feature", "-m", "bootstrap integration")
        integration = git(self.repo.root, "rev-parse", "HEAD")

        hosted = Path(self.repo.temp.name) / "hosted.json"
        hosted.write_text(
            json.dumps(
                {
                    "schema_version": vb.HOSTED_SCHEMA,
                    "source": vb.HOSTED_SOURCE,
                    "repository": vb.REPOSITORY,
                    "merge_records": [
                        {
                            "repository": vb.REPOSITORY,
                            "integration_sha": integration,
                            "merge_commit_sha": integration,
                            "merged": True,
                            "merge_method": "merge_commit",
                            "pr_number": 1,
                            "pr_head_sha": pr_head,
                            "base_sha": self.repo.base,
                            "base_ref": "main",
                        }
                    ],
                    "ci_runs": [
                        {
                            "commit_sha": pr_head,
                            "workflow_name": vb.WORKFLOW_NAME,
                            "event": "pull_request",
                            "conclusion": "success",
                            "run_id": 1,
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        env = {
            "PROJECT_FOUNDRY_TEST_MODE": "1",
            "PROJECT_FOUNDRY_HOSTED_PROVENANCE_PATH": str(hosted),
        }
        known = ValidationIssue(
            "PFV-036",
            f"integration {integration} does not integrate the canonical active Task at merge_pending",
        )
        unrelated = ValidationIssue(
            "PFV-036",
            "integration another does not integrate the canonical active Task at merge_pending",
        )
        with patch.dict(os.environ, env, clear=False), patch.multiple(
            vb,
            BOOTSTRAP_BASE_COMMIT=self.repo.base,
            BOOTSTRAP_ORIGIN_COMMIT=origin,
            BOOTSTRAP_PR_HEAD=pr_head,
            BOOTSTRAP_INTEGRATION_COMMIT=integration,
        ):
            adjusted = vb.apply_bootstrap_compatibility(self.repo.root, [known, unrelated])
        self.assertEqual([unrelated], adjusted)


if __name__ == "__main__":
    unittest.main()
