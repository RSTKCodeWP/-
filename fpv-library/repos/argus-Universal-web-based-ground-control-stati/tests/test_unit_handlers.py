"""Unit tests: MAVLink message handlers (merged from three test files)."""

from __future__ import annotations

import math
import struct
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.drone_link import DroneLink
from backend.mavlink_handlers import (
    handle_adsb_vehicle,
    handle_attitude,
    handle_autopilot_version,
    handle_battery_status,
    handle_command_ack,
    handle_ekf_status,
    handle_global_position_int,
    handle_gps_raw_int,
    handle_heartbeat,
    handle_home_position,
    handle_log_data,
    handle_log_entry,
    handle_mission_ack,
    handle_mission_count,
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
    """Link with serial mock, connected, sysid=1."""
    link = DroneLink()
    link._ser = MagicMock()
    link.connected = True
    link.vehicle.sysid = 1
    return link


# ── Heartbeat ────────────────────────────────────────────────────────────────


class TestHeartbeat:
    def test_sets_connected(self):
        link = make_link()
        p = struct.pack("<IBBBBB", 5, 2, 3, 0, 0, 3)
        handle_heartbeat(p, len(p), link)
        assert link.connected
        assert link.vehicle.mode == 5
        assert link.vehicle.vtype_raw == 2
        assert any(e["event_type"] == "connected" for e in link.events)

    def test_armed_flag(self):
        link = make_link()
        p = struct.pack("<IBBBBB", 5, 2, 3, 0x80, 0, 3)
        handle_heartbeat(p, len(p), link)
        assert link.vehicle.armed
        assert any(e["event_type"] == "armed" for e in link.events)

    def test_disarm_generates_summary(self):
        link = make_link()
        p_arm = struct.pack("<IBBBBB", 5, 2, 3, 0x80, 0, 3)
        handle_heartbeat(p_arm, len(p_arm), link)
        assert link.vehicle.armed
        p_disarm = struct.pack("<IBBBBB", 5, 2, 3, 0, 0, 3)
        handle_heartbeat(p_disarm, len(p_disarm), link)
        assert not link.vehicle.armed
        assert link.vehicle.flight_summary is not None
        assert "duration" in link.vehicle.flight_summary

    def test_empty_payload_ignored(self):
        # Per MAVLink 2 zero-trim, a truncated heartbeat is processed
        # zero-padded. Only an entirely empty payload (pl=0) is dropped.
        link = make_link()
        handle_heartbeat(b"", 0, link)
        assert link.connected is False

    def test_vehicle_type_detected(self):
        link = make_link()
        link._raw_sysid = 1
        p = bytearray(9)
        p[4] = 2  # quadrotor
        handle_heartbeat(p, len(p), link)
        assert link.vehicle.vtype_raw == 2

    def test_arm_resets_flight_stats(self):
        link = make_link()
        link.vehicle.max_alt = 100
        link.vehicle.max_speed = 50
        link._raw_sysid = 1
        p = bytearray(9)
        p[6] = 0x80
        handle_heartbeat(p, len(p), link)
        assert link.vehicle.max_alt == 0
        assert link.vehicle.max_speed == 0

    def test_disarm_via_bytearray(self):
        link = make_link()
        link.vehicle.armed = True
        link.vehicle.armed_time = time.time() - 60
        p = bytearray(9)
        p[6] = 0x00
        handle_heartbeat(p, len(p), link)
        assert link.vehicle.armed is False
        assert link.vehicle.flight_summary is not None


# ── Attitude ─────────────────────────────────────────────────────────────────


class TestAttitude:
    def test_parses_attitude(self):
        link = make_link()
        roll_rad = math.radians(10.5)
        pitch_rad = math.radians(-5.2)
        yaw_rad = math.radians(180.0)
        p = struct.pack("<Iffffff", 1000, roll_rad, pitch_rad, yaw_rad, 0, 0, 0)
        handle_attitude(p, len(p), link)
        assert abs(link.attitude.roll - 10.5) < 0.1
        assert abs(link.attitude.pitch - (-5.2)) < 0.1
        assert abs(link.attitude.yaw - 180.0) < 0.1

    def test_negative_yaw_wrapped(self):
        link = make_link()
        yaw_rad = math.radians(-90.0)
        p = struct.pack("<Iffffff", 1000, 0, 0, yaw_rad, 0, 0, 0)
        handle_attitude(p, len(p), link)
        assert link.attitude.yaw > 0

    def test_short_payload_ignored(self):
        link = make_link()
        p = bytearray(10)
        handle_attitude(p, len(p), link)
        assert link.attitude.roll == 0


# ── Global Position ──────────────────────────────────────────────────────────


class TestGlobalPosition:
    def test_parses_position(self):
        link = make_link()
        lat7 = int(34.258 * 1e7)
        lon7 = int(108.942 * 1e7)
        alt_msl = 400 * 1000
        alt_rel = 30 * 1000
        p = struct.pack("<IiiiihhhH", 1000, lat7, lon7, alt_msl, alt_rel, 500, 300, -100, 4500)
        handle_global_position_int(p, len(p), link)
        assert abs(link.attitude.lat - 34.258) < 0.001
        assert abs(link.attitude.lon - 108.942) < 0.001
        assert abs(link.attitude.alt_rel - 30.0) < 0.5
        assert abs(link.attitude.alt_msl - 400.0) < 0.5
        assert link.attitude.gs > 0

    def test_sets_home(self):
        link = make_link()
        lat7 = int(34.258 * 1e7)
        lon7 = int(108.942 * 1e7)
        p = struct.pack("<IiiiihhhH", 1000, lat7, lon7, 400000, 30000, 0, 0, 0, 0)
        handle_global_position_int(p, len(p), link)
        assert link.attitude.home_lat != 0

    def test_updates_max_alt_when_armed(self):
        link = make_link()
        link.vehicle.armed = True
        p = bytearray(30)
        struct.pack_into("<i", p, 4, int(30.0 * 1e7))
        struct.pack_into("<i", p, 8, int(120.0 * 1e7))
        struct.pack_into("<i", p, 12, 0)
        struct.pack_into("<i", p, 16, 200_000)  # 200m
        handle_global_position_int(p, len(p), link)
        assert link.vehicle.max_alt == 200.0


# ── SysStatus / Battery ─────────────────────────────────────────────────────


class TestSysStatus:
    def test_parses_battery(self):
        link = make_link()
        v_mv = 25200
        c_ca = 1200
        rem = 85
        p = struct.pack("<IIIHHhHHHHHHb", 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 500, v_mv, c_ca, 0, 0, 0, 0, 0, 0, rem)
        handle_sys_status(p, len(p), link)
        assert abs(link.battery.voltage - 25.2) < 0.1
        assert abs(link.battery.current - 12.0) < 0.1
        assert link.battery.remaining == 85

    def test_parses_voltage_separately(self):
        link = make_link()
        p = bytearray(35)
        struct.pack_into("<H", p, 14, 12600)  # 12.6V
        handle_sys_status(p, len(p), link)
        assert abs(link.battery.voltage - 12.6) < 0.01

    def test_parses_current_separately(self):
        link = make_link()
        p = bytearray(35)
        struct.pack_into("<H", p, 14, 12000)
        struct.pack_into("<h", p, 16, 1550)  # 15.5A
        handle_sys_status(p, len(p), link)
        assert abs(link.battery.current - 15.5) < 0.1

    def test_parses_remaining_separately(self):
        link = make_link()
        p = bytearray(35)
        struct.pack_into("<H", p, 14, 12000)
        struct.pack_into("<b", p, 30, 75)
        handle_sys_status(p, len(p), link)
        assert link.battery.remaining == 75


# ── GPS ──────────────────────────────────────────────────────────────────────


class TestGpsRaw:
    def test_parses_gps(self):
        link = make_link()
        p = struct.pack(
            "<QiiiHHHHBB", 1000000, int(34.258 * 1e7), int(108.942 * 1e7), 400000, 150, 200, 500, 4500, 3, 14
        )
        handle_gps_raw_int(p, len(p), link)
        assert link.gps.gps_fix == 3
        assert link.gps.gps_sats == 14

    def test_short_payload(self):
        link = make_link()
        p = bytearray(20)
        handle_gps_raw_int(p, len(p), link)
        assert link.gps.gps_fix == 0


# ── Statustext ───────────────────────────────────────────────────────────────


class TestStatustext:
    def test_filters_and_adds_event(self):
        link = make_link()
        text = b"PreArm: Need 3D Fix"
        p = struct.pack("<B", 6) + text + bytes(50 - len(text))
        handle_statustext(p, len(p), link)
        assert len(link.events) == 1
        assert "PreArm" not in link.events[0]["text"]

    def test_prearm_message_stored(self):
        link = make_link()
        link.locale = "en"
        msg = b"\x06" + b"PreArm: compass not calibrated\x00" + b"\x00" * 20
        handle_statustext(msg, len(msg), link)
        assert any("compass not calibrated" in m for m in link._prearm_messages)

    def test_prearm_list_capped(self):
        link = make_link()
        link.locale = "en"
        for i in range(25):
            msg = b"\x06" + f"PreArm: error {i}".encode().ljust(50, b"\x00")
            handle_statustext(msg, len(msg), link)
        assert len(link._prearm_messages) <= 20


# ── Command Ack ──────────────────────────────────────────────────────────────


class TestCommandAck:
    def test_adds_event_zh(self):
        link = make_link()
        p = struct.pack("<HBB", 400, 0, 0)
        handle_command_ack(p, len(p), link)
        assert len(link.events) == 1
        assert link.events[0]["event_type"] == "cmd_ack_ok"

    def test_failure(self):
        link = make_link()
        p = struct.pack("<HB", 400, 2)
        handle_command_ack(p, len(p), link)
        assert link.events[0]["event_type"] == "cmd_ack_fail"

    def test_in_progress_ignored(self):
        link = make_link()
        p = struct.pack("<HB", 400, 4)
        handle_command_ack(p, len(p), link)
        assert len(link.events) == 0

    def test_en_locale_arm_disarm(self):
        link = make_link()
        link.locale = "en"
        p = struct.pack("<HBB", 400, 0, 0)
        handle_command_ack(p, len(p), link)
        assert "success" in link.events[0]["text"]
        assert "Arm/Disarm" in link.events[0]["text"]

    def test_en_locale_takeoff(self):
        link = make_link()
        link.locale = "en"
        p = struct.pack("<HB", 22, 0)
        handle_command_ack(p, len(p), link)
        assert any("Takeoff" in e["text"] for e in link.events)


# ── Servo Output ─────────────────────────────────────────────────────────────


class TestServoOutput:
    def test_parses_8_servos(self):
        link = make_link()
        vals = [1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800]
        p = struct.pack("<I", 1000) + struct.pack("<8H", *vals) + b"\x00"
        handle_servo_output(p, len(p), link)
        assert link.rc_servo.servo_out[:8] == vals
        assert link.rc_servo.servo_out[8:] == [0] * 8

    def test_parses_16_servos(self):
        link = make_link()
        vals_lo = [1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800]
        vals_hi = [1900, 2000, 2100, 2200, 900, 950, 1000, 1050]
        p = struct.pack("<I", 1000) + struct.pack("<8H", *vals_lo) + struct.pack("<B", 0) + struct.pack("<8H", *vals_hi)
        handle_servo_output(p, len(p), link)
        assert link.rc_servo.servo_out[:8] == vals_lo
        assert link.rc_servo.servo_out[8:] == vals_hi


# ── RC Channels ──────────────────────────────────────────────────────────────


class TestRcChannels:
    def test_parses_channels_and_rssi(self):
        link = make_link()
        vals = [1000 + i * 50 for i in range(16)]
        # Wire order: time_boot_ms(u32) + chan1-18(u16×18) + chancount(u8) + rssi(u8)
        p = struct.pack("<I", 1000) + struct.pack("<16H", *vals)
        p += struct.pack("<HH", 0, 0)  # chan17, chan18
        p += struct.pack("<BB", 16, 220)  # chancount, rssi
        handle_rc_channels(p, len(p), link)
        assert link.rc_servo.rc_channels == vals
        assert link.rc_servo.rc_rssi == 220


# ── Vibration ────────────────────────────────────────────────────────────────


class TestVibration:
    def test_parses_vibration(self):
        link = make_link()
        p = struct.pack("<Q", 1000) + struct.pack("<fff", 1.5, 2.5, 3.5) + struct.pack("<III", 10, 20, 30)
        handle_vibration(p, len(p), link)
        assert abs(link.diagnostic.vibe_x - 1.5) < 0.01
        assert abs(link.diagnostic.vibe_y - 2.5) < 0.01
        assert abs(link.diagnostic.vibe_z - 3.5) < 0.01
        assert link.diagnostic.vibe_clip0 == 10
        assert link.diagnostic.vibe_clip1 == 20
        assert link.diagnostic.vibe_clip2 == 30


# ── EKF Status ───────────────────────────────────────────────────────────────


class TestEkfStatus:
    def test_parses_ekf(self):
        link = make_link()
        p = struct.pack("<fffffH", 0.1, 0.2, 0.3, 0.4, 0.5, 0x01FF)
        handle_ekf_status(p, len(p), link)
        assert abs(link.diagnostic.ekf_vel_var - 0.1) < 0.001
        assert abs(link.diagnostic.ekf_pos_h_var - 0.2) < 0.001
        assert abs(link.diagnostic.ekf_pos_v_var - 0.3) < 0.001
        assert abs(link.diagnostic.ekf_compass_var - 0.4) < 0.001
        assert link.diagnostic.ekf_flags == 0x01FF


# ── VFR_HUD ──────────────────────────────────────────────────────────────────


class TestVfrHud:
    def test_parses_vfr_hud(self):
        link = make_link()
        p = struct.pack("<ffffhH", 15.5, 12.3, 100.0, 2.5, 180, 45)
        handle_vfr_hud(p, len(p), link)
        assert abs(link.attitude.airspeed - 15.5) < 0.01
        assert link.attitude.throttle == 45
        assert abs(link.attitude.climb - 2.5) < 0.01

    def test_short_payload_ignored(self):
        link = make_link()
        handle_vfr_hud(b"\x00" * 19, 19, link)
        assert link.attitude.airspeed == 0.0


# ── Mount Status ─────────────────────────────────────────────────────────────


class TestMountStatus:
    def test_parses_gimbal_angles(self):
        link = make_link()
        p = struct.pack("<iii", -4500, 0, 9000)
        handle_mount_status(p, len(p), link)
        assert abs(link.diagnostic.gimbal_pitch - (-45.0)) < 0.01
        assert abs(link.diagnostic.gimbal_yaw - 90.0) < 0.01

    def test_short_payload_ignored(self):
        link = make_link()
        handle_mount_status(b"\x00" * 11, 11, link)
        assert link.diagnostic.gimbal_pitch == 0.0


# ── EKF dispatch registration ────────────────────────────────────────────────


class TestEkfDispatchRegistration:
    def test_ekf_registered_at_193(self):
        from backend.mavlink_handlers import mavlink_dispatch

        assert 193 in mavlink_dispatch._handlers
        assert mavlink_dispatch._handlers[193] == handle_ekf_status

    def test_vfr_hud_registered_at_74(self):
        from backend.mavlink_handlers import mavlink_dispatch

        assert 74 in mavlink_dispatch._handlers
        assert mavlink_dispatch._handlers[74] == handle_vfr_hud

    def test_mount_status_registered_at_158(self):
        from backend.mavlink_handlers import mavlink_dispatch

        assert 158 in mavlink_dispatch._handlers
        assert mavlink_dispatch._handlers[158] == handle_mount_status


# ── Terrain Report ───────────────────────────────────────────────────────────


class TestTerrainReport:
    def test_parses_terrain_alt(self):
        # TERRAIN_REPORT (136) wire layout sorted by field size:
        #   lat(i32, 0), lon(i32, 4), terrain_height(f, 8),
        #   current_height(f, 12), spacing(u16, 16), pending(u16, 18),
        #   loaded(u16, 20). The previous test used a 2-byte gap between
        #   the int32s and the float (i.e. <iiHHf) which placed the float
        #   at offset 12 (current_height) — masking the original handler
        #   bug that also read offset 12. Use correct wire order here.
        link = make_link()
        p = struct.pack("<iiffHHH", int(34.0 * 1e7), int(108.0 * 1e7), 456.78, 0.0, 100, 0, 0)
        handle_terrain_report(p, len(p), link)
        assert abs(link.diagnostic.terrain_alt - 456.78) < 0.01


# ── Wind ─────────────────────────────────────────────────────────────────────


class TestWind:
    def test_parses_wind(self):
        link = make_link()
        p = struct.pack("<fff", 270.0, 5.5, 1.0)
        handle_wind(p, len(p), link)
        assert abs(link.diagnostic.wind_dir - 270.0) < 0.01
        assert abs(link.diagnostic.wind_speed - 5.5) < 0.01

    def test_wind_dir_wraps(self):
        link = make_link()
        p = struct.pack("<fff", 370.0, 3.0, 0.0)
        handle_wind(p, len(p), link)
        assert abs(link.diagnostic.wind_dir - 10.0) < 0.01


# ── Autopilot Version ───────────────────────────────────────────────────────


class TestAutopilotVersion:
    def test_parses_version(self):
        link = make_link()
        major, minor, patch = 4, 5, 3
        fw_ver = (major << 24) | (minor << 16) | (patch << 8) | 0
        board = 56
        git_hash = b"\xab\xcd\xef\x12\x34\x56\x78\x00"
        # Wire order: capabilities(u64) + uid(u64) + flight_sw_version(u32) +
        # middleware_sw_version(u32) + os_sw_version(u32) + board_version(u32) +
        # flight_custom_version(u8[8]) + ...
        p = struct.pack("<Q", 0)  # capabilities at offset 0
        p += struct.pack("<Q", 0)  # uid at offset 8
        p += struct.pack("<I", fw_ver)  # flight_sw_version at offset 16
        p += struct.pack("<I", 0)  # middleware at offset 20
        p += struct.pack("<I", 0)  # os at offset 24
        p += struct.pack("<I", board)  # board_version at offset 28
        p += struct.pack("<I", 0)  # vendor_id etc at offset 32
        p += git_hash  # flight_custom_version at offset 36
        p += struct.pack("<I", 0)  # padding to reach 48 bytes
        handle_autopilot_version(p, len(p), link)
        assert link.vehicle.fw_version == "v4.5.3"
        assert link.vehicle.board_id == 56
        assert link.vehicle.fw_git == "abcdef12"


# ── Battery Status ───────────────────────────────────────────────────────────


class TestBatteryStatus:
    def test_parses_cells(self):
        link = make_link_connected()
        p = b"\x00" * 10  # header fields
        cells = [3850, 3840, 3830, 0xFFFF]
        p += struct.pack("<4H", *cells) + struct.pack("<6H", *([0xFFFF] * 6))
        p += b"\x00" * 6  # remaining fields to reach pl=36
        handle_battery_status(p, len(p), link)
        assert len(link.battery.battery_cells) == 3
        assert abs(link.battery.battery_cells[0] - 3.85) < 0.001

    def test_no_cells(self):
        link = make_link()
        p = bytearray(40)
        struct.pack_into("<H", p, 10, 0xFFFF)
        handle_battery_status(p, len(p), link)
        assert len(link.battery.battery_cells) == 0


# ── Mission Current ──────────────────────────────────────────────────────────


class TestMissionCurrent:
    def test_parses_wp_seq(self):
        link = make_link()
        p = struct.pack("<H", 7)
        handle_mission_current(p, len(p), link)
        assert link.mission.wp_seq == 7


# ── Home Position ────────────────────────────────────────────────────────────


class TestHomePosition:
    def test_parses_home(self):
        link = make_link()
        hlat = int(34.258 * 1e7)
        hlon = int(108.942 * 1e7)
        p = struct.pack("<iii", hlat, hlon, 400000)
        p += b"\x00" * (20 - len(p))
        handle_home_position(p, len(p), link)
        assert abs(link.attitude.home_lat - 34.258) < 0.001
        assert abs(link.attitude.home_lon - 108.942) < 0.001

    def test_ignores_zero_lat(self):
        link = make_link()
        p = struct.pack("<iii", 0, 0, 0)
        p += b"\x00" * (20 - len(p))
        handle_home_position(p, len(p), link)
        assert link.attitude.home_lat == 0.0


# ── Mission Item Reached ─────────────────────────────────────────────────────


class TestMissionItemReached:
    def test_adds_event(self):
        link = make_link()
        p = struct.pack("<H", 5)
        handle_mission_item_reached(p, len(p), link)
        assert len(link.events) == 1
        assert "5" in link.events[0]["text"]


# ── Mission Count ────────────────────────────────────────────────────────────


class TestMissionCount:
    def test_sets_dl_total(self):
        link = make_link()
        link.mission._dl_pending = True
        link.send = lambda frame: None
        p = struct.pack("<HBB", 10, link.vehicle.sysid, 1)
        handle_mission_count(p, len(p), link)
        assert link.mission._dl_total == 10
        assert len(link.mission._dl_items) == 10

    def test_zero_count(self):
        link = make_link()
        link.mission._dl_pending = True
        p = struct.pack("<HBB", 0, link.vehicle.sysid, 1)
        handle_mission_count(p, len(p), link)
        assert link.mission._dl_total == 0
        assert link.mission._dl_pending is False

    def test_ignored_when_not_pending(self):
        link = make_link()
        assert link.mission._dl_pending is False
        p = struct.pack("<HBB", 5, link.vehicle.sysid, 1)
        handle_mission_count(p, len(p), link)
        assert link.mission._dl_total == 0


# ── Mission Ack ──────────────────────────────────────────────────────────────


class TestMissionAck:
    def test_success(self):
        link = make_link()
        link.mission._mission_pending = True
        p = struct.pack("<BBBB", link.vehicle.sysid, 1, 0, 0)
        handle_mission_ack(p, len(p), link)
        assert link.mission._mission_pending is False
        assert len(link.events) == 1

    def test_failure(self):
        link = make_link()
        link.mission._mission_pending = True
        p = struct.pack("<BBBB", link.vehicle.sysid, 1, 3, 0)
        handle_mission_ack(p, len(p), link)
        assert link.mission._mission_pending is False

    def test_fence_ack(self):
        link = make_link()
        link.mission._fence_pending = True
        # mission_type=1 means fence
        p = struct.pack("<BBBB", link.vehicle.sysid, 1, 0, 1)
        handle_mission_ack(p, len(p), link)
        assert link.mission._fence_pending is False


# ── Log Entry ────────────────────────────────────────────────────────────────


class TestLogEntry:
    def test_appends_to_log_list(self):
        link = make_link()
        p = struct.pack("<IIHHH", 1700000000, 524288, 3, 5, 5)
        handle_log_entry(p, len(p), link)
        assert len(link.log_dl._log_list) == 1
        assert link.log_dl._log_list[0]["id"] == 3
        assert link.log_dl._log_list[0]["size"] == 524288

    def test_last_log_triggers_message(self):
        link = make_link()
        p1 = struct.pack("<IIHHH", 1700000000, 100000, 1, 2, 2)
        handle_log_entry(p1, len(p1), link)
        assert len(link.log_dl._log_messages) == 0
        p2 = struct.pack("<IIHHH", 1700000001, 200000, 2, 2, 2)
        handle_log_entry(p2, len(p2), link)
        assert len(link.log_dl._log_messages) == 1
        assert link.log_dl._log_messages[0]["type"] == "log_list"


# ── Log Data ─────────────────────────────────────────────────────────────────


class TestLogData:
    def test_writes_data(self):
        link = make_link()
        link.log_dl._log_download_id = 5
        link.log_dl._log_download_size = 20
        link.log_dl._log_download_data = bytearray(20)
        link.log_dl._log_download_ofs = 0
        link.send = lambda frame: None
        data_chunk = bytes(range(10))
        p = struct.pack("<IHB", 0, 5, 10) + data_chunk
        handle_log_data(p, len(p), link)
        assert link.log_dl._log_download_data[:10] == data_chunk
        assert link.log_dl._log_download_ofs == 10

    def test_ignores_wrong_id(self):
        link = make_link()
        link.log_dl._log_download_id = 5
        link.log_dl._log_download_size = 20
        link.log_dl._log_download_data = bytearray(20)
        p = struct.pack("<IHB", 0, 99, 10) + bytes(10)
        handle_log_data(p, len(p), link)
        assert link.log_dl._log_download_ofs == 0

    def test_complete_download(self):
        link = make_link()
        link.log_dl._log_download_id = 3
        link.log_dl._log_download_size = 8
        link.log_dl._log_download_data = bytearray(8)
        link.send = lambda frame: None
        data_chunk = b"\xaa\xbb\xcc\xdd\xee\xff\x11\x22"
        p = struct.pack("<IHB", 0, 3, 8) + data_chunk
        handle_log_data(p, len(p), link)
        assert link.log_dl._log_download_id == -1
        assert any(m["type"] == "log_complete" for m in link.log_dl._log_messages)

    def test_count_zero_finalizes_as_truncated(self):
        link = make_link()
        link.log_dl._log_download_id = 5
        link.log_dl._log_download_size = 100
        link.log_dl._log_download_data = bytearray(100)
        link.send = lambda f: None
        p = struct.pack("<IHB", 0, 5, 0) + bytes(90)
        handle_log_data(p, len(p), link)
        msgs = link.log_dl._log_messages
        assert any(m["type"] == "log_complete" and m["truncated"] for m in msgs)

    def test_out_of_order_chunk_ofs_stays_at_max(self):
        link = make_link()
        link.log_dl._log_download_id = 7
        link.log_dl._log_download_size = 30
        link.log_dl._log_download_data = bytearray(30)
        link.send = lambda frame: None
        # chunk at ofs=10 arrives first
        p1 = struct.pack("<IHB", 10, 7, 10) + bytes(range(10))
        handle_log_data(p1, len(p1), link)
        assert link.log_dl._log_download_ofs == 20
        # late chunk at ofs=0 must not rewind progress
        p2 = struct.pack("<IHB", 0, 7, 10) + bytes(range(10))
        handle_log_data(p2, len(p2), link)
        assert link.log_dl._log_download_ofs == 20
        assert link.log_dl._log_download_data[10:20] == bytes(range(10))
        assert link.log_dl._log_download_data[0:10] == bytes(range(10))


# ── Mission Item Int ─────────────────────────────────────────────────────────


class TestMissionItemInt:
    def test_stores_item(self):
        link = make_link()
        link.mission._dl_pending = True
        link.mission._dl_total = 3
        link.mission._dl_items = [None] * 3
        link.send = lambda frame: None
        lat = int(34.258 * 1e7)
        lon = int(108.942 * 1e7)
        p = struct.pack("<ffff", 0.0, 15.0, 0.0, 0.0)  # p1, p2, p3, p4
        p += struct.pack("<ii", lat, lon)
        p += struct.pack("<f", 100.0)  # alt
        p += struct.pack("<HH", 1, 16)  # seq=1, cmd=16 (waypoint)
        p += struct.pack("<BBBB", 1, 1, 3, 0)  # target_sys, target_comp, frame, current
        p += struct.pack("<B", 1)  # autocontinue
        handle_mission_item_int(p, len(p), link)
        assert link.mission._dl_items[1] is not None
        assert link.mission._dl_items[1]["seq"] == 1
        assert link.mission._dl_items[1]["cmd"] == 16
        assert abs(link.mission._dl_items[1]["lat"] - 34.258) < 0.001

    def test_last_item_completes_download(self):
        link = make_link()
        link.mission._dl_pending = True
        link.mission._dl_total = 1
        link.mission._dl_items = [None]
        link.send = lambda frame: None
        lat = int(34.258 * 1e7)
        lon = int(108.942 * 1e7)
        p = struct.pack("<ffff", 0.0, 0.0, 0.0, 0.0)
        p += struct.pack("<ii", lat, lon)
        p += struct.pack("<f", 50.0)
        p += struct.pack("<HH", 0, 16)  # seq=0, cmd=16
        p += struct.pack("<BBBBB", 1, 1, 3, 0, 1)
        handle_mission_item_int(p, len(p), link)
        assert link.mission._dl_pending is False

    @staticmethod
    def _item(seq, cmd=16, lat=34.0, lon=108.0, alt=50.0):
        p = struct.pack("<ffff", 0.0, 0.0, 0.0, 0.0)
        p += struct.pack("<ii", int(lat * 1e7), int(lon * 1e7))
        p += struct.pack("<f", alt)
        p += struct.pack("<HH", seq, cmd)
        p += struct.pack("<BBBBB", 1, 1, 3, 0, 1)
        return p

    def test_early_final_item_does_not_truncate(self):
        # Regression: a final MISSION_ITEM_INT (seq == _dl_total-1) arriving
        # before the middle items must NOT finalize the download and silently
        # drop the gaps — that yields a truncated mission on read-back.
        link = make_link()
        link.mission._dl_pending = True
        link.mission._dl_total = 3
        link.mission._dl_items = [None] * 3
        link.send = lambda frame: None
        # Final item (seq 2) arrives first, out of order.
        p = self._item(2)
        handle_mission_item_int(p, len(p), link)
        assert link.mission._dl_pending is True, "must not finalize while gaps remain"
        # Fill seq 0, then seq 1 — only now is every slot present.
        p = self._item(0)
        handle_mission_item_int(p, len(p), link)
        assert link.mission._dl_pending is True
        p = self._item(1)
        handle_mission_item_int(p, len(p), link)
        assert link.mission._dl_pending is False
        assert all(i is not None for i in link.mission._dl_items)
        assert [i["seq"] for i in link.mission._dl_items] == [0, 1, 2]

    def test_duplicate_item_completes_cleanly(self):
        # A retransmitted (duplicate) item must not finalize early or corrupt
        # the buffer; the download completes once the genuinely-missing seq lands.
        link = make_link()
        link.mission._dl_pending = True
        link.mission._dl_total = 2
        link.mission._dl_items = [None, None]
        link.send = lambda frame: None
        p = self._item(0)
        handle_mission_item_int(p, len(p), link)
        handle_mission_item_int(p, len(p), link)  # duplicate of seq 0
        assert link.mission._dl_pending is True  # seq 1 still missing
        p = self._item(1)
        handle_mission_item_int(p, len(p), link)
        assert link.mission._dl_pending is False
        assert all(i is not None for i in link.mission._dl_items)


# ── Mission Request ──────────────────────────────────────────────────────────


class TestMissionRequest:
    def test_no_crash_with_items(self):
        link = make_link()
        link.mission._mission_pending = True
        link.mission._mission_items = [
            {
                "seq": 0,
                "frame": 3,
                "cmd": 16,
                "current": 0,
                "autocontinue": 1,
                "p1": 0,
                "p2": 0,
                "p3": 0,
                "p4": 0,
                "lat": 34.258,
                "lon": 108.942,
                "alt": 100,
            },
        ]
        link.send = lambda frame: None
        p = struct.pack("<BBBBB", 0, 0, 1, 1, 0)
        handle_mission_request(p, len(p), link)
        assert link.mission._mission_pending is True

    def test_no_crash_out_of_range(self):
        link = make_link()
        link.mission._mission_pending = True
        link.mission._mission_items = []
        link.send = lambda frame: None
        p = struct.pack("<BBBBB", 5, 0, 1, 1, 0)
        handle_mission_request(p, len(p), link)


# ── ADSB Vehicle ─────────────────────────────────────────────────────────────


class TestAdsbVehicle:
    def test_adds_vehicle(self):
        link = make_link_connected()
        # Wire order: ICAO(u32) + lat(i32) + lon(i32) + alt(i32) + heading(u16) +
        # hor_velocity(u16) + ver_velocity(i16) + flags(u16) + squawk(u16) +
        # altitude_type(u8) + callsign(char[9]) + emitter_type(u8) + tslc(u8)
        p = struct.pack("<I", 0xABCDEF)
        p += struct.pack("<ii", int(30.5 * 1e7), int(120.3 * 1e7))
        p += struct.pack("<i", 5000 * 1000)
        p += struct.pack("<HHh", 18000, 25000, -500)
        p += struct.pack("<HHB", 0, 0, 0)  # flags, squawk, altitude_type
        p += b"TEST\x00\x00\x00\x00\x00"  # callsign at offset 27
        p += struct.pack("<BB", 0, 0)  # emitter_type, tslc
        handle_adsb_vehicle(p, len(p), link)
        assert 0xABCDEF in link.traffic._adsb_vehicles
        v = link.traffic._adsb_vehicles[0xABCDEF]
        assert v["callsign"] == "TEST"
        assert abs(v["alt"] - 5000) < 1

    def test_caps_at_200(self):
        link = make_link_connected()
        for i in range(205):
            p = struct.pack("<I", i)
            p += struct.pack("<ii", int(30.0 * 1e7), int(120.0 * 1e7))
            p += struct.pack("<i", 1000000)
            p += struct.pack("<HHh", 0, 0, 0)
            p += b"\x00" * 16
            handle_adsb_vehicle(p, len(p), link)
        assert len(link.traffic._adsb_vehicles) <= 200


# ── Serial Control ───────────────────────────────────────────────────────────


class TestSerialControl:
    def test_appends_console(self):
        link = make_link_connected()
        text = b"Hello Console"
        # Wire order: baudrate(u32) + timeout(u16) + device(u8) + flags(u8) + count(u8) + data
        p = struct.pack("<IHBBB", 0, 0, 10, 0x06, len(text))
        p += text + b"\x00" * (70 - len(text))
        handle_serial_control(p, len(p), link)
        assert "Hello Console" in "".join(link._console_buf)

    def test_trims_buffer(self):
        link = make_link_connected()
        link._console_buf = ["x"] * 501
        text = b"Y"
        p = struct.pack("<IHBBB", 0, 0, 10, 0x06, 1) + text + b"\x00" * 69
        handle_serial_control(p, len(p), link)
        assert len(link._console_buf) <= 251


# ── MAVLink Frame Parser ────────────────────────────────────────────────────


class TestMavlinkFrameParser:
    def test_parse_valid_frame(self):
        link = make_link()
        link._protocol = "standard"
        payload = struct.pack("<IBBBBB", 5, 2, 3, 0, 0, 3)
        header = bytes([len(payload), 0, 0, 1, 255, 1, 0, 0, 0])
        crc_data = header + payload + bytes([50])
        crc = link._mavlink_crc16(crc_data)
        frame = b"\xfd" + header + payload + struct.pack("<H", crc)
        link._buf = frame
        result, consumed = link._parse_mavlink_frame()
        assert result is not None
        assert consumed == len(frame)
        assert result[0] == 0xFD

    def test_parse_incomplete(self):
        link = make_link()
        link._buf = b"\xfd\x09\x00"
        result, consumed = link._parse_mavlink_frame()
        assert result is None
        assert consumed == 0

    def test_skip_garbage(self):
        link = make_link()
        link._buf = b"\x00\x00\x00\xfd\x09" + b"\x00" * 20
        result, consumed = link._parse_mavlink_frame()
        assert result is None
        assert consumed == 3

    def test_no_magic(self):
        link = make_link()
        link._buf = b"\x00\x01\x02\x03"
        result, consumed = link._parse_mavlink_frame()
        assert result is None
        assert consumed == 4

    def test_auto_detect_pllink(self):
        link = make_link()
        link._protocol = "auto"
        link._buf = b"\x50\x4c\x05\x00"
        link._next_frame()
        assert link._protocol == "pllink"

    def test_auto_detect_mavlink(self):
        link = make_link()
        link._protocol = "auto"
        link._buf = b"\xfd\x09\x00\x00\x01\x01\x01\x00\x00\x00"
        link._next_frame()
        assert link._protocol == "standard"


# ── Vehicle Types ────────────────────────────────────────────────────────────


class TestVehicleTypes:
    def test_copter(self):
        link = make_link()
        link.vehicle.vtype_raw = 2
        _, _, vn = link._get_vehicle_info()
        assert vn == "多旋翼"

    def test_plane(self):
        link = make_link()
        link.vehicle.vtype_raw = 1
        _, _, vn = link._get_vehicle_info()
        assert vn == "固定翼"

    def test_rover(self):
        link = make_link()
        link.vehicle.vtype_raw = 10
        _, _, vn = link._get_vehicle_info()
        assert vn == "地面车"

    def test_sub(self):
        link = make_link()
        link.vehicle.vtype_raw = 12
        _, _, vn = link._get_vehicle_info()
        assert vn == "水下机器人"

    def test_multi_vehicle_tracking(self):
        from backend.pllink_proto import bm as _bm

        link = make_link()
        link._protocol = "standard"
        hb = _bm(0, struct.pack("<IBBBBB", 5, 2, 3, 0, 0, 3), 0, 50, sysid=1)
        link._buf = hb
        payload, consumed = link._parse_mavlink_frame()
        assert payload is not None
        link._buf = link._buf[consumed:]
        link._process(payload)
        assert link.connected
        gps = _bm(
            33,
            struct.pack("<IiiiihhhH", 1000, int(34.258 * 1e7), int(108.942 * 1e7), 430000, 30000, 500, 300, -100, 4500),
            1,
            104,
            sysid=1,
        )
        link._buf = gps
        payload, consumed = link._parse_mavlink_frame()
        link._buf = link._buf[consumed:]
        link._process(payload)
        assert 1 in link._vehicles
        assert abs(link._vehicles[1]["lat"] - 34.258) < 0.001

    def test_get_state_vehicles_field(self):
        link = make_link()
        link.connected = True
        link.vehicle.sysid = 1
        link._vehicles[2] = {"sysid": 2, "lat": 35.0, "lon": 109.0, "alt": 50, "hdg": 90, "t": time.time()}
        link._vehicles[1] = {"sysid": 1, "lat": 34.0, "lon": 108.0, "alt": 30, "hdg": 45, "t": time.time()}
        state = link.get_state()
        assert "vehicles" in state
        assert len(state["vehicles"]) == 1
        assert state["vehicles"][0]["sysid"] == 2

    def test_force_plane(self):
        link = make_link()
        link.vehicle.vtype_raw = 2
        link.vehicle.force_plane = True
        _, _, vn = link._get_vehicle_info()
        assert vn == "固定翼"


# ── Short Payload Guards ────────────────────────────────────────────────────


class TestShortPayloadGuards:
    def test_all_handlers_reject_short_payload(self):
        link = make_link_connected()
        handlers_min = [
            (handle_mission_current, 1),
            (handle_home_position, 19),
            (handle_mission_item_reached, 1),
            (handle_command_ack, 2),
            (handle_servo_output, 20),
            (handle_rc_channels, 41),
            (handle_vibration, 31),
            (handle_ekf_status, 21),
            (handle_terrain_report, 15),
            (handle_wind, 11),
            (handle_autopilot_version, 35),
            (handle_mission_count, 2),
            (handle_log_entry, 13),
            (handle_log_data, 6),
            (handle_serial_control, 9),
            (handle_battery_status, 35),
            (handle_adsb_vehicle, 37),
        ]
        for handler, min_pl in handlers_min:
            short = b"\x00" * min_pl
            handler(short, min_pl, link)  # should not raise
