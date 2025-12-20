"""
Tiling Layout

Master-stack tiling layout with horizontal or vertical splits.
"""

from __future__ import annotations
from typing import List, Dict, Optional, TYPE_CHECKING

from .layout_base import Layout, LayoutGeometry, LayoutDirection
from ..protocol import Area, WindowEdges

if TYPE_CHECKING:
    from ..objects import Window


class TilingLayout(Layout):
    """
    Master-stack tiling layout.

    One or more master windows on one side, remaining windows stacked on the other.
    """

    def __init__(
        self,
        direction: LayoutDirection = LayoutDirection.HORIZONTAL,
        master_count: int = 1,
        master_ratio: float = 0.55,
        gap: int = 4,
    ):
        self.direction = direction
        self.master_count = master_count
        self.master_ratio = master_ratio
        self.gap = gap

    @property
    def name(self) -> str:
        if self.direction == LayoutDirection.HORIZONTAL:
            return "tile-right"
        return "tile-bottom"

    def calculate(
        self,
        windows: List["Window"],
        area: Area,
        focused_window: Optional["Window"] = None,
    ) -> Dict["Window", LayoutGeometry]:
        if not windows:
            return {}

        result = {}
        n = len(windows)
        master_n = min(self.master_count, n)
        stack_n = n - master_n

        # Apply gap to area
        usable = Area(
            area.x + self.gap,
            area.y + self.gap,
            area.width - 2 * self.gap,
            area.height - 2 * self.gap,
        )

        if n == 1:
            # Single window takes all space
            result[windows[0]] = LayoutGeometry(
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

        # Calculate master and stack areas
        if self.direction == LayoutDirection.HORIZONTAL:
            master_width = (
                int(usable.width * self.master_ratio) if stack_n > 0 else usable.width
            )
            stack_width = usable.width - master_width - self.gap if stack_n > 0 else 0

            # Layout master windows
            master_height = (usable.height - (master_n - 1) * self.gap) // master_n
            for i, win in enumerate(windows[:master_n]):
                y = usable.y + i * (master_height + self.gap)
                edges = WindowEdges.LEFT
                if i == 0:
                    edges |= WindowEdges.TOP
                if i == master_n - 1:
                    edges |= WindowEdges.BOTTOM
                if stack_n == 0:
                    edges |= WindowEdges.RIGHT

                result[win] = LayoutGeometry(
                    usable.x, y, master_width, master_height, edges
                )

            # Layout stack windows
            if stack_n > 0:
                stack_x = usable.x + master_width + self.gap
                stack_height = (usable.height - (stack_n - 1) * self.gap) // stack_n
                for i, win in enumerate(windows[master_n:]):
                    y = usable.y + i * (stack_height + self.gap)
                    edges = WindowEdges.RIGHT
                    if i == 0:
                        edges |= WindowEdges.TOP
                    if i == stack_n - 1:
                        edges |= WindowEdges.BOTTOM

                    result[win] = LayoutGeometry(
                        stack_x, y, stack_width, stack_height, edges
                    )

        else:  # VERTICAL
            master_height = (
                int(usable.height * self.master_ratio) if stack_n > 0 else usable.height
            )
            stack_height = (
                usable.height - master_height - self.gap if stack_n > 0 else 0
            )

            # Layout master windows
            master_width = (usable.width - (master_n - 1) * self.gap) // master_n
            for i, win in enumerate(windows[:master_n]):
                x = usable.x + i * (master_width + self.gap)
                edges = WindowEdges.TOP
                if i == 0:
                    edges |= WindowEdges.LEFT
                if i == master_n - 1:
                    edges |= WindowEdges.RIGHT
                if stack_n == 0:
                    edges |= WindowEdges.BOTTOM

                result[win] = LayoutGeometry(
                    x, usable.y, master_width, master_height, edges
                )

            # Layout stack windows
            if stack_n > 0:
                stack_y = usable.y + master_height + self.gap
                stack_width = (usable.width - (stack_n - 1) * self.gap) // stack_n
                for i, win in enumerate(windows[master_n:]):
                    x = usable.x + i * (stack_width + self.gap)
                    edges = WindowEdges.BOTTOM
                    if i == 0:
                        edges |= WindowEdges.LEFT
                    if i == stack_n - 1:
                        edges |= WindowEdges.RIGHT

                    result[win] = LayoutGeometry(
                        x, stack_y, stack_width, stack_height, edges
                    )

        return result
