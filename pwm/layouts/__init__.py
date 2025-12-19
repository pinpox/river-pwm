"""
Layout System

Provides window layout algorithms and management.
"""

from .layout_base import (
    Layout,
    LayoutGeometry,
    LayoutDirection,
    Workspace,
    LayoutManager,
)
from .layout_tiling import TilingLayout
from .layout_monocle import MonocleLayout
from .layout_grid import GridLayout
from .layout_floating import FloatingLayout
from .layout_centered_master import CenteredMasterLayout
from .layout_tabbed import TabbedLayout

__all__ = [
    # Base classes
    "Layout",
    "LayoutGeometry",
    "LayoutDirection",
    "Workspace",
    "LayoutManager",
    # Layout implementations
    "TilingLayout",
    "MonocleLayout",
    "GridLayout",
    "FloatingLayout",
    "CenteredMasterLayout",
    "TabbedLayout",
]
