from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tests.support import REPO_ROOT, read_json, run_subprocess_cli, write_json


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def receipt(
    verification_type: str,
    subject_kind: str,
    subject_sha: str,
    transition_from: str,
    transition_to: str,
    ref: str,
) -> dict[str, str]:
    return {
        "receipt_type": "git_history_attestation",
        "verification_type": verification_type,
        "subject_kind": subject_kind,
        "repository": "rezahh107/Project-Foundry",
        "ref": ref,
        "subject_sha": subject_sha,
        "transition_from": transition_from,
        "transition_to": transition_to,
    }


class GitHistoryHarness:
    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "repo"
        shutil.copytree(
            REPO_ROOT,
            self.root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache"),
        )
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Project Foundry Test")
        git(self.root, "config", "user.email", "foundry@example.invalid")
        self.commit("baseline foundation")

    def close(self) -> None:
        self.temporary.cleanup()

    def commit(self, message: str) -> str:
        git(self.root, "add", "-A")
        git(self.root, "commit", "--allow-empty", "-m", message)
        return git(self.root, "rev-parse", "HEAD")

    def set_task_status(
        self,
        task_id: str,
        status: str,
        transition_from: str,
        evidence: list[Any] | None = None,
        *,
        make_current: bool = True,
    ) -> None:
        evidence = evidence or []
        program = read_json(self.root, "planning/execution-program.v1.json")
        task = next(item for item in program["tasks"] if item["id"] == task_id)
        task["status"] = status
        task["evidence_refs"] = evidence
        write_json(self.root, "planning/execution-program.v1.json", program)
        if make_current:
            scope = read_json(self.root, "planning/scope-baseline.v1.json")
            scope["active_task_id"] = task_id
            write_json(self.root, "planning/scope-baseline.v1.json", scope)
            state = read_json(self.root, "planning/current-state.v1.json")
            state["current_task_id"] = task_id
            state["current_task_status"] = status
            state["active_context_path"] = [
                "PF-NORTH-STAR-001",
                "PF-PROGRAM-001",
                task["work_package_id"],
                task_id,
            ]
            state["evidence_refs"] = evidence
            state["last_transition"] = {
                "from": transition_from,
                "to": status,
                "reason": "real Git integration transition",
                "evidence_refs": evidence,
            }
            if status == "current_main_verified":
                state["completed_task_ids"] = sorted(set(state["completed_task_ids"]) | {task_id})
                state["next_task_id"] = "PF-002"
            else:
                state["next_task_id"] = task_id
            write_json(self.root, "planning/current-state.v1.json", state)
        self.render()

    def render(self) -> None:
        result = run_subprocess_cli(self.root, "scripts/render_views.py", "--write", env=self.local_env())
        if result.returncode != 0:
            raise AssertionError(result.stderr)

    def local_env(self) -> dict[str, str]:
        head = git(self.root, "rev-parse", "HEAD")
        branch = git(self.root, "branch", "--show-current")
        return {
            "PROJECT_FOUNDRY_EVENT_NAME": "local",
            "PROJECT_FOUNDRY_EXPECTED_HEAD_SHA": head,
            "PROJECT_FOUNDRY_GITHUB_REF": f"refs/heads/{branch}",
        }

    def pr_env(self, *, synthetic: str = "") -> dict[str, str]:
        head = git(self.root, "rev-parse", "HEAD")
        base = git(self.root, "rev-parse", "main")
        branch = git(self.root, "branch", "--show-current")
        return {
            "PROJECT_FOUNDRY_EVENT_NAME": "pull_request",
            "PROJECT_FOUNDRY_EXPECTED_HEAD_SHA": head,
            "PROJECT_FOUNDRY_GITHUB_REF": "refs/pull/1/merge",
            "PROJECT_FOUNDRY_PR_HEAD_SHA": head,
            "PROJECT_FOUNDRY_PR_BASE_SHA": base,
            "PROJECT_FOUNDRY_PR_HEAD_REF": branch,
            "PROJECT_FOUNDRY_SYNTHETIC_MERGE_SHA": synthetic,
        }

    def push_env(self, before: str, **overrides: str) -> dict[str, str]:
        head = git(self.root, "rev-parse", "HEAD")
        env = {
            "PROJECT_FOUNDRY_EVENT_NAME": "push",
            "PROJECT_FOUNDRY_EXPECTED_HEAD_SHA": head,
            "PROJECT_FOUNDRY_GITHUB_REF": "refs/heads/main",
            "PROJECT_FOUNDRY_PUSH_BEFORE_SHA": before,
        }
        env.update(overrides)
        return env

    def validate(self, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return run_subprocess_cli(self.root, "scripts/validate_repository.py", env=env)


class GitProvenanceIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.h = GitHistoryHarness()

    def tearDown(self) -> None:
        self.h.close()

    def assert_pass(self, env: dict[str, str]) -> None:
        result = self.h.validate(env)
        self.assertEqual(0, result.returncode, result.stderr)

    def assert_fail(self, env: dict[str, str], code: str) -> None:
        result = self.h.validate(env)
        self.assertNotEqual(0, result.returncode)
        self.assertIn(code, result.stderr)
        self.assertNotIn("PFV-199", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def build_branch_validation(self) -> tuple[str, str]:
        self.h.set_task_status("PF-001", "validation_pending", "implementation_submitted")
        self.h.commit("validation pending")
        git(self.h.root, "checkout", "-b", "feature")
        subject = self.h.commit("branch subject")
        evidence = [
            receipt(
                "branch_validation",
                "pull_request_head",
                subject,
                "validation_pending",
                "validated_on_branch",
                "refs/heads/feature",
            )
        ]
        self.h.set_task_status("PF-001", "validated_on_branch", "validation_pending", evidence)
        attestation = self.h.commit("branch validation receipt")
        return subject, attestation

    def build_verified_main(self) -> tuple[str, str, str]:
        self.build_branch_validation()
        self.h.set_task_status("PF-001", "merge_pending", "validated_on_branch")
        self.h.commit("merge pending")
        git(self.h.root, "checkout", "main")
        git(self.h.root, "merge", "--no-ff", "feature", "-m", "merge implementation")
        merge_subject = git(self.h.root, "rev-parse", "HEAD")
        merge_evidence = [
            receipt(
                "merge",
                "main_merge_subject",
                merge_subject,
                "merge_pending",
                "merged",
                "refs/heads/main",
            )
        ]
        self.h.set_task_status("PF-001", "merged", "merge_pending", merge_evidence)
        merge_receipt = self.h.commit("merge receipt")
        self.assert_pass(self.h.push_env(merge_subject))
        main_evidence = [
            receipt(
                "current_main",
                "verified_main_state",
                merge_receipt,
                "merged",
                "current_main_verified",
                "refs/heads/main",
            )
        ]
        self.h.set_task_status("PF-001", "current_main_verified", "merged", main_evidence)
        verification_commit = self.h.commit("current main verification receipt")
        self.assert_pass(self.h.push_env(merge_receipt))
        return merge_subject, merge_receipt, verification_commit

    def test_valid_branch_merge_and_post_merge_sequence(self) -> None:
        subject, _ = self.build_branch_validation()
        self.assert_pass(self.h.pr_env())
        self.assertNotEqual(subject, git(self.h.root, "rev-parse", "HEAD"))

    def test_non_self_referential_main_verification_and_history_preservation(self) -> None:
        _, receipt_commit, verification_commit = self.build_verified_main()
        program = read_json(self.h.root, "planning/execution-program.v1.json")
        evidence = next(t for t in program["tasks"] if t["id"] == "PF-001")["evidence_refs"][0]
        self.assertEqual(receipt_commit, evidence["subject_sha"])
        self.assertNotEqual(verification_commit, evidence["subject_sha"])
        later_before = git(self.h.root, "rev-parse", "HEAD")
        (self.h.root / "docs" / "later.txt").write_text("later main commit\n", encoding="utf-8")
        self.h.commit("later main commit")
        self.assert_pass(self.h.push_env(later_before))

    def test_self_reference_placeholder_pr_head_base_synthetic_and_unrelated_are_rejected(self) -> None:
        self.build_verified_main()
        program = read_json(self.h.root, "planning/execution-program.v1.json")
        task = next(t for t in program["tasks"] if t["id"] == "PF-001")
        state = read_json(self.h.root, "planning/current-state.v1.json")
        invalid = [
            "0" * 40,
            git(self.h.root, "rev-parse", "HEAD"),
            git(self.h.root, "rev-parse", "HEAD^^"),
        ]
        for candidate in invalid:
            task["evidence_refs"][0]["subject_sha"] = candidate
            state["evidence_refs"][0]["subject_sha"] = candidate
            state["last_transition"]["evidence_refs"][0]["subject_sha"] = candidate
            write_json(self.h.root, "planning/execution-program.v1.json", program)
            write_json(self.h.root, "planning/current-state.v1.json", state)
            self.assert_fail(self.h.local_env(), "PFV-085")

    def test_branch_and_merge_evidence_tampering_is_rejected(self) -> None:
        subject, _ = self.build_branch_validation()
        program = read_json(self.h.root, "planning/execution-program.v1.json")
        task = next(t for t in program["tasks"] if t["id"] == "PF-001")
        state = read_json(self.h.root, "planning/current-state.v1.json")
        for field, value in [("repository", "other/repository"), ("ref", "refs/heads/main"), ("subject_sha", "1" * 40)]:
            task["evidence_refs"][0][field] = value
            state["evidence_refs"][0][field] = value
            state["last_transition"]["evidence_refs"][0][field] = value
            write_json(self.h.root, "planning/execution-program.v1.json", program)
            write_json(self.h.root, "planning/current-state.v1.json", state)
            self.assert_fail(self.h.pr_env(synthetic=subject), "PFV-084")

    def test_fabricated_prior_state_is_rejected(self) -> None:
        self.h.set_task_status("PF-001", "validation_pending", "implementation_submitted")
        self.h.commit("validation pending")
        state = read_json(self.h.root, "planning/current-state.v1.json")
        state["last_transition"]["from"] = "active"
        write_json(self.h.root, "planning/current-state.v1.json", state)
        self.assert_fail(self.h.local_env(), "PFV-035")

    def test_pf001_completion_makes_pf002_dispatch_eligible(self) -> None:
        self.build_verified_main()
        before = git(self.h.root, "rev-parse", "HEAD")
        program = read_json(self.h.root, "planning/execution-program.v1.json")
        pf002 = next(t for t in program["tasks"] if t["id"] == "PF-002")
        pf002["status"] = "eligible"
        pf002["evidence_refs"] = []
        write_json(self.h.root, "planning/execution-program.v1.json", program)
        scope = read_json(self.h.root, "planning/scope-baseline.v1.json")
        scope["active_task_id"] = "PF-002"
        write_json(self.h.root, "planning/scope-baseline.v1.json", scope)
        state = read_json(self.h.root, "planning/current-state.v1.json")
        state["current_task_id"] = "PF-002"
        state["current_task_status"] = "eligible"
        state["active_context_path"] = ["PF-NORTH-STAR-001", "PF-PROGRAM-001", "WP-01", "PF-002"]
        state["next_task_id"] = "PF-002"
        state["evidence_refs"] = []
        state["last_transition"] = {"from": "planned", "to": "eligible", "reason": "PF-001 verified", "evidence_refs": []}
        write_json(self.h.root, "planning/current-state.v1.json", state)
        self.h.render()
        self.h.commit("dispatch PF-002")
        self.assert_pass(self.h.push_env(before))


if __name__ == "__main__":
    unittest.main()
