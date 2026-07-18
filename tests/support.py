from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable, Iterator

from scripts.render_views import main as renderer_main
from scripts.render_workflow import render_foundation_workflow
from scripts.validate_repository import main as validator_main, validate
from scripts.validation_semantics import load_and_validate_structures, validate_semantics

REPO_ROOT = Path(__file__).resolve().parents[1]
STRUCTURAL_FIXTURES = REPO_ROOT / "tests/fixtures/structural_mutations.json"
CRITICAL_VIEWS = ["PROJECT_CHARTER.md", "SYSTEM_MAP.md", "planning/NEXT_WORK.md"]


def copy_repo() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory()
    target = Path(temporary.name) / "repo"
    shutil.copytree(
        REPO_ROOT,
        target,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache"),
    )
    return temporary, target


def read_json(root: Path, relative: str) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: str, value: Any) -> None:
    (root / relative).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def set_path(document: Any, path: list[Any], value: Any) -> None:
    cursor = document
    for segment in path[:-1]:
        cursor = cursor[segment]
    cursor[path[-1]] = value


def delete_path(document: Any, path: list[Any]) -> None:
    cursor = document
    for segment in path[:-1]:
        cursor = cursor[segment]
    del cursor[path[-1]]


def apply_json_case(root: Path, case: dict[str, Any]) -> None:
    document = read_json(root, case["file"])
    if "replace_document" in case:
        document = case["replace_document"]
    elif "delete_path" in case:
        delete_path(document, case["delete_path"])
    else:
        set_path(document, case["path"], case["value"])
    write_json(root, case["file"], document)


@contextmanager
def patched_env(values: dict[str, str] | None = None) -> Iterator[None]:
    values = values or {}
    keys = set(values) | {
        "PROJECT_FOUNDRY_EVENT_NAME",
        "PROJECT_FOUNDRY_EXPECTED_HEAD_SHA",
        "PROJECT_FOUNDRY_GITHUB_REF",
        "PROJECT_FOUNDRY_PR_HEAD_SHA",
        "PROJECT_FOUNDRY_PR_BASE_SHA",
        "PROJECT_FOUNDRY_PR_HEAD_REF",
        "PROJECT_FOUNDRY_SYNTHETIC_MERGE_SHA",
        "PROJECT_FOUNDRY_PUSH_BEFORE_SHA",
        "PROJECT_FOUNDRY_CURRENT_MAIN_SHA",
    }
    previous = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)
        os.environ.update(values)
        yield
    finally:
        for key in keys:
            os.environ.pop(key, None)
        for key, value in previous.items():
            if value is not None:
                os.environ[key] = value


def issue_codes(
    root: Path,
    *,
    current_main_sha: str | None = None,
    env: dict[str, str] | None = None,
) -> set[str]:
    values = dict(env or {})
    if current_main_sha is not None:
        values["PROJECT_FOUNDRY_CURRENT_MAIN_SHA"] = current_main_sha
    with patched_env(values):
        return {issue.code for issue in validate(root)}


def run_cli(
    root: Path,
    script: str = "scripts/validate_repository.py",
    *args: str,
    current_main_sha: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    main = renderer_main if script.endswith("render_views.py") else validator_main
    values = dict(env or {})
    if current_main_sha is not None:
        values["PROJECT_FOUNDRY_CURRENT_MAIN_SHA"] = current_main_sha
    with patched_env(values), redirect_stdout(stdout), redirect_stderr(stderr):
        returncode = main([*args, "--root", str(root)])
    return subprocess.CompletedProcess([], returncode, stdout=stdout.getvalue(), stderr=stderr.getvalue())


def run_subprocess_cli(
    root: Path,
    script: str,
    *args: str,
    current_main_sha: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    process_env = os.environ.copy()
    for key in list(process_env):
        if key.startswith("PROJECT_FOUNDRY_"):
            process_env.pop(key, None)
    if current_main_sha is not None:
        process_env["PROJECT_FOUNDRY_CURRENT_MAIN_SHA"] = current_main_sha
    process_env.update(env or {})
    return subprocess.run(
        [sys.executable, script, *args, "--root", "."],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
        env=process_env,
    )


def mutate_json(root: Path, relative: str, mutator: Callable[[Any], None]) -> None:
    document = read_json(root, relative)
    mutator(document)
    write_json(root, relative, document)
