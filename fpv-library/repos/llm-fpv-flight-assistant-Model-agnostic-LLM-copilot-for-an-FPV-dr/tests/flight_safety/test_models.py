import pytest
from pydantic import ValidationError
from flight_safety.models import (
    Telemetry, parse_command, GotoCommand, OrbitCommand, ArmTakeoffCommand,
)


def test_parse_goto_command():
    cmd = parse_command({"verb": "goto", "lat": 47.397, "lon": 8.545, "alt": 30})
    assert isinstance(cmd, GotoCommand)
    assert cmd.alt == 30


def test_parse_orbit_command_defaults_center_none():
    cmd = parse_command({"verb": "orbit", "radius": 20, "alt": 25})
    assert isinstance(cmd, OrbitCommand)
    assert cmd.center is None


def test_parse_arm_takeoff():
    cmd = parse_command({"verb": "arm_takeoff", "alt": 5})
    assert isinstance(cmd, ArmTakeoffCommand)


def test_unknown_verb_rejected():
    with pytest.raises(ValidationError):
        parse_command({"verb": "self_destruct"})


def test_orbit_requires_positive_radius():
    with pytest.raises(ValidationError):
        parse_command({"verb": "orbit", "radius": -5, "alt": 25})


def test_telemetry_roundtrip():
    t = Telemetry(lat=47.0, lon=8.0, alt_m=10.0, speed_ms=1.0,
                  battery_pct=0.9, flight_mode="HOLD", armed=True,
                  gps_ok=True, ekf_ok=True)
    assert t.battery_pct == 0.9


def _base_telemetry():
    return dict(lat=47.0, lon=8.0, alt_m=10.0, speed_ms=1.0, battery_pct=0.9,
                flight_mode="HOLD", armed=True, gps_ok=True, ekf_ok=True)


def test_telemetry_attitude_defaults_to_zero():
    t = Telemetry(**_base_telemetry())
    assert (t.roll, t.pitch, t.yaw) == (0.0, 0.0, 0.0)


def test_telemetry_accepts_attitude():
    t = Telemetry(**_base_telemetry(), roll=5.0, pitch=-3.0, yaw=90.0)
    assert t.pitch == -3.0
