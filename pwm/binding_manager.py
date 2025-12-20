"""
Binding Manager

Handles keyboard and pointer bindings for window manager actions.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Dict
from dataclasses import dataclass

if TYPE_CHECKING:
    from .objects import Seat
    from .protocol import Modifiers


class BTN:
    """Mouse button constants."""

    LEFT = 0x110
    RIGHT = 0x111
    MIDDLE = 0x112


@dataclass
class KeyBinding:
    """Represents a keyboard binding."""

    keysym: int
    modifiers: "Modifiers"
    action: Callable


@dataclass
class PointerBinding:
    """Represents a pointer button binding."""

    button: int
    modifiers: "Modifiers"
    action: Callable


class BindingManager:
    """Manages keyboard and pointer bindings."""

    def __init__(self, manager):
        """Initialize binding manager.

        Args:
            manager: The RiverManager instance for accessing protocol bindings
        """
        self.manager = manager
        self.key_bindings: Dict[int, list[KeyBinding]] = {}  # seat_id -> bindings
        self.pointer_bindings: Dict[int, list[PointerBinding]] = (
            {}
        )  # seat_id -> bindings

    def bind_key(
        self, seat: Seat, keysym: int, modifiers: "Modifiers", action: Callable
    ):
        """Create and enable a key binding.

        Args:
            seat: The seat for this binding
            keysym: The key symbol
            modifiers: Modifier keys (Ctrl, Alt, etc.)
            action: Callback function to execute when pressed
        """
        binding = self.manager.get_xkb_binding(seat, keysym, modifiers)
        binding.on_pressed = action
        binding.enable()

        # Track binding
        if seat.object_id not in self.key_bindings:
            self.key_bindings[seat.object_id] = []
        self.key_bindings[seat.object_id].append(KeyBinding(keysym, modifiers, action))

    def bind_pointer(
        self, seat: Seat, button: int, modifiers: "Modifiers", action: Callable
    ):
        """Create and enable a pointer button binding.

        Args:
            seat: The seat for this binding
            button: Mouse button code
            modifiers: Modifier keys
            action: Callback function to execute when pressed
        """
        binding = seat.get_pointer_binding(button, modifiers)
        binding.on_pressed = action
        binding.enable()

        # Track binding
        if seat.object_id not in self.pointer_bindings:
            self.pointer_bindings[seat.object_id] = []
        self.pointer_bindings[seat.object_id].append(
            PointerBinding(button, modifiers, action)
        )

    def setup_default_bindings(
        self,
        seat: Seat,
        mod: "Modifiers",
        actions: Dict[str, Callable],
        config: Dict,
    ):
        """Set up default window manager bindings.

        Args:
            seat: The seat to configure
            mod: Primary modifier key
            actions: Dictionary mapping action names to callbacks
            config: Configuration dictionary with settings
        """
        from .protocol import Modifiers

        # XKB keysym values - import from parent module
        from .riverwm import XKB

        # Window management
        self.bind_key(seat, XKB.q, mod | Modifiers.SHIFT, actions["quit"])
        self.bind_key(seat, XKB.q, mod, actions["close_focused"])

        # Spawn applications
        self.bind_key(seat, XKB.Return, mod, actions["spawn_terminal"])
        self.bind_key(seat, XKB.d, mod, actions["spawn_launcher"])

        # Focus navigation
        self.bind_key(seat, XKB.j, mod, actions["focus_next"])
        self.bind_key(seat, XKB.k, mod, actions["focus_prev"])
        self.bind_key(seat, XKB.Down, mod, actions["focus_next"])
        self.bind_key(seat, XKB.Up, mod, actions["focus_prev"])

        # Swap windows
        self.bind_key(seat, XKB.j, mod | Modifiers.SHIFT, actions["swap_next"])
        self.bind_key(seat, XKB.k, mod | Modifiers.SHIFT, actions["swap_prev"])

        # Promote to master
        self.bind_key(seat, XKB.Return, mod | Modifiers.SHIFT, actions["promote"])

        # Cycle layouts
        self.bind_key(seat, XKB.space, mod, actions["cycle_layout"])
        self.bind_key(
            seat, XKB.space, mod | Modifiers.SHIFT, actions["cycle_layout_reverse"]
        )

        # Toggle fullscreen
        self.bind_key(seat, XKB.f, mod, actions["toggle_fullscreen"])

        # Tab cycling (for tabbed layout)
        self.bind_key(seat, XKB.Tab, mod, actions["cycle_tab_forward"])
        self.bind_key(seat, XKB.Tab, mod | Modifiers.SHIFT, actions["cycle_tab_backward"])

        # Workspace bindings: Mod+1-9
        num_workspaces = config.get("num_workspaces", 9)
        for i in range(1, num_workspaces + 1):
            keysym = getattr(XKB, f"_{i}")
            ws_id = i
            # Switch to workspace
            self.bind_key(
                seat, keysym, mod, lambda ws=ws_id: actions["switch_workspace"](ws)
            )
            # Move window to workspace
            self.bind_key(
                seat,
                keysym,
                mod | Modifiers.SHIFT,
                lambda ws=ws_id: actions["move_to_workspace"](ws),
            )

        # Pointer bindings
        self.bind_pointer(seat, BTN.LEFT, mod, actions["move_binding_pressed"])
        self.bind_pointer(seat, BTN.RIGHT, mod, actions["resize_binding_pressed"])

    def cleanup_seat(self, seat: Seat):
        """Clean up bindings for a removed seat.

        Args:
            seat: The seat being removed
        """
        if seat.object_id in self.key_bindings:
            del self.key_bindings[seat.object_id]
        if seat.object_id in self.pointer_bindings:
            del self.pointer_bindings[seat.object_id]
