"""Exact-byte and unique-identity validation for hardened GitHub Actions workflows."""
from __future__ import annotations

import re
from pathlib import Path

try:
    from scripts.render_trusted_workflow import (
        TRUSTED_WORKFLOW_PATH,
        render_trusted_provenance_workflow,
    )
    from scripts.render_workflow import WORKFLOW_PATH, render_foundation_workflow
    from scripts.validation_core import ValidationIssue
except ModuleNotFoundError:
    from render_trusted_workflow import (
        TRUSTED_WORKFLOW_PATH,
        render_trusted_provenance_workflow,
    )
    from render_workflow import WORKFLOW_PATH, render_foundation_workflow
    from validation_core import ValidationIssue

NAME_LINE = re.compile(r"^name:\s*['\"]?([^'\"#]+?)['\"]?\s*(?:#.*)?$")
CANONICAL_NAMES = {
    "Foundation validation": WORKFLOW_PATH,
    "Trusted provenance": TRUSTED_WORKFLOW_PATH,
}


def _exact_bytes(root: Path, relative: str, expected: str, code: str, label: str) -> list[ValidationIssue]:
    path = root / relative
    try:
        actual = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [ValidationIssue(code, f"{label} cannot be read: {exc}")]
    if actual != expected:
        return [ValidationIssue(code, f"{label} drifted from hardened deterministic projection")]
    return []


def _top_level_name(path: Path) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        if not line or line.startswith((" ", "\t", "#")):
            continue
        match = NAME_LINE.fullmatch(line)
        return match.group(1).strip() if match else None
    return None


def _unique_workflow_identities(root: Path) -> list[ValidationIssue]:
    workflows = root / ".github/workflows"
    issues: list[ValidationIssue] = []
    observed: dict[str, list[str]] = {}
    for pattern in ("*.yml", "*.yaml"):
        for path in sorted(workflows.glob(pattern)):
            name = _top_level_name(path)
            if name:
                observed.setdefault(name, []).append(path.relative_to(root).as_posix())
    for name, expected_path in CANONICAL_NAMES.items():
        paths = observed.get(name, [])
        if paths != [expected_path]:
            issues.append(
                ValidationIssue(
                    "PFV-138",
                    f"workflow identity {name!r} must exist exactly once at {expected_path}; observed {paths}",
                )
            )
    return issues


def validate_workflow(root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(
        _exact_bytes(
            root,
            WORKFLOW_PATH,
            render_foundation_workflow(),
            "PFV-136",
            "foundation workflow",
        )
    )
    issues.extend(
        _exact_bytes(
            root,
            TRUSTED_WORKFLOW_PATH,
            render_trusted_provenance_workflow(),
            "PFV-137",
            "trusted provenance workflow",
        )
    )
    issues.extend(_unique_workflow_identities(root))
    return issues
