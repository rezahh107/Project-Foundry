"""Compatibility entry points for the hardened split mutation corpus."""
from tests.test_structural_mutations import StructuralMutationTests
from tests.test_renderer_structure import RendererStructureTests
from tests.test_renderer_references import RendererReferenceTests
from tests.test_renderer_json_failures import RendererJsonFailureTests


class RendererStructuralGateTests(
    RendererStructureTests,
    RendererReferenceTests,
    RendererJsonFailureTests,
):
    """Run every renderer structural/reference/JSON gate through the legacy CI entry point."""
