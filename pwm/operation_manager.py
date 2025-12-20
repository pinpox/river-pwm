"""
Operation Manager

Handles interactive move and resize operations for windows.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional, Callable

if TYPE_CHECKING:
    from .objects import Window, Seat
    from .protocol import WindowEdges
    from .layouts import FloatingLayout


class OpType(Enum):
    """Type of interactive operation."""

    NONE = auto()
    MOVE = auto()
    RESIZE = auto()


@dataclass
class Operation:
    """Represents an active interactive operation."""

    type: OpType
    window: Window
    seat: Seat
    start_x: int
    start_y: int
    start_width: int = 0
    start_height: int = 0
    resize_edges: "WindowEdges" = None


class OperationManager:
    """Manages interactive move and resize operations."""

    def __init__(self, get_window_workspace_fn: Callable):
        """Initialize operation manager.

        Args:
            get_window_workspace_fn: Function to get the workspace containing a window
        """
        self.current: Optional[Operation] = None
        self._get_window_workspace = get_window_workspace_fn

    def is_active(self) -> bool:
        """Check if an operation is currently active."""
        return self.current is not None

    def get_operation_type(self) -> OpType:
        """Get the current operation type."""
        return self.current.type if self.current else OpType.NONE

    def start_move(self, seat: Seat, window: Window) -> bool:
        """Start an interactive move operation.

        Args:
            seat: The seat initiating the operation
            window: The window to move

        Returns:
            True if operation started, False if operation already active
        """
        if self.current is not None:
            return False

        # Get current position
        node = window.get_node()

        self.current = Operation(
            type=OpType.MOVE,
            window=window,
            seat=seat,
            start_x=node.x,
            start_y=node.y,
        )

        seat.op_start_pointer()
        return True

    def start_resize(
        self, seat: Seat, window: Window, edges: "WindowEdges"
    ) -> bool:
        """Start an interactive resize operation.

        Args:
            seat: The seat initiating the operation
            window: The window to resize
            edges: Which edges to resize from

        Returns:
            True if operation started, False if operation already active
        """
        from .protocol import WindowEdges

        if self.current is not None:
            return False

        # Get current geometry
        node = window.get_node()
        workspace = self._get_window_workspace(window)
        if not workspace:
            return False

        # Get size from floating layout if available
        from .layouts import FloatingLayout

        if isinstance(workspace.layout, FloatingLayout):
            positions = workspace.layout._positions
            sizes = workspace.layout._sizes
            width = sizes.get(window.object_id, (800, 600))[0]
            height = sizes.get(window.object_id, (800, 600))[1]
        else:
            # Fallback to window dimensions
            width = window.width or 800
            height = window.height or 600

        self.current = Operation(
            type=OpType.RESIZE,
            window=window,
            seat=seat,
            start_x=node.x,
            start_y=node.y,
            start_width=width,
            start_height=height,
            resize_edges=edges if edges else WindowEdges.NONE,
        )

        seat.op_start_pointer()
        return True

    def handle_delta(self, seat: Seat, dx: int, dy: int):
        """Handle pointer motion during operation.

        Args:
            seat: The seat with motion
            dx: X delta from operation start
            dy: Y delta from operation start
        """
        from .protocol import WindowEdges
        from .layouts import FloatingLayout

        if not self.current or self.current.seat != seat:
            return

        workspace = self._get_window_workspace(self.current.window)
        if not workspace:
            return

        if self.current.type == OpType.MOVE:
            # Update position in floating layout
            if isinstance(workspace.layout, FloatingLayout):
                new_x = self.current.start_x + dx
                new_y = self.current.start_y + dy
                workspace.layout.set_position(self.current.window, new_x, new_y)

        elif self.current.type == OpType.RESIZE:
            new_width = self.current.start_width
            new_height = self.current.start_height
            new_x = self.current.start_x
            new_y = self.current.start_y

            # Calculate new dimensions based on which edges are being dragged
            if self.current.resize_edges & WindowEdges.RIGHT:
                new_width = max(100, self.current.start_width + dx)
            elif self.current.resize_edges & WindowEdges.LEFT:
                new_width = max(100, self.current.start_width - dx)
                new_x = self.current.start_x + self.current.start_width - new_width

            if self.current.resize_edges & WindowEdges.BOTTOM:
                new_height = max(100, self.current.start_height + dy)
            elif self.current.resize_edges & WindowEdges.TOP:
                new_height = max(100, self.current.start_height - dy)
                new_y = self.current.start_y + self.current.start_height - new_height

            # Update floating layout
            if isinstance(workspace.layout, FloatingLayout):
                workspace.layout.set_position(self.current.window, new_x, new_y)
                workspace.layout.set_size(self.current.window, new_width, new_height)

    def end_operation(self, seat: Seat):
        """End the current operation.

        Args:
            seat: The seat ending the operation
        """
        if not self.current or self.current.seat != seat:
            return

        # Inform window that resize has ended
        if self.current.window:
            self.current.window.inform_resize_end()

        seat.op_end()
        self.current = None

    def get_current_window(self) -> Optional[Window]:
        """Get the window involved in the current operation."""
        return self.current.window if self.current else None
