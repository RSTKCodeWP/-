"""Assembled seeker head — the full bench pipeline from real, proven stages.

    real thermal detect (fpv.seeker.detect) -> gyro-stabilized gimbal (fpv.gimbal, IMU on head)
    -> gimbaled tracker (LOS rate = head gyro) -> preview PN guidance -> default-deny safety -> actuators

One sensor-in → actuator-out module, wired from ports of the verified fpv/ physics. This is the head
that `Pi5BenchIO` / `SimBenchIO` drives on the stand (Bench Stages 3–4).
"""
from __future__ import annotations

from seeker_core.core import DefaultDenySupervisor, SeekerCore, StandardActuatorMapper
from seeker_core.detector_stage import RealDetector
from seeker_core.gimbal_stage import GimbalControllerStage
from seeker_core.guidance_stage import PreviewGuidance
from seeker_core.tracker_stage import GimbaledTracker


def bench_seeker_head(**detector_kwargs) -> SeekerCore:
    """The complete gimbaled seeker head from real stages (detector kwargs pass through to RealDetector)."""
    return SeekerCore(
        detector=RealDetector(**detector_kwargs),
        tracker=GimbaledTracker(),
        guidance=PreviewGuidance(),
        supervisor=DefaultDenySupervisor(),
        mapper=StandardActuatorMapper(),
        gimbal=GimbalControllerStage(),
    )
