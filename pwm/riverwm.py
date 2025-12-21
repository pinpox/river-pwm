"""
River Window Manager Implementation

A complete window manager built on the River Wayland compositor.
"""

from __future__ import annotations
import time
from pubsub import pub
from . import topics
import subprocess
import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple
from enum import Enum, auto

from .manager import WindowManager, ManagerState
from .objects import Window, Output, Seat, XkbBinding, PointerBinding
from .layouts import (
    LayoutManager,
    LayoutGeometry,
    TilingLayout,
    MonocleLayout,
    GridLayout,
    CenteredMasterLayout,
    LayoutDirection,
)
from .protocol import Modifiers, WindowEdges, WindowCapabilities, BorderConfig
from .operation_manager import OperationManager, OpType
from .focus_manager import FocusManager
from .binding_manager import BindingManager, BTN


# XKB keysym values (from xkbcommon-keysyms.h)
class XKB:
    """Common XKB keysym constants."""

    # Letters
    a, b, c, d, e, f, g, h, i, j = (
        0x61,
        0x62,
        0x63,
        0x64,
        0x65,
        0x66,
        0x67,
        0x68,
        0x69,
        0x6A,
    )
    k, l, m, n, o, p, q, r, s, t = (
        0x6B,
        0x6C,
        0x6D,
        0x6E,
        0x6F,
        0x70,
        0x71,
        0x72,
        0x73,
        0x74,
    )
    u, v, w, x, y, z = 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A

    # Numbers
    _1, _2, _3, _4, _5 = 0x31, 0x32, 0x33, 0x34, 0x35
    _6, _7, _8, _9, _0 = 0x36, 0x37, 0x38, 0x39, 0x30

    # Function keys
    F1, F2, F3, F4, F5, F6 = 0xFFBE, 0xFFBF, 0xFFC0, 0xFFC1, 0xFFC2, 0xFFC3
    F7, F8, F9, F10, F11, F12 = 0xFFC4, 0xFFC5, 0xFFC6, 0xFFC7, 0xFFC8, 0xFFC9

    # Special keys
    Return = 0xFF0D
    Escape = 0xFF1B
    Tab = 0xFF09
    BackSpace = 0xFF08
    space = 0x20

    # Navigation
    Left = 0xFF51
    Up = 0xFF52
    Right = 0xFF53
    Down = 0xFF54
    Home = 0xFF50
    End = 0xFF57
    Page_Up = 0xFF55
    Page_Down = 0xFF56

    # Modifiers
    Shift_L = 0xFFE1
    Shift_R = 0xFFE2
    Control_L = 0xFFE3
    Control_R = 0xFFE4
    Alt_L = 0xFFE9
    Alt_R = 0xFFEA
    Super_L = 0xFFEB
    Super_R = 0xFFEC


# Linux input event codes (from linux/input-event-codes.h)
def parse_color(color: str | Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    """
    Parse a color value into RGBA tuple.

    Accepts:
    - Hex string: "#RRGGBB" or "#RRGGBBAA" (e.g., "#4c4c4c" or "#4c4c4cff")
    - Tuple: (R, G, B, A) where each value is 0-255

    Returns:
    - Tuple of (R, G, B, A) values from 0-255
    """
    if isinstance(color, str):
        # Remove '#' prefix if present
        color = color.lstrip("#")

        # Parse RGB or RGBA
        if len(color) == 6:
            # RGB format - add full opacity
            r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
            return (r, g, b, 0xFF)
        elif len(color) == 8:
            # RGBA format
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
            a = int(color[6:8], 16)
            return (r, g, b, a)
        else:
            raise ValueError(f"Invalid color format: {color}. Use #RRGGBB or #RRGGBBAA")
    elif isinstance(color, tuple) and len(color) == 4:
        return color
    else:
        raise ValueError(
            f"Invalid color type: {type(color)}. Use hex string or RGBA tuple"
        )


class DecorationPosition(Enum):
    """Position of server-side decorations."""

    TOP = "top"
    BOTTOM = "bottom"


@dataclass
class RiverConfig:
    """Window manager configuration."""

    # Key binding modifier (Alt for now, to avoid conflicts in nested mode)
    mod: Modifiers = Modifiers.MOD1

    # Layout settings
    gap: int = 4
    border_width: int = 2
    border_color: str | Tuple[int, int, int, int] = "#4c4c4c"
    focused_border_color: str | Tuple[int, int, int, int] = "#5294e2"

    # Server-side decorations
    use_ssd: bool = True
    ssd_position: DecorationPosition = DecorationPosition.BOTTOM
    ssd_height: int = 24
    ssd_background_color: str | Tuple[int, int, int, int] = "#2e3440"
    ssd_focused_background_color: str | Tuple[int, int, int, int] = "#3b4252"
    ssd_text_color: str | Tuple[int, int, int, int] = "#d8dee9"
    ssd_button_color: str | Tuple[int, int, int, int] = "#5e81ac"

    # Programs
    terminal: str = "foot"
    launcher: str = "fuzzel"

    # Number of workspaces
    num_workspaces: int = 9

    # Focus follows mouse
    focus_follows_mouse: bool = True

    # Layouts (default to all built-in layouts)
    layouts: Optional[List] = None

    # Custom keybindings: list of (keysym, modifiers, event_topic, event_data) tuples
    # Example: [(XKB.F1, Modifiers.MOD4, topics.CMD_SWITCH_WORKSPACE, {"workspace_id": 10})]
    custom_keybindings: Optional[List[Tuple[int, Modifiers, str, dict]]] = None

    def __post_init__(self):
        """Parse color strings into tuples."""
        self.border_color = parse_color(self.border_color)
        self.focused_border_color = parse_color(self.focused_border_color)
        self.ssd_background_color = parse_color(self.ssd_background_color)
        self.ssd_focused_background_color = parse_color(
            self.ssd_focused_background_color
        )
        self.ssd_text_color = parse_color(self.ssd_text_color)
        self.ssd_button_color = parse_color(self.ssd_button_color)

    def get_layouts(self):
        """Get configured layouts or default layouts."""
        if self.layouts is not None:
            return self.layouts

        # Default layouts
        from .layouts import TabbedLayout

        effective_gap = self.gap + (self.border_width * 2)
        return [
            TilingLayout(LayoutDirection.HORIZONTAL, gap=effective_gap),
            TilingLayout(LayoutDirection.VERTICAL, gap=effective_gap),
            MonocleLayout(gap=effective_gap),
            TabbedLayout(
                gap=effective_gap, tab_width=None, border_width=self.border_width
            ),  # Auto-width vertical tabs
            GridLayout(gap=effective_gap),
            CenteredMasterLayout(gap=effective_gap),
        ]


class RiverWM:
    """
    River Window Manager

    A tiling window manager for the River Wayland compositor.
    """

    def __init__(self, config: Optional[RiverConfig] = None):
        """Initialize River WM.

        Architecture:
        1. Create event bus (Pypubsub)
        2. Create components - they self-subscribe to events
        3. Set up Wayland callbacks to bridge protocol events into bus
        4. Run
        """
        self.config = config or RiverConfig()
        self.manager = WindowManager()

        # Setup debug event logging if enabled
        if os.getenv("PWM_DEBUG"):
            pub.subscribe(self.debug_event_logger, pub.ALL_TOPICS)

        # Create layout manager with configured layouts
        layouts = self.config.get_layouts()
        self.layout_manager = LayoutManager(bus=pub, layouts=layouts)

        # Configure layout manager
        self.layout_manager.gap = self.config.gap
        self.layout_manager.border_width = self.config.border_width
        self.layout_manager.num_workspaces = self.config.num_workspaces

        # Focus management (self-subscribes to events)
        self.focus_manager = FocusManager(
            bus=pub,
            get_window_workspace_fn=self._get_window_workspace,
            get_active_workspace_fn=lambda output: self.layout_manager.get_active_workspace(
                output
            ),
            focus_follows_mouse=self.config.focus_follows_mouse,
        )

        # Interactive operations (self-subscribes to events)
        self.operation_manager = OperationManager(
            get_window_workspace_fn=self._get_window_workspace
        )

        # Key and pointer bindings (publishes command events)
        self.binding_manager = BindingManager(manager=self.manager)

        # Window lifecycle commands (self-subscribes)
        from .window_controller import WindowController

        self.window_controller = WindowController(bus=pub, window_manager=self.manager)

        # Application spawning (self-subscribes)
        from .application_launcher import ApplicationLauncher

        self.application_launcher = ApplicationLauncher(bus=pub, config=self.config)

        # IPC server (self-subscribes for broadcasting, publishes commands)
        from .ipc import IPCServer

        self.ipc = IPCServer(self)
        self.manager.ipc_poll_callback = self.ipc.poll

        # Bridge Wayland protocol events into the event bus
        self._setup_callbacks()

    @property
    def focused_window(self):
        """Get the currently focused window (delegates to FocusManager)."""
        return self.focus_manager.focused_window

    @focused_window.setter
    def focused_window(self, value):
        """Set the focused window (delegates to FocusManager)."""
        self.focus_manager.set_focused_window(value)

    @property
    def focused_output(self):
        """Get the currently focused output (delegates to FocusManager)."""
        return self.focus_manager.focused_output

    @focused_output.setter
    def focused_output(self, value):
        """Set the focused output (delegates to FocusManager)."""
        self.focus_manager.set_focused_output(value)

    def debug_event_logger(self, topic=pub.AUTO_TOPIC, **kwargs):
        """Log all events published on the event bus."""
        timestamp = time.strftime("%H:%M:%S")
        topic_name = topic.getName()
        # Format the event data nicely
        data_str = ", ".join(f"{k}={v}" for k, v in kwargs.items() if k != "topic")
        print(f"[{timestamp}] EVENT: {topic_name} | {data_str}")

    def _setup_callbacks(self):
        """Bridge Wayland protocol events into the event bus.

        This method sets up callbacks on the WindowManager to publish events
        to the bus when Wayland protocol events occur. Components subscribe
        to these events to react accordingly.

        RiverWM also subscribes to some events for River-specific setup like
        window capabilities, decorations, and keybindings.
        """
        from pubsub import pub
        from . import topics

        # Window lifecycle events
        self.manager.on_window_created = lambda w: pub.sendMessage(
            topics.WINDOW_CREATED, window=w
        )
        self.manager.on_window_closed = lambda w: pub.sendMessage(
            topics.WINDOW_CLOSED, window=w
        )

        # Output (monitor) events
        self.manager.on_output_created = lambda o: pub.sendMessage(
            topics.OUTPUT_CREATED, output=o
        )
        self.manager.on_output_removed = lambda o: pub.sendMessage(
            topics.OUTPUT_REMOVED, output=o
        )

        # Seat (input device) events
        self.manager.on_seat_created = lambda s: pub.sendMessage(
            topics.SEAT_CREATED, seat=s
        )
        self.manager.on_seat_removed = lambda s: pub.sendMessage(
            topics.SEAT_REMOVED, seat=s
        )

        # Lifecycle events
        self.manager.on_manage_start = lambda: pub.sendMessage(
            topics.LIFECYCLE_MANAGE_START
        )
        self.manager.on_render_start = lambda: pub.sendMessage(
            topics.LIFECYCLE_RENDER_START
        )

        # Subscribe to events that need River-specific handling
        pub.subscribe(self._on_window_created, topics.WINDOW_CREATED)
        pub.subscribe(self._on_seat_created, topics.SEAT_CREATED)
        pub.subscribe(self._on_seat_removed, topics.SEAT_REMOVED)
        pub.subscribe(self._on_manage_start, topics.LIFECYCLE_MANAGE_START)
        pub.subscribe(self._on_render_start, topics.LIFECYCLE_RENDER_START)

        # Subscribe to interactive operation commands
        pub.subscribe(self._on_start_move, topics.CMD_START_MOVE)
        pub.subscribe(self._on_start_resize, topics.CMD_START_RESIZE)

    def _on_window_created(self, window: Window):
        """Handle River-specific window setup.

        Note: LayoutManager and FocusManager handle window lifecycle via their
        own subscriptions. This method only does River protocol setup.
        """
        # Set capabilities
        window.set_capabilities(
            WindowCapabilities.WINDOW_MENU
            | WindowCapabilities.MAXIMIZE
            | WindowCapabilities.FULLSCREEN
            | WindowCapabilities.MINIMIZE
        )

        # Smart detection: Auto-float dialogs/utilities
        if window.should_auto_float():
            window.is_floating = True
            if self.focused_output:
                # Count floating windows for cascade
                workspace = self.layout_manager.get_active_workspace(
                    self.focused_output
                )
                if workspace:
                    cascade_count = sum(1 for w in workspace.windows if w.is_floating)
                    area = self.focused_output.area
                    if self.focused_output.layer_shell_output:
                        ls_area = (
                            self.focused_output.layer_shell_output.non_exclusive_area
                        )
                        if ls_area.width > 0 and ls_area.height > 0:
                            area = ls_area
                    window.initialize_floating(area, cascade_count)

        # Enable server-side decorations if configured
        if self.config.use_ssd:
            from .decoration import DecorationStyle

            print(
                f"DEBUG: Enabling SSD for window {window.object_id}, title={window.title}"
            )
            # Config colors are already parsed into tuples in __post_init__
            assert isinstance(self.config.ssd_background_color, tuple)
            assert isinstance(self.config.ssd_focused_background_color, tuple)
            assert isinstance(self.config.ssd_text_color, tuple)
            assert isinstance(self.config.ssd_button_color, tuple)

            style = DecorationStyle(
                height=self.config.ssd_height,
                position=self.config.ssd_position.value,
                bg_color=self.config.ssd_background_color,
                focused_bg_color=self.config.ssd_focused_background_color,
                text_color=self.config.ssd_text_color,
                button_color=self.config.ssd_button_color,
                border_width=self.config.border_width,
            )
            window.enable_ssd(style)

        # Handle window requests
        self._handle_window_requests(window)

    def _on_seat_created(self, seat: Seat):
        """Handle new seat."""
        # Set up pointer callbacks
        if self.config.focus_follows_mouse:
            seat.on_pointer_enter = lambda win: self._on_pointer_enter(seat, win)

        seat.on_window_interaction = lambda win: self._on_window_interaction(seat, win)
        seat.on_op_delta = lambda dx, dy: self._on_op_delta(seat, dx, dy)
        seat.on_op_release = lambda: self._on_op_release(seat)

        # Set up bindings (delegated to BindingManager)
        self._setup_bindings(seat)

    def _on_seat_removed(self, seat: Seat):
        """Handle seat removed."""
        # End any operation from this seat
        self.operation_manager.end_operation(seat)
        # Clean up bindings
        self.binding_manager.cleanup_seat(seat)

    def _on_pointer_enter(self, seat: Seat, window: Window):
        """Handle pointer entering a window - publish event to bus."""
        from pubsub import pub
        from . import topics

        # Publish pointer enter event so FocusManager can react
        pub.sendMessage(
            topics.POINTER_ENTER,
            window=window,
            in_operation=self.operation_manager.is_active(),
        )
        self.manager.manage_dirty()

    def _on_window_interaction(self, seat: Seat, window: Window):
        """Handle window interaction (click)."""
        self.focused_window = window
        # Raise window to top
        workspace = self._get_window_workspace(window)
        if workspace and window in workspace.windows:
            workspace.focused_window = window

    def _on_op_delta(self, seat: Seat, dx: int, dy: int):
        """Handle operation delta - delegated to OperationManager."""
        self.operation_manager.handle_delta(seat, dx, dy)

    def _on_op_release(self, seat: Seat):
        """Handle operation release - delegated to OperationManager."""
        self.operation_manager.end_operation(seat)

    def _end_operation(self, seat: Seat):
        """End an interactive operation - delegated to OperationManager."""
        self.operation_manager.end_operation(seat)

    def _on_start_move(self, seat: Seat):
        """Handle CMD_START_MOVE command - start moving focused window."""
        print("DEBUG: _on_start_move called")
        if not self.focused_output:
            print("DEBUG: No focused output")
            return

        workspace = self.layout_manager.get_active_workspace(self.focused_output)
        if not workspace or not workspace.focused_window:
            print("DEBUG: No workspace or focused window")
            return

        print(f"DEBUG: Starting move for window {workspace.focused_window.object_id}")
        self._start_move(seat, workspace.focused_window)

    def _on_start_resize(self, seat: Seat):
        """Handle CMD_START_RESIZE command - start resizing focused window."""
        from .protocol import WindowEdges

        if not self.focused_output:
            return

        workspace = self.layout_manager.get_active_workspace(self.focused_output)
        if not workspace or not workspace.focused_window:
            return

        # Default to bottom-right resize
        self._start_resize(
            seat, workspace.focused_window, WindowEdges.BOTTOM | WindowEdges.RIGHT
        )

    def _start_move(self, seat: Seat, window: Window):
        """Start an interactive move operation."""
        if self.operation_manager.is_active():
            return

        # Auto-float on move if not already floating
        if not window.is_floating:
            window.is_floating = True
            # Initialize from current geometry
            geometries = self.layout_manager.calculate_layout(self.focused_output)
            if window in geometries:
                geom = geometries[window]
                window.floating_pos = (geom.x, geom.y)
                window.floating_size = (geom.width, geom.height)

        # Delegate to OperationManager
        self.operation_manager.start_move(seat, window)

    def _start_resize(self, seat: Seat, window: Window, edges: WindowEdges):
        """Start an interactive resize operation."""
        if self.operation_manager.is_active():
            return

        # Auto-float on resize
        if not window.is_floating:
            window.is_floating = True
            geometries = self.layout_manager.calculate_layout(self.focused_output)
            if window in geometries:
                geom = geometries[window]
                window.floating_pos = (geom.x, geom.y)
                window.floating_size = (geom.width, geom.height)

        window.inform_resize_start()
        # Delegate to OperationManager
        self.operation_manager.start_resize(seat, window, edges)

    def _get_window_workspace(self, window: Window):
        """Get the workspace containing a window."""
        if window.object_id in self.layout_manager.window_workspace:
            output_id, ws_id = self.layout_manager.window_workspace[window.object_id]
            if output_id in self.layout_manager.workspaces:
                return self.layout_manager.workspaces[output_id].get(ws_id)
        return None

    def _handle_window_requests(self, window: Window):
        """Handle pending window requests."""
        # Handle move request
        if window.pending_pointer_move:
            self._start_move(window.pending_pointer_move, window)
            window.pending_pointer_move = None

        # Handle resize request
        if window.pending_pointer_resize:
            seat, edges = window.pending_pointer_resize
            self._start_resize(seat, window, edges)
            window.pending_pointer_resize = None

        # Handle fullscreen request
        if window.pending_fullscreen is not None:
            output = window.pending_fullscreen or self.focused_output
            if output:
                window.fullscreen(output)
                window.inform_fullscreen()
            window.pending_fullscreen = None

        # Handle exit fullscreen request
        if window.pending_exit_fullscreen:
            window.exit_fullscreen()
            window.inform_not_fullscreen()
            window.pending_exit_fullscreen = False

        # Handle maximize request
        if window.pending_maximize:
            window.inform_maximized()
            window.pending_maximize = False

        # Handle unmaximize request
        if window.pending_unmaximize:
            window.inform_unmaximized()
            window.pending_unmaximize = False

        # Handle minimize request
        if window.pending_minimize:
            window.hide()
            window.pending_minimize = False

    def _on_manage_start(self):
        """Handle manage sequence start."""
        # Handle any pending window requests
        for window in list(self.manager.windows.values()):
            self._handle_window_requests(window)

        # Apply focus
        if self.focused_window and self.manager.seats:
            seat = next(iter(self.manager.seats.values()))
            seat.focus_window(self.focused_window)

            # Update workspace focus
            workspace = self._get_window_workspace(self.focused_window)
            if workspace:
                workspace.focused_window = self.focused_window

        # Propose dimensions for all windows
        if (
            self.focused_output
            and self.focused_output.width > 0
            and self.focused_output.height > 0
        ):
            geometries = self.layout_manager.calculate_layout(self.focused_output)
            for window, geom in geometries.items():
                # Ensure dimensions are positive
                width = max(1, geom.width)
                height = max(1, geom.height)

                window.propose_dimensions(width, height)
                window.set_tiled(geom.tiled_edges)

        # Finish manage sequence
        self.manager.manage_finish()

    def _on_render_start(self):
        """Handle render sequence start."""
        # Position all windows
        if self.focused_output:
            workspace = self.layout_manager.get_active_workspace(self.focused_output)
            if not workspace:
                self.manager.render_finish()
                return

            geometries = self.layout_manager.calculate_layout(self.focused_output)

            # Separate tiled and floating windows for z-ordering
            tiled = [(w, g) for w, g in geometries.items() if not w.is_floating]
            floating = [(w, g) for w, g in geometries.items() if w.is_floating]

            # Track z-order for tiled windows
            prev_node = None

            # Render tiled windows first (bottom layer)
            for window, geom in tiled:
                node = window.get_node()
                node.set_position(geom.x, geom.y)

                # Stack windows
                if prev_node:
                    node.place_above(prev_node)
                else:
                    node.place_bottom()
                prev_node = node

                # Set borders
                if window == self.focused_window:
                    window.set_borders(
                        self._make_border_config(self.config.focused_border_color)
                    )
                else:
                    window.set_borders(
                        self._make_border_config(self.config.border_color)
                    )

                # Render per-window decorations (for tiled windows if not using layout decorations)
                window.on_render_start()

                window.show()

            # Render floating windows on top (always above tiled windows)
            # Reset prev_node to ensure floating windows start above all tiled windows
            prev_node = None
            for window, geom in floating:
                node = window.get_node()
                node.set_position(geom.x, geom.y)

                # Stack floating windows above all tiled windows
                if prev_node:
                    # Continue stacking within floating windows
                    node.place_above(prev_node)
                else:
                    # First floating window goes on top
                    node.place_top()
                prev_node = node

                # Set borders
                if window == self.focused_window:
                    window.set_borders(
                        self._make_border_config(self.config.focused_border_color)
                    )
                else:
                    window.set_borders(
                        self._make_border_config(self.config.border_color)
                    )

                # Render per-window decorations for floating windows
                window.on_render_start()

                window.show()

            # Render layout decorations
            # Layouts are responsible for ALL window decorations (titlebars, tabs, etc.)
            if workspace.layout.should_render_decorations():
                # Create decorations if needed
                if not hasattr(workspace.layout, "_decorations_created"):
                    from .decoration import DecorationStyle

                    style = DecorationStyle(
                        height=self.config.ssd_height,
                        position=self.config.ssd_position.value,
                        bg_color=self.config.ssd_background_color,
                        focused_bg_color=self.config.ssd_focused_background_color,
                        text_color=self.config.ssd_text_color,
                        button_color=self.config.ssd_button_color,
                        border_width=self.config.border_width,
                    )
                    workspace.layout.create_decorations(self.manager.connection, style)
                    workspace.layout._decorations_created = True

                # Render decorations only for tiled windows
                # Filter out floating windows - they don't need layout decorations
                tiled_windows = [w for w in workspace.windows if not w.is_floating]
                workspace.layout.render_decorations(
                    tiled_windows,
                    workspace.focused_window,
                    self.focused_output.area,
                )

            # Commit per-window decorations
            for window in workspace.windows:
                is_focused = window == workspace.focused_window
                window.on_render_finish(focused=is_focused)

            # Hide windows not in current workspace
            visible_windows = set(workspace.windows)
            for window in self.manager.windows.values():
                if window not in visible_windows:
                    window.hide()

        # Finish render sequence
        self.manager.render_finish()

    def _make_border_config(self, color: Tuple[int, int, int, int]) -> BorderConfig:
        """Create a border configuration."""
        # Always show borders on all edges
        edges = (
            WindowEdges.TOP | WindowEdges.BOTTOM | WindowEdges.LEFT | WindowEdges.RIGHT
        )

        # Convert 8-bit color values (0-255) to 32-bit (0-0xFFFFFFFF)
        # River protocol expects 32-bit RGBA values
        def to_32bit(val: int) -> int:
            return (val * 0xFFFFFFFF) // 255

        return BorderConfig(
            edges=edges,
            width=self.config.border_width,
            r=to_32bit(color[0]),
            g=to_32bit(color[1]),
            b=to_32bit(color[2]),
            a=to_32bit(color[3]),
        )

    def _setup_bindings(self, seat: Seat):
        """Set up all bindings for a seat (delegates to BindingManager)."""
        config = {
            "num_workspaces": self.config.num_workspaces,
        }

        # BindingManager now publishes event topics instead of calling actions
        self.binding_manager.setup_default_bindings(seat, self.config.mod, config)

        # Set up custom bindings if configured
        if self.config.custom_keybindings:
            self.binding_manager.setup_custom_bindings(
                seat, self.config.custom_keybindings
            )

    def _on_move_binding_pressed(self, seat: Seat):
        """Handle move binding pressed."""
        if seat.pointer_window:
            self._start_move(seat, seat.pointer_window)

    def _on_resize_binding_pressed(self, seat: Seat):
        """Handle resize binding pressed."""
        if seat.pointer_window:
            # Default to bottom-right resize
            self._start_resize(
                seat, seat.pointer_window, WindowEdges.RIGHT | WindowEdges.BOTTOM
            )

    def run(self):
        """Run the window manager."""
        if not self.manager.connect():
            print("Failed to connect to River compositor")
            return 1

        # Start IPC server
        try:
            self.ipc.start()
            # Update WAYLAND_DISPLAY to match River's display
            # This ensures spawned programs connect to River, not parent compositor
            if hasattr(self.manager.connection, "display_name"):
                wayland_display = self.manager.connection.display_name
                os.environ["WAYLAND_DISPLAY"] = wayland_display
                print(f"IPC server listening on {self.ipc.socket_path}")
                print(f"Updated WAYLAND_DISPLAY={wayland_display}")
            else:
                print(f"IPC server listening on {self.ipc.socket_path}")

            # Set I3SOCK/SWAYSOCK so i3/sway-compatible tools (like Waybar) use pwm's IPC
            socket_path = str(self.ipc.socket_path)
            os.environ["I3SOCK"] = socket_path
            os.environ["SWAYSOCK"] = socket_path
            print(f"Set I3SOCK/SWAYSOCK={socket_path}")
        except Exception as e:
            print(f"Warning: Failed to start IPC server: {e}")

        print("River Window Manager started")
        print(f"  Mod key: Alt")
        print(f"  Terminal: {self.config.terminal}")
        print(f"  Launcher: {self.config.launcher}")

        try:
            self.manager.run()
        except KeyboardInterrupt:
            pass
        finally:
            self.ipc.stop()
            self.manager.disconnect()

        return 0


def main():
    """Main entry point."""
    config = RiverConfig()
    wm = PWM(config)
    return wm.run()


if __name__ == "__main__":
    import sys

    sys.exit(main())
