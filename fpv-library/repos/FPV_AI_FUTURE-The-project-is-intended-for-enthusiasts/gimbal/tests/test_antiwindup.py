"""Anti-windup: the integrated servo setpoint can never wind past the mechanical travel (the fix for
the real-hardware tilt runaway to -210deg). Opt-in via GimbalConfig limits; off = bit-identical."""
from fpv.gimbal.controller import GimbalConfig, GimbalController


def test_antiwindup_clamps_setpoint_to_mechanical_limits():
    cfg = GimbalConfig(accel_leveling=False, pan_limit_rad=(-0.10, 0.05), tilt_limit_rad=(-0.90, -0.01))
    ctrl = GimbalController(cfg)
    # a persistent far-corner target with no gyro would integrate the setpoint unboundedly
    out = None
    for _ in range(3000):
        out = ctrl.step((0.0, 0.0, 0.0), (0.0, 0.0, 9.81), (640.0, 512.0), 0.02)
    assert cfg.pan_limit_rad[0] <= out.pan_setpoint_rad <= cfg.pan_limit_rad[1]
    assert cfg.tilt_limit_rad[0] <= out.tilt_setpoint_rad <= cfg.tilt_limit_rad[1]


def test_without_limits_setpoint_is_free_bit_identical():
    ctrl = GimbalController(GimbalConfig(accel_leveling=False))   # no limits -> old behaviour
    out = None
    for _ in range(500):
        out = ctrl.step((0.0, 0.0, 0.0), (0.0, 0.0, 9.81), (640.0, 512.0), 0.02)
    assert abs(out.pan_setpoint_rad) > 0.10   # wound well past any small bound (no clamp applied)
