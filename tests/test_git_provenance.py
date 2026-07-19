from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tests.support import REPO_ROOT, read_json, run_subprocess_cli, write_json

REPOSITORY = "rezahh107/Project-Foundry"
WORKFLOW = "Foundation validation"


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False, timeout=30)
    if result.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def receipt(kind: str, subject: str, source: str, target: str, *, ref: str, predecessor: str | None = None,
            pr_head: str | None = None, integration: str | None = None, method: str | None = None,
            repository: str = REPOSITORY) -> dict[str, Any]:
    subject_kind = {"branch_validation": "pull_request_head", "merge": "hosted_merge", "current_main": "verified_main_state"}[kind]
    return {
        "receipt_type": "git_history_attestation", "receipt_version": "git-history-attestation.v2",
        "verification_type": kind, "subject_kind": subject_kind, "repository": repository, "ref": ref,
        "subject_sha": subject, "transition_from": source, "transition_to": target,
        "predecessor_receipt_sha256": predecessor, "pr_number": 1, "pr_head_sha": pr_head,
        "integration_sha": integration, "merge_method": method,
    }


def digest(record: dict[str, Any]) -> str:
    raw = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def ci(sha: str, event: str, run_id: int = 1) -> dict[str, Any]:
    return {"commit_sha": sha, "workflow_name": WORKFLOW, "event": event, "conclusion": "success", "run_id": run_id}


class Repo:
    def __init__(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        shutil.copytree(REPO_ROOT, self.root, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache"))
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Foundry Test")
        git(self.root, "config", "user.email", "foundry@example.invalid")
        self.base = self.commit("baseline")

    def close(self) -> None:
        self.temp.cleanup()

    def commit(self, message: str) -> str:
        git(self.root, "add", "-A")
        git(self.root, "commit", "--allow-empty", "-m", message)
        return git(self.root, "rev-parse", "HEAD")

    def set_status(self, status: str, source: str, evidence: list[Any] | None = None, *, render: bool = True) -> None:
        evidence = evidence or []
        program = read_json(self.root, "planning/execution-program.v1.json")
        task = next(item for item in program["tasks"] if item["id"] == "PF-001")
        task["status"], task["evidence_refs"] = status, evidence
        write_json(self.root, "planning/execution-program.v1.json", program)
        state = read_json(self.root, "planning/current-state.v1.json")
        state.update({"current_task_id": "PF-001", "current_task_status": status,
                      "active_context_path": ["PF-NORTH-STAR-001", "PF-PROGRAM-001", "WP-01", "PF-001"],
                      "evidence_refs": evidence,
                      "last_transition": {"from": source, "to": status, "reason": "test", "evidence_refs": evidence},
                      "completed_task_ids": ["PF-001"] if status == "current_main_verified" else [],
                      "next_task_id": "PF-002" if status == "current_main_verified" else "PF-001"})
        write_json(self.root, "planning/current-state.v1.json", state)
        if render:
            result = run_subprocess_cli(self.root, "scripts/render_views.py", "--write")
            if result.returncode:
                raise AssertionError(result.stderr)

    def hosted(self, merges: list[dict[str, Any]] | None = None, runs: list[dict[str, Any]] | None = None) -> str:
        path = Path(self.temp.name) / "hosted.json"
        path.write_text(json.dumps({"schema_version": "project-foundry-hosted-provenance.v1",
                                    "source": "github_rest_v2022_11_28", "repository": REPOSITORY,
                                    "merge_records": merges or [], "ci_runs": runs or []}) + "\n")
        return str(path)

    def pr_env(self, hosted: str, head: str) -> dict[str, str]:
        return {"PROJECT_FOUNDRY_TEST_MODE": "1", "PROJECT_FOUNDRY_HOSTED_PROVENANCE_PATH": hosted,
                "PROJECT_FOUNDRY_EVENT_NAME": "pull_request", "PROJECT_FOUNDRY_EXPECTED_HEAD_SHA": head,
                "PROJECT_FOUNDRY_GITHUB_REF": "refs/pull/1/merge", "PROJECT_FOUNDRY_PR_NUMBER": "1",
                "PROJECT_FOUNDRY_PR_HEAD_SHA": head, "PROJECT_FOUNDRY_PR_BASE_SHA": self.base,
                "PROJECT_FOUNDRY_PR_HEAD_REF": "feature", "PROJECT_FOUNDRY_SYNTHETIC_MERGE_SHA": "f" * 40}

    def push_env(self, hosted: str, before: str, head: str) -> dict[str, str]:
        return {"PROJECT_FOUNDRY_TEST_MODE": "1", "PROJECT_FOUNDRY_HOSTED_PROVENANCE_PATH": hosted,
                "PROJECT_FOUNDRY_EVENT_NAME": "push", "PROJECT_FOUNDRY_EXPECTED_HEAD_SHA": head,
                "PROJECT_FOUNDRY_GITHUB_REF": "refs/heads/main", "PROJECT_FOUNDRY_PUSH_BEFORE_SHA": before}

    def validate(self, env: dict[str, str]):
        return run_subprocess_cli(self.root, "scripts/validate_repository.py", env=env)

    def branch(self, valid: bool = True) -> tuple[dict[str, Any] | None, str, str]:
        git(self.root, "checkout", "-b", "feature")
        self.set_status("validation_pending", "implementation_submitted")
        self.commit("validation pending")
        subject = self.commit("branch subject")
        record = receipt("branch_validation", subject, "validation_pending", "validated_on_branch", ref="refs/heads/feature") if valid else None
        self.set_status("validated_on_branch", "validation_pending", [record] if record else [], render=valid)
        return record, self.commit("branch receipt"), subject

    def merge_pending(self, valid: bool = True) -> tuple[dict[str, Any] | None, str, str]:
        record, receipt_commit, _ = self.branch(valid)
        self.set_status("merge_pending", "validated_on_branch")
        return record, receipt_commit, self.commit("merge pending")

    def integrate(self, strategy: str = "ort") -> dict[str, Any]:
        branch_receipt, branch_commit, pr_head = self.merge_pending()
        assert branch_receipt
        git(self.root, "checkout", "main")
        args = ["merge", "--no-ff", "feature", "-m", "integration"] if strategy == "ort" else ["merge", "--no-ff", "-s", "ours", "feature", "-m", "integration"]
        git(self.root, *args)
        integration = git(self.root, "rev-parse", "HEAD")
        parents = git(self.root, "show", "-s", "--format=%P", integration).split()
        merge_record = {"repository": REPOSITORY, "integration_sha": integration, "merge_commit_sha": integration,
                        "merged": True, "merge_method": "merge_commit", "pr_number": 1,
                        "pr_head_sha": parents[1], "base_sha": parents[0], "base_ref": "main"}
        return {"branch_receipt": branch_receipt, "branch_commit": branch_commit, "pr_head": pr_head,
                "integration": integration, "parents": parents, "merge_record": merge_record}

    def full_chain(self) -> dict[str, Any]:
        data = self.integrate()
        merge_receipt = receipt("merge", data["integration"], "merge_pending", "merged", ref="refs/heads/main",
                                predecessor=digest(data["branch_receipt"]), pr_head=data["pr_head"],
                                integration=data["integration"], method="merge_commit")
        self.set_status("merged", "merge_pending", [merge_receipt])
        merge_commit = self.commit("merge receipt")
        current = receipt("current_main", merge_commit, "merged", "current_main_verified", ref="refs/heads/main",
                          predecessor=digest(merge_receipt), pr_head=data["pr_head"],
                          integration=data["integration"], method="merge_commit")
        self.set_status("current_main_verified", "merged", [current])
        data.update({"merge_receipt": merge_receipt, "merge_receipt_commit": merge_commit,
                     "current_receipt": current, "verification_commit": self.commit("current main")})
        return data


class GitProvenanceIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.r = Repo()

    def tearDown(self) -> None:
        self.r.close()

    def ok(self, env: dict[str, str]) -> None:
        result = self.r.validate(env)
        self.assertEqual(0, result.returncode, result.stderr)

    def bad(self, env: dict[str, str], code: str) -> None:
        result = self.r.validate(env)
        self.assertNotEqual(0, result.returncode)
        self.assertIn(code, result.stderr)
        self.assertNotIn("PFV-199", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_collector_avoids_network_without_candidates(self) -> None:
        output = Path(self.r.temp.name) / "collector.json"
        result = run_subprocess_cli(self.r.root, "scripts/collect_hosted_provenance.py", "--output", str(output))
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(output.read_text())
        self.assertEqual([], payload["merge_records"])
        self.assertEqual([], payload["ci_runs"])

    def test_branch_receipt_chain_and_latest_head_only_push(self) -> None:
        record, branch_commit, _ = self.r.branch()
        self.ok(self.r.pr_env(self.r.hosted(), branch_commit))
        self.r.set_status("merge_pending", "validated_on_branch")
        latest = self.r.commit("latest")
        self.bad(self.r.pr_env(self.r.hosted(), latest), "PFV-086")
        self.ok(self.r.pr_env(self.r.hosted(runs=[ci(branch_commit, "pull_request")]), latest))
        self.assertIsNotNone(record)

    def test_invalid_or_empty_branch_receipt_cannot_be_laundered(self) -> None:
        _, branch_commit, _ = self.r.branch(False)
        self.r.set_status("merge_pending", "validated_on_branch")
        latest = self.r.commit("launder attempt")
        self.bad(self.r.pr_env(self.r.hosted(runs=[ci(branch_commit, "pull_request")]), latest), "PFV-086")

    def test_actual_merge_commit_passes_and_first_parent_cannot_replace_branch(self) -> None:
        data = self.r.integrate()
        hosted = self.r.hosted([data["merge_record"]], [ci(data["branch_commit"], "pull_request"), ci(data["pr_head"], "pull_request")])
        self.ok(self.r.push_env(hosted, data["parents"][0], data["integration"]))
        self.r.close(); self.r = Repo()
        bad = self.r.integrate("ours")
        hosted = self.r.hosted([bad["merge_record"]], [ci(bad["branch_commit"], "pull_request"), ci(bad["pr_head"], "pull_request")])
        self.bad(self.r.push_env(hosted, bad["parents"][0], bad["integration"]), "PFV-036")

    def test_wrong_branch_state_fails(self) -> None:
        _, branch_commit, branch_head = self.r.branch()
        git(self.r.root, "checkout", "main"); git(self.r.root, "merge", "--no-ff", "feature", "-m", "wrong state")
        integration = git(self.r.root, "rev-parse", "HEAD"); parents = git(self.r.root, "show", "-s", "--format=%P", integration).split()
        record = {"repository": REPOSITORY, "integration_sha": integration, "merge_commit_sha": integration, "merged": True,
                  "merge_method": "merge_commit", "pr_number": 1, "pr_head_sha": parents[1], "base_sha": parents[0], "base_ref": "main"}
        hosted = self.r.hosted([record], [ci(branch_commit, "pull_request"), ci(branch_head, "pull_request")])
        self.bad(self.r.push_env(hosted, parents[0], integration), "PFV-036")

    def test_squash_and_rebase_are_rejected(self) -> None:
        for method in ("squash", "rebase"):
            with self.subTest(method=method):
                self.r.close(); self.r = Repo(); _, branch_commit, pr_head = self.r.merge_pending()
                git(self.r.root, "checkout", "main"); git(self.r.root, "merge", "--squash", "feature")
                integration = self.r.commit(method); parent = git(self.r.root, "rev-parse", f"{integration}^1")
                record = {"repository": REPOSITORY, "integration_sha": integration, "merge_commit_sha": integration, "merged": True,
                          "merge_method": method, "pr_number": 1, "pr_head_sha": pr_head, "base_sha": parent, "base_ref": "main"}
                hosted = self.r.hosted([record], [ci(branch_commit, "pull_request"), ci(pr_head, "pull_request")])
                self.bad(self.r.push_env(hosted, parent, integration), "PFV-036")

    def test_direct_push_and_missing_integration_ci_cannot_be_merge(self) -> None:
        data = self.r.integrate()
        merge_receipt = receipt("merge", data["integration"], "merge_pending", "merged", ref="refs/heads/main",
                                predecessor=digest(data["branch_receipt"]), pr_head=data["pr_head"],
                                integration=data["integration"], method="merge_commit")
        self.r.set_status("merged", "merge_pending", [merge_receipt]); latest = self.r.commit("receipt")
        no_integration_ci = self.r.hosted([data["merge_record"]], [ci(data["branch_commit"], "pull_request"), ci(data["pr_head"], "pull_request")])
        self.bad(self.r.push_env(no_integration_ci, data["integration"], latest), "PFV-086")
        self.r.close(); self.r = Repo(); branch_receipt, branch_commit, pr_head = self.r.merge_pending(); assert branch_receipt
        git(self.r.root, "checkout", "main"); git(self.r.root, "merge", "--ff-only", "feature"); direct = self.r.commit("direct")
        false_receipt = receipt("merge", direct, "merge_pending", "merged", ref="refs/heads/main",
                                predecessor=digest(branch_receipt), pr_head=pr_head, integration=direct, method="merge_commit")
        self.r.set_status("merged", "merge_pending", [false_receipt]); latest = self.r.commit("false receipt")
        self.bad(self.r.push_env(self.r.hosted(runs=[ci(branch_commit, "pull_request"), ci(pr_head, "pull_request"), ci(direct, "push")]), direct, latest), "PFV-087")

    def test_invalid_merge_receipt_and_digest_cannot_be_laundered(self) -> None:
        data = self.r.integrate()
        malformed = receipt("merge", data["integration"], "merge_pending", "merged", ref="refs/heads/main",
                            predecessor="0" * 64, pr_head=data["pr_head"], integration=data["integration"],
                            method="merge_commit", repository="other/repository")
        self.r.set_status("merged", "merge_pending", [malformed], render=False); malformed_commit = self.r.commit("malformed")
        current = receipt("current_main", malformed_commit, "merged", "current_main_verified", ref="refs/heads/main",
                          predecessor=digest(malformed), pr_head=data["pr_head"], integration=data["integration"], method="merge_commit")
        self.r.set_status("current_main_verified", "merged", [current]); latest = self.r.commit("launder")
        runs = [ci(data["branch_commit"], "pull_request"), ci(data["pr_head"], "pull_request"), ci(data["integration"], "push"), ci(malformed_commit, "push")]
        self.bad(self.r.push_env(self.r.hosted([data["merge_record"]], runs), malformed_commit, latest), "PFV-086")

    def test_valid_end_to_end_chain_survives_later_commit_and_unlocks_pf002(self) -> None:
        data = self.r.full_chain()
        runs = [ci(data["branch_commit"], "pull_request"), ci(data["pr_head"], "pull_request"),
                ci(data["integration"], "push"), ci(data["merge_receipt_commit"], "push")]
        hosted = self.r.hosted([data["merge_record"]], runs)
        self.ok(self.r.push_env(hosted, data["merge_receipt_commit"], data["verification_commit"]))
        before = data["verification_commit"]
        (self.r.root / "later.txt").write_text("later\n"); later = self.r.commit("later")
        hosted = self.r.hosted([data["merge_record"]], runs + [ci(data["verification_commit"], "push")])
        self.ok(self.r.push_env(hosted, before, later))
        program = read_json(self.r.root, "planning/execution-program.v1.json")
        pf002 = next(item for item in program["tasks"] if item["id"] == "PF-002"); pf002["status"] = "eligible"
        write_json(self.r.root, "planning/execution-program.v1.json", program)
        scope = read_json(self.r.root, "planning/scope-baseline.v1.json"); scope["active_task_id"] = "PF-002"; write_json(self.r.root, "planning/scope-baseline.v1.json", scope)
        state = read_json(self.r.root, "planning/current-state.v1.json"); state.update({"current_task_id": "PF-002", "current_task_status": "eligible",
            "active_context_path": ["PF-NORTH-STAR-001", "PF-PROGRAM-001", "WP-01", "PF-002"], "next_task_id": "PF-002",
            "evidence_refs": [], "last_transition": {"from": "planned", "to": "eligible", "reason": "PF-001 verified", "evidence_refs": []}})
        write_json(self.r.root, "planning/current-state.v1.json", state)
        result = run_subprocess_cli(self.r.root, "scripts/render_views.py", "--write"); self.assertEqual(0, result.returncode, result.stderr)
        next_commit = self.r.commit("dispatch PF-002")
        self.ok(self.r.push_env(hosted, later, next_commit))


if __name__ == "__main__":
    unittest.main()
