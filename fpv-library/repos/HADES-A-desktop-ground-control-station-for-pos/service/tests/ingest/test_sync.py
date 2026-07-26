"""Tests for frame<->telemetry time-sync alignment (Task 1.5)."""

import numpy as np
import pytest

from hades.ingest.frame_source import Frame
from hades.ingest.sync import AlignedFrame, PoseStatus, align
from hades.ingest.telemetry_source import Pose


def _frame(seq: int, t: float) -> Frame:
    return Frame(frame=np.zeros((2, 2, 3), np.uint8), timestamp=t, seq=seq)


def _pose(t: float, lat: float = 35.0, lon: float = -80.0, **kw) -> Pose:
    return Pose(t=t, lat=lat, lon=lon, alt=50.0, alt_datum="REL_TAKEOFF", **kw)


# (a) each frame gets the nearest/interpolated pose
def test_frame_paired_with_interpolated_pose_at_its_timestamp():
    frames = [_frame(0, 0.5)]
    poses = [_pose(0.0, lat=10.0, lon=0.0), _pose(1.0, lat=20.0, lon=10.0)]
    [aligned] = list(align(frames, poses))
    # Frame at t=0.5 lands halfway between the two poses.
    assert aligned.pose.lat == pytest.approx(15.0)
    assert aligned.pose.lon == pytest.approx(5.0)
    assert aligned.pose_status is PoseStatus.INTERPOLATED


def test_exact_timestamp_match_is_ok_status():
    frames = [_frame(0, 1.0)]
    poses = [_pose(0.0), _pose(1.0, lat=42.0)]
    [aligned] = list(align(frames, poses))
    assert aligned.pose.lat == pytest.approx(42.0)
    assert aligned.pose_status is PoseStatus.OK


def test_output_is_aligned_frame_carrying_original_frame():
    frames = [_frame(7, 0.0)]
    [aligned] = list(align(frames, [_pose(0.0)]))
    assert isinstance(aligned, AlignedFrame)
    assert aligned.frame.seq == 7


# None attitude propagates (SRT case: always None)
def test_none_attitude_interpolates_to_none_not_zero():
    frames = [_frame(0, 0.5)]
    poses = [_pose(0.0), _pose(1.0)]  # roll/pitch/yaw default None
    [aligned] = list(align(frames, poses))
    assert aligned.pose.roll is None
    assert aligned.pose.pitch is None
    assert aligned.pose.yaw is None


def test_attitude_interpolates_when_both_endpoints_have_it():
    # v1 uses linear interpolation of each angle (no attitude source supplies angles
    # in v1 — the .srt path is always None). A quaternion-SLERP seam can replace this
    # when a CRSF path lands; until then, assert linear behavior, not SLERP.
    frames = [_frame(0, 0.5)]
    poses = [_pose(0.0, yaw=0.0, pitch=0.0, roll=0.0), _pose(1.0, yaw=10.0, pitch=4.0, roll=2.0)]
    [aligned] = list(align(frames, poses))
    assert aligned.pose.yaw == pytest.approx(5.0)
    assert aligned.pose.pitch == pytest.approx(2.0)
    assert aligned.pose.roll == pytest.approx(1.0)


# (b) injected constant offset + jitter shifts the pairing correctly
def test_constant_offset_shifts_pairing_by_expected_poses():
    # Poses every 1.0s; a frame at t=0.0 with a +2.0s clock offset on the pose
    # clock should bind near the pose originally at t=-2.0 ... but since poses
    # start at 0, offset shifts which pose bracket the frame falls in.
    frames = [_frame(0, 2.0)]
    poses = [_pose(float(i), lat=float(i)) for i in range(5)]  # t=0..4, lat=0..4
    # No offset: frame at t=2.0 -> lat 2.0.
    [base] = list(align(frames, poses))
    assert base.pose.lat == pytest.approx(2.0)
    # Pose clock shifted +1.0s: pose formerly at t=2 now reads t=3, so the frame
    # at t=2.0 now matches the pose formerly at t=1 (lat 1.0).
    [shifted] = list(align(frames, poses, clock_offset=1.0))
    assert shifted.pose.lat == pytest.approx(1.0)


def test_jitter_is_deterministic_under_seed():
    frames = [_frame(0, 2.0)]
    poses = [_pose(float(i)) for i in range(5)]
    jit = lambda p: 0.01  # noqa: E731 - tiny constant "jitter" for determinism
    a = list(align(frames, poses, jitter_fn=jit))
    b = list(align(frames, poses, jitter_fn=jit))
    assert a[0].pose.t == b[0].pose.t


# (c) missing telemetry -> flagged, not crash
def test_empty_telemetry_flags_missing_not_crash():
    frames = [_frame(0, 0.0), _frame(1, 0.1)]
    aligned = list(align(frames, []))
    assert len(aligned) == 2
    assert all(a.pose is None for a in aligned)
    assert all(a.pose_status is PoseStatus.MISSING for a in aligned)


# edge: before first / after last pose -> clamp + flag, never extrapolate
def test_frame_before_first_pose_is_clamped_and_flagged():
    frames = [_frame(0, -1.0)]
    poses = [_pose(0.0, lat=10.0), _pose(1.0, lat=20.0)]
    [aligned] = list(align(frames, poses))
    assert aligned.pose_status in (PoseStatus.EXTRAPOLATED, PoseStatus.MISSING)
    # Must NOT extrapolate past the data (no lat < 10 invented).
    if aligned.pose is not None:
        assert aligned.pose.lat == pytest.approx(10.0)


def test_frame_after_last_pose_is_clamped_and_flagged():
    frames = [_frame(0, 99.0)]
    poses = [_pose(0.0, lat=10.0), _pose(1.0, lat=20.0)]
    [aligned] = list(align(frames, poses))
    assert aligned.pose_status in (PoseStatus.EXTRAPOLATED, PoseStatus.MISSING)
    if aligned.pose is not None:
        assert aligned.pose.lat == pytest.approx(20.0)


# edge: telemetry gap larger than threshold -> stale flag
def test_gap_larger_than_threshold_flags_stale():
    frames = [_frame(0, 5.0)]
    poses = [_pose(0.0), _pose(10.0)]  # 10s gap; frame falls in the middle
    [aligned] = list(align(frames, poses, max_gap_s=1.0))
    assert aligned.pose_status is PoseStatus.STALE


# edge: non-monotonic pose timestamps must not silently corrupt bracketing
def test_non_monotonic_pose_timestamps_raise():
    frames = [_frame(0, 0.5)]
    poses = [_pose(1.0), _pose(0.0)]  # backward
    with pytest.raises(ValueError):
        list(align(frames, poses))


# edge: a no-GPS endpoint poisons interpolation to None (gps_valid False)
def test_no_gps_endpoint_poisons_position_to_none():
    frames = [_frame(0, 0.5)]
    poses = [
        _pose(0.0),
        Pose(t=1.0, lat=None, lon=None, alt=50.0, alt_datum="REL_TAKEOFF", gps_valid=False),
    ]
    [aligned] = list(align(frames, poses))
    assert aligned.pose.lat is None
    assert aligned.pose.gps_valid is False


def test_abs_alt_valid_false_when_interpolated_abs_alt_is_none():
    # One endpoint has no abs_alt -> interpolated abs_alt is None; the validity
    # flag must say False, never green-light a None as a number (M1).
    frames = [_frame(0, 0.5)]
    poses = [
        _pose(0.0, abs_alt=168.0),
        _pose(1.0),  # abs_alt defaults None
    ]
    [aligned] = list(align(frames, poses))
    assert aligned.pose.abs_alt is None
    assert aligned.pose.abs_alt_valid is False


def test_duplicate_pose_timestamps_raise():
    # Equal timestamps are non-monotonic (not strictly increasing) -> raise,
    # rather than a silent arbitrary tie-break (M2).
    frames = [_frame(0, 1.0)]
    poses = [_pose(1.0, lat=99.0), _pose(1.0, lat=11.0)]
    with pytest.raises(ValueError):
        list(align(frames, poses))


def test_interpolated_pose_seq_is_none_not_stale_lower_bracket():
    # An interpolated pose is synthesized; carrying p0.seq mislabels its frame_id
    # and breaks the seq cross-check. It must be None (M3).
    frames = [_frame(5, 0.5)]
    poses = [_pose(0.0, seq=0), _pose(1.0, seq=1)]
    [aligned] = list(align(frames, poses))
    assert aligned.pose.seq is None


def test_time_error_reported_for_uncertainty():
    frames = [_frame(0, 0.5)]
    poses = [_pose(0.0), _pose(1.0)]
    [aligned] = list(align(frames, poses))
    assert aligned.time_error_s is not None
    assert aligned.time_error_s >= 0.0
