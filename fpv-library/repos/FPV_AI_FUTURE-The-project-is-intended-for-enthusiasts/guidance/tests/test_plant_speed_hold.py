"""Plant forward speed-hold (enables meaningful high-speed Mode-B).

Legacy plant: forward accel = g*tan(pitch) - drag*v.  With the pilot's constant forward pitch
(0.4 -> 16 deg -> 2.81 m/s^2) and drag_coeff=0.05 the forward speed settles at ~56 m/s regardless of
interceptor_speed_mps -- the audit's speed-runaway, which makes a 150 m/s intercept miss meaningless.
The speed_hold flag replaces the forward-axis dynamics with a first-order controller onto the
setpoint.  Default OFF -> legacy behaviour (these tests also pin that OFF still runs away).
"""

from __future__ import annotations

import math

from fpv.guidance.quad_sim import QuadSim, SimConfig

_DT = 1.0 / 60.0
_PILOT_PITCH = 0.40          # command_map forward_pitch_fraction (constant forward lean)
_HOVER = 0.50
_THETA_MAX = math.radians(40.0)


def _fly_forward_speed(cfg: SimConfig, seconds: float, *, v0_override: float | None = None) -> float:
    qs = QuadSim(cfg)
    if v0_override is not None:
        qs._state.vel[1] = v0_override
    st = qs._state
    for _ in range(int(seconds / _DT)):
        st = qs.step(0.0, _PILOT_PITCH, 0.0, _HOVER, _DT)
    return float(st.vel[1])


def test_legacy_plant_runs_away_from_setpoint():
    """OFF (legacy): a 15 m/s interceptor climbs far past its setpoint toward the ~56 m/s balance."""
    steady = 9.81 * math.tan(_PILOT_PITCH * _THETA_MAX) / 0.05     # g*tan(16 deg)/drag ~ 56 m/s
    assert 45.0 < steady < 65.0
    v = _fly_forward_speed(SimConfig(interceptor_speed_mps=15.0, speed_hold=False), 15.0)
    assert v > 30.0, f"legacy plant should run away above the 15 m/s setpoint, got {v:.1f} m/s"
    assert v < steady + 1.0, "must not exceed the analytic pitch-vs-drag steady state"


def test_speed_hold_holds_high_setpoint():
    """ON: a 150 m/s interceptor stays at ~150 (does NOT decay toward the 56 m/s legacy balance)."""
    v = _fly_forward_speed(SimConfig(interceptor_speed_mps=150.0, speed_hold=True), 5.0)
    assert abs(v - 150.0) < 5.0, f"speed-hold should hold ~150 m/s, got {v:.1f} m/s"


def test_legacy_150_would_decay_but_hold_keeps_it():
    """Direct contrast at the SAME 150 start: legacy decays toward 56, speed-hold keeps 150."""
    legacy = _fly_forward_speed(SimConfig(interceptor_speed_mps=150.0, speed_hold=False), 8.0)
    held = _fly_forward_speed(SimConfig(interceptor_speed_mps=150.0, speed_hold=True), 8.0)
    assert legacy < 120.0, f"legacy plant should decay from 150 toward ~56, got {legacy:.1f}"
    assert abs(held - 150.0) < 5.0, f"speed-hold should keep 150, got {held:.1f}"


def test_speed_hold_regulates_from_off_setpoint():
    """ON: starting well below the setpoint, the controller pulls forward speed up to it."""
    v = _fly_forward_speed(
        SimConfig(interceptor_speed_mps=150.0, speed_hold=True, speed_hold_gain_hz=3.0),
        3.0, v0_override=60.0)
    assert abs(v - 150.0) < 5.0, f"controller should converge to 150 from 60, got {v:.1f} m/s"
