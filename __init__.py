"""
River Window Manager for Python

A Python-based tiling window manager for the River Wayland compositor.

This package provides:
- Protocol bindings for river-window-management-v1
- Connection handling for Wayland sockets
- Window, output, and seat management objects
- Layout algorithms (tiling, monocle, grid, floating)
- A complete window manager implementation

Example usage:
    from pywm import RiverWM, RiverConfig

    config = RiverConfig(
        terminal='alacritty',
        launcher='wofi',
        gap=8,
    )
    wm = RiverWM(config)
    wm.run()

Or run directly:
    python -m pywm
"""

__version__ = '0.1.0'
__author__ = 'River Developers'

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

from .layout import (
    Layout,
    LayoutGeometry,
    LayoutDirection,
    TilingLayout,
    MonocleLayout,
    GridLayout,
    FloatingLayout,
    CenteredMasterLayout,
    Workspace,
    LayoutManager,
)

from .riverwm import (
    RiverWM,
    RiverConfig,
    XKB,
    BTN,
)

__all__ = [
    # Version
    '__version__',

    # Protocol types
    'DecorationHint',
    'WindowEdges',
    'WindowCapabilities',
    'Modifiers',
    'DimensionHint',
    'Position',
    'Dimensions',
    'Area',
    'BorderConfig',

    # Connection
    'WaylandConnection',

    # Objects
    'Window',
    'Node',
    'Output',
    'Seat',
    'PointerBinding',
    'XkbBinding',
    'LayerShellOutput',
    'LayerShellSeat',

    # Manager
    'WindowManager',
    'ManagerState',

    # Layouts
    'Layout',
    'LayoutGeometry',
    'LayoutDirection',
    'TilingLayout',
    'MonocleLayout',
    'GridLayout',
    'FloatingLayout',
    'CenteredMasterLayout',
    'Workspace',
    'LayoutManager',

    # Window Manager
    'RiverWM',
    'RiverConfig',
    'XKB',
    'BTN',
]
