"""
Event Topics for pwm Window Manager

All pub/sub topics are defined here for easy discovery and documentation.
Topic naming convention: <category>.<action>

This centralizes all event topic names to make it easy to:
1. Discover what events are available
2. Ensure consistent naming across the codebase
3. Prevent typos in topic names
4. Document the purpose of each event
"""

# Window lifecycle events
WINDOW_CREATED = "window.created"
"""Published when a new window is created by the window manager."""

WINDOW_CLOSED = "window.closed"
"""Published when a window is closed/destroyed."""

WINDOW_FOCUSED = "window.focused"
"""Published when a window receives focus."""

# Output (monitor) events
OUTPUT_CREATED = "output.created"
"""Published when a new output (monitor) is connected."""

OUTPUT_REMOVED = "output.removed"
"""Published when an output (monitor) is disconnected."""

# Seat (input device) events
SEAT_CREATED = "seat.created"
"""Published when a new seat (input device group) is created."""

SEAT_REMOVED = "seat.removed"
"""Published when a seat is removed."""

# Pointer (mouse) events
POINTER_ENTER = "pointer.enter"
"""Published when the pointer enters a window."""

POINTER_LEAVE = "pointer.leave"
"""Published when the pointer leaves a window."""

# Workspace events
WORKSPACE_SWITCHED = "workspace.switched"
"""Published when switching between workspaces."""

# Operation events (interactive move/resize)
OPERATION_STARTED = "operation.started"
"""Published when an interactive operation (move/resize) starts."""

OPERATION_ENDED = "operation.ended"
"""Published when an interactive operation ends."""

# Lifecycle events
LIFECYCLE_MANAGE_START = "lifecycle.manage_start"
"""Published when window management starts."""

LIFECYCLE_RENDER_START = "lifecycle.render_start"
"""Published when rendering starts."""

# Command events (imperative - tell components to do something)
# These are triggered by user input (keybinds) or IPC commands

# Window management commands
CMD_CLOSE_WINDOW = "cmd.close_window"
"""Command: Close the focused window."""

CMD_QUIT = "cmd.quit"
"""Command: Quit the window manager."""

CMD_TOGGLE_FULLSCREEN = "cmd.toggle_fullscreen"
"""Command: Toggle fullscreen for focused window."""

# Focus commands
CMD_FOCUS_NEXT = "cmd.focus_next"
"""Command: Focus next window."""

CMD_FOCUS_PREV = "cmd.focus_prev"
"""Command: Focus previous window."""

# Window swap commands
CMD_SWAP_NEXT = "cmd.swap_next"
"""Command: Swap focused window with next."""

CMD_SWAP_PREV = "cmd.swap_prev"
"""Command: Swap focused window with previous."""

CMD_PROMOTE = "cmd.promote"
"""Command: Promote focused window to master position."""

# Layout commands
CMD_CYCLE_LAYOUT = "cmd.cycle_layout"
"""Command: Cycle to next layout."""

CMD_CYCLE_LAYOUT_REVERSE = "cmd.cycle_layout_reverse"
"""Command: Cycle to previous layout."""

# Tab commands (for tabbed layout)
CMD_CYCLE_TAB_FORWARD = "cmd.cycle_tab_forward"
"""Command: Cycle to next tab."""

CMD_CYCLE_TAB_BACKWARD = "cmd.cycle_tab_backward"
"""Command: Cycle to previous tab."""

# Workspace commands
CMD_SWITCH_WORKSPACE = "cmd.switch_workspace"
"""Command: Switch to a workspace. Requires workspace_id parameter."""

CMD_MOVE_TO_WORKSPACE = "cmd.move_to_workspace"
"""Command: Move focused window to a workspace. Requires workspace_id parameter."""

# Spawn commands
CMD_SPAWN_TERMINAL = "cmd.spawn_terminal"
"""Command: Spawn a terminal."""

CMD_SPAWN_LAUNCHER = "cmd.spawn_launcher"
"""Command: Spawn application launcher."""

# Interactive operation commands
CMD_START_MOVE = "cmd.start_move"
"""Command: Start interactive window move."""

CMD_START_RESIZE = "cmd.start_resize"
"""Command: Start interactive window resize."""

# Focus state notifications
FOCUS_CHANGED = "focus.changed"
"""Published when window focus changes. Params: window (or None)"""

FOCUSED_OUTPUT_CHANGED = "focus.output_changed"
"""Published when output focus changes. Params: output (or None)"""

LAYOUT_CHANGED = "layout.changed"
"""Published when the layout is changed (e.g., tile → grid → monocle)."""
