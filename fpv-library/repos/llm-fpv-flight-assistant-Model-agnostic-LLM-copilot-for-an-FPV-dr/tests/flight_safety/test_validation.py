from flight_safety.config import Limits
from flight_safety.models import parse_command, Telemetry
from flight_safety.validation import validate_command, ValidationResult

GEOFENCE = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]
LIMITS = Limits(max_alt_m=120, min_alt_m=0, max_speed_ms=12, min_battery_pct=0.20)


def _tlm(**kw) -> Telemetry:
    base = dict(lat=0.0, lon=0.0, alt_m=10.0, speed_ms=1.0, battery_pct=0.9,
                flight_mode="HOLD", armed=True, gps_ok=True, ekf_ok=True)
    base.update(kw)
    return Telemetry(**base)


def test_valid_goto_accepted():
    cmd = parse_command({"verb": "goto", "lat": 0.5, "lon": 0.5, "alt": 30})
    res = validate_command(cmd, _tlm(), LIMITS, GEOFENCE)
    assert res.ok is True


def test_goto_outside_geofence_rejected():
    cmd = parse_command({"verb": "goto", "lat": 5.0, "lon": 0.0, "alt": 30})
    res = validate_command(cmd, _tlm(), LIMITS, GEOFENCE)
    assert res.ok is False and "geofence" in res.reason.lower()


def test_goto_above_ceiling_rejected():
    tight = Limits(max_alt_m=50)
    cmd = parse_command({"verb": "goto", "lat": 0.0, "lon": 0.0, "alt": 80})
    res = validate_command(cmd, _tlm(), tight, GEOFENCE)
    assert res.ok is False and "alt" in res.reason.lower()


def test_command_rejected_on_low_battery():
    cmd = parse_command({"verb": "goto", "lat": 0.0, "lon": 0.0, "alt": 30})
    res = validate_command(cmd, _tlm(battery_pct=0.10), LIMITS, GEOFENCE)
    assert res.ok is False and "battery" in res.reason.lower()


def test_command_rejected_when_gps_unhealthy():
    cmd = parse_command({"verb": "goto", "lat": 0.0, "lon": 0.0, "alt": 30})
    res = validate_command(cmd, _tlm(gps_ok=False), LIMITS, GEOFENCE)
    assert res.ok is False and "gps" in res.reason.lower()


def test_command_rejected_when_ekf_unhealthy():
    cmd = parse_command({"verb": "orbit", "radius": 20, "alt": 25})
    res = validate_command(cmd, _tlm(ekf_ok=False), LIMITS, GEOFENCE)
    assert res.ok is False and "ekf" in res.reason.lower()


def test_orbit_alt_within_limits_accepted():
    cmd = parse_command({"verb": "orbit", "radius": 20, "alt": 25})
    res = validate_command(cmd, _tlm(), LIMITS, GEOFENCE)
    assert res.ok is True


def test_safety_verbs_always_allowed():
    for verb in ("return_to_launch", "land", "handback", "loiter", "takeover"):
        cmd = parse_command({"verb": verb})
        res = validate_command(cmd, _tlm(battery_pct=0.05), LIMITS, GEOFENCE)
        assert res.ok is True, f"{verb} should be allowed"


def test_takeover_bypasses_health_gating():
    cmd = parse_command({"verb": "takeover"})
    res = validate_command(
        cmd, _tlm(gps_ok=False, ekf_ok=False, battery_pct=0.01), LIMITS, GEOFENCE
    )
    assert res.ok is True


def test_alt_floor_is_exclusive():
    limits = Limits(min_alt_m=30, max_alt_m=120)
    at_floor = parse_command({"verb": "goto", "lat": 0.0, "lon": 0.0, "alt": 30})
    res = validate_command(at_floor, _tlm(), limits, GEOFENCE)
    assert res.ok is False and "alt" in res.reason.lower()

    above_floor = parse_command({"verb": "goto", "lat": 0.0, "lon": 0.0, "alt": 31})
    res = validate_command(above_floor, _tlm(), limits, GEOFENCE)
    assert res.ok is True


def test_arm_takeoff_rejected_if_already_armed_and_flying():
    cmd = parse_command({"verb": "arm_takeoff", "alt": 5})
    res = validate_command(cmd, _tlm(armed=True, alt_m=10.0), LIMITS, GEOFENCE)
    assert res.ok is False and "already" in res.reason.lower()
