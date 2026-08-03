"""NED / body-axis mapping checks for ExternalNav."""

import math

from aerostab.estimator import OdometryState
from aerostab.mavlink_bridge import MavlinkBridge
from aerostab.config import MavlinkConfig


def body_to_ned(x_m: float, y_m: float, yaw_rad: float):
    """Same transform as MavlinkBridge.send_odometry."""
    cos_y, sin_y = math.cos(yaw_rad), math.sin(yaw_rad)
    x_n = y_m * cos_y - x_m * sin_y
    y_e = y_m * sin_y + x_m * cos_y
    return x_n, y_e


def test_forward_motion_at_zero_yaw_is_north():
    # Body +Y (forward) at yaw=0 → North
    xn, ye = body_to_ned(0.0, 2.0, 0.0)
    assert abs(xn - 2.0) < 1e-6
    assert abs(ye) < 1e-6


def test_right_motion_at_zero_yaw_is_east():
    # Body +X (right) at yaw=0 → East
    xn, ye = body_to_ned(1.5, 0.0, 0.0)
    assert abs(xn) < 1e-6
    assert abs(ye - 1.5) < 1e-6


def test_yaw_90_deg_rotates_axes():
    # yaw = 90° (π/2): body forward (+Y) → East
    xn, ye = body_to_ned(0.0, 1.0, math.pi / 2)
    assert abs(xn) < 1e-6
    assert abs(ye - 1.0) < 1e-6


def test_bridge_send_does_not_crash_without_conn():
    br = MavlinkBridge(MavlinkConfig(enabled=True))
    st = OdometryState(x_m=1, y_m=2, vx_m_s=0.1, vy_m_s=0.2, yaw_rad=0, quality=1, nav_valid=True)
    assert br.send_odometry(st, 2.0, nav_valid=True) is False
