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
    """Manages focus for windows and outputs.

    This component subscribes to window/output lifecycle events and focus command events.
    It publishes FOCUS_CHANGED and FOCUSED_OUTPUT_CHANGED events for other components
    to track focus state.

    Responsibilities:
    - Track focused window and output
    - Handle window/output creation and removal
    - Handle pointer enter events for focus-follows-mouse
    - CMD_FOCUS_NEXT: Focus next window
    - CMD_FOCUS_PREV: Focus previous window
    """

    def __init__(
        self,
        bus,
        get_window_workspace_fn: Callable,
        get_active_workspace_fn: Callable,
        focus_follows_mouse: bool = True,
    ):
        """Initialize focus manager.

        Args:
            bus: Event bus instance (Pypubsub)
            get_window_workspace_fn: Function to get the workspace containing a window
            get_active_workspace_fn: Function to get the active workspace for an output
            focus_follows_mouse: Whether focus follows mouse pointer
        """
        self.bus = bus
        self._get_window_workspace = get_window_workspace_fn
        self._get_active_workspace = get_active_workspace_fn
        self.focus_follows_mouse = focus_follows_mouse

        self.focused_window: Optional[Window] = None
        self.focused_output: Optional[Output] = None

        self._setup_subscriptions()

    def _setup_subscriptions(self):
        """Subscribe to events FocusManager cares about."""
        from pubsub import pub
        from . import topics

        # Notification events
        pub.subscribe(self._on_window_created, topics.WINDOW_CREATED)
        pub.subscribe(self._on_window_closed, topics.WINDOW_CLOSED)
        pub.subscribe(self._on_pointer_enter, topics.POINTER_ENTER)
        pub.subscribe(self._on_output_created, topics.OUTPUT_CREATED)
        pub.subscribe(self._on_output_removed, topics.OUTPUT_REMOVED)

        # Command events
        pub.subscribe(self._on_focus_next, topics.CMD_FOCUS_NEXT)
        pub.subscribe(self._on_focus_prev, topics.CMD_FOCUS_PREV)

        # Workspace change notification
        pub.subscribe(self._on_workspace_switched, topics.WORKSPACE_SWITCHED)

    def set_focused_window(self, window: Optional[Window]):
        """Set the focused window and update workspace focus.

        Args:
            window: The window to focus, or None to clear focus
        """
        from pubsub import pub
        from . import topics

        self.focused_window = window

        # Update workspace focus
        if window:
            workspace = self._get_window_workspace(window)
            if workspace:
                workspace.focused_window = window

        # Publish focus change event
        pub.sendMessage(topics.FOCUS_CHANGED, window=window)

    def set_focused_output(self, output: Optional[Output]):
        """Set the focused output.

        Args:
            output: The output to focus, or None to clear
        """
        from pubsub import pub
        from . import topics

        self.focused_output = output

        # Publish output focus change event
        pub.sendMessage(topics.FOCUSED_OUTPUT_CHANGED, output=output)

    def _on_pointer_enter(self, window: Window, in_operation: bool):
        """Handle POINTER_ENTER event.

        Args:
            window: The window the pointer entered
            in_operation: Whether an interactive operation is active
        """
        if self.focus_follows_mouse and not in_operation:
            self.set_focused_window(window)

    def _on_window_created(self, window: Window):
        """Handle WINDOW_CREATED event.

        Args:
            window: The newly created window
        """
        # Focus the new window
        self.set_focused_window(window)

    def _on_window_closed(self, window: Window):
        """Handle WINDOW_CLOSED event.

        Args:
            window: The window being closed
        """
        # Update focus if this was the focused window
        if self.focused_window == window:
            # Clear focus first
            self.focused_window = None

            # Try to focus another window in the current workspace
            if self.focused_output:
                workspace = self._get_active_workspace(self.focused_output)
                if workspace and workspace.focused_window:
                    self.set_focused_window(workspace.focused_window)
                else:
                    # Publish None to indicate no focused window
                    from pubsub import pub
                    from . import topics

                    pub.sendMessage(topics.FOCUS_CHANGED, window=None)

    def _on_output_created(self, output: Output):
        """Handle OUTPUT_CREATED event.

        Args:
            output: The newly created output
        """
        # Set as focused if none
        if self.focused_output is None:
            self.set_focused_output(output)

    def _on_output_removed(self, output: Output):
        """Handle OUTPUT_REMOVED event.

        Args:
            output: The output being removed
        """
        # Need access to remaining outputs - get from riverwm via bus
        # For now, just clear if it's the focused one
        if self.focused_output == output:
            self.set_focused_output(None)

    def _on_focus_next(self):
        """Handle CMD_FOCUS_NEXT command."""
        if self.focused_output:
            workspace = self._get_active_workspace(self.focused_output)
            if workspace:
                workspace.focus_next()
                self.set_focused_window(workspace.focused_window)

    def _on_focus_prev(self):
        """Handle CMD_FOCUS_PREV command."""
        if self.focused_output:
            workspace = self._get_active_workspace(self.focused_output)
            if workspace:
                workspace.focus_prev()
                self.set_focused_window(workspace.focused_window)

    def _on_workspace_switched(self, current_workspace, old_workspace, output_name):
        """Handle WORKSPACE_SWITCHED event.

        Args:
            current_workspace: The new workspace ID
            old_workspace: The previous workspace ID
            output_name: Name of the output where switch occurred
        """
        # Update focus to reflect the new workspace's focused window
        if self.focused_output:
            workspace = self._get_active_workspace(self.focused_output)
            if workspace and workspace.focused_window:
                self.set_focused_window(workspace.focused_window)
            else:
                self.set_focused_window(None)

    def apply_focus(self, seats: list[Seat]):
        """Apply the current focus to all seats.

        Args:
            seats: List of seats to apply focus to
        """
        if self.focused_window and seats:
            for seat in seats:
                seat.focus_window(self.focused_window)

    def get_focused_window(self) -> Optional[Window]:
        """Get the currently focused window."""
        return self.focused_window

    def get_focused_output(self) -> Optional[Output]:
        """Get the currently focused output."""
        return self.focused_output
