"""
Test script for tabbed layout functionality.

This script tests:
1. Switching to tabbed layout
2. Opening multiple windows
3. Tab cycling with Alt+Tab
4. IPC queries for tab information
"""

import socket
import struct
import json
import time
import os
import subprocess
import sys


def send_ipc_message(msg_type, payload=""):
    """Send message to pwm IPC socket."""
    runtime_dir = os.getenv("XDG_RUNTIME_DIR", "/tmp")
    wayland_display = os.getenv("WAYLAND_DISPLAY", "wayland-0")
    socket_path = f"{runtime_dir}/pwm-{wayland_display}.sock"

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(socket_path)

        # Send message
        data = payload.encode("utf-8") if payload else b""
        magic = b"i3-ipc"
        header = magic + struct.pack("<II", len(data), msg_type)
        sock.send(header + data)

        # Receive response
        header = sock.recv(14)
        if len(header) < 14:
            return None

        magic_resp = header[:6]
        if magic_resp != magic:
            return None

        length, resp_type = struct.unpack("<II", header[6:])
        response = b""
        while len(response) < length:
            chunk = sock.recv(length - len(response))
            if not chunk:
                break
            response += chunk

        sock.close()
        return json.loads(response.decode("utf-8"))
    except Exception as e:
        print(f"IPC Error: {e}")
        return None


def get_workspaces():
    """Get workspace information."""
    return send_ipc_message(1)  # GET_WORKSPACES


def main():
    print("Testing Tabbed Layout")
    print("=" * 50)

    # Wait for IPC to be available
    print("\nWaiting for IPC server...")
    time.sleep(2)

    # Get initial workspace state
    print("\n1. Initial workspace state:")
    workspaces = get_workspaces()
    if workspaces:
        for ws in workspaces:
            if ws.get("focused"):
                print(f"  Workspace {ws['num']}: {ws['name']}")
                print(f"    Layout: {ws.get('layout', 'unknown')}")
                print(f"    Tabs: {ws.get('tabs', {})}")
    else:
        print("  ERROR: Could not get workspace information")
        return 1

    # TODO: Switch to tabbed layout (would require riverctl or keybinding)
    # For now, user must manually press Alt+Space to cycle to tabbed layout

    print("\n2. Manual testing instructions:")
    print("  a. Press Alt+Space multiple times to cycle to 'tabbed' layout")
    print("  b. Press Alt+Return to open terminal windows (open 3-4)")
    print("  c. Press Alt+Tab to cycle through tabs")
    print("  d. Press Alt+Shift+Tab to cycle backwards")
    print("  e. Observe:")
    print("     - Tab bar appears at top of windows")
    print("     - Only focused tab content is visible")
    print("     - Tab titles show window names")
    print("     - Focused tab has different background color")

    print("\n3. Monitoring workspace changes...")
    for i in range(10):
        time.sleep(1)
        workspaces = get_workspaces()
        if workspaces:
            for ws in workspaces:
                if ws.get("focused"):
                    layout = ws.get("layout", "unknown")
                    tabs = ws.get("tabs", {})
                    if tabs.get("is_tabbed"):
                        print(
                            f"\n  [Tabbed] {tabs['tab_count']} tabs, focused: {tabs['focused_tab_index']}"
                        )
                    elif i == 0:
                        print(f"  Current layout: {layout}")

    print("\n\nTest completed. Check for any TabDecoration errors in logs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
