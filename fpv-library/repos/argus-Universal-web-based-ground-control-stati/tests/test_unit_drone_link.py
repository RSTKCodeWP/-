"""Tests for DroneLink state machine, heartbeat timeout, reconnect logic."""

from __future__ import annotations

import struct
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backend.drone_link as _dl_module
from backend.config import cfg
from backend.drone_link import _CRC_EXTRA, _MSG_NAMES, DroneLink


@pytest.fixture(autouse=True)
def _isolate_log_dir(tmp_path, monkeypatch):
    # Repoint drone_link.__file__ so _start_log's Path(__file__).parent.parent/'logs' lands in tmp_path — second-resolution argus_*.csv names collide across same-second tests, which on Windows cascades file-lock failures.
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    fake_drone_link = fake_backend / "drone_link.py"
    fake_drone_link.touch()
    monkeypatch.setattr(_dl_module, "__file__", str(fake_drone_link))
    yield tmp_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_mavlink_frame(link, msg_id=0, payload=b"\x00" * 9, sysid=1, compid=1, seq=0):
    """Build a valid MAVLink v2 frame with correct CRC."""
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


def _build_heartbeat_payload(mode=0, vtype=2, armed=False):
    """Build a minimal HEARTBEAT payload (msg_id=0, 9 bytes)."""
    base_mode = 0x80 if armed else 0x00
    # mode as uint32 LE, then vtype, autopilot, base_mode, status, mavlink_version
    p = struct.pack("<IBBBBB", mode, vtype, 0, base_mode, 0, 3)
    return p


def _build_global_position_int_payload(lat_deg=30.0, lon_deg=120.0, alt_m=100.0, hdg_deg=90.0):
    """Build GLOBAL_POSITION_INT payload (msg_id=33, >=28 bytes)."""
    time_boot_ms = 1000
    lat = int(lat_deg * 1e7)
    lon = int(lon_deg * 1e7)
    alt = int(alt_m * 1000)
    relative_alt = int(alt_m * 1000)
    vx, vy, vz = 0, 0, 0
    hdg = int(hdg_deg * 100)
    return struct.pack("<IiiiihhH", time_boot_ms, lat, lon, alt, relative_alt, vx, vy, vz) + struct.pack("<H", hdg)


# ---------------------------------------------------------------------------
# TestDroneLinkInit
# ---------------------------------------------------------------------------


class TestDroneLinkInit:
    def test_initial_state(self):
        link = DroneLink()
        assert link.connected is False
        assert link.frame_count == 0
        assert link._running is False
        assert link._ser is None
        assert link.locale == "zh"
        assert link.active_sysid == 1
        assert link.inspector_enabled is False

    def test_state_objects_created(self):
        link = DroneLink()
        assert link.attitude is not None
        assert link.battery is not None
        assert link.gps is not None
        assert link.vehicle is not None
        assert link.mission is not None
        assert link.diagnostic is not None
        assert link.rc_servo is not None
        assert link.log_dl is not None
        assert link.traffic is not None

    def test_param_manager_created(self):
        link = DroneLink()
        assert link.param_mgr is not None

    def test_default_protocol_auto(self):
        link = DroneLink()
        assert link._protocol == "auto"

    def test_default_locks_created(self):
        link = DroneLink()
        assert isinstance(link._lock, type(threading.Lock()))
        assert isinstance(link._state_lock, type(threading.RLock()))

    def test_default_buf_empty(self):
        link = DroneLink()
        assert link._buf == b""
        assert link.sq == 0
        assert link._parse_errors == 0

    def test_default_vehicles_empty(self):
        link = DroneLink()
        assert link._vehicles == {}
        assert link._msg_stats == {}
        assert link._console_buf == []
        assert link._prearm_messages == []

    def test_default_reconnect_enabled(self):
        link = DroneLink()
        assert link._reconnect_enabled is True


# ---------------------------------------------------------------------------
# TestDroneLinkIsPlane
# ---------------------------------------------------------------------------


class TestDroneLinkIsPlane:
    def test_not_plane_by_default(self):
        link = DroneLink()
        assert link.is_plane() is False

    def test_plane_vtype(self):
        link = DroneLink()
        for vt in (1, 19, 20, 21, 22, 23, 24, 25):
            link.vehicle.vtype_raw = vt
            assert link.is_plane() is True, f"vtype_raw={vt} should be plane"

    def test_copter_vtype(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 2
        assert link.is_plane() is False

    def test_force_plane_overrides(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 2
        link.vehicle.force_plane = True
        assert link.is_plane() is True

    def test_force_copter_overrides(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 1
        link.vehicle.force_plane = False
        assert link.is_plane() is False


# ---------------------------------------------------------------------------
# TestDroneLinkEvents
# ---------------------------------------------------------------------------


class TestDroneLinkEvents:
    def test_add_event(self):
        link = DroneLink()
        link.add_event("test event", "test")
        assert len(link.events) == 1
        assert link.events[0]["text"] == "test event"
        assert link.events[0]["event_type"] == "test"

    def test_event_capped(self):
        link = DroneLink()
        for i in range(120):
            link.add_event(f"event {i}", "test")
        assert len(link.events) <= 100

    def test_event_trim_keeps_recent(self):
        """After trimming, the most recent events are kept."""
        link = DroneLink()
        for i in range(110):
            link.add_event(f"event {i}", "test")
        # Trim fires when len > 100, keeps last 50 + additions after trim
        assert len(link.events) <= 100
        assert link.events[-1]["text"] == "event 109"

    def test_ws_queue_capped(self):
        link = DroneLink()
        for i in range(2100):
            link.queue_ws({"type": "test", "i": i})
        assert len(link._ws_queue) <= 2000

    def test_event_default_type(self):
        link = DroneLink()
        link.add_event("no type")
        assert link.events[0]["event_type"] == ""

    def test_event_has_time_field(self):
        link = DroneLink()
        link.add_event("timed event")
        assert "time" in link.events[0]
        # Should be in HH:MM:SS format
        assert len(link.events[0]["time"]) == 8


# ---------------------------------------------------------------------------
# TestDroneLinkConnect
# ---------------------------------------------------------------------------


class TestDroneLinkConnect:
    @patch.object(DroneLink, "_open_port")
    def test_connect_success(self, mock_open):
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            result = link.connect("udp:14550")
        assert result is True
        assert link._running is True
        assert link._protocol == "standard"

    @patch.object(DroneLink, "_open_port", side_effect=OSError("fail"))
    def test_connect_failure(self, mock_open):
        link = DroneLink()
        result = link.connect("tcp:bad:99")
        assert result is False
        assert link._running is False

    @patch.object(DroneLink, "_open_port")
    def test_connect_resets_state(self, mock_open):
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link.connected = True
        link.frame_count = 999
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            link.connect("udp:14550")
        assert link.connected is False
        assert link.frame_count == 0

    @patch.object(DroneLink, "_open_port")
    def test_udp_forces_standard_protocol(self, mock_open):
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            link.connect("udp:14550", protocol="pllink")
        assert link._protocol == "standard"

    @patch.object(DroneLink, "_open_port")
    def test_connect_stores_last_port_baud(self, mock_open):
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            link.connect("tcp:localhost:5770", baudrate=115200)
        assert link._last_port == "tcp:localhost:5770"
        assert link._last_baud == 115200

    @patch.object(DroneLink, "_open_port")
    def test_connect_enables_reconnect(self, mock_open):
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link._reconnect_enabled = False
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            link.connect("udp:14550")
        assert link._reconnect_enabled is True

    @patch.object(DroneLink, "_open_port")
    def test_connect_resets_home(self, mock_open):
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link.attitude.home_lat = 30.0
        link.attitude.home_lon = 120.0
        link.attitude.dist_home = 500.0
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            link.connect("udp:14550")
        assert link.attitude.home_lat == 0.0
        assert link.attitude.home_lon == 0.0
        assert link.attitude.dist_home == 0.0

    @patch.object(DroneLink, "_open_port")
    def test_connect_tcp_adds_event(self, mock_open):
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            link.connect("tcp:localhost:5770")
        tcp_events = [e for e in link.events if e["event_type"] == "tcp"]
        assert len(tcp_events) >= 1

    @patch.object(DroneLink, "_open_port")
    def test_connect_udp_adds_event(self, mock_open):
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            link.connect("udp:14550")
        udp_events = [e for e in link.events if e["event_type"] == "udp"]
        assert len(udp_events) >= 1

    @patch.object(DroneLink, "_open_port", side_effect=OSError("port busy"))
    def test_connect_failure_adds_event(self, mock_open):
        link = DroneLink()
        link.connect("tcp:bad:99")
        fail_events = [e for e in link.events if e["event_type"] == "connect_fail"]
        assert len(fail_events) >= 1

    @patch.object(DroneLink, "_open_port")
    def test_connect_tcp_keeps_protocol(self, mock_open):
        """TCP connections respect the protocol parameter."""
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            link.connect("tcp:localhost:5770", protocol="pllink")
        assert link._protocol == "pllink"

    @patch.object(DroneLink, "_open_port")
    def test_connect_serial_keeps_protocol(self, mock_open):
        """Serial connections respect the protocol parameter."""
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            link.connect("/dev/ttyUSB0", protocol="auto")
        assert link._protocol == "auto"


# ---------------------------------------------------------------------------
# TestDroneLinkDisconnect
# ---------------------------------------------------------------------------


class TestDroneLinkDisconnect:
    def test_disconnect_clears_state(self):
        link = DroneLink()
        link.connected = True
        link._running = True
        link.vehicle.vtype_raw = 2
        link.disconnect()
        assert link.connected is False
        assert link._running is False
        assert link.vehicle.vtype_raw == 0
        assert link._reconnect_enabled is False

    def test_disconnect_clears_force_plane(self):
        link = DroneLink()
        link.vehicle.force_plane = True
        link.disconnect()
        assert link.vehicle.force_plane is None

    def test_disconnect_clears_mission_pending(self):
        link = DroneLink()
        link.mission._mission_pending = True
        link.disconnect()
        assert link.mission._mission_pending is False

    def test_disconnect_clears_prev_pos(self):
        link = DroneLink()
        link.attitude._prev_pos = (30.0, 120.0)
        link.disconnect()
        assert link.attitude._prev_pos is None

    def test_disconnect_adds_event(self):
        link = DroneLink()
        link.disconnect()
        disc_events = [e for e in link.events if e["event_type"] == "disconnected"]
        assert len(disc_events) == 1

    def test_disconnect_closes_serial(self):
        mock_ser = MagicMock(in_waiting=0)
        link = DroneLink()
        link._ser = mock_ser
        link.disconnect()
        mock_ser.close.assert_called_once()
        assert link._ser is None

    def test_disconnect_handles_close_error(self):
        """OSError from close is caught gracefully."""
        mock_ser = MagicMock(in_waiting=0)
        mock_ser.close.side_effect = OSError("close failed")
        link = DroneLink()
        link._ser = mock_ser
        link.disconnect()
        assert link._ser is None
        assert link.connected is False

    def test_disconnect_stops_log(self):
        link = DroneLink()
        link._start_log()
        try:
            assert link._logfile is not None
            link.disconnect()
            assert link._logfile is None
        finally:
            link._stop_log()


# ---------------------------------------------------------------------------
# TestDroneLinkReconnect
# ---------------------------------------------------------------------------


class TestDroneLinkReconnect:
    @patch.object(DroneLink, "_open_port")
    def test_reconnect_success(self, mock_open):
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link._last_port = "tcp:localhost:5770"
        link._last_baud = 57600
        link._running = True
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            result = link.reconnect()
        assert result is True
        assert link._running is True

    @patch.object(DroneLink, "_open_port", side_effect=OSError("reconnect fail"))
    def test_reconnect_failure(self, mock_open):
        link = DroneLink()
        link._last_port = "tcp:localhost:5770"
        link._last_baud = 57600
        result = link.reconnect()
        assert result is False

    @patch.object(DroneLink, "_open_port")
    def test_reconnect_resets_sequence(self, mock_open):
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link._last_port = "tcp:localhost:5770"
        link.sq = 42
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            link.reconnect()
        assert link.sq == 0

    @patch.object(DroneLink, "_open_port")
    def test_reconnect_clears_buf(self, mock_open):
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link._last_port = "tcp:localhost:5770"
        link._buf = b"\xfd\x00\x01"
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            link.reconnect()
        assert link._buf == b""

    @patch.object(DroneLink, "_open_port")
    def test_reconnect_adds_event(self, mock_open):
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link._last_port = "tcp:localhost:5770"
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            link.reconnect()
        reconn_events = [e for e in link.events if e["event_type"] == "reconnected"]
        assert len(reconn_events) >= 1

    @patch.object(DroneLink, "_open_port", side_effect=OSError("fail"))
    def test_reconnect_failure_adds_event(self, mock_open):
        link = DroneLink()
        link._last_port = "tcp:localhost:5770"
        link.reconnect()
        err_events = [e for e in link.events if e["event_type"] == "reconnect_err"]
        assert len(err_events) >= 1

    @patch.object(DroneLink, "_open_port")
    def test_reconnect_closes_existing_serial(self, mock_open):
        old_ser = MagicMock(in_waiting=0)
        mock_open.return_value = MagicMock()
        link = DroneLink()
        link._ser = old_ser
        link._last_port = "tcp:localhost:5770"
        link._loop = MagicMock()
        with patch.object(threading.Thread, "start"):
            link.reconnect()
        old_ser.close.assert_called_once()


# ---------------------------------------------------------------------------
# TestDroneLinkSend
# ---------------------------------------------------------------------------


class TestDroneLinkSend:
    def test_send_with_no_serial(self):
        link = DroneLink()
        link.send(b"\xfd\x00\x00")

    @patch.object(DroneLink, "_open_port")
    def test_send_increments_sequence(self, mock_open):
        mock_ser = MagicMock(in_waiting=0)
        link = DroneLink()
        link._ser = mock_ser
        link._protocol = "standard"
        link.sq = 0
        link.send(b"\xfd\x00\x00")
        assert link.sq == 1

    def test_send_exception_handled(self):
        link = DroneLink()
        mock_ser = MagicMock(in_waiting=0)
        mock_ser.write.side_effect = OSError("write failed")
        link._ser = mock_ser
        link._protocol = "standard"
        link.send(b"\xfd\x00\x00")

    def test_send_standard_writes_raw(self):
        """Standard protocol writes the raw frame bytes."""
        mock_ser = MagicMock(in_waiting=0)
        link = DroneLink()
        link._ser = mock_ser
        link._protocol = "standard"
        frame = b"\xfd\x09\x00\x00\x01\x01\x01\x00\x00\x00"
        link.send(frame)
        mock_ser.write.assert_called_once_with(frame)

    def test_send_pllink_wraps_frame(self):
        """PL-Link protocol wraps the frame with PL-Link envelope."""
        mock_ser = MagicMock(in_waiting=0)
        link = DroneLink()
        link._ser = mock_ser
        link._protocol = "pllink"
        link.sq = 5
        frame = b"\xfd\x09\x00\x00\x01\x01\x01\x00\x00\x00"
        link.send(frame)
        written = mock_ser.write.call_args[0][0]
        # PL-Link frames start with 0x50 0x4C
        assert written[0] == 0x50
        assert written[1] == 0x4C

    def test_send_auto_protocol_sends_standard(self):
        """Auto protocol sends standard MAVLink (not PL-Link wrapped)."""
        mock_ser = MagicMock(in_waiting=0)
        link = DroneLink()
        link._ser = mock_ser
        link._protocol = "auto"
        link.sq = 0
        frame = b"\xfd\x09"
        link.send(frame)
        written = mock_ser.write.call_args[0][0]
        assert written[0] == 0xFD


# ---------------------------------------------------------------------------
# TestDroneLinkGetState
# ---------------------------------------------------------------------------


class TestDroneLinkGetState:
    def test_get_state_returns_dict(self):
        link = DroneLink()
        state = link.get_state()
        assert isinstance(state, dict)
        assert state["type"] == "state"
        assert state["connected"] is False

    def test_get_state_includes_all_fields(self):
        link = DroneLink()
        state = link.get_state()
        expected_keys = [
            "type",
            "connected",
            "frames",
            "mode",
            "armed",
            "roll",
            "pitch",
            "yaw",
            "lat",
            "lon",
            "alt_rel",
            "alt_msl",
            "gs",
            "vz",
            "hdg",
            "dist_home",
            "voltage",
            "current",
            "remaining",
            "gps_fix",
            "gps_sats",
            "wp",
            "vtype",
            "rc",
            "servo",
            "vibe",
            "ekf_vel",
            "wind_dir",
            "prearm",
            "adsb",
            "cells",
            "flight_summary",
        ]
        for key in expected_keys:
            assert key in state, f"Missing key: {key}"

    def test_get_state_reflects_changes(self):
        link = DroneLink()
        link.attitude.roll = 15.5
        link.battery.voltage = 12.6
        state = link.get_state()
        assert state["roll"] == 15.5
        assert state["voltage"] == 12.6

    def test_get_state_flight_time_zero_when_disarmed(self):
        link = DroneLink()
        link.vehicle.armed = False
        state = link.get_state()
        assert state["flight_time"] == 0

    def test_get_state_flight_time_when_armed(self):
        link = DroneLink()
        link.vehicle.armed = True
        link.vehicle.armed_time = time.time() - 60
        state = link.get_state()
        assert state["flight_time"] >= 59

    def test_get_state_link_age_when_not_connected(self):
        link = DroneLink()
        link.connected = False
        state = link.get_state()
        assert state["link_age"] == -1

    def test_get_state_link_age_when_connected(self):
        link = DroneLink()
        link.connected = True
        link.last_frame_time = time.time() - 1.0
        state = link.get_state()
        assert state["link_age"] >= 0.9

    def test_get_state_bat_time_negative_when_unknown(self):
        link = DroneLink()
        link.battery.bat_time_remaining = -1
        state = link.get_state()
        assert state["bat_time"] == -1

    def test_get_state_bat_time_positive(self):
        link = DroneLink()
        link.battery.bat_time_remaining = 300
        state = link.get_state()
        assert state["bat_time"] == 300

    def test_get_state_vz_sign_inverted(self):
        """vz in state is the negative of attitude.vz (convention: positive = climb)."""
        link = DroneLink()
        link.attitude.vz = 2.5
        state = link.get_state()
        assert state["vz"] == -2.5

    def test_get_state_mode_fallback(self):
        """Unknown mode ID produces MODE<N> string."""
        link = DroneLink()
        link.vehicle.mode = 999
        state = link.get_state()
        assert state["mode"] == "MODE999"

    def test_get_state_log_active(self):
        link = DroneLink()
        assert link.get_state()["log_active"] is False
        link._start_log()
        try:
            assert link.get_state()["log_active"] is True
        finally:
            link._stop_log()


# ---------------------------------------------------------------------------
# TestDroneLinkMavlinkCrc
# ---------------------------------------------------------------------------


class TestDroneLinkMavlinkCrc:
    def test_crc_empty(self):
        link = DroneLink()
        crc = link._mavlink_crc16(b"")
        assert crc == 0xFFFF

    def test_crc_known_value(self):
        link = DroneLink()
        crc = link._mavlink_crc16(b"\x00")
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF

    def test_crc_deterministic(self):
        link = DroneLink()
        data = b"\x09\x00\x00\x01\x01\x01\x00\x00\x00"
        assert link._mavlink_crc16(data) == link._mavlink_crc16(data)

    def test_crc_different_data_different_crc(self):
        link = DroneLink()
        assert link._mavlink_crc16(b"\x00") != link._mavlink_crc16(b"\x01")

    def test_crc_long_data(self):
        link = DroneLink()
        crc = link._mavlink_crc16(b"\xaa" * 255)
        assert 0 <= crc <= 0xFFFF


# ---------------------------------------------------------------------------
# TestDroneLinkLog
# ---------------------------------------------------------------------------


class TestDroneLinkLog:
    def test_start_stop_log(self):
        link = DroneLink()
        link._start_log()
        try:
            assert link._logfile is not None
        finally:
            link._stop_log()
        assert link._logfile is None

    def test_get_log_path_none(self):
        link = DroneLink()
        assert link.get_log_path() is None

    def test_get_log_path_returns_path(self):
        link = DroneLink()
        link._start_log()
        try:
            path = link.get_log_path()
            assert path is not None
            assert "argus_" in path
            assert path.endswith(".csv")
        finally:
            link._stop_log()

    def test_log_file_has_csv_header(self):
        link = DroneLink()
        link._start_log()
        try:
            path = link._logfile.name
            link._logfile.flush()
            with open(path, encoding="utf-8") as f:
                header = f.readline()
            assert header.startswith("time,roll,pitch,yaw,lat,lon")
        finally:
            link._stop_log()

    def test_start_log_adds_event(self):
        link = DroneLink()
        link._start_log()
        try:
            log_events = [e for e in link.events if e["event_type"] == "log_file"]
            assert len(log_events) >= 1
        finally:
            link._stop_log()

    def test_write_log_line_respects_interval(self):
        """_write_log_line does nothing if called too soon after last write."""
        link = DroneLink()
        link._start_log()
        try:
            path = link._logfile.name
            link.start_time = time.time()
            link._last_log_time = time.time()  # set to now
            link._write_log_line()
            link._logfile.flush()
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
            # Only the header line, no data line
            assert len(lines) == 1
        finally:
            link._stop_log()

    def test_write_log_line_writes_data(self):
        """_write_log_line writes data when interval elapsed."""
        link = DroneLink()
        link._start_log()
        try:
            path = link._logfile.name
            link.start_time = time.time() - 10.0
            link._last_log_time = 0.0  # force write
            link.attitude.roll = 5.0
            link.battery.voltage = 12.6
            link._write_log_line()
            link._logfile.flush()
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) == 2  # header + 1 data line
            data_line = lines[1]
            assert "5.00" in data_line
            assert "12.60" in data_line
        finally:
            link._stop_log()

    def test_write_log_line_no_logfile(self):
        """_write_log_line is a no-op when no log file is open."""
        link = DroneLink()
        link._write_log_line()  # should not raise

    def test_stop_log_handles_already_none(self):
        """_stop_log is safe when _logfile is already None."""
        link = DroneLink()
        link._stop_log()  # should not raise

    def test_log_created_in_logs_dir(self):
        link = DroneLink()
        link._start_log()
        try:
            path = link._logfile.name
            assert "/logs/" in path or "\\logs\\" in path
        finally:
            link._stop_log()


# ---------------------------------------------------------------------------
# TestGetVehicleInfo
# ---------------------------------------------------------------------------


class TestGetVehicleInfo:
    def test_copter_zh(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 2
        link.locale = "zh"
        modes, btns, name = link._get_vehicle_info()
        assert name == "多旋翼"

    def test_copter_en(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 2
        link.locale = "en"
        modes, btns, name = link._get_vehicle_info()
        assert name == "Multirotor"

    def test_plane_zh(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 1
        link.locale = "zh"
        modes, btns, name = link._get_vehicle_info()
        assert name == "固定翼"

    def test_plane_en(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 1
        link.locale = "en"
        modes, btns, name = link._get_vehicle_info()
        assert name == "Fixed Wing"

    def test_rover_zh(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 10
        link.locale = "zh"
        modes, btns, name = link._get_vehicle_info()
        assert name == "地面车"

    def test_rover_en(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 10
        link.locale = "en"
        modes, btns, name = link._get_vehicle_info()
        assert name == "Rover"

    def test_sub_zh(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 12
        link.locale = "zh"
        modes, btns, name = link._get_vehicle_info()
        assert name == "水下机器人"

    def test_sub_en(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 12
        link.locale = "en"
        modes, btns, name = link._get_vehicle_info()
        assert name == "Sub"

    def test_unknown_vtype_defaults_copter(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 0
        modes, btns, name = link._get_vehicle_info()
        # vtype 0 returns empty name
        assert name == ""

    def test_force_plane_overrides_vehicle_info(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 2  # copter
        link.vehicle.force_plane = True
        link.locale = "en"
        modes, btns, name = link._get_vehicle_info()
        assert name == "Fixed Wing"

    def test_force_copter_overrides_vehicle_info(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 1  # plane
        link.vehicle.force_plane = False
        link.locale = "en"
        modes, btns, name = link._get_vehicle_info()
        assert name == "Multirotor"


# ---------------------------------------------------------------------------
# TestProcess
# ---------------------------------------------------------------------------


class TestProcess:
    def test_process_rejects_short_payload(self):
        """Payloads shorter than 12 bytes are ignored."""
        link = DroneLink()
        link._process(b"\xfd\x00")
        assert link.last_frame_time == 0.0

    def test_process_rejects_non_mavlink(self):
        """Payloads not starting with 0xFD are ignored."""
        link = DroneLink()
        link._process(b"\x00" * 20)
        assert link.last_frame_time == 0.0

    def test_process_updates_last_frame_time(self):
        link = DroneLink()
        frame = _build_mavlink_frame(link, msg_id=30, payload=b"\x00" * 28)
        before = time.time()
        link._process(frame)
        assert link.last_frame_time >= before

    def test_process_updates_raw_sysid(self):
        link = DroneLink()
        frame = _build_mavlink_frame(link, msg_id=30, payload=b"\x00" * 28, sysid=7)
        link._process(frame)
        assert link._raw_sysid == 7

    def test_process_heartbeat_tracks_vehicle(self):
        """HEARTBEAT (msg_id=0) updates _vehicles dict."""
        link = DroneLink()
        hb_payload = _build_heartbeat_payload(mode=5, vtype=2, armed=True)
        frame = _build_mavlink_frame(link, msg_id=0, payload=hb_payload, sysid=3)
        link._process(frame)
        assert 3 in link._vehicles
        v = link._vehicles[3]
        assert v["sysid"] == 3
        assert v["armed"] is True
        assert v["vtype"] == 2

    def test_process_global_position_tracks_vehicle(self):
        """GLOBAL_POSITION_INT (msg_id=33) updates _vehicles dict."""
        link = DroneLink()
        gp_payload = _build_global_position_int_payload(lat_deg=30.5, lon_deg=120.3, alt_m=150.0, hdg_deg=45.0)
        frame = _build_mavlink_frame(link, msg_id=33, payload=gp_payload, sysid=5)
        link._process(frame)
        assert 5 in link._vehicles
        v = link._vehicles[5]
        assert v["sysid"] == 5
        assert abs(v["lat"] - 30.5) < 0.001
        assert abs(v["lon"] - 120.3) < 0.001
        assert abs(v["hdg"] - 45.0) < 1.0

    def test_process_inspector_stats(self):
        """When inspector_enabled, _process updates _msg_stats."""
        link = DroneLink()
        link.inspector_enabled = True
        hb_payload = _build_heartbeat_payload()
        frame = _build_mavlink_frame(link, msg_id=0, payload=hb_payload)
        link._process(frame)
        assert 0 in link._msg_stats
        st = link._msg_stats[0]
        assert st["count"] == 1
        assert st["name"] == "HEARTBEAT"

    def test_process_inspector_stats_increments(self):
        link = DroneLink()
        link.inspector_enabled = True
        hb_payload = _build_heartbeat_payload()
        frame = _build_mavlink_frame(link, msg_id=0, payload=hb_payload)
        link._process(frame)
        link._process(frame)
        assert link._msg_stats[0]["count"] == 2

    def test_process_inspector_disabled_no_stats(self):
        link = DroneLink()
        link.inspector_enabled = False
        hb_payload = _build_heartbeat_payload()
        frame = _build_mavlink_frame(link, msg_id=0, payload=hb_payload)
        link._process(frame)
        assert link._msg_stats == {}

    def test_process_inspector_trims_times(self):
        """Inspector stats trims times list when it exceeds 100 entries."""
        link = DroneLink()
        link.inspector_enabled = True
        hb_payload = _build_heartbeat_payload()
        frame = _build_mavlink_frame(link, msg_id=0, payload=hb_payload)
        for _ in range(110):
            link._process(frame)
        assert len(link._msg_stats[0]["times"]) <= 100

    def test_process_calls_dispatch(self):
        """_process calls mavlink_dispatch.dispatch."""
        link = DroneLink()
        hb_payload = _build_heartbeat_payload()
        frame = _build_mavlink_frame(link, msg_id=0, payload=hb_payload)
        with patch("backend.drone_link.mavlink_dispatch.dispatch") as mock_disp:
            link._process(frame)
            mock_disp.assert_called_once()
            args = mock_disp.call_args[0]
            assert args[0] == 0  # msg_id
            assert args[3] is link


# ---------------------------------------------------------------------------
# TestGetInspectorData
# ---------------------------------------------------------------------------


class TestGetInspectorData:
    def test_returns_list(self):
        link = DroneLink()
        data = link.get_inspector_data()
        assert isinstance(data, list)

    def test_reflects_msg_stats(self):
        link = DroneLink()
        link._msg_stats[0] = {
            "name": "HEARTBEAT",
            "count": 100,
            "size": 9,
            "times": [time.time()] * 5,
            "last_fields": {},
        }
        data = link.get_inspector_data()
        assert len(data) >= 1
        assert data[0]["name"] == "HEARTBEAT"
        assert data[0]["count"] == 100
        assert data[0]["hz"] > 0

    def test_stale_times_pruned(self):
        """Times older than _msg_stats_window are pruned."""
        link = DroneLink()
        old_time = time.time() - link._msg_stats_window - 1.0
        link._msg_stats[0] = {
            "name": "HEARTBEAT",
            "count": 50,
            "size": 9,
            "times": [old_time] * 5,
            "last_fields": {},
        }
        data = link.get_inspector_data()
        assert data[0]["hz"] == 0.0

    def test_sorted_by_msg_id(self):
        link = DroneLink()
        now = time.time()
        link._msg_stats[33] = {
            "name": "GLOBAL_POSITION_INT",
            "count": 10,
            "size": 28,
            "times": [now],
            "last_fields": {},
        }
        link._msg_stats[0] = {"name": "HEARTBEAT", "count": 20, "size": 9, "times": [now], "last_fields": {}}
        data = link.get_inspector_data()
        assert data[0]["id"] == 0
        assert data[1]["id"] == 33


# ---------------------------------------------------------------------------
# TestNextFrame
# ---------------------------------------------------------------------------


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

    def test_auto_detection_adds_event_standard(self):
        link = DroneLink()
        link._protocol = "auto"
        link._buf = b"\xfd\x09\x00\x00\x01\x01\x01\x00\x00\x00" + b"\x00" * 11
        link._next_frame()
        proto_events = [e for e in link.events if e["event_type"] == "proto_std"]
        assert len(proto_events) == 1

    def test_auto_detection_adds_event_pllink(self):
        link = DroneLink()
        link._protocol = "auto"
        from backend.pllink_proto import ple

        link._buf = ple(b"\xfd\x09\x00\x00\x01\x01\x01\x00\x00\x00", 0)
        link._next_frame()
        proto_events = [e for e in link.events if e["event_type"] == "proto_pllink"]
        assert len(proto_events) == 1

    def test_already_standard_skips_detection(self):
        link = DroneLink()
        link._protocol = "standard"
        link._buf = b"\x50\x4c" + b"\x00" * 20  # looks like PL-Link
        link._next_frame()
        assert link._protocol == "standard"  # unchanged

    def test_already_pllink_skips_detection(self):
        link = DroneLink()
        link._protocol = "pllink"
        link._buf = b"\xfd\x09\x00\x00\x01\x01\x01\x00\x00\x00" + b"\x00" * 11
        link._next_frame()
        assert link._protocol == "pllink"  # unchanged

    def test_auto_needs_at_least_2_bytes(self):
        link = DroneLink()
        link._protocol = "auto"
        link._buf = b"\xfd"
        link._next_frame()
        # Not enough data for detection, stays auto
        assert link._protocol == "auto"


# ---------------------------------------------------------------------------
# TestParseMavlinkFrame
# ---------------------------------------------------------------------------


class TestParseMavlinkFrame:
    def test_valid_frame_parsed(self):
        link = DroneLink()
        frame = _build_mavlink_frame(link, msg_id=0, payload=b"\x00" * 9)
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
        assert skip == 2

    def test_incomplete_header(self):
        link = DroneLink()
        link._buf = b"\xfd\x09\x00"
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip == 0

    def test_incomplete_payload(self):
        """Frame with payload_len indicating more data than available."""
        link = DroneLink()
        # header says 50-byte payload but we only provide 10
        link._buf = b"\xfd\x32\x00\x00\x01\x01\x01\x00\x00\x00" + b"\x00" * 10
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip == 0  # need more data

    def test_bad_crc_rejected(self):
        link = DroneLink()
        frame = bytearray(_build_mavlink_frame(link, msg_id=0))
        frame[-1] ^= 0xFF
        link._buf = bytes(frame)
        result, skip = link._parse_mavlink_frame()
        assert result is None
        assert skip == 1

    def test_signature_flag_extends_frame(self):
        """Frame with signature flag requires 13 extra bytes."""
        link = DroneLink()
        payload = b"\x00" * 9
        header = bytes(
            [
                len(payload),
                0x01,
                0,  # incompat_flags=0x01 means signature present
                0,
                1,
                1,
                0,
                0,
                0,
            ]
        )
        crc_extra = _CRC_EXTRA.get(0, 0)
        crc = link._mavlink_crc16(header + payload + bytes([crc_extra]))
        frame = b"\xfd" + header + payload + struct.pack("<H", crc) + b"\x00" * 13
        link._buf = frame
        result, consumed = link._parse_mavlink_frame()
        # Frame includes signature area
        assert consumed == 12 + 9 + 13


# ---------------------------------------------------------------------------
# TestLoop
# ---------------------------------------------------------------------------


class TestLoop:
    def test_loop_sends_heartbeat(self):
        """_loop sends heartbeat via commands module."""
        link = DroneLink()
        link._running = True
        mock_ser = MagicMock(in_waiting=0)
        mock_ser.read.return_value = b""
        link._ser = mock_ser

        call_count = 0

        def stop_after_one(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                link._running = False

        with (
            patch("backend.drone_link.cmd_module.send_heartbeat") as mock_hb,
            patch("backend.drone_link.cmd_module.request_streams"),
            patch("backend.drone_link.time.sleep", side_effect=stop_after_one),
        ):
            link._loop()
            mock_hb.assert_called()

    def test_loop_runs_log_dl_stall_checker(self):
        """_loop must actually invoke check_log_dl_stall each tick — the six
        stall tests call the function directly, so without this anchor the
        main-loop wiring line could be deleted and the suite would stay green
        while a real stalled download hung forever."""
        link = DroneLink()
        link._running = True
        mock_ser = MagicMock(in_waiting=0)
        mock_ser.read.return_value = b""
        link._ser = mock_ser

        def stop(*a, **kw):
            link._running = False

        with (
            patch("backend.drone_link.cmd_module.send_heartbeat"),
            patch("backend.drone_link.cmd_module.request_streams"),
            patch("backend.mavlink_handlers.check_log_dl_stall") as mock_chk,
            patch("backend.drone_link.time.sleep", side_effect=stop),
        ):
            link._loop()
        mock_chk.assert_called_with(link)

    def test_loop_read_size_tracks_in_waiting(self):
        """The read loop drains in_waiting (capped 64 KB) instead of a fixed
        1024 B/tick — that fixed read + 20 ms sleep capped intake at ~50 KB/s
        and throttled log downloads regardless of protocol. Without this
        anchor the batching could silently regress to read(1024) and the
        suite would stay green while downloads crawled again."""
        for avail, expected in [(0, 1024), (500, 1024), (50000, 50000), (70000, 65536)]:
            link = DroneLink()
            link._running = True
            sizes: list[int] = []
            mock_ser = MagicMock(in_waiting=avail)

            def mock_read(n, _sizes=sizes, _link=link):
                _sizes.append(n)
                _link._running = False
                return b""

            mock_ser.read = mock_read
            link._ser = mock_ser
            with (
                patch("backend.drone_link.cmd_module.send_heartbeat"),
                patch("backend.drone_link.cmd_module.request_streams"),
                patch("backend.drone_link.time.sleep"),
            ):
                link._loop()
            assert sizes == [expected], f"in_waiting={avail} → read({sizes}), expected [{expected}]"

    def test_loop_read_size_survives_missing_in_waiting(self):
        """A wrapper without in_waiting (getattr default 0) must fall back to
        read(1024), never crash — UdpWrapper/ReplayWrapper lack the property."""
        link = DroneLink()
        link._running = True
        sizes: list[int] = []

        class NoInWaiting:
            def read(self, n):
                sizes.append(n)
                link._running = False
                return b""

        link._ser = NoInWaiting()
        with (
            patch("backend.drone_link.cmd_module.send_heartbeat"),
            patch("backend.drone_link.cmd_module.request_streams"),
            patch("backend.drone_link.time.sleep"),
        ):
            link._loop()
        assert sizes == [1024]

    def test_loop_reads_serial_data(self):
        """_loop reads data from serial port and appends to _buf."""
        link = DroneLink()
        link._running = True
        mock_ser = MagicMock(in_waiting=0)

        call_count = 0

        def mock_read(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"\xaa\xbb"
            link._running = False
            return b""

        mock_ser.read = mock_read
        link._ser = mock_ser
        link._protocol = "standard"

        with (
            patch("backend.drone_link.cmd_module.send_heartbeat"),
            patch("backend.drone_link.cmd_module.request_streams"),
            patch("backend.drone_link.time.sleep"),
        ):
            link._loop()

    def test_loop_handles_oserror_on_read(self):
        """_loop catches OSError from serial read."""
        link = DroneLink()
        link._running = True
        mock_ser = MagicMock(in_waiting=0)

        call_count = 0

        def mock_read(n):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise OSError("read fail")
            link._running = False
            return b""

        mock_ser.read = mock_read
        link._ser = mock_ser

        with (
            patch("backend.drone_link.cmd_module.send_heartbeat"),
            patch("backend.drone_link.cmd_module.request_streams"),
            patch("backend.drone_link.time.sleep"),
        ):
            link._loop()  # should not raise

    def test_loop_buffer_overflow_trimmed(self):
        """Buffer is trimmed when it exceeds 65536 bytes."""
        link = DroneLink()
        link._running = True
        link._protocol = "standard"
        mock_ser = MagicMock(in_waiting=0)

        call_count = 0

        def mock_read(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"\x00" * 70000
            link._running = False
            return b""

        mock_ser.read = mock_read
        link._ser = mock_ser

        with (
            patch("backend.drone_link.cmd_module.send_heartbeat"),
            patch("backend.drone_link.cmd_module.request_streams"),
            patch("backend.drone_link.time.sleep"),
        ):
            link._loop()
        assert len(link._buf) <= 65536
        assert link._parse_errors >= 1

    def test_loop_heartbeat_timeout_detection(self):
        """_loop detects heartbeat timeout and sets connected=False."""
        link = DroneLink()
        link._running = True
        link.connected = True
        link.last_frame_time = time.time() - cfg.LINK_LOST_TIMEOUT - 1.0
        link._reconnect_enabled = False  # disable auto-reconnect for this test
        mock_ser = MagicMock(in_waiting=0)
        mock_ser.read.return_value = b""
        link._ser = mock_ser

        call_count = 0

        def stop_sleep(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                link._running = False

        with (
            patch("backend.drone_link.cmd_module.send_heartbeat"),
            patch("backend.drone_link.cmd_module.request_streams"),
            patch("backend.drone_link.time.sleep", side_effect=stop_sleep),
        ):
            link._loop()
        assert link.connected is False
        lost_events = [e for e in link.events if e["event_type"] == "link_lost"]
        assert len(lost_events) >= 1

    def test_loop_auto_reconnect_on_timeout(self):
        """_loop attempts reconnect when link is lost and reconnect enabled."""
        link = DroneLink()
        link._running = True
        link.connected = True
        link.last_frame_time = time.time() - cfg.LINK_LOST_TIMEOUT - 1.0
        link._reconnect_enabled = True
        link._last_port = "tcp:localhost:5770"
        link._last_baud = 57600
        mock_ser = MagicMock(in_waiting=0)
        mock_ser.read.return_value = b""
        link._ser = mock_ser

        new_ser = MagicMock(in_waiting=0)
        new_ser.read.return_value = b""

        call_count = 0

        def stop_sleep(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                link._running = False

        with (
            patch.object(link, "_open_port", return_value=new_ser) as mock_open,
            patch("backend.drone_link.cmd_module.send_heartbeat"),
            patch("backend.drone_link.cmd_module.request_streams"),
            patch("backend.drone_link.time.sleep", side_effect=stop_sleep),
        ):
            link._loop()
        mock_open.assert_called_with("tcp:localhost:5770", 57600)
        reconn_events = [e for e in link.events if e["event_type"] == "reconnected"]
        assert len(reconn_events) >= 1

    def test_loop_reconnect_failure(self):
        """_loop handles OSError during reconnect attempt."""
        link = DroneLink()
        link._running = True
        link.connected = True
        link.last_frame_time = time.time() - cfg.LINK_LOST_TIMEOUT - 1.0
        link._reconnect_enabled = True
        link._last_port = "tcp:localhost:5770"
        link._last_baud = 57600
        mock_ser = MagicMock(in_waiting=0)
        mock_ser.read.return_value = b""
        link._ser = mock_ser

        call_count = 0

        def stop_sleep(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                link._running = False

        with (
            patch.object(link, "_open_port", side_effect=OSError("fail")),
            patch("backend.drone_link.cmd_module.send_heartbeat"),
            patch("backend.drone_link.cmd_module.request_streams"),
            patch("backend.drone_link.time.sleep", side_effect=stop_sleep),
        ):
            link._loop()
        fail_events = [e for e in link.events if e["event_type"] == "reconnect_fail"]
        assert len(fail_events) >= 1

    def test_loop_reconnect_retries_with_backoff_not_single_shot(self):
        """Regression: a FAILED reconnect keeps retrying _open_port with
        exponential backoff — it must NOT strand the link after one attempt.
        The reconnect used to sit behind `if self.connected`, which
        _reset_session_state flips False, so _open_port fired exactly once and
        the W1 backoff never advanced past attempt 1 (dead code)."""
        link = DroneLink()
        link._running = True
        link.connected = True
        link.last_frame_time = time.time() - cfg.LINK_LOST_TIMEOUT - 1.0
        link._reconnect_enabled = True
        link._last_port = "tcp:localhost:5770"
        link._last_baud = 57600
        mock_ser = MagicMock(in_waiting=0)
        mock_ser.read.side_effect = OSError("closed")
        link._ser = mock_ser

        delays: list[float] = []

        def stop_sleep(d=0, *a, **kw):
            delays.append(d)
            if len(delays) > 6:
                link._running = False

        with (
            patch.object(link, "_open_port", side_effect=OSError("down")) as mock_open,
            patch("backend.drone_link.cmd_module.send_heartbeat"),
            patch("backend.drone_link.cmd_module.request_streams"),
            patch("backend.drone_link.time.sleep", side_effect=stop_sleep),
        ):
            link._loop()
        assert mock_open.call_count >= 3, "reconnect must retry, not single-shot"
        # Backoff = min(RECONNECT_DELAY * 2**min(n,5), 60): first step, non-decreasing, capped.
        assert delays[0] == min(cfg.RECONNECT_DELAY * 2, 60.0)
        assert delays == sorted(delays)
        assert max(delays) <= 60.0

    def test_loop_reconnect_recovers_after_transient_failure(self):
        """A port that fails a couple reopen attempts then returns must
        reconnect, reset the backoff counter, and clear _reconnecting — a brief
        USB glitch auto-recovers instead of stranding on a closed serial."""
        link = DroneLink()
        link._running = True
        link.connected = True
        link.last_frame_time = time.time() - cfg.LINK_LOST_TIMEOUT - 1.0
        link._reconnect_enabled = True
        link._last_port = "tcp:localhost:5770"
        link._last_baud = 57600
        old_ser = MagicMock(in_waiting=0)
        old_ser.read.side_effect = OSError("closed")
        link._ser = old_ser
        new_ser = MagicMock(in_waiting=0)
        new_ser.read.return_value = b""

        opens = {"n": 0}

        def open_side_effect(*a, **kw):
            opens["n"] += 1
            if opens["n"] < 3:
                raise OSError("still down")
            return new_ser

        sleeps = {"n": 0}

        def stop_sleep(*a, **kw):
            sleeps["n"] += 1
            if sleeps["n"] > 6:
                link._running = False

        with (
            patch.object(link, "_open_port", side_effect=open_side_effect),
            patch("backend.drone_link.cmd_module.send_heartbeat"),
            patch("backend.drone_link.cmd_module.request_streams"),
            patch("backend.drone_link.time.sleep", side_effect=stop_sleep),
        ):
            link._loop()
        assert link._reconnecting is False
        assert link._reconnect_attempts == 0
        assert link._ser is new_ser
        reconn = [e for e in link.events if e["event_type"] == "reconnected"]
        assert len(reconn) == 1

    def test_loop_normal_tick_runs_both_watchdogs(self):
        """Every normal tick calls the param AND mission-download watchdogs;
        dropping either would silently strand a pending fetch/download."""
        link = DroneLink()
        link._running = True
        link.connected = True
        link.last_frame_time = time.time()  # fresh — no link-lost
        mock_ser = MagicMock(in_waiting=0)
        mock_ser.read.return_value = b""
        link._ser = mock_ser

        def stop_sleep(*a, **kw):
            link._running = False

        with (
            patch("backend.drone_link.cmd_module.send_heartbeat"),
            patch("backend.drone_link.cmd_module.request_streams"),
            patch("backend.drone_link.time.sleep", side_effect=stop_sleep),
            patch.object(link.param_mgr, "check_timeout") as mock_pt,
            patch.object(link, "_check_mission_dl_timeout") as mock_mt,
            patch.object(link, "feed"),
            patch.object(link, "_write_log_line"),
        ):
            link._loop()
        mock_pt.assert_called()
        mock_mt.assert_called()

    def test_loop_request_streams_when_not_connected(self):
        """_loop requests streams when not connected and frame_count < 3."""
        link = DroneLink()
        link._running = True
        link.connected = False
        link.frame_count = 0
        mock_ser = MagicMock(in_waiting=0)
        mock_ser.read.return_value = b""
        link._ser = mock_ser

        call_count = 0

        def stop_sleep(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                link._running = False

        with (
            patch("backend.drone_link.cmd_module.send_heartbeat"),
            patch("backend.drone_link.cmd_module.request_streams") as mock_streams,
            patch("backend.drone_link.time.sleep", side_effect=stop_sleep),
        ):
            link._loop()
            mock_streams.assert_called()

    def test_loop_processes_valid_frame(self):
        """_loop processes a valid frame and increments frame_count."""
        link = DroneLink()
        link._running = True
        link._protocol = "standard"
        hb_payload = _build_heartbeat_payload(mode=3, vtype=2)
        frame = _build_mavlink_frame(link, msg_id=0, payload=hb_payload)
        mock_ser = MagicMock(in_waiting=0)

        call_count = 0

        def mock_read(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return frame
            link._running = False
            return b""

        mock_ser.read = mock_read
        link._ser = mock_ser

        with (
            patch("backend.drone_link.cmd_module.send_heartbeat"),
            patch("backend.drone_link.cmd_module.request_streams"),
            patch("backend.drone_link.time.sleep"),
        ):
            link._loop()
        assert link.frame_count >= 1

    def test_loop_parse_error_increments_counter(self):
        """_loop increments _parse_errors on struct/value/index errors in _process."""
        link = DroneLink()
        link._running = True
        link._protocol = "standard"
        hb_payload = _build_heartbeat_payload()
        frame = _build_mavlink_frame(link, msg_id=0, payload=hb_payload)
        mock_ser = MagicMock(in_waiting=0)

        call_count = 0

        def mock_read(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return frame
            link._running = False
            return b""

        mock_ser.read = mock_read
        link._ser = mock_ser

        with (
            patch.object(link, "_process", side_effect=struct.error("bad")),
            patch("backend.drone_link.cmd_module.send_heartbeat"),
            patch("backend.drone_link.cmd_module.request_streams"),
            patch("backend.drone_link.time.sleep"),
        ):
            link._loop()
        assert link._parse_errors >= 1


# ---------------------------------------------------------------------------
# TestThreadSafety
# ---------------------------------------------------------------------------


class TestDroneLinkThreadSafety:
    def test_concurrent_get_state(self):
        link = DroneLink()
        results = []
        errors = []

        def worker():
            try:
                for _ in range(50):
                    s = link.get_state()
                    results.append(s["type"])
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert len(results) == 200

    def test_concurrent_add_event(self):
        link = DroneLink()
        errors = []

        def worker(n):
            try:
                for i in range(50):
                    link.add_event(f"thread-{n}-event-{i}", "test")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0

    def test_concurrent_state_mutation_and_read(self):
        """Concurrent state writes and reads do not raise."""
        link = DroneLink()
        errors = []

        def writer():
            try:
                for i in range(100):
                    with link._state_lock:
                        link.attitude.roll = float(i)
                        link.battery.voltage = 10.0 + i * 0.01
            except Exception as e:
                errors.append(str(e))

        def reader():
            try:
                for _ in range(100):
                    s = link.get_state()
                    assert isinstance(s["roll"], float)
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
        assert len(errors) == 0

    def test_concurrent_send(self):
        """Multiple threads can call send() without error."""
        mock_ser = MagicMock(in_waiting=0)
        link = DroneLink()
        link._ser = mock_ser
        link._protocol = "standard"
        errors = []

        def sender(n):
            try:
                for _i in range(50):
                    link.send(b"\xfd\x00\x00")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=sender, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# TestCrcExtraAndMsgNames
# ---------------------------------------------------------------------------


class TestModuleLevelConstants:
    def test_crc_extra_has_heartbeat(self):
        assert 0 in _CRC_EXTRA

    def test_msg_names_has_heartbeat(self):
        assert _MSG_NAMES[0] == "HEARTBEAT"

    def test_msg_names_has_global_position(self):
        assert _MSG_NAMES[33] == "GLOBAL_POSITION_INT"

    def test_crc_extra_values_are_ints(self):
        for _mid, ce in _CRC_EXTRA.items():
            assert isinstance(ce, int)
            assert 0 <= ce <= 255


# ---------------------------------------------------------------------------
# TestQueueWs
# ---------------------------------------------------------------------------


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

    def test_trims_preserves_recent(self):
        link = DroneLink()
        for i in range(2100):
            link.queue_ws({"i": i})
        # After trim, the last entries should be the most recent
        assert link._ws_queue[-1]["i"] == 2099
