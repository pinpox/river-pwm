"""
Centered Master Layout

Master window(s) centered with stack windows on both sides.
"""

from __future__ import annotations
from typing import List, Dict, Optional, TYPE_CHECKING

from .layout_base import Layout, LayoutGeometry
from ..protocol import Area, WindowEdges

if TYPE_CHECKING:
    from ..objects import Window


class CenteredMasterLayout(Layout):
    """
    Centered master layout.

    Master window(s) centered, stack windows on both sides.
    """

    def __init__(self, master_count: int = 1, master_ratio: float = 0.5, gap: int = 4):
        self.master_count = master_count
        self.master_ratio = master_ratio
        self.gap = gap

    @property
    def name(self) -> str:
        return "centered-master"

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

        # Apply gap
        usable = Area(
            area.x + self.gap,
            area.y + self.gap,
            area.width - 2 * self.gap,
            area.height - 2 * self.gap,
        )

        if stack_n == 0:
            # Only master windows - center them
            master_width = int(usable.width * self.master_ratio)
            master_x = usable.x + (usable.width - master_width) // 2
            master_height = (usable.height - (master_n - 1) * self.gap) // master_n

            for i, win in enumerate(windows):
                y = usable.y + i * (master_height + self.gap)
                result[win] = LayoutGeometry(
                    master_x,
                    y,
                    master_width,
                    master_height,
                    WindowEdges.TOP
                    | WindowEdges.BOTTOM
                    | WindowEdges.LEFT
                    | WindowEdges.RIGHT,
                )
        else:
            # Master in center, stack split on sides
            master_width = int(usable.width * self.master_ratio)
            side_width = (usable.width - master_width - 2 * self.gap) // 2
            master_x = usable.x + side_width + self.gap

            # Master windows
            master_height = (usable.height - (master_n - 1) * self.gap) // master_n
            for i, win in enumerate(windows[:master_n]):
                y = usable.y + i * (master_height + self.gap)
                result[win] = LayoutGeometry(
                    master_x,
                    y,
                    master_width,
                    master_height,
                    WindowEdges.TOP | WindowEdges.BOTTOM,
                )

            # Split stack between left and right
            left_n = stack_n // 2
            right_n = stack_n - left_n

            # Left stack
            if left_n > 0:
                left_height = (usable.height - (left_n - 1) * self.gap) // left_n
                for i, win in enumerate(windows[master_n : master_n + left_n]):
                    y = usable.y + i * (left_height + self.gap)
                    edges = WindowEdges.LEFT
                    if i == 0:
                        edges |= WindowEdges.TOP
                    if i == left_n - 1:
                        edges |= WindowEdges.BOTTOM
                    result[win] = LayoutGeometry(
                        usable.x, y, side_width, left_height, edges
                    )

            # Right stack
            if right_n > 0:
                right_x = master_x + master_width + self.gap
                right_height = (usable.height - (right_n - 1) * self.gap) // right_n
                for i, win in enumerate(windows[master_n + left_n :]):
                    y = usable.y + i * (right_height + self.gap)
                    edges = WindowEdges.RIGHT
                    if i == 0:
                        edges |= WindowEdges.TOP
                    if i == right_n - 1:
                        edges |= WindowEdges.BOTTOM
                    result[win] = LayoutGeometry(
                        right_x, y, side_width, right_height, edges
                    )

        return result
