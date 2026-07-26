"""Comprehensive unit tests for the MAVLink simulator (sim_pllink.py).

Tests that generated frames are valid MAVLink v2, contain correct message
IDs, have valid CRC, and carry realistic telemetry values.
"""

import math
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.pllink_proto import mc
from scripts.sim_pllink import Simulator


@pytest.fixture
def sim():
    """Fresh simulator instance."""
    s = Simulator()
    s.tick(0.1)  # advance time slightly so fields are populated
    return s


def _parse_mavlink_frame(frame: bytes):
    """Parse a MAVLink v2 frame into components."""
    assert frame[0] == 0xFD, f"Expected magic 0xFD, got 0x{frame[0]:02X}"
    payload_len = frame[1]
    incompat_flags = frame[2]
    compat_flags = frame[3]
    seq = frame[4]
    sysid = frame[5]
    compid = frame[6]
    msgid = frame[7] | (frame[8] << 8) | (frame[9] << 16)
    payload = frame[10 : 10 + payload_len]
    crc_bytes = frame[10 + payload_len : 12 + payload_len]
    crc_value = struct.unpack("<H", crc_bytes)[0]
    return {
        "magic": frame[0],
        "payload_len": payload_len,
        "incompat_flags": incompat_flags,
        "compat_flags": compat_flags,
        "seq": seq,
        "sysid": sysid,
        "compid": compid,
        "msgid": msgid,
        "payload": payload,
        "crc": crc_value,
        "header": frame[1:10],
    }


class TestFrameFormat:
    def test_heartbeat_starts_with_magic(self, sim):
        frame = sim.msg_heartbeat()
        assert frame[0] == 0xFD

    def test_all_messages_start_with_magic(self, sim):
        messages = [
            sim.msg_heartbeat(),
            sim.msg_attitude(),
            sim.msg_global_pos(),
            sim.msg_gps_raw(),
            sim.msg_sys_status(),
            sim.msg_rc_channels(),
            sim.msg_vibration(),
            sim.msg_ekf_status(),
        ]
        for msg in messages:
            assert msg[0] == 0xFD, "Frame does not start with 0xFD"

    def test_frame_minimum_length(self, sim):
        """A MAVLink v2 frame is at least 12 bytes (header + CRC, no payload)."""
        frame = sim.msg_heartbeat()
        assert len(frame) >= 12


class TestHeartbeat:
    def test_heartbeat_message_id_is_zero(self, sim):
        frame = sim.msg_heartbeat()
        parsed = _parse_mavlink_frame(frame)
        assert parsed["msgid"] == 0

    def test_heartbeat_sysid(self, sim):
        frame = sim.msg_heartbeat()
        parsed = _parse_mavlink_frame(frame)
        assert parsed["sysid"] == 1  # sim uses sysid=1

    def test_heartbeat_compid(self, sim):
        frame = sim.msg_heartbeat()
        parsed = _parse_mavlink_frame(frame)
        assert parsed["compid"] == 1

    def test_heartbeat_payload_contains_mode(self, sim):
        frame = sim.msg_heartbeat()
        parsed = _parse_mavlink_frame(frame)
        # Heartbeat payload: custom_mode(u32), type(u8), autopilot(u8), base_mode(u8), ...
        custom_mode = struct.unpack_from("<I", parsed["payload"], 0)[0]
        assert custom_mode == sim.mode

    def test_heartbeat_armed_flag(self, sim):
        sim.armed = True
        frame = sim.msg_heartbeat()
        parsed = _parse_mavlink_frame(frame)
        # Heartbeat payload: custom_mode(u32=4) + type(u8) + autopilot(u8) + base_mode(u8)
        base_mode = parsed["payload"][6]
        assert base_mode & 0x80 != 0, "Armed flag (0x80) should be set"

    def test_heartbeat_disarmed_flag(self, sim):
        sim.armed = False
        frame = sim.msg_heartbeat()
        parsed = _parse_mavlink_frame(frame)
        base_mode = parsed["payload"][6]
        assert base_mode & 0x80 == 0, "Armed flag (0x80) should not be set"


class TestAttitude:
    def test_attitude_message_id(self, sim):
        frame = sim.msg_attitude()
        parsed = _parse_mavlink_frame(frame)
        assert parsed["msgid"] == 30

    def test_attitude_contains_valid_angles(self, sim):
        frame = sim.msg_attitude()
        parsed = _parse_mavlink_frame(frame)
        # Payload: time_boot_ms(u32), roll(f32), pitch(f32), yaw(f32), ...
        _, roll, pitch, yaw = struct.unpack_from("<Ifff", parsed["payload"], 0)
        assert -math.pi <= roll <= math.pi
        assert -math.pi <= pitch <= math.pi
        assert -2 * math.pi <= yaw <= 2 * math.pi

    def test_attitude_roll_pitch_reasonable(self, sim):
        """Simulator should produce small roll/pitch in normal operation."""
        frame = sim.msg_attitude()
        parsed = _parse_mavlink_frame(frame)
        _, roll, pitch, _ = struct.unpack_from("<Ifff", parsed["payload"], 0)
        # Sim generates ~2 deg roll, ~1.5 deg pitch
        assert abs(roll) < math.radians(15)
        assert abs(pitch) < math.radians(15)


class TestGPS:
    def test_global_pos_message_id(self, sim):
        frame = sim.msg_global_pos()
        parsed = _parse_mavlink_frame(frame)
        assert parsed["msgid"] == 33

    def test_gps_raw_message_id(self, sim):
        frame = sim.msg_gps_raw()
        parsed = _parse_mavlink_frame(frame)
        assert parsed["msgid"] == 24

    def test_global_pos_lat_lon_reasonable(self, sim):
        frame = sim.msg_global_pos()
        parsed = _parse_mavlink_frame(frame)
        # Payload: time(u32), lat(i32), lon(i32), alt(i32), relative_alt(i32), ...
        _, lat_e7, lon_e7 = struct.unpack_from("<Iii", parsed["payload"], 0)
        lat = lat_e7 / 1e7
        lon = lon_e7 / 1e7
        assert -90 <= lat <= 90, f"Latitude {lat} out of range"
        assert -180 <= lon <= 180, f"Longitude {lon} out of range"
        # Sim starts at 34.258330, 108.942500
        assert 30 <= lat <= 40
        assert 100 <= lon <= 115

    def test_gps_raw_fix_type(self, sim):
        frame = sim.msg_gps_raw()
        parsed = _parse_mavlink_frame(frame)
        # GPS_RAW_INT payload has fix_type at offset 28 (after u64 + 3*i32 + 4*u16)
        fix_type = parsed["payload"][28]
        assert fix_type == 3  # 3D fix

    def test_gps_raw_satellite_count(self, sim):
        frame = sim.msg_gps_raw()
        parsed = _parse_mavlink_frame(frame)
        sats = parsed["payload"][29]
        assert sats == 14  # sim default


class TestBattery:
    def test_sys_status_message_id(self, sim):
        frame = sim.msg_sys_status()
        parsed = _parse_mavlink_frame(frame)
        assert parsed["msgid"] == 1

    def test_battery_voltage_in_range(self, sim):
        frame = sim.msg_sys_status()
        parsed = _parse_mavlink_frame(frame)
        # SYS_STATUS payload: sensors(3*u32) + load(u16) + voltage(u16) ...
        voltage_mv = struct.unpack_from("<H", parsed["payload"], 14)[0]
        voltage_v = voltage_mv / 1000.0
        # Sim starts at 25.2V, a 6S battery range is ~20-25.5V
        assert 10.0 <= voltage_v <= 30.0, f"Voltage {voltage_v}V out of expected range"

    def test_battery_remaining_percentage(self, sim):
        frame = sim.msg_sys_status()
        parsed = _parse_mavlink_frame(frame)
        # remaining is at offset 30 (i8 after many fields)
        remaining = struct.unpack_from("<b", parsed["payload"], 30)[0]
        assert 0 <= remaining <= 100


class TestCRC:
    def test_heartbeat_crc_valid(self, sim):
        frame = sim.msg_heartbeat()
        parsed = _parse_mavlink_frame(frame)
        # Recalculate CRC: mc(header + payload, crc_extra)
        # Heartbeat crc_extra = 50
        computed = mc(parsed["header"] + parsed["payload"], 50)
        assert computed == parsed["crc"], f"CRC mismatch: computed=0x{computed:04X}, frame=0x{parsed['crc']:04X}"

    def test_attitude_crc_valid(self, sim):
        frame = sim.msg_attitude()
        parsed = _parse_mavlink_frame(frame)
        computed = mc(parsed["header"] + parsed["payload"], 39)
        assert computed == parsed["crc"]

    def test_global_pos_crc_valid(self, sim):
        frame = sim.msg_global_pos()
        parsed = _parse_mavlink_frame(frame)
        computed = mc(parsed["header"] + parsed["payload"], 104)
        assert computed == parsed["crc"]

    def test_gps_raw_crc_valid(self, sim):
        frame = sim.msg_gps_raw()
        parsed = _parse_mavlink_frame(frame)
        computed = mc(parsed["header"] + parsed["payload"], 24)
        assert computed == parsed["crc"]

    def test_sys_status_crc_valid(self, sim):
        frame = sim.msg_sys_status()
        parsed = _parse_mavlink_frame(frame)
        computed = mc(parsed["header"] + parsed["payload"], 124)
        assert computed == parsed["crc"]

    def test_corrupted_frame_fails_crc(self, sim):
        """Flipping a bit should cause CRC mismatch."""
        frame = bytearray(sim.msg_heartbeat())
        # Flip a bit in the payload area
        frame[10] ^= 0x01
        parsed = _parse_mavlink_frame(bytes(frame))
        computed = mc(parsed["header"] + parsed["payload"], 50)
        assert computed != parsed["crc"]


class TestSimulatorState:
    def test_tick_advances_time(self, sim):
        t0 = sim.t
        sim.tick(1.0)
        assert sim.t == pytest.approx(t0 + 1.0)

    def test_armed_drains_battery(self, sim):
        sim.armed = True
        initial = sim.remaining
        sim.tick(10.0)
        assert sim.remaining < initial

    def test_disarmed_no_battery_drain(self, sim):
        sim.armed = False
        initial = sim.remaining
        sim.tick(10.0)
        assert sim.remaining == initial
