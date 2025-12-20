"""
Tab Decoration Rendering

Renders a tab bar showing all windows as tabs with Cairo.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Tuple
import cairo

if TYPE_CHECKING:
    from ..objects import Window
    from ..connection import WaylandConnection
    from ..decoration import DecorationStyle
    from ..protocol import Area


class TabDecoration:
    """Renders a tab bar for tabbed layout."""

    def __init__(
        self,
        connection: "WaylandConnection",
        style: "DecorationStyle",
        size: int = 30,
        orientation: str = "horizontal",
        gap: int = 0,
        border_width: int = 0,
    ):
        self.connection = connection
        self.style = style
        self.orientation = orientation  # "horizontal" or "vertical"
        self.gap = gap  # Gap to subtract from area dimensions
        self.border_width = border_width  # Border width to add back to decoration size

        if orientation == "vertical":
            self.width = size  # Width for vertical tabs (already calculated)
            self.height = 0  # Will be set based on area height
        else:
            self.width = 0  # Will be set based on area width
            self.height = size  # Fixed height for horizontal tabs

        # Map of window_id -> (surface, decoration_obj, pool, buffer)
        self.window_decorations = {}

    def render(
        self,
        windows: List["Window"],
        focused_window: Optional["Window"],
        area: "Area",
    ):
        """Render tab bar showing all windows as tabs."""
        if not windows:
            return

        # Update dimensions based on orientation
        # Decoration should extend to outer border edges
        # Gap includes border_width*2, so window height is: area.height - 2*gap
        # Decoration should be window_height + 2*border_width to reach outer edges
        # = (area.height - 2*gap) + 2*border_width
        # = area.height - 2*gap + 2*border_width
        if self.orientation == "vertical":
            adjusted_height = area.height - 2 * self.gap + 2 * self.border_width
            if adjusted_height != self.height:
                self.height = adjusted_height
        else:
            adjusted_width = area.width - 2 * self.gap + 2 * self.border_width
            if adjusted_width != self.width:
                self.width = adjusted_width

        # Ensure all windows have decorations
        for window in windows:
            if window.object_id not in self.window_decorations:
                print(
                    f"TabDecoration: Creating decoration for window {window.object_id}"
                )
                self._create_decoration_for_window(window, self.width, self.height)

        # Remove decorations for windows no longer in list
        current_window_ids = {w.object_id for w in windows}
        for window_id in list(self.window_decorations.keys()):
            if window_id not in current_window_ids:
                print(f"TabDecoration: Removing decoration for window {window_id}")
                self._cleanup_window_decoration(window_id)

        # Render and commit for each window
        for window in windows:
            if window.object_id in self.window_decorations:
                self._render_and_commit_window(window, windows, focused_window)

    def _create_decoration_for_window(self, window: "Window", width: int, height: int):
        """Create tab bar decoration for a specific window."""
        from ..wayland import WlCompositor
        from ..shm import ShmPool, WlShm
        from ..protocol import (
            MessageEncoder,
            RiverWindowV1,
            RiverDecorationV1,
            ProtocolObject,
        )

        try:
            # Create wl_surface
            compositor = WlCompositor(self.connection.compositor_id, self.connection)
            surface = compositor.create_surface()

            # Create river_decoration_v1 - always use ABOVE, then position with offset
            decoration_id = self.connection.allocate_id()
            payload = MessageEncoder().new_id(decoration_id).object(surface).bytes()

            # Always attach decoration above window
            self.connection.send_message(
                window.object_id,
                RiverWindowV1.Request.GET_DECORATION_ABOVE,
                payload,
            )

            decoration_obj = ProtocolObject(decoration_id, RiverDecorationV1.INTERFACE)
            self.connection.register_object(decoration_obj)

            # Set offset based on orientation
            if self.orientation == "vertical":
                # Position on left side: negative X offset moves it left
                # Y offset: move up by border_width to align with outer border edge
                y_offset = -self.border_width
                offset_payload = MessageEncoder().int32(-width).int32(y_offset).bytes()
            else:
                # Position on top: X=0 keeps it centered, negative Y moves it up
                # Add border_width to move to outer top edge
                offset_payload = (
                    MessageEncoder().int32(0).int32(-height - self.border_width).bytes()
                )

            self.connection.send_message(
                decoration_id,
                RiverDecorationV1.Request.SET_OFFSET,
                offset_payload,
            )

            # Synchronize decoration with window commits
            self.connection.send_message(
                decoration_id,
                RiverDecorationV1.Request.SYNC_NEXT_COMMIT,
            )

            # Create shared memory pool and buffer
            stride = width * 4
            size = stride * self.height
            pool = ShmPool(self.connection, size)
            buffer = pool.create_buffer(
                0, width, self.height, stride, WlShm.FORMAT_ARGB8888
            )

            # Store decoration data
            self.window_decorations[window.object_id] = {
                "surface": surface,
                "decoration": decoration_obj,
                "pool": pool,
                "buffer": buffer,
                "width": width,
            }

        except Exception as e:
            print(
                f"TabDecoration: Error creating decoration for window {window.object_id}: {e}"
            )

    def _render_and_commit_window(
        self,
        window: "Window",
        all_windows: List["Window"],
        focused_window: Optional["Window"],
    ):
        """Render tabs for a specific window's decoration."""
        dec = self.window_decorations.get(window.object_id)
        if not dec:
            return

        try:
            # Get shared memory data
            shm_data = dec["pool"].get_data()

            # Render tabs with Cairo
            self._render_tabs_to_buffer(
                shm_data, dec["width"], all_windows, focused_window
            )

            # Attach, damage, and commit
            from ..wayland import WlSurface

            if isinstance(dec["surface"], WlSurface):
                dec["surface"].attach(dec["buffer"], 0, 0)
                dec["surface"].damage_buffer(0, 0, dec["width"], self.height)
                dec["surface"].commit()

        except Exception as e:
            print(f"TabDecoration: Error rendering window {window.object_id}: {e}")

    def _render_tabs_to_buffer(
        self,
        shm_data,
        width: int,
        windows: List["Window"],
        focused_window: Optional["Window"],
    ):
        """Render tabs with Cairo to shared memory buffer."""
        if not shm_data:
            return

        try:
            # Create Cairo surface
            stride = width * 4
            surface = cairo.ImageSurface.create_for_data(
                shm_data, cairo.FORMAT_ARGB32, width, self.height, stride
            )
            ctx = cairo.Context(surface)

            if self.orientation == "vertical":
                self._render_vertical_tabs(ctx, width, windows, focused_window)
            else:
                self._render_horizontal_tabs(ctx, width, windows, focused_window)

            # Ensure drawing is complete
            surface.flush()
        except Exception as e:
            print(f"TabDecoration: Error rendering tabs: {e}")

    def _render_horizontal_tabs(
        self,
        ctx,
        width: int,
        windows: List["Window"],
        focused_window: Optional["Window"],
    ):
        """Render horizontal tabs."""
        num_tabs = len(windows)
        tab_width = width // num_tabs if num_tabs > 0 else width

        for i, window in enumerate(windows):
            x = i * tab_width
            is_focused = window == focused_window

            # Draw tab background
            if is_focused:
                self._set_cairo_color(ctx, self.style.focused_bg_color)
            else:
                self._set_cairo_color(ctx, self.style.bg_color)

            ctx.rectangle(x, 0, tab_width, self.height)
            ctx.fill()

            # Draw separator
            if i < num_tabs - 1:
                ctx.set_source_rgba(0.3, 0.3, 0.3, 1.0)
                ctx.set_line_width(1)
                ctx.move_to(x + tab_width, 0)
                ctx.line_to(x + tab_width, self.height)
                ctx.stroke()

            # Draw title
            title = window.title or "Untitled"
            self._set_cairo_color(ctx, self.style.text_color)
            ctx.select_font_face(
                "sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
            )
            ctx.set_font_size(12)

            # Truncate title if too long
            text_extents = ctx.text_extents(title)
            max_text_width = tab_width - 10
            if text_extents.width > max_text_width:
                # Binary search for right length
                left, right = 0, len(title)
                ellipsis = "..."
                ellipsis_width = ctx.text_extents(ellipsis).width
                available = max_text_width - ellipsis_width

                while left < right:
                    mid = (left + right + 1) // 2
                    test_width = ctx.text_extents(title[:mid]).width
                    if test_width <= available:
                        left = mid
                    else:
                        right = mid - 1

                title = title[:left] + ellipsis

            # Center text in tab
            text_extents = ctx.text_extents(title)
            text_x = x + (tab_width - text_extents.width) / 2
            text_y = self.height / 2 + text_extents.height / 2
            ctx.move_to(text_x, text_y)
            ctx.show_text(title)

    def _render_vertical_tabs(
        self,
        ctx,
        width: int,
        windows: List["Window"],
        focused_window: Optional["Window"],
    ):
        """Render vertical tabs with rotated text and control buttons."""
        import math

        num_tabs = len(windows)
        tab_height = self.height // num_tabs if num_tabs > 0 else self.height

        # Button configuration
        button_size = 16  # Size of each button
        button_padding = 4  # Padding between buttons
        buttons_area_height = (
            button_size + button_padding * 2
        )  # Total height for buttons at top

        for i, window in enumerate(windows):
            y = i * tab_height
            is_focused = window == focused_window

            # Draw tab background
            if is_focused:
                self._set_cairo_color(ctx, self.style.focused_bg_color)
            else:
                self._set_cairo_color(ctx, self.style.bg_color)

            ctx.rectangle(0, y, width, tab_height)
            ctx.fill()

            # Draw separator (horizontal line between tabs)
            if i < num_tabs - 1:
                ctx.set_source_rgba(0.3, 0.3, 0.3, 1.0)
                ctx.set_line_width(1)
                ctx.move_to(0, y + tab_height)
                ctx.line_to(width, y + tab_height)
                ctx.stroke()

            # Draw control buttons at the top of each tab (close, minimize, maximize)
            # Only show buttons if tab is tall enough
            if (
                tab_height > buttons_area_height + 40
            ):  # Need space for buttons + some text
                self._draw_tab_buttons(
                    ctx, width, y, button_size, button_padding, is_focused
                )
                # Adjust available space for title
                title_start_y = y + buttons_area_height
                title_available_height = tab_height - buttons_area_height - 10
            else:
                title_start_y = y + 5
                title_available_height = tab_height - 10

            # Draw title (rotated 90 degrees counterclockwise)
            title = window.title or "Untitled"
            self._set_cairo_color(ctx, self.style.text_color)
            ctx.select_font_face(
                "sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
            )
            ctx.set_font_size(12)

            # Truncate title if too long for available height
            text_extents = ctx.text_extents(title)
            if text_extents.width > title_available_height:
                # Binary search for right length
                left, right = 0, len(title)
                ellipsis = "..."
                ellipsis_width = ctx.text_extents(ellipsis).width
                available = title_available_height - ellipsis_width

                while left < right:
                    mid = (left + right + 1) // 2
                    test_width = ctx.text_extents(title[:mid]).width
                    if test_width <= available:
                        left = mid
                    else:
                        right = mid - 1

                title = title[:left] + ellipsis

            # Rotate and position text
            text_extents = ctx.text_extents(title)

            # Save context, translate to center of available space, rotate, draw text
            ctx.save()

            # Move to center of available text area
            text_center_x = width / 2
            text_center_y = title_start_y + title_available_height / 2
            ctx.translate(text_center_x, text_center_y)

            # Rotate 90 degrees counterclockwise (text runs from bottom to top)
            ctx.rotate(-math.pi / 2)

            # Draw text centered at origin
            ctx.move_to(-text_extents.width / 2, text_extents.height / 2)
            ctx.show_text(title)

            ctx.restore()

    def _draw_tab_buttons(
        self,
        ctx: cairo.Context,
        width: int,
        y_offset: int,
        button_size: int,
        padding: int,
        is_focused: bool,
    ):
        """Draw close, minimize, and maximize buttons for a tab.

        Buttons are arranged horizontally at the top of the tab.
        Layout: [close] [minimize] [maximize] (left to right)
        """
        # Button positions (centered horizontally in tab)
        total_buttons_width = 3 * button_size + 2 * padding
        start_x = (width - total_buttons_width) // 2
        button_y = y_offset + padding

        # Set button color
        button_color = (
            self.style.text_color
            if hasattr(self.style, "button_color")
            else self.style.text_color
        )

        ctx.set_line_width(1.5)

        # Close button (red X)
        close_x = start_x
        ctx.set_source_rgba(0.8, 0.2, 0.2, 1.0)  # Red
        # Draw X
        icon_padding = 3
        ctx.move_to(close_x + icon_padding, button_y + icon_padding)
        ctx.line_to(
            close_x + button_size - icon_padding, button_y + button_size - icon_padding
        )
        ctx.stroke()
        ctx.move_to(close_x + button_size - icon_padding, button_y + icon_padding)
        ctx.line_to(close_x + icon_padding, button_y + button_size - icon_padding)
        ctx.stroke()

        # Minimize button (horizontal line)
        minimize_x = start_x + button_size + padding
        self._set_cairo_color(ctx, button_color)
        y_center = button_y + button_size // 2
        ctx.move_to(minimize_x + 3, y_center)
        ctx.line_to(minimize_x + button_size - 3, y_center)
        ctx.stroke()

        # Maximize button (square)
        maximize_x = start_x + 2 * (button_size + padding)
        self._set_cairo_color(ctx, button_color)
        ctx.rectangle(maximize_x + 3, button_y + 3, button_size - 6, button_size - 6)
        ctx.stroke()

    def _set_cairo_color(self, ctx: cairo.Context, color: Tuple[int, int, int, int]):
        """Set Cairo color from RGBA tuple (0-255 values)."""
        ctx.set_source_rgba(
            color[0] / 255.0, color[1] / 255.0, color[2] / 255.0, color[3] / 255.0
        )

    def _cleanup_window_decoration(self, window_id: int):
        """Clean up decoration for a specific window."""
        if window_id not in self.window_decorations:
            return

        print(f"TabDecoration: Cleaning up decoration for window {window_id}")
        dec = self.window_decorations[window_id]

        # IMPORTANT: Destroy in correct order to avoid Wayland protocol errors
        # 1. Buffer first
        # 2. Decoration (role object) before surface
        # 3. Surface
        # 4. Pool last

        try:
            if dec.get("buffer"):
                if hasattr(dec["buffer"], "destroy_request"):
                    dec["buffer"].destroy_request()
                else:
                    dec["buffer"].destroy()
        except Exception as e:
            print(f"TabDecoration: Error destroying buffer: {e}")

        try:
            if dec.get("decoration"):
                # Destroy decoration BEFORE surface (it's the role object)
                # Send the river_decoration_v1.destroy request
                from ..protocol import RiverDecorationV1

                self.connection.send_message(
                    dec["decoration"].object_id, RiverDecorationV1.Request.DESTROY
                )
                dec["decoration"].destroy()
        except Exception as e:
            print(f"TabDecoration: Error destroying decoration: {e}")

        try:
            if dec.get("surface"):
                # Destroy surface AFTER decoration
                if hasattr(dec["surface"], "destroy_request"):
                    dec["surface"].destroy_request()
                else:
                    dec["surface"].destroy()
        except Exception as e:
            print(f"TabDecoration: Error destroying surface: {e}")

        try:
            if dec.get("pool"):
                # Pool uses destroy(), not cleanup()
                dec["pool"].destroy()
        except Exception as e:
            print(f"TabDecoration: Error destroying pool: {e}")

        del self.window_decorations[window_id]

    def cleanup(self):
        """Clean up all resources."""
        print(
            f"TabDecoration: Cleaning up all decorations ({len(self.window_decorations)} windows)"
        )
        for window_id in list(self.window_decorations.keys()):
            self._cleanup_window_decoration(window_id)
