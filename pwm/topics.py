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
