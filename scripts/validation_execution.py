"""Dependency, dispatch, lifecycle, and evidence closure validation."""
from __future__ import annotations

import os
import re
from typing import Any

try:
    from scripts.validation_core import ValidationIssue, duplicates
except ModuleNotFoundError:
    from validation_core import ValidationIssue, duplicates

PROGRESSED_STATES = {
    "eligible", "active", "implementation_submitted", "validation_pending",
    "validated_on_branch", "merge_pending", "merged", "current_main_verified", "complete",
}
UNSUCCESSFUL_TERMINAL_STATES = {"blocked", "invalidated", "superseded"}
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "planned": {"eligible", "active", "implementation_submitted", "blocked", "invalidated", "superseded"},
    "eligible": {"active", "implementation_submitted", "blocked", "invalidated", "superseded"},
    "active": {"implementation_submitted", "blocked", "invalidated", "superseded"},
    "implementation_submitted": {"validation_pending", "validated_on_branch", "blocked", "invalidated", "superseded"},
    "validation_pending": {"validated_on_branch", "blocked", "invalidated", "superseded"},
    "validated_on_branch": {"merge_pending", "blocked", "invalidated", "superseded"},
    "merge_pending": {"merged", "blocked", "invalidated", "superseded"},
    "merged": {"current_main_verified", "blocked", "invalidated", "superseded"},
    "current_main_verified": {"current_main_verified"},
    "blocked": {"planned", "eligible", "active", "invalidated", "superseded"},
    "invalidated": {"planned", "superseded"},
    "superseded": set(),
    "complete": set(),
}
EVIDENCE_BEARING_STATES = {
    "validated_on_branch": "branch_validation",
    "merged": "merge",
    "current_main_verified": "current_main",
}
SHA40 = re.compile(r"^[0-9a-f]{40}$")
CANONICAL_REPOSITORY = "rezahh107/Project-Foundry"
MAIN_REF = "refs/heads/main"


def _first_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        result.setdefault(record["id"], record)
    return result


def _dependencies_satisfied(task: dict[str, Any], task_map: dict[str, dict[str, Any]]) -> bool:
    return all(
        dependency in task_map and task_map[dependency]["status"] == "current_main_verified"
        for dependency in task["depends_on"]
    )


def _find_cycle(task_map: dict[str, dict[str, Any]]) -> list[str] | None:
    color = {task_id: 0 for task_id in task_map}
    stack: list[str] = []
    positions: dict[str, int] = {}

    def visit(task_id: str) -> list[str] | None:
        color[task_id] = 1
        positions[task_id] = len(stack)
        stack.append(task_id)
        for dependency in task_map[task_id]["depends_on"]:
            if dependency not in task_map or dependency == task_id:
                continue
            if color[dependency] == 0:
                cycle = visit(dependency)
                if cycle:
                    return cycle
            elif color[dependency] == 1:
                return stack[positions[dependency]:] + [dependency]
        stack.pop()
        positions.pop(task_id, None)
        color[task_id] = 2
        return None

    for task_id in task_map:
        if color[task_id] == 0:
            cycle = visit(task_id)
            if cycle:
                return cycle
    return None


def _evidence_key(record: Any) -> tuple[str, str, str, str] | None:
    if not isinstance(record, dict):
        return None
    fields = ("verification_type", "repository", "ref", "commit_sha")
    if set(record) != set(fields) or not all(isinstance(record.get(field), str) for field in fields):
        return None
    return tuple(record[field] for field in fields)  # type: ignore[return-value]


def _evidence_set(records: list[Any]) -> set[tuple[str, str, str, str]] | None:
    keys = [_evidence_key(record) for record in records]
    if any(key is None for key in keys):
        return None
    return set(keys)  # type: ignore[arg-type]


def _valid_current_main(records: list[Any], trusted_main_sha: str | None) -> bool:
    evidence = _evidence_set(records)
    if not evidence or not trusted_main_sha or SHA40.fullmatch(trusted_main_sha) is None:
        return False
    return all(
        verification_type == "current_main"
        and repository == CANONICAL_REPOSITORY
        and ref == MAIN_REF
        and SHA40.fullmatch(commit_sha) is not None
        and commit_sha == trusted_main_sha
        for verification_type, repository, ref, commit_sha in evidence
    )


def validate_execution_controls(
    documents: dict[str, dict[str, Any]],
    *,
    current_main_sha: str | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    program = documents["planning/execution-program.v1.json"]
    scope = documents["planning/scope-baseline.v1.json"]
    state = documents["planning/current-state.v1.json"]
    tasks = program["tasks"]
    task_ids = [task["id"] for task in tasks]
    task_map = _first_by_id(tasks)
    trusted_main_sha = current_main_sha or os.environ.get("PROJECT_FOUNDRY_CURRENT_MAIN_SHA")

    if not duplicates(task_ids):
        cycle = _find_cycle(task_map)
        if cycle:
            issues.append(ValidationIssue("PFV-032", f"dependency graph contains a cycle: {' -> '.join(cycle)}"))
    for task in tasks:
        if task["status"] in PROGRESSED_STATES and not _dependencies_satisfied(task, task_map):
            issues.append(ValidationIssue("PFV-033", f"task {task['id']} progressed while a dependency is unsatisfied"))

    active_scope_ref = f"{scope['scope_id']}@{scope['scope_version']}"
    included_tasks = set(scope["included_task_ids"])
    included_work_packages = set(scope["included_work_package_ids"])
    current_task = task_map.get(state["current_task_id"])
    next_task = task_map.get(state["next_task_id"])
    if next_task is not None:
        next_is_scoped = (
            next_task["id"] in included_tasks
            and next_task["work_package_id"] in included_work_packages
            and next_task["scope_ref"] == active_scope_ref
        )
        ready = _dependencies_satisfied(next_task, task_map)
        if next_task["id"] == state["current_task_id"]:
            ready = ready and next_task["status"] not in (
                UNSUCCESSFUL_TERMINAL_STATES | {"current_main_verified", "complete"}
            )
        else:
            ready = (
                ready
                and current_task is not None
                and current_task["status"] == "current_main_verified"
                and next_task["status"] in {"planned", "eligible"}
            )
        if not next_is_scoped or not ready:
            issues.append(ValidationIssue("PFV-046", f"next task {next_task['id']} is outside active Scope or is not dispatch-eligible"))

    transition = state["last_transition"]
    if current_task is not None:
        status = current_task["status"]
        if transition["to"] != state["current_task_status"] or state["current_task_status"] != status:
            issues.append(ValidationIssue("PFV-034", "last transition target, current state, and Task status must agree"))
        if transition["to"] not in ALLOWED_TRANSITIONS.get(transition["from"], set()):
            issues.append(ValidationIssue("PFV-034", f"illegal lifecycle transition {transition['from']} -> {transition['to']}"))
        expected_type = EVIDENCE_BEARING_STATES.get(status)
        if expected_type is not None:
            task_evidence = _evidence_set(current_task["evidence_refs"])
            state_evidence = _evidence_set(state["evidence_refs"])
            transition_evidence = _evidence_set(transition["evidence_refs"])
            if not task_evidence or task_evidence != state_evidence or task_evidence != transition_evidence:
                issues.append(ValidationIssue("PFV-082", "Task, state, and transition evidence must be non-empty and identical"))
            elif any(item[0] != expected_type for item in task_evidence):
                issues.append(ValidationIssue("PFV-082", f"evidence type must be {expected_type}"))
            elif status == "current_main_verified" and not _valid_current_main(
                current_task["evidence_refs"], trusted_main_sha
            ):
                issues.append(ValidationIssue("PFV-082", "current-main evidence is malformed, stale, or not bound to exact main"))

    completed = set(state["completed_task_ids"])
    blocked = set(state["blocked_task_ids"])
    known = set(task_map)
    if blocked - known:
        issues.append(ValidationIssue("PFV-083", f"blocked collection contains unknown task(s): {sorted(blocked - known)}"))
    if completed & blocked:
        issues.append(ValidationIssue("PFV-083", f"tasks cannot be both completed and blocked: {sorted(completed & blocked)}"))
    verified_ids = {task["id"] for task in tasks if task["status"] == "current_main_verified"}
    blocked_ids = {task["id"] for task in tasks if task["status"] == "blocked"}
    if verified_ids - completed:
        issues.append(ValidationIssue("PFV-083", f"verified tasks omitted from completed collection: {sorted(verified_ids - completed)}"))
    if blocked != blocked_ids:
        issues.append(ValidationIssue("PFV-083", "blocked collection must exactly match Tasks with blocked status"))

    for task in tasks:
        if task["status"] == "current_main_verified" and not _valid_current_main(
            task["evidence_refs"], trusted_main_sha
        ):
            issues.append(ValidationIssue("PFV-082", f"task {task['id']} lacks valid exact-main evidence"))
        blocker = task.get("blocker")
        if task["status"] == "blocked":
            valid = (
                isinstance(blocker, dict)
                and isinstance(blocker.get("code"), str)
                and bool(blocker.get("code"))
                and isinstance(blocker.get("reason"), str)
                and bool(blocker.get("reason"))
                and isinstance(blocker.get("evidence_refs"), list)
                and bool(blocker.get("evidence_refs"))
            )
            if not valid:
                issues.append(ValidationIssue("PFV-083", f"blocked task {task['id']} lacks blocker information"))
        elif blocker is not None:
            issues.append(ValidationIssue("PFV-083", f"non-blocked task {task['id']} may not retain blocker information"))
    return issues
