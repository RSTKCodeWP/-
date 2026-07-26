"""Integration: the REAL fpv detector feeds the gimbaled seeker core on synthetic thermal frames.

Closes Stages 1->4 of the bench sequence in software: FT640-style frame -> real detect -> gimbal
tracks the detected centroid. (On the bench the frame is live FT640; here it's the sim camera.)
"""
from __future__ import annotations

from seeker_core.adapters import SimCameraSource
from seeker_core.contracts import ActuatorChannel, ImuSample, OperatorButton, OperatorCommand, Provenance
from seeker_core.core import gimbaled_core
from seeker_core.detector_stage import RealDetector
from seeker_core.gimbal_stage import GimbalControllerStage


def _op():
    return OperatorCommand(button=OperatorButton.NONE, auth_token=None, t_ns=0)


def test_real_detector_finds_target_and_gimbal_tracks():
    core = gimbaled_core(GimbalControllerStage())
    core.detector = RealDetector()                     # the proven thermal detector
    cam = SimCameraSource()                            # synthetic hot target on cold sky
    imu = ImuSample(gyro_rps=(0.0, 0.0, 0.0), accel_mps2=(0.0, 0.0, 9.81),
                    provenance=Provenance("imu", 0, synthetic=True))
    tracked = 0
    out = None
    for _ in range(30):
        out = core.step(cam.read(), imu, _op(), dt=1 / 60)
        if out.gimbal is not None and out.gimbal.tracking:
            tracked += 1
    assert tracked >= 20, f"real detector should find the synthetic hot target most frames ({tracked}/30)"
    assert out.actuators.by_channel(ActuatorChannel.GIMBAL_AZ) is not None          # gimbal aiming
    assert out.actuators.by_channel(ActuatorChannel.AIRFRAME_YAW).value == 0.0      # not engaging (no commit)
    print(f"\n[seeker_core] real detector -> gimbaled head: tracked {tracked}/30 frames, "
          f"GIMBAL_AZ={out.actuators.by_channel(ActuatorChannel.GIMBAL_AZ).value:+.3f} rad, airframe neutral")
