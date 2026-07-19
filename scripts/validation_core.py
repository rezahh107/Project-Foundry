"""Shared deterministic validation primitives."""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALLOWED_TASK_STATES = {
    "planned", "eligible", "active", "implementation_submitted",
    "validation_pending", "validated_on_branch", "merge_pending", "merged",
    "current_main_verified", "complete", "blocked", "invalidated", "superseded",
}

CANONICAL_DOCUMENTS = {
    "governance/project-constitution.v1.json": "schemas/project-constitution.schema.json",
    "planning/execution-program.v1.json": "schemas/execution-program.schema.json",
    "planning/scope-baseline.v1.json": "schemas/scope-baseline.schema.json",
    "planning/current-state.v1.json": "schemas/current-state.schema.json",
    "decisions/decision-registry.v1.json": "schemas/decision-registry.schema.json",
    "dogfooding/dogfooding-registry.v1.json": "schemas/dogfooding-registry.schema.json",
}

REQUIRED_FILES = [
    "README.md", "PROJECT_CHARTER.md", "SYSTEM_MAP.md", "AGENTS.md",
    "CONTRIBUTING.md", "planning/NEXT_WORK.md", "scripts/render_views.py",
    "scripts/render_workflow.py", "scripts/validate_repository.py",
    ".github/workflows/foundation-validation.yml",
    *CANONICAL_DOCUMENTS.keys(), *CANONICAL_DOCUMENTS.values(),
]

RENDER_DIAGNOSTICS = {
    "PROJECT_CHARTER.md": "PFV-120",
    "SYSTEM_MAP.md": "PFV-121",
    "planning/NEXT_WORK.md": "PFV-122",
}

CHECKOUT_PIN = "df4cb1c069e1874edd31b4311f1884172cec0e10"
SETUP_PYTHON_PIN = "ece7cb06caefa5fff74198d8649806c4678c61a1"
EXPECTED_SHA_EXPRESSION = "${{ github.event.pull_request.head.sha || github.sha }}"


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


def _reject_non_finite(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def load_json_strict(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_non_finite)


def duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    found: set[str] = set()
    for value in values:
        if value in seen:
            found.add(value)
        seen.add(value)
    return found


def _json_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__


def _stable_item_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def validate_schema_instance(value: Any, schema: dict[str, Any], *, document: str, path: str = "$") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    expected_type = schema.get("type")
    if expected_type is not None:
        allowed = expected_type if isinstance(expected_type, list) else [expected_type]
        if not all(isinstance(item, str) for item in allowed):
            return [ValidationIssue("PFV-103", f"{document}: invalid schema type declaration at {path}")]
        if not any(_json_type_matches(value, item) for item in allowed):
            return [ValidationIssue("PFV-110", f"{document}{path}: expected {' or '.join(allowed)}, got {_type_name(value)}")]
    if "const" in schema and value != schema["const"]:
        issues.append(ValidationIssue("PFV-112", f"{document}{path}: value must equal {schema['const']!r}"))
    if "enum" in schema and value not in schema["enum"]:
        issues.append(ValidationIssue("PFV-112", f"{document}{path}: value is outside the allowed enum"))
    if isinstance(value, dict):
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        if not isinstance(required, list) or not isinstance(properties, dict):
            return [ValidationIssue("PFV-103", f"{document}: invalid object schema at {path}")]
        for key in required:
            if key not in value:
                issues.append(ValidationIssue("PFV-111", f"{document}{path}: missing required property {key!r}"))
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key in properties and isinstance(properties[key], dict):
                issues.extend(validate_schema_instance(item, properties[key], document=document, path=child_path))
            elif key in properties:
                issues.append(ValidationIssue("PFV-103", f"{document}: invalid child schema at {child_path}"))
            elif additional is False:
                issues.append(ValidationIssue("PFV-115", f"{document}{path}: unexpected property {key!r}"))
            elif isinstance(additional, dict):
                issues.extend(validate_schema_instance(item, additional, document=document, path=child_path))
        min_properties = schema.get("minProperties")
        if isinstance(min_properties, int) and len(value) < min_properties:
            issues.append(ValidationIssue("PFV-113", f"{document}{path}: expected at least {min_properties} properties"))
    if isinstance(value, list):
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if isinstance(min_items, int) and len(value) < min_items:
            issues.append(ValidationIssue("PFV-113", f"{document}{path}: expected at least {min_items} items"))
        if isinstance(max_items, int) and len(value) > max_items:
            issues.append(ValidationIssue("PFV-113", f"{document}{path}: expected at most {max_items} items"))
        if schema.get("uniqueItems") is True:
            keys = [_stable_item_key(item) for item in value]
            if len(keys) != len(set(keys)):
                issues.append(ValidationIssue("PFV-113", f"{document}{path}: items must be unique"))
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                issues.extend(validate_schema_instance(item, item_schema, document=document, path=f"{path}[{index}]"))
        elif item_schema is not None:
            issues.append(ValidationIssue("PFV-103", f"{document}: invalid items schema at {path}"))
    if isinstance(value, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            issues.append(ValidationIssue("PFV-114", f"{document}{path}: string is shorter than {min_length}"))
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            issues.append(ValidationIssue("PFV-116", f"{document}{path}: string does not match required pattern"))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if not math.isfinite(value):
            issues.append(ValidationIssue("PFV-114", f"{document}{path}: number must be finite"))
        if isinstance(minimum, (int, float)) and value < minimum:
            issues.append(ValidationIssue("PFV-114", f"{document}{path}: number is below minimum {minimum}"))
        if isinstance(maximum, (int, float)) and value > maximum:
            issues.append(ValidationIssue("PFV-114", f"{document}{path}: number exceeds maximum {maximum}"))
    return issues
