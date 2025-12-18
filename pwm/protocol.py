"""
River Window Management Protocol Bindings for Python

This module provides Python bindings for the river-window-management-v1,
river-xkb-bindings-v1, and river-layer-shell-v1 Wayland protocols.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import Callable, Any, Optional
import struct


class DecorationHint(IntEnum):
    """Window decoration hint."""

    ONLY_SUPPORTS_CSD = 0
    PREFERS_CSD = 1
    PREFERS_SSD = 2
    NO_PREFERENCE = 3


class WindowEdges(IntFlag):
    """Window edge flags."""

    NONE = 0
    TOP = 1
    BOTTOM = 2
    LEFT = 4
    RIGHT = 8


class WindowCapabilities(IntFlag):
    """Window capabilities."""

    WINDOW_MENU = 1
    MAXIMIZE = 2
    FULLSCREEN = 4
    MINIMIZE = 8


class Modifiers(IntFlag):
    """Keyboard modifiers."""

    NONE = 0
    SHIFT = 1
    CTRL = 4
    MOD1 = 8  # Alt
    MOD3 = 32
    MOD4 = 64  # Super/Logo
    MOD5 = 128


@dataclass
class DimensionHint:
    """Window dimension hints."""

    min_width: int = 0
    min_height: int = 0
    max_width: int = 0
    max_height: int = 0


@dataclass
class Position:
    """Position in logical coordinate space."""

    x: int = 0
    y: int = 0


@dataclass
class Dimensions:
    """Dimensions in logical coordinate space."""

    width: int = 0
    height: int = 0


@dataclass
class Area:
    """Area with position and dimensions."""

    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


@dataclass
class BorderConfig:
    """Window border configuration."""

    edges: WindowEdges = WindowEdges.NONE
    width: int = 0
    r: int = 0
    g: int = 0
    b: int = 0
    a: int = 0xFFFFFFFF


class ProtocolObject:
    """Base class for Wayland protocol objects."""

    def __init__(self, object_id: int, interface_name: str):
        self.object_id = object_id
        self.interface_name = interface_name
        self._destroyed = False

    def destroy(self):
        """Mark object as destroyed."""
        self._destroyed = True

    @property
    def is_valid(self) -> bool:
        """Check if object is still valid."""
        return not self._destroyed


class WaylandMessage:
    """Represents a Wayland wire protocol message."""

    def __init__(self, object_id: int, opcode: int, payload: bytes = b""):
        self.object_id = object_id
        self.opcode = opcode
        self.payload = payload

    def encode(self) -> bytes:
        """Encode message to wire format."""
        size = 8 + len(self.payload)
        # Pad to 32-bit boundary
        padding = (4 - (size % 4)) % 4
        header = struct.pack("<II", self.object_id, (size << 16) | self.opcode)
        return header + self.payload + (b"\x00" * padding)

    @classmethod
    def decode(cls, data: bytes) -> tuple["WaylandMessage", bytes]:
        """Decode message from wire format."""
        if len(data) < 8:
            raise ValueError("Not enough data for header")
        object_id, size_opcode = struct.unpack("<II", data[:8])
        size = size_opcode >> 16
        opcode = size_opcode & 0xFFFF
        if len(data) < size:
            raise ValueError(
                f"Not enough data for message: need {size}, have {len(data)}"
            )
        payload = data[8:size]
        # Round up to 32-bit boundary
        consumed = size + ((4 - (size % 4)) % 4)
        return cls(object_id, opcode, payload), data[consumed:]


class MessageEncoder:
    """Helper for encoding Wayland message arguments."""

    def __init__(self):
        self.data = bytearray()

    def int32(self, value: int) -> "MessageEncoder":
        self.data.extend(struct.pack("<i", value))
        return self

    def uint32(self, value: int) -> "MessageEncoder":
        self.data.extend(struct.pack("<I", value))
        return self

    def new_id(self, value: int) -> "MessageEncoder":
        return self.uint32(value)

    def object(self, obj: Optional[ProtocolObject]) -> "MessageEncoder":
        return self.uint32(obj.object_id if obj else 0)

    def string(self, value: Optional[str]) -> "MessageEncoder":
        if value is None:
            self.uint32(0)
        else:
            encoded = value.encode("utf-8") + b"\x00"
            self.uint32(len(encoded))
            self.data.extend(encoded)
            # Pad to 32-bit boundary
            padding = (4 - (len(encoded) % 4)) % 4
            self.data.extend(b"\x00" * padding)
        return self

    def fd(self, fd: int) -> "MessageEncoder":
        """Mark that a file descriptor will be sent.

        File descriptors are sent via SCM_RIGHTS ancillary data, not in the
        message payload. This method just records that an FD should be sent.
        """
        if not hasattr(self, 'fds'):
            self.fds = []
        self.fds.append(fd)
        return self

    def bytes(self) -> bytes:
        return bytes(self.data)


class MessageDecoder:
    """Helper for decoding Wayland message arguments."""

    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def int32(self) -> int:
        value = struct.unpack_from("<i", self.data, self.offset)[0]
        self.offset += 4
        return value

    def uint32(self) -> int:
        value = struct.unpack_from("<I", self.data, self.offset)[0]
        self.offset += 4
        return value

    def new_id(self) -> int:
        return self.uint32()

    def object_id(self) -> int:
        return self.uint32()

    def string(self) -> Optional[str]:
        length = self.uint32()
        if length == 0:
            return None
        # Length includes null terminator
        value = self.data[self.offset : self.offset + length - 1].decode("utf-8")
        self.offset += length
        # Skip padding
        padding = (4 - (length % 4)) % 4
        self.offset += padding
        return value


# Protocol interface names and opcodes
class RiverWindowManagerV1:
    """river_window_manager_v1 interface."""

    INTERFACE = "river_window_manager_v1"
    VERSION = 1

    # Requests (client -> server)
    class Request:
        STOP = 0
        DESTROY = 1
        MANAGE_FINISH = 2
        MANAGE_DIRTY = 3
        RENDER_FINISH = 4
        GET_SHELL_SURFACE = 5

    # Events (server -> client)
    class Event:
        UNAVAILABLE = 0
        FINISHED = 1
        MANAGE_START = 2
        RENDER_START = 3
        SESSION_LOCKED = 4
        SESSION_UNLOCKED = 5
        WINDOW = 6
        OUTPUT = 7
        SEAT = 8


class RiverWindowV1:
    """river_window_v1 interface."""

    INTERFACE = "river_window_v1"
    VERSION = 1

    class Request:
        DESTROY = 0
        CLOSE = 1
        GET_NODE = 2
        PROPOSE_DIMENSIONS = 3
        HIDE = 4
        SHOW = 5
        USE_CSD = 6
        USE_SSD = 7
        SET_BORDERS = 8
        SET_TILED = 9
        GET_DECORATION_ABOVE = 10
        GET_DECORATION_BELOW = 11
        INFORM_RESIZE_START = 12
        INFORM_RESIZE_END = 13
        SET_CAPABILITIES = 14
        INFORM_MAXIMIZED = 15
        INFORM_UNMAXIMIZED = 16
        INFORM_FULLSCREEN = 17
        INFORM_NOT_FULLSCREEN = 18
        FULLSCREEN = 19
        EXIT_FULLSCREEN = 20

    class Event:
        CLOSED = 0
        DIMENSIONS_HINT = 1
        DIMENSIONS = 2
        APP_ID = 3
        TITLE = 4
        PARENT = 5
        DECORATION_HINT = 6
        POINTER_MOVE_REQUESTED = 7
        POINTER_RESIZE_REQUESTED = 8
        SHOW_WINDOW_MENU_REQUESTED = 9
        MAXIMIZE_REQUESTED = 10
        UNMAXIMIZE_REQUESTED = 11
        FULLSCREEN_REQUESTED = 12
        EXIT_FULLSCREEN_REQUESTED = 13
        MINIMIZE_REQUESTED = 14


class RiverNodeV1:
    """river_node_v1 interface."""

    INTERFACE = "river_node_v1"
    VERSION = 1

    class Request:
        DESTROY = 0
        SET_POSITION = 1
        PLACE_TOP = 2
        PLACE_BOTTOM = 3
        PLACE_ABOVE = 4
        PLACE_BELOW = 5


class RiverOutputV1:
    """river_output_v1 interface."""

    INTERFACE = "river_output_v1"
    VERSION = 1

    class Request:
        DESTROY = 0

    class Event:
        REMOVED = 0
        WL_OUTPUT = 1
        POSITION = 2
        DIMENSIONS = 3


class RiverSeatV1:
    """river_seat_v1 interface."""

    INTERFACE = "river_seat_v1"
    VERSION = 1

    class Request:
        DESTROY = 0
        FOCUS_WINDOW = 1
        FOCUS_SHELL_SURFACE = 2
        CLEAR_FOCUS = 3
        OP_START_POINTER = 4
        OP_END = 5
        GET_POINTER_BINDING = 6

    class Event:
        REMOVED = 0
        WL_SEAT = 1
        POINTER_ENTER = 2
        POINTER_LEAVE = 3
        WINDOW_INTERACTION = 4
        SHELL_SURFACE_INTERACTION = 5
        OP_DELTA = 6
        OP_RELEASE = 7


class RiverPointerBindingV1:
    """river_pointer_binding_v1 interface."""

    INTERFACE = "river_pointer_binding_v1"
    VERSION = 1

    class Request:
        DESTROY = 0
        ENABLE = 1
        DISABLE = 2

    class Event:
        PRESSED = 0
        RELEASED = 1


class RiverXkbBindingsV1:
    """river_xkb_bindings_v1 interface."""

    INTERFACE = "river_xkb_bindings_v1"
    VERSION = 1

    class Request:
        DESTROY = 0
        GET_XKB_BINDING = 1


class RiverXkbBindingV1:
    """river_xkb_binding_v1 interface."""

    INTERFACE = "river_xkb_binding_v1"
    VERSION = 1

    class Request:
        DESTROY = 0
        SET_LAYOUT_OVERRIDE = 1
        ENABLE = 2
        DISABLE = 3

    class Event:
        PRESSED = 0
        RELEASED = 1


class RiverLayerShellV1:
    """river_layer_shell_v1 interface."""

    INTERFACE = "river_layer_shell_v1"
    VERSION = 1

    class Request:
        DESTROY = 0
        GET_OUTPUT = 1
        GET_SEAT = 2


class RiverLayerShellOutputV1:
    """river_layer_shell_output_v1 interface."""

    INTERFACE = "river_layer_shell_output_v1"
    VERSION = 1

    class Request:
        DESTROY = 0
        SET_DEFAULT = 1

    class Event:
        NON_EXCLUSIVE_AREA = 0


class RiverLayerShellSeatV1:
    """river_layer_shell_seat_v1 interface."""

    INTERFACE = "river_layer_shell_seat_v1"
    VERSION = 1

    class Request:
        DESTROY = 0

    class Event:
        FOCUS_EXCLUSIVE = 0
        FOCUS_NON_EXCLUSIVE = 1
        FOCUS_NONE = 2


class RiverShellSurfaceV1:
    """river_shell_surface_v1 interface."""

    INTERFACE = "river_shell_surface_v1"
    VERSION = 1

    class Request:
        DESTROY = 0
        GET_NODE = 1
        SYNC_NEXT_COMMIT = 2


class RiverDecorationV1:
    """river_decoration_v1 interface."""

    INTERFACE = "river_decoration_v1"
    VERSION = 1

    class Request:
        DESTROY = 0
        SET_OFFSET = 1
        SYNC_NEXT_COMMIT = 2
