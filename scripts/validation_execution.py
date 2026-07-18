"""Dependency, dispatch, lifecycle, and Git-verifiable evidence validation."""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
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
ALLOWED_TRANSITIONS = {
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
EVIDENCE_STATES = {
    "validated_on_branch": ("branch_validation", "pull_request_head", "PFV-084"),
    "merged": ("merge", "main_merge_subject", "PFV-084"),
    "current_main_verified": ("current_main", "verified_main_state", "PFV-085"),
}
SHA40 = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY = "rezahh107/Project-Foundry"
MAIN_REF = "refs/heads/main"
PROGRAM_PATH = "planning/execution-program.v1.json"


@dataclass(frozen=True)
class GitContext:
    root: Path
    head: str
    event: str
    ref: str
    pr_head: str | None
    pr_base: str | None
    pr_head_ref: str | None
    push_before: str | None
    synthetic_merge: str | None
    main_tip: str | None


@dataclass(frozen=True)
class Provenance:
    transition_commit: str
    prior_commit: str | None
    prior_status: str | None


def _first_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        result.setdefault(record["id"], record)
    return result


def _dependencies_satisfied(task: dict[str, Any], task_map: dict[str, dict[str, Any]]) -> bool:
    return all(dep in task_map and task_map[dep]["status"] == "current_main_verified" for dep in task["depends_on"])


def _find_cycle(task_map: dict[str, dict[str, Any]]) -> list[str] | None:
    color = {task_id: 0 for task_id in task_map}
    stack: list[str] = []
    positions: dict[str, int] = {}

    def visit(task_id: str) -> list[str] | None:
        color[task_id] = 1
        positions[task_id] = len(stack)
        stack.append(task_id)
        for dep in task_map[task_id]["depends_on"]:
            if dep not in task_map or dep == task_id:
                continue
            if color[dep] == 0:
                cycle = visit(dep)
                if cycle:
                    return cycle
            elif color[dep] == 1:
                return stack[positions[dep]:] + [dep]
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


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False, timeout=20)


def _value(root: Path, *args: str) -> str | None:
    result = _git(root, *args)
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _exists(root: Path, sha: str | None) -> bool:
    return bool(sha and SHA40.fullmatch(sha) and _git(root, "cat-file", "-e", f"{sha}^{{commit}}").returncode == 0)


def _ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return _git(root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def _symbolic_ref(root: Path) -> str | None:
    return _value(root, "symbolic-ref", "-q", "HEAD")


def _context(root: Path) -> tuple[GitContext | None, list[ValidationIssue]]:
    if _git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        return None, []
    issues: list[ValidationIssue] = []
    head = _value(root, "rev-parse", "HEAD")
    if head is None or SHA40.fullmatch(head) is None:
        return None, [ValidationIssue("PFV-084", "Git trust context lacks an exact validation commit")]
    expected = os.environ.get("PROJECT_FOUNDRY_EXPECTED_HEAD_SHA")
    if expected and expected != head:
        issues.append(ValidationIssue("PFV-084", "checked-out Git Head disagrees with workflow identity"))
    event = os.environ.get("PROJECT_FOUNDRY_EVENT_NAME", "local")
    ref = os.environ.get("PROJECT_FOUNDRY_GITHUB_REF") or (_symbolic_ref(root) or "")
    main_tip = head if event == "push" and ref == MAIN_REF else None
    if main_tip is None:
        for candidate in ("refs/remotes/origin/main", "refs/heads/main"):
            value = _value(root, "rev-parse", "--verify", candidate)
            if value and SHA40.fullmatch(value):
                main_tip = value
                break
    context = GitContext(
        root=root,
        head=head,
        event=event,
        ref=ref,
        pr_head=os.environ.get("PROJECT_FOUNDRY_PR_HEAD_SHA") or None,
        pr_base=os.environ.get("PROJECT_FOUNDRY_PR_BASE_SHA") or None,
        pr_head_ref=os.environ.get("PROJECT_FOUNDRY_PR_HEAD_REF") or None,
        push_before=os.environ.get("PROJECT_FOUNDRY_PUSH_BEFORE_SHA") or None,
        synthetic_merge=os.environ.get("PROJECT_FOUNDRY_SYNTHETIC_MERGE_SHA") or None,
        main_tip=main_tip,
    )
    if context.pr_head and context.event == "pull_request" and context.pr_head != head:
        issues.append(ValidationIssue("PFV-084", "PR Head context disagrees with checked-out commit"))
    if context.pr_base and not _exists(root, context.pr_base):
        issues.append(ValidationIssue("PFV-084", "PR base commit is absent from fetched history"))
    return context, issues


def _status_at(root: Path, sha: str, task_id: str) -> str | None:
    result = _git(root, "show", f"{sha}:{PROGRAM_PATH}")
    if result.returncode != 0:
        return None
    try:
        program = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    for task in program.get("tasks", []):
        if isinstance(task, dict) and task.get("id") == task_id:
            return task.get("status") if isinstance(task.get("status"), str) else None
    return None


def _provenance(context: GitContext, task_id: str, status: str) -> Provenance | None:
    history = _value(context.root, "rev-list", "--first-parent", "HEAD")
    if not history:
        return None
    contiguous: list[str] = []
    for sha in history.splitlines():
        observed = _status_at(context.root, sha, task_id)
        if observed == status:
            contiguous.append(sha)
        elif contiguous:
            return Provenance(contiguous[-1], sha, observed)
    if contiguous:
        transition = contiguous[-1]
        return Provenance(transition, _value(context.root, "rev-parse", f"{transition}^1"), None)
    return None


def _record(records: list[Any]) -> dict[str, str] | None:
    if len(records) != 1 or not isinstance(records[0], dict):
        return None
    record = records[0]
    required = {"receipt_type", "verification_type", "subject_kind", "repository", "ref", "subject_sha", "transition_from", "transition_to"}
    if set(record) != required or not all(isinstance(record.get(field), str) for field in required):
        return None
    return record


def _fingerprint(records: list[Any]) -> tuple[tuple[str, str], ...] | None:
    record = _record(records)
    return tuple(sorted(record.items())) if record else None


def _validate_receipt(task: dict[str, Any], context: GitContext | None, *, git_required: bool) -> list[ValidationIssue]:
    status = task["status"]
    expected_type, expected_kind, code = EVIDENCE_STATES[status]
    record = _record(task["evidence_refs"])
    if record is None:
        return [ValidationIssue(code, f"task {task['id']} lacks one structured Git-history receipt")]
    if (
        record["receipt_type"] != "git_history_attestation"
        or record["verification_type"] != expected_type
        or record["subject_kind"] != expected_kind
        or record["repository"] != REPOSITORY
        or SHA40.fullmatch(record["subject_sha"]) is None
        or record["transition_to"] != status
    ):
        return [ValidationIssue(code, f"task {task['id']} has malformed or mismatched {expected_type} evidence")]
    if context is None:
        return [ValidationIssue(code, f"task {task['id']} evidence cannot be verified without Git history")] if git_required else []
    provenance = _provenance(context, task["id"], status)
    if provenance is None or provenance.prior_commit is None:
        return [ValidationIssue(code, f"task {task['id']} transition provenance is absent")]
    if (
        record["transition_from"] != provenance.prior_status
        or record["subject_sha"] != provenance.prior_commit
        or record["subject_sha"] == provenance.transition_commit
        or not _exists(context.root, record["subject_sha"])
        or not _ancestor(context.root, record["subject_sha"], context.head)
    ):
        return [ValidationIssue(code, f"task {task['id']} receipt disagrees with Git transition history")]
    if status == "validated_on_branch":
        expected_ref = f"refs/heads/{context.pr_head_ref}" if context.pr_head_ref else _symbolic_ref(context.root)
        if (
            context.event != "pull_request"
            or context.pr_head != context.head
            or expected_ref is None
            or record["ref"] != expected_ref
            or record["ref"] == MAIN_REF
            or record["subject_sha"] in {context.pr_base, context.synthetic_merge}
        ):
            return [ValidationIssue("PFV-084", f"task {task['id']} branch evidence is not trusted")]
    else:
        if (
            record["ref"] != MAIN_REF
            or context.main_tip is None
            or not _ancestor(context.root, provenance.transition_commit, context.main_tip)
            or not _ancestor(context.root, record["subject_sha"], context.main_tip)
            or record["subject_sha"] in {context.pr_head, context.pr_base, context.synthetic_merge}
        ):
            return [ValidationIssue(code, f"task {task['id']} main evidence is not on trusted main ancestry")]
        if provenance.transition_commit == context.head and (
            context.event != "push" or context.ref != MAIN_REF or context.push_before != record["subject_sha"]
        ):
            return [ValidationIssue(code, f"task {task['id']} receipt commit lacks trusted main push context")]
    return []


def _prior_state(task: dict[str, Any], transition: dict[str, Any], context: GitContext | None) -> list[ValidationIssue]:
    if context is None:
        return []
    provenance = _provenance(context, task["id"], task["status"])
    if provenance is None:
        return [ValidationIssue("PFV-035", f"task {task['id']} has no trusted transition provenance")]
    if provenance.prior_status is None:
        if task["status"] == "implementation_submitted" and transition["from"] == "planned" and transition["to"] == task["status"]:
            return []
        return [ValidationIssue("PFV-035", f"task {task['id']} bootstrap edge is invalid")]
    if transition["from"] != provenance.prior_status:
        return [ValidationIssue("PFV-035", f"task {task['id']} prior status disagrees with Git history")]
    return []


def validate_execution_controls(documents: dict[str, dict[str, Any]], *, root: Path | None = None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    program = documents[PROGRAM_PATH]
    scope = documents["planning/scope-baseline.v1.json"]
    state = documents["planning/current-state.v1.json"]
    tasks = program["tasks"]
    task_map = _first_by_id(tasks)
    context = None
    if root is not None:
        context, context_issues = _context(root.resolve())
        issues.extend(context_issues)

    if not duplicates([task["id"] for task in tasks]):
        cycle = _find_cycle(task_map)
        if cycle:
            issues.append(ValidationIssue("PFV-032", f"dependency graph contains a cycle: {' -> '.join(cycle)}"))
    for task in tasks:
        if task["status"] in PROGRESSED_STATES and not _dependencies_satisfied(task, task_map):
            issues.append(ValidationIssue("PFV-033", f"task {task['id']} progressed while a dependency is unsatisfied"))

    active_scope_ref = f"{scope['scope_id']}@{scope['scope_version']}"
    included_tasks = set(scope["included_task_ids"])
    included_wps = set(scope["included_work_package_ids"])
    current = task_map.get(state["current_task_id"])
    next_task = task_map.get(state["next_task_id"])
    if next_task is not None:
        scoped = next_task["id"] in included_tasks and next_task["work_package_id"] in included_wps and next_task["scope_ref"] == active_scope_ref
        ready = _dependencies_satisfied(next_task, task_map)
        if next_task["id"] == state["current_task_id"]:
            ready = ready and next_task["status"] not in (UNSUCCESSFUL_TERMINAL_STATES | {"current_main_verified", "complete"})
        else:
            ready = ready and current is not None and current["status"] == "current_main_verified" and next_task["status"] in {"planned", "eligible"}
        if not scoped or not ready:
            issues.append(ValidationIssue("PFV-046", f"next task {next_task['id']} is outside active Scope or is not dispatch-eligible"))

    transition = state["last_transition"]
    if current is not None:
        status = current["status"]
        if transition["to"] != state["current_task_status"] or state["current_task_status"] != status:
            issues.append(ValidationIssue("PFV-034", "last transition target, current state, and Task status must agree"))
        if transition["to"] not in ALLOWED_TRANSITIONS.get(transition["from"], set()):
            issues.append(ValidationIssue("PFV-034", f"illegal lifecycle transition {transition['from']} -> {transition['to']}"))
        issues.extend(_prior_state(current, transition, context))
        if status in EVIDENCE_STATES:
            task_ev = _fingerprint(current["evidence_refs"])
            if not task_ev or task_ev != _fingerprint(state["evidence_refs"]) or task_ev != _fingerprint(transition["evidence_refs"]):
                issues.append(ValidationIssue("PFV-082", "Task, state, and transition evidence must be non-empty and identical"))

    completed = set(state["completed_task_ids"])
    blocked = set(state["blocked_task_ids"])
    known = set(task_map)
    if blocked - known:
        issues.append(ValidationIssue("PFV-083", f"blocked collection contains unknown task(s): {sorted(blocked - known)}"))
    if completed & blocked:
        issues.append(ValidationIssue("PFV-083", f"tasks cannot be both completed and blocked: {sorted(completed & blocked)}"))
    verified_ids = {task["id"] for task in tasks if task["status"] == "current_main_verified"}
    blocked_ids = {task["id"] for task in tasks if task["status"] == "blocked"}
    if completed != verified_ids:
        issues.append(ValidationIssue("PFV-083", "completed collection must exactly match verified Tasks"))
    if blocked != blocked_ids:
        issues.append(ValidationIssue("PFV-083", "blocked collection must exactly match blocked Tasks"))

    for task in tasks:
        if task["status"] in EVIDENCE_STATES:
            issues.extend(_validate_receipt(task, context, git_required=root is not None))
        blocker = task.get("blocker")
        if task["status"] == "blocked":
            valid = isinstance(blocker, dict) and all(blocker.get(key) for key in ("code", "reason", "evidence_refs"))
            if not valid:
                issues.append(ValidationIssue("PFV-083", f"blocked task {task['id']} lacks blocker information"))
        elif blocker is not None:
            issues.append(ValidationIssue("PFV-083", f"non-blocked task {task['id']} may not retain blocker information"))
    return issues
