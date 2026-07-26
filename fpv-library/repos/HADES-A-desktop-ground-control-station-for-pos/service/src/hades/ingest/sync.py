"""Frame <-> telemetry time-sync alignment by timestamp (Task 1.5).

Each `Frame` is paired with a `Pose` interpolated at the frame's timestamp. The
binding primitive is the **clock value** (`Pose.t`), found by bracketing the frame
time between two consecutive poses — a value match, so it is immune to the
index-drift that a positional `poses[i]` join would suffer when the telemetry and
video frame counts differ (a missing pose just widens the bracket; it never shifts
which poses a later frame binds to). `Pose.seq` is a debug cross-check, not the key.

Honesty rules (DESIGN.md "never a false-precision pin"):
- A None endpoint (attitude or position) propagates to None — never 0 / level / north.
- Out-of-range frames clamp to the nearest pose but are flagged EXTRAPOLATED (no
  invented motion past the data).
- A bracket wider than `max_gap_s` is flagged STALE (interpolating across a hole lies).
- No telemetry at all -> `pose=None`, status MISSING (never a silent default pose).

The `clock_offset` + `jitter_fn` knobs perturb the pose clock before matching — the
same time-sync-offset the Monte Carlo samples (DESIGN.md §3.1). An offset of
`k*dt + eps` shifts the chosen bracket by `k` poses (the time-sync-error test).
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from enum import Enum

from hades.ingest.frame_source import Frame
from hades.ingest.telemetry_source import Pose


class PoseStatus(Enum):
    OK = "ok"  # exact timestamp hit
    INTERPOLATED = "interpolated"  # between two in-range poses
    EXTRAPOLATED = "extrapolated"  # clamped to an endpoint (outside the pose span)
    STALE = "stale"  # bracket interval exceeded max_gap_s
    MISSING = "missing"  # no telemetry to pair


# eq=False -> identity eq/hash (it holds a Frame, which holds an ndarray).
@dataclass(frozen=True, eq=False)
class AlignedFrame:
    """A frame paired with its (possibly None) pose and the sync provenance."""

    frame: Frame
    pose: Pose | None
    pose_status: PoseStatus
    time_error_s: float | None  # |frame.t - pose.t| or bracket half-width; feeds uncertainty


def align(
    frames: Iterable[Frame],
    poses: Iterable[Pose],
    *,
    clock_offset: float = 0.0,
    jitter_fn: Callable[[Pose], float] | None = None,
    max_gap_s: float = 2.0,
) -> Iterator[AlignedFrame]:
    """Pair each frame with a pose interpolated at its timestamp.

    Args:
        frames: source frames (any order; matched by their `timestamp`).
        poses: telemetry poses; must be timestamp-monotonic after the clock shift.
        clock_offset: seconds added to every `Pose.t` before matching (clock skew).
        jitter_fn: optional per-pose additive time noise (seeded by the caller).
        max_gap_s: bracket intervals wider than this are flagged STALE (default 2.0s —
            normal GPS-fix spacing is ~1s, so this flags genuine multi-second dropouts).
    """
    # Poses are fully materialized for bisect — fine for replay (a 10-min mission is
    # ~tens of thousands of poses, a few MB). The live CrsfSerialSource path must
    # replace this with a streaming/windowed match. Frames stay lazily iterated.
    pose_list = list(poses)
    shifted = [_shifted_t(p, clock_offset, jitter_fn) for p in pose_list]
    # Require strictly increasing timestamps: a duplicate t is non-monotonic and
    # would make the exact-hit branch tie-break arbitrarily between the two poses.
    if any(b <= a for a, b in zip(shifted, shifted[1:])):
        raise ValueError("pose timestamps are not strictly increasing after clock shift")

    for frame in frames:
        if not pose_list:
            yield AlignedFrame(frame, None, PoseStatus.MISSING, None)
            continue
        yield _align_one(frame, pose_list, shifted, max_gap_s)


def _shifted_t(pose: Pose, offset: float, jitter_fn: Callable[[Pose], float] | None) -> float:
    return pose.t + offset + (jitter_fn(pose) if jitter_fn else 0.0)


def _align_one(
    frame: Frame, poses: list[Pose], times: list[float], max_gap_s: float
) -> AlignedFrame:
    ft = frame.timestamp
    i = bisect_left(times, ft)

    # Out of range -> clamp to nearest endpoint, flag EXTRAPOLATED (no extrapolation).
    # Precedence is intentional: clamp dominates a stale-gap check — a frame outside
    # the pose span is reported EXTRAPOLATED even if the nearest gap is also large.
    if i == 0 and ft < times[0]:
        return AlignedFrame(frame, poses[0], PoseStatus.EXTRAPOLATED, times[0] - ft)
    if i >= len(times):
        last = len(times) - 1
        return AlignedFrame(frame, poses[last], PoseStatus.EXTRAPOLATED, ft - times[last])

    # Exact hit.
    if times[i] == ft:
        return AlignedFrame(frame, poses[i], PoseStatus.OK, 0.0)

    # Interpolate between the bracketing poses i-1 and i.
    lo, hi = i - 1, i
    span = times[hi] - times[lo]
    status = PoseStatus.STALE if span > max_gap_s else PoseStatus.INTERPOLATED
    frac = (ft - times[lo]) / span if span > 0 else 0.0
    pose = _interp(poses[lo], poses[hi], frac)
    time_error = min(ft - times[lo], times[hi] - ft)
    return AlignedFrame(frame, pose, status, time_error)


def _lerp(a: float | None, b: float | None, f: float) -> float | None:
    """Linear interpolate; any None endpoint -> None (honest, never defaulted)."""
    if a is None or b is None:
        return None
    return a + (b - a) * f


def _interp(p0: Pose, p1: Pose, f: float) -> Pose:
    gps_valid = p0.gps_valid and p1.gps_valid
    lat = _lerp(p0.lat, p1.lat, f) if gps_valid else None
    lon = _lerp(p0.lon, p1.lon, f) if gps_valid else None
    # Altitude only interpolates within one datum.
    alt = _lerp(p0.alt, p1.alt, f) if p0.alt_datum == p1.alt_datum else None
    abs_alt = _lerp(p0.abs_alt, p1.abs_alt, f)
    return Pose(
        t=p0.t + (p1.t - p0.t) * f,
        lat=lat,
        lon=lon,
        alt=alt,
        alt_datum=p0.alt_datum if p0.alt_datum == p1.alt_datum else "UNKNOWN",
        # Attitude: lerp each angle; any None endpoint -> None. (Small-angle lerp is
        # adequate at sub-second spacing; a quaternion SLERP seam can replace this
        # when a CRSF path actually supplies attitude — not built unused in v1.)
        roll=_lerp(p0.roll, p1.roll, f),
        pitch=_lerp(p0.pitch, p1.pitch, f),
        yaw=_lerp(p0.yaw, p1.yaw, f),
        # Synthesized pose has no native frame_id — None, not p0's (which would
        # mislabel the seq cross-check against the frame it now aligns to).
        seq=None,
        gps_valid=gps_valid,
        abs_alt=abs_alt,
        # Never green-light a None abs_alt as valid.
        abs_alt_valid=abs_alt is not None and p0.abs_alt_valid and p1.abs_alt_valid,
    )
