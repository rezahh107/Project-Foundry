from __future__ import annotations

import copy
import json
import shutil
import re
import subprocess
import io
from contextlib import redirect_stderr, redirect_stdout
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

from scripts.render_views import check_views, write_views, main as renderer_main
from scripts.render_workflow import render_foundation_workflow
from scripts.validate_repository import validate, main as validator_main
from scripts.validation_semantics import load_and_validate_structures, validate_semantics

REPO_ROOT = Path(__file__).resolve().parents[1]
STRUCTURAL_FIXTURES = REPO_ROOT / "tests/fixtures/structural_mutations.json"
CRITICAL_VIEWS = ["PROJECT_CHARTER.md", "SYSTEM_MAP.md", "planning/NEXT_WORK.md"]


def copy_repo() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory()
    target = Path(temporary.name) / "repo"
    shutil.copytree(REPO_ROOT, target)
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


def issue_codes(root: Path) -> set[str]:
    return {issue.code for issue in validate(root)}


def run_cli(root: Path, script: str = "scripts/validate_repository.py", *args: str) -> subprocess.CompletedProcess[str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    main = renderer_main if script.endswith("render_views.py") else validator_main
    with redirect_stdout(stdout), redirect_stderr(stderr):
        returncode = main([*args, "--root", str(root)])
    return subprocess.CompletedProcess([], returncode, stdout=stdout.getvalue(), stderr=stderr.getvalue())


def run_subprocess_cli(root: Path, script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, script, *args, "--root", "."],
        cwd=root, text=True, capture_output=True, check=False, timeout=20,
    )


def mutate_json(root: Path, relative: str, mutator: Callable[[Any], None]) -> None:
    document = read_json(root, relative)
    mutator(document)
    write_json(root, relative, document)


