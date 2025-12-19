#!/usr/bin/env python3
"""Test IPC workspace query."""
import socket
import struct
import json
import os
from pathlib import Path

# Get socket path
runtime_dir = os.getenv("XDG_RUNTIME_DIR", "/tmp")
wayland_display = os.getenv("WAYLAND_DISPLAY", "wayland-0")
socket_path = Path(runtime_dir) / f"pwm-{wayland_display}.sock"

print(f"Connecting to: {socket_path}")

if not socket_path.exists():
    print(f"ERROR: Socket does not exist!")
    exit(1)

# Connect to IPC
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect(str(socket_path))

# Send GET_WORKSPACES request (type 1)
MAGIC = b"i3-ipc"
msg_type = 1  # GET_WORKSPACES
payload = b""
length = len(payload)

header = MAGIC + struct.pack("<II", length, msg_type)
sock.send(header + payload)

# Receive response
header = sock.recv(14)
magic = header[:6]
length, response_type = struct.unpack("<II", header[6:])

print(f"Response type: {response_type}, length: {length}")

# Read payload
data = sock.recv(length)
workspaces = json.loads(data.decode("utf-8"))

print(f"\nReceived {len(workspaces)} workspaces:")
print(json.dumps(workspaces, indent=2))

sock.close()
