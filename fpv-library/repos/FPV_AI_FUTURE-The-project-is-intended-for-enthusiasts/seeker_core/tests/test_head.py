"""The assembled bench seeker head: real detect -> gimbal -> track -> preview guidance, end to end."""
from __future__ import annotations

from seeker_core.adapters import SimCameraSource
from seeker_core.contracts import (
    ActuatorChannel, ImuSample, OperatorButton, OperatorCommand, Provenance,
)
from seeker_core.head import bench_seeker_head


def _op(button=OperatorButton.NONE, token=None):
    return OperatorCommand(button=button, auth_token=token, t_ns=0)


def _imu():
    return ImuSample(gyro_rps=(0.0, 0.0, 0.02), accel_mps2=(0.0, 0.0, 9.81),
                     provenance=Provenance("imu", 0, synthetic=True))


def test_bench_head_full_loop_preview_no_commit():
    head = bench_seeker_head()
    cam = SimCameraSource()
    out = None
    for _ in range(20):
        out = head.step(cam.read(), _imu(), _op(), dt=1 / 60)
    assert out.track.locked and out.track.range_m is None                 # locked, no fabricated range
    assert abs(out.track.los_rate_az - 0.02) < 1e-9                        # LOS rate = head gyro
    assert out.guidance.a_cmd_az != 0.0                                    # preview steering demand exists
    assert not out.authority.committed
    assert out.actuators.by_channel(ActuatorChannel.AIRFRAME_THROTTLE).value == 0.0   # neutral, no motors
    assert out.actuators.by_channel(ActuatorChannel.GIMBAL_AZ) is not None            # gimbal aiming
    print(f"\n[head] real detect->gimbal->track->preview: locked={out.track.locked}, "
          f"los_rate_az={out.track.los_rate_az:.3f} (=head gyro), a_cmd_az={out.guidance.a_cmd_az:.2f} "
          f"(preview), required_g={out.guidance.required_g:.2f}, airframe neutral")


def test_bench_head_steers_only_on_commit():
    head = bench_seeker_head()
    cam = SimCameraSource()
    out = None
    for _ in range(20):
        out = head.step(cam.read(), _imu(), _op(button=OperatorButton.COMMIT, token=b"sig"), dt=1 / 60)
    assert out.authority.committed                                        # locked + two-press
    assert out.actuators.by_channel(ActuatorChannel.AIRFRAME_YAW).value != 0.0        # now it steers
    assert out.actuators.by_channel(ActuatorChannel.AIRFRAME_THROTTLE).value > 0.0
