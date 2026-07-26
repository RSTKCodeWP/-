"""Tests for the numpy ByteTrack tracker (Task 3.1).

The tracker is a stateful `list[Detection] -> list[Track]` that assigns persistent
IDs, bridges the 10→30fps gap with Kalman prediction, survives short occlusions, and
NEVER resurrects a dead ID. It is a from-scratch numpy port of ByteTrack (two-stage
association: high-conf detections first, low-conf second) — deliberately torch-free so
it runs deterministically on lean CI (the project keeps PyTorch out of runtime/CI;
Ultralytics' BYTETracker imports torch and auto-`pip install`s `lap`).

These tests are pure numpy: hand-authored `Detection` sequences, no model, no frames.
"""

from __future__ import annotations

import sys

import pytest

from hades.detect.detector import Detection
from hades.track.tracker import ByteTracker, Track, TrackState


def _det(x: float, y: float, w: float = 20.0, h: float = 40.0, conf: float = 0.9) -> Detection:
    """Detection at top-left (x, y) with size (w, h)."""
    return Detection(box_xyxy=(x, y, x + w, y + h), conf=conf)


def _ids(tracks: list[Track]) -> set[int]:
    return {t.track_id for t in tracks}


# --- contract / construction ------------------------------------------------


def test_track_holds_id_box_state():
    t = Track(track_id=1, box_xyxy=(10.0, 20.0, 30.0, 60.0), state=TrackState.CONFIRMED)
    assert t.track_id == 1
    assert t.box_xyxy == (10.0, 20.0, 30.0, 60.0)
    assert t.state is TrackState.CONFIRMED


def test_update_returns_list_of_tracks():
    trk = ByteTracker()
    out = trk.update([_det(100, 100)])
    assert isinstance(out, list)
    assert all(isinstance(t, Track) for t in out)


def test_tracker_does_not_import_torch():
    # Lock the lean-runtime constraint into CI: nothing on the tracker path may pull
    # torch. If this fails, someone wired Ultralytics/torch back into the live loop.
    assert "torch" not in sys.modules


# --- persistence: stable ID across frames -----------------------------------


def test_stable_id_across_linear_motion():
    # One survivor drifting linearly keeps ONE id the whole way (the bread-and-butter case).
    trk = ByteTracker(min_hits=1)
    ids_over_time = []
    for k in range(10):
        out = trk.update([_det(100 + 5 * k, 100 + 2 * k)])
        confirmed = [t for t in out if t.state is TrackState.CONFIRMED]
        assert len(confirmed) == 1
        ids_over_time.append(confirmed[0].track_id)
    assert len(set(ids_over_time)) == 1  # exactly one id, never reassigned


def test_two_tracks_keep_distinct_ids_no_swap():
    # Two well-separated survivors moving in parallel must keep distinct, non-swapped ids.
    trk = ByteTracker(min_hits=1)
    first = trk.update([_det(100, 100), _det(400, 400)])
    id_left = min(first, key=lambda t: t.box_xyxy[0]).track_id
    id_right = max(first, key=lambda t: t.box_xyxy[0]).track_id
    assert id_left != id_right
    for k in range(1, 6):
        out = trk.update([_det(100 + 3 * k, 100), _det(400 + 3 * k, 400)])
        left = min(out, key=lambda t: t.box_xyxy[0])
        right = max(out, key=lambda t: t.box_xyxy[0])
        assert left.track_id == id_left
        assert right.track_id == id_right


# --- occlusion survival + no resurrection -----------------------------------


def test_id_survives_short_occlusion():
    # Disappear for fewer than track_buffer frames, reappear nearby -> SAME id.
    trk = ByteTracker(min_hits=1, track_buffer=30)
    first = trk.update([_det(200, 200)])
    original_id = first[0].track_id
    # 3-frame gap (no detections) — well within the 30-frame lost buffer.
    for _ in range(3):
        trk.update([])
    # Reappear near where it was predicted to drift.
    out = trk.update([_det(200, 200)])
    confirmed = [t for t in out if t.state is TrackState.CONFIRMED]
    assert len(confirmed) == 1
    assert confirmed[0].track_id == original_id


def test_no_id_resurrection_after_death():
    # Gone for LONGER than track_buffer -> the track dies; a later detection at the same
    # place gets a NEW, strictly-greater id. A removed track must never come back.
    trk = ByteTracker(min_hits=1, track_buffer=5)
    first = trk.update([_det(200, 200)])
    dead_id = first[0].track_id
    for _ in range(8):  # exceed the 5-frame buffer
        trk.update([])
    out = trk.update([_det(200, 200)])
    new_id = out[0].track_id
    assert new_id != dead_id
    assert new_id > dead_id  # ids are monotonic, never reused


# --- two-stage association: the ByteTrack-vs-SORT discriminator --------------


def test_low_conf_detection_sustains_existing_track():
    # The defining ByteTrack behavior: an established track whose detection drops to LOW
    # confidence is still matched (round 2) rather than lost. SORT would drop it.
    trk = ByteTracker(min_hits=1, track_thresh=0.5)
    first = trk.update([_det(150, 150, conf=0.9)])
    original_id = first[0].track_id
    # Same object, now only a low-conf detection (below the high gate, above the floor).
    out = trk.update([_det(153, 151, conf=0.3)])
    confirmed = [t for t in out if t.state is TrackState.CONFIRMED]
    assert len(confirmed) == 1
    assert confirmed[0].track_id == original_id


def test_spurious_low_conf_detection_does_not_confirm_a_track():
    # A lone low-conf detection with no prior track must NOT spawn a confirmed track —
    # only high-conf detections initiate. (Otherwise round-2 noise becomes survivors.)
    trk = ByteTracker(min_hits=1, track_thresh=0.5)
    out = trk.update([_det(150, 150, conf=0.2)])
    confirmed = [t for t in out if t.state is TrackState.CONFIRMED]
    assert confirmed == []


# --- determinism ------------------------------------------------------------


def test_deterministic_id_assignment():
    # Same fixture twice -> identical id assignments (no RNG anywhere in the tracker).
    def run() -> list[set[int]]:
        trk = ByteTracker(min_hits=1)
        history = []
        for k in range(6):
            out = trk.update([_det(100 + 4 * k, 100), _det(300, 300 + 4 * k)])
            history.append(_ids(out))
        return history

    assert run() == run()


# --- GMC seam (forward-looking for Task 3.2) --------------------------------


def test_update_accepts_identity_gmc_warp_as_noop():
    # The tracker exposes a gmc_warp seam (Task 3.2 fills it). Passing the identity warp
    # must be a no-op versus not passing one at all — so 3.2 has a tested seam.
    import numpy as np

    identity = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float64)

    trk_a = ByteTracker(min_hits=1)
    trk_b = ByteTracker(min_hits=1)
    for k in range(5):
        dets = [_det(120 + 5 * k, 140)]
        out_a = trk_a.update(dets)
        out_b = trk_b.update(dets, gmc_warp=identity)
        assert _ids(out_a) == _ids(out_b)
        assert [t.box_xyxy for t in out_a] == pytest.approx(
            [t.box_xyxy for t in out_b]
        )
