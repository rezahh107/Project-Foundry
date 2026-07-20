from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import Any, Callable

from tests.support import (
    REPO_ROOT,
    copy_repo,
    current_validation_env,
    issue_codes,
    read_json,
    run_cli,
    write_json,
)


class ClosureTestBase(unittest.TestCase):
    def assert_invalid_repository(
        self,
        name: str,
        mutation: Callable[[Path], None],
        expected: str,
    ) -> None:
        temporary, target = copy_repo()
        try:
            mutation(target)
            codes = issue_codes(target)
            self.assertIn(expected, codes, name)
            self.assertNotIn("PFV-199", codes, name)
            result = run_cli(target)
            self.assertNotEqual(0, result.returncode, name)
            self.assertIn(expected, result.stderr, name)
            self.assertNotIn("PFV-199", result.stderr, name)
            self.assertNotIn("Traceback", result.stderr, name)
        finally:
            temporary.cleanup()

    @staticmethod
    def mutate_program(root: Path, mutator: Callable[[dict[str, Any]], None]) -> None:
        program = read_json(root, "planning/execution-program.v1.json")
        mutator(program)
        write_json(root, "planning/execution-program.v1.json", program)

    @staticmethod
    def mutate_scope_and_state(
        root: Path,
        scope_mutator: Callable[[dict[str, Any]], None],
        state_mutator: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        scope = read_json(root, "planning/scope-baseline.v1.json")
        scope_mutator(scope)
        write_json(root, "planning/scope-baseline.v1.json", scope)
        if state_mutator is not None:
            state = read_json(root, "planning/current-state.v1.json")
            state_mutator(state)
            write_json(root, "planning/current-state.v1.json", state)


class ProgramMembershipClosureTests(ClosureTestBase):
    @staticmethod
    def remove_membership(program: dict[str, Any], task_id: str, work_package_id: str) -> None:
        work_package = next(
            item for item in program["work_packages"] if item["id"] == work_package_id
        )
        work_package["task_ids"].remove(task_id)

    def test_program_membership_mutations(self) -> None:
        def orphan_pf061(program: dict[str, Any]) -> None:
            self.remove_membership(program, "PF-061", "WP-07")

        def orphan_pf060(program: dict[str, Any]) -> None:
            self.remove_membership(program, "PF-060", "WP-07")

        def list_only_under_wrong_work_package(program: dict[str, Any]) -> None:
            self.remove_membership(program, "PF-061", "WP-07")
            next(item for item in program["work_packages"] if item["id"] == "WP-08")[
                "task_ids"
            ].append("PF-061")

        def list_under_correct_and_wrong_work_packages(program: dict[str, Any]) -> None:
            next(item for item in program["work_packages"] if item["id"] == "WP-08")[
                "task_ids"
            ].append("PF-061")

        cases = [
            ("orphan_pf061", orphan_pf061),
            ("move_out_without_relisting", orphan_pf060),
            ("listed_only_under_wrong_work_package", list_only_under_wrong_work_package),
            ("listed_under_correct_and_wrong_work_packages", list_under_correct_and_wrong_work_packages),
        ]
        for name, mutation in cases:
            with self.subTest(case=name):
                self.assert_invalid_repository(
                    name,
                    lambda root, mutation=mutation: self.mutate_program(root, mutation),
                    "PFV-031",
                )

    def test_renderer_rejects_orphaned_program(self) -> None:
        temporary, target = copy_repo()
        try:
            self.mutate_program(
                target,
                lambda program: self.remove_membership(program, "PF-061", "WP-07"),
            )
            result = run_cli(target, "scripts/render_views.py", "--check")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("PFV-031", result.stderr)
            self.assertNotIn("PFV-199", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
        finally:
            temporary.cleanup()


class ScopeMembershipClosureTests(ClosureTestBase):
    def test_scope_membership_mutations(self) -> None:
        def append_pf010(root: Path) -> None:
            self.mutate_scope_and_state(
                root,
                lambda scope: scope["included_task_ids"].append("PF-010"),
            )

        def activate_pf010(root: Path) -> None:
            def scope_mutator(scope: dict[str, Any]) -> None:
                scope["included_task_ids"].append("PF-010")
                scope["active_task_id"] = "PF-010"

            def state_mutator(state: dict[str, Any]) -> None:
                state["current_task_id"] = "PF-010"
                state["current_task_status"] = "planned"
                state["active_context_path"] = [
                    "PF-NORTH-STAR-001",
                    "PF-PROGRAM-001",
                    "WP-02",
                    "PF-010",
                ]

            self.mutate_scope_and_state(root, scope_mutator, state_mutator)

        def set_task_scope_ref(root: Path, task_id: str, scope_ref: str) -> None:
            def mutator(program: dict[str, Any]) -> None:
                next(task for task in program["tasks"] if task["id"] == task_id)[
                    "scope_ref"
                ] = scope_ref

            self.mutate_program(root, mutator)

        def remove_active_work_package(root: Path) -> None:
            self.mutate_scope_and_state(
                root,
                lambda scope: scope.__setitem__("included_work_package_ids", ["WP-02"]),
            )

        cases = [
            ("future_task_added_without_work_package", append_pf010, "PFV-044"),
            ("future_task_made_active_without_work_package", activate_pf010, "PFV-044"),
            (
                "active_task_scope_ref_future",
                lambda root: set_task_scope_ref(root, "PF-001", "future_scope"),
                "PFV-045",
            ),
            (
                "included_task_scope_ref_stale",
                lambda root: set_task_scope_ref(root, "PF-002", "PF-SCOPE-001@0.0.9"),
                "PFV-045",
            ),
            ("active_work_package_removed", remove_active_work_package, "PFV-044"),
        ]
        for name, mutation, expected in cases:
            with self.subTest(case=name):
                self.assert_invalid_repository(name, mutation, expected)

    def test_future_scope_task_outside_active_scope_is_valid(self) -> None:
        program = read_json(REPO_ROOT, "planning/execution-program.v1.json")
        scope = read_json(REPO_ROOT, "planning/scope-baseline.v1.json")
        task = next(item for item in program["tasks"] if item["id"] == "PF-010")
        self.assertEqual("future_scope", task["scope_ref"])
        self.assertNotIn(task["id"], scope["included_task_ids"])
        self.assertNotIn(task["work_package_id"], scope["included_work_package_ids"])
        self.assertEqual(
            set(),
            issue_codes(REPO_ROOT, env=current_validation_env()),
        )


class RendererTaskSetCompletenessTests(unittest.TestCase):
    def test_rendered_task_sets_are_complete_and_scope_closed(self) -> None:
        program = read_json(REPO_ROOT, "planning/execution-program.v1.json")
        scope = read_json(REPO_ROOT, "planning/scope-baseline.v1.json")
        task_map = {task["id"]: task for task in program["tasks"]}

        system_map = (REPO_ROOT / "SYSTEM_MAP.md").read_text(encoding="utf-8")
        rendered_program_tasks = set(
            re.findall(r"^  - `(PF-[^`]+)` — ", system_map, flags=re.MULTILINE)
        )
        self.assertEqual(
            {task["id"] for task in program["tasks"]},
            rendered_program_tasks,
        )

        next_work = (REPO_ROOT / "planning/NEXT_WORK.md").read_text(encoding="utf-8")
        scoped_section = next_work.split("### Taskهای داخل Scope", 1)[1].split(
            "### موارد خارج از Scope فعلی", 1
        )[0]
        rendered_scope_tasks = set(re.findall(r"`(PF-[^`]+)`", scoped_section))
        self.assertEqual(set(scope["included_task_ids"]), rendered_scope_tasks)

        active_scope_ref = f"{scope['scope_id']}@{scope['scope_version']}"
        included_work_packages = set(scope["included_work_package_ids"])
        for task_id in rendered_scope_tasks:
            self.assertIn(task_map[task_id]["work_package_id"], included_work_packages)
            self.assertEqual(active_scope_ref, task_map[task_id]["scope_ref"])
