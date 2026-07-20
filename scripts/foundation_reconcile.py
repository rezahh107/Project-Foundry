#!/usr/bin/env python3
"""One-time, default-branch-controlled reconciliation for PF-001.

This helper is executed only by the trusted reconciliation workflow loaded from
main. It writes canonical state and deterministic views; the workflow creates
and pushes the atomic Git commits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROGRAM_PATH = ROOT / "planning/execution-program.v1.json"
STATE_PATH = ROOT / "planning/current-state.v1.json"
SCOPE_PATH = ROOT / "planning/scope-baseline.v1.json"
README_PATH = ROOT / "README.md"
TASK_ID = "PF-001"
NEXT_TASK_ID = "PF-002"
REPOSITORY = "rezahh107/Project-Foundry"
MAIN_REF = "refs/heads/main"
ORCHESTRATOR_PATH = ROOT / ".github/workflows/foundation-reconciliation.yml"
SELF_PATH = Path(__file__).resolve()


def run(*args: str) -> str:
    result = subprocess.run(
        list(args), cwd=ROOT, text=True, capture_output=True, check=False, timeout=60
    )
    if result.returncode:
        raise RuntimeError(f"{' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} is not a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def task(program: dict[str, Any]) -> dict[str, Any]:
    for item in program["tasks"]:
        if isinstance(item, dict) and item.get("id") == TASK_ID:
            return item
    raise RuntimeError(f"{TASK_ID} is absent")


def receipt_digest(record: dict[str, Any]) -> str:
    encoded = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def receipt(
    verification_type: str,
    subject_kind: str,
    subject_sha: str,
    source: str,
    target: str,
    *,
    ref: str,
    predecessor: str | None,
    pr_number: int,
    pr_head_sha: str | None,
    integration_sha: str | None,
    merge_method: str | None,
) -> dict[str, Any]:
    return {
        "receipt_type": "git_history_attestation",
        "receipt_version": "git-history-attestation.v2",
        "verification_type": verification_type,
        "subject_kind": subject_kind,
        "repository": REPOSITORY,
        "ref": ref,
        "subject_sha": subject_sha,
        "transition_from": source,
        "transition_to": target,
        "predecessor_receipt_sha256": predecessor,
        "pr_number": pr_number,
        "pr_head_sha": pr_head_sha,
        "integration_sha": integration_sha,
        "merge_method": merge_method,
    }


def set_status(
    status: str,
    source: str,
    reason: str,
    evidence: list[Any] | None = None,
    *,
    next_action: str,
) -> None:
    evidence = evidence or []
    program = read_json(PROGRAM_PATH)
    current_task = task(program)
    if current_task["status"] != source:
        raise RuntimeError(
            f"expected {TASK_ID} at {source}, observed {current_task['status']}"
        )
    current_task["status"] = status
    current_task["evidence_refs"] = evidence
    write_json(PROGRAM_PATH, program)

    state = read_json(STATE_PATH)
    if state["current_task_id"] != TASK_ID or state["current_task_status"] != source:
        raise RuntimeError("current-state does not match the expected transition source")
    state["current_task_status"] = status
    state["evidence_refs"] = evidence
    state["last_transition"] = {
        "from": source,
        "to": status,
        "reason": reason,
        "evidence_refs": evidence,
    }
    state["completed_task_ids"] = [TASK_ID] if status == "current_main_verified" else []
    state["next_task_id"] = NEXT_TASK_ID if status == "current_main_verified" else TASK_ID
    state["next_action"] = next_action
    write_json(STATE_PATH, state)
    render_views()


def render_views() -> None:
    run("python", "scripts/render_views.py", "--write", "--root", ".")


def json_at(sha: str, relative: str) -> dict[str, Any] | None:
    result = subprocess.run(
        ["git", "show", f"{sha}:{relative}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def branch_receipt(pr_head: str) -> dict[str, Any]:
    commits = run("git", "rev-list", "--reverse", pr_head).splitlines()
    candidate: dict[str, Any] | None = None
    for sha in commits:
        program = json_at(sha, "planning/execution-program.v1.json")
        if not program:
            continue
        try:
            item = next(
                value for value in program.get("tasks", [])
                if isinstance(value, dict) and value.get("id") == TASK_ID
            )
        except StopIteration:
            continue
        evidence = item.get("evidence_refs")
        if (
            item.get("status") == "validated_on_branch"
            and isinstance(evidence, list)
            and len(evidence) == 1
            and isinstance(evidence[0], dict)
            and evidence[0].get("verification_type") == "branch_validation"
        ):
            candidate = evidence[0]
    if candidate is None:
        raise RuntimeError("validated branch receipt is absent from PR history")
    return candidate


def update_readme() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    marker = "## Current lifecycle truth"
    if marker not in text:
        raise RuntimeError("README lifecycle marker is absent")
    prefix = text.split(marker, 1)[0].rstrip()
    replacement = f"""{prefix}\n\n{marker}\n\nThe governed repository foundation is verified on current `main`. The canonical next Task is `PF-002`: research and select the bounded MVP dogfooding implementation strategy. Future sessions must recover the North Star, Program, Scope, current state, and exact next action from the canonical repository files rather than regenerate them.\n"""
    README_PATH.write_text(replacement, encoding="utf-8")


def command_validation_pending(_: argparse.Namespace) -> None:
    set_status(
        "validation_pending",
        "implementation_submitted",
        "Begin exact branch validation of the merged Foundation implementation and trusted provenance controls.",
        next_action="Complete exact branch validation for PF-001 and record a branch-validation receipt.",
    )


def command_validated(args: argparse.Namespace) -> None:
    record = receipt(
        "branch_validation",
        "pull_request_head",
        args.subject_sha,
        "validation_pending",
        "validated_on_branch",
        ref=f"refs/heads/{args.branch}",
        predecessor=None,
        pr_number=args.pr_number,
        pr_head_sha=None,
        integration_sha=None,
        merge_method=None,
    )
    set_status(
        "validated_on_branch",
        "validation_pending",
        "The exact immutable branch subject passed the canonical Foundation validation workflow.",
        [record],
        next_action="Advance the exact validated branch to merge_pending after its canonical CI and external attestation succeed.",
    )


def command_merge_pending(_: argparse.Namespace) -> None:
    set_status(
        "merge_pending",
        "validated_on_branch",
        "The exact PR Head has successful canonical CI and external hosted-provenance attestation.",
        next_action="Merge this exact PR Head with the supported two-parent merge-commit method.",
    )


def command_merged(args: argparse.Namespace) -> None:
    predecessor = branch_receipt(args.pr_head_sha)
    record = receipt(
        "merge",
        "hosted_merge",
        args.integration_sha,
        "merge_pending",
        "merged",
        ref=MAIN_REF,
        predecessor=receipt_digest(predecessor),
        pr_number=args.pr_number,
        pr_head_sha=args.pr_head_sha,
        integration_sha=args.integration_sha,
        merge_method="merge_commit",
    )
    set_status(
        "merged",
        "merge_pending",
        "The exact merge commit is bound to the hosted pull request, its validated Head, and current main history.",
        [record],
        next_action="Verify the merged receipt on the exact current main commit and close PF-001 with a current-main receipt.",
    )


def command_verified(_: argparse.Namespace) -> None:
    program = read_json(PROGRAM_PATH)
    current_task = task(program)
    evidence = current_task.get("evidence_refs")
    if (
        current_task.get("status") != "merged"
        or not isinstance(evidence, list)
        or len(evidence) != 1
        or not isinstance(evidence[0], dict)
    ):
        raise RuntimeError("one valid Merge receipt is required")
    merge_record = evidence[0]
    subject_sha = run("git", "rev-parse", "HEAD")
    record = receipt(
        "current_main",
        "verified_main_state",
        subject_sha,
        "merged",
        "current_main_verified",
        ref=MAIN_REF,
        predecessor=receipt_digest(merge_record),
        pr_number=int(merge_record["pr_number"]),
        pr_head_sha=str(merge_record["pr_head_sha"]),
        integration_sha=str(merge_record["integration_sha"]),
        merge_method="merge_commit",
    )
    set_status(
        "current_main_verified",
        "merged",
        "PF-001 and its transitive evidence chain are verified on current main.",
        [record],
        next_action="Execute PF-002: research and select the bounded MVP dogfooding implementation strategy using DEC-002 and the registered Decision Intelligence criteria; do not regenerate the North Star, Program, Scope, or Task inventory.",
    )

    program = read_json(PROGRAM_PATH)
    program["status"] = "active"
    write_json(PROGRAM_PATH, program)
    scope = read_json(SCOPE_PATH)
    scope["status"] = "active"
    write_json(SCOPE_PATH, scope)
    state = read_json(STATE_PATH)
    state["state_version"] = "0.2.0"
    state["phase"] = "foundation_verified_ready_for_pf002"
    write_json(STATE_PATH, state)
    update_readme()
    render_views()

    if ORCHESTRATOR_PATH.exists():
        ORCHESTRATOR_PATH.unlink()
    if SELF_PATH.exists():
        SELF_PATH.unlink()


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("validation-pending").set_defaults(func=command_validation_pending)
    validated = commands.add_parser("validated-on-branch")
    validated.add_argument("--subject-sha", required=True)
    validated.add_argument("--pr-number", type=int, required=True)
    validated.add_argument("--branch", required=True)
    validated.set_defaults(func=command_validated)
    commands.add_parser("merge-pending").set_defaults(func=command_merge_pending)
    merged = commands.add_parser("merged")
    merged.add_argument("--integration-sha", required=True)
    merged.add_argument("--pr-head-sha", required=True)
    merged.add_argument("--pr-number", type=int, required=True)
    merged.set_defaults(func=command_merged)
    commands.add_parser("current-main-verified").set_defaults(func=command_verified)
    return root


def main() -> int:
    args = parser().parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
