from __future__ import annotations

import unittest

from tests.renderer_support import assert_renderer_rejects
from tests.support import mutate_json, write_json


class RendererStructureTests(unittest.TestCase):
    def test_null_and_top_level_structure_failures(self) -> None:
        cases = [
            (
                lambda root: mutate_json(
                    root,
                    "governance/project-constitution.v1.json",
                    lambda doc: doc.__setitem__("north_star", None),
                ),
                "PFV-110",
            ),
            (
                lambda root: mutate_json(
                    root,
                    "governance/project-constitution.v1.json",
                    lambda doc: doc.__setitem__("operating_profile", None),
                ),
                "PFV-110",
            ),
            (
                lambda root: write_json(root, "planning/current-state.v1.json", []),
                "PFV-110",
            ),
        ]
        for mutation, expected in cases:
            with self.subTest(expected=expected):
                assert_renderer_rejects(self, mutation, expected)
