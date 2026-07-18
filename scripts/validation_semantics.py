"""Canonical structure and cross-document semantic validation."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
try:
    from scripts.validation_core import (
        ALLOWED_TASK_STATES, CANONICAL_DOCUMENTS, ValidationIssue, duplicates,
        load_json_strict, validate_schema_instance,
    )
except ModuleNotFoundError:
    from validation_core import (
        ALLOWED_TASK_STATES, CANONICAL_DOCUMENTS, ValidationIssue, duplicates,
        load_json_strict, validate_schema_instance,
    )


def _load_and_validate_structures(
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


def _validate_semantics(documents: dict[str, dict[str, Any]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    constitution = documents["governance/project-constitution.v1.json"]
    program = documents["planning/execution-program.v1.json"]
    scope = documents["planning/scope-baseline.v1.json"]
    state = documents["planning/current-state.v1.json"]
    decisions = documents["decisions/decision-registry.v1.json"]
    dogfooding = documents["dogfooding/dogfooding-registry.v1.json"]

    all_documents = [constitution, program, scope, state, decisions, dogfooding]
    project_ids = {document["project_id"] for document in all_documents}
    if project_ids != {"PROJECT-FOUNDRY"}:
        issues.append(ValidationIssue("PFV-010", f"project identity mismatch: {sorted(project_ids)}"))

    north_star_id = constitution["north_star"]["id"]
    if north_star_id != "PF-NORTH-STAR-001":
        issues.append(ValidationIssue("PFV-011", "canonical North Star identity changed"))
    for name, document in [
        ("program", program), ("scope", scope), ("state", state),
        ("decisions", decisions), ("dogfooding", dogfooding),
    ]:
        if document["north_star_id"] != north_star_id:
            issues.append(ValidationIssue("PFV-012", f"{name} is not bound to canonical North Star"))

    work_packages = program["work_packages"]
    tasks = program["tasks"]
    work_package_ids = [item["id"] for item in work_packages]
    task_ids = [item["id"] for item in tasks]
    if duplicates(work_package_ids):
        issues.append(ValidationIssue("PFV-020", "duplicate work package IDs"))
    if duplicates(task_ids):
        issues.append(ValidationIssue("PFV-021", "duplicate task IDs"))
    work_package_map = {item["id"]: item for item in work_packages}
    task_map = {item["id"]: item for item in tasks}

    for task in tasks:
        task_id = task["id"]
        if task["work_package_id"] not in work_package_map:
            issues.append(ValidationIssue("PFV-022", f"task {task_id} references unknown work package"))
        if task["status"] not in ALLOWED_TASK_STATES:
            issues.append(ValidationIssue("PFV-023", f"task {task_id} has invalid status {task['status']}"))
        for dependency in task["depends_on"]:
            if dependency not in task_map:
                issues.append(ValidationIssue("PFV-024", f"task {task_id} references unknown dependency {dependency}"))
            if dependency == task_id:
                issues.append(ValidationIssue("PFV-025", f"task {task_id} depends on itself"))
        if task["status"] in {"complete", "current_main_verified"} and not task["evidence_refs"]:
            issues.append(ValidationIssue("PFV-027", f"task {task_id} claims completion without evidence"))
        if task["status"] == "complete":
            issues.append(ValidationIssue("PFV-028", f"task {task_id} must preserve current_main_verified evidence state"))

    for work_package in work_packages:
        for task_id in work_package["task_ids"]:
            if task_id not in task_map:
                issues.append(ValidationIssue("PFV-029", f"work package {work_package['id']} references unknown task {task_id}"))
            elif task_map[task_id]["work_package_id"] != work_package["id"]:
                issues.append(ValidationIssue("PFV-030", f"task {task_id} work package linkage is inconsistent"))

    included_work_packages = set(scope["included_work_package_ids"])
    included_tasks = set(scope["included_task_ids"])
    if not included_work_packages.issubset(work_package_map):
        issues.append(ValidationIssue("PFV-040", "scope includes unknown work package"))
    if not included_tasks.issubset(task_map):
        issues.append(ValidationIssue("PFV-041", "scope includes unknown task"))
    if scope["active_task_id"] not in included_tasks:
        issues.append(ValidationIssue("PFV-042", "active task is outside active scope"))

    current_task_id = state["current_task_id"]
    if current_task_id != scope["active_task_id"]:
        issues.append(ValidationIssue("PFV-050", "current state and scope baseline disagree on active task"))
    if current_task_id not in included_tasks:
        issues.append(ValidationIssue("PFV-051", "current task is outside included scope"))
    if state["current_task_status"] != task_map[current_task_id]["status"]:
        issues.append(ValidationIssue("PFV-052", "current task status differs from execution program"))
    expected_context = [
        north_star_id, program["program_id"], task_map[current_task_id]["work_package_id"], current_task_id,
    ]
    if state["active_context_path"] != expected_context:
        issues.append(ValidationIssue("PFV-053", f"active context path must be {expected_context}"))
    if state["program_ref"] != f"{program['program_id']}@{program['program_version']}":
        issues.append(ValidationIssue("PFV-054", "current state has stale program reference"))
    if state["scope_ref"] != f"{scope['scope_id']}@{scope['scope_version']}":
        issues.append(ValidationIssue("PFV-055", "current state has stale scope reference"))
    for completed_id in state["completed_task_ids"]:
        completed = task_map.get(completed_id)
        if completed is None:
            issues.append(ValidationIssue("PFV-056", f"unknown completed task {completed_id}"))
        elif completed["status"] != "current_main_verified" or not completed["evidence_refs"]:
            issues.append(ValidationIssue("PFV-057", f"completed task {completed_id} lacks exact-main status or evidence"))
    if state["next_task_id"] not in task_map:
        issues.append(ValidationIssue("PFV-058", "next task does not exist"))

    decision_ids = [item["id"] for item in decisions["decisions"]]
    if duplicates(decision_ids):
        issues.append(ValidationIssue("PFV-060", "duplicate decision IDs"))
    for decision in decisions["decisions"]:
        decision_id = decision["id"]
        if decision["decision_class"] in {"D2_STRUCTURED", "D3_HIGH_CONSEQUENCE"}:
            weights = decision["criteria_weights"]
            if sum(weights.values()) != 100:
                issues.append(ValidationIssue("PFV-062", f"decision {decision_id} criteria weights must total 100"))
            for required in ["ai_operability", "owner_usability"]:
                if required not in weights:
                    issues.append(ValidationIssue("PFV-063", f"decision {decision_id} is missing criterion {required}"))
        if decision["status"] == "research_required" and decision["selected_option"] is not None:
            issues.append(ValidationIssue("PFV-065", f"decision {decision_id} selected an option before research"))

    observation_ids = {item["id"] for item in dogfooding["observations"]}
    lesson_ids = {item["id"] for item in dogfooding["lesson_candidates"]}
    for lesson in dogfooding["lesson_candidates"]:
        for reference in lesson["observation_refs"]:
            if reference not in observation_ids:
                issues.append(ValidationIssue("PFV-070", f"lesson {lesson['id']} references unknown observation {reference}"))
    for promotion in dogfooding["promotions"]:
        if promotion["lesson_id"] not in lesson_ids:
            issues.append(ValidationIssue("PFV-071", f"promotion {promotion['id']} references unknown lesson"))
        if promotion["status"] == "automatic":
            issues.append(ValidationIssue("PFV-073", "dogfooding promotion may not be automatic"))
    return issues
