from __future__ import annotations

import copy
import unittest
from typing import Any, Callable

from scripts.validation_semantics import load_and_validate_structures, validate_semantics
from tests.support import (
    REPO_ROOT,
    copy_repo,
    issue_codes,
    mutate_json,
    read_json,
    run_cli,
    write_json,
)


class SemanticReferenceTests(unittest.TestCase):
    def _assert_case(self, name: str, relative: str, mutate: Callable[[Any], None], expected: str) -> None:
        temporary, target = copy_repo()
        try:
            mutate_json(target, relative, mutate)
            codes = issue_codes(target)
            self.assertIn(expected, codes, name)
            self.assertNotIn("PFV-199", codes, name)
            result = run_cli(target)
            self.assertNotEqual(0, result.returncode)
            self.assertIn(expected, result.stderr)
            self.assertNotIn("PFV-199", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
        finally:
            temporary.cleanup()

    def test_reference_and_lifecycle_mutation_corpus(self) -> None:
        cases = [
            ("project_id", "planning/current-state.v1.json", lambda d: d.__setitem__("project_id", "OTHER"), "PFV-010"),
            ("north_star", "governance/project-constitution.v1.json", lambda d: d["north_star"].__setitem__("id", "OTHER"), "PFV-011"),
            ("north_binding", "planning/current-state.v1.json", lambda d: d.__setitem__("north_star_id", "OTHER"), "PFV-012"),
            ("duplicate_wp", "planning/execution-program.v1.json", lambda d: d["work_packages"].append(copy.deepcopy(d["work_packages"][0])), "PFV-020"),
            ("duplicate_task", "planning/execution-program.v1.json", lambda d: d["tasks"].append(copy.deepcopy(d["tasks"][0])), "PFV-021"),
            ("unknown_wp", "planning/execution-program.v1.json", lambda d: d["tasks"][0].__setitem__("work_package_id", "WP-404"), "PFV-022"),
            ("invalid_task_status", "planning/execution-program.v1.json", lambda d: d["tasks"][0].__setitem__("status", "BAD"), "PFV-023"),
            ("unknown_dep", "planning/execution-program.v1.json", lambda d: d["tasks"][0]["depends_on"].append("PF-404"), "PFV-024"),
            ("self_dep", "planning/execution-program.v1.json", lambda d: d["tasks"][0]["depends_on"].append("PF-001"), "PFV-025"),
            ("no_acceptance", "planning/execution-program.v1.json", lambda d: d["tasks"][0].__setitem__("acceptance_criteria", []), "PFV-026"),
            (
                "completion_no_evidence",
                "planning/execution-program.v1.json",
                lambda d: (
                    d["tasks"][0].__setitem__("status", "current_main_verified"),
                    d["tasks"][0].__setitem__("evidence_refs", []),
                ),
                "PFV-027",
            ),
            ("complete_state", "planning/execution-program.v1.json", lambda d: (d["tasks"][0].__setitem__("status", "complete"), d["tasks"][0].__setitem__("evidence_refs", ["e"])), "PFV-028"),
            ("wp_unknown_task", "planning/execution-program.v1.json", lambda d: d["work_packages"][0]["task_ids"].append("PF-404"), "PFV-029"),
            ("wp_link_mismatch", "planning/execution-program.v1.json", lambda d: d["work_packages"][0]["task_ids"].append("PF-010"), "PFV-030"),
            ("scope_unknown_wp", "planning/scope-baseline.v1.json", lambda d: d["included_work_package_ids"].append("WP-404"), "PFV-040"),
            ("scope_unknown_task", "planning/scope-baseline.v1.json", lambda d: d["included_task_ids"].append("PF-404"), "PFV-041"),
            ("active_outside", "planning/scope-baseline.v1.json", lambda d: d.__setitem__("active_task_id", "PF-010"), "PFV-042"),
            ("active_unknown", "planning/scope-baseline.v1.json", lambda d: (d["included_task_ids"].append("PF-404"), d.__setitem__("active_task_id", "PF-404")), "PFV-043"),
            ("state_scope_disagree", "planning/current-state.v1.json", lambda d: d.__setitem__("current_task_id", "PF-002"), "PFV-050"),
            ("current_outside", "planning/current-state.v1.json", lambda d: d.__setitem__("current_task_id", "PF-010"), "PFV-051"),
            ("status_drift", "planning/current-state.v1.json", lambda d: d.__setitem__("current_task_status", "planned"), "PFV-052"),
            ("context_drift", "planning/current-state.v1.json", lambda d: d["active_context_path"].__setitem__(2, "WP-02"), "PFV-053"),
            ("program_ref", "planning/current-state.v1.json", lambda d: d.__setitem__("program_ref", "STALE"), "PFV-054"),
            ("scope_ref", "planning/current-state.v1.json", lambda d: d.__setitem__("scope_ref", "STALE"), "PFV-055"),
            ("unknown_completed", "planning/current-state.v1.json", lambda d: d["completed_task_ids"].append("PF-404"), "PFV-056"),
            ("invalid_completed", "planning/current-state.v1.json", lambda d: d["completed_task_ids"].append("PF-002"), "PFV-057"),
            ("unknown_next", "planning/current-state.v1.json", lambda d: d.__setitem__("next_task_id", "PF-404"), "PFV-058"),
            ("unknown_current", "planning/current-state.v1.json", lambda d: d.__setitem__("current_task_id", "PF-404"), "PFV-059"),
        ]
        for name, relative, mutation, expected in cases:
            with self.subTest(case=name):
                self._assert_case(name, relative, mutation, expected)

    def test_semantic_validator_is_substantive(self) -> None:
        documents, issues = load_and_validate_structures(REPO_ROOT)
        self.assertEqual([], issues)
        mutated = copy.deepcopy(documents)
        mutated["planning/execution-program.v1.json"]["tasks"][0]["depends_on"].append("PF-404")
        self.assertIn("PFV-024", {issue.code for issue in validate_semantics(mutated)})


class DecisionIntelligenceTests(unittest.TestCase):
    def _assert_decision_case(self, index: int, mutation: Callable[[dict[str, Any]], None], expected: str) -> None:
        temporary, target = copy_repo()
        try:
            def mutate_registry(registry: dict[str, Any]) -> None:
                mutation(registry["decisions"][index])
            mutate_json(target, "decisions/decision-registry.v1.json", mutate_registry)
            codes = issue_codes(target)
            self.assertIn(expected, codes)
            self.assertNotIn("PFV-199", codes)
            result = run_cli(target)
            self.assertNotEqual(0, result.returncode)
            self.assertIn(expected, result.stderr)
            self.assertNotIn("PFV-199", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
        finally:
            temporary.cleanup()

    def test_accepted_and_research_decision_invariants(self) -> None:
        accepted = [
            (lambda d: d.__setitem__("status", "BAD"), "PFV-061"),
            (lambda d: d.pop("options_considered"), "PFV-066"),
            (lambda d: d.__setitem__("options_considered", ["only"]), "PFV-066"),
            (lambda d: d.__setitem__("selected_option", None), "PFV-067"),
            (lambda d: d.__setitem__("selected_option", "unconsidered"), "PFV-067"),
            (lambda d: d.__setitem__("rationale", ""), "PFV-068"),
            (lambda d: d.__setitem__("evidence_refs", []), "PFV-068"),
            (lambda d: d.__setitem__("reconsideration_triggers", []), "PFV-069"),
            (lambda d: d.__setitem__("hard_constraints", []), "PFV-064"),
            (lambda d: d["criteria_weights"].pop("ai_operability"), "PFV-063"),
            (lambda d: d["criteria_weights"].pop("owner_usability"), "PFV-063"),
            (lambda d: d["criteria_weights"].__setitem__("technical_fitness", 24), "PFV-062"),
        ]
        research = [
            (lambda d: d.pop("options_to_research"), "PFV-066"),
            (lambda d: d.__setitem__("options_to_research", ["only"]), "PFV-066"),
            (lambda d: d.__setitem__("selected_option", "manual"), "PFV-065"),
            (lambda d: d.__setitem__("rationale", "chosen"), "PFV-065"),
        ]
        for mutation, expected in accepted:
            with self.subTest(status="accepted", expected=expected):
                self._assert_decision_case(0, mutation, expected)
        for mutation, expected in research:
            with self.subTest(status="research", expected=expected):
                self._assert_decision_case(1, mutation, expected)

    def test_duplicate_decision_id(self) -> None:
        self._assert_decision_case(1, lambda d: d.__setitem__("id", "DEC-001"), "PFV-060")


class DogfoodingTests(unittest.TestCase):
    def test_dogfooding_reference_and_promotion_controls(self) -> None:
        cases = [
            (lambda d: d["lesson_candidates"][0]["observation_refs"].append("OBS-404"), "PFV-070"),
            (lambda d: d["promotions"][0].__setitem__("lesson_id", "LSN-404"), "PFV-071"),
            (lambda d: d["promotions"][0].__setitem__("evidence_refs", []), "PFV-072"),
            (lambda d: d["promotions"][0].__setitem__("status", "automatic"), "PFV-073"),
        ]
        for mutation, expected in cases:
            with self.subTest(expected=expected):
                temporary, target = copy_repo()
                try:
                    mutate_json(target, "dogfooding/dogfooding-registry.v1.json", mutation)
                    codes = issue_codes(target)
                    self.assertIn(expected, codes)
                    self.assertNotIn("PFV-199", codes)
                    result = run_cli(target)
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn(expected, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                finally:
                    temporary.cleanup()


class WorkflowHardeningTests(unittest.TestCase):
    @staticmethod
    def _prepare_non_evidence_fixture(target) -> None:
        program = read_json(target, "planning/execution-program.v1.json")
        program["tasks"][0]["status"] = "implementation_submitted"
        program["tasks"][0]["evidence_refs"] = []
        write_json(target, "planning/execution-program.v1.json", program)

        state = read_json(target, "planning/current-state.v1.json")
        state["current_task_status"] = "implementation_submitted"
        state["evidence_refs"] = []
        state["last_transition"] = {
            "from": "planned",
            "to": "implementation_submitted",
            "reason": "isolated workflow-hardening fixture",
            "evidence_refs": [],
        }
        write_json(target, "planning/current-state.v1.json", state)
        rendered = run_cli(target, "scripts/render_views.py", "--write")
        if rendered.returncode != 0:
            raise AssertionError(rendered.stderr)

    def _assert_workflow_drift(self, mutation: Callable[[str], str]) -> None:
        temporary, target = copy_repo()
        try:
            self._prepare_non_evidence_fixture(target)
            path = target / ".github/workflows/foundation-validation.yml"
            path.write_text(mutation(path.read_text(encoding="utf-8")), encoding="utf-8")
            self.assertIn("PFV-136", issue_codes(target))
            result = run_cli(target)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("PFV-136", result.stderr)
        finally:
            temporary.cleanup()

    def test_workflow_decoy_and_effective_bypass_corpus(self) -> None:
        mutations = [
            lambda t: t.replace("persist-credentials: false", "persist-credentials: true\n          # persist-credentials: false"),
            lambda t: t.replace("ref: ${{ github.event.pull_request.head.sha || github.sha }}", "ref: ${{ github.ref }}\n          # ref: ${{ github.event.pull_request.head.sha || github.sha }}", 1),
            lambda t: t.replace('test "$actual_sha" = "$EXPECTED_SHA"', 'echo "$actual_sha"\n          # test "$actual_sha" = "$EXPECTED_SHA"'),
            lambda t: t.replace("runs-on: ubuntu-latest", "permissions:\n      contents: write\n    runs-on: ubuntu-latest"),
            lambda t: t.replace("permissions:\n  contents: read", "permissions:\n  contents: read\npermissions:\n  contents: write"),
            lambda t: t.replace("persist-credentials: false", "persist-credentials: false\n        with:\n          persist-credentials: true"),
            lambda t: t.replace("      - name: Set up Python", "      - uses: actions/checkout@v6\n\n      - name: Set up Python"),
            lambda t: t.replace("uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1", "uses: actions/setup-python@v6"),
            lambda t: t.replace("      - name: Run deterministic repository validation", "      - name: Run deterministic repository validation\n        continue-on-error: true"),
            lambda t: t.replace("      - name: Verify exact checkout identity", "      - name: Verify exact checkout identity\n        if: false"),
            lambda t: t.replace("run: python scripts/validate_repository.py --root .", "run: echo skipped\n        # run: python scripts/validate_repository.py --root ."),
        ]
        for index, mutation in enumerate(mutations):
            with self.subTest(case=index):
                self._assert_workflow_drift(mutation)
