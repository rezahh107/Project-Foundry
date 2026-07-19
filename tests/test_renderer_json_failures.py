from __future__ import annotations

import re
import unittest

from tests.renderer_support import assert_renderer_rejects


class RendererJsonFailureTests(unittest.TestCase):
    def test_malformed_non_finite_and_missing_inputs_are_controlled(self) -> None:
        cases = [
            lambda root: (root / "planning/current-state.v1.json").write_text("{bad", encoding="utf-8"),
            lambda root: self._replace_weight(root, "NaN"),
            lambda root: self._replace_weight(root, "Infinity"),
            lambda root: (root / "planning/current-state.v1.json").unlink(),
        ]
        for mutation in cases:
            with self.subTest(mutation=mutation):
                assert_renderer_rejects(self, mutation, "PFV-101")

    @staticmethod
    def _replace_weight(root, replacement: str) -> None:
        path = root / "decisions/decision-registry.v1.json"
        text = re.sub(
            r'"ai_operability"\s*:\s*25',
            f'"ai_operability": {replacement}',
            path.read_text(encoding="utf-8"),
            count=1,
        )
        path.write_text(text, encoding="utf-8")
