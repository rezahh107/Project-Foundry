"""Canonical structure and cross-document semantic validation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from scripts.validation_core import (
        ALLOWED_TASK_STATES,
        CANONICAL_DOCUMENTS,
        ValidationIssue,
        duplicates,
        load_json_strict,
        validate_schema_instance,
    )
except ModuleNotFoundError:
    from validation_core import (
        ALLOWED_TASK_STATES,
        CANONICAL_DOCUMENTS,
        ValidationIssue,
        duplicates,
        load_json_strict,
        validate_schema_instance,
    )

ACCEPTED_DECISION_STATUSES = {
    "accepted_for_foundation_candidate",
    "accepted",
    "authorized",
    "implemented",
}
DECISION_STATUSES = ACCEPTED_DECISION_STATUSES | {
    "research_required",
    "rejected",
    "superseded",
}


def load_and_validate_structures(
    root: Path,
) -> tuple[dict[str, dict[str, Any]], list[ValidationIssue]]:
    documents: dict[str, dict[str, Any]] = {}
    issues: list[ValidationIssue] = []
    for document_path, schema_path in CANONICAL_DOCUMENTS.items():
        try:
            schema = load_json_strict(root / schema_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            issues.append(ValidationIssue("PFV-100", f"{schema_path}: schema cannot be read: {exc}"))
            continue
        if not isinstance(schema, dict):
            issues.append(ValidationIssue("PFV-103", f"{schema_path}: schema root must be an object"))
            continue
        try:
            document = load_json_strict(root / document_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            issues.append(ValidationIssue("PFV-101", f"{document_path}: canonical JSON cannot be read: {exc}"))
            continue
        structural = validate_schema_instance(document, schema, document=document_path)
        issues.extend(structural)
        if not structural and isinstance(document, dict):
            documents[document_path] = document
    return documents, issues


# Compatibility alias retained for existing imports.
_load_and_validate_structures = load_and_validate_structures


def _validate_identity_bindings(documents: dict[str, dict[str, Any]]) -> tuple[list[ValidationIssue], str]:
    issues: list[ValidationIssue] = []
    constitution = documents["governance/project-constitution.v1.json"]
    program = documents["planning/execution-program.v1.json"]
    scope = documents["planning/scope-baseline.v1.json"]
    state = documents["planning/current-state.v1.json"]
    decisions = documents["decisions/decision-registry.v1.json"]
    dogfooding = documents["dogfooding/dogfooding-registry.v1.json"]
    project_ids = {
        document["project_id"]
        for document in [constitution, program, scope, state, decisions, dogfooding]
    }
    if project_ids != {"PROJECT-FOUNDRY"}:
        issues.append(ValidationIssue("PFV-010", f"project identity mismatch: {sorted(project_ids)}"))
    north_star_id = constitution["north_star"]["id"]
    if north_star_id != "PF-NORTH-STAR-001":
        issues.append(ValidationIssue("PFV-011", "canonical North Star identity changed"))
    for name, document in [
        ("program", program),
        ("scope", scope),
        ("state", state),
        ("decisions", decisions),
        ("dogfooding", dogfooding),
    ]:
        if document["north_star_id"] != north_star_id:
            issues.append(ValidationIssue("PFV-012", f"{name} is not bound to canonical North Star"))
    return issues, north_star_id


def _first_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index first records without silently overwriting duplicate identities."""
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        indexed.setdefault(record["id"], record)
    return indexed


def _validate_program_and_scope(
    documents: dict[str, dict[str, Any]], north_star_id: str
) -> tuple[list[ValidationIssue], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    issues: list[ValidationIssue] = []
    program = documents["planning/execution-program.v1.json"]
    scope = documents["planning/scope-baseline.v1.json"]
    state = documents["planning/current-state.v1.json"]
    work_packages = program["work_packages"]
    tasks = program["tasks"]
    work_package_ids = [item["id"] for item in work_packages]
    task_ids = [item["id"] for item in tasks]
    duplicate_work_package_ids = duplicates(work_package_ids)
    duplicate_task_ids = duplicates(task_ids)
    if duplicate_work_package_ids:
        issues.append(ValidationIssue("PFV-020", "duplicate work package IDs"))
    if duplicate_task_ids:
        issues.append(ValidationIssue("PFV-021", "duplicate task IDs"))

    work_package_map = _first_by_id(work_packages)
    task_map = _first_by_id(tasks)
    membership_by_task: dict[str, list[str]] = {}

    for work_package in work_packages:
        work_package_id = work_package["id"]
        for task_id in work_package["task_ids"]:
            membership_by_task.setdefault(task_id, []).append(work_package_id)
            task = task_map.get(task_id)
            if task is None:
                issues.append(
                    ValidationIssue(
                        "PFV-029",
                        f"work package {work_package_id} references unknown task {task_id}",
                    )
                )
            elif task["work_package_id"] != work_package_id:
                issues.append(
                    ValidationIssue(
                        "PFV-030",
                        f"task {task_id} work package linkage is inconsistent",
                    )
                )

    for task in tasks:
        task_id = task["id"]
        declared_work_package_id = task["work_package_id"]
        if declared_work_package_id not in work_package_map:
            issues.append(ValidationIssue("PFV-022", f"task {task_id} references unknown work package"))
        elif task_id not in duplicate_task_ids and declared_work_package_id not in duplicate_work_package_ids:
            memberships = membership_by_task.get(task_id, [])
            if memberships != [declared_work_package_id]:
                issues.append(
                    ValidationIssue(
                        "PFV-031",
                        f"task {task_id} must appear exactly once in declared work package "
                        f"{declared_work_package_id}; observed memberships: {memberships}",
                    )
                )
        if task["status"] not in ALLOWED_TASK_STATES:
            issues.append(ValidationIssue("PFV-023", f"task {task_id} has invalid status {task['status']}"))
        for dependency in task["depends_on"]:
            if dependency not in task_map:
                issues.append(ValidationIssue("PFV-024", f"task {task_id} references unknown dependency {dependency}"))
            if dependency == task_id:
                issues.append(ValidationIssue("PFV-025", f"task {task_id} depends on itself"))
        if not task["acceptance_criteria"]:
            issues.append(ValidationIssue("PFV-026", f"task {task_id} has no acceptance criteria"))
        if task["status"] in {"complete", "current_main_verified"} and not task["evidence_refs"]:
            issues.append(ValidationIssue("PFV-027", f"task {task_id} claims completion without evidence"))
        if task["status"] == "complete":
            issues.append(ValidationIssue("PFV-028", f"task {task_id} must preserve current_main_verified evidence state"))

    included_work_packages = set(scope["included_work_package_ids"])
    included_tasks = set(scope["included_task_ids"])
    unknown_scope_wps = included_work_packages - set(work_package_map)
    if unknown_scope_wps:
        issues.append(ValidationIssue("PFV-040", f"scope includes unknown work package(s): {sorted(unknown_scope_wps)}"))
    unknown_scope_tasks = included_tasks - set(task_map)
    if unknown_scope_tasks:
        issues.append(ValidationIssue("PFV-041", f"scope includes unknown task(s): {sorted(unknown_scope_tasks)}"))

    active_scope_ref = f"{scope['scope_id']}@{scope['scope_version']}"
    for included_task_id in sorted(included_tasks - unknown_scope_tasks):
        included_task = task_map[included_task_id]
        if included_task["work_package_id"] not in included_work_packages:
            issues.append(
                ValidationIssue(
                    "PFV-044",
                    f"included task {included_task_id} belongs to work package "
                    f"{included_task['work_package_id']} outside active scope",
                )
            )
        if included_task["scope_ref"] != active_scope_ref:
            issues.append(
                ValidationIssue(
                    "PFV-045",
                    f"included task {included_task_id} has scope_ref "
                    f"{included_task['scope_ref']!r}; expected {active_scope_ref!r}",
                )
            )

    active_task_id = scope["active_task_id"]
    if active_task_id not in included_tasks:
        issues.append(ValidationIssue("PFV-042", "active task is outside active scope"))
    if active_task_id not in task_map:
        issues.append(ValidationIssue("PFV-043", f"active task {active_task_id} is absent from the program"))

    current_task_id = state["current_task_id"]
    if current_task_id != active_task_id:
        issues.append(ValidationIssue("PFV-050", "current state and scope baseline disagree on active task"))
    if current_task_id not in included_tasks:
        issues.append(ValidationIssue("PFV-051", "current task is outside included scope"))
    current_task = task_map.get(current_task_id)
    if current_task is None:
        issues.append(ValidationIssue("PFV-059", f"current task {current_task_id} is absent from the program"))
    else:
        if current_task["work_package_id"] not in included_work_packages:
            issues.append(
                ValidationIssue(
                    "PFV-044",
                    f"current task {current_task_id} belongs to work package "
                    f"{current_task['work_package_id']} outside active scope",
                )
            )
        if state["current_task_status"] != current_task["status"]:
            issues.append(ValidationIssue("PFV-052", "current task status differs from execution program"))
        expected_context = [
            north_star_id,
            program["program_id"],
            current_task["work_package_id"],
            current_task_id,
        ]
        if state["active_context_path"] != expected_context:
            issues.append(ValidationIssue("PFV-053", f"active context path must be {expected_context}"))

    context = state["active_context_path"]
    if len(context) == 4:
        if context[3] not in task_map:
            issues.append(ValidationIssue("PFV-053", f"active context path references unknown task {context[3]}"))
        if context[2] not in included_work_packages:
            issues.append(
                ValidationIssue(
                    "PFV-044",
                    f"active context work package {context[2]} is outside active scope",
                )
            )
    if state["program_ref"] != f"{program['program_id']}@{program['program_version']}":
        issues.append(ValidationIssue("PFV-054", "current state has stale program reference"))
    if state["scope_ref"] != active_scope_ref:
        issues.append(ValidationIssue("PFV-055", "current state has stale scope reference"))
    for completed_id in state["completed_task_ids"]:
        completed = task_map.get(completed_id)
        if completed is None:
            issues.append(ValidationIssue("PFV-056", f"unknown completed task {completed_id}"))
        elif completed["status"] != "current_main_verified" or not completed["evidence_refs"]:
            issues.append(ValidationIssue("PFV-057", f"completed task {completed_id} lacks exact-main status or evidence"))
    if state["next_task_id"] not in task_map:
        issues.append(ValidationIssue("PFV-058", f"next task {state['next_task_id']} does not exist"))
    return issues, work_package_map, task_map


def _validate_decisions(decisions: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    records = decisions["decisions"]
    decision_ids = [item["id"] for item in records]
    if duplicates(decision_ids):
        issues.append(ValidationIssue("PFV-060", "duplicate decision IDs"))
    for decision in records:
        decision_id = decision["id"]
        decision_class = decision["decision_class"]
        status = decision["status"]
        if status not in DECISION_STATUSES:
            issues.append(ValidationIssue("PFV-061", f"decision {decision_id} has invalid status {status}"))
        if decision_class in {"D2_STRUCTURED", "D3_HIGH_CONSEQUENCE"}:
            if not decision["hard_constraints"]:
                issues.append(ValidationIssue("PFV-064", f"decision {decision_id} has no hard constraints"))
            weights = decision["criteria_weights"]
            if sum(weights.values()) != 100:
                issues.append(ValidationIssue("PFV-062", f"decision {decision_id} criteria weights must total 100"))
            for required in ["ai_operability", "owner_usability"]:
                if required not in weights:
                    issues.append(ValidationIssue("PFV-063", f"decision {decision_id} is missing criterion {required}"))

        if status == "research_required":
            options = decision.get("options_to_research") or []
            if len(options) < 2 or len(options) != len(set(options)):
                issues.append(ValidationIssue("PFV-066", f"decision {decision_id} needs at least two distinct research options"))
            if decision["selected_option"] is not None or decision["rationale"] is not None:
                issues.append(ValidationIssue("PFV-065", f"decision {decision_id} claims a result before research"))
            if decision["evidence_refs"]:
                issues.append(ValidationIssue("PFV-065", f"decision {decision_id} claims result evidence before research"))

        if status in ACCEPTED_DECISION_STATUSES:
            options = decision.get("options_considered") or []
            if len(options) < 2 or len(options) != len(set(options)):
                issues.append(ValidationIssue("PFV-066", f"decision {decision_id} needs at least two distinct considered options"))
            selected = decision["selected_option"]
            if not isinstance(selected, str) or not selected or selected not in options:
                issues.append(ValidationIssue("PFV-067", f"decision {decision_id} selected option is missing or was not considered"))
            rationale = decision["rationale"]
            if not isinstance(rationale, str) or not rationale.strip() or not decision["evidence_refs"]:
                issues.append(ValidationIssue("PFV-068", f"decision {decision_id} lacks rationale or evidence"))
            if not decision["reconsideration_triggers"]:
                issues.append(ValidationIssue("PFV-069", f"decision {decision_id} lacks uncertainty or reconsideration triggers"))
    return issues


def _validate_dogfooding(dogfooding: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    observation_ids = {item["id"] for item in dogfooding["observations"]}
    lesson_ids = {item["id"] for item in dogfooding["lesson_candidates"]}
    for lesson in dogfooding["lesson_candidates"]:
        for reference in lesson["observation_refs"]:
            if reference not in observation_ids:
                issues.append(ValidationIssue("PFV-070", f"lesson {lesson['id']} references unknown observation {reference}"))
    for promotion in dogfooding["promotions"]:
        if promotion["lesson_id"] not in lesson_ids:
            issues.append(ValidationIssue("PFV-071", f"promotion {promotion['id']} references unknown lesson"))
        if not promotion["authority"] or not promotion["evidence_refs"] or not promotion["carrier_refs"]:
            issues.append(ValidationIssue("PFV-072", f"promotion {promotion['id']} lacks authority, evidence, or carriers"))
        if promotion["status"] == "automatic":
            issues.append(ValidationIssue("PFV-073", "dogfooding promotion may not be automatic"))
    return issues


def validate_semantics(documents: dict[str, dict[str, Any]]) -> list[ValidationIssue]:
    issues, north_star_id = _validate_identity_bindings(documents)
    program_issues, _, _ = _validate_program_and_scope(documents, north_star_id)
    issues.extend(program_issues)
    issues.extend(_validate_decisions(documents["decisions/decision-registry.v1.json"]))
    issues.extend(_validate_dogfooding(documents["dogfooding/dogfooding-registry.v1.json"]))
    constitution = documents["governance/project-constitution.v1.json"]
    if constitution["operating_profile"]["security_priority"] != "low_with_mandatory_safety_floor":
        issues.append(ValidationIssue("PFV-080", "security profile must preserve mandatory safety floor"))
    completion_rule = constitution["completion_rule"]
    if completion_rule["required_lifecycle_state"] != "current_main_verified" or completion_rule["evidence_required"] is not True:
        issues.append(ValidationIssue("PFV-081", "completion rule is weaker than required"))
    return issues


# Compatibility alias retained for existing imports.
_validate_semantics = validate_semantics
