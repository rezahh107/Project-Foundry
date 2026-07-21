#!/usr/bin/env python3
"""Render the external trusted-provenance workflow deterministically."""
from __future__ import annotations

import argparse
from pathlib import Path

TRUSTED_WORKFLOW_PATH = ".github/workflows/trusted-provenance.yml"
TRUSTED_ATTESTOR_PIN = "662fd78c4ee08bd5aeb3e68aee84f5d970a85ef4"


def render_trusted_provenance_workflow() -> str:
    rendered = """name: Trusted provenance

on:
  workflow_run:
    workflows:
      - Foundation validation
    types:
      - completed

permissions:
  actions: read
  contents: read
  pull-requests: read

jobs:
  attest-canonical-run:
    name: Verify immutable hosted provenance
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-latest
    steps:
      - name: Verify external attestation
        uses: rezahh107/Post-Merge-Auditor/attestors/project_foundry_v1@__PIN__
        with:
          token: ${{ github.token }}
          repository: ${{ github.repository }}
          workflow-run-id: ${{ github.event.workflow_run.id }}
          run-attempt: ${{ github.event.workflow_run.run_attempt }}
          expected-workflow-id: "315675709"
          expected-workflow-path: .github/workflows/foundation-validation.yml
          expected-head-sha: ${{ github.event.workflow_run.head_sha }}
          expected-event: ${{ github.event.workflow_run.event }}
          expected-pr-number: ${{ github.event.workflow_run.pull_requests[0].number || '' }}
          expected-head-ref: ${{ github.event.workflow_run.head_branch }}
          expected-base-ref: main
  """
    return rendered.replace("__PIN__", TRUSTED_ATTESTOR_PIN).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    path = root / TRUSTED_WORKFLOW_PATH
    expected = render_trusted_provenance_workflow()
    if args.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(expected, encoding="utf-8", newline="\n")
        temporary.replace(path)
        print("Trusted provenance workflow: UPDATED")
        return 0
    try:
        actual = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"PFV-137: trusted provenance workflow cannot be read: {exc}")
        return 1
    if actual != expected:
        print("PFV-137: trusted provenance workflow drifted from deterministic projection")
        return 1
    print("Trusted provenance workflow: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
