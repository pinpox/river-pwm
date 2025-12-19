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
        readable, _, _ = select.select(
            [self.server_socket] + self.clients, [], [], 0
        )

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
                print(f"IPC: Invalid magic bytes: {magic}")
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
        if client in self.clients:
            self.clients.remove(client)
        if client in self.subscribers:
            del self.subscribers[client]
        try:
            client.close()
        except:
            pass
        print(f"IPC: Client disconnected (total: {len(self.clients)})")

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
        try:
            if msg_type == MessageType.GET_WORKSPACES:
                return self._get_workspaces()
            elif msg_type == MessageType.GET_OUTPUTS:
                return self._get_outputs()
            elif msg_type == MessageType.GET_VERSION:
                return self._get_version()
            elif msg_type == MessageType.GET_TREE:
                return self._get_tree()
            elif msg_type == MessageType.SUBSCRIBE:
                events = json.loads(payload.decode("utf-8"))
                self.subscribers[client] = events
                print(f"IPC: Client subscribed to events: {events}")
                return {"success": True}
            elif msg_type == MessageType.RUN_COMMAND:
                # TODO: Implement command execution
                return [{"success": False, "error": "RUN_COMMAND not yet implemented"}]
            else:
                return [{"success": False, "error": f"Unknown message type: {msg_type}"}]
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
        workspaces = []

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
            if ws:
                is_active = num == active_num
                workspaces.append(
                    {
                        "num": num,
                        "name": ws.name,
                        "visible": is_active,
                        "focused": is_active,
                        "urgent": False,
                        "rect": {
                            "x": output.x,
                            "y": output.y,
                            "width": output.width,
                            "height": output.height,
                        },
                        "output": output.wl_output_name or "unknown",
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
            current_ws = (
                active_workspace.name if active_workspace else "1"
            )

            outputs.append(
                {
                    "name": output.wl_output_name or "unknown",
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
        """Get window tree in i3 format.

        Returns:
            Tree dictionary
        """
        # Simplified tree structure - just list windows
        windows = []

        for window in self.wm.manager.windows.values():
            if window.is_visible:
                windows.append(
                    {
                        "id": window.object_id,
                        "name": window.title or "unknown",
                        "type": "con",
                        "focused": window == self.wm.focused_window,
                        "rect": {
                            "x": window.node.x if window.node else 0,
                            "y": window.node.y if window.node else 0,
                            "width": window.width,
                            "height": window.height,
                        },
                        "window_properties": {
                            "title": window.title,
                            "class": window.app_id,
                        },
                    }
                )

        return {
            "id": 0,
            "name": "root",
            "type": "root",
            "nodes": [
                {
                    "id": 1,
                    "name": "workspace",
                    "type": "workspace",
                    "nodes": windows,
                }
            ],
        }

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
