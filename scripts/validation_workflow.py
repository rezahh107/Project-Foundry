"""GitHub Actions exact-head and supply-chain validation."""
from __future__ import annotations
import re
from pathlib import Path
try:
    from scripts.validation_core import (
        CHECKOUT_PIN, EXPECTED_SHA_EXPRESSION, SETUP_PYTHON_PIN, ValidationIssue,
    )
except ModuleNotFoundError:
    from validation_core import (
        CHECKOUT_PIN, EXPECTED_SHA_EXPRESSION, SETUP_PYTHON_PIN, ValidationIssue,
    )


def validate_workflow(root: Path) -> list[ValidationIssue]:
    workflow_path = root / ".github/workflows/foundation-validation.yml"
    try:
        text = workflow_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [ValidationIssue("PFV-001", f"workflow cannot be read: {exc}")]

    issues: list[ValidationIssue] = []
    uses = re.findall(r"^\s*uses:\s*([^\s#]+)", text, flags=re.MULTILINE)
    if not uses:
        issues.append(ValidationIssue("PFV-130", "workflow contains no pinned action dependencies"))
    for reference in uses:
        if re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", reference) is None:
            issues.append(ValidationIssue("PFV-130", f"workflow action reference is mutable: {reference}"))

    checkout_reference = f"actions/checkout@{CHECKOUT_PIN}"
    setup_reference = f"actions/setup-python@{SETUP_PYTHON_PIN}"
    if checkout_reference not in text:
        issues.append(ValidationIssue("PFV-135", "workflow checkout pin is not the verified commit"))
    if setup_reference not in text:
        issues.append(ValidationIssue("PFV-135", "workflow setup-python pin is not the verified commit"))

    checkout_block_match = re.search(
        r"- name: Check out exact triggering head(?P<body>.*?)(?=\n\s*- name:|\Z)",
        text,
        flags=re.DOTALL,
    )
    if checkout_block_match is None:
        issues.append(ValidationIssue("PFV-132", "exact-head checkout step is missing"))
    else:
        checkout_block = checkout_block_match.group("body")
        if f"ref: {EXPECTED_SHA_EXPRESSION}" not in checkout_block:
            issues.append(ValidationIssue("PFV-132", "checkout ref is not bound to exact triggering head"))
        if "persist-credentials: false" not in checkout_block:
            issues.append(ValidationIssue("PFV-131", "checkout must disable credential persistence"))

    identity_block_match = re.search(
        r"- name: Verify exact checkout identity(?P<body>.*?)(?=\n\s*- name:|\Z)",
        text,
        flags=re.DOTALL,
    )
    if identity_block_match is None:
        issues.append(ValidationIssue("PFV-133", "exact checkout identity step is missing"))
    else:
        identity_block = identity_block_match.group("body")
        required_fragments = [
            f"EXPECTED_SHA: {EXPECTED_SHA_EXPRESSION}",
            'actual_sha="$(git rev-parse HEAD)"',
            'test "$actual_sha" = "$EXPECTED_SHA"',
            "EVENT_NAME: ${{ github.event_name }}",
            "TRIGGER_REF: ${{ github.ref }}",
            "printf 'event_name=%s\\ntrigger_ref=%s\\nexpected_sha=%s\\nactual_sha=%s\\n'",
        ]
        for fragment in required_fragments:
            if fragment not in identity_block:
                issues.append(ValidationIssue("PFV-133", f"identity step is missing required assertion: {fragment}"))

    permissions_match = re.search(
        r"^permissions:\s*\n(?P<body>(?:^[ \t]+.*(?:\n|$))*)",
        text,
        flags=re.MULTILINE,
    )
    if permissions_match is None:
        issues.append(ValidationIssue("PFV-134", "workflow permissions block is missing"))
    else:
        permissions_body = permissions_match.group("body")
        if re.search(r"^\s*contents:\s*read\s*$", permissions_body, flags=re.MULTILINE) is None:
            issues.append(ValidationIssue("PFV-134", "workflow must use contents: read permissions"))
        if re.search(r"\bwrite\b", permissions_body):
            issues.append(ValidationIssue("PFV-134", "workflow permissions may not grant write access"))
    return issues
