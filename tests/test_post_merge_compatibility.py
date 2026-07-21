from __future__ import annotations

import copy
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import validation_bootstrap_followup as followup
from scripts.validation_core import ValidationIssue


class PostMergeCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(".").resolve()
        self.base = followup.RECONCILIATION_BASE_COMMIT
        self.pr_head = followup.RECONCILIATION_PR_HEAD
        self.integration = followup.RECONCILIATION_INTEGRATION_COMMIT
        self.pr_number = followup.RECONCILIATION_PR_NUMBER
        self.merge_record = {
            "repository": followup.REPOSITORY,
            "integration_sha": self.integration,
            "merge_commit_sha": self.integration,
            "merged": True,
            "merge_method": "merge_commit",
            "pr_number": self.pr_number,
            "pr_head_sha": self.pr_head,
            "base_sha": self.base,
            "base_ref": "main",
        }
        self.ci_run = {
            "commit_sha": self.pr_head,
            "workflow_name": followup.WORKFLOW_NAME,
            "event": "pull_request",
            "conclusion": "success",
        }

    def _boundary_valid(self, payload: dict[str, object], *, parents: list[str] | None = None) -> bool:
        completed = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch.object(followup, "_value", return_value="f" * 40),
            patch.object(followup, "_ancestor", return_value=True),
            patch.object(followup, "_parents", return_value=parents or [self.base, self.pr_head]),
            patch.object(followup, "_git", return_value=completed),
            patch.object(followup, "_hosted_payload", return_value=payload),
        ):
            return followup._exact_boundary_valid(
                self.root,
                base=self.base,
                pr_head=self.pr_head,
                integration=self.integration,
                pr_number=self.pr_number,
            )

    def test_exact_reconciliation_identity_is_pinned(self) -> None:
        self.assertEqual("27f95557416a706f52c60df75fa9e4277c978929", self.base)
        self.assertEqual("fff94ce52ffb1fbc0ac563aa1c20eeed1c1edc7a", self.pr_head)
        self.assertEqual("eb94ea2e5e2427b492b77948b6e53c9ddf2d709d", self.integration)
        self.assertEqual(5, self.pr_number)

    def test_exact_hosted_boundary_is_accepted(self) -> None:
        payload = {"merge_records": [self.merge_record], "ci_runs": [self.ci_run]}
        self.assertTrue(self._boundary_valid(payload))

    def test_every_hosted_identity_mutation_is_rejected(self) -> None:
        mutations = {
            "repository": "other/repository",
            "integration_sha": "0" * 40,
            "merge_commit_sha": "0" * 40,
            "merged": False,
            "merge_method": "squash",
            "pr_number": 6,
            "pr_head_sha": "1" * 40,
            "base_sha": "2" * 40,
            "base_ref": "develop",
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                record = copy.deepcopy(self.merge_record)
                record[field] = value
                payload = {"merge_records": [record], "ci_runs": [self.ci_run]}
                self.assertFalse(self._boundary_valid(payload))

    def test_duplicate_merge_records_are_rejected(self) -> None:
        payload = {
            "merge_records": [self.merge_record, copy.deepcopy(self.merge_record)],
            "ci_runs": [self.ci_run],
        }
        self.assertFalse(self._boundary_valid(payload))

    def test_parent_order_is_exact(self) -> None:
        payload = {"merge_records": [self.merge_record], "ci_runs": [self.ci_run]}
        self.assertFalse(self._boundary_valid(payload, parents=[self.pr_head, self.base]))

    def test_ci_identity_mutations_are_rejected(self) -> None:
        mutations = {
            "commit_sha": "3" * 40,
            "workflow_name": "Decoy validation",
            "event": "push",
            "conclusion": "failure",
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                ci_run = copy.deepcopy(self.ci_run)
                ci_run[field] = value
                payload = {"merge_records": [self.merge_record], "ci_runs": [ci_run]}
                self.assertFalse(self._boundary_valid(payload))

    def test_unchanged_first_parent_descendant_is_recognized(self) -> None:
        commit = "4" * 40
        head = "5" * 40
        completed = subprocess.CompletedProcess([], 0, "", "")

        def value(_root: Path, *args: str) -> str | None:
            if args == ("rev-parse", "HEAD"):
                return head
            if args[:2] == ("rev-list", "--first-parent"):
                return commit
            return None

        with (
            patch.object(followup, "_value", side_effect=value),
            patch.object(followup, "_git", return_value=completed),
        ):
            self.assertTrue(followup._unchanged_reconciliation_descendant(self.root, commit))

    def test_changed_or_unrelated_descendant_is_rejected(self) -> None:
        commit = "4" * 40
        head = "5" * 40

        def value_without_commit(_root: Path, *args: str) -> str | None:
            if args == ("rev-parse", "HEAD"):
                return head
            if args[:2] == ("rev-list", "--first-parent"):
                return "6" * 40
            return None

        with patch.object(followup, "_value", side_effect=value_without_commit):
            self.assertFalse(followup._unchanged_reconciliation_descendant(self.root, commit))

        def value_with_commit(_root: Path, *args: str) -> str | None:
            if args == ("rev-parse", "HEAD"):
                return head
            if args[:2] == ("rev-list", "--first-parent"):
                return commit
            return None

        changed = subprocess.CompletedProcess([], 1, "", "")
        with (
            patch.object(followup, "_value", side_effect=value_with_commit),
            patch.object(followup, "_git", return_value=changed),
        ):
            self.assertFalse(followup._unchanged_reconciliation_descendant(self.root, commit))

        self.assertFalse(followup._unchanged_reconciliation_descendant(self.root, "not-a-sha"))

    def test_only_exact_known_messages_are_suppressed(self) -> None:
        descendant = "4" * 40
        exact = [
            ValidationIssue(
                "PFV-036",
                f"integration {self.integration} does not integrate the canonical active Task at merge_pending",
            ),
            ValidationIssue(
                "PFV-086",
                f"historical integration {self.integration} lacks a successful exact-SHA push workflow",
            ),
            ValidationIssue(
                "PFV-035",
                f"task transition at {self.integration} disagrees with trusted prior state implementation_submitted",
            ),
            ValidationIssue(
                "PFV-086",
                f"task receipt at {self.integration} is malformed or mismatched",
            ),
            ValidationIssue(
                "PFV-086",
                f"task PF-001 historical receipt changed without a lifecycle transition at {descendant}",
            ),
        ]
        unrelated = [
            ValidationIssue("PFV-036", "integration deadbeef remains invalid"),
            ValidationIssue("PFV-087", "hosted Merge identity is inconsistent"),
            ValidationIssue(
                "PFV-086",
                "task OTHER historical receipt changed without a lifecycle transition at " + descendant,
            ),
        ]
        with (
            patch.object(followup, "_exact_repair_boundary_valid", return_value=False),
            patch.object(followup, "_exact_trust_boundary_valid", return_value=False),
            patch.object(followup, "_exact_reconciliation_boundary_valid", return_value=True),
            patch.object(followup, "_unchanged_reconciliation_descendant", return_value=True),
        ):
            self.assertEqual(unrelated, followup.apply_followup_bootstrap_compatibility(self.root, exact + unrelated))

    def test_changed_descendant_issue_is_not_suppressed(self) -> None:
        descendant = "4" * 40
        issue = ValidationIssue(
            "PFV-086",
            f"task PF-001 historical receipt changed without a lifecycle transition at {descendant}",
        )
        with (
            patch.object(followup, "_exact_repair_boundary_valid", return_value=False),
            patch.object(followup, "_exact_trust_boundary_valid", return_value=False),
            patch.object(followup, "_exact_reconciliation_boundary_valid", return_value=True),
            patch.object(followup, "_unchanged_reconciliation_descendant", return_value=False),
        ):
            self.assertEqual([issue], followup.apply_followup_bootstrap_compatibility(self.root, [issue]))

    def test_no_suppression_without_exact_boundary(self) -> None:
        issue = ValidationIssue(
            "PFV-036",
            f"integration {self.integration} does not integrate the canonical active Task at merge_pending",
        )
        with (
            patch.object(followup, "_exact_repair_boundary_valid", return_value=False),
            patch.object(followup, "_exact_trust_boundary_valid", return_value=False),
            patch.object(followup, "_exact_reconciliation_boundary_valid", return_value=False),
        ):
            self.assertEqual([issue], followup.apply_followup_bootstrap_compatibility(self.root, [issue]))


if __name__ == "__main__":
    unittest.main()
