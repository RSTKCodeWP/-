"""Up-looking-camera command mapping: intercept from BELOW with PN in the horizontal plane + climb.

When the boresight points straight up, the image plane is HORIZONTAL, so BOTH LOS-rate axes are
horizontal translation:  a_cmd_az -> ROLL, a_cmd_el -> PITCH.  Throttle CLIMBS to close the vertical
gap (which the pixel cannot see); yaw stays ~0 (yawing a strapdown up-camera only spins the frame).
This is the opposite of the forward-camera mapping (a_cmd_el -> throttle, pitch = constant march),
which must remain bit-identical when the flag is off.
"""

from __future__ import annotations

from fpv.guidance.bearing_rate import GeometryClass, GuidanceCommand
from fpv.guidance.command_map import LosGuidancePilot, PilotConfig


def _gcmd(az=0.0, el=0.0):
    return GuidanceCommand(a_cmd_az_mps2=az, a_cmd_el_mps2=el, blend_factor=1.0,
                           geometry=GeometryClass.HEAD_ON, apn_active=False, Vc_sched_mps=20.0,
                           N_effective=3.0, required_g=0.2, achievable_g=0.84, envelope_ok=True)


def _cmd(pilot, gc, az=0.0, el=0.0):
    return pilot.command_from_guidance(gc, az_rad=az, el_rad=el, sequence_id=1, timestamp_ms=1)


def test_up_camera_both_los_axes_become_translation():
    """a_cmd_az -> ROLL, a_cmd_el -> PITCH (both horizontal); throttle climbs; yaw ~0."""
    p = LosGuidancePilot(config=PilotConfig(up_looking_camera=True, climb_throttle=0.62, yaw_gain_up=0.0))
    c = _cmd(p, _gcmd(az=3.0, el=2.0), az=0.2, el=0.1)
    assert c.roll_cmd > 0.0, c.roll_cmd                 # right LOS -> roll right
    assert c.pitch_cmd > 0.0, c.pitch_cmd               # the SECOND horizontal axis -> pitch (not march)
    assert c.throttle_cmd > 0.55, c.throttle_cmd        # climbing from below (>= hover)
    assert abs(c.yaw_rate_cmd) < 1e-9, c.yaw_rate_cmd   # no yaw authority (frame stays fixed)


def test_up_camera_elevation_drives_pitch_not_throttle():
    """Growing a_cmd_el must grow PITCH, and must NOT scale throttle (throttle is climb+tilt-comp)."""
    p = LosGuidancePilot(config=PilotConfig(up_looking_camera=True, climb_throttle=0.60))
    small = _cmd(p, _gcmd(el=1.0))
    p.reset()
    big = _cmd(p, _gcmd(el=6.0))
    assert big.pitch_cmd > small.pitch_cmd + 0.05, (small.pitch_cmd, big.pitch_cmd)
    # throttle only rises via tilt compensation (cos), never as a linear elevation term -> stays modest
    assert big.throttle_cmd <= 0.75, big.throttle_cmd


def test_forward_camera_mapping_is_unchanged_when_flag_off():
    """Regression: default (forward) mapping still sends a_cmd_el -> throttle and pitch = constant march."""
    p = LosGuidancePilot(config=PilotConfig())          # up_looking_camera defaults False
    base = _cmd(p, _gcmd(el=0.0))
    p.reset()
    up = _cmd(p, _gcmd(el=8.0))                          # strong "accelerate up" demand
    assert up.throttle_cmd > base.throttle_cmd + 0.02, (base.throttle_cmd, up.throttle_cmd)  # el -> throttle
    assert abs(up.pitch_cmd - base.pitch_cmd) < 1e-9    # pitch is the constant forward march, not el-driven
