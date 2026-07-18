from __future__ import annotations

import unittest

from tests.renderer_support import assert_renderer_rejects
from tests.support import mutate_json


class RendererReferenceTests(unittest.TestCase):
    def test_unresolved_references_fail_before_rendering(self) -> None:
        cases = [
            (
                lambda root: mutate_json(
                    root,
                    "planning/execution-program.v1.json",
                    lambda doc: doc["work_packages"][0]["task_ids"].append("PF-404"),
                ),
                "PFV-029",
            ),
            (
                lambda root: mutate_json(
                    root,
                    "planning/current-state.v1.json",
                    lambda doc: doc.__setitem__("current_task_id", "PF-404"),
                ),
                "PFV-059",
            ),
        ]
        for mutation, expected in cases:
            with self.subTest(expected=expected):
                assert_renderer_rejects(self, mutation, expected)
