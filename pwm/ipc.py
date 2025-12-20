"""
i3-compatible IPC Server for pwm

Implements the i3/sway IPC protocol to allow external programs like
Waybar, i3status, etc. to query window manager state and subscribe to events.

Protocol documentation: https://i3wm.org/docs/ipc.html
"""

from __future__ import annotations
import socket
import struct
import json
import select
import os
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple, Optional, Any, Dict

if TYPE_CHECKING:
    from .riverwm import RiverWM


class MessageType(IntEnum):
    """i3 IPC message types."""

    RUN_COMMAND = 0
    GET_WORKSPACES = 1
    SUBSCRIBE = 2
    GET_OUTPUTS = 3
    GET_TREE = 4
    GET_MARKS = 5
    GET_BAR_CONFIG = 6
    GET_VERSION = 7
    GET_BINDING_MODES = 8
    GET_CONFIG = 9
    SEND_TICK = 10
    SYNC = 11
    GET_BINDING_STATE = 12


class EventType(IntEnum):
    """i3 IPC event types (with high bit set)."""

    WORKSPACE = 0x80000000
    OUTPUT = 0x80000001
    MODE = 0x80000002
    WINDOW = 0x80000003
    BARCONFIG_UPDATE = 0x80000004
    BINDING = 0x80000005
    SHUTDOWN = 0x80000006
    TICK = 0x80000007


class IPCServer:
    """
    i3-compatible IPC server for pwm.

    Allows external programs to query WM state and subscribe to events.
    """

    MAGIC = b"i3-ipc"

    def __init__(self, wm: "RiverWM"):
        """Initialize the IPC server.

        Args:
            wm: RiverWM instance to query state from
        """
        self.wm = wm
        self.socket_path = self._get_socket_path()
        self.server_socket: Optional[socket.socket] = None
        self.clients: List[socket.socket] = []
        # Map client socket to list of subscribed event type names
        self.subscribers: Dict[socket.socket, List[str]] = {}

        # Subscribe to window manager events for IPC broadcasting
        self._setup_event_subscriptions()

    def _setup_event_subscriptions(self):
        """Subscribe to window manager events for IPC broadcasting.

        When window manager events occur, IPC broadcasts them to
        subscribed clients in i3/sway format.
        """
        from pubsub import pub
        from . import topics

        # Workspace events -> Broadcast to IPC clients
        pub.subscribe(self._on_workspace_switched, topics.WORKSPACE_SWITCHED)

        # Window events -> Broadcast to IPC clients
        pub.subscribe(self._on_window_created, topics.WINDOW_CREATED)
        pub.subscribe(self._on_window_closed, topics.WINDOW_CLOSED)

    def _on_workspace_switched(self, current_workspace, old_workspace, output_name):
        """Handle workspace switched event.

        Args:
            current_workspace: New workspace number
            old_workspace: Previous workspace number
            output_name: Name of the output
        """
        # Broadcast to IPC clients in i3 format
        self.broadcast_event(
            "workspace",
            {
                "change": "focus",
                "current": {
                    "num": current_workspace,
                    "name": str(current_workspace),
                    "visible": True,
                    "focused": True,
                    "output": output_name,
                },
                "old": {
                    "num": old_workspace,
                    "name": str(old_workspace),
                    "visible": False,
                    "focused": False,
                    "output": output_name,
                },
            },
        )

    def _on_window_created(self, window):
        """Handle window created event.

        Args:
            window: The created window
        """
        # TODO: Broadcast window creation event to IPC clients
        pass

    def _on_window_closed(self, window):
        """Handle window closed event.

        Args:
            window: The closed window
        """
        # TODO: Broadcast window close event to IPC clients
        pass

    def _get_socket_path(self) -> Path:
        """Get the Unix socket path for IPC.

        Returns:
            Path to socket file
        """
        runtime_dir = os.getenv("XDG_RUNTIME_DIR", "/tmp")
        wayland_display = os.getenv("WAYLAND_DISPLAY", "wayland-0")
        return Path(runtime_dir) / f"pwm-{wayland_display}.sock"

    def start(self):
        """Start the IPC server and listen for connections."""
        # Remove existing socket if present
        if self.socket_path.exists():
            self.socket_path.unlink()

        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(str(self.socket_path))
        self.server_socket.listen(10)
        self.server_socket.setblocking(False)

        print(f"IPC server listening on {self.socket_path}")

    def poll(self):
        """Poll for new connections and messages.

        Should be called regularly from the main event loop.
        """
        if not self.server_socket:
            return

        # Check for readable sockets
        readable, _, _ = select.select([self.server_socket] + self.clients, [], [], 0)

        for sock in readable:
            if sock == self.server_socket:
                self._accept_client()
            else:
                self._handle_client(sock)

    def _accept_client(self):
        """Accept a new client connection."""
        try:
            client, _ = self.server_socket.accept()
            client.setblocking(False)
            self.clients.append(client)
            print(f"IPC: New client connected (total: {len(self.clients)})")
        except Exception as e:
            print(f"IPC: Error accepting client: {e}")

    def _handle_client(self, client: socket.socket):
        """Handle a message from a client.

        Args:
            client: Client socket
        """
        try:
            # Read header (14 bytes: 6 magic + 4 length + 4 type)
            header = client.recv(14)
            if len(header) < 14:
                self._remove_client(client)
                return

            magic = header[:6]
            if magic != self.MAGIC:
                print(f"IPC: Invalid magic bytes: {magic!r}")
                self._remove_client(client)
                return

            length, msg_type = struct.unpack("<II", header[6:])

            # Read payload
            payload = b""
            while len(payload) < length:
                chunk = client.recv(length - len(payload))
                if not chunk:
                    self._remove_client(client)
                    return
                payload += chunk

            # Handle message and send response
            response = self._handle_message(client, msg_type, payload)
            self._send_message(client, msg_type, response)

        except BlockingIOError:
            # No data available, try again later
            pass
        except Exception as e:
            print(f"IPC: Error handling client: {e}")
            self._remove_client(client)

    def _remove_client(self, client: socket.socket):
        """Remove and close a client connection.

        Args:
            client: Client socket to remove
        """
        was_subscriber = client in self.subscribers
        if client in self.clients:
            self.clients.remove(client)
        if client in self.subscribers:
            del self.subscribers[client]
        try:
            client.close()
        except:
            pass
        print(
            f"IPC: Client disconnected (total: {len(self.clients)}, subscribers: {len(self.subscribers)}, was_subscriber: {was_subscriber})"
        )

    def _handle_message(
        self, client: socket.socket, msg_type: int, payload: bytes
    ) -> Any:
        """Process an IPC message and return response.

        Args:
            client: Client socket
            msg_type: Message type code
            payload: Message payload bytes

        Returns:
            Response data (will be JSON encoded)
        """
        print(f"IPC: Received message type {msg_type}")
        try:
            if msg_type == MessageType.GET_WORKSPACES:
                print(f"IPC: GET_WORKSPACES request")
                result = self._get_workspaces()
                print(f"IPC: Returning {len(result)} workspaces")
                return result
            elif msg_type == MessageType.GET_OUTPUTS:
                print(f"IPC: GET_OUTPUTS request")
                return self._get_outputs()
            elif msg_type == MessageType.GET_VERSION:
                return self._get_version()
            elif msg_type == MessageType.GET_TREE:
                print(f"IPC: GET_TREE request")
                tree_result: Dict[str, Any] = self._get_tree()
                nodes = tree_result.get("nodes", [])
                if isinstance(nodes, list):
                    print(f"IPC: Returning tree with {len(nodes)} nodes")
                return tree_result
            elif msg_type == MessageType.SUBSCRIBE:
                events = json.loads(payload.decode("utf-8"))
                # Add to existing subscriptions rather than replacing
                if client in self.subscribers:
                    # Merge with existing subscriptions
                    existing = set(self.subscribers[client])
                    new_events = set(events)
                    self.subscribers[client] = list(existing | new_events)
                    print(
                        f"IPC: Client added subscriptions {events}, now subscribed to: {self.subscribers[client]}"
                    )
                else:
                    self.subscribers[client] = events
                    print(f"IPC: Client subscribed to events: {events}")
                print(f"IPC: Total subscribers now: {len(self.subscribers)}")
                return {"success": True}
            elif msg_type == MessageType.RUN_COMMAND:
                command = payload.decode("utf-8").strip()
                print(f"IPC: RUN_COMMAND request: {command}")
                return self._run_command(command)
            else:
                return [
                    {"success": False, "error": f"Unknown message type: {msg_type}"}
                ]
        except Exception as e:
            print(f"IPC: Error handling message type {msg_type}: {e}")
            return [{"success": False, "error": str(e)}]

    def _send_message(self, client: socket.socket, msg_type: int, payload: Any):
        """Send a message to a client in i3 IPC format.

        Args:
            client: Client socket
            msg_type: Message type code
            payload: Payload data (will be JSON encoded)
        """
        try:
            data = json.dumps(payload).encode("utf-8")
            header = self.MAGIC + struct.pack("<II", len(data), msg_type)
            client.send(header + data)
        except Exception as e:
            print(f"IPC: Error sending message: {e}")
            self._remove_client(client)

    def _get_workspaces(self) -> List[Dict[str, Any]]:
        """Get list of workspaces in i3 format.

        Returns:
            List of workspace dictionaries
        """
        workspaces: List[Dict[str, Any]] = []

        if not self.wm.focused_output:
            return workspaces

        output = self.wm.focused_output
        active_workspace = self.wm.layout_manager.get_active_workspace(output)
        active_num = (
            self.wm.layout_manager.active_workspace.get(output.object_id, 1)
            if active_workspace
            else 1
        )

        for num in range(1, self.wm.config.num_workspaces + 1):
            ws = self.wm.layout_manager.workspaces.get(output.object_id, {}).get(num)
            is_active = num == active_num

            # Add layout and tab information
            layout_name = ws.layout.name if ws and ws.layout else "tile-right"
            tab_info: Dict[str, Any] = {}
            if ws and ws.layout and ws.layout.name == "tabbed":
                focused_idx = 0
                if ws.focused_window and ws.focused_window in ws.windows:
                    focused_idx = ws.windows.index(ws.focused_window)

                tab_info = {
                    "is_tabbed": True,
                    "tab_count": len(ws.windows),
                    "focused_tab_index": focused_idx,
                }
            else:
                tab_info = {"is_tabbed": False}

            # Always return all workspaces, even if not yet initialized
            workspaces.append(
                {
                    "num": num,
                    "name": ws.name if ws else str(num),
                    "visible": is_active,
                    "focused": is_active,
                    "urgent": False,
                    "rect": {
                        "x": output.x,
                        "y": output.y,
                        "width": output.width,
                        "height": output.height,
                    },
                    "output": (
                        f"output-{output.wl_output_name}"
                        if output.wl_output_name
                        else "unknown"
                    ),
                    "layout": layout_name,
                    "tabs": tab_info,
                }
            )

        return workspaces

    def _get_outputs(self) -> List[Dict[str, Any]]:
        """Get list of outputs in i3 format.

        Returns:
            List of output dictionaries
        """
        outputs = []

        for output in self.wm.manager.outputs.values():
            active_workspace = self.wm.layout_manager.get_active_workspace(output)
            current_ws = active_workspace.name if active_workspace else "1"

            outputs.append(
                {
                    "name": (
                        f"output-{output.wl_output_name}"
                        if output.wl_output_name
                        else "unknown"
                    ),
                    "active": True,
                    "current_workspace": current_ws,
                    "rect": {
                        "x": output.x,
                        "y": output.y,
                        "width": output.width,
                        "height": output.height,
                    },
                }
            )

        return outputs

    def _get_tree(self) -> Dict[str, Any]:
        """Get window tree in i3/Sway format with outputs and workspaces.

        Returns:
            Tree dictionary matching Sway's structure
        """
        output_nodes = []

        # Build tree for each output
        for output in self.wm.manager.outputs.values():
            workspace_nodes = []
            active_num = self.wm.layout_manager.active_workspace.get(
                output.object_id, 1
            )

            # Create nodes for all configured workspaces
            for num in range(1, self.wm.config.num_workspaces + 1):
                ws = self.wm.layout_manager.workspaces.get(output.object_id, {}).get(
                    num
                )
                is_focused = num == active_num

                # Get windows for this workspace
                window_nodes: List[Dict[str, Any]] = []
                if ws:
                    for window in ws.windows:
                        window_nodes.append(
                            {
                                "id": window.object_id,
                                "name": window.title or "unknown",
                                "type": "con",
                                "focused": window == self.wm.focused_window,
                            }
                        )

                # Add workspace node
                workspace_nodes.append(
                    {
                        "id": 1000 + num,
                        "num": num,
                        "name": ws.name if ws else str(num),
                        "type": "workspace",
                        "focused": is_focused,
                        "visible": is_focused,
                        "urgent": False,
                        "output": (
                            f"output-{output.wl_output_name}"
                            if output.wl_output_name
                            else "unknown"
                        ),
                        "nodes": window_nodes,
                    }
                )

            # Create output node containing workspaces
            output_nodes.append(
                {
                    "id": output.object_id,
                    "name": (
                        f"output-{output.wl_output_name}"
                        if output.wl_output_name
                        else "unknown"
                    ),
                    "type": "output",
                    "active": True,
                    "nodes": workspace_nodes,
                    "floating_nodes": [],  # Required by Waybar
                }
            )

        return {
            "id": 0,
            "name": "root",
            "type": "root",
            "nodes": output_nodes,
        }

    def _run_command(self, command: str) -> List[Dict[str, Any]]:
        """Execute a command by publishing it to the event bus.

        Args:
            command: Command string to execute

        Returns:
            List with command result
        """
        from pubsub import pub
        from . import topics

        # Parse workspace switching commands
        # Waybar sends: workspace "X" or workspace X or workspace number X
        parts = command.split()

        if len(parts) >= 2 and parts[0] == "workspace":
            # Extract workspace number (last part, strip quotes)
            ws_num_str = parts[-1].strip("\"'")
            try:
                ws_num = int(ws_num_str)
                if 1 <= ws_num <= self.wm.config.num_workspaces:
                    # Publish command event instead of calling directly
                    print(
                        f"IPC: Publishing CMD_SWITCH_WORKSPACE for workspace {ws_num}"
                    )
                    pub.sendMessage(topics.CMD_SWITCH_WORKSPACE, workspace_id=ws_num)
                    return [{"success": True}]
                else:
                    return [
                        {
                            "success": False,
                            "error": f"Invalid workspace number: {ws_num}",
                        }
                    ]
            except ValueError:
                return [
                    {
                        "success": False,
                        "error": f"Invalid workspace number: {ws_num_str}",
                    }
                ]

        # Map other i3/sway commands to our command events
        command_map = {
            "kill": topics.CMD_CLOSE_WINDOW,
            "fullscreen": topics.CMD_TOGGLE_FULLSCREEN,
            "focus next": topics.CMD_FOCUS_NEXT,
            "focus prev": topics.CMD_FOCUS_PREV,
            "swap next": topics.CMD_SWAP_NEXT,
            "swap prev": topics.CMD_SWAP_PREV,
            "layout toggle": topics.CMD_CYCLE_LAYOUT,
        }

        if command in command_map:
            print(f"IPC: Publishing {command_map[command]} for command: {command}")
            pub.sendMessage(command_map[command])
            return [{"success": True}]

        # Unknown command
        return [{"success": False, "error": f"Unknown command: {command}"}]

    def _get_version(self) -> Dict[str, Any]:
        """Get version info in i3 format.

        Returns:
            Version dictionary
        """
        return {
            "human_readable": "pwm 0.1.0",
            "loaded_config_file_name": "",
            "minor": 1,
            "patch": 0,
            "major": 0,
        }

    def broadcast_event(self, event_name: str, payload: Dict[str, Any]):
        """Broadcast an event to all subscribed clients.

        Args:
            event_name: Event name (e.g., "workspace", "window")
            payload: Event payload data
        """
        # Map event name to event type code
        event_map = {
            "workspace": EventType.WORKSPACE,
            "output": EventType.OUTPUT,
            "window": EventType.WINDOW,
            "mode": EventType.MODE,
        }

        event_type = event_map.get(event_name)
        if not event_type:
            print(f"IPC: Unknown event type: {event_name}")
            return

        # Count subscribers for this event
        subscriber_count = sum(
            1 for subs in self.subscribers.values() if event_name in subs
        )
        print(f"IPC: Broadcasting {event_name} event to {subscriber_count} subscribers")
        if event_name == "workspace":
            print(
                f"IPC: Workspace event: {payload.get('change')} - current={payload.get('current', {}).get('num')}, old={payload.get('old', {}).get('num')}"
            )

        # Send to all subscribed clients
        for client, subscribed_events in list(self.subscribers.items()):
            if event_name in subscribed_events:
                try:
                    self._send_message(client, event_type, payload)
                except:
                    self._remove_client(client)

    def stop(self):
        """Stop the IPC server and close all connections."""
        # Close all client connections
        for client in list(self.clients):
            self._remove_client(client)

        # Close server socket
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None

        # Remove socket file
        if self.socket_path.exists():
            self.socket_path.unlink()

        print("IPC server stopped")
