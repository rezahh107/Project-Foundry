from __future__ import annotations

import argparse
import unittest
from unittest.mock import patch

from scripts import foundation_reconcile as reconcile


class MergePendingReceiptTests(unittest.TestCase):
    def test_merge_pending_preserves_the_branch_validation_receipt(self) -> None:
        receipt = {
            "verification_type": "branch_validation",
            "subject_sha": "a" * 40,
        }
        program = {
            "tasks": [
                {
                    "id": reconcile.TASK_ID,
                    "status": "validated_on_branch",
                    "evidence_refs": [receipt],
                }
            ]
        }
        with (
            patch.object(reconcile, "read_json", return_value=program),
            patch.object(reconcile, "set_status") as set_status,
        ):
            reconcile.command_merge_pending(argparse.Namespace())

        set_status.assert_called_once_with(
            "merge_pending",
            "validated_on_branch",
            "The exact PR Head has successful canonical CI and external hosted-provenance attestation.",
            [receipt],
            next_action="Merge this exact PR Head with the supported two-parent merge-commit method.",
        )

    def test_merge_pending_rejects_missing_or_wrong_receipt(self) -> None:
        cases = (
            [],
            [{"verification_type": "merge"}],
            [{"verification_type": "branch_validation"}, {"verification_type": "branch_validation"}],
        )
        for evidence in cases:
            with self.subTest(evidence=evidence):
                program = {
                    "tasks": [
                        {
                            "id": reconcile.TASK_ID,
                            "status": "validated_on_branch",
                            "evidence_refs": evidence,
                        }
                    ]
                }
                with (
                    patch.object(reconcile, "read_json", return_value=program),
                    patch.object(reconcile, "set_status") as set_status,
                    self.assertRaisesRegex(RuntimeError, "branch-validation receipt"),
                ):
                    reconcile.command_merge_pending(argparse.Namespace())
                set_status.assert_not_called()


if __name__ == "__main__":
    unittest.main()
