"""Tests for backend/drone_link.py — CRC, frame parsing, and utility methods."""

import struct

from backend.drone_link import _CRC_EXTRA, DroneLink


class TestMavlinkCrc16:
    def test_returns_uint16(self):
        link = DroneLink()
        crc = link._mavlink_crc16(b"\x00")
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF

    def test_empty(self):
        link = DroneLink()
        crc = link._mavlink_crc16(b"")
        assert crc == 0xFFFF

    def test_deterministic(self):
        link = DroneLink()
        data = b"\x09\x00\x00\x01\x01\x01\x00\x00\x00"
        assert link._mavlink_crc16(data) == link._mavlink_crc16(data)

    def test_different_data_different_crc(self):
        link = DroneLink()
        assert link._mavlink_crc16(b"\x00") != link._mavlink_crc16(b"\x01")


class TestParseMavlinkFrame:
    def _build_mavlink_frame(self, link, msg_id=0, payload=b"\x00" * 9, sysid=1, compid=1, seq=0):
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

    def test_valid_frame_parsed(self):
        link = DroneLink()
        frame = self._build_mavlink_frame(link, msg_id=0, payload=b"\x00" * 9)
        link._buf = frame
        result, consumed = link._parse_mavlink_frame()
        assert result is not None
        assert consumed == len(frame)

    def test_no_magic_byte(self):
        link = DroneLink()
        link._buf = b"\x00\x01\x02\x03"
        result, skip = link._parse_mavlink_frame()
        assert result is None

    def test_magic_not_at_start(self):
        link = DroneLink()
        link._buf = b"\x00\x00\xfd" + b"\x00" * 20
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip == 2  # skip to \xfd

    def test_incomplete_header(self):
        link = DroneLink()
        link._buf = b"\xfd\x09\x00"
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip == 0  # need more data

    def test_bad_crc_rejected(self):
        link = DroneLink()
        frame = bytearray(self._build_mavlink_frame(link, msg_id=0))
        frame[-1] ^= 0xFF  # corrupt CRC
        link._buf = bytes(frame)
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip == 1

    def test_heartbeat_frame(self):
        link = DroneLink()
        payload = b"\x00" * 9  # heartbeat payload
        frame = self._build_mavlink_frame(link, msg_id=0, payload=payload)
        link._buf = frame
        result, consumed = link._parse_mavlink_frame()
        assert result is not None
        assert result[0] == 0xFD
        assert result[7] == 0  # msg_id

    def test_unknown_msg_id_dropped(self):
        """Fail-loud: msg_id not in _CRC_EXTRA should drop the frame and bump
        the unknown-id counter (so missing entries surface in logs)."""
        link = DroneLink()
        unknown_id = 9999
        assert unknown_id not in _CRC_EXTRA
        header = bytes(
            [
                9,
                0,
                0,
                0,
                1,
                1,
                unknown_id & 0xFF,
                (unknown_id >> 8) & 0xFF,
                (unknown_id >> 16) & 0xFF,
            ]
        )
        payload = b"\x00" * 9
        link._buf = b"\xfd" + header + payload + b"\x00\x00"
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip == 1
        assert link._unknown_msg_ids.get(unknown_id) == 1

    def test_mag_cal_msg_ids_have_crc_extra(self):
        """Regression: msg 191 (MAG_CAL_PROGRESS) and 192 (MAG_CAL_REPORT) were
        previously missing from _CRC_EXTRA, which let frames slip through
        without CRC verification."""
        assert _CRC_EXTRA.get(191) == 92
        assert _CRC_EXTRA.get(192) == 36


class TestNextFrame:
    def test_auto_detects_standard(self):
        link = DroneLink()
        link._protocol = "auto"
        link._buf = b"\xfd\x09\x00\x00\x01\x01\x01\x00\x00\x00" + b"\x00" * 11
        link._next_frame()
        assert link._protocol == "standard"

    def test_auto_detects_pllink(self):
        link = DroneLink()
        link._protocol = "auto"
        from backend.pllink_proto import ple

        link._buf = ple(b"\xfd\x09\x00\x00\x01\x01\x01\x00\x00\x00", 0)
        link._next_frame()
        assert link._protocol == "pllink"


class TestGetInspectorData:
    def test_returns_list(self):
        link = DroneLink()
        data = link.get_inspector_data()
        assert isinstance(data, list)

    def test_reflects_msg_stats(self):
        import time

        link = DroneLink()
        link._msg_stats[0] = {
            "name": "HEARTBEAT",
            "count": 100,
            "bytes": 900,
            "times": [time.time()] * 5,
        }
        data = link.get_inspector_data()
        assert len(data) >= 1
        assert data[0]["name"] == "HEARTBEAT"


class TestQueueWs:
    def test_appends(self):
        link = DroneLink()
        link.queue_ws({"test": 1})
        assert len(link._ws_queue) == 1

    def test_trims_at_2000(self):
        link = DroneLink()
        for i in range(2100):
            link.queue_ws({"i": i})
        assert len(link._ws_queue) <= 1100
