"""
River Window Manager Protocol Objects

High-level Python objects representing River protocol objects.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, TYPE_CHECKING
from enum import Enum, auto

from .protocol import (
    ProtocolObject, MessageEncoder, MessageDecoder, WaylandMessage,
    DecorationHint, WindowEdges, WindowCapabilities, Modifiers,
    DimensionHint, Position, Dimensions, Area, BorderConfig,
    RiverWindowV1, RiverNodeV1, RiverOutputV1, RiverSeatV1,
    RiverPointerBindingV1, RiverXkbBindingV1,
    RiverLayerShellOutputV1, RiverLayerShellSeatV1,
)

if TYPE_CHECKING:
    from .manager import WindowManager


class WindowState(Enum):
    """Window state tracking."""
    NORMAL = auto()
    MAXIMIZED = auto()
    FULLSCREEN = auto()
    HIDDEN = auto()


class Window(ProtocolObject):
    """Represents a managed window."""

    def __init__(self, object_id: int, manager: 'WindowManager'):
        super().__init__(object_id, RiverWindowV1.INTERFACE)
        self.manager = manager

        # Window properties
        self.app_id: Optional[str] = None
        self.title: Optional[str] = None
        self.parent: Optional[Window] = None
        self.decoration_hint = DecorationHint.NO_PREFERENCE

        # Dimension hints from client
        self.dimension_hint = DimensionHint()

        # Current dimensions (from server)
        self.width: int = 0
        self.height: int = 0

        # Proposed dimensions (from WM)
        self._proposed_width: int = 0
        self._proposed_height: int = 0
        self._dimensions_proposed = False

        # State
        self.state = WindowState.NORMAL
        self.fullscreen_output: Optional[Output] = None
        self.is_visible = True

        # Node for rendering
        self.node: Optional[Node] = None

        # Pending requests from window
        self.pending_pointer_move: Optional['Seat'] = None
        self.pending_pointer_resize: Optional[tuple['Seat', WindowEdges]] = None
        self.pending_maximize = False
        self.pending_unmaximize = False
        self.pending_fullscreen: Optional[Output] = None
        self.pending_exit_fullscreen = False
        self.pending_minimize = False

        # Callbacks
        self.on_closed: Optional[Callable[[], None]] = None

    def handle_event(self, msg: WaylandMessage):
        """Handle events from the compositor."""
        decoder = MessageDecoder(msg.payload)

        if msg.opcode == RiverWindowV1.Event.CLOSED:
            if self.on_closed:
                self.on_closed()

        elif msg.opcode == RiverWindowV1.Event.DIMENSIONS_HINT:
            self.dimension_hint.min_width = decoder.int32()
            self.dimension_hint.min_height = decoder.int32()
            self.dimension_hint.max_width = decoder.int32()
            self.dimension_hint.max_height = decoder.int32()

        elif msg.opcode == RiverWindowV1.Event.DIMENSIONS:
            self.width = decoder.int32()
            self.height = decoder.int32()
            self._dimensions_proposed = False

        elif msg.opcode == RiverWindowV1.Event.APP_ID:
            self.app_id = decoder.string()

        elif msg.opcode == RiverWindowV1.Event.TITLE:
            self.title = decoder.string()

        elif msg.opcode == RiverWindowV1.Event.PARENT:
            parent_id = decoder.object_id()
            self.parent = self.manager.windows.get(parent_id) if parent_id else None

        elif msg.opcode == RiverWindowV1.Event.DECORATION_HINT:
            self.decoration_hint = DecorationHint(decoder.uint32())

        elif msg.opcode == RiverWindowV1.Event.POINTER_MOVE_REQUESTED:
            seat_id = decoder.object_id()
            self.pending_pointer_move = self.manager.seats.get(seat_id)

        elif msg.opcode == RiverWindowV1.Event.POINTER_RESIZE_REQUESTED:
            seat_id = decoder.object_id()
            edges = WindowEdges(decoder.uint32())
            seat = self.manager.seats.get(seat_id)
            if seat:
                self.pending_pointer_resize = (seat, edges)

        elif msg.opcode == RiverWindowV1.Event.MAXIMIZE_REQUESTED:
            self.pending_maximize = True

        elif msg.opcode == RiverWindowV1.Event.UNMAXIMIZE_REQUESTED:
            self.pending_unmaximize = True

        elif msg.opcode == RiverWindowV1.Event.FULLSCREEN_REQUESTED:
            output_id = decoder.object_id()
            self.pending_fullscreen = self.manager.outputs.get(output_id)

        elif msg.opcode == RiverWindowV1.Event.EXIT_FULLSCREEN_REQUESTED:
            self.pending_exit_fullscreen = True

        elif msg.opcode == RiverWindowV1.Event.MINIMIZE_REQUESTED:
            self.pending_minimize = True

    def close(self):
        """Request window to close (manage state)."""
        self.manager.send_request(self.object_id, RiverWindowV1.Request.CLOSE)

    def get_node(self) -> 'Node':
        """Get or create the render node for this window."""
        if self.node is None:
            node_id = self.manager.connection.allocate_id()
            self.node = Node(node_id, self.manager)
            self.manager.connection.register_object(self.node)
            payload = MessageEncoder().new_id(node_id).bytes()
            self.manager.send_request(self.object_id, RiverWindowV1.Request.GET_NODE, payload)
        return self.node

    def propose_dimensions(self, width: int, height: int):
        """Propose dimensions for the window (manage state)."""
        self._proposed_width = width
        self._proposed_height = height
        self._dimensions_proposed = True
        payload = MessageEncoder().int32(width).int32(height).bytes()
        self.manager.send_request(self.object_id, RiverWindowV1.Request.PROPOSE_DIMENSIONS, payload)

    def hide(self):
        """Hide the window (render state)."""
        self.is_visible = False
        self.manager.send_request(self.object_id, RiverWindowV1.Request.HIDE)

    def show(self):
        """Show the window (render state)."""
        self.is_visible = True
        self.manager.send_request(self.object_id, RiverWindowV1.Request.SHOW)

    def use_csd(self):
        """Tell client to use client-side decoration (manage state)."""
        self.manager.send_request(self.object_id, RiverWindowV1.Request.USE_CSD)

    def use_ssd(self):
        """Tell client to use server-side decoration (manage state)."""
        self.manager.send_request(self.object_id, RiverWindowV1.Request.USE_SSD)

    def set_borders(self, config: BorderConfig):
        """Set window borders (render state)."""
        payload = (MessageEncoder()
                   .uint32(config.edges.value)
                   .int32(config.width)
                   .uint32(config.r)
                   .uint32(config.g)
                   .uint32(config.b)
                   .uint32(config.a)
                   .bytes())
        self.manager.send_request(self.object_id, RiverWindowV1.Request.SET_BORDERS, payload)

    def set_tiled(self, edges: WindowEdges):
        """Set tiled state (manage state)."""
        payload = MessageEncoder().uint32(edges.value).bytes()
        self.manager.send_request(self.object_id, RiverWindowV1.Request.SET_TILED, payload)

    def set_capabilities(self, caps: WindowCapabilities):
        """Set supported capabilities (manage state)."""
        payload = MessageEncoder().uint32(caps.value).bytes()
        self.manager.send_request(self.object_id, RiverWindowV1.Request.SET_CAPABILITIES, payload)

    def inform_resize_start(self):
        """Inform window resize is starting (manage state)."""
        self.manager.send_request(self.object_id, RiverWindowV1.Request.INFORM_RESIZE_START)

    def inform_resize_end(self):
        """Inform window resize has ended (manage state)."""
        self.manager.send_request(self.object_id, RiverWindowV1.Request.INFORM_RESIZE_END)

    def inform_maximized(self):
        """Inform window it is maximized (manage state)."""
        self.state = WindowState.MAXIMIZED
        self.manager.send_request(self.object_id, RiverWindowV1.Request.INFORM_MAXIMIZED)

    def inform_unmaximized(self):
        """Inform window it is unmaximized (manage state)."""
        self.state = WindowState.NORMAL
        self.manager.send_request(self.object_id, RiverWindowV1.Request.INFORM_UNMAXIMIZED)

    def inform_fullscreen(self):
        """Inform window it is fullscreen (manage state)."""
        self.manager.send_request(self.object_id, RiverWindowV1.Request.INFORM_FULLSCREEN)

    def inform_not_fullscreen(self):
        """Inform window it is not fullscreen (manage state)."""
        self.manager.send_request(self.object_id, RiverWindowV1.Request.INFORM_NOT_FULLSCREEN)

    def fullscreen(self, output: 'Output'):
        """Make window fullscreen on output (manage state)."""
        self.state = WindowState.FULLSCREEN
        self.fullscreen_output = output
        payload = MessageEncoder().object(output).bytes()
        self.manager.send_request(self.object_id, RiverWindowV1.Request.FULLSCREEN, payload)

    def exit_fullscreen(self):
        """Exit fullscreen mode (manage state)."""
        self.state = WindowState.NORMAL
        self.fullscreen_output = None
        self.manager.send_request(self.object_id, RiverWindowV1.Request.EXIT_FULLSCREEN)


class Node(ProtocolObject):
    """Represents a render list node."""

    def __init__(self, object_id: int, manager: 'WindowManager'):
        super().__init__(object_id, RiverNodeV1.INTERFACE)
        self.manager = manager
        self.x: int = 0
        self.y: int = 0

    def set_position(self, x: int, y: int):
        """Set absolute position (render state)."""
        self.x = x
        self.y = y
        payload = MessageEncoder().int32(x).int32(y).bytes()
        self.manager.send_request(self.object_id, RiverNodeV1.Request.SET_POSITION, payload)

    def place_top(self):
        """Place above all other nodes (render state)."""
        self.manager.send_request(self.object_id, RiverNodeV1.Request.PLACE_TOP)

    def place_bottom(self):
        """Place below all other nodes (render state)."""
        self.manager.send_request(self.object_id, RiverNodeV1.Request.PLACE_BOTTOM)

    def place_above(self, other: 'Node'):
        """Place above another node (render state)."""
        payload = MessageEncoder().object(other).bytes()
        self.manager.send_request(self.object_id, RiverNodeV1.Request.PLACE_ABOVE, payload)

    def place_below(self, other: 'Node'):
        """Place below another node (render state)."""
        payload = MessageEncoder().object(other).bytes()
        self.manager.send_request(self.object_id, RiverNodeV1.Request.PLACE_BELOW, payload)


class Output(ProtocolObject):
    """Represents a logical output."""

    def __init__(self, object_id: int, manager: 'WindowManager'):
        super().__init__(object_id, RiverOutputV1.INTERFACE)
        self.manager = manager

        self.wl_output_name: Optional[int] = None
        self.x: int = 0
        self.y: int = 0
        self.width: int = 0
        self.height: int = 0
        self.removed = False

        # Layer shell support
        self.layer_shell_output: Optional['LayerShellOutput'] = None

        # Callbacks
        self.on_removed: Optional[Callable[[], None]] = None

    def handle_event(self, msg: WaylandMessage):
        """Handle events from the compositor."""
        decoder = MessageDecoder(msg.payload)

        if msg.opcode == RiverOutputV1.Event.REMOVED:
            print(f"[DEBUG] Output {self.object_id:x}: REMOVED event")
            self.removed = True
            if self.on_removed:
                self.on_removed()

        elif msg.opcode == RiverOutputV1.Event.WL_OUTPUT:
            self.wl_output_name = decoder.uint32()
            print(f"[DEBUG] Output {self.object_id:x}: WL_OUTPUT event, name={self.wl_output_name}")

        elif msg.opcode == RiverOutputV1.Event.POSITION:
            self.x = decoder.int32()
            self.y = decoder.int32()
            print(f"[DEBUG] Output {self.object_id:x}: POSITION event, pos=({self.x}, {self.y})")

        elif msg.opcode == RiverOutputV1.Event.DIMENSIONS:
            self.width = decoder.int32()
            self.height = decoder.int32()
            print(f"[DEBUG] Output {self.object_id:x}: DIMENSIONS event, size={self.width}x{self.height}")

    @property
    def area(self) -> Area:
        """Get the output area."""
        return Area(self.x, self.y, self.width, self.height)


class Seat(ProtocolObject):
    """Represents a seat (input devices + focus)."""

    def __init__(self, object_id: int, manager: 'WindowManager'):
        super().__init__(object_id, RiverSeatV1.INTERFACE)
        self.manager = manager

        self.wl_seat_name: Optional[int] = None
        self.removed = False

        # Pointer state
        self.pointer_window: Optional[Window] = None

        # Operation state
        self.op_dx: int = 0
        self.op_dy: int = 0
        self.op_released = False

        # Layer shell support
        self.layer_shell_seat: Optional['LayerShellSeat'] = None

        # Bindings
        self.pointer_bindings: Dict[int, 'PointerBinding'] = {}
        self.xkb_bindings: Dict[int, 'XkbBinding'] = {}

        # Callbacks
        self.on_removed: Optional[Callable[[], None]] = None
        self.on_pointer_enter: Optional[Callable[[Window], None]] = None
        self.on_pointer_leave: Optional[Callable[[], None]] = None
        self.on_window_interaction: Optional[Callable[[Window], None]] = None
        self.on_op_delta: Optional[Callable[[int, int], None]] = None
        self.on_op_release: Optional[Callable[[], None]] = None

    def handle_event(self, msg: WaylandMessage):
        """Handle events from the compositor."""
        decoder = MessageDecoder(msg.payload)

        if msg.opcode == RiverSeatV1.Event.REMOVED:
            self.removed = True
            if self.on_removed:
                self.on_removed()

        elif msg.opcode == RiverSeatV1.Event.WL_SEAT:
            self.wl_seat_name = decoder.uint32()

        elif msg.opcode == RiverSeatV1.Event.POINTER_ENTER:
            window_id = decoder.object_id()
            self.pointer_window = self.manager.windows.get(window_id)
            if self.on_pointer_enter and self.pointer_window:
                self.on_pointer_enter(self.pointer_window)

        elif msg.opcode == RiverSeatV1.Event.POINTER_LEAVE:
            self.pointer_window = None
            if self.on_pointer_leave:
                self.on_pointer_leave()

        elif msg.opcode == RiverSeatV1.Event.WINDOW_INTERACTION:
            window_id = decoder.object_id()
            window = self.manager.windows.get(window_id)
            if self.on_window_interaction and window:
                self.on_window_interaction(window)

        elif msg.opcode == RiverSeatV1.Event.OP_DELTA:
            self.op_dx = decoder.int32()
            self.op_dy = decoder.int32()
            if self.on_op_delta:
                self.on_op_delta(self.op_dx, self.op_dy)

        elif msg.opcode == RiverSeatV1.Event.OP_RELEASE:
            self.op_released = True
            if self.on_op_release:
                self.on_op_release()

    def focus_window(self, window: Window):
        """Focus a window (manage state)."""
        payload = MessageEncoder().object(window).bytes()
        self.manager.send_request(self.object_id, RiverSeatV1.Request.FOCUS_WINDOW, payload)

    def clear_focus(self):
        """Clear keyboard focus (manage state)."""
        self.manager.send_request(self.object_id, RiverSeatV1.Request.CLEAR_FOCUS)

    def op_start_pointer(self):
        """Start an interactive pointer operation (manage state)."""
        self.op_dx = 0
        self.op_dy = 0
        self.op_released = False
        self.manager.send_request(self.object_id, RiverSeatV1.Request.OP_START_POINTER)

    def op_end(self):
        """End an interactive operation (manage state)."""
        self.manager.send_request(self.object_id, RiverSeatV1.Request.OP_END)

    def get_pointer_binding(self, button: int, modifiers: Modifiers) -> 'PointerBinding':
        """Create a pointer binding."""
        binding_id = self.manager.connection.allocate_id()
        binding = PointerBinding(binding_id, self.manager, self, button, modifiers)
        self.pointer_bindings[binding_id] = binding
        self.manager.connection.register_object(binding)

        payload = (MessageEncoder()
                   .new_id(binding_id)
                   .uint32(button)
                   .uint32(modifiers.value)
                   .bytes())
        self.manager.send_request(self.object_id, RiverSeatV1.Request.GET_POINTER_BINDING, payload)
        return binding


class PointerBinding(ProtocolObject):
    """Represents a pointer binding."""

    def __init__(self, object_id: int, manager: 'WindowManager', seat: Seat,
                 button: int, modifiers: Modifiers):
        super().__init__(object_id, RiverPointerBindingV1.INTERFACE)
        self.manager = manager
        self.seat = seat
        self.button = button
        self.modifiers = modifiers
        self.enabled = False

        # Callbacks
        self.on_pressed: Optional[Callable[[], None]] = None
        self.on_released: Optional[Callable[[], None]] = None

    def handle_event(self, msg: WaylandMessage):
        """Handle events from the compositor."""
        if msg.opcode == RiverPointerBindingV1.Event.PRESSED:
            if self.on_pressed:
                self.on_pressed()
        elif msg.opcode == RiverPointerBindingV1.Event.RELEASED:
            if self.on_released:
                self.on_released()

    def enable(self):
        """Enable the binding (manage state)."""
        self.enabled = True
        self.manager.send_request(self.object_id, RiverPointerBindingV1.Request.ENABLE)

    def disable(self):
        """Disable the binding (manage state)."""
        self.enabled = False
        self.manager.send_request(self.object_id, RiverPointerBindingV1.Request.DISABLE)


class XkbBinding(ProtocolObject):
    """Represents an XKB key binding."""

    def __init__(self, object_id: int, manager: 'WindowManager', seat: Seat,
                 keysym: int, modifiers: Modifiers):
        super().__init__(object_id, RiverXkbBindingV1.INTERFACE)
        self.manager = manager
        self.seat = seat
        self.keysym = keysym
        self.modifiers = modifiers
        self.enabled = False
        self.layout_override: Optional[int] = None

        # Callbacks
        self.on_pressed: Optional[Callable[[], None]] = None
        self.on_released: Optional[Callable[[], None]] = None

    def handle_event(self, msg: WaylandMessage):
        """Handle events from the compositor."""
        if msg.opcode == RiverXkbBindingV1.Event.PRESSED:
            if self.on_pressed:
                self.on_pressed()
        elif msg.opcode == RiverXkbBindingV1.Event.RELEASED:
            if self.on_released:
                self.on_released()

    def set_layout_override(self, layout: int):
        """Set layout override (manage state)."""
        self.layout_override = layout
        payload = MessageEncoder().uint32(layout).bytes()
        self.manager.send_request(self.object_id, RiverXkbBindingV1.Request.SET_LAYOUT_OVERRIDE, payload)

    def enable(self):
        """Enable the binding (manage state)."""
        self.enabled = True
        self.manager.send_request(self.object_id, RiverXkbBindingV1.Request.ENABLE)

    def disable(self):
        """Disable the binding (manage state)."""
        self.enabled = False
        self.manager.send_request(self.object_id, RiverXkbBindingV1.Request.DISABLE)


class LayerShellOutput(ProtocolObject):
    """Represents layer shell output state."""

    def __init__(self, object_id: int, manager: 'WindowManager', output: Output):
        super().__init__(object_id, RiverLayerShellOutputV1.INTERFACE)
        self.manager = manager
        self.output = output
        output.layer_shell_output = self

        # Non-exclusive area
        self.non_exclusive_area = Area()

    def handle_event(self, msg: WaylandMessage):
        """Handle events from the compositor."""
        if msg.opcode == RiverLayerShellOutputV1.Event.NON_EXCLUSIVE_AREA:
            decoder = MessageDecoder(msg.payload)
            self.non_exclusive_area.x = decoder.int32()
            self.non_exclusive_area.y = decoder.int32()
            self.non_exclusive_area.width = decoder.int32()
            self.non_exclusive_area.height = decoder.int32()

    def set_default(self):
        """Set as default output for layer surfaces (manage state)."""
        self.manager.send_request(self.object_id, RiverLayerShellOutputV1.Request.SET_DEFAULT)


class LayerShellSeat(ProtocolObject):
    """Represents layer shell seat state."""

    def __init__(self, object_id: int, manager: 'WindowManager', seat: Seat):
        super().__init__(object_id, RiverLayerShellSeatV1.INTERFACE)
        self.manager = manager
        self.seat = seat
        seat.layer_shell_seat = self

        self.focus_exclusive = False
        self.focus_non_exclusive = False

        # Callbacks
        self.on_focus_exclusive: Optional[Callable[[], None]] = None
        self.on_focus_non_exclusive: Optional[Callable[[], None]] = None
        self.on_focus_none: Optional[Callable[[], None]] = None

    def handle_event(self, msg: WaylandMessage):
        """Handle events from the compositor."""
        if msg.opcode == RiverLayerShellSeatV1.Event.FOCUS_EXCLUSIVE:
            self.focus_exclusive = True
            self.focus_non_exclusive = False
            if self.on_focus_exclusive:
                self.on_focus_exclusive()

        elif msg.opcode == RiverLayerShellSeatV1.Event.FOCUS_NON_EXCLUSIVE:
            self.focus_exclusive = False
            self.focus_non_exclusive = True
            if self.on_focus_non_exclusive:
                self.on_focus_non_exclusive()

        elif msg.opcode == RiverLayerShellSeatV1.Event.FOCUS_NONE:
            self.focus_exclusive = False
            self.focus_non_exclusive = False
            if self.on_focus_none:
                self.on_focus_none()
