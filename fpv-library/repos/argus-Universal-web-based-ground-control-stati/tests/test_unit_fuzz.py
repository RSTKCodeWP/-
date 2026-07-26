"""Fuzz tests for MAVLink parser and PL-Link protocol codec.

Ensures malformed, truncated, and random data does not crash the parser.
"""

import os
import struct

from backend.drone_link import _CRC_EXTRA, DroneLink
from backend.pllink_proto import bm, c16, mc, pld, ple, xp

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _build_valid_mavlink(link, msg_id=0, payload=b"\x00" * 9, sysid=1, compid=1, seq=0):
    """Build a valid MAVLink v2 frame for comparison / mutation tests."""
    header = bytes(
        [
            len(payload),
            0,
            0,
            seq & 0xFF,
            sysid & 0xFF,
            compid & 0xFF,
            msg_id & 0xFF,
            (msg_id >> 8) & 0xFF,
            (msg_id >> 16) & 0xFF,
        ]
    )
    crc_extra = _CRC_EXTRA.get(msg_id, 0)
    crc = link._mavlink_crc16(header + payload + bytes([crc_extra]))
    return b"\xfd" + header + payload + struct.pack("<H", crc)


# ---------------------------------------------------------------------------
# MAVLink parser fuzz: random / garbage data
# ---------------------------------------------------------------------------


class TestMavlinkParserRandomData:
    """Ensure _parse_mavlink_frame never raises on garbage input."""

    def test_empty_buffer(self):
        link = DroneLink()
        link._buf = b""
        result, skip = link._parse_mavlink_frame()
        assert result is None

    def test_single_byte_zero(self):
        link = DroneLink()
        link._buf = b"\x00"
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip >= 1

    def test_single_byte_magic(self):
        link = DroneLink()
        link._buf = b"\xfd"
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip == 0  # needs more data

    def test_random_bytes_short(self):
        link = DroneLink()
        link._buf = os.urandom(5)
        result, skip = link._parse_mavlink_frame()
        assert result is None

    def test_random_bytes_medium(self):
        link = DroneLink()
        link._buf = os.urandom(64)
        result, skip = link._parse_mavlink_frame()
        assert result is None

    def test_random_bytes_large(self):
        link = DroneLink()
        link._buf = os.urandom(1024)
        result, skip = link._parse_mavlink_frame()
        assert result is None

    def test_all_zeros(self):
        link = DroneLink()
        link._buf = b"\x00" * 100
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip >= 1

    def test_all_ff(self):
        link = DroneLink()
        link._buf = b"\xff" * 100
        result, skip = link._parse_mavlink_frame()
        assert result is None


# ---------------------------------------------------------------------------
# MAVLink parser fuzz: structural malformations
# ---------------------------------------------------------------------------


class TestMavlinkParserMalformed:
    """Test partial / malformed MAVLink frames."""

    def test_magic_then_truncated_header(self):
        link = DroneLink()
        link._buf = b"\xfd\x09\x00\x00"
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip == 0

    def test_wrong_magic_byte(self):
        link = DroneLink()
        link._buf = b"\xfe\x09\x00\x00\x01\x01\x01\x00\x00\x00" + b"\x00" * 11
        result, skip = link._parse_mavlink_frame()
        assert result is None

    def test_invalid_crc(self):
        link = DroneLink()
        frame = bytearray(_build_valid_mavlink(link))
        frame[-1] ^= 0xFF  # flip last CRC byte
        frame[-2] ^= 0xFF  # flip first CRC byte
        link._buf = bytes(frame)
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip == 1

    def test_truncated_payload(self):
        """Payload length says 9, but buffer only has 3 bytes of payload."""
        link = DroneLink()
        link._buf = b"\xfd\x09\x00\x00\x01\x01\x01\x00\x00\x00\x01\x02\x03"
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip == 0  # waiting for more data

    def test_oversized_payload_length(self):
        """Claimed payload length of 255 with insufficient data."""
        link = DroneLink()
        link._buf = b"\xfd\xff\x00\x00\x01\x01\x01\x00\x00\x00" + b"\x00" * 20
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip == 0

    def test_magic_in_middle_garbage_before(self):
        link = DroneLink()
        link._buf = b"\xaa\xbb\xcc\xfd\x00\x00\x00\x01\x01\x00\x00\x00\x00"
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip == 3  # skip to the magic byte

    def test_repeated_magic_bytes(self):
        link = DroneLink()
        link._buf = b"\xfd" * 50
        result, skip = link._parse_mavlink_frame()
        # Should not crash; may find or reject frame
        assert result is None or isinstance(result, bytes)

    def test_zero_length_payload(self):
        link = DroneLink()
        # A heartbeat-like frame with 0-byte payload
        link._buf = b"\xfd\x00\x00\x00\x01\x01\x01\x00\x00\x00\x00\x00"
        result, skip = link._parse_mavlink_frame()
        # Should not crash
        assert result is None or isinstance(result, bytes)


# ---------------------------------------------------------------------------
# PL-Link protocol codec fuzz: pld (decode)
# ---------------------------------------------------------------------------


class TestPldFuzz:
    """Fuzz tests for the PL-Link decode function."""

    def test_empty_bytes(self):
        decoded, skip = pld(b"")
        assert decoded is None

    def test_single_byte(self):
        decoded, skip = pld(b"\x50")
        assert decoded is None

    def test_just_magic(self):
        decoded, skip = pld(b"\x50\x4c")
        assert decoded is None
        assert skip >= 0

    def test_random_garbage_short(self):
        decoded, skip = pld(os.urandom(10))
        assert decoded is None

    def test_random_garbage_long(self):
        decoded, skip = pld(os.urandom(512))
        assert decoded is None

    def test_valid_header_bad_crc(self):
        original = b"\xfd\x01\x02\x03"
        frame = bytearray(ple(original, 0))
        frame[-1] ^= 0xFF
        frame[-2] ^= 0xFF
        decoded, skip = pld(bytes(frame))
        assert decoded is None

    def test_length_field_zero(self):
        data = b"\x50\x4c\x00\x00\x00" + b"\x00" * 10
        decoded, skip = pld(data)
        assert decoded is None

    def test_length_field_max(self):
        """Length field at maximum (280) but not enough data."""
        data = b"\x50\x4c" + struct.pack("<H", 280) + b"\x00" * 10
        decoded, skip = pld(data)
        assert decoded is None

    def test_length_field_overflow(self):
        """Length field exceeds 280 limit."""
        data = b"\x50\x4c" + struct.pack("<H", 500) + b"\x00" * 600
        decoded, skip = pld(data)
        assert decoded is None
        assert skip == 2

    def test_corrupted_xor_payload(self):
        """Valid header/CRC structure, but garbled XOR payload."""
        original = b"\xfd\x09\x00\x00\x01\x01\x00\x00\x00"
        frame = bytearray(ple(original, 0))
        # Corrupt the XOR'd payload bytes (keep header and CRC structure)
        if len(frame) > 7:
            frame[5] ^= 0xAA
            frame[6] ^= 0xBB
        decoded, skip = pld(bytes(frame))
        # CRC mismatch should make it return None
        assert decoded is None


# ---------------------------------------------------------------------------
# PL-Link protocol codec fuzz: ple (encode) robustness
# ---------------------------------------------------------------------------


class TestPleFuzz:
    """Ensure ple (encode) handles edge-case inputs without crashing."""

    def test_empty_payload(self):
        frame = ple(b"", 0)
        assert isinstance(frame, bytes)
        assert len(frame) == 2 + 3 + 0 + 2  # magic + header + payload + crc

    def test_single_byte_payload(self):
        frame = ple(b"\x00", 0)
        assert frame[0] == 0x50 and frame[1] == 0x4C

    def test_max_payload_280(self):
        payload = os.urandom(280)
        frame = ple(payload, 0)
        assert len(frame) == 2 + 3 + 280 + 2

    def test_large_sequence_number(self):
        frame = ple(b"\xfd", 65535)
        assert frame[4] == (65535 & 0xFF)

    def test_all_zeros_payload(self):
        frame = ple(b"\x00" * 50, 0)
        assert isinstance(frame, bytes)


# ---------------------------------------------------------------------------
# XOR cipher fuzz
# ---------------------------------------------------------------------------


class TestXorCipherFuzz:
    """Fuzz xp (xor cipher) with edge-case inputs."""

    def test_random_bytes_roundtrip(self):
        for _ in range(10):
            data = os.urandom(64)
            assert xp(xp(data)) == data

    def test_long_random_roundtrip(self):
        data = os.urandom(1000)
        assert xp(xp(data)) == data

    def test_all_same_byte(self):
        data = b"\xaa" * 32
        assert xp(xp(data)) == data


# ---------------------------------------------------------------------------
# CRC16 fuzz
# ---------------------------------------------------------------------------


class TestCrc16Fuzz:
    """Fuzz c16 (CRC-16) with garbage data."""

    def test_random_data_returns_uint16(self):
        for _ in range(20):
            data = os.urandom(128)
            crc = c16(data)
            assert isinstance(crc, int)
            assert 0 <= crc <= 0xFFFF

    def test_very_long_data(self):
        data = os.urandom(10000)
        crc = c16(data)
        assert 0 <= crc <= 0xFFFF

    def test_single_bit_difference(self):
        data = b"\x00" * 16
        crc1 = c16(data)
        flipped = bytearray(data)
        flipped[0] = 0x01
        crc2 = c16(bytes(flipped))
        assert crc1 != crc2


# ---------------------------------------------------------------------------
# MAVLink CRC (mc) fuzz
# ---------------------------------------------------------------------------


class TestMavlinkCrcFuzz:
    """Fuzz mc (MAVLink CRC) with garbage data."""

    def test_empty_data(self):
        crc = mc(b"", 0)
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF

    def test_random_payload_random_extra(self):
        for _ in range(20):
            data = os.urandom(32)
            extra = int.from_bytes(os.urandom(1), "little")
            crc = mc(data, extra)
            assert 0 <= crc <= 0xFFFF

    def test_large_payload(self):
        data = os.urandom(512)
        crc = mc(data, 50)
        assert 0 <= crc <= 0xFFFF


# ---------------------------------------------------------------------------
# Build MAVLink frame (bm) fuzz
# ---------------------------------------------------------------------------


class TestBuildMavlinkFuzz:
    """Fuzz bm (build MAVLink frame) with edge-case inputs."""

    def test_empty_payload(self):
        frame = bm(0, b"", 0, 50)
        assert frame[0] == 0xFD
        assert frame[1] == 0  # length

    def test_max_msg_id(self):
        frame = bm(0xFFFFFF, b"\x00", 0, 50)
        assert frame[7] == 0xFF
        assert frame[8] == 0xFF
        assert frame[9] == 0xFF

    def test_large_payload(self):
        payload = os.urandom(255)
        frame = bm(0, payload, 0, 50)
        assert frame[1] == 255

    def test_zero_crc_extra(self):
        frame = bm(0, b"\x00" * 9, 0, 0)
        assert isinstance(frame, bytes)
        assert len(frame) == 1 + 9 + 9 + 2
