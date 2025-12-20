"""
Unit tests for Wayland protocol encoding/decoding.
"""

import pytest
from pwm.protocol import (
    MessageEncoder,
    MessageDecoder,
    Area,
    Position,
    WindowEdges,
    Modifiers,
)


@pytest.mark.unit
class TestMessageEncoder:
    """Test protocol message encoding."""

    def test_encode_int32(self):
        """Test encoding 32-bit integers."""
        encoder = MessageEncoder()
        encoder.int32(42)
        data = encoder.bytes()

        assert len(data) == 4
        assert int.from_bytes(data, "little") == 42

    def test_encode_negative_int32(self):
        """Test encoding negative 32-bit integers."""
        encoder = MessageEncoder()
        encoder.int32(-100)
        data = encoder.bytes()

        assert len(data) == 4
        # Unpack as signed int
        import struct

        assert struct.unpack("<i", data)[0] == -100

    def test_encode_uint32(self):
        """Test encoding unsigned 32-bit integers."""
        encoder = MessageEncoder()
        encoder.uint32(0xFFFFFFFF)
        data = encoder.bytes()

        assert len(data) == 4
        assert int.from_bytes(data, "little", signed=False) == 0xFFFFFFFF

    def test_encode_string(self):
        """Test encoding strings with length prefix and null terminator."""
        encoder = MessageEncoder()
        encoder.string("hello")
        data = encoder.bytes()

        # String format: 4 bytes length + string + null terminator + padding to 4-byte boundary
        # "hello\x00" = 6 bytes, needs 2 bytes padding to reach 12 total (4 length + 8 data)
        assert len(data) == 12  # 4 (length) + 6 (string+null) + 2 (padding)
        # First 4 bytes are length (6, includes null terminator)
        length = int.from_bytes(data[:4], "little")
        assert length == 6
        # Next 6 bytes are "hello\x00"
        assert data[4:10] == b"hello\x00"

    def test_encode_multiple_values(self):
        """Test encoding multiple values in sequence."""
        encoder = MessageEncoder()
        encoder.int32(10).uint32(20).int32(30)
        data = encoder.bytes()

        assert len(data) == 12  # 3 * 4 bytes
        # Decode
        import struct

        values = struct.unpack("<III", data)
        assert values == (10, 20, 30)

    def test_encode_new_id(self):
        """Test encoding new_id protocol objects."""
        encoder = MessageEncoder()
        encoder.new_id(12345)
        data = encoder.bytes()

        assert len(data) == 4
        assert int.from_bytes(data, "little") == 12345

    def test_encode_object(self):
        """Test encoding object references."""

        class MockObject:
            def __init__(self, obj_id):
                self.object_id = obj_id

        encoder = MessageEncoder()
        obj = MockObject(99)
        encoder.object(obj)
        data = encoder.bytes()

        assert len(data) == 4
        assert int.from_bytes(data, "little") == 99

    def test_chaining(self):
        """Test method chaining works."""
        encoder = MessageEncoder()
        result = encoder.int32(1).uint32(2).int32(3)
        assert result is encoder  # Chaining returns self


@pytest.mark.unit
class TestMessageDecoder:
    """Test protocol message decoding."""

    def test_decode_int32(self):
        """Test decoding 32-bit integers."""
        data = (42).to_bytes(4, "little", signed=True)
        decoder = MessageDecoder(data)

        value = decoder.int32()
        assert value == 42

    def test_decode_negative_int32(self):
        """Test decoding negative integers."""
        import struct

        data = struct.pack("<i", -100)
        decoder = MessageDecoder(data)

        value = decoder.int32()
        assert value == -100

    def test_decode_uint32(self):
        """Test decoding unsigned 32-bit integers."""
        data = (0xFFFFFFFF).to_bytes(4, "little", signed=False)
        decoder = MessageDecoder(data)

        value = decoder.uint32()
        assert value == 0xFFFFFFFF

    def test_decode_string(self):
        """Test decoding strings with null terminator."""
        # Encode a string manually (length includes null terminator)
        text = "hello"
        text_with_null = text + "\x00"
        length = len(text_with_null)  # 6
        padding = (4 - (length % 4)) % 4  # 2 bytes padding
        data = (
            length.to_bytes(4, "little") + text_with_null.encode() + b"\x00" * padding
        )

        decoder = MessageDecoder(data)
        value = decoder.string()
        assert value == "hello"  # Decoder strips null terminator

    def test_decode_multiple_values(self):
        """Test decoding multiple values in sequence."""
        import struct

        data = struct.pack("<III", 10, 20, 30)
        decoder = MessageDecoder(data)

        v1 = decoder.int32()
        v2 = decoder.uint32()
        v3 = decoder.int32()
        assert (v1, v2, v3) == (10, 20, 30)

    def test_decode_insufficient_data(self):
        """Test decoding with insufficient data raises error."""
        import struct

        data = b"\x01\x02"  # Only 2 bytes
        decoder = MessageDecoder(data)

        with pytest.raises((ValueError, IndexError, struct.error)):
            decoder.int32()


@pytest.mark.unit
class TestDataStructures:
    """Test protocol data structures."""

    def test_area_creation(self):
        """Test Area dataclass."""
        area = Area(10, 20, 800, 600)
        assert area.x == 10
        assert area.y == 20
        assert area.width == 800
        assert area.height == 600

    def test_position_creation(self):
        """Test Position dataclass."""
        pos = Position(100, 200)
        assert pos.x == 100
        assert pos.y == 200

    def test_window_edges_none(self):
        """Test WindowEdges.NONE has no edges set."""
        edges = WindowEdges.NONE
        assert not (edges & WindowEdges.TOP)
        assert not (edges & WindowEdges.BOTTOM)
        assert not (edges & WindowEdges.LEFT)
        assert not (edges & WindowEdges.RIGHT)

    def test_window_edges_combination(self):
        """Test combining window edge flags."""
        edges = WindowEdges.TOP | WindowEdges.BOTTOM
        assert edges & WindowEdges.TOP
        assert edges & WindowEdges.BOTTOM
        assert not (edges & WindowEdges.LEFT)
        assert not (edges & WindowEdges.RIGHT)

    def test_window_edges_all(self):
        """Test all window edges set."""
        edges = (
            WindowEdges.TOP | WindowEdges.BOTTOM | WindowEdges.LEFT | WindowEdges.RIGHT
        )
        assert edges & WindowEdges.TOP
        assert edges & WindowEdges.BOTTOM
        assert edges & WindowEdges.LEFT
        assert edges & WindowEdges.RIGHT

    def test_modifiers_none(self):
        """Test Modifiers.NONE has no modifiers set."""
        mods = Modifiers.NONE
        assert not (mods & Modifiers.SHIFT)
        assert not (mods & Modifiers.CTRL)
        assert not (mods & Modifiers.MOD1)

    def test_modifiers_combination(self):
        """Test combining modifier flags."""
        mods = Modifiers.SHIFT | Modifiers.CTRL
        assert mods & Modifiers.SHIFT
        assert mods & Modifiers.CTRL
        assert not (mods & Modifiers.MOD1)
        assert not (mods & Modifiers.MOD4)

    def test_modifiers_all(self):
        """Test all common modifiers set."""
        mods = Modifiers.SHIFT | Modifiers.CTRL | Modifiers.MOD1 | Modifiers.MOD4
        assert mods & Modifiers.SHIFT
        assert mods & Modifiers.CTRL
        assert mods & Modifiers.MOD1  # Alt
        assert mods & Modifiers.MOD4  # Super


@pytest.mark.unit
class TestEncodingRoundtrip:
    """Test encoding/decoding round-trips."""

    def test_int32_roundtrip(self):
        """Test encoding then decoding int32 returns original."""
        original = 12345
        encoder = MessageEncoder()
        encoder.int32(original)
        data = encoder.bytes()

        decoder = MessageDecoder(data)
        result = decoder.int32()
        assert result == original

    def test_string_roundtrip(self):
        """Test encoding then decoding string returns original."""
        original = "test string"
        encoder = MessageEncoder()
        encoder.string(original)
        data = encoder.bytes()

        decoder = MessageDecoder(data)
        result = decoder.string()
        assert result == original

    def test_multiple_values_roundtrip(self):
        """Test encoding/decoding multiple values."""
        encoder = MessageEncoder()
        encoder.int32(10).uint32(20).string("hello").int32(30)
        data = encoder.bytes()

        decoder = MessageDecoder(data)
        v1 = decoder.int32()
        v2 = decoder.uint32()
        v3 = decoder.string()
        v4 = decoder.int32()

        assert v1 == 10
        assert v2 == 20
        assert v3 == "hello"
        assert v4 == 30

    def test_empty_string_roundtrip(self):
        """Test encoding/decoding empty string."""
        original = ""
        encoder = MessageEncoder()
        encoder.string(original)
        data = encoder.bytes()

        decoder = MessageDecoder(data)
        result = decoder.string()
        assert result == original

    def test_unicode_string_roundtrip(self):
        """Test encoding/decoding Unicode strings."""
        original = "Hello 世界 🌍"
        encoder = MessageEncoder()
        encoder.string(original)
        data = encoder.bytes()

        decoder = MessageDecoder(data)
        result = decoder.string()
        assert result == original
