"""
Focus Manager

Handles window and output focus tracking and management.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Callable

if TYPE_CHECKING:
    from .objects import Window, Output, Seat
    from .layouts.layout_base import Workspace


class FocusManager:
    """Manages focus for windows and outputs."""

    def __init__(
        self,
        get_window_workspace_fn: Callable,
        get_active_workspace_fn: Callable,
        focus_follows_mouse: bool = True,
    ):
        """Initialize focus manager.

        Args:
            get_window_workspace_fn: Function to get the workspace containing a window
            get_active_workspace_fn: Function to get the active workspace for an output
            focus_follows_mouse: Whether focus follows mouse pointer
        """
        self._get_window_workspace = get_window_workspace_fn
        self._get_active_workspace = get_active_workspace_fn
        self.focus_follows_mouse = focus_follows_mouse

        self.focused_window: Optional[Window] = None
        self.focused_output: Optional[Output] = None

    def set_focused_window(self, window: Optional[Window]):
        """Set the focused window and update workspace focus.

        Args:
            window: The window to focus, or None to clear focus
        """
        self.focused_window = window

        # Update workspace focus
        if window:
            workspace = self._get_window_workspace(window)
            if workspace:
                workspace.focused_window = window

    def set_focused_output(self, output: Optional[Output]):
        """Set the focused output.

        Args:
            output: The output to focus, or None to clear
        """
        self.focused_output = output

    def handle_pointer_enter(self, window: Window, in_operation: bool):
        """Handle pointer entering a window.

        Args:
            window: The window the pointer entered
            in_operation: Whether an interactive operation is active
        """
        if self.focus_follows_mouse and not in_operation:
            self.set_focused_window(window)

    def handle_window_added(self, window: Window):
        """Handle a new window being added.

        Args:
            window: The newly added window
        """
        # Focus the new window
        self.set_focused_window(window)

    def handle_window_removed(self, window: Window, outputs: dict):
        """Handle a window being removed.

        Args:
            window: The window being removed
            outputs: Dictionary of available outputs
        """
        # Update focus if this was the focused window
        if self.focused_window == window:
            self.focused_window = None

            # Try to focus another window
            if self.focused_output:
                workspace = self._get_active_workspace(self.focused_output)
                if workspace and workspace.focused_window:
                    self.set_focused_window(workspace.focused_window)

    def handle_output_added(self, output: Output):
        """Handle a new output being added.

        Args:
            output: The newly added output
        """
        # Set as focused if none
        if self.focused_output is None:
            self.focused_output = output

    def handle_output_removed(self, output: Output, outputs: dict):
        """Handle an output being removed.

        Args:
            output: The output being removed
            outputs: Dictionary of remaining outputs
        """
        if self.focused_output == output:
            self.focused_output = None
            if outputs:
                self.focused_output = next(iter(outputs.values()))

    def focus_next(self):
        """Focus the next window in the current workspace."""
        if self.focused_output:
            workspace = self._get_active_workspace(self.focused_output)
            if workspace:
                workspace.focus_next()
                self.set_focused_window(workspace.focused_window)

    def focus_prev(self):
        """Focus the previous window in the current workspace."""
        if self.focused_output:
            workspace = self._get_active_workspace(self.focused_output)
            if workspace:
                workspace.focus_prev()
                self.set_focused_window(workspace.focused_window)

    def apply_focus(self, seats: list[Seat]):
        """Apply the current focus to all seats.

        Args:
            seats: List of seats to apply focus to
        """
        if self.focused_window and seats:
            for seat in seats:
                seat.focus_window(self.focused_window)

    def update_after_workspace_change(self):
        """Update focus after workspace change."""
        if self.focused_output:
            workspace = self._get_active_workspace(self.focused_output)
            if workspace and workspace.focused_window:
                self.set_focused_window(workspace.focused_window)

    def get_focused_window(self) -> Optional[Window]:
        """Get the currently focused window."""
        return self.focused_window

    def get_focused_output(self) -> Optional[Output]:
        """Get the currently focused output."""
        return self.focused_output
