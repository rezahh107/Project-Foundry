from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import Any, Callable

from tests.support import (
    REPO_ROOT,
    copy_repo,
    issue_codes,
    read_json,
    run_subprocess_cli,
    write_json,
)

MAIN_SHA = "d197447598d7108c44e79fbaa57d71e529930052"
PR_HEAD_SHA = "dc54ee5e24a1420bfe2bb81b0bc8c8733a4f32aa"
SYNTHETIC_MERGE_SHA = "4a0fcf3a465fb28cc68b9eac1c5aba5bc94bb839"
STALE_MAIN_SHA = "1111111111111111111111111111111111111111"


def evidence(commit_sha: str = MAIN_SHA, *, ref: str = "refs/heads/main") -> dict[str, str]:
    return {
        "verification_type": "current_main",
        "repository": "rezahh107/Project-Foundry",
        "ref": ref,
        "commit_sha": commit_sha,
    }


class RepairTestBase(unittest.TestCase):
    def assert_invalid(
        self,
        mutation: Callable[[Path], None],
        expected: str,
        *,
        current_main_sha: str | None = None,
    ) -> None:
        temporary, target = copy_repo()
        try:
            mutation(target)
            codes = issue_codes(target, current_main_sha=current_main_sha)
            self.assertIn(expected, codes)
            self.assertNotIn("PFV-199", codes)
            result = run_subprocess_cli(
                target,
                "scripts/validate_repository.py",
                current_main_sha=current_main_sha,
            )
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

    def set_current_task(
        self,
        root: Path,
        task_id: str,
        status: str,
        *,
        transition_from: str = "planned",
    ) -> None:
        program = read_json(root, "planning/execution-program.v1.json")
        task = self.task(program, task_id)
        task["status"] = status
        write_json(root, "planning/execution-program.v1.json", program)
        scope = read_json(root, "planning/scope-baseline.v1.json")
        scope["active_task_id"] = task_id
        write_json(root, "planning/scope-baseline.v1.json", scope)
        state = read_json(root, "planning/current-state.v1.json")
        state["current_task_id"] = task_id
        state["current_task_status"] = status
        state["next_task_id"] = task_id
        state["active_context_path"] = [
            "PF-NORTH-STAR-001",
            "PF-PROGRAM-001",
            task["work_package_id"],
            task_id,
        ]
        state["last_transition"] = {
            "from": transition_from,
            "to": status,
            "reason": "test mutation",
            "evidence_refs": [],
        }
        write_json(root, "planning/current-state.v1.json", state)

    def set_current_main_claim(
        self,
        root: Path,
        task_evidence: list[Any],
        *,
        state_evidence: list[Any] | None = None,
        transition_evidence: list[Any] | None = None,
        transition_from: str = "merged",
        transition_to: str = "current_main_verified",
        include_completed: bool = True,
    ) -> None:
        program = read_json(root, "planning/execution-program.v1.json")
        task = self.task(program, "PF-001")
        task["status"] = "current_main_verified"
        task["evidence_refs"] = task_evidence
        write_json(root, "planning/execution-program.v1.json", program)
        state = read_json(root, "planning/current-state.v1.json")
        state["current_task_status"] = "current_main_verified"
        state["completed_task_ids"] = ["PF-001"] if include_completed else []
        state["evidence_refs"] = task_evidence if state_evidence is None else state_evidence
        state["last_transition"] = {
            "from": transition_from,
            "to": transition_to,
            "reason": "exact-main verification",
            "evidence_refs": task_evidence if transition_evidence is None else transition_evidence,
        }
        state["next_task_id"] = "PF-002"
        write_json(root, "planning/current-state.v1.json", state)


class DependencyGraphAcyclicityTests(RepairTestBase):
    def test_two_and_three_task_cycles_fail(self) -> None:
        def two_cycle(root: Path) -> None:
            self.mutate_program(
                root,
                lambda program: self.task(program, "PF-001").__setitem__("depends_on", ["PF-003"]),
            )

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
        def make_active(root: Path, dependency_status: str, task_status: str) -> None:
            program = read_json(root, "planning/execution-program.v1.json")
            self.task(program, "PF-001")["status"] = dependency_status
            self.task(program, "PF-002")["status"] = task_status
            write_json(root, "planning/execution-program.v1.json", program)
            self.set_current_task(root, "PF-002", task_status)

        cases = [
            ("planned", "active"),
            ("implementation_submitted", "active"),
            ("implementation_submitted", "eligible"),
        ]
        for dependency_status, task_status in cases:
            with self.subTest(dependency=dependency_status, task=task_status):
                self.assert_invalid(
                    lambda root, d=dependency_status, s=task_status: make_active(root, d, s),
                    "PFV-033",
                )

    def test_planned_future_task_may_retain_unresolved_dependencies(self) -> None:
        self.assertNotIn("PFV-033", issue_codes(REPO_ROOT))


class NextTaskDispatchTests(RepairTestBase):
    def test_unsafe_next_task_mutations(self) -> None:
        self.assert_invalid(
            lambda root: self.mutate_state(root, lambda state: state.__setitem__("next_task_id", "PF-090")),
            "PFV-046",
        )
        self.assert_invalid(
            lambda root: self.mutate_state(root, lambda state: state.__setitem__("next_task_id", "PF-002")),
            "PFV-046",
        )

    def test_current_unfinished_task_is_valid_next_task(self) -> None:
        self.assertEqual(set(), issue_codes(REPO_ROOT))

    def test_dependency_ready_successor_is_valid(self) -> None:
        temporary, target = copy_repo()
        try:
            self.set_current_main_claim(target, [evidence()])
            rendered = run_subprocess_cli(
                target,
                "scripts/render_views.py",
                "--write",
                current_main_sha=MAIN_SHA,
            )
            self.assertEqual(0, rendered.returncode, rendered.stderr)
            self.assertEqual(set(), issue_codes(target, current_main_sha=MAIN_SHA))
            result = run_subprocess_cli(
                target,
                "scripts/validate_repository.py",
                current_main_sha=MAIN_SHA,
            )
            self.assertEqual(0, result.returncode, result.stderr)
        finally:
            temporary.cleanup()


class LifecycleTransitionTests(RepairTestBase):
    def test_transition_target_and_edge_are_enforced(self) -> None:
        self.assert_invalid(
            lambda root: self.mutate_state(root, lambda state: state["last_transition"].__setitem__("to", "active")),
            "PFV-034",
        )
        self.assert_invalid(
            lambda root: self.set_current_main_claim(
                root,
                [evidence()],
                transition_from="planned",
                transition_to="current_main_verified",
            ),
            "PFV-034",
            current_main_sha=MAIN_SHA,
        )


class ExactMainEvidenceTests(RepairTestBase):
    def test_invalid_exact_main_evidence(self) -> None:
        cases: list[tuple[str, Callable[[Path], None], str | None]] = [
            ("arbitrary_string", lambda root: self.set_current_main_claim(root, ["claim"]), MAIN_SHA),
            ("malformed_sha", lambda root: self.set_current_main_claim(root, [evidence("bad")]), MAIN_SHA),
            ("pr_head", lambda root: self.set_current_main_claim(root, [evidence(PR_HEAD_SHA)]), MAIN_SHA),
            ("synthetic_merge", lambda root: self.set_current_main_claim(root, [evidence(SYNTHETIC_MERGE_SHA)]), MAIN_SHA),
            ("stale_main", lambda root: self.set_current_main_claim(root, [evidence(STALE_MAIN_SHA)]), MAIN_SHA),
            ("missing_state", lambda root: self.set_current_main_claim(root, [evidence()], state_evidence=[]), MAIN_SHA),
            ("missing_transition", lambda root: self.set_current_main_claim(root, [evidence()], transition_evidence=[]), MAIN_SHA),
            (
                "mismatched_evidence",
                lambda root: self.set_current_main_claim(root, [evidence()], state_evidence=[evidence(STALE_MAIN_SHA)]),
                MAIN_SHA,
            ),
        ]
        for name, mutation, trusted in cases:
            with self.subTest(case=name):
                self.assert_invalid(mutation, "PFV-082", current_main_sha=trusted)

    def test_valid_exact_main_record(self) -> None:
        temporary, target = copy_repo()
        try:
            self.set_current_main_claim(target, [evidence()])
            rendered = run_subprocess_cli(
                target,
                "scripts/render_views.py",
                "--write",
                current_main_sha=MAIN_SHA,
            )
            self.assertEqual(0, rendered.returncode, rendered.stderr)
            self.assertEqual(set(), issue_codes(target, current_main_sha=MAIN_SHA))
        finally:
            temporary.cleanup()


class ProgressCollectionClosureTests(RepairTestBase):
    def test_completed_and_blocked_collections_are_closed(self) -> None:
        self.assert_invalid(
            lambda root: self.set_current_main_claim(root, [evidence()], include_completed=False),
            "PFV-083",
            current_main_sha=MAIN_SHA,
        )
        self.assert_invalid(
            lambda root: self.mutate_state(root, lambda state: state["blocked_task_ids"].append("PF-404")),
            "PFV-083",
        )
        self.assert_invalid(
            lambda root: self.mutate_state(root, lambda state: state["blocked_task_ids"].append("PF-002")),
            "PFV-083",
        )

        def both_completed_and_blocked(root: Path) -> None:
            self.set_current_main_claim(root, [evidence()])
            self.mutate_state(root, lambda state: state["blocked_task_ids"].append("PF-001"))

        self.assert_invalid(both_completed_and_blocked, "PFV-083", current_main_sha=MAIN_SHA)

    def test_valid_blocked_task_has_blocker_information(self) -> None:
        temporary, target = copy_repo()
        try:
            program = read_json(target, "planning/execution-program.v1.json")
            task = self.task(program, "PF-002")
            task["status"] = "blocked"
            task["blocker"] = {
                "code": "BLOCK-TEST",
                "reason": "bounded test blocker",
                "evidence_refs": ["OBS-TEST"],
            }
            write_json(target, "planning/execution-program.v1.json", program)
            state = read_json(target, "planning/current-state.v1.json")
            state["blocked_task_ids"] = ["PF-002"]
            write_json(target, "planning/current-state.v1.json", state)
            rendered = run_subprocess_cli(target, "scripts/render_views.py", "--write")
            self.assertEqual(0, rendered.returncode, rendered.stderr)
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
