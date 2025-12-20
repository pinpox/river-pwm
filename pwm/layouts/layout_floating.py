"""
Floating Layout

Traditional floating windows with manual positioning.
"""

from __future__ import annotations
from typing import List, Dict, Tuple, TYPE_CHECKING

from .layout_base import Layout, LayoutGeometry
from ..protocol import Area

if TYPE_CHECKING:
    from ..objects import Window


class FloatingLayout(Layout):
    """
    Floating layout - windows keep their current positions.
    """

    def __init__(self, default_width: int = 800, default_height: int = 600):
        self.default_width = default_width
        self.default_height = default_height
        self._positions: Dict[int, Tuple[int, int]] = {}
        self._sizes: Dict[int, Tuple[int, int]] = {}

    @property
    def name(self) -> str:
        return "floating"

    def set_position(self, window: "Window", x: int, y: int):
        """Set window position."""
        self._positions[window.object_id] = (x, y)

    def set_size(self, window: "Window", width: int, height: int):
        """Set window size."""
        self._sizes[window.object_id] = (width, height)

    def calculate(
        self, windows: List["Window"], area: Area
    ) -> Dict["Window", LayoutGeometry]:
        if not windows:
            return {}

        result = {}

        for i, win in enumerate(windows):
            # Get stored or calculate default position
            if win.object_id in self._positions:
                x, y = self._positions[win.object_id]
            else:
                # Cascade new windows
                offset = (i % 10) * 30
                x = area.x + 50 + offset
                y = area.y + 50 + offset
                self._positions[win.object_id] = (x, y)

            # Get stored or calculate default size
            if win.object_id in self._sizes:
                width, height = self._sizes[win.object_id]
            else:
                width = self.default_width
                height = self.default_height
                if win.width > 0 and win.height > 0:
                    width = win.width
                    height = win.height
                self._sizes[win.object_id] = (width, height)

            result[win] = LayoutGeometry(x, y, width, height)

        return result

    def remove_window(self, window: "Window"):
        """Remove window from tracking."""
        self._positions.pop(window.object_id, None)
        self._sizes.pop(window.object_id, None)

    # Decoration interface implementation
    def should_render_decorations(self) -> bool:
        return True

    def create_decorations(self, connection, style):
        """Create titlebar decorations for floating windows."""
        from .default_window_decoration import DefaultWindowDecoration

        self.window_decoration = DefaultWindowDecoration(connection, style)

    def render_decorations(self, windows, focused_window, area):
        """Render titlebar for each floating window."""
        if hasattr(self, 'window_decoration') and self.window_decoration and windows:
            self.window_decoration.render(windows, focused_window, area)

    def cleanup_decorations(self):
        """Clean up titlebar decorations."""
        if hasattr(self, 'window_decoration') and self.window_decoration:
            self.window_decoration.cleanup()
            self.window_decoration = None
