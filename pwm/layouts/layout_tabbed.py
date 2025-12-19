"""
Tabbed Layout

All windows become tabs with a tab bar showing window titles.
Only the focused window is visible.
"""

from __future__ import annotations
from typing import List, Dict, TYPE_CHECKING

from .layout_base import Layout, LayoutGeometry
from ..protocol import Area, WindowEdges

if TYPE_CHECKING:
    from ..objects import Window


class TabbedLayout(Layout):
    """
    Tabbed layout - all windows become tabs with tab bar.

    Only the focused window is visible, with a tab bar showing all windows.
    """

    def __init__(self, gap: int = 0, tab_width: int = None, border_width: int = 0):
        self.gap = gap
        self.border_width = border_width
        # Auto-calculate tab width if not specified
        if tab_width is None:
            self.tab_width = self._calculate_auto_width()
            print(f"TabbedLayout: Auto-calculated tab width: {self.tab_width}px")
        else:
            self.tab_width = tab_width
            print(f"TabbedLayout: Using fixed tab width: {self.tab_width}px")
        self.tab_decoration = None

    def _calculate_auto_width(self) -> int:
        """Calculate width based on font height plus padding."""
        import cairo

        # Create temporary surface to measure font
        temp_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
        ctx = cairo.Context(temp_surface)

        # Set font to match rendering settings
        ctx.select_font_face(
            "sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
        )
        ctx.set_font_size(12)

        # Measure font metrics - font_extents returns (ascent, descent, height, max_x_advance, max_y_advance)
        font_extents = ctx.font_extents()
        font_height = font_extents[2]  # height is the 3rd element

        # Add minimal padding (5px on each side = 10px total)
        padding = 10

        return int(font_height + padding)

    @property
    def name(self) -> str:
        return "tabbed"

    def calculate(
        self, windows: List["Window"], area: Area
    ) -> Dict["Window", LayoutGeometry]:
        if not windows:
            return {}

        result = {}

        # Reserve space for vertical tab bar on left
        usable = Area(
            area.x + self.gap + self.tab_width,  # Tab bar on left
            area.y + self.gap,
            area.width - 2 * self.gap - self.tab_width,
            area.height - 2 * self.gap,
        )

        # All windows get same geometry (fullscreen minus tab bar)
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

    # Decoration interface implementation
    def should_render_decorations(self) -> bool:
        return True

    def create_decorations(self, connection, style):
        """Create tab bar decoration."""
        from .tab_decoration import TabDecoration

        self.tab_decoration = TabDecoration(
            connection,
            style,
            self.tab_width,
            orientation="vertical",
            gap=self.gap,
            border_width=self.border_width,
        )

    def render_decorations(self, windows, focused_window, area):
        """Render tab bar."""
        if self.tab_decoration and windows:
            self.tab_decoration.render(windows, focused_window, area)

    def cleanup_decorations(self):
        """Clean up tab bar."""
        if self.tab_decoration:
            self.tab_decoration.cleanup()
            self.tab_decoration = None
