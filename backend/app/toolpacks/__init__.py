"""Modular toolpack declarations (forge.toolpack/v1).

BETA declares; the lead wires REGISTRY. This package contains only
declarations and family metadata — no registry edits, no wiring.
"""

from .declaration import ToolDecl, ToolPackSpec
from .families import (
    ALL_VERIFIED_TOOLS,
    DEMO_TOOLS,
    FAMILY_METADATA,
    FAMILY_TOOL_MAP,
    PROPOSED_TOOLPACKS,
    all_mapped_tools,
    family_for_tool,
)

__all__ = [
    "ALL_VERIFIED_TOOLS",
    "DEMO_TOOLS",
    "FAMILY_METADATA",
    "FAMILY_TOOL_MAP",
    "PROPOSED_TOOLPACKS",
    "ToolDecl",
    "ToolPackSpec",
    "all_mapped_tools",
    "family_for_tool",
]
