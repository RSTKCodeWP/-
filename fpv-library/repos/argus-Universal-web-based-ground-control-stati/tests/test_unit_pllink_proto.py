"""Tests for backend/pllink_proto.py — PL-Link XOR framing + MAVLink v2 construction."""

import struct

from backend.pllink_proto import bm, c16, mc, pld, ple, xp


class TestXorCipher:
    def test_roundtrip(self):
        data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        assert xp(xp(data)) == data

    def test_double_xor_is_identity(self):
        data = b"Hello MAVLink!"
        assert xp(xp(data)) == data

    def test_empty_data(self):
        assert xp(b"") == b""

    def test_single_byte(self):
        result = xp(b"\x00")
        assert result == bytes([0x4B])
        assert xp(result) == b"\x00"

    def test_longer_than_key(self):
        data = bytes(range(16))
        result = xp(data)
        assert len(result) == 16
        assert xp(result) == data


class TestCrc16:
    def test_known_value(self):
        crc = c16(b"\x00")
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF

    def test_empty(self):
        crc = c16(b"")
        assert crc == 0xFFFF

    def test_different_data_different_crc(self):
        assert c16(b"\x00") != c16(b"\x01")

    def test_deterministic(self):
        data = b"test data for crc"
        assert c16(data) == c16(data)


class TestPleEncode:
    def test_header_magic(self):
        frame = ple(b"\xfd\x00", 0)
        assert frame[0] == 0x50
        assert frame[1] == 0x4C

    def test_length_in_header(self):
        payload = b"\xfd\x00\x01\x02\x03"
        frame = ple(payload, 0)
        length = frame[2] | (frame[3] << 8)
        assert length == len(payload)

    def test_sequence_number(self):
        frame = ple(b"\xfd", 42)
        assert frame[4] == 42

    def test_sequence_wraps(self):
        frame = ple(b"\xfd", 256)
        assert frame[4] == 0

    def test_crc_appended(self):
        payload = b"\xfd\x09"
        frame = ple(payload, 0)
        assert len(frame) == 2 + 3 + len(payload) + 2  # magic + header + xor_payload + crc


class TestPldDecode:
    def test_roundtrip(self):
        original = b"\xfd\x09\x00\x00\x01\x01\x00\x00\x00"
        frame = ple(original, 5)
        decoded, consumed = pld(frame)
        assert decoded == original
        assert consumed == len(frame)

    def test_invalid_magic(self):
        data = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        decoded, skip = pld(data)
        assert decoded is None

    def test_too_short(self):
        decoded, skip = pld(b"\x50\x4c")
        assert decoded is None
        assert skip >= 0  # implementation returns 1 (skip past partial header)

    def test_empty(self):
        decoded, skip = pld(b"")
        assert decoded is None

    def test_bad_crc_returns_none(self):
        original = b"\xfd\x01\x02"
        frame = bytearray(ple(original, 0))
        frame[-1] ^= 0xFF  # corrupt CRC
        decoded, skip = pld(bytes(frame))
        assert decoded is None

    def test_length_too_large(self):
        bad = b"\x50\x4c" + struct.pack("<HB", 300, 0) + b"\x00" * 307
        decoded, skip = pld(bad)
        assert decoded is None
        assert skip == 2


class TestMavlinkCrc:
    def test_returns_uint16(self):
        crc = mc(b"\xfd\x09\x00", 50)
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF

    def test_deterministic(self):
        data = b"\x09\x00\x00\x01\x01\x01\x00\x00\x00"
        assert mc(data, 50) == mc(data, 50)

    def test_different_crc_extra(self):
        data = b"\x09\x00\x00\x01\x01\x01\x00\x00\x00"
        assert mc(data, 50) != mc(data, 51)


class TestBuildMavlink:
    def test_magic_byte(self):
        frame = bm(0, b"\x00" * 9, 0, 50)
        assert frame[0] == 0xFD

    def test_payload_length(self):
        payload = b"\x00" * 9
        frame = bm(0, payload, 0, 50)
        assert frame[1] == len(payload)

    def test_sysid_compid(self):
        frame = bm(0, b"\x00", 0, 50, sysid=1, compid=190)
        assert frame[5] == 1
        assert frame[6] == 190

    def test_msg_id_encoding(self):
        frame = bm(33, b"\x00" * 28, 0, 104)
        assert frame[7] == 33
        assert frame[8] == 0
        assert frame[9] == 0

    def test_crc_appended(self):
        payload = b"\x00" * 9
        frame = bm(0, payload, 0, 50)
        expected_len = 1 + 9 + len(payload) + 2  # magic + header + payload + crc
        assert len(frame) == expected_len

    def test_default_sysid_compid(self):
        frame = bm(0, b"\x00", 0, 50)
        assert frame[5] == 255  # default sysid
        assert frame[6] == 1  # default compid
