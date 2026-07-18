#!/usr/bin/env python3
"""Collect read-only GitHub-hosted Merge and exact-SHA workflow evidence.

This script intentionally uses anonymous HTTPS against the public GitHub REST API.
It does not read GITHUB_TOKEN or any repository secret. The output is written to a
runner-temporary path and is consumed as external evidence by the validator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPOSITORY = "rezahh107/Project-Foundry"
PROGRAM_PATH = "planning/execution-program.v1.json"
SCHEMA = "project-foundry-hosted-provenance.v1"
SOURCE = "github_rest_v2022_11_28"
WORKFLOW_NAME = "Foundation validation"
API_ROOT = "https://api.github.com"


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def git_optional(root: Path, *args: str) -> str | None:
    try:
        value = git(root, *args)
    except RuntimeError:
        return None
    return value or None


def parents(root: Path, sha: str) -> list[str]:
    value = git_optional(root, "show", "-s", "--format=%P", sha)
    return value.split() if value else []


def json_at(root: Path, sha: str, path: str) -> dict[str, Any] | None:
    value = git_optional(root, "show", f"{sha}:{path}")
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def receipt_digest(record: dict[str, Any]) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def scan_candidates(root: Path) -> tuple[set[str], set[str]]:
    commits = git(root, "rev-list", "--reverse", "HEAD").splitlines()
    ci_candidates: set[str] = set()
    integration_candidates: set[str] = set()
    seen_receipts: set[str] = set()
    for sha in commits:
        program = json_at(root, sha, PROGRAM_PATH)
        if program is not None:
            for task in program.get("tasks", []):
                if not isinstance(task, dict):
                    continue
                evidence = task.get("evidence_refs")
                if not isinstance(evidence, list) or len(evidence) != 1 or not isinstance(evidence[0], dict):
                    continue
                record = evidence[0]
                if record.get("receipt_version") != "git-history-attestation.v2":
                    continue
                digest = receipt_digest(record)
                if digest not in seen_receipts:
                    seen_receipts.add(digest)
                    ci_candidates.add(sha)
                integration = record.get("integration_sha")
                if isinstance(integration, str) and len(integration) == 40:
                    integration_candidates.add(integration)
        commit_parents = parents(root, sha)
        if len(commit_parents) == 2 and program is not None:
            integration_candidates.add(sha)
            ci_candidates.add(sha)
            ci_candidates.add(commit_parents[1])
    return ci_candidates, integration_candidates


def api_json(path: str) -> Any:
    request = urllib.request.Request(
        f"{API_ROOT}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Project-Foundry-Provenance-Collector/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub REST request failed for {path}: {exc}") from exc


def collect_ci(commit_sha: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"head_sha": commit_sha, "per_page": 100})
    payload = api_json(f"/repos/{REPOSITORY}/actions/runs?{query}")
    runs = payload.get("workflow_runs", []) if isinstance(payload, dict) else []
    output: list[dict[str, Any]] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        if run.get("name") != WORKFLOW_NAME or run.get("head_sha") != commit_sha:
            continue
        output.append(
            {
                "commit_sha": commit_sha,
                "workflow_name": WORKFLOW_NAME,
                "event": run.get("event"),
                "conclusion": run.get("conclusion"),
                "run_id": run.get("id"),
            }
        )
    return output


def collect_merge(root: Path, integration_sha: str) -> dict[str, Any]:
    commit_parents = parents(root, integration_sha)
    pulls: list[Any] = []
    for attempt in range(5):
        payload = api_json(f"/repos/{REPOSITORY}/commits/{integration_sha}/pulls")
        pulls = payload if isinstance(payload, list) else []
        if any(isinstance(pr, dict) and pr.get("merged_at") for pr in pulls):
            break
        if attempt < 4:
            time.sleep(1 + attempt)
    if len(commit_parents) != 2:
        merged = [pr for pr in pulls if isinstance(pr, dict) and pr.get("merged_at")]
        pr = merged[0] if len(merged) == 1 else {}
        return {
            "repository": REPOSITORY,
            "integration_sha": integration_sha,
            "merge_commit_sha": pr.get("merge_commit_sha"),
            "merged": bool(pr.get("merged_at")),
            "merge_method": "unsupported_one_parent_integration",
            "pr_number": pr.get("number"),
            "pr_head_sha": (pr.get("head") or {}).get("sha") if isinstance(pr.get("head"), dict) else None,
            "base_sha": commit_parents[0] if commit_parents else None,
            "base_ref": (pr.get("base") or {}).get("ref") if isinstance(pr.get("base"), dict) else None,
        }
    first, second = commit_parents
    matches: list[dict[str, Any]] = []
    for pr in pulls:
        if not isinstance(pr, dict) or not pr.get("merged_at"):
            continue
        head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
        base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
        base_repo = base.get("repo") if isinstance(base.get("repo"), dict) else {}
        if (
            pr.get("merge_commit_sha") == integration_sha
            and head.get("sha") == second
            and base.get("ref") == "main"
            and base_repo.get("full_name") == REPOSITORY
        ):
            matches.append(pr)
    if len(matches) != 1:
        return {
            "repository": REPOSITORY,
            "integration_sha": integration_sha,
            "merge_commit_sha": None,
            "merged": False,
            "merge_method": "unverified",
            "pr_number": None,
            "pr_head_sha": second,
            "base_sha": first,
            "base_ref": "main",
        }
    pr = matches[0]
    return {
        "repository": REPOSITORY,
        "integration_sha": integration_sha,
        "merge_commit_sha": integration_sha,
        "merged": True,
        "merge_method": "merge_commit",
        "pr_number": pr.get("number"),
        "pr_head_sha": second,
        "base_sha": first,
        "base_ref": "main",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    try:
        ci_candidates, integration_candidates = scan_candidates(root)
        ci_runs: list[dict[str, Any]] = []
        for sha in sorted(ci_candidates):
            ci_runs.extend(collect_ci(sha))
        merge_records = [collect_merge(root, sha) for sha in sorted(integration_candidates)]
        payload = {
            "schema_version": SCHEMA,
            "source": SOURCE,
            "repository": REPOSITORY,
            "merge_records": merge_records,
            "ci_runs": ci_runs,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(output)
    except Exception as exc:
        print(f"PFV-087: hosted provenance collection failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"Hosted provenance evidence: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
