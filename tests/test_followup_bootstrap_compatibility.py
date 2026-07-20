from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.validation_bootstrap_followup import (
    REPAIR_INTEGRATION_COMMIT,
    apply_followup_bootstrap_compatibility,
)
from scripts.validation_core import ValidationIssue


class FollowupBootstrapCompatibilityTests(unittest.TestCase):
    def test_only_exact_known_false_positives_are_suppressed(self) -> None:
        issues = [
            ValidationIssue(
                "PFV-036",
                f"integration {REPAIR_INTEGRATION_COMMIT} does not integrate the canonical active Task at merge_pending",
            ),
            ValidationIssue(
                "PFV-086",
                f"historical integration {REPAIR_INTEGRATION_COMMIT} lacks a successful exact-SHA push workflow",
            ),
            ValidationIssue("PFV-036", "integration another-commit is invalid"),
        ]
        with patch(
            "scripts.validation_bootstrap_followup._exact_repair_boundary_valid",
            return_value=True,
        ):
            result = apply_followup_bootstrap_compatibility(Path("."), issues)
        self.assertEqual([ValidationIssue("PFV-036", "integration another-commit is invalid")], result)

    def test_nothing_is_suppressed_when_identity_proof_fails(self) -> None:
        issues = [ValidationIssue("PFV-036", "unrelated boundary")]
        with patch(
            "scripts.validation_bootstrap_followup._exact_repair_boundary_valid",
            return_value=False,
        ):
            result = apply_followup_bootstrap_compatibility(Path("."), issues)
        self.assertEqual(issues, result)


if __name__ == "__main__":
    unittest.main()
