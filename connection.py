"""
Wayland Connection Module

Handles low-level Wayland socket communication.
"""

from __future__ import annotations
import os
import socket
import struct
import select
from typing import Callable, Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

from .protocol import (
    WaylandMessage, MessageEncoder, MessageDecoder, ProtocolObject
)


@dataclass
class GlobalInfo:
    """Information about a Wayland global."""
    name: int
    interface: str
    version: int


class WaylandConnection:
    """Manages the Wayland socket connection."""

    # Standard Wayland interfaces
    WL_DISPLAY = 1
    WL_REGISTRY_INTERFACE = "wl_registry"

    # wl_display opcodes
    WL_DISPLAY_SYNC = 0
    WL_DISPLAY_GET_REGISTRY = 1

    # wl_registry opcodes
    WL_REGISTRY_BIND = 0

    # wl_display events
    WL_DISPLAY_ERROR = 0
    WL_DISPLAY_DELETE_ID = 1

    # wl_registry events
    WL_REGISTRY_GLOBAL = 0
    WL_REGISTRY_GLOBAL_REMOVE = 1

    def __init__(self):
        self.socket: Optional[socket.socket] = None
        self.recv_buffer = bytearray()
        self.send_buffer = bytearray()

        # Object ID allocation
        self._next_id = 2  # 1 is reserved for wl_display
        self._objects: Dict[int, ProtocolObject] = {}

        # Registry
        self.registry_id: Optional[int] = None
        self.globals: Dict[int, GlobalInfo] = {}

        # Event handlers
        self._event_handlers: Dict[str, Dict[int, Callable]] = {}

        # Sync callbacks
        self._sync_callbacks: Dict[int, Callable] = {}
        self._sync_serial = 0

    def connect(self, display_name: Optional[str] = None) -> bool:
        """Connect to the Wayland display."""
        if display_name is None:
            display_name = os.environ.get('WAYLAND_DISPLAY', 'wayland-0')

        # Try XDG_RUNTIME_DIR first
        runtime_dir = os.environ.get('XDG_RUNTIME_DIR')
        if runtime_dir:
            socket_path = os.path.join(runtime_dir, display_name)
        else:
            socket_path = f'/tmp/{display_name}'

        try:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.setblocking(False)
            self.socket.connect(socket_path)
            return True
        except (socket.error, FileNotFoundError) as e:
            print(f"Failed to connect to Wayland display: {e}")
            return False

    def disconnect(self):
        """Disconnect from the Wayland display."""
        if self.socket:
            self.socket.close()
            self.socket = None

    def allocate_id(self) -> int:
        """Allocate a new object ID."""
        obj_id = self._next_id
        self._next_id += 1
        return obj_id

    def register_object(self, obj: ProtocolObject):
        """Register a protocol object."""
        self._objects[obj.object_id] = obj

    def unregister_object(self, obj_id: int):
        """Unregister a protocol object."""
        if obj_id in self._objects:
            del self._objects[obj_id]

    def get_object(self, obj_id: int) -> Optional[ProtocolObject]:
        """Get a registered protocol object."""
        return self._objects.get(obj_id)

    def send_message(self, object_id: int, opcode: int, payload: bytes = b''):
        """Queue a message to be sent."""
        msg = WaylandMessage(object_id, opcode, payload)
        self.send_buffer.extend(msg.encode())

    def flush(self) -> bool:
        """Send all queued messages."""
        if not self.socket or not self.send_buffer:
            return True

        try:
            sent = self.socket.send(bytes(self.send_buffer))
            self.send_buffer = self.send_buffer[sent:]
            return len(self.send_buffer) == 0
        except BlockingIOError:
            return False
        except socket.error as e:
            print(f"Socket send error: {e}")
            return False

    def recv(self) -> bool:
        """Receive data from socket."""
        if not self.socket:
            return False

        try:
            data = self.socket.recv(4096)
            if not data:
                return False
            self.recv_buffer.extend(data)
            return True
        except BlockingIOError:
            return True
        except socket.error as e:
            print(f"Socket recv error: {e}")
            return False

    def dispatch_events(self) -> int:
        """Process received events."""
        count = 0
        while len(self.recv_buffer) >= 8:
            try:
                msg, remaining = WaylandMessage.decode(bytes(self.recv_buffer))
                self.recv_buffer = bytearray(remaining)
                self._handle_event(msg)
                count += 1
            except ValueError:
                # Not enough data
                break
        return count

    def _handle_event(self, msg: WaylandMessage):
        """Handle an incoming event."""
        # Handle wl_display events
        if msg.object_id == self.WL_DISPLAY:
            if msg.opcode == self.WL_DISPLAY_ERROR:
                decoder = MessageDecoder(msg.payload)
                obj_id = decoder.object_id()
                code = decoder.uint32()
                message = decoder.string()
                print(f"Wayland error: object={obj_id}, code={code}, message={message}")
            elif msg.opcode == self.WL_DISPLAY_DELETE_ID:
                decoder = MessageDecoder(msg.payload)
                obj_id = decoder.uint32()
                self.unregister_object(obj_id)
            return

        # Handle wl_registry events
        if msg.object_id == self.registry_id:
            if msg.opcode == self.WL_REGISTRY_GLOBAL:
                decoder = MessageDecoder(msg.payload)
                name = decoder.uint32()
                interface = decoder.string()
                version = decoder.uint32()
                self.globals[name] = GlobalInfo(name, interface, version)
                self._dispatch_event('wl_registry', 'global', name, interface, version)
            elif msg.opcode == self.WL_REGISTRY_GLOBAL_REMOVE:
                decoder = MessageDecoder(msg.payload)
                name = decoder.uint32()
                if name in self.globals:
                    del self.globals[name]
                self._dispatch_event('wl_registry', 'global_remove', name)
            return

        # Handle wl_callback events (for sync)
        if msg.object_id in self._sync_callbacks:
            callback = self._sync_callbacks.pop(msg.object_id)
            decoder = MessageDecoder(msg.payload)
            serial = decoder.uint32()
            callback(serial)
            self.unregister_object(msg.object_id)
            return

        # Dispatch to registered handlers
        obj = self._objects.get(msg.object_id)
        if obj:
            self._dispatch_event(obj.interface_name, msg.opcode, msg)

    def _dispatch_event(self, interface: str, event: Any, *args):
        """Dispatch event to handlers."""
        if interface in self._event_handlers:
            handlers = self._event_handlers[interface]
            if event in handlers:
                handlers[event](*args)

    def on_event(self, interface: str, event: Any, handler: Callable):
        """Register an event handler."""
        if interface not in self._event_handlers:
            self._event_handlers[interface] = {}
        self._event_handlers[interface][event] = handler

    def get_registry(self) -> int:
        """Get the wl_registry object."""
        self.registry_id = self.allocate_id()
        payload = MessageEncoder().new_id(self.registry_id).bytes()
        self.send_message(self.WL_DISPLAY, self.WL_DISPLAY_GET_REGISTRY, payload)
        return self.registry_id

    def sync(self, callback: Callable[[int], None]) -> int:
        """Request a sync callback."""
        callback_id = self.allocate_id()
        self._sync_callbacks[callback_id] = callback
        payload = MessageEncoder().new_id(callback_id).bytes()
        self.send_message(self.WL_DISPLAY, self.WL_DISPLAY_SYNC, payload)
        return callback_id

    def bind_global(self, name: int, interface: str, version: int) -> int:
        """Bind to a global interface."""
        if self.registry_id is None:
            raise RuntimeError("Registry not initialized")

        obj_id = self.allocate_id()
        payload = (MessageEncoder()
                   .uint32(name)
                   .string(interface)
                   .uint32(version)
                   .new_id(obj_id)
                   .bytes())
        self.send_message(self.registry_id, self.WL_REGISTRY_BIND, payload)
        return obj_id

    def roundtrip(self, timeout: float = 1.0) -> bool:
        """Perform a blocking roundtrip."""
        done = False

        def on_done(_serial):
            nonlocal done
            done = True

        self.sync(on_done)
        self.flush()

        while not done:
            readable, _, _ = select.select([self.socket], [], [], timeout)
            if not readable:
                return False
            if not self.recv():
                return False
            self.dispatch_events()

        return True

    def poll(self, timeout: float = 0.0) -> bool:
        """Poll for events without blocking."""
        if not self.socket:
            return False

        # Check for readable data
        readable, writable, _ = select.select(
            [self.socket],
            [self.socket] if self.send_buffer else [],
            [],
            timeout
        )

        # Send pending data
        if writable:
            self.flush()

        # Receive and dispatch
        if readable:
            if not self.recv():
                return False
            self.dispatch_events()

        return True

    def run_once(self, timeout: float = -1.0) -> bool:
        """Run a single iteration of the event loop."""
        if not self.socket:
            return False

        # Flush pending writes
        self.flush()

        # Wait for events
        if timeout < 0:
            readable, _, _ = select.select([self.socket], [], [])
        else:
            readable, _, _ = select.select([self.socket], [], [], timeout)

        if readable:
            if not self.recv():
                return False
            self.dispatch_events()

        return True

    def fileno(self) -> int:
        """Get the socket file descriptor."""
        return self.socket.fileno() if self.socket else -1
