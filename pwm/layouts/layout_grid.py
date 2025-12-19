"""
Grid Layout

Windows arranged in a grid pattern.
"""

from __future__ import annotations
from typing import List, Dict, TYPE_CHECKING

from .layout_base import Layout, LayoutGeometry
from ..protocol import Area, WindowEdges

if TYPE_CHECKING:
    from ..objects import Window


class GridLayout(Layout):
    """
    Grid layout - windows arranged in a grid pattern.
    """

    def __init__(self, gap: int = 4):
        self.gap = gap

    @property
    def name(self) -> str:
        return "grid"

    def calculate(
        self, windows: List["Window"], area: Area
    ) -> Dict["Window", LayoutGeometry]:
        if not windows:
            return {}

        result = {}
        n = len(windows)

        # Calculate grid dimensions
        cols = 1
        while cols * cols < n:
            cols += 1
        rows = (n + cols - 1) // cols

        # Apply gap to area
        usable = Area(
            area.x + self.gap,
            area.y + self.gap,
            area.width - 2 * self.gap,
            area.height - 2 * self.gap,
        )

        cell_width = (usable.width - (cols - 1) * self.gap) // cols
        cell_height = (usable.height - (rows - 1) * self.gap) // rows

        for i, win in enumerate(windows):
            row = i // cols
            col = i % cols
            x = usable.x + col * (cell_width + self.gap)
            y = usable.y + row * (cell_height + self.gap)

            # Calculate tiled edges
            edges = WindowEdges.NONE
            if col == 0:
                edges |= WindowEdges.LEFT
            if col == cols - 1:
                edges |= WindowEdges.RIGHT
            if row == 0:
                edges |= WindowEdges.TOP
            if row == rows - 1:
                edges |= WindowEdges.BOTTOM

            result[win] = LayoutGeometry(x, y, cell_width, cell_height, edges)

        return result
