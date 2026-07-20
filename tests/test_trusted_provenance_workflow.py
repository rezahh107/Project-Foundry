from __future__ import annotations

import unittest

from scripts.render_trusted_workflow import (
    TRUSTED_ATTESTOR_PIN,
    TRUSTED_WORKFLOW_PATH,
    render_trusted_provenance_workflow,
)
from scripts.validation_workflow import validate_workflow
from tests.support import REPO_ROOT, copy_repo


class TrustedProvenanceWorkflowTests(unittest.TestCase):
    def test_exact_renderer_parity(self) -> None:
        actual = (REPO_ROOT / TRUSTED_WORKFLOW_PATH).read_text(encoding="utf-8")
        self.assertEqual(render_trusted_provenance_workflow(), actual)

    def test_external_attestor_is_exact_sha_pinned(self) -> None:
        workflow = render_trusted_provenance_workflow()
        self.assertEqual(40, len(TRUSTED_ATTESTOR_PIN))
        self.assertIn(
            f"uses: rezahh107/Post-Merge-Auditor/attestors/project_foundry_v1@{TRUSTED_ATTESTOR_PIN}",
            workflow,
        )
        self.assertNotIn("@main", workflow)

    def test_trusted_workflow_does_not_execute_target_code(self) -> None:
        workflow = render_trusted_provenance_workflow()
        self.assertIn("workflow_run:", workflow)
        self.assertNotIn("actions/checkout", workflow)
        self.assertNotIn("python scripts/", workflow)
        self.assertNotIn("PROJECT_FOUNDRY_HOSTED_PROVENANCE_PATH", workflow)

    def test_permissions_are_read_only(self) -> None:
        workflow = render_trusted_provenance_workflow()
        self.assertIn("  actions: read\n", workflow)
        self.assertIn("  contents: read\n", workflow)
        self.assertIn("  pull-requests: read\n", workflow)
        self.assertNotIn(": write", workflow)

    def test_duplicate_foundation_name_is_rejected(self) -> None:
        temporary, target = copy_repo()
        try:
            (target / ".github/workflows/decoy.yml").write_text(
                "name: Foundation validation\n\non: pull_request\njobs: {}\n",
                encoding="utf-8",
            )
            issues = validate_workflow(target)
            self.assertIn("PFV-138", {issue.code for issue in issues})
        finally:
            temporary.cleanup()

    def test_duplicate_trusted_name_is_rejected(self) -> None:
        temporary, target = copy_repo()
        try:
            (target / ".github/workflows/decoy.yaml").write_text(
                "name: Trusted provenance\n\non: workflow_dispatch\njobs: {}\n",
                encoding="utf-8",
            )
            issues = validate_workflow(target)
            self.assertIn("PFV-138", {issue.code for issue in issues})
        finally:
            temporary.cleanup()

    def test_pin_or_contract_mutation_is_rejected(self) -> None:
        temporary, target = copy_repo()
        try:
            path = target / TRUSTED_WORKFLOW_PATH
            path.write_text(
                path.read_text(encoding="utf-8").replace(TRUSTED_ATTESTOR_PIN, "0" * 40),
                encoding="utf-8",
            )
            issues = validate_workflow(target)
            self.assertIn("PFV-137", {issue.code for issue in issues})
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
