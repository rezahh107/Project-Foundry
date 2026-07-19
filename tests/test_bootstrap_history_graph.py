from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import validation_bootstrap as vb


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

    def write_tasks(self, tasks: object) -> None:
        planning = self.root / "planning"
        planning.mkdir(exist_ok=True)
        (planning / "execution-program.v1.json").write_text(
            json.dumps({"tasks": tasks}) + "\n",
            encoding="utf-8",
        )


class BootstrapHistoryGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repo()

    def tearDown(self) -> None:
        self.repo.close()

    def test_nested_merge_preserves_the_real_planned_origin(self) -> None:
        git(self.repo.root, "checkout", "-b", "feature")
        git(self.repo.root, "checkout", "-b", "nested")
        self.repo.write_tasks([{"id": "T-NESTED", "status": "planned", "evidence_refs": []}])
        self.repo.commit("introduce nested task as planned")
        self.repo.write_tasks([{"id": "T-NESTED", "status": "active", "evidence_refs": []}])
        self.repo.commit("advance nested task")

        git(self.repo.root, "checkout", "feature")
        git(self.repo.root, "merge", "--no-ff", "nested", "-m", "merge nested branch")
        git(self.repo.root, "checkout", "main")
        git(self.repo.root, "merge", "--no-ff", "feature", "-m", "merge feature branch")

        self.assertEqual([], vb.validate_task_origins(self.repo.root))

    def test_independent_advanced_origin_is_not_hidden_by_topological_order(self) -> None:
        git(self.repo.root, "checkout", "-b", "planned-origin")
        self.repo.write_tasks([{"id": "T-SHARED", "status": "planned", "evidence_refs": []}])
        self.repo.commit("planned origin")
        git(self.repo.root, "checkout", "main")
        git(self.repo.root, "merge", "--no-ff", "planned-origin", "-m", "merge planned origin")

        git(self.repo.root, "checkout", "-b", "advanced-origin", self.repo.base)
        self.repo.write_tasks([{"id": "T-SHARED", "status": "active", "evidence_refs": []}])
        advanced = self.repo.commit("independent advanced origin")
        git(self.repo.root, "checkout", "main")
        git(self.repo.root, "merge", "--no-ff", "-s", "ours", "advanced-origin", "-m", "join histories")

        issues = vb.validate_task_origins(self.repo.root)
        self.assertEqual(["PFV-037"], [issue.code for issue in issues])
        self.assertIn(advanced, issues[0].message)
        self.assertIn("T-SHARED", issues[0].message)

    def test_non_list_historical_tasks_fail_closed_without_crashing(self) -> None:
        self.repo.write_tasks(None)
        malformed = self.repo.commit("malformed historical task collection")

        issues = vb.validate_task_origins(self.repo.root)
        self.assertEqual(["PFV-037"], [issue.code for issue in issues])
        self.assertIn(malformed, issues[0].message)
        self.assertIn("non-list tasks collection", issues[0].message)


if __name__ == "__main__":
    unittest.main()
