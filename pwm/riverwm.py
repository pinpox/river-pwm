"""
River Window Manager Implementation

A complete window manager built on the River Wayland compositor.
"""

from __future__ import annotations
import subprocess
import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple
from enum import Enum, auto

from .manager import WindowManager, ManagerState
from .objects import Window, Output, Seat, XkbBinding, PointerBinding
from .layout import (
    LayoutManager,
    LayoutGeometry,
    TilingLayout,
    MonocleLayout,
    GridLayout,
    FloatingLayout,
    CenteredMasterLayout,
    LayoutDirection,
)
from .protocol import Modifiers, WindowEdges, WindowCapabilities, BorderConfig


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
class BTN:
    """Mouse button codes."""

    LEFT = 0x110
    RIGHT = 0x111
    MIDDLE = 0x112


@dataclass
class RiverConfig:
    """Window manager configuration."""

    # Key binding modifier (Alt for now, to avoid conflicts in nested mode)
    mod: Modifiers = Modifiers.MOD1

    # Layout settings
    gap: int = 4
    border_width: int = 2
    border_color: Tuple[int, int, int, int] = (0x4C, 0x4C, 0x4C, 0xFF)
    focused_border_color: Tuple[int, int, int, int] = (0x52, 0x94, 0xE2, 0xFF)

    # Programs
    terminal: str = "foot"
    launcher: str = "fuzzel"

    # Number of workspaces
    num_workspaces: int = 9

    # Focus follows mouse
    focus_follows_mouse: bool = True


class OpType(Enum):
    """Interactive operation types."""

    NONE = auto()
    MOVE = auto()
    RESIZE = auto()


class RiverWM:
    """
    River Window Manager

    A tiling window manager for the River Wayland compositor.
    """

    def __init__(self, config: Optional[RiverConfig] = None):
        self.config = config or RiverConfig()
        self.manager = WindowManager()
        self.layout_manager = LayoutManager()

        # Configure layout manager
        self.layout_manager.gap = self.config.gap
        self.layout_manager.border_width = self.config.border_width
        self.layout_manager.num_workspaces = self.config.num_workspaces

        # Active state
        self.focused_window: Optional[Window] = None
        self.focused_output: Optional[Output] = None

        # Interactive operations
        self.op_type = OpType.NONE
        self.op_window: Optional[Window] = None
        self.op_seat: Optional[Seat] = None
        self.op_start_x: int = 0
        self.op_start_y: int = 0
        self.op_start_width: int = 0
        self.op_start_height: int = 0
        self.op_resize_edges: WindowEdges = WindowEdges.NONE

        # Set up callbacks
        self._setup_callbacks()

    def _setup_callbacks(self):
        """Set up window manager callbacks."""
        self.manager.on_window_created = self._on_window_created
        self.manager.on_window_closed = self._on_window_closed
        self.manager.on_output_created = self._on_output_created
        self.manager.on_output_removed = self._on_output_removed
        self.manager.on_seat_created = self._on_seat_created
        self.manager.on_seat_removed = self._on_seat_removed
        self.manager.on_manage_start = self._on_manage_start
        self.manager.on_render_start = self._on_render_start

    def _on_window_created(self, window: Window):
        """Handle new window."""
        # Add to layout
        self.layout_manager.add_window(window, self.focused_output)

        # Focus the new window
        self.focused_window = window

        # Set capabilities
        window.set_capabilities(
            WindowCapabilities.WINDOW_MENU
            | WindowCapabilities.MAXIMIZE
            | WindowCapabilities.FULLSCREEN
            | WindowCapabilities.MINIMIZE
        )

        # Handle window requests
        self._handle_window_requests(window)

    def _on_window_closed(self, window: Window):
        """Handle window closed."""
        self.layout_manager.remove_window(window)

        # Update focus
        if self.focused_window == window:
            self.focused_window = None
            # Try to focus another window
            if self.focused_output:
                workspace = self.layout_manager.get_active_workspace(
                    self.focused_output
                )
                if workspace and workspace.focused_window:
                    self.focused_window = workspace.focused_window

    def _on_output_created(self, output: Output):
        """Handle new output."""
        self.layout_manager.add_output(output)

        # Set as focused if none
        if self.focused_output is None:
            self.focused_output = output

        # Set as default for layer shell
        if output.layer_shell_output:
            output.layer_shell_output.set_default()

    def _on_output_removed(self, output: Output):
        """Handle output removed."""
        self.layout_manager.remove_output(output)

        if self.focused_output == output:
            self.focused_output = None
            if self.layout_manager.outputs:
                self.focused_output = next(iter(self.layout_manager.outputs.values()))

    def _on_seat_created(self, seat: Seat):
        """Handle new seat."""
        # Set up pointer callbacks
        if self.config.focus_follows_mouse:
            seat.on_pointer_enter = lambda win: self._on_pointer_enter(seat, win)

        seat.on_window_interaction = lambda win: self._on_window_interaction(seat, win)
        seat.on_op_delta = lambda dx, dy: self._on_op_delta(seat, dx, dy)
        seat.on_op_release = lambda: self._on_op_release(seat)

        # Set up key bindings
        self._setup_key_bindings(seat)

        # Set up pointer bindings
        self._setup_pointer_bindings(seat)

    def _on_seat_removed(self, seat: Seat):
        """Handle seat removed."""
        if self.op_seat == seat:
            self.op_type = OpType.NONE
            self.op_window = None
            self.op_seat = None

    def _on_pointer_enter(self, seat: Seat, window: Window):
        """Handle pointer entering a window."""
        if self.config.focus_follows_mouse and self.op_type == OpType.NONE:
            self.focused_window = window
            # Focus will be applied in next manage sequence
            self.manager.manage_dirty()

    def _on_window_interaction(self, seat: Seat, window: Window):
        """Handle window interaction (click)."""
        self.focused_window = window
        # Raise window to top
        workspace = self._get_window_workspace(window)
        if workspace and window in workspace.windows:
            workspace.focused_window = window

    def _on_op_delta(self, seat: Seat, dx: int, dy: int):
        """Handle operation delta."""
        if self.op_type == OpType.NONE or self.op_window is None:
            return

        if self.op_type == OpType.MOVE:
            # Update position in floating layout
            workspace = self._get_window_workspace(self.op_window)
            if workspace and isinstance(workspace.layout, FloatingLayout):
                new_x = self.op_start_x + dx
                new_y = self.op_start_y + dy
                workspace.layout.set_position(self.op_window, new_x, new_y)

        elif self.op_type == OpType.RESIZE:
            workspace = self._get_window_workspace(self.op_window)
            if workspace:
                new_width = self.op_start_width
                new_height = self.op_start_height
                new_x = self.op_start_x
                new_y = self.op_start_y

                if self.op_resize_edges & WindowEdges.RIGHT:
                    new_width = max(100, self.op_start_width + dx)
                elif self.op_resize_edges & WindowEdges.LEFT:
                    new_width = max(100, self.op_start_width - dx)
                    new_x = self.op_start_x + self.op_start_width - new_width

                if self.op_resize_edges & WindowEdges.BOTTOM:
                    new_height = max(100, self.op_start_height + dy)
                elif self.op_resize_edges & WindowEdges.TOP:
                    new_height = max(100, self.op_start_height - dy)
                    new_y = self.op_start_y + self.op_start_height - new_height

                if isinstance(workspace.layout, FloatingLayout):
                    workspace.layout.set_position(self.op_window, new_x, new_y)
                    workspace.layout.set_size(self.op_window, new_width, new_height)

    def _on_op_release(self, seat: Seat):
        """Handle operation release."""
        if self.op_window:
            self.op_window.inform_resize_end()
        self._end_operation(seat)

    def _end_operation(self, seat: Seat):
        """End an interactive operation."""
        if self.op_seat == seat:
            seat.op_end()
            self.op_type = OpType.NONE
            self.op_window = None
            self.op_seat = None

    def _start_move(self, seat: Seat, window: Window):
        """Start an interactive move operation."""
        if self.op_type != OpType.NONE:
            return

        # Switch to floating layout if not already
        workspace = self._get_window_workspace(window)
        if workspace and not isinstance(workspace.layout, FloatingLayout):
            workspace.layout = FloatingLayout()
            # Initialize positions from current geometry
            geometries = self.layout_manager.calculate_layout(self.focused_output)
            for win, geom in geometries.items():
                workspace.layout.set_position(win, geom.x, geom.y)
                workspace.layout.set_size(win, geom.width, geom.height)

        self.op_type = OpType.MOVE
        self.op_window = window
        self.op_seat = seat

        # Get current position
        node = window.get_node()
        self.op_start_x = node.x
        self.op_start_y = node.y

        seat.op_start_pointer()

    def _start_resize(self, seat: Seat, window: Window, edges: WindowEdges):
        """Start an interactive resize operation."""
        if self.op_type != OpType.NONE:
            return

        # Switch to floating layout if not already
        workspace = self._get_window_workspace(window)
        if workspace and not isinstance(workspace.layout, FloatingLayout):
            workspace.layout = FloatingLayout()
            # Initialize positions from current geometry
            geometries = self.layout_manager.calculate_layout(self.focused_output)
            for win, geom in geometries.items():
                workspace.layout.set_position(win, geom.x, geom.y)
                workspace.layout.set_size(win, geom.width, geom.height)

        self.op_type = OpType.RESIZE
        self.op_window = window
        self.op_seat = seat
        self.op_resize_edges = edges

        # Get current geometry
        node = window.get_node()
        self.op_start_x = node.x
        self.op_start_y = node.y
        self.op_start_width = window.width
        self.op_start_height = window.height

        window.inform_resize_start()
        seat.op_start_pointer()

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
            geometries = self.layout_manager.calculate_layout(self.focused_output)

            # Track z-order
            prev_node = None
            for window, geom in geometries.items():
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
                        self._make_border_config(
                            geom.tiled_edges, self.config.focused_border_color
                        )
                    )
                else:
                    window.set_borders(
                        self._make_border_config(
                            geom.tiled_edges, self.config.border_color
                        )
                    )

                # Show window
                window.show()

            # Hide windows not in current workspace
            workspace = self.layout_manager.get_active_workspace(self.focused_output)
            if workspace:
                visible_windows = set(workspace.windows)
                for window in self.manager.windows.values():
                    if window not in visible_windows:
                        window.hide()

        # Finish render sequence
        self.manager.render_finish()

    def _make_border_config(
        self, edges: WindowEdges, color: Tuple[int, int, int, int]
    ) -> BorderConfig:
        """Create a border configuration."""
        if edges == WindowEdges.NONE:
            edges = (
                WindowEdges.TOP
                | WindowEdges.BOTTOM
                | WindowEdges.LEFT
                | WindowEdges.RIGHT
            )
        return BorderConfig(
            edges=edges,
            width=self.config.border_width,
            r=color[0],
            g=color[1],
            b=color[2],
            a=color[3],
        )

    def _setup_key_bindings(self, seat: Seat):
        """Set up key bindings for a seat."""
        mod = self.config.mod

        # Quit: Mod+Shift+Q
        self._bind_key(seat, XKB.q, mod | Modifiers.SHIFT, self._quit)

        # Close window: Mod+Q
        self._bind_key(seat, XKB.q, mod, self._close_focused)

        # Spawn terminal: Mod+Return
        self._bind_key(seat, XKB.Return, mod, lambda: self._spawn(self.config.terminal))

        # Spawn launcher: Mod+D
        self._bind_key(seat, XKB.d, mod, lambda: self._spawn(self.config.launcher))

        # Focus navigation
        self._bind_key(seat, XKB.j, mod, self._focus_next)
        self._bind_key(seat, XKB.k, mod, self._focus_prev)
        self._bind_key(seat, XKB.Down, mod, self._focus_next)
        self._bind_key(seat, XKB.Up, mod, self._focus_prev)

        # Swap windows
        self._bind_key(seat, XKB.j, mod | Modifiers.SHIFT, self._swap_next)
        self._bind_key(seat, XKB.k, mod | Modifiers.SHIFT, self._swap_prev)

        # Promote to master
        self._bind_key(seat, XKB.Return, mod | Modifiers.SHIFT, self._promote)

        # Cycle layouts
        self._bind_key(seat, XKB.space, mod, self._cycle_layout)
        self._bind_key(
            seat, XKB.space, mod | Modifiers.SHIFT, self._cycle_layout_reverse
        )

        # Toggle fullscreen: Mod+F
        self._bind_key(seat, XKB.f, mod, self._toggle_fullscreen)

        # Workspace bindings: Mod+1-9
        for i in range(1, self.config.num_workspaces + 1):
            keysym = getattr(XKB, f"_{i}")
            ws_id = i
            self._bind_key(
                seat, keysym, mod, lambda ws=ws_id: self._switch_workspace(ws)
            )
            self._bind_key(
                seat,
                keysym,
                mod | Modifiers.SHIFT,
                lambda ws=ws_id: self._move_to_workspace(ws),
            )

    def _bind_key(
        self, seat: Seat, keysym: int, modifiers: Modifiers, action: Callable
    ):
        """Create and enable a key binding."""
        binding = self.manager.get_xkb_binding(seat, keysym, modifiers)
        binding.on_pressed = action
        binding.enable()

    def _setup_pointer_bindings(self, seat: Seat):
        """Set up pointer bindings for a seat."""
        mod = self.config.mod

        # Move window: Mod+Left click
        move_binding = seat.get_pointer_binding(BTN.LEFT, mod)
        move_binding.on_pressed = lambda: self._on_move_binding_pressed(seat)
        move_binding.enable()

        # Resize window: Mod+Right click
        resize_binding = seat.get_pointer_binding(BTN.RIGHT, mod)
        resize_binding.on_pressed = lambda: self._on_resize_binding_pressed(seat)
        resize_binding.enable()

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

    # Actions

    def _quit(self):
        """Quit the window manager."""
        self.manager.stop()

    def _close_focused(self):
        """Close the focused window."""
        if self.focused_window:
            self.focused_window.close()

    def _spawn(self, command: str):
        """Spawn a program."""
        try:
            subprocess.Popen(
                command,
                shell=True,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"Failed to spawn {command}: {e}")

    def _focus_next(self):
        """Focus the next window."""
        if self.focused_output:
            workspace = self.layout_manager.get_active_workspace(self.focused_output)
            if workspace:
                workspace.focus_next()
                self.focused_window = workspace.focused_window
                self.manager.manage_dirty()

    def _focus_prev(self):
        """Focus the previous window."""
        if self.focused_output:
            workspace = self.layout_manager.get_active_workspace(self.focused_output)
            if workspace:
                workspace.focus_prev()
                self.focused_window = workspace.focused_window
                self.manager.manage_dirty()

    def _swap_next(self):
        """Swap focused window with next."""
        if self.focused_output:
            workspace = self.layout_manager.get_active_workspace(self.focused_output)
            if workspace:
                workspace.swap_next()
                self.manager.manage_dirty()

    def _swap_prev(self):
        """Swap focused window with previous."""
        if self.focused_output:
            workspace = self.layout_manager.get_active_workspace(self.focused_output)
            if workspace:
                workspace.swap_prev()
                self.manager.manage_dirty()

    def _promote(self):
        """Promote focused window to master."""
        if self.focused_output:
            workspace = self.layout_manager.get_active_workspace(self.focused_output)
            if workspace:
                workspace.promote()
                self.manager.manage_dirty()

    def _cycle_layout(self):
        """Cycle to the next layout."""
        if self.focused_output:
            self.layout_manager.cycle_layout(self.focused_output, 1)
            self.manager.manage_dirty()

    def _cycle_layout_reverse(self):
        """Cycle to the previous layout."""
        if self.focused_output:
            self.layout_manager.cycle_layout(self.focused_output, -1)
            self.manager.manage_dirty()

    def _toggle_fullscreen(self):
        """Toggle fullscreen for the focused window."""
        if self.focused_window and self.focused_output:
            from .objects import WindowState

            if self.focused_window.state == WindowState.FULLSCREEN:
                self.focused_window.exit_fullscreen()
                self.focused_window.inform_not_fullscreen()
            else:
                self.focused_window.fullscreen(self.focused_output)
                self.focused_window.inform_fullscreen()
            self.manager.manage_dirty()

    def _switch_workspace(self, workspace_id: int):
        """Switch to a workspace."""
        if self.focused_output:
            self.layout_manager.switch_workspace(self.focused_output, workspace_id)
            workspace = self.layout_manager.get_active_workspace(self.focused_output)
            if workspace:
                self.focused_window = workspace.focused_window
            self.manager.manage_dirty()

    def _move_to_workspace(self, workspace_id: int):
        """Move focused window to a workspace."""
        if self.focused_window:
            self.layout_manager.move_window_to_workspace(
                self.focused_window, workspace_id
            )
            # Focus another window in current workspace
            if self.focused_output:
                workspace = self.layout_manager.get_active_workspace(
                    self.focused_output
                )
                if workspace:
                    self.focused_window = workspace.focused_window
            self.manager.manage_dirty()

    def run(self):
        """Run the window manager."""
        if not self.manager.connect():
            print("Failed to connect to River compositor")
            return 1

        print("River Window Manager started")
        print(f"  Mod key: Alt")
        print(f"  Terminal: {self.config.terminal}")
        print(f"  Launcher: {self.config.launcher}")

        try:
            self.manager.run()
        except KeyboardInterrupt:
            pass
        finally:
            self.manager.disconnect()

        return 0


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="River Window Manager - A Python-based tiling window manager for River"
    )
    parser.add_argument(
        "--terminal",
        "-t",
        default="foot",
        help="Terminal emulator command (default: foot)",
    )
    parser.add_argument(
        "--launcher",
        "-l",
        default="fuzzel",
        help="Application launcher command (default: fuzzel)",
    )
    parser.add_argument(
        "--gap",
        "-g",
        type=int,
        default=4,
        help="Gap between windows in pixels (default: 4)",
    )
    parser.add_argument(
        "--border-width",
        "-b",
        type=int,
        default=2,
        help="Border width in pixels (default: 2)",
    )

    args = parser.parse_args()

    config = RiverConfig(
        terminal=args.terminal,
        launcher=args.launcher,
        gap=args.gap,
        border_width=args.border_width,
    )

    wm = RiverWM(config)
    return wm.run()


if __name__ == "__main__":
    import sys

    sys.exit(main())
