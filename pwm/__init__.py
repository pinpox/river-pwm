"""
pinpox' Window Manager (pwm)

A Python-based tiling window manager for the River Wayland compositor.

This package provides:
- Protocol bindings for river-window-management-v1
- Connection handling for Wayland sockets
- Window, output, and seat management objects
- Layout algorithms (tiling, monocle, grid, floating)
- A complete window manager implementation

Example usage:
    from pwm import RiverWM, RiverConfig

    config = RiverConfig(
        terminal='alacritty',
        launcher='wofi',
        gap=8,
    )
    wm = RiverWM(config)
    wm.run()

Or run directly:
    python -m pwm
"""

__version__ = "0.1.0"
__author__ = "pinpox"

from .protocol import (
    DecorationHint,
    WindowEdges,
    WindowCapabilities,
    Modifiers,
    DimensionHint,
    Position,
    Dimensions,
    Area,
    BorderConfig,
)

from .connection import WaylandConnection

from .objects import (
    Window,
    Node,
    Output,
    Seat,
    PointerBinding,
    XkbBinding,
    LayerShellOutput,
    LayerShellSeat,
)

from .manager import WindowManager, ManagerState

from .layouts import (
    Layout,
    LayoutGeometry,
    LayoutDirection,
    TilingLayout,
    MonocleLayout,
    GridLayout,
    FloatingLayout,
    CenteredMasterLayout,
    TabbedLayout,
    Workspace,
    LayoutManager,
)

from .riverwm import (
    RiverWM,
    RiverConfig,
    DecorationPosition,
    XKB,
    BTN,
)

from . import topics

__all__ = [
    # Version
    "__version__",
    # Protocol types
    "DecorationHint",
    "WindowEdges",
    "WindowCapabilities",
    "Modifiers",
    "DimensionHint",
    "Position",
    "Dimensions",
    "Area",
    "BorderConfig",
    # Connection
    "WaylandConnection",
    # Objects
    "Window",
    "Node",
    "Output",
    "Seat",
    "PointerBinding",
    "XkbBinding",
    "LayerShellOutput",
    "LayerShellSeat",
    # Manager
    "WindowManager",
    "ManagerState",
    # Layouts
    "Layout",
    "LayoutGeometry",
    "LayoutDirection",
    "TilingLayout",
    "MonocleLayout",
    "GridLayout",
    "FloatingLayout",
    "CenteredMasterLayout",
    "TabbedLayout",
    "Workspace",
    "LayoutManager",
    # Window Manager
    "RiverWM",
    "RiverConfig",
    "DecorationPosition",
    "XKB",
    "BTN",
    # Event topics
    "topics",
]
