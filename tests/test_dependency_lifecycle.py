from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import Any, Callable

from tests.support import REPO_ROOT, copy_repo, issue_codes, read_json, run_subprocess_cli, write_json


def receipt(
    verification_type: str,
    subject_kind: str,
    subject_sha: str,
    transition_from: str,
    transition_to: str,
    *,
    ref: str = "refs/heads/main",
    repository: str = "rezahh107/Project-Foundry",
) -> dict[str, str]:
    return {
        "receipt_type": "git_history_attestation",
        "verification_type": verification_type,
        "subject_kind": subject_kind,
        "repository": repository,
        "ref": ref,
        "subject_sha": subject_sha,
        "transition_from": transition_from,
        "transition_to": transition_to,
    }


class RepairTestBase(unittest.TestCase):
    def assert_invalid(self, mutation: Callable[[Path], None], expected: str) -> None:
        temporary, target = copy_repo()
        try:
            mutation(target)
            codes = issue_codes(target)
            self.assertIn(expected, codes)
            self.assertNotIn("PFV-199", codes)
            result = run_subprocess_cli(target, "scripts/validate_repository.py")
            self.assertNotEqual(0, result.returncode)
            self.assertIn(expected, result.stderr)
            self.assertNotIn("PFV-199", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
        finally:
            temporary.cleanup()

    @staticmethod
    def mutate_program(root: Path, mutator: Callable[[dict[str, Any]], None]) -> None:
        program = read_json(root, "planning/execution-program.v1.json")
        mutator(program)
        write_json(root, "planning/execution-program.v1.json", program)

    @staticmethod
    def mutate_state(root: Path, mutator: Callable[[dict[str, Any]], None]) -> None:
        state = read_json(root, "planning/current-state.v1.json")
        mutator(state)
        write_json(root, "planning/current-state.v1.json", state)

    @staticmethod
    def task(program: dict[str, Any], task_id: str) -> dict[str, Any]:
        return next(task for task in program["tasks"] if task["id"] == task_id)


class DependencyGraphAcyclicityTests(RepairTestBase):
    def test_two_and_three_task_cycles_fail(self) -> None:
        def two_cycle(root: Path) -> None:
            self.mutate_program(root, lambda program: self.task(program, "PF-001").__setitem__("depends_on", ["PF-003"]))

        def three_cycle(root: Path) -> None:
            def mutate(program: dict[str, Any]) -> None:
                self.task(program, "PF-010")["depends_on"] = ["PF-020"]
                self.task(program, "PF-020")["depends_on"] = ["PF-030"]
                self.task(program, "PF-030")["depends_on"] = ["PF-010"]
            self.mutate_program(root, mutate)

        for mutation in [two_cycle, three_cycle]:
            with self.subTest(mutation=mutation.__name__):
                self.assert_invalid(mutation, "PFV-032")


class DependencySatisfactionTests(RepairTestBase):
    def test_progressed_task_requires_verified_dependencies(self) -> None:
        def mutate(root: Path, dependency_status: str, task_status: str) -> None:
            program = read_json(root, "planning/execution-program.v1.json")
            self.task(program, "PF-001")["status"] = dependency_status
            self.task(program, "PF-002")["status"] = task_status
            write_json(root, "planning/execution-program.v1.json", program)

        for dependency_status, task_status in [("planned", "active"), ("implementation_submitted", "active"), ("implementation_submitted", "eligible")]:
            with self.subTest(dependency=dependency_status, task=task_status):
                self.assert_invalid(lambda root, d=dependency_status, s=task_status: mutate(root, d, s), "PFV-033")

    def test_planned_future_task_may_retain_unresolved_dependencies(self) -> None:
        self.assertNotIn("PFV-033", issue_codes(REPO_ROOT))


class NextTaskDispatchTests(RepairTestBase):
    def test_unsafe_next_task_mutations(self) -> None:
        self.assert_invalid(lambda root: self.mutate_state(root, lambda state: state.__setitem__("next_task_id", "PF-090")), "PFV-046")
        self.assert_invalid(lambda root: self.mutate_state(root, lambda state: state.__setitem__("next_task_id", "PF-002")), "PFV-046")

    def test_current_unfinished_task_is_valid_next_task(self) -> None:
        self.assertEqual(set(), issue_codes(REPO_ROOT))


class LifecycleTransitionTests(RepairTestBase):
    def test_transition_target_and_edge_are_enforced(self) -> None:
        self.assert_invalid(lambda root: self.mutate_state(root, lambda state: state["last_transition"].__setitem__("to", "active")), "PFV-034")

    def test_legacy_current_main_self_assertion_is_rejected(self) -> None:
        def mutate(root: Path) -> None:
            program = read_json(root, "planning/execution-program.v1.json")
            task = self.task(program, "PF-001")
            task["status"] = "current_main_verified"
            task["evidence_refs"] = ["claim"]
            write_json(root, "planning/execution-program.v1.json", program)
            state = read_json(root, "planning/current-state.v1.json")
            state["current_task_status"] = "current_main_verified"
            state["completed_task_ids"] = ["PF-001"]
            state["next_task_id"] = "PF-002"
            state["evidence_refs"] = ["claim"]
            state["last_transition"] = {"from": "merged", "to": "current_main_verified", "reason": "claim", "evidence_refs": ["claim"]}
            write_json(root, "planning/current-state.v1.json", state)
        self.assert_invalid(mutate, "PFV-085")


class ExactMainEvidenceTests(RepairTestBase):
    def test_malformed_or_unverifiable_receipts_fail(self) -> None:
        sha = "1" * 40

        def claim(root: Path, evidence: list[Any]) -> None:
            program = read_json(root, "planning/execution-program.v1.json")
            task = self.task(program, "PF-001")
            task["status"] = "current_main_verified"
            task["evidence_refs"] = evidence
            write_json(root, "planning/execution-program.v1.json", program)
            state = read_json(root, "planning/current-state.v1.json")
            state["current_task_status"] = "current_main_verified"
            state["completed_task_ids"] = ["PF-001"]
            state["next_task_id"] = "PF-002"
            state["evidence_refs"] = evidence
            state["last_transition"] = {"from": "merged", "to": "current_main_verified", "reason": "test", "evidence_refs": evidence}
            write_json(root, "planning/current-state.v1.json", state)

        cases = [
            ["claim"],
            [receipt("current_main", "verified_main_state", "bad", "merged", "current_main_verified")],
            [receipt("current_main", "verified_main_state", sha, "merged", "current_main_verified")],
        ]
        for evidence in cases:
            with self.subTest(evidence=evidence):
                self.assert_invalid(lambda root, evidence=evidence: claim(root, evidence), "PFV-085")


class ProgressCollectionClosureTests(RepairTestBase):
    def test_completed_and_blocked_collections_are_closed(self) -> None:
        self.assert_invalid(lambda root: self.mutate_state(root, lambda state: state["blocked_task_ids"].append("PF-404")), "PFV-083")
        self.assert_invalid(lambda root: self.mutate_state(root, lambda state: state["blocked_task_ids"].append("PF-002")), "PFV-083")

    def test_valid_blocked_task_has_blocker_information(self) -> None:
        temporary, target = copy_repo()
        try:
            program = read_json(target, "planning/execution-program.v1.json")
            task = self.task(program, "PF-002")
            task["status"] = "blocked"
            task["blocker"] = {"code": "BLOCK-TEST", "reason": "bounded test blocker", "evidence_refs": ["OBS-TEST"]}
            write_json(target, "planning/execution-program.v1.json", program)
            state = read_json(target, "planning/current-state.v1.json")
            state["blocked_task_ids"] = ["PF-002"]
            write_json(target, "planning/current-state.v1.json", state)
            self.assertEqual(set(), issue_codes(target))
        finally:
            temporary.cleanup()


class NextWorkDispatchRenderingTests(unittest.TestCase):
    def test_next_task_identity_title_and_action_are_rendered(self) -> None:
        state = read_json(REPO_ROOT, "planning/current-state.v1.json")
        program = read_json(REPO_ROOT, "planning/execution-program.v1.json")
        task = next(item for item in program["tasks"] if item["id"] == state["next_task_id"])
        rendered = (REPO_ROOT / "planning/NEXT_WORK.md").read_text(encoding="utf-8")
        section = rendered.split("## Task بعدی canonical", 1)[1].split("## دستور عملی بعدی", 1)[0]
        self.assertRegex(section, rf"شناسه: `{re.escape(task['id'])}`")
        self.assertIn(f"عنوان: {task['title']}", section)
        self.assertIn(state["next_action"], rendered)
