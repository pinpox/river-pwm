"""
River Window Manager Core

Main window manager class that handles the protocol state machine
and coordinates window management.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Set, Any
import signal

from .connection import WaylandConnection, GlobalInfo
from .protocol import (
    MessageEncoder, MessageDecoder, WaylandMessage, ProtocolObject,
    RiverWindowManagerV1, RiverWindowV1, RiverOutputV1, RiverSeatV1,
    RiverXkbBindingsV1, RiverLayerShellV1, Modifiers,
)
from .objects import (
    Window, Node, Output, Seat, PointerBinding, XkbBinding,
    LayerShellOutput, LayerShellSeat,
)


class ManagerState(Enum):
    """Window manager state machine states."""
    IDLE = auto()
    MANAGE = auto()
    RENDER = auto()


class WindowManager:
    """
    River Window Manager

    Implements the river-window-management-v1 protocol to manage windows.
    """

    def __init__(self):
        self.connection = WaylandConnection()

        # Protocol objects
        self.wm_id: Optional[int] = None
        self.xkb_bindings_id: Optional[int] = None
        self.layer_shell_id: Optional[int] = None

        # Managed objects
        self.windows: Dict[int, Window] = {}
        self.outputs: Dict[int, Output] = {}
        self.seats: Dict[int, Seat] = {}

        # State
        self.state = ManagerState.IDLE
        self.session_locked = False
        self.running = False
        self.unavailable = False

        # Pending events to process
        self._pending_events: List[WaylandMessage] = []

        # Callbacks
        self.on_window_created: Optional[Callable[[Window], None]] = None
        self.on_window_closed: Optional[Callable[[Window], None]] = None
        self.on_output_created: Optional[Callable[[Output], None]] = None
        self.on_output_removed: Optional[Callable[[Output], None]] = None
        self.on_seat_created: Optional[Callable[[Seat], None]] = None
        self.on_seat_removed: Optional[Callable[[Seat], None]] = None
        self.on_manage_start: Optional[Callable[[], None]] = None
        self.on_render_start: Optional[Callable[[], None]] = None
        self.on_session_locked: Optional[Callable[[], None]] = None
        self.on_session_unlocked: Optional[Callable[[], None]] = None

    def connect(self, display: Optional[str] = None) -> bool:
        """Connect to the Wayland display and bind to River protocols."""
        if not self.connection.connect(display):
            return False

        # Get registry and wait for globals
        self.connection.get_registry()
        self.connection.on_event('wl_registry', 'global', self._on_global)

        if not self.connection.roundtrip():
            return False

        # Bind to river_window_manager_v1
        wm_global = self._find_global(RiverWindowManagerV1.INTERFACE)
        if not wm_global:
            print("river_window_manager_v1 not available")
            return False

        self.wm_id = self.connection.bind_global(
            wm_global.name,
            RiverWindowManagerV1.INTERFACE,
            min(wm_global.version, RiverWindowManagerV1.VERSION)
        )

        # Register the wm object so events are dispatched to it
        # This is critical - without this, River events won't be received!
        wm_obj = ProtocolObject(self.wm_id, RiverWindowManagerV1.INTERFACE)
        self.connection.register_object(wm_obj)

        # Bind to river_xkb_bindings_v1 if available
        xkb_global = self._find_global(RiverXkbBindingsV1.INTERFACE)
        if xkb_global:
            self.xkb_bindings_id = self.connection.bind_global(
                xkb_global.name,
                RiverXkbBindingsV1.INTERFACE,
                min(xkb_global.version, RiverXkbBindingsV1.VERSION)
            )

        # Bind to river_layer_shell_v1 if available
        layer_shell_global = self._find_global(RiverLayerShellV1.INTERFACE)
        if layer_shell_global:
            self.layer_shell_id = self.connection.bind_global(
                layer_shell_global.name,
                RiverLayerShellV1.INTERFACE,
                min(layer_shell_global.version, RiverLayerShellV1.VERSION)
            )

        # Set up event handling - register handlers for each event type
        for opcode in range(9):  # Events 0-8
            self.connection.on_event(RiverWindowManagerV1.INTERFACE, opcode, self._dispatch_wm_event)

        # Roundtrip to get initial state
        if not self.connection.roundtrip():
            return False

        return not self.unavailable

    def _find_global(self, interface: str) -> Optional[GlobalInfo]:
        """Find a global by interface name."""
        for g in self.connection.globals.values():
            if g.interface == interface:
                return g
        return None

    def _on_global(self, name: int, interface: str, version: int):
        """Handle new global advertisement."""
        pass  # We handle globals in connect()

    def send_request(self, object_id: int, opcode: int, payload: bytes = b''):
        """Send a request to the compositor."""
        self.connection.send_message(object_id, opcode, payload)

    def manage_finish(self):
        """Finish the current manage sequence."""
        if self.state != ManagerState.MANAGE:
            raise RuntimeError("manage_finish called outside manage sequence")
        self.send_request(self.wm_id, RiverWindowManagerV1.Request.MANAGE_FINISH)
        self.state = ManagerState.IDLE

    def manage_dirty(self):
        """Request a new manage sequence."""
        self.send_request(self.wm_id, RiverWindowManagerV1.Request.MANAGE_DIRTY)

    def render_finish(self):
        """Finish the current render sequence."""
        if self.state != ManagerState.RENDER:
            raise RuntimeError("render_finish called outside render sequence")
        self.send_request(self.wm_id, RiverWindowManagerV1.Request.RENDER_FINISH)
        self.state = ManagerState.IDLE

    def _handle_wm_event(self, msg: WaylandMessage):
        """Handle window manager events."""
        try:
            decoder = MessageDecoder(msg.payload)
        except Exception as e:
            print(f"[DEBUG] Error creating decoder: {e}")
            import traceback
            traceback.print_exc()
            return

        if msg.opcode == RiverWindowManagerV1.Event.UNAVAILABLE:
            print("Window management unavailable (another WM running?)")
            self.unavailable = True
            self.running = False

        elif msg.opcode == RiverWindowManagerV1.Event.FINISHED:
            self.running = False

        elif msg.opcode == RiverWindowManagerV1.Event.MANAGE_START:
            self.state = ManagerState.MANAGE
            # Process pending events
            self._process_pending_events()
            if self.on_manage_start:
                self.on_manage_start()

        elif msg.opcode == RiverWindowManagerV1.Event.RENDER_START:
            self.state = ManagerState.RENDER
            # Process pending events
            self._process_pending_events()
            if self.on_render_start:
                self.on_render_start()

        elif msg.opcode == RiverWindowManagerV1.Event.SESSION_LOCKED:
            self.session_locked = True
            if self.on_session_locked:
                self.on_session_locked()

        elif msg.opcode == RiverWindowManagerV1.Event.SESSION_UNLOCKED:
            self.session_locked = False
            if self.on_session_unlocked:
                self.on_session_unlocked()

        elif msg.opcode == RiverWindowManagerV1.Event.WINDOW:
            window_id = decoder.new_id()
            window = Window(window_id, self)
            self.windows[window_id] = window
            self.connection.register_object(window)
            window.on_closed = lambda w=window: self._on_window_closed(w)
            if self.on_window_created:
                self.on_window_created(window)

        elif msg.opcode == RiverWindowManagerV1.Event.OUTPUT:
            print(f"[DEBUG] Handling OUTPUT event")
            output_id = decoder.new_id()
            print(f"[DEBUG] Creating output with id={output_id}")
            output = Output(output_id, self)
            self.outputs[output_id] = output
            self.connection.register_object(output)
            output.on_removed = lambda o=output: self._on_output_removed(o)
            # Create layer shell output if available
            if self.layer_shell_id:
                self._create_layer_shell_output(output)
            print(f"[DEBUG] Calling on_output_created callback: {self.on_output_created}")
            if self.on_output_created:
                self.on_output_created(output)

        elif msg.opcode == RiverWindowManagerV1.Event.SEAT:
            print(f"[DEBUG] Handling SEAT event")
            seat_id = decoder.new_id()
            print(f"[DEBUG] Creating seat with id={seat_id}")
            seat = Seat(seat_id, self)
            self.seats[seat_id] = seat
            self.connection.register_object(seat)
            seat.on_removed = lambda s=seat: self._on_seat_removed(s)
            # Create layer shell seat if available
            if self.layer_shell_id:
                self._create_layer_shell_seat(seat)
            print(f"[DEBUG] Calling on_seat_created callback: {self.on_seat_created}")
            if self.on_seat_created:
                self.on_seat_created(seat)

    def _on_window_closed(self, window: Window):
        """Handle window closed."""
        if self.on_window_closed:
            self.on_window_closed(window)
        if window.object_id in self.windows:
            del self.windows[window.object_id]

    def _on_output_removed(self, output: Output):
        """Handle output removed."""
        if self.on_output_removed:
            self.on_output_removed(output)
        if output.object_id in self.outputs:
            del self.outputs[output.object_id]

    def _on_seat_removed(self, seat: Seat):
        """Handle seat removed."""
        if self.on_seat_removed:
            self.on_seat_removed(seat)
        if seat.object_id in self.seats:
            del self.seats[seat.object_id]

    def _create_layer_shell_output(self, output: Output):
        """Create layer shell output object."""
        obj_id = self.connection.allocate_id()
        ls_output = LayerShellOutput(obj_id, self, output)
        self.connection.register_object(ls_output)
        payload = MessageEncoder().new_id(obj_id).object(output).bytes()
        self.send_request(self.layer_shell_id, RiverLayerShellV1.Request.GET_OUTPUT, payload)

    def _create_layer_shell_seat(self, seat: Seat):
        """Create layer shell seat object."""
        obj_id = self.connection.allocate_id()
        ls_seat = LayerShellSeat(obj_id, self, seat)
        self.connection.register_object(ls_seat)
        payload = MessageEncoder().new_id(obj_id).object(seat).bytes()
        self.send_request(self.layer_shell_id, RiverLayerShellV1.Request.GET_SEAT, payload)

    def get_xkb_binding(self, seat: Seat, keysym: int, modifiers: Modifiers) -> XkbBinding:
        """Create an XKB key binding."""
        if not self.xkb_bindings_id:
            raise RuntimeError("XKB bindings not available")

        binding_id = self.connection.allocate_id()
        binding = XkbBinding(binding_id, self, seat, keysym, modifiers)
        seat.xkb_bindings[binding_id] = binding
        self.connection.register_object(binding)

        payload = (MessageEncoder()
                   .object(seat)
                   .new_id(binding_id)
                   .uint32(keysym)
                   .uint32(modifiers.value)
                   .bytes())
        self.send_request(self.xkb_bindings_id, RiverXkbBindingsV1.Request.GET_XKB_BINDING, payload)
        return binding

    def _process_pending_events(self):
        """Process any pending events."""
        events = self._pending_events
        self._pending_events = []
        for msg in events:
            self._dispatch_object_event(msg)

    def _dispatch_object_event(self, msg: WaylandMessage):
        """Dispatch an event to the appropriate object."""
        obj = self.connection.get_object(msg.object_id)
        if obj and hasattr(obj, 'handle_event'):
            obj.handle_event(msg)

    def _dispatch_wm_event(self, msg: WaylandMessage):
        """Dispatch window manager events."""
        if msg.object_id == self.wm_id:
            self._handle_wm_event(msg)
        else:
            # Queue event for object processing
            self._pending_events.append(msg)

    def run(self):
        """Run the main event loop."""
        self.running = True

        # Set up signal handling
        def signal_handler(signum, frame):
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        while self.running:
            # Poll for events
            if not self.connection.run_once(timeout=0.1):
                break

            # Dispatch any received events
            self._dispatch_events()

    def _dispatch_events(self):
        """Dispatch all received events."""
        # Process events in receive buffer
        while len(self.connection.recv_buffer) >= 8:
            try:
                msg, remaining = WaylandMessage.decode(bytes(self.connection.recv_buffer))
                self.connection.recv_buffer = bytearray(remaining)

                # Route to appropriate handler
                if msg.object_id == self.wm_id:
                    self._handle_wm_event(msg)
                elif msg.object_id == self.connection.registry_id:
                    # Registry events handled by connection
                    pass
                else:
                    # Object events queued for processing
                    self._dispatch_object_event(msg)

            except ValueError:
                break

    def stop(self):
        """Request to stop the window manager."""
        if self.wm_id:
            self.send_request(self.wm_id, RiverWindowManagerV1.Request.STOP)
        self.running = False

    def disconnect(self):
        """Disconnect from the Wayland display."""
        self.connection.disconnect()
