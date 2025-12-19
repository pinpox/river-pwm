"""
Shared Memory Management for Wayland

Provides ShmPool class for managing shared memory buffers used by Wayland
to pass rendered content to the compositor.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional
import os
import mmap

from .wayland import WlShm, WlShmPool, WlBuffer

if TYPE_CHECKING:
    from .connection import WaylandConnection

# MFD_CLOEXEC constant (may not be available on all systems)
MFD_CLOEXEC = getattr(os, "MFD_CLOEXEC", 0x0001)


class ShmPool:
    """Manages a shared memory pool for Wayland buffer allocation."""

    def __init__(self, connection: WaylandConnection, size: int):
        """Create a new shared memory pool.

        Args:
            connection: Wayland connection
            size: Size of the shared memory pool in bytes
        """
        self.connection = connection
        self.size = size

        # Create anonymous file descriptor using memfd_create
        self.fd = os.memfd_create("pwm-shm", MFD_CLOEXEC)

        # Set file size
        os.ftruncate(self.fd, size)

        # Memory map the file
        self.mmap = mmap.mmap(
            self.fd, size, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE
        )

        # Get wl_shm object from connection
        if self.connection.shm_id is None:
            raise RuntimeError("wl_shm not bound")

        wl_shm = WlShm(self.connection.shm_id, self.connection)

        # Create wl_shm_pool
        self.pool = wl_shm.create_pool(self.fd, size)

    def create_buffer(
        self, offset: int, width: int, height: int, stride: int, format: int
    ) -> WlBuffer:
        """Create a buffer from the pool.

        Args:
            offset: Offset into the pool in bytes
            width: Buffer width in pixels
            height: Buffer height in pixels
            stride: Number of bytes per row
            format: Pixel format (e.g., WlShm.FORMAT_ARGB8888)

        Returns:
            WlBuffer object
        """
        return self.pool.create_buffer(offset, width, height, stride, format)

    def get_data(self, offset: int = 0, size: Optional[int] = None) -> memoryview:
        """Get a memoryview for writing to the pool.

        Args:
            offset: Offset into the pool
            size: Number of bytes (default: entire pool from offset)

        Returns:
            memoryview for writing
        """
        if size is None:
            size = self.size - offset
        return memoryview(self.mmap)[offset : offset + size]

    def resize(self, new_size: int):
        """Resize the shared memory pool.

        Args:
            new_size: New size in bytes
        """
        # Unmap current mapping
        self.mmap.close()

        # Resize file
        os.ftruncate(self.fd, new_size)

        # Create new mapping
        self.mmap = mmap.mmap(
            self.fd,
            new_size,
            flags=mmap.MAP_SHARED,
            prot=mmap.PROT_READ | mmap.PROT_WRITE,
        )

        # Tell wl_shm_pool about the resize
        self.pool.resize(new_size)

        self.size = new_size

    def destroy(self):
        """Clean up the pool."""
        if hasattr(self, "pool"):
            self.pool.destroy_request()

        if hasattr(self, "mmap"):
            self.mmap.close()

        if hasattr(self, "fd"):
            os.close(self.fd)
