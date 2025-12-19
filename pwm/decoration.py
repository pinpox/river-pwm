"""
Server-Side Decoration Rendering with Cairo

Provides DecorationStyle and DecorationRenderer classes for rendering window
titlebars with title text and control buttons (close, minimize, maximize).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Optional
import cairo


@dataclass
class DecorationStyle:
    """Styling configuration for window decorations."""

    height: int = 24
    position: str = "top"  # "top" or "bottom"
    bg_color: Tuple[int, int, int, int] = (46, 52, 64, 255)
    focused_bg_color: Tuple[int, int, int, int] = (59, 66, 82, 255)
    text_color: Tuple[int, int, int, int] = (216, 222, 233, 255)
    button_color: Tuple[int, int, int, int] = (94, 129, 172, 255)
    font_family: str = "sans-serif"
    font_size: int = 11
    border_width: int = 2  # Window border width (decoration should extend over borders)


class DecorationRenderer:
    """Renders window decorations with a fixed layout.

    Layout: title on left, buttons (minimize, maximize, close) on right.
    """

    def __init__(self, style: DecorationStyle):
        """Initialize the renderer.

        Args:
            style: Decoration styling configuration
        """
        self.style = style
        self.button_width = 24
        self.button_padding = 4
        self.title_padding = 8
        self.hover_button: Optional[str] = None  # "close", "minimize", "maximize"

    def render(
        self, width: int, title: str, focused: bool, maximized: bool, shm_data: memoryview
    ):
        """Render the titlebar to the shared memory buffer.

        Args:
            width: Titlebar width in pixels
            title: Window title text
            focused: Whether window is focused
            maximized: Whether window is maximized
            shm_data: Shared memory buffer to render into
        """
        height = self.style.height

        # Create Cairo surface from shared memory buffer
        # Format: ARGB32 (4 bytes per pixel)
        stride = width * 4
        surface = cairo.ImageSurface.create_for_data(
            shm_data, cairo.FORMAT_ARGB32, width, height, stride
        )
        ctx = cairo.Context(surface)

        # Clear background
        bg = (
            self.style.focused_bg_color if focused else self.style.bg_color
        )
        self._set_color(ctx, bg)
        ctx.rectangle(0, 0, width, height)
        ctx.fill()

        # Calculate button area width (3 buttons)
        buttons_width = 3 * self.button_width

        # Render title on left
        title_max_width = width - buttons_width - self.title_padding * 2
        if title_max_width > 0:
            self._render_title(ctx, title, focused, title_max_width)

        # Render buttons on right
        self._render_buttons(ctx, focused, maximized, width, height)

        # Ensure drawing is complete
        surface.flush()

    def _render_title(self, ctx: cairo.Context, title: str, focused: bool, max_width: int):
        """Render the window title text.

        Args:
            ctx: Cairo context
            title: Window title
            focused: Whether window is focused
            max_width: Maximum width for title text
        """
        # Set font
        ctx.select_font_face(
            self.style.font_family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
        )
        ctx.set_font_size(self.style.font_size)

        # Set text color
        self._set_color(ctx, self.style.text_color)

        # Measure text
        extents = ctx.text_extents(title)

        # Truncate with ellipsis if too long
        display_title = title
        if extents.width > max_width:
            # Binary search for the right length
            ellipsis = "..."
            ellipsis_width = ctx.text_extents(ellipsis).width
            available = max_width - ellipsis_width

            left = 0
            right = len(title)
            while left < right:
                mid = (left + right + 1) // 2
                test_width = ctx.text_extents(title[:mid]).width
                if test_width <= available:
                    left = mid
                else:
                    right = mid - 1

            display_title = title[:left] + ellipsis

        # Draw text
        y_offset = (self.style.height + self.style.font_size) // 2 - 2
        ctx.move_to(self.title_padding, y_offset)
        ctx.show_text(display_title)

    def _render_buttons(
        self, ctx: cairo.Context, focused: bool, maximized: bool, width: int, height: int
    ):
        """Render control buttons.

        Args:
            ctx: Cairo context
            focused: Whether window is focused
            maximized: Whether window is maximized
            width: Titlebar width
            height: Titlebar height
        """
        # Buttons from right to left: close, maximize, minimize
        buttons = ["close", "maximize", "minimize"]

        for i, button in enumerate(buttons):
            # Calculate button position (right-aligned)
            x = width - (i + 1) * self.button_width
            y = 0
            w = self.button_width
            h = height

            # Draw button background if hovered
            if self.hover_button == button:
                if button == "close":
                    # Red hover for close button
                    ctx.set_source_rgba(0.8, 0.2, 0.2, 1.0)
                else:
                    # Lighter background for other buttons
                    ctx.set_source_rgba(0.3, 0.3, 0.3, 1.0)
                ctx.rectangle(x, y, w, h)
                ctx.fill()

            # Draw button icon
            icon_size = 10
            icon_x = x + (w - icon_size) // 2
            icon_y = y + (h - icon_size) // 2

            self._set_color(ctx, self.style.button_color)
            ctx.set_line_width(1.5)

            if button == "close":
                self._draw_close_icon(ctx, icon_x, icon_y, icon_size)
            elif button == "maximize":
                self._draw_maximize_icon(ctx, icon_x, icon_y, icon_size, maximized)
            elif button == "minimize":
                self._draw_minimize_icon(ctx, icon_x, icon_y, icon_size)

    def _draw_close_icon(self, ctx: cairo.Context, x: int, y: int, size: int):
        """Draw an X for the close button.

        Args:
            ctx: Cairo context
            x, y: Icon position
            size: Icon size
        """
        ctx.move_to(x, y)
        ctx.line_to(x + size, y + size)
        ctx.stroke()

        ctx.move_to(x + size, y)
        ctx.line_to(x, y + size)
        ctx.stroke()

    def _draw_maximize_icon(
        self, ctx: cairo.Context, x: int, y: int, size: int, maximized: bool
    ):
        """Draw a rectangle for the maximize button.

        Args:
            ctx: Cairo context
            x, y: Icon position
            size: Icon size
            maximized: Whether window is currently maximized
        """
        if maximized:
            # Draw two overlapping rectangles to indicate "restore"
            offset = 2
            small_size = size - offset

            # Back rectangle
            ctx.rectangle(x + offset, y, small_size, small_size)
            ctx.stroke()

            # Front rectangle
            ctx.rectangle(x, y + offset, small_size, small_size)
            ctx.stroke()
        else:
            # Single rectangle for maximize
            ctx.rectangle(x, y, size, size)
            ctx.stroke()

    def _draw_minimize_icon(self, ctx: cairo.Context, x: int, y: int, size: int):
        """Draw a horizontal line for the minimize button.

        Args:
            ctx: Cairo context
            x, y: Icon position
            size: Icon size
        """
        y_center = y + size // 2
        ctx.move_to(x, y_center)
        ctx.line_to(x + size, y_center)
        ctx.stroke()

    def hit_test_button(self, x: int, y: int, width: int) -> Optional[str]:
        """Test if a point is over a button.

        Args:
            x, y: Point coordinates
            width: Titlebar width

        Returns:
            Button name ("close", "minimize", "maximize") or None
        """
        # Check if in button area (rightmost 3 * button_width pixels)
        buttons_start = width - 3 * self.button_width
        if x < buttons_start or y < 0 or y >= self.style.height:
            return None

        # Determine which button
        offset = x - buttons_start
        button_index = offset // self.button_width

        buttons = ["minimize", "maximize", "close"]
        if 0 <= button_index < len(buttons):
            return buttons[button_index]

        return None

    def update_hover(self, x: int, y: int, width: int) -> bool:
        """Update hover state based on pointer position.

        Args:
            x, y: Pointer coordinates
            width: Titlebar width

        Returns:
            True if hover state changed (needs re-render)
        """
        button = self.hit_test_button(x, y, width)
        if button != self.hover_button:
            self.hover_button = button
            return True
        return False

    def _set_color(self, ctx: cairo.Context, color: Tuple[int, int, int, int]):
        """Set Cairo color from RGBA tuple.

        Args:
            ctx: Cairo context
            color: (R, G, B, A) tuple with values 0-255
        """
        r, g, b, a = color
        ctx.set_source_rgba(r / 255.0, g / 255.0, b / 255.0, a / 255.0)
