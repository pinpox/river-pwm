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
    event_topic: str  # Event topic to publish (e.g., 'cmd.close_window')
    event_data: dict  # Additional event parameters


@dataclass
class PointerBinding:
    """Represents a pointer button binding."""

    button: int
    modifiers: "Modifiers"
    event_topic: str  # Event topic to publish
    event_data: dict  # Additional event parameters


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
        self,
        seat: Seat,
        keysym: int,
        modifiers: "Modifiers",
        event_topic: str,
        **event_data,
    ):
        """Create and enable a key binding that publishes a command event.

        Args:
            seat: The seat for this binding
            keysym: The key symbol
            modifiers: Modifier keys (Ctrl, Alt, etc.)
            event_topic: The command event topic to publish (e.g., 'cmd.close_window')
            **event_data: Optional data to pass with the event (e.g., workspace_id=3)
        """
        from pubsub import pub

        # Create a lambda that publishes the event
        def publish_command():
            pub.sendMessage(event_topic, **event_data)

        binding = self.manager.get_xkb_binding(seat, keysym, modifiers)
        binding.on_pressed = publish_command
        binding.enable()

        # Track binding
        if seat.object_id not in self.key_bindings:
            self.key_bindings[seat.object_id] = []
        self.key_bindings[seat.object_id].append(
            KeyBinding(keysym, modifiers, event_topic, event_data)
        )

    def bind_pointer(
        self,
        seat: Seat,
        button: int,
        modifiers: "Modifiers",
        event_topic: str,
        **event_data,
    ):
        """Create and enable a pointer button binding that publishes a command event.

        Args:
            seat: The seat for this binding
            button: Mouse button code
            modifiers: Modifier keys
            event_topic: The command event topic to publish
            **event_data: Optional data to pass with the event
        """
        from pubsub import pub

        # Create a lambda that publishes the event
        # For pointer bindings, we need to pass the seat
        def publish_command():
            pub.sendMessage(event_topic, seat=seat, **event_data)

        binding = seat.get_pointer_binding(button, modifiers)
        binding.on_pressed = publish_command
        binding.enable()

        # Track binding
        if seat.object_id not in self.pointer_bindings:
            self.pointer_bindings[seat.object_id] = []
        self.pointer_bindings[seat.object_id].append(
            PointerBinding(button, modifiers, event_topic, event_data)
        )

    def setup_default_bindings(
        self,
        seat: Seat,
        mod: "Modifiers",
        config: Dict,
    ):
        """Set up default window manager bindings (now event-based).

        Args:
            seat: The seat to configure
            mod: Primary modifier key
            config: Configuration dictionary with settings
        """
        from .protocol import Modifiers
        from . import topics

        # XKB keysym values - import from parent module
        from .riverwm import XKB

        # Window management
        self.bind_key(seat, XKB.q, mod | Modifiers.SHIFT, topics.CMD_QUIT)
        self.bind_key(seat, XKB.q, mod, topics.CMD_CLOSE_WINDOW)
        self.bind_key(seat, XKB.f, mod, topics.CMD_TOGGLE_FULLSCREEN)

        # Spawn applications
        self.bind_key(seat, XKB.Return, mod, topics.CMD_SPAWN_TERMINAL)
        self.bind_key(seat, XKB.d, mod, topics.CMD_SPAWN_LAUNCHER)

        # Focus navigation
        self.bind_key(seat, XKB.j, mod, topics.CMD_FOCUS_NEXT)
        self.bind_key(seat, XKB.k, mod, topics.CMD_FOCUS_PREV)
        self.bind_key(seat, XKB.Down, mod, topics.CMD_FOCUS_NEXT)
        self.bind_key(seat, XKB.Up, mod, topics.CMD_FOCUS_PREV)

        # Swap windows
        self.bind_key(seat, XKB.j, mod | Modifiers.SHIFT, topics.CMD_SWAP_NEXT)
        self.bind_key(seat, XKB.k, mod | Modifiers.SHIFT, topics.CMD_SWAP_PREV)

        # Promote to master
        self.bind_key(seat, XKB.Return, mod | Modifiers.SHIFT, topics.CMD_PROMOTE)

        # Cycle layouts
        self.bind_key(seat, XKB.space, mod, topics.CMD_CYCLE_LAYOUT)
        self.bind_key(
            seat, XKB.space, mod | Modifiers.SHIFT, topics.CMD_CYCLE_LAYOUT_REVERSE
        )

        # Tab cycling (for tabbed layout)
        self.bind_key(seat, XKB.Tab, mod, topics.CMD_CYCLE_TAB_FORWARD)
        self.bind_key(
            seat, XKB.Tab, mod | Modifiers.SHIFT, topics.CMD_CYCLE_TAB_BACKWARD
        )

        # Floating window toggles
        self.bind_key(seat, XKB.v, mod, topics.CMD_TOGGLE_FLOATING)
        self.bind_key(
            seat, XKB.v, mod | Modifiers.SHIFT, topics.CMD_TOGGLE_ALL_FLOATING
        )

        # Workspace bindings: Mod+1-9
        num_workspaces = config.get("num_workspaces", 9)
        for i in range(1, num_workspaces + 1):
            keysym = getattr(XKB, f"_{i}")
            # Switch to workspace
            self.bind_key(
                seat, keysym, mod, topics.CMD_SWITCH_WORKSPACE, workspace_id=i
            )
            # Move window to workspace
            self.bind_key(
                seat,
                keysym,
                mod | Modifiers.SHIFT,
                topics.CMD_MOVE_TO_WORKSPACE,
                workspace_id=i,
            )

        # Pointer bindings
        self.bind_pointer(seat, BTN.LEFT, mod, topics.CMD_START_MOVE)
        self.bind_pointer(seat, BTN.RIGHT, mod, topics.CMD_START_RESIZE)

    def setup_custom_bindings(self, seat: Seat, custom_bindings: list):
        """Set up user-defined custom keybindings.

        Args:
            seat: The seat to configure
            custom_bindings: List of (keysym, modifiers, event_topic, event_data) tuples
        """
        if not custom_bindings:
            return

        for binding in custom_bindings:
            keysym, modifiers, event_topic, event_data = binding
            self.bind_key(seat, keysym, modifiers, event_topic, **event_data)

    def cleanup_seat(self, seat: Seat):
        """Clean up bindings for a removed seat.

        Args:
            seat: The seat being removed
        """
        if seat.object_id in self.key_bindings:
            del self.key_bindings[seat.object_id]
        if seat.object_id in self.pointer_bindings:
            del self.pointer_bindings[seat.object_id]
