"""Dependency, dispatch, lifecycle, and transitively closed provenance validation."""
from __future__ import annotations

import hashlib
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
    "merged": ("merge", "hosted_merge", "PFV-087"),
    "current_main_verified": ("current_main", "verified_main_state", "PFV-085"),
}
RECEIPT_FIELDS = {
    "receipt_type", "receipt_version", "verification_type", "subject_kind",
    "repository", "ref", "subject_sha", "transition_from", "transition_to",
    "predecessor_receipt_sha256", "pr_number", "pr_head_sha",
    "integration_sha", "merge_method",
}
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
BRANCH_REF = re.compile(r"^refs/heads/(?!main$).+")
REPOSITORY = "rezahh107/Project-Foundry"
MAIN_REF = "refs/heads/main"
PROGRAM_PATH = "planning/execution-program.v1.json"
STATE_PATH = "planning/current-state.v1.json"
SCOPE_PATH = "planning/scope-baseline.v1.json"
HOSTED_SCHEMA = "project-foundry-hosted-provenance.v1"
HOSTED_SOURCE = "github_rest_v2022_11_28"
WORKFLOW_NAME = "Foundation validation"


@dataclass(frozen=True)
class HostedEvidence:
    trusted: bool
    merge_records: dict[str, dict[str, Any]]
    successful_ci: dict[str, set[str]]
    error: str | None = None


@dataclass(frozen=True)
class GitContext:
    root: Path
    head: str
    event: str
    ref: str
    pr_number: int | None
    pr_head: str | None
    pr_base: str | None
    pr_head_ref: str | None
    push_before: str | None
    synthetic_merge: str | None
    main_tip: str | None
    hosted: HostedEvidence


@dataclass(frozen=True)
class Snapshot:
    commit: str
    status: str
    task_evidence: list[Any]
    current_task_id: str | None
    current_task_status: str | None
    state_evidence: list[Any]
    transition: dict[str, Any] | None


@dataclass(frozen=True)
class ReceiptState:
    record: dict[str, Any]
    digest: str
    transition_commit: str
    status: str


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


def _exists(root: Path, sha: str | None) -> bool:
    return bool(sha and SHA40.fullmatch(sha) and _git(root, "cat-file", "-e", f"{sha}^{{commit}}").returncode == 0)


def _ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return _git(root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def _parents(root: Path, sha: str) -> list[str]:
    value = _value(root, "show", "-s", "--format=%P", sha)
    return value.split() if value else []


def _symbolic_ref(root: Path) -> str | None:
    return _value(root, "symbolic-ref", "-q", "HEAD")


def _json_at(root: Path, sha: str, path: str) -> dict[str, Any] | None:
    result = _git(root, "show", f"{sha}:{path}")
    if result.returncode != 0:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _status_at(root: Path, sha: str, task_id: str) -> tuple[str, list[Any]] | None:
    program = _json_at(root, sha, PROGRAM_PATH)
    if program is None:
        return None
    for task in program.get("tasks", []):
        if isinstance(task, dict) and task.get("id") == task_id and isinstance(task.get("status"), str):
            evidence = task.get("evidence_refs")
            return task["status"], evidence if isinstance(evidence, list) else []
    return None


def _snapshot_at(root: Path, sha: str, task_id: str) -> Snapshot | None:
    observed = _status_at(root, sha, task_id)
    if observed is None:
        return None
    status, task_evidence = observed
    state = _json_at(root, sha, STATE_PATH) or {}
    transition = state.get("last_transition")
    return Snapshot(
        commit=sha,
        status=status,
        task_evidence=task_evidence,
        current_task_id=state.get("current_task_id") if isinstance(state.get("current_task_id"), str) else None,
        current_task_status=state.get("current_task_status") if isinstance(state.get("current_task_status"), str) else None,
        state_evidence=state.get("evidence_refs") if isinstance(state.get("evidence_refs"), list) else [],
        transition=transition if isinstance(transition, dict) else None,
    )


def _load_hosted(root: Path) -> HostedEvidence:
    path_value = os.environ.get("PROJECT_FOUNDRY_HOSTED_PROVENANCE_PATH")
    if not path_value:
        return HostedEvidence(False, {}, {})
    path = Path(path_value).resolve()
    test_mode = os.environ.get("PROJECT_FOUNDRY_TEST_MODE") == "1"
    if not test_mode:
        runner_temp = os.environ.get("RUNNER_TEMP")
        if os.environ.get("GITHUB_ACTIONS") != "true" or not runner_temp:
            return HostedEvidence(False, {}, {}, "hosted evidence is outside a trusted GitHub Actions context")
        try:
            path.relative_to(Path(runner_temp).resolve())
        except ValueError:
            return HostedEvidence(False, {}, {}, "hosted evidence path is not under RUNNER_TEMP")
        try:
            path.relative_to(root.resolve())
        except ValueError:
            pass
        else:
            return HostedEvidence(False, {}, {}, "hosted evidence must not be stored inside the repository")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return HostedEvidence(False, {}, {}, f"hosted evidence cannot be read: {exc}")
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != HOSTED_SCHEMA
        or payload.get("source") != HOSTED_SOURCE
        or payload.get("repository") != REPOSITORY
        or not isinstance(payload.get("merge_records"), list)
        or not isinstance(payload.get("ci_runs"), list)
    ):
        return HostedEvidence(False, {}, {}, "hosted evidence has an invalid envelope")
    merges: dict[str, dict[str, Any]] = {}
    for record in payload["merge_records"]:
        if not isinstance(record, dict):
            continue
        sha = record.get("integration_sha")
        if isinstance(sha, str) and SHA40.fullmatch(sha):
            merges[sha] = record
    successful: dict[str, set[str]] = {}
    for run in payload["ci_runs"]:
        if not isinstance(run, dict):
            continue
        sha = run.get("commit_sha")
        if (
            isinstance(sha, str)
            and SHA40.fullmatch(sha)
            and run.get("workflow_name") == WORKFLOW_NAME
            and run.get("conclusion") == "success"
            and run.get("event") in {"pull_request", "push"}
        ):
            successful.setdefault(sha, set()).add(run["event"])
    return HostedEvidence(True, merges, successful)


def _parse_int(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


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
    main_tip = head if ref == MAIN_REF else None
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
        pr_number=_parse_int(os.environ.get("PROJECT_FOUNDRY_PR_NUMBER")),
        pr_head=os.environ.get("PROJECT_FOUNDRY_PR_HEAD_SHA") or None,
        pr_base=os.environ.get("PROJECT_FOUNDRY_PR_BASE_SHA") or None,
        pr_head_ref=os.environ.get("PROJECT_FOUNDRY_PR_HEAD_REF") or None,
        push_before=os.environ.get("PROJECT_FOUNDRY_PUSH_BEFORE_SHA") or None,
        synthetic_merge=os.environ.get("PROJECT_FOUNDRY_SYNTHETIC_MERGE_SHA") or None,
        main_tip=main_tip,
        hosted=_load_hosted(root),
    )
    if context.pr_head and context.event == "pull_request" and context.pr_head != head:
        issues.append(ValidationIssue("PFV-084", "PR Head context disagrees with checked-out commit"))
    if context.pr_base and not _exists(root, context.pr_base):
        issues.append(ValidationIssue("PFV-084", "PR base commit is absent from fetched history"))
    return context, issues


def _record(records: list[Any]) -> dict[str, Any] | None:
    if len(records) != 1 or not isinstance(records[0], dict):
        return None
    record = records[0]
    if set(record) != RECEIPT_FIELDS:
        return None
    string_fields = {
        "receipt_type", "receipt_version", "verification_type", "subject_kind",
        "repository", "ref", "subject_sha", "transition_from", "transition_to",
    }
    if not all(isinstance(record.get(field), str) for field in string_fields):
        return None
    nullable_strings = {"predecessor_receipt_sha256", "pr_head_sha", "integration_sha", "merge_method"}
    if not all(record.get(field) is None or isinstance(record.get(field), str) for field in nullable_strings):
        return None
    if record.get("pr_number") is not None and (not isinstance(record.get("pr_number"), int) or isinstance(record.get("pr_number"), bool)):
        return None
    return record


def _digest(record: dict[str, Any]) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _fingerprint(records: list[Any]) -> str | None:
    record = _record(records)
    return _digest(record) if record else None


def _linearized_history(context: GitContext) -> tuple[list[str], list[ValidationIssue]]:
    root = context.root
    on_main = context.ref == MAIN_REF or _symbolic_ref(root) == MAIN_REF
    first_parent = _value(root, "rev-list", "--first-parent", "--reverse", context.head)
    if not first_parent:
        return [], [ValidationIssue("PFV-035", "Git history cannot be enumerated")]
    chain = first_parent.splitlines()
    if not on_main:
        base = context.pr_base
        if base and _ancestor(root, base, context.head):
            branch = _value(root, "rev-list", "--first-parent", "--reverse", f"{base}..{context.head}") or ""
            for sha in branch.splitlines():
                if len(_parents(root, sha)) > 1:
                    return [], [ValidationIssue("PFV-036", "PR branch contains an unsupported internal merge")]
        return chain, []

    result: list[str] = []
    seen: set[str] = set()
    for sha in chain:
        parents = _parents(root, sha)
        if len(parents) > 2:
            return [], [ValidationIssue("PFV-036", f"integration commit {sha} has unsupported parent cardinality")]
        if len(parents) == 2:
            first, second = parents
            merge_base = _value(root, "merge-base", first, second)
            if not merge_base:
                return [], [ValidationIssue("PFV-036", f"integration commit {sha} has no deterministic merge base")]
            branch = _value(root, "rev-list", "--first-parent", "--reverse", f"{merge_base}..{second}") or ""
            for branch_sha in branch.splitlines():
                if len(_parents(root, branch_sha)) > 1:
                    return [], [ValidationIssue("PFV-036", f"integrated branch for {sha} contains an unsupported internal merge")]
                if branch_sha not in seen:
                    result.append(branch_sha)
                    seen.add(branch_sha)
        if sha not in seen:
            result.append(sha)
            seen.add(sha)
    return result, []


def _successful_ci(context: GitContext, sha: str, event: str) -> bool:
    return context.hosted.trusted and event in context.hosted.successful_ci.get(sha, set())


def _merge_record(context: GitContext, integration_sha: str) -> dict[str, Any] | None:
    if not context.hosted.trusted:
        return None
    return context.hosted.merge_records.get(integration_sha)


def _validate_hosted_merge_record(
    context: GitContext,
    integration_sha: str,
    *,
    expected_pr_number: int | None = None,
    expected_pr_head: str | None = None,
) -> list[ValidationIssue]:
    record = _merge_record(context, integration_sha)
    if record is None:
        detail = context.hosted.error or "hosted Merge evidence is absent"
        return [ValidationIssue("PFV-087", f"integration {integration_sha} is not bound to an actual hosted Merge: {detail}")]
    parents = _parents(context.root, integration_sha)
    if len(parents) != 2:
        return [ValidationIssue("PFV-036", f"integration {integration_sha} is not a supported two-parent merge commit")]
    first, second = parents
    valid = (
        record.get("repository") == REPOSITORY
        and record.get("integration_sha") == integration_sha
        and record.get("merge_commit_sha") == integration_sha
        and record.get("merged") is True
        and record.get("merge_method") == "merge_commit"
        and record.get("base_ref") == "main"
        and record.get("base_sha") == first
        and record.get("pr_head_sha") == second
        and isinstance(record.get("pr_number"), int)
    )
    if expected_pr_number is not None:
        valid = valid and record.get("pr_number") == expected_pr_number
    if expected_pr_head is not None:
        valid = valid and record.get("pr_head_sha") == expected_pr_head
    if not valid:
        return [ValidationIssue("PFV-087", f"integration {integration_sha} hosted Merge identity is inconsistent")]
    return []


def _validate_integration_boundaries(context: GitContext, history: list[str]) -> tuple[list[ValidationIssue], set[str]]:
    issues: list[ValidationIssue] = []
    integrations: set[str] = set()
    for sha in history:
        parents = _parents(context.root, sha)
        if len(parents) != 2:
            continue
        if _json_at(context.root, sha, PROGRAM_PATH) is None:
            continue
        integrations.add(sha)
        first, second = parents
        if _git(context.root, "diff", "--quiet", second, sha, "--", PROGRAM_PATH, STATE_PATH, SCOPE_PATH).returncode != 0:
            issues.append(ValidationIssue("PFV-036", f"integration {sha} rewrites canonical lifecycle state instead of preserving the merged branch"))
            continue
        second_program = _json_at(context.root, second, PROGRAM_PATH) or {}
        second_state = _json_at(context.root, second, STATE_PATH) or {}
        active_task_id = second_state.get("current_task_id")
        active_status = second_state.get("current_task_status")
        active_task = next(
            (
                item for item in second_program.get("tasks", [])
                if isinstance(item, dict) and item.get("id") == active_task_id
            ),
            None,
        )
        if (
            not isinstance(active_task_id, str)
            or active_status != "merge_pending"
            or not isinstance(active_task, dict)
            or active_task.get("status") != "merge_pending"
        ):
            issues.append(ValidationIssue("PFV-036", f"integration {sha} does not integrate the canonical active Task at merge_pending"))
            continue
        issues.extend(_validate_hosted_merge_record(context, sha, expected_pr_head=second))
        if not _successful_ci(context, second, "pull_request"):
            issues.append(ValidationIssue("PFV-086", f"integrated PR Head {second} lacks successful exact-SHA pull-request CI"))
        if sha == context.head:
            if context.event != "push" or context.ref != MAIN_REF or context.push_before != first:
                issues.append(ValidationIssue("PFV-036", f"integration {sha} lacks exact push-to-main boundary context"))
        elif not _successful_ci(context, sha, "push"):
            issues.append(ValidationIssue("PFV-086", f"historical integration {sha} lacks a successful exact-SHA push workflow"))
    for sha, record in context.hosted.merge_records.items():
        if sha == context.head or _ancestor(context.root, sha, context.head):
            if record.get("merge_method") != "merge_commit":
                issues.append(ValidationIssue("PFV-036", f"hosted integration {sha} uses unsupported merge method {record.get('merge_method')!r}"))
    return issues, integrations


def _transition_metadata(snapshot: Snapshot, previous_status: str | None, task_id: str) -> list[ValidationIssue]:
    if previous_status is None:
        if snapshot.status == "implementation_submitted":
            transition = snapshot.transition or {}
            if (
                snapshot.current_task_id == task_id
                and snapshot.current_task_status == snapshot.status
                and transition.get("from") == "planned"
                and transition.get("to") == snapshot.status
            ):
                return []
        return []
    if snapshot.status == previous_status:
        return []
    transition = snapshot.transition or {}
    if (
        snapshot.current_task_id != task_id
        or snapshot.current_task_status != snapshot.status
        or transition.get("from") != previous_status
        or transition.get("to") != snapshot.status
    ):
        return [ValidationIssue("PFV-035", f"task transition at {snapshot.commit} disagrees with trusted prior state {previous_status}")]
    if snapshot.status not in ALLOWED_TRANSITIONS.get(previous_status, set()):
        return [ValidationIssue("PFV-035", f"task transition {previous_status} -> {snapshot.status} is not allowed")]
    return []


def _receipt_shape(record: dict[str, Any], status: str, previous_status: str) -> bool:
    expected_type, expected_kind, _ = EVIDENCE_STATES[status]
    return (
        record.get("receipt_type") == "git_history_attestation"
        and record.get("receipt_version") == "git-history-attestation.v2"
        and record.get("verification_type") == expected_type
        and record.get("subject_kind") == expected_kind
        and record.get("repository") == REPOSITORY
        and SHA40.fullmatch(record.get("subject_sha", "")) is not None
        and record.get("transition_from") == previous_status
        and record.get("transition_to") == status
    )


def _validate_receipt_transition(
    context: GitContext,
    snapshot: Snapshot,
    previous_snapshot: Snapshot,
    predecessor: ReceiptState | None,
    integration_sha: str | None,
    *,
    historical: bool,
) -> tuple[list[ValidationIssue], ReceiptState | None]:
    status = snapshot.status
    _, _, direct_code = EVIDENCE_STATES[status]
    code = "PFV-086" if historical else direct_code
    record = _record(snapshot.task_evidence)
    if record is None or not _receipt_shape(record, status, previous_snapshot.status):
        return [ValidationIssue(code, f"task receipt at {snapshot.commit} is malformed or mismatched")], None
    digest = _digest(record)
    if _fingerprint(snapshot.state_evidence) != digest:
        return [ValidationIssue("PFV-082" if not historical else "PFV-086", f"task and current-state receipt disagree at {snapshot.commit}")], None
    transition_evidence = (snapshot.transition or {}).get("evidence_refs")
    if not isinstance(transition_evidence, list) or _fingerprint(transition_evidence) != digest:
        return [ValidationIssue("PFV-082" if not historical else "PFV-086", f"transition receipt disagrees at {snapshot.commit}")], None
    if record["subject_sha"] == snapshot.commit or not _exists(context.root, record["subject_sha"]):
        return [ValidationIssue(code, f"task receipt at {snapshot.commit} is self-referential or names a missing subject")], None

    if status == "validated_on_branch":
        valid = (
            record.get("predecessor_receipt_sha256") is None
            and record.get("integration_sha") is None
            and record.get("merge_method") is None
            and record.get("pr_head_sha") is None
            and isinstance(record.get("pr_number"), int)
            and BRANCH_REF.fullmatch(record.get("ref", "")) is not None
            and record["subject_sha"] == previous_snapshot.commit
        )
        if not historical:
            expected_ref = f"refs/heads/{context.pr_head_ref}" if context.pr_head_ref else None
            valid = valid and (
                context.event == "pull_request"
                and context.pr_number == record.get("pr_number")
                and context.pr_head == snapshot.commit == context.head
                and expected_ref == record.get("ref")
                and record["subject_sha"] not in {context.pr_base, context.synthetic_merge}
            )
        else:
            valid = valid and _successful_ci(context, snapshot.commit, "pull_request")
        if not valid:
            return [ValidationIssue(code, f"branch-validation receipt at {snapshot.commit} is untrusted")], None

    elif status == "merged":
        if predecessor is None or predecessor.status != "validated_on_branch":
            return [ValidationIssue("PFV-086", f"Merge receipt at {snapshot.commit} lacks a valid branch-validation predecessor")], None
        if integration_sha is None:
            return [ValidationIssue(code, f"Merge receipt at {snapshot.commit} does not follow a supported integration boundary")], None
        integration_parents = _parents(context.root, integration_sha)
        integrated_task = _status_at(context.root, integration_parents[1], snapshot.current_task_id or "") if len(integration_parents) == 2 else None
        chain_valid = (
            record.get("ref") == MAIN_REF
            and record.get("subject_sha") == integration_sha
            and record.get("integration_sha") == integration_sha
            and record.get("merge_method") == "merge_commit"
            and isinstance(record.get("pr_number"), int)
            and isinstance(record.get("pr_head_sha"), str)
            and SHA40.fullmatch(record["pr_head_sha"]) is not None
            and record.get("predecessor_receipt_sha256") == predecessor.digest
            and record.get("pr_number") == predecessor.record.get("pr_number")
            and integrated_task is not None
            and integrated_task[0] == "merge_pending"
            and _ancestor(context.root, predecessor.transition_commit, record["pr_head_sha"])
            and _successful_ci(context, predecessor.transition_commit, "pull_request")
            and _successful_ci(context, record["pr_head_sha"], "pull_request")
            and _successful_ci(context, integration_sha, "push")
        )
        if not chain_valid:
            return [ValidationIssue("PFV-086", f"Merge receipt at {snapshot.commit} has an incomplete predecessor or integration-CI chain")], None
        hosted_issues = _validate_hosted_merge_record(
            context,
            integration_sha,
            expected_pr_number=record["pr_number"],
            expected_pr_head=record["pr_head_sha"],
        )
        if hosted_issues:
            return [ValidationIssue(code, f"Merge receipt at {snapshot.commit} is not bound to the actual hosted Merge")], None
        if historical and not _successful_ci(context, snapshot.commit, "push"):
            return [ValidationIssue("PFV-086", f"historical Merge receipt {snapshot.commit} lacks successful exact-SHA CI")], None
        if not historical and snapshot.commit == context.head and (
            context.event != "push" or context.ref != MAIN_REF or context.push_before != previous_snapshot.commit
        ):
            return [ValidationIssue("PFV-087", f"Merge receipt {snapshot.commit} lacks exact main-push context")], None

    elif status == "current_main_verified":
        if predecessor is None or predecessor.status != "merged":
            return [ValidationIssue("PFV-086", f"current-main receipt at {snapshot.commit} lacks a valid Merge predecessor")], None
        merge_record = predecessor.record
        valid = (
            record.get("ref") == MAIN_REF
            and record.get("subject_sha") == predecessor.transition_commit
            and record.get("predecessor_receipt_sha256") == predecessor.digest
            and record.get("pr_number") == merge_record.get("pr_number")
            and record.get("pr_head_sha") == merge_record.get("pr_head_sha")
            and record.get("integration_sha") == merge_record.get("integration_sha")
            and record.get("merge_method") == "merge_commit"
            and _successful_ci(context, predecessor.transition_commit, "push")
        )
        if not valid:
            return [ValidationIssue(code, f"current-main receipt at {snapshot.commit} is not transitively bound to the Merge receipt")], None
        if historical and not _successful_ci(context, snapshot.commit, "push"):
            return [ValidationIssue("PFV-086", f"historical current-main receipt {snapshot.commit} lacks successful exact-SHA CI")], None
        if not historical and snapshot.commit == context.head and (
            context.event != "push" or context.ref != MAIN_REF or context.push_before != previous_snapshot.commit
        ):
            return [ValidationIssue("PFV-085", f"current-main receipt {snapshot.commit} lacks exact main-push context")], None

    return [], ReceiptState(record, digest, snapshot.commit, status)


def _validate_task_history(
    context: GitContext,
    history: list[str],
    task_id: str,
    integrations: set[str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    snapshots = [snapshot for sha in history if (snapshot := _snapshot_at(context.root, sha, task_id)) is not None]
    previous: Snapshot | None = None
    predecessor: ReceiptState | None = None
    active_receipt: ReceiptState | None = None
    latest_integration: str | None = None

    for snapshot in snapshots:
        if snapshot.commit in integrations:
            latest_integration = snapshot.commit
        if previous is None:
            issues.extend(_transition_metadata(snapshot, None, task_id))
            if snapshot.status in EVIDENCE_STATES or snapshot.status in {"merge_pending", "current_main_verified"}:
                issues.append(ValidationIssue("PFV-086", f"task {task_id} begins history in an ungrounded lifecycle state {snapshot.status}"))
            previous = snapshot
            continue
        if snapshot.status == previous.status:
            if snapshot.status in EVIDENCE_STATES:
                digest = _fingerprint(snapshot.task_evidence)
                if active_receipt is None or digest != active_receipt.digest:
                    issues.append(ValidationIssue("PFV-086", f"task {task_id} historical receipt changed without a lifecycle transition at {snapshot.commit}"))
            previous = snapshot
            continue

        issues.extend(_transition_metadata(snapshot, previous.status, task_id))
        if snapshot.status == "merge_pending":
            if predecessor is None or predecessor.status != "validated_on_branch":
                issues.append(ValidationIssue("PFV-086", f"task {task_id} entered merge_pending without a valid branch-validation receipt"))
        if snapshot.status in {"planned", "eligible", "active", "implementation_submitted", "validation_pending", "blocked", "invalidated", "superseded"}:
            if snapshot.status in {"planned", "blocked", "invalidated", "superseded"}:
                predecessor = None
            active_receipt = None
        if snapshot.status in EVIDENCE_STATES:
            historical = snapshot.commit != context.head
            receipt_issues, receipt_state = _validate_receipt_transition(
                context,
                snapshot,
                previous,
                predecessor,
                latest_integration,
                historical=historical,
            )
            issues.extend(receipt_issues)
            if receipt_state is not None:
                predecessor = receipt_state
                active_receipt = receipt_state
        previous = snapshot
    return issues


def _current_receipt_shape(task: dict[str, Any], state: dict[str, Any]) -> list[ValidationIssue]:
    status = task["status"]
    if status not in EVIDENCE_STATES:
        return []
    _, _, code = EVIDENCE_STATES[status]
    record = _record(task["evidence_refs"])
    transition = state["last_transition"]
    if record is None or not _receipt_shape(record, status, transition["from"]):
        return [ValidationIssue(code, f"task {task['id']} lacks one structurally valid v2 receipt")]
    if record.get("predecessor_receipt_sha256") is not None and SHA256.fullmatch(record["predecessor_receipt_sha256"]) is None:
        return [ValidationIssue(code, f"task {task['id']} predecessor receipt digest is malformed")]
    for field in ("pr_head_sha", "integration_sha"):
        value = record.get(field)
        if value is not None and SHA40.fullmatch(value) is None:
            return [ValidationIssue(code, f"task {task['id']} {field} is malformed")]
    task_digest = _digest(record)
    state_digest = _fingerprint(state["evidence_refs"])
    transition_digest = _fingerprint(transition["evidence_refs"])
    if task_digest != state_digest or task_digest != transition_digest:
        return [ValidationIssue("PFV-082", "Task, state, and transition evidence must be non-empty and identical")]
    return []


def validate_execution_controls(documents: dict[str, dict[str, Any]], *, root: Path | None = None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    program = documents[PROGRAM_PATH]
    scope = documents[SCOPE_PATH]
    state = documents[STATE_PATH]
    tasks = program["tasks"]
    task_map = _first_by_id(tasks)
    context = None
    history: list[str] = []
    integrations: set[str] = set()
    if root is not None:
        context, context_issues = _context(root.resolve())
        issues.extend(context_issues)
        if context is not None:
            history, history_issues = _linearized_history(context)
            issues.extend(history_issues)
            if history:
                integration_issues, integrations = _validate_integration_boundaries(context, history)
                issues.extend(integration_issues)

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
        issues.extend(_current_receipt_shape(current, state))
        if root is not None and context is None and status in EVIDENCE_STATES:
            _, _, code = EVIDENCE_STATES[status]
            issues.append(ValidationIssue(code, f"task {current['id']} evidence cannot be verified without Git history"))

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
        blocker = task.get("blocker")
        if task["status"] == "blocked":
            valid = isinstance(blocker, dict) and all(blocker.get(key) for key in ("code", "reason", "evidence_refs"))
            if not valid:
                issues.append(ValidationIssue("PFV-083", f"blocked task {task['id']} lacks blocker information"))
        elif blocker is not None:
            issues.append(ValidationIssue("PFV-083", f"non-blocked task {task['id']} may not retain blocker information"))
        if context is not None and history:
            issues.extend(_validate_task_history(context, history, task["id"], integrations))
    return issues
