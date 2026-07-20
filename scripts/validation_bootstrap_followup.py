"""Identity-bound compatibility for the validator-bootstrap repair merge."""
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

REPOSITORY = "rezahh107/Project-Foundry"
PROGRAM_PATH = "planning/execution-program.v1.json"
STATE_PATH = "planning/current-state.v1.json"
SCOPE_PATH = "planning/scope-baseline.v1.json"
HOSTED_SCHEMA = "project-foundry-hosted-provenance.v1"
HOSTED_SOURCE = "github_rest_v2022_11_28"
WORKFLOW_NAME = "Foundation validation"

REPAIR_BASE_COMMIT = "c44ced1d858bd0d1b6d690e47ae12355c79166ca"
REPAIR_PR_HEAD = "0d997d0429c2e3099e9ec5a09c83eea69f14a6ab"
REPAIR_INTEGRATION_COMMIT = "cac31e13815a7c52d436fcf34f65dbe997980a37"
REPAIR_PR_NUMBER = 2


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


def _hosted_payload(root: Path) -> dict[str, Any] | None:
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


def _exact_repair_boundary_valid(root: Path) -> bool:
    head = _value(root, "rev-parse", "HEAD")
    if head is None or not _ancestor(root, REPAIR_INTEGRATION_COMMIT, head):
        return False
    if _parents(root, REPAIR_INTEGRATION_COMMIT) != [REPAIR_BASE_COMMIT, REPAIR_PR_HEAD]:
        return False
    if _git(
        root,
        "diff",
        "--quiet",
        REPAIR_PR_HEAD,
        REPAIR_INTEGRATION_COMMIT,
        "--",
        PROGRAM_PATH,
        STATE_PATH,
        SCOPE_PATH,
    ).returncode != 0:
        return False
    payload = _hosted_payload(root)
    if payload is None:
        return False
    records = [
        item
        for item in payload["merge_records"]
        if isinstance(item, dict) and item.get("integration_sha") == REPAIR_INTEGRATION_COMMIT
    ]
    if len(records) != 1:
        return False
    record = records[0]
    merge_valid = (
        record.get("repository") == REPOSITORY
        and record.get("merge_commit_sha") == REPAIR_INTEGRATION_COMMIT
        and record.get("merged") is True
        and record.get("merge_method") == "merge_commit"
        and record.get("pr_number") == REPAIR_PR_NUMBER
        and record.get("pr_head_sha") == REPAIR_PR_HEAD
        and record.get("base_sha") == REPAIR_BASE_COMMIT
        and record.get("base_ref") == "main"
    )
    pr_ci_valid = any(
        isinstance(run, dict)
        and run.get("commit_sha") == REPAIR_PR_HEAD
        and run.get("workflow_name") == WORKFLOW_NAME
        and run.get("event") == "pull_request"
        and run.get("conclusion") == "success"
        for run in payload["ci_runs"]
    )
    return bool(merge_valid and pr_ci_valid)


def apply_followup_bootstrap_compatibility(
    root: Path, issues: list[ValidationIssue]
) -> list[ValidationIssue]:
    """Suppress only the two exact false positives caused by merging PR #2."""
    if not _exact_repair_boundary_valid(root.resolve()):
        return list(issues)
    allowed = {
        (
            "PFV-036",
            f"integration {REPAIR_INTEGRATION_COMMIT} does not integrate the canonical active Task at merge_pending",
        ),
        (
            "PFV-086",
            f"historical integration {REPAIR_INTEGRATION_COMMIT} lacks a successful exact-SHA push workflow",
        ),
    }
    return [issue for issue in issues if (issue.code, issue.message) not in allowed]
