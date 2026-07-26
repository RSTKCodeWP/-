"""Unit tests: MAVLink handler coverage for uncovered paths.

Targets the 66 uncovered lines identified by --cov-report=term-missing:
  - Short payload guards (early returns)
  - mag_cal_progress / mag_cal_report state machines
  - Mission download completion (CMD 178 speed, CMD 181 relay, overflow)
  - Mission request: fence / rally item dispatch
  - Mission ack: fence fail, rally ack
  - Battery time-remaining estimation
  - Log download: 64KB chunking, progress messages, overflow trimming
  - Statustext dedup, empty text, short payload
  - Command ack calibration suppression
  - Global position armed tracking with _prev_pos
"""

from __future__ import annotations

import struct
import time
from unittest.mock import MagicMock

from backend.drone_link import DroneLink
from backend.mavlink_handlers import (
    _emit_log_chunks,
    _finalize_log_download,
    handle_adsb_vehicle,
    handle_attitude,
    handle_autopilot_version,
    handle_battery_status,
    handle_command_ack,
    handle_ekf_status,
    handle_gimbal_device_attitude_status,
    handle_global_position_int,
    handle_gps_raw_int,
    handle_home_position,
    handle_log_data,
    handle_log_entry,
    handle_mag_cal_progress,
    handle_mag_cal_report,
    handle_mission_ack,
    handle_mission_current,
    handle_mission_item_int,
    handle_mission_item_reached,
    handle_mission_request,
    handle_mount_status,
    handle_rc_channels,
    handle_serial_control,
    handle_servo_output,
    handle_statustext,
    handle_sys_status,
    handle_terrain_report,
    handle_vfr_hud,
    handle_vibration,
    handle_wind,
)


def make_link() -> DroneLink:
    link = DroneLink()
    return link


def make_link_connected() -> DroneLink:
    link = DroneLink()
    link._ser = MagicMock()
    link.connected = True
    link.vehicle.sysid = 1
    return link


# ---------------------------------------------------------------------------
# Short-payload early returns (each hits the `if pl < N: return` branch)
# ---------------------------------------------------------------------------


class TestShortPayloadReturns:
    """Cover every handler's short-payload guard that was previously untested."""

    def test_attitude_empty(self):
        link = make_link()
        handle_attitude(b"", 0, link)
        assert link.attitude.roll == 0.0

    def test_global_position_int_empty(self):
        link = make_link()
        handle_global_position_int(b"", 0, link)
        assert link.attitude.lat == 0.0

    def test_gps_raw_int_empty(self):
        link = make_link()
        handle_gps_raw_int(b"", 0, link)
        assert link.gps.gps_fix == 0

    def test_mission_current_empty(self):
        link = make_link()
        handle_mission_current(b"", 0, link)
        assert link.mission.wp_seq == 0

    def test_home_position_empty(self):
        link = make_link()
        handle_home_position(b"", 0, link)
        assert link.attitude.home_lat == 0.0

    def test_mission_item_reached_empty(self):
        link = make_link()
        handle_mission_item_reached(b"", 0, link)
        assert len(link.events) == 0

    def test_command_ack_too_short(self):
        link = make_link()
        handle_command_ack(b"\x00", 1, link)
        assert len(link.events) == 0

    def test_statustext_too_short(self):
        link = make_link()
        handle_statustext(b"\x06", 1, link)
        assert len(link.events) == 0

    def test_servo_output_too_short(self):
        link = make_link()
        handle_servo_output(b"\x00" * 5, 5, link)
        assert link.rc_servo.servo_out == [0] * 16

    def test_rc_channels_too_short(self):
        link = make_link()
        handle_rc_channels(b"\x00" * 5, 5, link)
        assert link.rc_servo.rc_channels == [0] * 16

    def test_vibration_too_short(self):
        link = make_link()
        handle_vibration(b"\x00" * 11, 11, link)
        assert link.diagnostic.vibe_x == 0.0

    def test_vfr_hud_too_short(self):
        link = make_link()
        handle_vfr_hud(b"\x00" * 3, 3, link)
        assert link.attitude.airspeed == 0.0

    def test_ekf_status_empty(self):
        link = make_link()
        handle_ekf_status(b"", 0, link)
        assert link.diagnostic.ekf_vel_var == 0.0

    def test_mount_status_empty(self):
        link = make_link()
        handle_mount_status(b"", 0, link)
        assert link.diagnostic.gimbal_pitch == 0.0

    def test_gimbal_device_attitude_status_short(self):
        link = make_link()
        handle_gimbal_device_attitude_status(b"\x00" * 10, 10, link)
        assert link.diagnostic.gimbal_pitch == 0.0

    def test_gimbal_device_attitude_status_identity_quat(self):
        link = make_link()
        # Identity quaternion [w=1, x=0, y=0, z=0] → pitch=0, yaw=0
        p = struct.pack("<I", 0)  # time_boot_ms
        p += struct.pack("<4f", 1.0, 0.0, 0.0, 0.0)  # q[w,x,y,z]
        p += struct.pack("<3f", 0.0, 0.0, 0.0)  # angular velocities
        p += struct.pack("<I", 0)  # failure_flags
        handle_gimbal_device_attitude_status(p, len(p), link)
        assert abs(link.diagnostic.gimbal_pitch) < 0.1
        assert abs(link.diagnostic.gimbal_yaw) < 0.1

    def test_gimbal_device_attitude_status_pitched_down(self):
        link = make_link()
        import math

        # 45° pitch down: w=cos(22.5°), x=0, y=sin(22.5°), z=0
        angle = math.radians(45)
        w = math.cos(angle / 2)
        y = math.sin(angle / 2)
        p = struct.pack("<I", 1000)
        p += struct.pack("<4f", w, 0.0, y, 0.0)
        p += struct.pack("<3f", 0.0, 0.0, 0.0)
        p += struct.pack("<I", 0)
        handle_gimbal_device_attitude_status(p, len(p), link)
        assert abs(link.diagnostic.gimbal_pitch - 45.0) < 0.5

    def test_terrain_report_empty(self):
        link = make_link()
        handle_terrain_report(b"", 0, link)
        assert link.diagnostic.terrain_alt == -1.0

    def test_wind_empty(self):
        link = make_link()
        handle_wind(b"", 0, link)
        assert link.diagnostic.wind_dir == 0.0

    def test_autopilot_version_empty(self):
        link = make_link()
        handle_autopilot_version(b"", 0, link)
        assert link.vehicle.fw_version == ""

    def test_mission_request_empty(self):
        link = make_link()
        handle_mission_request(b"", 0, link)
        # no crash

    def test_log_entry_empty(self):
        link = make_link()
        handle_log_entry(b"", 0, link)
        assert len(link.log_dl._log_list) == 0

    def test_battery_status_too_short(self):
        link = make_link()
        handle_battery_status(b"\x00" * 9, 9, link)
        assert len(link.battery.battery_cells) == 0

    def test_adsb_vehicle_empty(self):
        link = make_link()
        handle_adsb_vehicle(b"", 0, link)
        assert len(link.traffic._adsb_vehicles) == 0

    def test_serial_control_too_short(self):
        link = make_link()
        handle_serial_control(b"\x00" * 8, 8, link)
        assert len(link._console_buf) == 0


# ---------------------------------------------------------------------------
# Mag cal progress / report state machine
# ---------------------------------------------------------------------------


class TestMagCalProgress:
    def test_progress_adds_event_at_5pct_boundary(self):
        link = make_link()
        # First call at 0%
        p = bytearray(17)
        p[16] = 0
        handle_mag_cal_progress(p, len(p), link)
        assert link._mag_cal_pct == 0

        # Call at 5% -- crosses a 5% boundary
        p[16] = 5
        handle_mag_cal_progress(p, len(p), link)
        assert link._mag_cal_pct == 5
        assert any(e["event_type"] == "cal_compass" for e in link.events)

    def test_progress_skipped_when_done(self):
        link = make_link()
        link._mag_cal_done = True
        p = bytearray(17)
        p[16] = 50
        handle_mag_cal_progress(p, len(p), link)
        assert len(link.events) == 0

    def test_progress_not_emitted_for_same_5pct_band(self):
        link = make_link()
        p = bytearray(17)
        p[16] = 1
        handle_mag_cal_progress(p, len(p), link)
        events_before = len(link.events)
        p[16] = 2  # same 5% band (0-4)
        handle_mag_cal_progress(p, len(p), link)
        assert len(link.events) == events_before


class TestMagCalReport:
    def test_success_report(self):
        link = make_link()
        p = bytearray(44)
        p[42] = 4  # cal_status = SUCCESS
        handle_mag_cal_report(p, len(p), link)
        assert link._mag_cal_done is True
        # Two events: cal done + reboot
        cal_events = [e for e in link.events if e["event_type"] == "cal_compass"]
        assert len(cal_events) == 2

    def test_failure_report(self):
        link = make_link()
        p = bytearray(44)
        p[42] = 2  # cal_status = FAILED
        handle_mag_cal_report(p, len(p), link)
        assert link._mag_cal_done is True
        cal_events = [e for e in link.events if e["event_type"] == "cal_compass"]
        assert len(cal_events) == 1  # just the failure event

    def test_report_skipped_when_already_done(self):
        link = make_link()
        link._mag_cal_done = True
        p = bytearray(44)
        p[42] = 4
        handle_mag_cal_report(p, len(p), link)
        assert len(link.events) == 0

    def test_short_report_ignored(self):
        link = make_link()
        p = bytearray(42)  # too short (needs 43)
        handle_mag_cal_report(p, len(p), link)
        assert not hasattr(link, "_mag_cal_done") or not link._mag_cal_done


# ---------------------------------------------------------------------------
# Command ack: calibration suppression
# ---------------------------------------------------------------------------


class TestCommandAckCalibrationSuppression:
    def test_cal_success_suppressed(self):
        """CMD 241 (cal) with result=0 (success) should NOT generate an event."""
        link = make_link()
        p = struct.pack("<HB", 241, 0)
        handle_command_ack(p, len(p), link)
        assert len(link.events) == 0

    def test_compass_cal_success_suppressed(self):
        """CMD 42424 (compass cal) with result=0 should NOT generate an event."""
        link = make_link()
        p = struct.pack("<HB", 42424, 0)
        handle_command_ack(p, len(p), link)
        assert len(link.events) == 0

    def test_accept_compass_cal_success_suppressed(self):
        """CMD 42425 with result=0 should NOT generate an event."""
        link = make_link()
        p = struct.pack("<HB", 42425, 0)
        handle_command_ack(p, len(p), link)
        assert len(link.events) == 0

    def test_cancel_compass_cal_success_suppressed(self):
        """CMD 42426 with result=0 should NOT generate an event."""
        link = make_link()
        p = struct.pack("<HB", 42426, 0)
        handle_command_ack(p, len(p), link)
        assert len(link.events) == 0

    def test_cal_failure_not_suppressed(self):
        """CMD 241 with result=2 (denied) SHOULD generate an event."""
        link = make_link()
        p = struct.pack("<HB", 241, 2)
        handle_command_ack(p, len(p), link)
        assert len(link.events) == 1
        assert link.events[0]["event_type"] == "cmd_ack_fail"

    def test_unknown_result_text(self):
        """Unknown result code uses fallback text."""
        link = make_link()
        link.locale = "en"
        p = struct.pack("<HB", 400, 99)
        handle_command_ack(p, len(p), link)
        assert "unknown(99)" in link.events[0]["text"]


# ---------------------------------------------------------------------------
# Statustext: empty text, dedup
# ---------------------------------------------------------------------------


class TestStatustextEdgeCases:
    def test_empty_text_ignored(self):
        link = make_link()
        # severity byte + all-zero text (50 bytes)
        p = b"\x06" + b"\x00" * 50
        handle_statustext(p, len(p), link)
        assert len(link.events) == 0

    def test_prearm_dedup(self):
        """Same PreArm message repeated should not add a second event."""
        link = make_link()
        link.locale = "en"
        msg = b"\x06" + b"PreArm: compass not calibrated\x00" + b"\x00" * 19
        handle_statustext(msg, len(msg), link)
        count1 = len(link.events)
        # Same message again
        handle_statustext(msg, len(msg), link)
        assert len(link.events) == count1  # no new event


# ---------------------------------------------------------------------------
# Global position: armed tracking with _prev_pos and max_speed
# ---------------------------------------------------------------------------


class TestGlobalPositionArmedTracking:
    def test_total_dist_accumulated(self):
        link = make_link()
        link.vehicle.armed = True
        link.attitude._home_set = True
        link.attitude.home_lat = 34.0
        link.attitude.home_lon = 108.0

        # First position
        p1 = struct.pack("<IiiiihhhH", 1000, int(34.0 * 1e7), int(108.0 * 1e7), 0, 50_000, 500, 300, 0, 0)
        handle_global_position_int(p1, len(p1), link)
        assert link.attitude._prev_pos is not None

        # Second position slightly different
        p2 = struct.pack("<IiiiihhhH", 2000, int(34.001 * 1e7), int(108.001 * 1e7), 0, 50_000, 500, 300, 0, 0)
        handle_global_position_int(p2, len(p2), link)
        assert link.vehicle.total_dist > 0

    def test_max_speed_tracked(self):
        link = make_link()
        link.vehicle.armed = True
        link.attitude._home_set = True
        link.attitude.home_lat = 34.0
        link.attitude.home_lon = 108.0

        # vx=1000 cm/s = 10 m/s, vy=0
        p = struct.pack("<IiiiihhhH", 1000, int(34.0 * 1e7), int(108.0 * 1e7), 0, 50_000, 1000, 0, 0, 0)
        handle_global_position_int(p, len(p), link)
        assert link.vehicle.max_speed == 10.0


# ---------------------------------------------------------------------------
# Battery time-remaining estimation
# ---------------------------------------------------------------------------


class TestBatteryTimeRemaining:
    def test_bat_time_estimated(self):
        link = make_link()
        link.vehicle.armed = True
        link.battery.remaining = 80
        link.battery._bat_start_pct = 100

        now = time.time()
        # Seed history: 80% at t=now-60, 75% at t=now
        link.battery._bat_history = [(now - 60, 80)]
        # Payload with remaining=75 to create new entry and trigger calc
        p = bytearray(31)
        struct.pack_into("<H", p, 14, 12600)  # 12.6V
        struct.pack_into("<h", p, 16, 500)  # 5A
        struct.pack_into("<b", p, 30, 75)
        # Need dt > 10 and dr > 0
        handle_sys_status(p, 31, link)

        # bat_time_remaining should be set: remaining=75, dr=5 over 60s
        # rate = 5/60 => time_remaining = 75 / (5/60) = 900
        assert link.battery.bat_time_remaining > 0

    def test_bat_history_trimmed_to_120s(self):
        link = make_link()
        link.vehicle.armed = True
        link.battery.remaining = 50

        now = time.time()
        # Add old entries beyond 120s window
        link.battery._bat_history = [(now - 200, 90), (now - 10, 55)]

        p = bytearray(31)
        struct.pack_into("<H", p, 14, 12000)
        struct.pack_into("<h", p, 16, 500)
        struct.pack_into("<b", p, 30, 50)
        handle_sys_status(p, 31, link)

        # Old entry (200s ago) should be trimmed
        for t, _ in link.battery._bat_history:
            assert now - t < 130  # within ~120s + epsilon


# ---------------------------------------------------------------------------
# Mission item int: full download with CMD 178, 181, overflow
# ---------------------------------------------------------------------------


def _make_mission_item(
    seq, cmd, lat=34.0, lon=108.0, alt=100.0, p1=0.0, p2=0.0, p3=0.0, p4=0.0, frame=3, current=0, autocontinue=1
):
    """Build a MISSION_ITEM_INT payload."""
    return struct.pack(
        "<ffffiif HH BBBBB",
        p1,
        p2,
        p3,
        p4,
        int(lat * 1e7),
        int(lon * 1e7),
        alt,
        seq,
        cmd,
        1,
        1,
        frame,
        current,
        autocontinue,
    )


class TestMissionDownloadFull:
    def test_cmd178_sets_speed_on_next_wp(self):
        """DO_CHANGE_SPEED (178) sets pending_speed for the next waypoint."""
        link = make_link()
        link.send = lambda frame: None
        m = link.mission
        m._dl_pending = True
        m._dl_total = 3
        m._dl_items = [None] * 3

        # Item 0: home (cmd=16, seq=0, skipped in wp list)
        p0 = _make_mission_item(0, 16)
        handle_mission_item_int(p0, len(p0), link)

        # Item 1: DO_CHANGE_SPEED with p2=5.0
        p1 = _make_mission_item(1, 178, p2=5.0)
        handle_mission_item_int(p1, len(p1), link)

        # Item 2: waypoint (cmd=16, seq=2) -- last item, triggers completion
        p2 = _make_mission_item(2, 16)
        handle_mission_item_int(p2, len(p2), link)

        assert m._dl_pending is False
        msgs = [msg for msg in m._dl_messages if msg["type"] == "mission_downloaded"]
        assert len(msgs) == 1
        wps = msgs[0]["waypoints"]
        assert len(wps) == 1  # only seq=2, seq=0 is home
        assert wps[0]["speed"] == 5.0

    def test_cmd181_marks_drop(self):
        """DO_SET_RELAY (181) sets drop=True on the preceding waypoint."""
        link = make_link()
        link.send = lambda frame: None
        m = link.mission
        m._dl_pending = True
        m._dl_total = 3
        m._dl_items = [None] * 3

        # Item 0: home
        p0 = _make_mission_item(0, 16)
        handle_mission_item_int(p0, len(p0), link)

        # Item 1: waypoint
        p1 = _make_mission_item(1, 16, lat=34.1, lon=108.1)
        handle_mission_item_int(p1, len(p1), link)

        # Item 2: DO_SET_RELAY (181) -- last item, triggers completion
        p2 = _make_mission_item(2, 181)
        handle_mission_item_int(p2, len(p2), link)

        assert m._dl_pending is False
        wps = m._dl_messages[-1]["waypoints"]
        assert len(wps) == 1
        assert wps[0]["drop"] is True

    def test_loiter_turns_type(self):
        """CMD 18 produces wtype='loiter_turns'."""
        link = make_link()
        link.send = lambda frame: None
        m = link.mission
        m._dl_pending = True
        m._dl_total = 2
        m._dl_items = [None] * 2

        p0 = _make_mission_item(0, 16)
        handle_mission_item_int(p0, len(p0), link)
        p1 = _make_mission_item(1, 18, p1=3.0)
        handle_mission_item_int(p1, len(p1), link)

        wps = m._dl_messages[-1]["waypoints"]
        assert wps[0]["type"] == "loiter_turns"
        assert wps[0]["loiter_param"] == 3.0

    def test_loiter_time_type(self):
        """CMD 19 produces wtype='loiter_time'."""
        link = make_link()
        link.send = lambda frame: None
        m = link.mission
        m._dl_pending = True
        m._dl_total = 2
        m._dl_items = [None] * 2

        p0 = _make_mission_item(0, 16)
        handle_mission_item_int(p0, len(p0), link)
        p1 = _make_mission_item(1, 19, p1=10.0)
        handle_mission_item_int(p1, len(p1), link)

        wps = m._dl_messages[-1]["waypoints"]
        assert wps[0]["type"] == "loiter_time"

    def test_spline_type(self):
        """CMD 82 produces wtype='spline'."""
        link = make_link()
        link.send = lambda frame: None
        m = link.mission
        m._dl_pending = True
        m._dl_total = 2
        m._dl_items = [None] * 2

        p0 = _make_mission_item(0, 16)
        handle_mission_item_int(p0, len(p0), link)
        p1 = _make_mission_item(1, 82)
        handle_mission_item_int(p1, len(p1), link)

        wps = m._dl_messages[-1]["waypoints"]
        assert wps[0]["type"] == "spline"

    def test_dl_messages_overflow_trimmed(self):
        """When _dl_messages exceeds 500, it's trimmed to last 200."""
        link = make_link()
        link.send = lambda frame: None
        m = link.mission
        m._dl_messages = [{"type": "dummy"}] * 500

        m._dl_pending = True
        m._dl_total = 1
        m._dl_items = [None]
        p = _make_mission_item(0, 16)
        handle_mission_item_int(p, len(p), link)

        # After adding mission_downloaded msg, total > 500 => trimmed to 200
        assert len(m._dl_messages) == 200

    def test_not_pending_ignored(self):
        """Mission item int ignored when _dl_pending is False."""
        link = make_link()
        link.mission._dl_pending = False
        p = _make_mission_item(0, 16)
        handle_mission_item_int(p, len(p), link)
        assert link.mission._dl_items == []


# ---------------------------------------------------------------------------
# Mission request: fence and rally dispatch
# ---------------------------------------------------------------------------


class TestMissionRequestFenceRally:
    def test_fence_item_dispatched(self):
        link = make_link_connected()
        link.send = MagicMock()
        m = link.mission
        m._fence_pending = True
        m._fence_items = [
            {
                "seq": 0,
                "frame": 3,
                "cmd": 5001,
                "current": 0,
                "autocontinue": 0,
                "p1": 0,
                "p2": 0,
                "p3": 0,
                "p4": 0,
                "lat": 34.0,
                "lon": 108.0,
                "alt": 100,
            },
        ]
        # seq=0, target_sys=1, target_comp=1, mission_type=1 (fence)
        p = struct.pack("<HBBB", 0, 1, 1, 1)
        p = p[:2] + p[2:]  # Ensure 5 bytes
        p = bytearray(5)
        struct.pack_into("<H", p, 0, 0)  # seq=0
        p[2] = 1  # target_system
        p[3] = 1  # target_component
        p[4] = 1  # mission_type = fence
        handle_mission_request(bytes(p), len(p), link)
        assert m._fence_ul_start_time > 0

    def test_rally_item_dispatched(self):
        link = make_link_connected()
        link.send = MagicMock()
        m = link.mission
        m._rally_pending = True
        m._rally_items = [
            {
                "seq": 0,
                "frame": 3,
                "cmd": 5100,
                "current": 0,
                "autocontinue": 0,
                "p1": 0,
                "p2": 0,
                "p3": 0,
                "p4": 0,
                "lat": 34.0,
                "lon": 108.0,
                "alt": 200,
            },
        ]
        p = bytearray(5)
        struct.pack_into("<H", p, 0, 0)  # seq=0
        p[2] = 1  # target_system
        p[3] = 1  # target_component
        p[4] = 2  # mission_type = rally
        handle_mission_request(bytes(p), len(p), link)
        assert m._rally_ul_start_time > 0

    def test_fence_out_of_range_no_crash(self):
        link = make_link_connected()
        link.send = MagicMock()
        m = link.mission
        m._fence_pending = True
        m._fence_items = []  # empty
        p = bytearray(5)
        struct.pack_into("<H", p, 0, 5)  # seq=5, out of range
        p[4] = 1  # fence
        handle_mission_request(bytes(p), len(p), link)
        # No crash, no send

    def test_rally_out_of_range_no_crash(self):
        link = make_link_connected()
        link.send = MagicMock()
        m = link.mission
        m._rally_pending = True
        m._rally_items = []
        p = bytearray(5)
        struct.pack_into("<H", p, 0, 3)  # seq=3, out of range
        p[4] = 2  # rally
        handle_mission_request(bytes(p), len(p), link)


# ---------------------------------------------------------------------------
# Mission ack: fence fail, rally ack ok/fail
# ---------------------------------------------------------------------------


class TestMissionAckFenceRally:
    def test_fence_ack_fail(self):
        link = make_link()
        m = link.mission
        m._fence_pending = True
        m._fence_ul_start_time = time.time()
        # mtype=3 (error), mission_type=1 (fence)
        p = struct.pack("<BBBB", 1, 1, 3, 1)
        handle_mission_ack(p, len(p), link)
        assert m._fence_pending is False
        assert m._fence_ul_start_time == 0.0
        assert any(e["event_type"] == "fence_ack_fail" for e in link.events)

    def test_rally_ack_ok(self):
        link = make_link()
        m = link.mission
        m._rally_pending = True
        m._rally_ul_start_time = time.time()
        # mtype=0 (accepted), mission_type=2 (rally)
        p = struct.pack("<BBBB", 1, 1, 0, 2)
        handle_mission_ack(p, len(p), link)
        assert m._rally_pending is False
        assert m._rally_ul_start_time == 0.0
        assert any(e["event_type"] == "mission_ack_ok" for e in link.events)

    def test_rally_ack_fail(self):
        link = make_link()
        m = link.mission
        m._rally_pending = True
        m._rally_ul_start_time = time.time()
        # mtype=5 (error), mission_type=2 (rally)
        p = struct.pack("<BBBB", 1, 1, 5, 2)
        handle_mission_ack(p, len(p), link)
        assert m._rally_pending is False
        assert any(e["event_type"] == "mission_ack_fail" for e in link.events)

    def test_mission_ack_fail(self):
        link = make_link()
        m = link.mission
        m._mission_pending = True
        m._mission_ul_start_time = time.time()
        # mtype=2 (error), mission_type=0 (mission)
        p = struct.pack("<BBBB", 1, 1, 2, 0)
        handle_mission_ack(p, len(p), link)
        assert m._mission_pending is False
        assert m._mission_ul_start_time == 0.0
        assert any(e["event_type"] == "mission_ack_fail" for e in link.events)


# ---------------------------------------------------------------------------
# Log download: 64KB chunking, progress messages, overflow trim
# ---------------------------------------------------------------------------


class TestLogChunking:
    def test_emit_log_chunks_streams_64kb(self):
        """_emit_log_chunks emits a chunk when data reaches 64KB."""
        from backend.state import LogState

        lg = LogState()
        lg._log_download_data = bytearray(65536 + 100)
        lg._log_download_ofs = 65536 + 100
        # Chunks stream only from the contiguous prefix — a hole must never
        # ship inside an already-emitted chunk (gap-fill can't amend it).
        lg._log_recv_intervals = [(0, 65536 + 100)]
        lg._log_emit_ofs = 0

        _emit_log_chunks(lg, log_id=5)

        assert len(lg._log_messages) == 1
        assert lg._log_messages[0]["type"] == "log_chunk"
        assert lg._log_messages[0]["id"] == 5
        assert lg._log_messages[0]["ofs"] == 0
        assert lg._log_emit_ofs == 65536

    def test_emit_log_chunks_multiple(self):
        """Emits two chunks when data is >= 128KB."""
        from backend.state import LogState

        lg = LogState()
        size = 65536 * 2 + 50
        lg._log_download_data = bytearray(size)
        lg._log_download_ofs = size
        lg._log_recv_intervals = [(0, size)]
        lg._log_emit_ofs = 0

        _emit_log_chunks(lg, log_id=3)

        assert len(lg._log_messages) == 2
        assert lg._log_emit_ofs == 65536 * 2

    def test_emit_log_chunks_freezes_at_hole(self):
        """A coverage hole freezes chunk emission at the contiguous prefix:
        an already-emitted chunk can never be amended, so zeros must not
        ship while gap-fill can still repair them."""
        from backend.mavlink_handlers import _mark_received
        from backend.state import LogState

        lg = LogState()
        size = 65536 * 2
        lg._log_download_data = bytearray(size)
        lg._log_download_ofs = size  # high-water reached the end...
        lg._log_recv_intervals = [(0, 1000), (1500, size)]  # ...but 1000..1500 missing
        lg._log_emit_ofs = 0

        _emit_log_chunks(lg, log_id=5)
        assert lg._log_messages == []  # nothing may ship past the hole

        _mark_received(lg._log_recv_intervals, 1000, 1500)  # gap-fill lands
        _emit_log_chunks(lg, log_id=5)
        assert len(lg._log_messages) == 2
        assert lg._log_emit_ofs == size

    def test_finalize_emits_trailing_partial_chunk(self):
        """_finalize_log_download emits the last partial chunk + log_complete."""
        link = make_link()
        lg = link.log_dl
        lg._log_download_data = bytearray(b"\xaa" * 1000)
        lg._log_download_ofs = 1000
        # A clean download received every byte — without this the hole
        # detector would (correctly) flag the file as truncated.
        lg._log_recv_intervals = [(0, 1000)]
        lg._log_emit_ofs = 0
        lg._log_download_id = 7

        _finalize_log_download(lg, log_id=7, truncated=False, link=link)

        chunk_msgs = [m for m in lg._log_messages if m["type"] == "log_chunk"]
        complete_msgs = [m for m in lg._log_messages if m["type"] == "log_complete"]
        assert len(chunk_msgs) == 1
        assert chunk_msgs[0]["ofs"] == 0
        assert len(complete_msgs) == 1
        assert complete_msgs[0]["truncated"] is False
        assert complete_msgs[0]["size"] == 1000
        assert lg._log_download_id == -1

    def test_finalize_never_drops_payload_messages(self):
        """The ws drain is an unacked cursor over _log_messages — finalize
        must NOT trim it (the old [-200:] trim silently ate log_chunk
        payload on any download longer than ~500 messages; the frontend
        could never recover those bytes)."""
        link = make_link()
        lg = link.log_dl
        lg._log_messages = [{"type": "log_chunk", "id": 1, "ofs": i, "data": ""} for i in range(600)]
        lg._log_download_data = bytearray(100)
        lg._log_download_ofs = 100
        lg._log_emit_ofs = 0
        lg._log_download_id = 1

        _finalize_log_download(lg, log_id=1, truncated=True, link=link)

        chunks = [m for m in lg._log_messages if m["type"] == "log_chunk"]
        assert len(chunks) == 600 + 1  # every queued chunk + the trailing partial
        assert lg._log_messages[-1]["type"] == "log_complete"


class TestLogDataProgress:
    def test_progress_message_emitted(self):
        """A frame past the throttle window emits a log_progress message
        carrying the covered-byte count."""
        link = make_link()
        link.send = lambda frame: None
        lg = link.log_dl
        lg._log_download_id = 10
        lg._log_download_size = 10000
        lg._log_download_data = bytearray(10000)
        lg._log_download_ofs = 0
        lg._log_last_progress_time = 0.0  # throttle window long expired

        p = struct.pack("<IHB", 0, 10, 10) + bytes(10) + b"\x00" * 80
        handle_log_data(p, len(p), link)

        progress_msgs = [m for m in lg._log_messages if m["type"] == "log_progress"]
        assert len(progress_msgs) == 1
        assert progress_msgs[0]["received"] == 10
        assert progress_msgs[0]["total"] == 10000

    def test_progress_messages_time_throttled(self):
        """Progress is wall-clock throttled, not per-N-frames: a whole-log
        stream delivers thousands of frames per second and a frame-count
        cadence would flood the ws queue (tens of thousands of messages for
        a 28 MB log)."""
        import time as _time

        link = make_link()
        link.send = lambda frame: None
        lg = link.log_dl
        lg._log_download_id = 10
        lg._log_download_size = 100000
        lg._log_download_data = bytearray(100000)
        lg._log_download_ofs = 0
        lg._log_last_progress_time = _time.time()  # window just started

        for i in range(50):  # a burst well inside the throttle window
            p = struct.pack("<IHB", i * 10, 10, 10) + bytes(10) + b"\x00" * 80
            handle_log_data(p, len(p), link)

        assert [m for m in lg._log_messages if m["type"] == "log_progress"] == []

    def test_large_log_with_64kb_streaming(self):
        """Full download >64KB uses chunk streaming."""
        link = make_link()
        link.send = lambda frame: None
        lg = link.log_dl
        total = 65536 + 1000  # just over one chunk
        lg._log_download_id = 1
        lg._log_download_size = total
        lg._log_download_data = bytearray(total)
        lg._log_download_ofs = 0

        # Feed data in 90-byte chunks until complete
        ofs = 0
        while ofs < total:
            chunk_size = min(90, total - ofs)
            data = bytes([ofs & 0xFF] * chunk_size)
            p = struct.pack("<IHB", ofs, 1, chunk_size) + data + b"\x00" * (90 - chunk_size)
            handle_log_data(p, len(p), link)
            ofs += chunk_size

        chunk_msgs = [m for m in lg._log_messages if m["type"] == "log_chunk"]
        complete_msgs = [m for m in lg._log_messages if m["type"] == "log_complete"]
        # At least one streaming chunk (64KB) + trailing partial
        assert len(chunk_msgs) >= 2
        assert len(complete_msgs) == 1
        assert complete_msgs[0]["size"] == total


# ---------------------------------------------------------------------------
# Remaining short-payload guards
# ---------------------------------------------------------------------------


class TestRemainingShortPayloads:
    def test_sys_status_empty(self):
        link = make_link()
        handle_sys_status(b"", 0, link)
        assert link.battery.voltage == 0.0

    def test_mag_cal_progress_empty(self):
        link = make_link()
        handle_mag_cal_progress(b"", 0, link)
        assert not hasattr(link, "_mag_cal_pct")

    def test_mission_ack_empty(self):
        link = make_link()
        handle_mission_ack(b"", 0, link)
        assert len(link.events) == 0


# ---------------------------------------------------------------------------
# Gimbal device attitude status (msg 285)
# ---------------------------------------------------------------------------


class TestGimbalDeviceAttitudeStatus:
    def test_parses_quaternion_to_pitch_yaw(self):
        """Quaternion [1,0,0,0] (identity) maps to pitch=0, yaw=0."""
        link = make_link()
        # time_boot_ms(u32) + q[4](f32x4) + angular_velocity(f32x3) + failure_flags(u32)
        p = struct.pack("<I", 1000)  # time_boot_ms
        p += struct.pack("<4f", 1.0, 0, 0, 0)  # quaternion identity
        p += struct.pack("<3f", 0, 0, 0)  # angular velocity
        p += struct.pack("<I", 0)  # failure_flags
        handle_gimbal_device_attitude_status(p, len(p), link)
        assert abs(link.diagnostic.gimbal_pitch) < 0.1
        assert abs(link.diagnostic.gimbal_yaw) < 0.1

    def test_pitch_down_45(self):
        """Quaternion for 45-degree pitch-down."""
        import math as m

        link = make_link()
        # pitch = -45 degrees about Y axis
        angle = m.radians(-45)
        w = m.cos(angle / 2)
        y = m.sin(angle / 2)
        p = struct.pack("<I", 1000)
        p += struct.pack("<4f", w, 0.0, y, 0.0)
        p += struct.pack("<3f", 0, 0, 0)
        p += struct.pack("<I", 0)
        handle_gimbal_device_attitude_status(p, len(p), link)
        assert abs(link.diagnostic.gimbal_pitch - (-45.0)) < 0.5

    def test_yaw_90(self):
        """Quaternion for 90-degree yaw."""
        import math as m

        link = make_link()
        angle = m.radians(90)
        w = m.cos(angle / 2)
        z = m.sin(angle / 2)
        p = struct.pack("<I", 1000)
        p += struct.pack("<4f", w, 0.0, 0.0, z)
        p += struct.pack("<3f", 0, 0, 0)
        p += struct.pack("<I", 0)
        handle_gimbal_device_attitude_status(p, len(p), link)
        assert abs(link.diagnostic.gimbal_yaw - 90.0) < 0.5

    def test_short_payload_ignored(self):
        link = make_link()
        handle_gimbal_device_attitude_status(b"\x00" * 19, 19, link)
        assert link.diagnostic.gimbal_pitch == 0.0
