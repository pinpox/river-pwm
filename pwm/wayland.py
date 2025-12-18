"""
Core Wayland Protocol Implementations

Provides implementations for wl_compositor, wl_surface, wl_shm, wl_shm_pool,
and wl_buffer protocols.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from .protocol import ProtocolObject, MessageEncoder

if TYPE_CHECKING:
    from .connection import WaylandConnection


class WlCompositor(ProtocolObject):
    """wl_compositor protocol object."""

    # Opcodes
    CREATE_SURFACE = 0
    CREATE_REGION = 1

    def __init__(self, object_id: int, connection: WaylandConnection):
        super().__init__(object_id, "wl_compositor")
        self.connection = connection

    def create_surface(self) -> WlSurface:
        """Create a new surface."""
        surface_id = self.connection.allocate_id()
        surface = WlSurface(surface_id, self.connection)
        self.connection.register_object(surface)

        # Send create_surface request
        encoder = MessageEncoder()
        encoder.new_id(surface_id)
        self.connection.send_message(
            self.object_id, self.CREATE_SURFACE, encoder.data
        )

        return surface


class WlSurface(ProtocolObject):
    """wl_surface protocol object."""

    # Opcodes
    DESTROY = 0
    ATTACH = 1
    DAMAGE = 2
    FRAME = 3
    SET_OPAQUE_REGION = 4
    SET_INPUT_REGION = 5
    COMMIT = 6
    SET_BUFFER_TRANSFORM = 7
    SET_BUFFER_SCALE = 8
    DAMAGE_BUFFER = 9

    def __init__(self, object_id: int, connection: WaylandConnection):
        super().__init__(object_id, "wl_surface")
        self.connection = connection

    def attach(self, buffer: Optional[WlBuffer], x: int = 0, y: int = 0):
        """Attach a buffer to the surface."""
        encoder = MessageEncoder()
        encoder.object(buffer)  # Can be None
        encoder.int32(x).int32(y)
        self.connection.send_message(self.object_id, self.ATTACH, encoder.data)

    def damage(self, x: int, y: int, width: int, height: int):
        """Mark a region as damaged (surface coordinates)."""
        encoder = MessageEncoder()
        encoder.int32(x).int32(y).int32(width).int32(height)
        self.connection.send_message(self.object_id, self.DAMAGE, encoder.data)

    def damage_buffer(self, x: int, y: int, width: int, height: int):
        """Mark a region as damaged (buffer coordinates)."""
        encoder = MessageEncoder()
        encoder.int32(x).int32(y).int32(width).int32(height)
        self.connection.send_message(self.object_id, self.DAMAGE_BUFFER, encoder.data)

    def commit(self):
        """Commit the surface state."""
        self.connection.send_message(self.object_id, self.COMMIT)

    def destroy_request(self):
        """Send destroy request."""
        self.connection.send_message(self.object_id, self.DESTROY)
        self.destroy()


class WlShm(ProtocolObject):
    """wl_shm protocol object."""

    # Opcodes
    CREATE_POOL = 0

    # Events
    FORMAT = 0

    # Formats
    FORMAT_ARGB8888 = 0
    FORMAT_XRGB8888 = 1

    def __init__(self, object_id: int, connection: WaylandConnection):
        super().__init__(object_id, "wl_shm")
        self.connection = connection

    def create_pool(self, fd: int, size: int) -> WlShmPool:
        """Create a shared memory pool."""
        pool_id = self.connection.allocate_id()
        pool = WlShmPool(pool_id, self.connection)
        self.connection.register_object(pool)

        # Send create_pool request with file descriptor
        encoder = MessageEncoder()
        encoder.new_id(pool_id)
        encoder.fd(fd)
        encoder.int32(size)

        # Extract FDs from encoder if present
        fds = getattr(encoder, 'fds', None)
        self.connection.send_message(self.object_id, self.CREATE_POOL, encoder.data, fds=fds)

        return pool


class WlShmPool(ProtocolObject):
    """wl_shm_pool protocol object."""

    # Opcodes
    CREATE_BUFFER = 0
    DESTROY = 1
    RESIZE = 2

    def __init__(self, object_id: int, connection: WaylandConnection):
        super().__init__(object_id, "wl_shm_pool")
        self.connection = connection

    def create_buffer(
        self, offset: int, width: int, height: int, stride: int, format: int
    ) -> WlBuffer:
        """Create a buffer from the pool."""
        buffer_id = self.connection.allocate_id()
        buffer = WlBuffer(buffer_id, self.connection)
        self.connection.register_object(buffer)

        # Send create_buffer request
        encoder = MessageEncoder()
        encoder.new_id(buffer_id)
        encoder.int32(offset)
        encoder.int32(width)
        encoder.int32(height)
        encoder.int32(stride)
        encoder.uint32(format)
        self.connection.send_message(self.object_id, self.CREATE_BUFFER, encoder.data)

        return buffer

    def resize(self, size: int):
        """Resize the pool."""
        encoder = MessageEncoder()
        encoder.int32(size)
        self.connection.send_message(self.object_id, self.RESIZE, encoder.data)

    def destroy_request(self):
        """Send destroy request."""
        self.connection.send_message(self.object_id, self.DESTROY)
        self.destroy()


class WlBuffer(ProtocolObject):
    """wl_buffer protocol object."""

    # Opcodes
    DESTROY = 0

    # Events
    RELEASE = 0

    def __init__(self, object_id: int, connection: WaylandConnection):
        super().__init__(object_id, "wl_buffer")
        self.connection = connection

    def destroy_request(self):
        """Send destroy request."""
        self.connection.send_message(self.object_id, self.DESTROY)
        self.destroy()
