"""
Window Controller

Handles window lifecycle commands (close, fullscreen, quit).
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .objects import Window, WindowManager


class WindowController:
    """Handles window lifecycle commands.

    This component subscribes to command events and executes window operations.
    It tracks the focused window via the event bus to know which window to operate on.

    Responsibilities:
    - CMD_CLOSE_WINDOW: Close focused window
    - CMD_TOGGLE_FULLSCREEN: Toggle fullscreen on focused window
    - CMD_QUIT: Quit window manager
    """

    def __init__(self, bus, window_manager: "WindowManager"):
        """Initialize window controller.

        Args:
            bus: Event bus instance (Pypubsub)
            window_manager: WindowManager instance for quit operation
        """
        self.bus = bus
        self.window_manager = window_manager

        # Track focused window and output via bus subscriptions
        self.focused_window: Window | None = None
        self.focused_output = None

        self._setup_subscriptions()

    def _setup_subscriptions(self):
        """Subscribe to focus state and window command events."""
        from pubsub import pub
        from . import topics

        # Subscribe to focus state changes
        pub.subscribe(self._on_focus_changed, topics.FOCUS_CHANGED)
        pub.subscribe(self._on_focused_output_changed, topics.FOCUSED_OUTPUT_CHANGED)

        # Subscribe to window command events
        pub.subscribe(self._on_close_window, topics.CMD_CLOSE_WINDOW)
        pub.subscribe(self._on_toggle_fullscreen, topics.CMD_TOGGLE_FULLSCREEN)
        pub.subscribe(self._on_quit, topics.CMD_QUIT)

    def _on_focus_changed(self, window):
        """Track focused window from FocusManager."""
        self.focused_window = window

    def _on_focused_output_changed(self, output):
        """Track focused output from FocusManager."""
        self.focused_output = output

    def _on_close_window(self):
        """Handle CMD_CLOSE_WINDOW command."""
        if self.focused_window:
            self.focused_window.close()
            # window.close() will trigger window.closed notification event

    def _on_toggle_fullscreen(self):
        """Handle CMD_TOGGLE_FULLSCREEN command."""
        if self.focused_window and self.focused_output:
            from .objects import WindowState

            if self.focused_window.state == WindowState.FULLSCREEN:
                self.focused_window.exit_fullscreen()
                self.focused_window.inform_not_fullscreen()
            else:
                self.focused_window.fullscreen(self.focused_output)
                self.focused_window.inform_fullscreen()

    def _on_quit(self):
        """Handle CMD_QUIT command."""
        self.window_manager.stop()
