"""Tests for backend/state.py — domain state dataclass correctness."""

from backend.state import (
    AttitudeState,
    BatteryState,
    DiagnosticState,
    GpsState,
    LogState,
    MissionState,
    RcServoState,
    TrafficState,
    VehicleState,
)


class TestDefaults:
    def test_attitude_defaults(self):
        a = AttitudeState()
        assert a.roll == 0.0
        assert a.lat == 0.0
        assert a._prev_pos is None

    def test_battery_defaults(self):
        b = BatteryState()
        assert b.voltage == 0.0
        assert b.remaining == -1
        assert b._bat_history == []
        assert b.battery_cells == []

    def test_gps_defaults(self):
        g = GpsState()
        assert g.gps_fix == 0
        assert g.gps_sats == 0

    def test_vehicle_defaults(self):
        v = VehicleState()
        assert v.armed is False
        assert v.force_plane is None
        assert v.sysid == 1
        assert v.flight_summary is None

    def test_mission_defaults(self):
        m = MissionState()
        assert m._mission_items == []
        assert m._mission_pending is False
        assert m._dl_messages == []

    def test_diagnostic_defaults(self):
        d = DiagnosticState()
        assert d.ekf_flags == 0
        assert d.terrain_alt == -1.0

    def test_rc_servo_defaults(self):
        r = RcServoState()
        assert len(r.rc_channels) == 16
        assert len(r.servo_out) == 16

    def test_log_defaults(self):
        l = LogState()
        assert l._log_download_id == -1
        assert l._log_download_data == bytearray()

    def test_traffic_defaults(self):
        t = TrafficState()
        assert t._adsb_vehicles == {}


class TestMutableIsolation:
    def test_battery_history_independent(self):
        b1 = BatteryState()
        b2 = BatteryState()
        b1._bat_history.append((1.0, 95))
        assert len(b2._bat_history) == 0

    def test_mission_items_independent(self):
        m1 = MissionState()
        m2 = MissionState()
        m1._mission_items.append({"seq": 0})
        assert len(m2._mission_items) == 0

    def test_rc_channels_independent(self):
        r1 = RcServoState()
        r2 = RcServoState()
        r1.rc_channels[0] = 1500
        assert r2.rc_channels[0] == 0

    def test_log_data_independent(self):
        l1 = LogState()
        l2 = LogState()
        l1._log_download_data.extend(b"\x01\x02")
        assert len(l2._log_download_data) == 0


class TestFieldAssignment:
    def test_attitude_writable(self):
        a = AttitudeState()
        a.roll = 15.5
        a.lat = 30.12345
        assert a.roll == 15.5
        assert a.lat == 30.12345

    def test_vehicle_writable(self):
        v = VehicleState()
        v.armed = True
        v.mode = 6
        v.sysid = 2
        assert v.armed is True
        assert v.mode == 6
