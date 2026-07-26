"""seeker_core smoke + honesty tests: contracts validate, and the safety boundary holds end to end."""
from __future__ import annotations

import numpy as np
import pytest

from seeker_core.adapters import RecordActuatorSink, SimCameraSource
from seeker_core.contracts import (
    ActuatorChannel,
    Blob,
    Detections,
    Frame,
    GuidanceCommand,
    ImuSample,
    OperatorButton,
    OperatorCommand,
    Provenance,
    Track,
)
from seeker_core.core import (
    DefaultDenySupervisor,
    HoldGuidance,
    NullDetector,
    SeekerCore,
    StandardActuatorMapper,
    default_core,
    gimbaled_core,
)
from seeker_core.gimbal_stage import GimbalControllerStage


def _op(button=OperatorButton.NONE, token=None, t=0):
    return OperatorCommand(button=button, auth_token=token, t_ns=t)


def _prov():
    return Provenance("test", t_capture_ns=1, synthetic=True)


# ── contracts refuse to carry malformed / fabricated state ────────────────────────────────────────
def test_frame_rejects_bad_shape_and_dtype():
    with pytest.raises(ValueError):
        Frame(np.zeros((3, 4, 5), np.uint16), radiometric=False, provenance=_prov())
    with pytest.raises(ValueError):
        Frame(np.zeros((4, 4), np.float32), radiometric=False, provenance=_prov())


def test_track_rejects_impossible_values():
    with pytest.raises(ValueError):
        Track(True, 0, 0, 0, 0, None, None, quality=1.5, provenance=_prov())
    with pytest.raises(ValueError):
        Track(True, 0, 0, 0, 0, range_m=-1.0, t_go_s=None, quality=1.0, provenance=_prov())


# ── honesty: no lock -> safe neutral actuators, never an engage ───────────────────────────────────
def test_default_core_no_lock_is_safe_neutral():
    core = default_core()
    cam = SimCameraSource()
    frame = cam.read()
    out = core.step(frame, imu=None, op=_op(), dt=1 / 60)
    assert not out.track.locked and out.track.range_m is None       # NullDetector -> no fabrication
    assert not out.authority.committed
    thr = out.actuators.by_channel(ActuatorChannel.AIRFRAME_THROTTLE)
    assert thr is not None and thr.value == 0.0                     # idle, no motor authority
    assert out.actuators.by_channel(ActuatorChannel.AIRFRAME_YAW).value == 0.0


# ── the weaponization boundary: airframe steers ONLY on a verified two-press ──────────────────────
class _LockTracker:
    def update(self, detections: Detections, imu, gimbal, dt: float) -> Track:
        return Track(True, 0.1, -0.05, 0.02, 0.0, 120.0, 1.5, 0.9, detections.provenance)


class _DemandGuidance:
    def command(self, track: Track) -> GuidanceCommand:
        return GuidanceCommand(a_cmd_az=3.0, a_cmd_el=-2.0, roe_abort=False, engage_permit=True,
                               required_g=0.3, provenance=track.provenance)


def _wired(gimbal=False):
    return SeekerCore(detector=NullDetector(), tracker=_LockTracker(), guidance=_DemandGuidance(),
                      supervisor=DefaultDenySupervisor(), mapper=StandardActuatorMapper(),
                      gimbal=GimbalControllerStage() if gimbal else None)


def test_locked_but_no_commit_stays_neutral():
    core = _wired()
    frame = SimCameraSource().read()
    out = core.step(frame, imu=None, op=_op(button=OperatorButton.NONE, token=None), dt=1 / 60)
    assert out.track.locked and not out.authority.committed        # locked, but human hasn't committed
    assert out.actuators.by_channel(ActuatorChannel.AIRFRAME_YAW).value == 0.0
    assert out.actuators.by_channel(ActuatorChannel.AIRFRAME_THROTTLE).value == 0.0


def test_commit_with_token_and_lock_steers():
    core = _wired()
    frame = SimCameraSource().read()
    out = core.step(frame, imu=None, op=_op(button=OperatorButton.COMMIT, token=b"signed"), dt=1 / 60)
    assert out.authority.committed and out.authority.reason == "committed"
    assert out.actuators.by_channel(ActuatorChannel.AIRFRAME_YAW).value != 0.0      # now it steers
    assert out.actuators.by_channel(ActuatorChannel.AIRFRAME_THROTTLE).value > 0.0


def test_commit_without_token_is_denied():
    core = _wired()
    frame = SimCameraSource().read()
    out = core.step(frame, imu=None, op=_op(button=OperatorButton.COMMIT, token=None), dt=1 / 60)
    assert not out.authority.committed and out.authority.reason == "no_auth_token"
    assert out.actuators.by_channel(ActuatorChannel.AIRFRAME_YAW).value == 0.0


def test_gimbal_aims_before_commit_but_airframe_does_not():
    core = _wired(gimbal=True)
    frame = SimCameraSource().read()
    out = core.step(frame, imu=None, op=_op(), dt=1 / 60)           # locked, not committed
    assert out.actuators.by_channel(ActuatorChannel.GIMBAL_AZ) is not None          # aiming allowed
    assert out.actuators.by_channel(ActuatorChannel.AIRFRAME_YAW).value == 0.0      # engaging not


class _BlobDetector:
    """Emits one off-centre blob so the gimbal stage has a target to track."""
    def detect(self, frame: Frame) -> Detections:
        return Detections(blobs=(Blob(centroid_px=(420.0, 200.0), area_px=30, snr=12.0,
                                      bbox=(410, 190, 20, 20)),), provenance=frame.provenance)


def test_gimbaled_core_tracks_and_surfaces_head_gyro_as_los_rate():
    """The seeker head as one module: gimbal tracks the blob (GIMBAL_AZ moves), head gyro IS the LOS
    rate (surfaced), airframe stays neutral (no commit)."""
    core = gimbaled_core(GimbalControllerStage())
    core.detector = _BlobDetector()
    cam = SimCameraSource()
    imu = ImuSample(gyro_rps=(0.0, 0.0, 0.05), accel_mps2=(0.0, 0.0, 9.81), provenance=_prov())
    out = None
    for _ in range(50):
        out = core.step(cam.read(), imu, _op(), dt=1 / 500)
    assert out.gimbal is not None and out.gimbal.tracking                       # a target was tracked
    gaz = out.actuators.by_channel(ActuatorChannel.GIMBAL_AZ)
    assert gaz is not None and abs(gaz.value) > 1e-3                            # gimbal slewed to aim
    assert abs(out.gimbal.los_rate_yaw - 0.05) < 1e-9                           # head gyro IS the LOS rate
    assert out.actuators.by_channel(ActuatorChannel.AIRFRAME_YAW).value == 0.0  # not engaging
    print(f"\n[seeker_core] gimbaled head: tracking={out.gimbal.tracking}, GIMBAL_AZ={gaz.value:+.3f} rad, "
          f"los_rate_yaw={out.gimbal.los_rate_yaw:.3f} rad/s (= head gyro), airframe neutral")


def test_abort_latches_kill():
    core = _wired()
    frame = SimCameraSource().read()
    core.step(frame, None, _op(button=OperatorButton.ABORT), 1 / 60)
    out = core.step(frame, None, _op(button=OperatorButton.COMMIT, token=b"signed"), 1 / 60)
    assert out.authority.kill and not out.authority.committed       # kill is sticky, overrides commit
    assert out.actuators.by_channel(ActuatorChannel.AIRFRAME_THROTTLE).value == 0.0


def test_sink_records_frames():
    core, sink = default_core(), RecordActuatorSink()
    cam = SimCameraSource()
    for _ in range(3):
        out = core.step(cam.read(), None, _op(), 1 / 60)
        sink.write(out.actuators)
    assert len(sink.frames) == 3
