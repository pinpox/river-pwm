"""
Monocle Layout

All windows fullscreen and stacked - only focused window visible.
"""

from __future__ import annotations
from typing import List, Dict, TYPE_CHECKING

from .layout_base import Layout, LayoutGeometry
from ..protocol import Area, WindowEdges

if TYPE_CHECKING:
    from ..objects import Window


class MonocleLayout(Layout):
    """
    Monocle layout - all windows full size, stacked.

    Only the focused window is shown.
    """

    def __init__(self, gap: int = 0):
        self.gap = gap

    @property
    def name(self) -> str:
        return "monocle"

    def calculate(
        self, windows: List["Window"], area: Area
    ) -> Dict["Window", LayoutGeometry]:
        if not windows:
            return {}

        result = {}

        # Apply gap to area
        usable = Area(
            area.x + self.gap,
            area.y + self.gap,
            area.width - 2 * self.gap,
            area.height - 2 * self.gap,
        )

        # All windows get full size
        for win in windows:
            result[win] = LayoutGeometry(
                usable.x,
                usable.y,
                usable.width,
                usable.height,
                WindowEdges.TOP
                | WindowEdges.BOTTOM
                | WindowEdges.LEFT
                | WindowEdges.RIGHT,
            )

        return result
