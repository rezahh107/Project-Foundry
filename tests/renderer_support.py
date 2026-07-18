from __future__ import annotations

from pathlib import Path
from typing import Callable

from tests.support import CRITICAL_VIEWS, copy_repo, run_cli


def assert_renderer_rejects(test_case, mutation: Callable[[Path], None], expected: str) -> None:
    temporary, target = copy_repo()
    try:
        before = {path: (target / path).read_bytes() for path in CRITICAL_VIEWS}
        mutation(target)
        for mode in ["--check", "--write"]:
            result = run_cli(target, "scripts/render_views.py", mode)
            test_case.assertNotEqual(0, result.returncode)
            test_case.assertIn(expected, result.stderr)
            test_case.assertNotIn("Traceback", result.stderr)
            after = {path: (target / path).read_bytes() for path in CRITICAL_VIEWS}
            test_case.assertEqual(before, after)
    finally:
        temporary.cleanup()
