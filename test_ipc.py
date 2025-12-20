"""
Test script for pwm IPC server.

This script demonstrates how to connect to pwm's IPC server
and query workspace information.
"""

import socket
import struct
import json
import os
from pathlib import Path


def get_socket_path():
    """Get the IPC socket path."""
    runtime_dir = os.getenv("XDG_RUNTIME_DIR", "/tmp")
    wayland_display = os.getenv("WAYLAND_DISPLAY", "wayland-0")
    return Path(runtime_dir) / f"pwm-{wayland_display}.sock"


def send_message(sock, msg_type, payload=""):
    """Send an i3 IPC message."""
    magic = b"i3-ipc"
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    header = magic + struct.pack("<II", len(data), msg_type)
    sock.send(header + data)


def recv_message(sock):
    """Receive an i3 IPC message."""
    # Read header
    header = sock.recv(14)
    if len(header) < 14:
        return None, None

    magic = header[:6]
    if magic != b"i3-ipc":
        print(f"Invalid magic: {magic}")
        return None, None

    length, msg_type = struct.unpack("<II", header[6:])

    # Read payload
    payload = b""
    while len(payload) < length:
        chunk = sock.recv(length - len(payload))
        if not chunk:
            return None, None
        payload += chunk

    return msg_type, json.loads(payload.decode("utf-8"))


def main():
    """Main test function."""
    socket_path = get_socket_path()

    print(f"Connecting to pwm IPC at {socket_path}...")

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(socket_path))
        print("Connected!")

        # Test GET_VERSION (type 7)
        print("\n=== Testing GET_VERSION ===")
        send_message(sock, 7)
        msg_type, response = recv_message(sock)
        print(f"Response: {json.dumps(response, indent=2)}")

        # Test GET_WORKSPACES (type 1)
        print("\n=== Testing GET_WORKSPACES ===")
        send_message(sock, 1)
        msg_type, response = recv_message(sock)
        print(f"Workspaces:")
        for ws in response:
            status = (
                "FOCUSED" if ws["focused"] else "visible" if ws["visible"] else "hidden"
            )
            print(f"  [{status}] Workspace {ws['num']}: {ws['name']} on {ws['output']}")

        # Test GET_OUTPUTS (type 3)
        print("\n=== Testing GET_OUTPUTS ===")
        send_message(sock, 3)
        msg_type, response = recv_message(sock)
        print(f"Outputs:")
        for output in response:
            print(
                f"  {output['name']}: {output['rect']['width']}x{output['rect']['height']} (workspace: {output['current_workspace']})"
            )

        # Test SUBSCRIBE (type 2)
        print("\n=== Testing SUBSCRIBE (workspace events) ===")
        print("Subscribing to workspace events... Switch workspaces to see events!")
        print("Press Ctrl+C to stop.")

        subscribe_payload = json.dumps(["workspace"])
        send_message(sock, 2, subscribe_payload)
        msg_type, response = recv_message(sock)
        print(f"Subscribe response: {response}")

        # Listen for events
        while True:
            msg_type, event = recv_message(sock)
            if msg_type == 0x80000000:  # WORKSPACE event
                print(f"\nWorkspace event: {event['change']}")
                print(f"  From: Workspace {event['old']['num']}")
                print(f"  To:   Workspace {event['current']['num']}")

    except FileNotFoundError:
        print(f"Error: Socket not found at {socket_path}")
        print("Make sure pwm is running!")
    except ConnectionRefusedError:
        print(f"Error: Connection refused to {socket_path}")
        print("Make sure pwm is running!")
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        sock.close()


if __name__ == "__main__":
    main()
