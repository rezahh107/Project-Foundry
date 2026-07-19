"""One-time bootstrap compatibility and immutable Task-origin validation."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

try:
    from scripts.validation_core import ValidationIssue
except ModuleNotFoundError:
    from validation_core import ValidationIssue

PROGRAM_PATH = "planning/execution-program.v1.json"
STATE_PATH = "planning/current-state.v1.json"
SCOPE_PATH = "planning/scope-baseline.v1.json"
REPOSITORY = "rezahh107/Project-Foundry"
MAIN_REF = "refs/heads/main"
HOSTED_SCHEMA = "project-foundry-hosted-provenance.v1"
HOSTED_SOURCE = "github_rest_v2022_11_28"
WORKFLOW_NAME = "Foundation validation"

# This repository was born in PR #1 before the lifecycle validator existed on main.
# The exception is intentionally identity-bound and cannot authorize later Tasks or merges.
BOOTSTRAP_TASK_ID = "PF-001"
BOOTSTRAP_INITIAL_STATUS = "implementation_submitted"
BOOTSTRAP_BASE_COMMIT = "d197447598d7108c44e79fbaa57d71e529930052"
BOOTSTRAP_ORIGIN_COMMIT = "fd039af9f1771922c185d3595afd975ad93dfd04"
BOOTSTRAP_PR_HEAD = "75282b08d27015543e7467dabb34395803ed1ed5"
BOOTSTRAP_INTEGRATION_COMMIT = "c44ced1d858bd0d1b6d690e47ae12355c79166ca"
BOOTSTRAP_PR_NUMBER = 1


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


def _value(root: Path, *args: str) -> str | None:
    result = _git(root, *args)
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _parents(root: Path, sha: str) -> list[str]:
    value = _value(root, "show", "-s", "--format=%P", sha)
    return value.split() if value else []


def _ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return _git(root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def _json_at(root: Path, sha: str, path: str) -> dict[str, Any] | None:
    result = _git(root, "show", f"{sha}:{path}")
    if result.returncode != 0:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _task(document: dict[str, Any] | None, task_id: str) -> dict[str, Any] | None:
    if document is None:
        return None
    for item in document.get("tasks", []):
        if isinstance(item, dict) and item.get("id") == task_id:
            return item
    return None


def _bootstrap_origin_valid(root: Path) -> bool:
    if _parents(root, BOOTSTRAP_ORIGIN_COMMIT) != [BOOTSTRAP_BASE_COMMIT]:
        return False
    program = _json_at(root, BOOTSTRAP_ORIGIN_COMMIT, PROGRAM_PATH)
    state = _json_at(root, BOOTSTRAP_ORIGIN_COMMIT, STATE_PATH)
    task = _task(program, BOOTSTRAP_TASK_ID)
    transition = state.get("last_transition") if isinstance(state, dict) else None
    return bool(
        isinstance(task, dict)
        and task.get("status") == BOOTSTRAP_INITIAL_STATUS
        and task.get("evidence_refs") == []
        and isinstance(state, dict)
        and state.get("current_task_id") == BOOTSTRAP_TASK_ID
        and state.get("current_task_status") == BOOTSTRAP_INITIAL_STATUS
        and state.get("evidence_refs") == []
        and isinstance(transition, dict)
        and transition.get("from") == "planned"
        and transition.get("to") == BOOTSTRAP_INITIAL_STATUS
        and transition.get("evidence_refs") == []
    )


def _trusted_hosted_payload(root: Path) -> dict[str, Any] | None:
    path_value = os.environ.get("PROJECT_FOUNDRY_HOSTED_PROVENANCE_PATH")
    if not path_value:
        return None
    path = Path(path_value).resolve()
    if os.environ.get("PROJECT_FOUNDRY_TEST_MODE") != "1":
        runner_temp = os.environ.get("RUNNER_TEMP")
        if os.environ.get("GITHUB_ACTIONS") != "true" or not runner_temp:
            return None
        try:
            path.relative_to(Path(runner_temp).resolve())
        except ValueError:
            return None
        try:
            path.relative_to(root.resolve())
        except ValueError:
            pass
        else:
            return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if (
        payload.get("schema_version") != HOSTED_SCHEMA
        or payload.get("source") != HOSTED_SOURCE
        or payload.get("repository") != REPOSITORY
        or not isinstance(payload.get("merge_records"), list)
        or not isinstance(payload.get("ci_runs"), list)
    ):
        return None
    return payload


def _bootstrap_hosted_valid(root: Path) -> bool:
    payload = _trusted_hosted_payload(root)
    if payload is None:
        return False
    merge_records = [
        item
        for item in payload["merge_records"]
        if isinstance(item, dict) and item.get("integration_sha") == BOOTSTRAP_INTEGRATION_COMMIT
    ]
    if len(merge_records) != 1:
        return False
    record = merge_records[0]
    merge_valid = (
        record.get("repository") == REPOSITORY
        and record.get("merge_commit_sha") == BOOTSTRAP_INTEGRATION_COMMIT
        and record.get("merged") is True
        and record.get("merge_method") == "merge_commit"
        and record.get("pr_number") == BOOTSTRAP_PR_NUMBER
        and record.get("pr_head_sha") == BOOTSTRAP_PR_HEAD
        and record.get("base_sha") == BOOTSTRAP_BASE_COMMIT
        and record.get("base_ref") == "main"
    )
    pr_ci_valid = any(
        isinstance(run, dict)
        and run.get("commit_sha") == BOOTSTRAP_PR_HEAD
        and run.get("workflow_name") == WORKFLOW_NAME
        and run.get("event") == "pull_request"
        and run.get("conclusion") == "success"
        for run in payload["ci_runs"]
    )
    return bool(merge_valid and pr_ci_valid)


def _bootstrap_topology_valid(root: Path) -> bool:
    head = _value(root, "rev-parse", "HEAD")
    if head is None or not _ancestor(root, BOOTSTRAP_INTEGRATION_COMMIT, head):
        return False
    if _parents(root, BOOTSTRAP_INTEGRATION_COMMIT) != [BOOTSTRAP_BASE_COMMIT, BOOTSTRAP_PR_HEAD]:
        return False
    if not _bootstrap_origin_valid(root) or not _ancestor(root, BOOTSTRAP_ORIGIN_COMMIT, BOOTSTRAP_PR_HEAD):
        return False
    if _git(
        root,
        "diff",
        "--quiet",
        BOOTSTRAP_PR_HEAD,
        BOOTSTRAP_INTEGRATION_COMMIT,
        "--",
        PROGRAM_PATH,
        STATE_PATH,
        SCOPE_PATH,
    ).returncode != 0:
        return False
    head_program = _json_at(root, BOOTSTRAP_PR_HEAD, PROGRAM_PATH)
    head_state = _json_at(root, BOOTSTRAP_PR_HEAD, STATE_PATH)
    head_task = _task(head_program, BOOTSTRAP_TASK_ID)
    if not (
        isinstance(head_task, dict)
        and head_task.get("status") == BOOTSTRAP_INITIAL_STATUS
        and isinstance(head_state, dict)
        and head_state.get("current_task_id") == BOOTSTRAP_TASK_ID
        and head_state.get("current_task_status") == BOOTSTRAP_INITIAL_STATUS
    ):
        return False
    return _bootstrap_hosted_valid(root)


def _linearized_history(root: Path) -> list[str]:
    head = _value(root, "rev-parse", "HEAD")
    if head is None:
        return []
    first_parent = _value(root, "rev-list", "--first-parent", "--reverse", head)
    if not first_parent:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for sha in first_parent.splitlines():
        parents = _parents(root, sha)
        if len(parents) == 2:
            first, second = parents
            merge_base = _value(root, "merge-base", first, second)
            if merge_base:
                branch = _value(root, "rev-list", "--first-parent", "--reverse", f"{merge_base}..{second}") or ""
                for branch_sha in branch.splitlines():
                    if branch_sha not in seen:
                        result.append(branch_sha)
                        seen.add(branch_sha)
        if sha not in seen:
            result.append(sha)
            seen.add(sha)
    return result


def validate_task_origins(root: Path) -> list[ValidationIssue]:
    root = root.resolve()
    if _git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        return []
    issues: list[ValidationIssue] = []
    seen: set[str] = set()
    bootstrap_origin_valid = _bootstrap_origin_valid(root)
    for sha in _linearized_history(root):
        program = _json_at(root, sha, PROGRAM_PATH)
        if program is None:
            continue
        for item in program.get("tasks", []):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in seen:
                continue
            task_id = item["id"]
            seen.add(task_id)
            status = item.get("status")
            evidence = item.get("evidence_refs")
            normal_origin = status == "planned" and evidence == []
            bootstrap_origin = (
                bootstrap_origin_valid
                and task_id == BOOTSTRAP_TASK_ID
                and sha == BOOTSTRAP_ORIGIN_COMMIT
                and status == BOOTSTRAP_INITIAL_STATUS
                and evidence == []
            )
            if not normal_origin and not bootstrap_origin:
                issues.append(
                    ValidationIssue(
                        "PFV-037",
                        f"task {task_id} first appears at {sha} in {status!r}; new Tasks must begin at planned",
                    )
                )
    return issues


def apply_bootstrap_compatibility(root: Path, issues: list[ValidationIssue]) -> list[ValidationIssue]:
    root = root.resolve()
    adjusted = list(issues)
    if _bootstrap_topology_valid(root):
        allowed = {
            (
                "PFV-036",
                f"integration {BOOTSTRAP_INTEGRATION_COMMIT} does not integrate the canonical active Task at merge_pending",
            ),
            (
                "PFV-086",
                f"historical integration {BOOTSTRAP_INTEGRATION_COMMIT} lacks a successful exact-SHA push workflow",
            ),
        }
        adjusted = [issue for issue in adjusted if (issue.code, issue.message) not in allowed]
    adjusted.extend(validate_task_origins(root))
    return adjusted
