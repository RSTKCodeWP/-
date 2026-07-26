import pytest
from flight_safety.config import Limits
from flight_safety.dispatcher import Dispatcher
from flight_safety.models import Telemetry

def _tlm(lat=47.3978, lon=8.5456, yaw=0.0):
    return Telemetry(lat=lat, lon=lon, alt_m=10.0, speed_ms=0.0, battery_pct=1.0,
                     flight_mode="OFFBOARD", armed=True, gps_ok=True, ekf_ok=True, yaw=yaw)

# square geofence around home
FENCE = [(47.3970, 8.5450), (47.3990, 8.5450), (47.3990, 8.5470), (47.3970, 8.5470)]

def _disp(bridge=None):
    return Dispatcher(bridge or object(), Limits(), FENCE)

def test_setpoint_ignored_when_not_offboard():
    d = _disp(); d._tlm_cache = _tlm()
    d.manual_setpoint(5, 0, 0, 0)
    assert d._setpoint == (0.0, 0.0, 0.0, 0.0)

def test_setpoint_clamped_to_limits():
    d = _disp(); d._offboard = True; d._tlm_cache = _tlm()
    d.manual_setpoint(100.0, 0.0, 0.0, 999.0)  # way over
    f, r, dn, yr = d._setpoint
    assert abs((f**2 + r**2) ** 0.5 - 12.0) < 1e-6   # max_speed_ms
    assert yr == 90.0                                 # max_yaw_rate_dps

def test_geofence_brake_zeroes_horizontal_when_projected_outside():
    d = _disp(); d._offboard = True
    # near east edge, pushing further east (right, heading north -> east)
    d._tlm_cache = _tlm(lat=47.3980, lon=8.54699, yaw=0.0)
    d.manual_setpoint(0.0, 10.0, -1.0, 0.0)
    f, r, dn, yr = d._setpoint
    assert f == 0.0 and r == 0.0   # braked
    assert dn == -1.0              # vertical preserved

def test_effective_setpoint_decays_when_stale():
    d = _disp(); d._offboard = True; d._tlm_cache = _tlm()
    d.manual_setpoint(5.0, 0.0, 0.0, 0.0)
    assert d._effective_setpoint(now=d._setpoint_ts + 0.1) == d._setpoint
    assert d._effective_setpoint(now=d._setpoint_ts + 1.0) == (0.0, 0.0, 0.0, 0.0)
