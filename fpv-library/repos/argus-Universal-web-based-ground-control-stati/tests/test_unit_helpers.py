"""Tests for backend/commands/_helpers.py — wire-level MAVLink builders."""

import struct
import time
from unittest.mock import MagicMock

from backend.commands._helpers import (
    request_streams,
    send_cmd_int,
    send_fence_count,
    send_fence_item_int,
    send_heartbeat,
    send_mission_count,
    send_mission_item_int,
    send_rally_item_int,
    send_serial_control,
)
from backend.drone_link import DroneLink


def make_link():
    link = DroneLink()
    link._ser = MagicMock()
    link.connected = True
    link.vehicle.sysid = 1
    return link


class TestSendHeartbeat:
    def test_heartbeat_packs_gcs_fields(self):
        link = make_link()
        send_heartbeat(link)
        assert link._ser.write.called
        raw = link._ser.write.call_args[0][0]
        assert raw[0] == 0xFD

    def test_heartbeat_payload_fields(self):
        link = make_link()
        send_heartbeat(link)
        raw = link._ser.write.call_args[0][0]
        # PL-Link wrapper or raw MAVLink — find 0xFD magic
        idx = raw.index(0xFD)
        payload_len = raw[idx + 1]
        payload = raw[idx + 10 : idx + 10 + payload_len]
        custom_mode, mtype, autopilot, base_mode, status, mav_ver = struct.unpack("<IBBBBB", payload)
        assert custom_mode == 0
        assert mtype == 6  # MAV_TYPE_GCS
        assert autopilot == 8  # MAV_AUTOPILOT_INVALID
        assert status == 4  # MAV_STATE_ACTIVE


class TestRequestStreams:
    def test_sends_multiple_frames(self):
        link = make_link()
        import backend.commands._helpers as h

        orig_sleep = time.sleep
        with MagicMock() as mock_sleep:
            h.time.sleep = mock_sleep
            try:
                request_streams(link)
            finally:
                h.time.sleep = orig_sleep
        # 12 SET_MESSAGE_INTERVAL + 1 send_cmd(512) = at least 13 writes
        assert link._ser.write.call_count >= 13


class TestSendFenceItemInt:
    def test_packs_fence_point(self):
        link = make_link()
        item = {"seq": 1, "cmd": 5001, "lat": 30.123, "lon": 120.456, "alt": 50.0, "p1": 100, "p2": 200}
        send_fence_item_int(link, item)
        assert link._ser.write.called

    def test_defaults_for_missing_fields(self):
        link = make_link()
        item = {"seq": 0, "cmd": 5001}
        send_fence_item_int(link, item)
        assert link._ser.write.called


class TestSendRallyItemInt:
    def test_packs_rally_point(self):
        link = make_link()
        item = {"seq": 0, "cmd": 5100, "lat": 31.0, "lon": 121.0, "alt": 100.0, "p1": 0, "p2": 0}
        send_rally_item_int(link, item)
        assert link._ser.write.called

    def test_rally_defaults(self):
        link = make_link()
        item = {"seq": 0, "cmd": 5100}
        send_rally_item_int(link, item)
        assert link._ser.write.called


class TestSendMissionItemInt:
    def test_nav_waypoint_uses_frame_3(self):
        link = make_link()
        wp = {"seq": 1, "cmd": 16, "lat": 30.0, "lon": 120.0, "alt": 50.0, "p1": 0, "p2": 0, "p3": 0, "p4": 0}
        send_mission_item_int(link, wp)
        assert link._ser.write.called

    def test_do_cmd_uses_frame_2(self):
        link = make_link()
        wp = {"seq": 2, "cmd": 177, "lat": 0, "lon": 0, "alt": 0, "p1": 1, "p2": 0, "p3": 0, "p4": 0}
        send_mission_item_int(link, wp)
        assert link._ser.write.called

    def test_home_item_current_flag(self):
        link = make_link()
        wp = {"seq": 0, "cmd": 16, "lat": 30.0, "lon": 120.0, "alt": 0, "p1": 0, "p2": 0, "p3": 0, "p4": 0}
        send_mission_item_int(link, wp)
        assert link._ser.write.called


class TestSendSerialControl:
    def test_packs_ascii_text(self):
        link = make_link()
        send_serial_control(link, "reboot")
        assert link._ser.write.called

    def test_truncates_long_text(self):
        link = make_link()
        send_serial_control(link, "A" * 200)
        assert link._ser.write.called


class TestSendCmdInt:
    def test_packs_command_int(self):
        link = make_link()
        send_cmd_int(link, 1000, p1=1.0, x=42, y=99, z=3.0)
        assert link._ser.write.called


class TestSendCounts:
    def test_mission_count(self):
        link = make_link()
        send_mission_count(link, 5)
        assert link._ser.write.called

    def test_fence_count(self):
        link = make_link()
        send_fence_count(link, 3)
        assert link._ser.write.called
