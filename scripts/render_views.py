#!/usr/bin/env python3
"""Render critical Markdown views deterministically from canonical JSON state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

CANONICAL_PATHS = {
    "constitution": "governance/project-constitution.v1.json",
    "program": "planning/execution-program.v1.json",
    "scope": "planning/scope-baseline.v1.json",
    "state": "planning/current-state.v1.json",
}


def _load_json(root: Path, relative: str) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{relative} must contain a JSON object")
    return value


def load_render_state(root: Path) -> dict[str, dict[str, Any]]:
    return {name: _load_json(root, path) for name, path in CANONICAL_PATHS.items()}


def _bullets(values: list[str]) -> str:
    return "\n".join(f"- `{value}`" for value in values)


def render_project_charter(data: dict[str, dict[str, Any]]) -> str:
    constitution = data["constitution"]
    scope = data["scope"]
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


def render_system_map(data: dict[str, dict[str, Any]]) -> str:
    constitution = data["constitution"]
    program = data["program"]
    state = data["state"]
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
    controls = "\n".join(
        f"- `{control}`" for control in constitution["constitutional_controls"]
    )
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


def render_next_work(data: dict[str, dict[str, Any]]) -> str:
    constitution = data["constitution"]
    program = data["program"]
    scope = data["scope"]
    state = data["state"]
    north_star = constitution["north_star"]
    task_map = {task["id"]: task for task in program["tasks"]}
    current = task_map[state["current_task_id"]]
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

## تنها قدم بعدی

{state['next_action']}
"""


RENDERERS: dict[str, Callable[[dict[str, dict[str, Any]]], str]] = {
    "PROJECT_CHARTER.md": render_project_charter,
    "SYSTEM_MAP.md": render_system_map,
    "planning/NEXT_WORK.md": render_next_work,
}


def render_all(root: Path) -> dict[str, str]:
    data = load_render_state(root)
    return {path: renderer(data) for path, renderer in RENDERERS.items()}


def write_views(root: Path) -> None:
    for relative, content in render_all(root).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def check_views(root: Path) -> list[str]:
    drifted: list[str] = []
    for relative, expected in render_all(root).items():
        path = root / relative
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            drifted.append(relative)
    return drifted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.write:
        write_views(root)
        print("Rendered critical views: UPDATED")
        return 0
    drifted = check_views(root)
    if drifted:
        for relative in drifted:
            print(f"PFR-001: rendered view drift: {relative}")
        return 1
    print("Rendered critical views: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
