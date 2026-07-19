"""Exact-byte validation for the generated hardened GitHub Actions workflow."""
from __future__ import annotations

from pathlib import Path

try:
    from scripts.render_workflow import WORKFLOW_PATH, render_foundation_workflow
    from scripts.validation_core import ValidationIssue
except ModuleNotFoundError:
    from render_workflow import WORKFLOW_PATH, render_foundation_workflow
    from validation_core import ValidationIssue


def validate_workflow(root: Path) -> list[ValidationIssue]:
    path = root / WORKFLOW_PATH
    try:
        actual = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [ValidationIssue("PFV-001", f"workflow cannot be read: {exc}")]
    expected = render_foundation_workflow()
    if actual != expected:
        return [
            ValidationIssue(
                "PFV-136",
                "foundation workflow drifted from hardened deterministic projection",
            )
        ]
    return []
