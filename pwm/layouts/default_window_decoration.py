"""
Default Window Decoration Rendering

Provides standard titlebar decorations for floating windows.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Dict

if TYPE_CHECKING:
    from ..objects import Window
    from ..connection import WaylandConnection
    from ..decoration import DecorationStyle
    from ..protocol import Area


class DefaultWindowDecoration:
    """Renders standard titlebar decorations for floating windows."""

    def __init__(
        self,
        connection: "WaylandConnection",
        style: "DecorationStyle",
    ):
        self.connection = connection
        self.style = style

        # Map of window_id -> decoration data
        self.window_decorations: Dict[int, Dict] = {}

    def render(
        self,
        windows: List["Window"],
        focused_window: Optional["Window"],
        area: "Area",
    ):
        """Render titlebar for each window."""
        if not windows:
            return

        # Ensure all windows have decorations
        for window in windows:
            if window.object_id not in self.window_decorations:
                print(
                    f"DefaultWindowDecoration: Creating decoration for window {window.object_id}"
                )
                self._create_decoration_for_window(window)

        # Remove decorations for windows no longer in list
        current_window_ids = {w.object_id for w in windows}
        for window_id in list(self.window_decorations.keys()):
            if window_id not in current_window_ids:
                print(
                    f"DefaultWindowDecoration: Removing decoration for window {window_id}"
                )
                self._cleanup_window_decoration(window_id)

        # Render and commit for each window
        for window in windows:
            if window.object_id in self.window_decorations:
                is_focused = window == focused_window
                self._render_and_commit_window(window, is_focused)

    def _create_decoration_for_window(self, window: "Window"):
        """Create titlebar decoration for a specific window."""
        from ..wayland import WlCompositor, WlSurface
        from ..shm import ShmPool, WlShm
        from ..protocol import (
            MessageEncoder,
            RiverWindowV1,
            RiverDecorationV1,
            ProtocolObject,
        )

        try:
            # Create wl_surface
            if self.connection.compositor_id is None:
                return
            compositor = WlCompositor(self.connection.compositor_id, self.connection)
            surface = compositor.create_surface()

            # Create river_decoration_v1
            decoration_id = self.connection.allocate_id()
            payload = MessageEncoder().new_id(decoration_id).object(surface).bytes()

            # Attach decoration based on position
            if self.style.position == "top":
                self.connection.send_message(
                    window.object_id,
                    RiverWindowV1.Request.GET_DECORATION_ABOVE,
                    payload,
                )
            else:  # bottom
                self.connection.send_message(
                    window.object_id,
                    RiverWindowV1.Request.GET_DECORATION_BELOW,
                    payload,
                )

            decoration_obj = ProtocolObject(decoration_id, RiverDecorationV1.INTERFACE)
            self.connection.register_object(decoration_obj)

            # Set offset based on position and borders
            if self.style.position == "top":
                # Move up by height + border to align with outer top edge
                offset_payload = (
                    MessageEncoder()
                    .int32(0)
                    .int32(-self.style.height - self.style.border_width)
                    .bytes()
                )
            else:  # bottom
                # Move down by border to align with outer bottom edge
                offset_payload = (
                    MessageEncoder().int32(0).int32(self.style.border_width).bytes()
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
            # Width will be updated based on window width
            width = 800  # Initial width, will be updated
            stride = width * 4
            size = stride * self.style.height
            pool = ShmPool(self.connection, size)
            buffer = pool.create_buffer(
                0, width, self.style.height, stride, WlShm.FORMAT_ARGB8888
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
                f"DefaultWindowDecoration: Error creating decoration for window {window.object_id}: {e}"
            )

    def _render_and_commit_window(self, window: "Window", is_focused: bool):
        """Render titlebar for a specific window."""
        dec = self.window_decorations.get(window.object_id)
        if not dec:
            return

        try:
            # Update buffer if window width changed
            # Use floating_size if available, otherwise use window.width
            if window.floating_size:
                window_width = window.floating_size[0]
            else:
                window_width = window.width if window.width > 0 else 800

            # Resize decoration if needed (decoration extends over borders)
            decoration_width = window_width + (self.style.border_width * 2)
            if decoration_width != dec["width"]:
                self._resize_decoration(window.object_id, decoration_width)

            # Get shared memory data
            shm_data = dec["pool"].get_data()

            # Render titlebar with DecorationRenderer
            from ..decoration import DecorationRenderer

            renderer = DecorationRenderer(self.style)
            renderer.render(
                width=dec["width"],
                title=window.title or "Untitled",
                focused=is_focused,
                maximized=False,  # TODO: Track maximize state
                shm_data=shm_data,
            )

            # Attach, damage, and commit
            from ..wayland import WlSurface

            if isinstance(dec["surface"], WlSurface):
                dec["surface"].attach(dec["buffer"], 0, 0)
                dec["surface"].damage_buffer(0, 0, dec["width"], self.style.height)
                dec["surface"].commit()

        except Exception as e:
            print(
                f"DefaultWindowDecoration: Error rendering window {window.object_id}: {e}"
            )

    def _resize_decoration(self, window_id: int, new_width: int):
        """Resize decoration buffer for a window.

        Args:
            window_id: Window object ID
            new_width: New decoration width (including borders)
        """
        dec = self.window_decorations.get(window_id)
        if not dec:
            return

        from ..shm import WlShm

        # Destroy old buffer
        if dec.get("buffer"):
            try:
                if hasattr(dec["buffer"], "destroy_request"):
                    dec["buffer"].destroy_request()
                else:
                    dec["buffer"].destroy()
            except Exception as e:
                print(f"DefaultWindowDecoration: Error destroying old buffer: {e}")

        # Create new buffer with updated width
        stride = new_width * 4
        size = stride * self.style.height

        # Resize pool if needed (can only grow)
        if dec["pool"].size < size:
            dec["pool"].resize(size)

        # Create new buffer
        dec["buffer"] = dec["pool"].create_buffer(
            0, new_width, self.style.height, stride, WlShm.FORMAT_ARGB8888
        )
        dec["width"] = new_width

    def _cleanup_window_decoration(self, window_id: int):
        """Clean up decoration for a specific window."""
        if window_id not in self.window_decorations:
            return

        print(f"DefaultWindowDecoration: Cleaning up decoration for window {window_id}")
        dec = self.window_decorations[window_id]

        # Destroy in correct order
        try:
            if dec.get("buffer"):
                if hasattr(dec["buffer"], "destroy_request"):
                    dec["buffer"].destroy_request()
                else:
                    dec["buffer"].destroy()
        except Exception as e:
            print(f"DefaultWindowDecoration: Error destroying buffer: {e}")

        try:
            if dec.get("decoration"):
                from ..protocol import RiverDecorationV1

                self.connection.send_message(
                    dec["decoration"].object_id, RiverDecorationV1.Request.DESTROY
                )
                dec["decoration"].destroy()
        except Exception as e:
            print(f"DefaultWindowDecoration: Error destroying decoration: {e}")

        try:
            if dec.get("surface"):
                if hasattr(dec["surface"], "destroy_request"):
                    dec["surface"].destroy_request()
                else:
                    dec["surface"].destroy()
        except Exception as e:
            print(f"DefaultWindowDecoration: Error destroying surface: {e}")

        try:
            if dec.get("pool"):
                dec["pool"].destroy()
        except Exception as e:
            print(f"DefaultWindowDecoration: Error destroying pool: {e}")

        del self.window_decorations[window_id]

    def cleanup(self):
        """Clean up all resources."""
        print(
            f"DefaultWindowDecoration: Cleaning up all decorations ({len(self.window_decorations)} windows)"
        )
        for window_id in list(self.window_decorations.keys()):
            self._cleanup_window_decoration(window_id)
