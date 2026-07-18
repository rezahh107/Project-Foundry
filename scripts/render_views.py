#!/usr/bin/env python3
"""Render critical Markdown views from structurally and semantically valid canonical state."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.validation_core import ValidationIssue
    from scripts.validation_execution import validate_execution_controls
    from scripts.validation_semantics import load_and_validate_structures, validate_semantics
except ModuleNotFoundError:
    from validation_core import ValidationIssue
    from validation_execution import validate_execution_controls
    from validation_semantics import load_and_validate_structures, validate_semantics


class RenderInputError(Exception):
    """Controlled failure carrying deterministic repository diagnostics."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        super().__init__("canonical state is not renderable")
        self.issues = issues


def _bullets(values: list[str]) -> str:
    return "\n".join(f"- `{value}`" for value in values)


def render_project_charter(documents: dict[str, dict[str, Any]]) -> str:
    constitution = documents["governance/project-constitution.v1.json"]
    scope = documents["planning/scope-baseline.v1.json"]
    north_star = constitution["north_star"]
    authority = constitution["authority_model"]
    completion = constitution["completion_rule"]
    exclusions = "\n".join(
        f"- **{item['item']}** — `{item['disposition']}`; authority: `{item['authority']}`"
        for item in scope["explicit_exclusions"]
    )
    return f"""<!-- GENERATED FILE. Run: python scripts/render_views.py --write --root . -->
# Project Foundry Charter

## The simple picture

```text
raw idea
→ clarified concept
→ reliable specifications
→ prepared repository
→ execution program and tasks
→ precise implementation prompts
→ evidence-backed completion
```

## North Star

**ID:** `{north_star['id']}`

{north_star['statement']}

**Change policy:** `{north_star['change_policy']}`

## Authority model

### Project owner

{_bullets(authority['project_owner'])}

### AI technical authority inside approved scope

{_bullets(authority['ai_technical_authority'])}

### Evidence authority

{_bullets(authority['evidence_authority'])}

## Active foundation scope

**Scope:** `{scope['scope_id']}@{scope['scope_version']}`

{scope['objective']}

### Explicit exclusions

{exclusions}

## Completion truth

A task may be treated as complete only after `{completion['required_lifecycle_state']}` with evidence. An agent claim alone is not sufficient: `{str(completion['agent_claim_alone_is_sufficient']).lower()}`.
"""


def render_system_map(documents: dict[str, dict[str, Any]]) -> str:
    constitution = documents["governance/project-constitution.v1.json"]
    program = documents["planning/execution-program.v1.json"]
    state = documents["planning/current-state.v1.json"]
    task_map = {task["id"]: task for task in program["tasks"]}
    sections: list[str] = []
    for work_package in program["work_packages"]:
        task_lines = "\n".join(
            f"  - `{task_id}` — {task_map[task_id]['title']} (`{task_map[task_id]['status']}`)"
            for task_id in work_package["task_ids"]
        )
        sections.append(
            f"- `{work_package['id']}` — **{work_package['title']}**\n"
            f"  - Objective: {work_package['objective']}\n"
            f"{task_lines}"
        )
    context = " → ".join(f"`{value}`" for value in state["active_context_path"])
    controls = "\n".join(f"- `{control}`" for control in constitution["constitutional_controls"])
    return f"""<!-- GENERATED FILE. Run: python scripts/render_views.py --write --root . -->
# Project Foundry System Map

## Full registered program

**Program:** `{program['program_id']}@{program['program_version']}`  
**Program status:** `{program['status']}`

{chr(10).join(sections)}

## Active context

{context}

The current operation is subordinate to the task, work package, program, and North Star. It cannot redefine them.

## Cross-cutting constitutional controls

{controls}

## Verification, authority, transition, and evidence

```text
Verifier → produces an assessment
Authority policy → permits or denies a transition
Transition logic → records the state change
Repository evidence → supports the factual claim
```

## Canonical and rendered information

```text
Canonical JSON state
├── generated owner-facing views
└── precise agent-facing contracts
```

Critical rendered views are generated from canonical state and exact-byte checked by the repository validator.
"""


def render_next_work(documents: dict[str, dict[str, Any]]) -> str:
    constitution = documents["governance/project-constitution.v1.json"]
    program = documents["planning/execution-program.v1.json"]
    scope = documents["planning/scope-baseline.v1.json"]
    state = documents["planning/current-state.v1.json"]
    north_star = constitution["north_star"]
    task_map = {task["id"]: task for task in program["tasks"]}
    current = task_map[state["current_task_id"]]
    next_task = task_map[state["next_task_id"]]
    scoped_tasks = "\n".join(
        f"- `{task_id}` — {task_map[task_id]['title']} — `{task_map[task_id]['status']}`"
        for task_id in scope["included_task_ids"]
    )
    exclusions = "\n".join(
        f"- {item['item']} — `{item['disposition']}`"
        for item in scope["explicit_exclusions"]
    )
    uncertainties = "\n".join(f"- {item}" for item in state["uncertainties"]) or "- مورد مهمی ثبت نشده است."
    context = " → ".join(f"`{item}`" for item in state["active_context_path"])
    return f"""<!-- GENERATED FILE. Run: python scripts/render_views.py --write --root . -->
# کار بعدی

## تصویر ساده

ما در حال ساخت فونداسیون حافظه و کنترل Project Foundry هستیم؛ کل کارخانه در برنامه ثبت شده و کار فعلی نمی‌تواند جای هدف اصلی را بگیرد.

## هدف اصلی

**{north_star['id']}** — {north_star['statement']}

## جای فعلی

{context}

## Scope فعال

**{scope['scope_id']}@{scope['scope_version']}** — {scope['objective']}

### Taskهای داخل Scope

{scoped_tasks}

### موارد خارج از Scope فعلی

{exclusions}

## وضعیت دقیق کار فعلی

- Task: `{current['id']}` — {current['title']}
- وضعیت canonical: `{state['current_task_status']}`
- وضعیت ثبت‌شده در برنامه: `{current['status']}`
- این Task هنوز کامل نیست مگر پس از `{constitution['completion_rule']['required_lifecycle_state']}` همراه با Evidence.

## ابهام‌های ثبت‌شده

{uncertainties}

## Task بعدی canonical

- شناسه: `{next_task['id']}`
- عنوان: {next_task['title']}

## دستور عملی بعدی

{state['next_action']}
"""


RENDERERS: dict[str, Callable[[dict[str, dict[str, Any]]], str]] = {
    "PROJECT_CHARTER.md": render_project_charter,
    "SYSTEM_MAP.md": render_system_map,
    "planning/NEXT_WORK.md": render_next_work,
}


def load_render_documents(root: Path) -> dict[str, dict[str, Any]]:
    documents, issues = load_and_validate_structures(root)
    if not issues:
        issues = validate_semantics(documents)
    if not issues:
        issues = validate_execution_controls(documents)
    if issues:
        raise RenderInputError(issues)
    return documents


def render_all_from_documents(documents: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {path: renderer(documents) for path, renderer in RENDERERS.items()}


def render_all(root: Path) -> dict[str, str]:
    return render_all_from_documents(load_render_documents(root.resolve()))


def write_views(root: Path) -> None:
    rendered = render_all(root)
    staged: list[tuple[Path, Path]] = []
    try:
        for relative, content in rendered.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(content, encoding="utf-8", newline="\n")
            staged.append((temporary, path))
        for temporary, path in staged:
            temporary.replace(path)
    finally:
        for temporary, _ in staged:
            if temporary.exists():
                temporary.unlink()


def check_views(root: Path) -> list[str]:
    drifted: list[str] = []
    for relative, expected in render_all(root).items():
        path = root / relative
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            drifted.append(relative)
    return drifted


def _print_issues(issues: list[ValidationIssue]) -> None:
    for issue in issues:
        print(f"{issue.code}: {issue.message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.write:
            write_views(root)
            print("Rendered critical views: UPDATED")
            return 0
        drifted = check_views(root)
    except RenderInputError as exc:
        _print_issues(exc.issues)
        return 1
    except OSError as exc:
        print(f"PFR-002: rendered view I/O failure: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"PFR-199: controlled renderer failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if drifted:
        for relative in drifted:
            print(f"PFR-001: rendered view drift: {relative}", file=sys.stderr)
        return 1
    print("Rendered critical views: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
