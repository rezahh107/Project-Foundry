"""Identity-bound compatibility for the three post-genesis bootstrap merges."""
from __future__ import annotations

import json
import os
import re
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
SHA40 = re.compile(r"^[0-9a-f]{40}$")

REPAIR_BASE_COMMIT = "c44ced1d858bd0d1b6d690e47ae12355c79166ca"
REPAIR_PR_HEAD = "0d997d0429c2e3099e9ec5a09c83eea69f14a6ab"
REPAIR_INTEGRATION_COMMIT = "cac31e13815a7c52d436fcf34f65dbe997980a37"
REPAIR_PR_NUMBER = 2

TRUST_BASE_COMMIT = "cac31e13815a7c52d436fcf34f65dbe997980a37"
TRUST_PR_HEAD = "01ead12c071d925de5e98994116afe66f830ac47"
TRUST_INTEGRATION_COMMIT = "6cebe25fec6bac15b9aa82eedc8a4cdc1a7eebe3"
TRUST_PR_NUMBER = 3

RECONCILIATION_BASE_COMMIT = "27f95557416a706f52c60df75fa9e4277c978929"
RECONCILIATION_PR_HEAD = "fff94ce52ffb1fbc0ac563aa1c20eeed1c1edc7a"
RECONCILIATION_INTEGRATION_COMMIT = "eb94ea2e5e2427b492b77948b6e53c9ddf2d709d"
RECONCILIATION_PR_NUMBER = 5
RECONCILIATION_TASK_ID = "PF-001"


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


def _exact_boundary_valid(
    root: Path,
    *,
    base: str,
    pr_head: str,
    integration: str,
    pr_number: int,
) -> bool:
    head = _value(root, "rev-parse", "HEAD")
    if head is None or not _ancestor(root, integration, head):
        return False
    if _parents(root, integration) != [base, pr_head]:
        return False
    if _git(
        root,
        "diff",
        "--quiet",
        pr_head,
        integration,
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
        if isinstance(item, dict) and item.get("integration_sha") == integration
    ]
    if len(records) != 1:
        return False
    record = records[0]
    merge_valid = (
        record.get("repository") == REPOSITORY
        and record.get("integration_sha") == integration
        and record.get("merge_commit_sha") == integration
        and record.get("merged") is True
        and record.get("merge_method") == "merge_commit"
        and record.get("pr_number") == pr_number
        and record.get("pr_head_sha") == pr_head
        and record.get("base_sha") == base
        and record.get("base_ref") == "main"
    )
    pr_ci_valid = any(
        isinstance(run, dict)
        and run.get("commit_sha") == pr_head
        and run.get("workflow_name") == WORKFLOW_NAME
        and run.get("event") == "pull_request"
        and run.get("conclusion") == "success"
        for run in payload["ci_runs"]
    )
    return bool(merge_valid and pr_ci_valid)


def _exact_repair_boundary_valid(root: Path) -> bool:
    return _exact_boundary_valid(
        root,
        base=REPAIR_BASE_COMMIT,
        pr_head=REPAIR_PR_HEAD,
        integration=REPAIR_INTEGRATION_COMMIT,
        pr_number=REPAIR_PR_NUMBER,
    )


def _exact_trust_boundary_valid(root: Path) -> bool:
    return _exact_boundary_valid(
        root,
        base=TRUST_BASE_COMMIT,
        pr_head=TRUST_PR_HEAD,
        integration=TRUST_INTEGRATION_COMMIT,
        pr_number=TRUST_PR_NUMBER,
    )


def _exact_reconciliation_boundary_valid(root: Path) -> bool:
    return _exact_boundary_valid(
        root,
        base=RECONCILIATION_BASE_COMMIT,
        pr_head=RECONCILIATION_PR_HEAD,
        integration=RECONCILIATION_INTEGRATION_COMMIT,
        pr_number=RECONCILIATION_PR_NUMBER,
    )


def _unchanged_reconciliation_descendant(root: Path, commit: str) -> bool:
    """Accept only first-parent descendants whose canonical lifecycle bytes are unchanged."""
    if SHA40.fullmatch(commit) is None:
        return False
    head = _value(root, "rev-parse", "HEAD")
    if head is None:
        return False
    chain = _value(
        root,
        "rev-list",
        "--first-parent",
        f"{RECONCILIATION_INTEGRATION_COMMIT}..{head}",
    )
    if not chain or commit not in set(chain.splitlines()):
        return False
    return _git(
        root,
        "diff",
        "--quiet",
        RECONCILIATION_INTEGRATION_COMMIT,
        commit,
        "--",
        PROGRAM_PATH,
        STATE_PATH,
        SCOPE_PATH,
    ).returncode == 0


def _allowed_for(integration: str) -> set[tuple[str, str]]:
    return {
        (
            "PFV-036",
            f"integration {integration} does not integrate the canonical active Task at merge_pending",
        ),
        (
            "PFV-086",
            f"historical integration {integration} lacks a successful exact-SHA push workflow",
        ),
    }


def _exact_reconciliation_history_issue(root: Path, issue: ValidationIssue) -> bool:
    exact = {
        (
            "PFV-035",
            f"task transition at {RECONCILIATION_INTEGRATION_COMMIT} disagrees with trusted prior state implementation_submitted",
        ),
        (
            "PFV-086",
            f"task receipt at {RECONCILIATION_INTEGRATION_COMMIT} is malformed or mismatched",
        ),
    }
    if (issue.code, issue.message) in exact:
        return True
    prefix = (
        f"task {RECONCILIATION_TASK_ID} historical receipt changed "
        "without a lifecycle transition at "
    )
    if issue.code != "PFV-086" or not issue.message.startswith(prefix):
        return False
    return _unchanged_reconciliation_descendant(root, issue.message[len(prefix):])


def apply_followup_bootstrap_compatibility(
    root: Path, issues: list[ValidationIssue]
) -> list[ValidationIssue]:
    """Suppress only exact, evidence-bound false positives from PR #2, #3, and #5."""
    root = root.resolve()
    allowed: set[tuple[str, str]] = set()
    if _exact_repair_boundary_valid(root):
        allowed.update(_allowed_for(REPAIR_INTEGRATION_COMMIT))
    if _exact_trust_boundary_valid(root):
        allowed.update(_allowed_for(TRUST_INTEGRATION_COMMIT))
    reconciliation_valid = _exact_reconciliation_boundary_valid(root)
    if reconciliation_valid:
        allowed.update(_allowed_for(RECONCILIATION_INTEGRATION_COMMIT))
    if not allowed and not reconciliation_valid:
        return list(issues)
    return [
        issue
        for issue in issues
        if (issue.code, issue.message) not in allowed
        and not (reconciliation_valid and _exact_reconciliation_history_issue(root, issue))
    ]
