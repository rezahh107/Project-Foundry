#!/usr/bin/env python3
"""Deterministic structural, semantic, rendering, and workflow validation."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
try:
    from scripts.render_views import render_all
    from scripts.validation_core import RENDER_DIAGNOSTICS, REQUIRED_FILES, ValidationIssue
    from scripts.validation_semantics import _load_and_validate_structures, _validate_semantics
    from scripts.validation_workflow import validate_workflow
except ModuleNotFoundError:
    from render_views import render_all
    from validation_core import RENDER_DIAGNOSTICS, REQUIRED_FILES, ValidationIssue
    from validation_semantics import _load_and_validate_structures, _validate_semantics
    from validation_workflow import validate_workflow

def _validate_rendered_views(root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        expected_views = render_all(root)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return [ValidationIssue("PFV-123", f"critical views cannot be rendered: {exc}")]
    for relative, expected in expected_views.items():
        try:
            actual = (root / relative).read_text(encoding="utf-8")
        except OSError as exc:
            issues.append(ValidationIssue(RENDER_DIAGNOSTICS[relative], f"{relative}: {exc}"))
            continue
        if actual != expected:
            issues.append(
                ValidationIssue(
                    RENDER_DIAGNOSTICS[relative],
                    f"{relative} drifted from deterministic canonical projection",
                )
            )
    return issues


def validate(root: Path) -> list[ValidationIssue]:
    root = root.resolve()
    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    if missing:
        return [ValidationIssue("PFV-001", f"required file missing: {relative}") for relative in missing]

    documents, structural_issues = _load_and_validate_structures(root)
    if structural_issues:
        return structural_issues

    try:
        issues = _validate_semantics(documents)
        issues.extend(_validate_rendered_views(root))
        issues.extend(validate_workflow(root))
        return issues
    except Exception as exc:  # fail closed without leaking malformed-input tracebacks
        return [ValidationIssue("PFV-199", f"controlled validator failure: {type(exc).__name__}: {exc}")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    issues = validate(Path(args.root))
    if issues:
        for issue in issues:
            print(f"{issue.code}: {issue.message}", file=sys.stderr)
        print(f"Validation failed with {len(issues)} issue(s).", file=sys.stderr)
        return 1
    print("Project Foundry foundation validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
