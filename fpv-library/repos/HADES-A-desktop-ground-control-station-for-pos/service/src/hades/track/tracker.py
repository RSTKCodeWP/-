"""ByteTracker — a from-scratch numpy ByteTrack (Task 3.1).

Stateful `list[Detection] -> list[Track]`: assigns persistent IDs, bridges the
10→30fps gap with Kalman prediction, survives short occlusions, and NEVER resurrects a
dead ID. The defining ByteTrack behavior is **two-stage association**: high-confidence
detections are matched first, then *low*-confidence detections are matched only against
the tracks still unmatched after round one — this rescues a real survivor whose box
momentarily drops below the detection gate (the SAR recall-first doctrine) without
letting lone low-conf noise spawn a track (only high-conf detections initiate).

Deliberately torch-free (the project keeps PyTorch out of runtime/CI): the only
dependency is scipy's `linear_sum_assignment` for the optimal IoU matching. No RNG —
the tracker is fully deterministic, which the CI fixtures assert.

Coordinates are `box_xyxy` in original-frame pixels throughout (DESIGN.md §3.2); the
internal Kalman works in XYAH (see `kalman.py`) and converts at its boundary only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from scipy.optimize import linear_sum_assignment

from hades.detect.detector import Detection
from hades.track.kalman import KalmanFilter, xyah_to_xyxy, xyxy_to_xyah


class TrackState(Enum):
    """Lifecycle of a track. TENTATIVE → CONFIRMED → LOST → (removed, never resurrected)."""

    TENTATIVE = "tentative"  # newly initiated, not yet enough hits to be trusted
    CONFIRMED = "confirmed"  # matched on the current frame, surfaced to the pipeline
    LOST = "lost"  # unmatched but within the lost buffer; may still come back


@dataclass(frozen=True)
class Track:
    """A tracked object surfaced to the pipeline (box in original-frame pixels)."""

    track_id: int
    box_xyxy: tuple[float, float, float, float]
    state: TrackState
    conf: float = 0.0
    age: int = 0  # frames since the track was created
    hits: int = 0  # number of frames the track was matched to a detection
    time_since_update: int = 0  # frames since last matched (0 == matched this frame)


def _iou_matrix(tracks_xyxy: np.ndarray, dets_xyxy: np.ndarray) -> np.ndarray:
    """IoU between every (track, detection) pair. Shapes (T,4),(D,4) → (T,D)."""
    if len(tracks_xyxy) == 0 or len(dets_xyxy) == 0:
        return np.zeros((len(tracks_xyxy), len(dets_xyxy)), dtype=np.float64)

    tx1, ty1, tx2, ty2 = (tracks_xyxy[:, i][:, None] for i in range(4))
    dx1, dy1, dx2, dy2 = (dets_xyxy[:, i][None, :] for i in range(4))

    inter_w = np.clip(np.minimum(tx2, dx2) - np.maximum(tx1, dx1), 0, None)
    inter_h = np.clip(np.minimum(ty2, dy2) - np.maximum(ty1, dy1), 0, None)
    inter = inter_w * inter_h

    area_t = ((tx2 - tx1) * (ty2 - ty1))
    area_d = ((dx2 - dx1) * (dy2 - dy1))
    union = area_t + area_d - inter
    # Guard the 0/0 a zero-area box would produce (the §3.2/NMS division trap class).
    return np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)


def _associate(
    track_boxes: np.ndarray, det_boxes: np.ndarray, iou_thresh: float
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Optimal IoU assignment. Returns (matches, unmatched_track_idx, unmatched_det_idx).

    Indices are into the *input arrays*, not track ids. A pair is only kept if its IoU
    clears `iou_thresh` (the Hungarian optimum can still include a bad pair, so we filter).
    """
    n_t, n_d = len(track_boxes), len(det_boxes)
    if n_t == 0 or n_d == 0:
        return [], list(range(n_t)), list(range(n_d))

    iou = _iou_matrix(track_boxes, det_boxes)
    # linear_sum_assignment minimises cost; we want to maximise IoU → minimise (1 - IoU).
    row_idx, col_idx = linear_sum_assignment(1.0 - iou)

    matches: list[tuple[int, int]] = []
    matched_t: set[int] = set()
    matched_d: set[int] = set()
    for r, c in zip(row_idx, col_idx):
        if iou[r, c] >= iou_thresh:
            matches.append((int(r), int(c)))
            matched_t.add(int(r))
            matched_d.add(int(c))

    unmatched_t = [i for i in range(n_t) if i not in matched_t]
    unmatched_d = [i for i in range(n_d) if i not in matched_d]
    return matches, unmatched_t, unmatched_d


@dataclass
class _Track:
    """Internal mutable track carrying Kalman state. Public `Track` is the snapshot."""

    track_id: int
    mean: np.ndarray
    covariance: np.ndarray
    state: TrackState
    conf: float
    age: int = 0
    hits: int = 0
    time_since_update: int = 0
    _history: list = field(default_factory=list)

    def box_xyxy(self) -> tuple[float, float, float, float]:
        return xyah_to_xyxy(self.mean)


class ByteTracker:
    """Two-stage ByteTrack association over a shared constant-velocity Kalman filter.

    Args:
        track_thresh: high/low confidence split. Detections ≥ this initiate and match in
            round 1; detections in `[det_thresh, track_thresh)` only match (round 2) and
            never initiate a track.
        det_thresh: floor below which a detection is ignored entirely.
        match_thresh: IoU floor for round-1 (high-conf) association.
        match_thresh_low: IoU floor for round-2 (low-conf) association — TIGHTER than
            round 1 (canonical ByteTrack: 0.5 vs 0.2). A low-conf detection is noisier, so
            it must overlap an existing track more closely to link; a loose floor here would
            attach round-2 garbage to a real track. Round 2 recovers a momentarily-faint
            box on an ESTABLISHED track, it does not chase weak matches.
        track_buffer: frames a LOST track is kept alive (and re-matchable) before it is
            permanently removed. At ~10fps detection cadence, 30 ≈ 3s of occlusion.
        min_hits: matches required before a TENTATIVE track is CONFIRMED (surfaced).
    """

    def __init__(
        self,
        track_thresh: float = 0.5,
        det_thresh: float = 0.1,
        match_thresh: float = 0.2,
        match_thresh_low: float = 0.5,
        track_buffer: int = 30,
        min_hits: int = 3,
    ) -> None:
        self.track_thresh = track_thresh
        self.det_thresh = det_thresh
        self.match_thresh = match_thresh
        self.match_thresh_low = match_thresh_low
        self.track_buffer = track_buffer
        self.min_hits = min_hits

        self._kf = KalmanFilter()
        self._tracks: list[_Track] = []
        self._next_id = 1  # monotonic; ids are never reused (no resurrection)

    def _new_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    def update(
        self,
        detections: list[Detection],
        gmc_warp: np.ndarray | None = None,
    ) -> list[Track]:
        """Advance one detection frame and return the active (CONFIRMED) tracks.

        `gmc_warp` (Task 3.2) is an optional 2×3 affine mapping the *previous* frame's
        pixels into the *current* frame; when supplied it warps each track's predicted
        position before association so a moving camera does not break IoU matching. The
        identity warp is a no-op.
        """
        # 1. Predict every existing track forward one frame, then apply ego-motion.
        for t in self._tracks:
            t.mean, t.covariance = self._kf.predict(t.mean, t.covariance)
            t.age += 1
            t.time_since_update += 1
        if gmc_warp is not None:
            self._apply_gmc(gmc_warp)

        # 2. Split detections into high / low confidence (the ByteTrack two-stage split).
        high = [d for d in detections if d.conf >= self.track_thresh]
        low = [
            d for d in detections if self.det_thresh <= d.conf < self.track_thresh
        ]

        # 3. Round 1: match high-conf detections against all live (non-removed) tracks.
        live = self._tracks  # all are still alive at this point
        live_boxes = np.array([t.box_xyxy() for t in live], dtype=np.float64).reshape(-1, 4)
        high_boxes = np.array([_box(d) for d in high], dtype=np.float64).reshape(-1, 4)
        matches, u_tracks, u_dets = _associate(live_boxes, high_boxes, self.match_thresh)

        matched_track_idx: set[int] = set()
        for ti, di in matches:
            self._mark_matched(live[ti], high[di])
            matched_track_idx.add(ti)

        # 4. Round 2: low-conf detections vs ONLY the tracks unmatched in round 1.
        r1_unmatched = [live[i] for i in u_tracks]
        r1_boxes = np.array(
            [t.box_xyxy() for t in r1_unmatched], dtype=np.float64
        ).reshape(-1, 4)
        low_boxes = np.array([_box(d) for d in low], dtype=np.float64).reshape(-1, 4)
        matches_low, u_tracks_low, _ = _associate(
            r1_boxes, low_boxes, self.match_thresh_low
        )
        for ti, di in matches_low:
            self._mark_matched(r1_unmatched[ti], low[di])

        # 5. Tracks still unmatched after both rounds become / stay LOST.
        still_unmatched = [r1_unmatched[i] for i in u_tracks_low]
        for t in still_unmatched:
            if t.state is not TrackState.LOST:
                t.state = TrackState.LOST

        # 6. Initiate NEW tracks from unmatched HIGH-conf detections only (round-2 noise
        #    never initiates — that is the false-survivor guard).
        for di in u_dets:
            self._initiate(high[di])

        # 7. Remove tracks that have been lost longer than the buffer (no resurrection).
        self._tracks = [
            t
            for t in self._tracks
            if not (
                t.state is TrackState.LOST and t.time_since_update > self.track_buffer
            )
        ]

        # 8. Surface the snapshot of currently-confirmed, this-frame-matched tracks.
        return [self._snapshot(t) for t in self._tracks if self._is_active(t)]

    def _mark_matched(self, t: _Track, det: Detection) -> None:
        measurement = xyxy_to_xyah(_box(det))
        t.mean, t.covariance = self._kf.update(t.mean, t.covariance, measurement)
        t.hits += 1
        t.time_since_update = 0
        t.conf = det.conf
        # A matched TENTATIVE/LOST track is promoted to CONFIRMED once it has enough hits;
        # a re-found LOST track already has its hits so it returns to CONFIRMED immediately.
        # A track that matches but has not yet earned min_hits stays TENTATIVE. A CONFIRMED
        # track that matches simply stays CONFIRMED.
        if t.state is not TrackState.CONFIRMED:
            t.state = (
                TrackState.CONFIRMED if t.hits >= self.min_hits else TrackState.TENTATIVE
            )

    def _initiate(self, det: Detection) -> None:
        mean, covariance = self._kf.initiate(xyxy_to_xyah(_box(det)))
        state = TrackState.CONFIRMED if self.min_hits <= 1 else TrackState.TENTATIVE
        self._tracks.append(
            _Track(
                track_id=self._new_id(),
                mean=mean,
                covariance=covariance,
                state=state,
                conf=det.conf,
                age=0,
                hits=1,
                time_since_update=0,
            )
        )

    def _is_active(self, t: _Track) -> bool:
        # Active == confirmed AND matched this frame (so the pipeline sees a live contact,
        # not a coasting prediction). Lost/tentative tracks are not surfaced as contacts.
        return t.state is TrackState.CONFIRMED and t.time_since_update == 0

    def _snapshot(self, t: _Track) -> Track:
        return Track(
            track_id=t.track_id,
            box_xyxy=t.box_xyxy(),
            state=t.state,
            conf=t.conf,
            age=t.age,
            hits=t.hits,
            time_since_update=t.time_since_update,
        )

    def _apply_gmc(self, warp: np.ndarray) -> None:
        """Warp each track's predicted center by the 2×3 affine (ego-motion comp).

        Only the position center is moved (the minimal viable warp that passes the
        association test); the affine's linear block also scales/rotates the velocity so
        a panning camera does not inject phantom track velocity. The identity warp leaves
        everything unchanged (it is a genuine no-op).
        """
        linear = warp[:2, :2]
        translation = warp[:2, 2]
        for t in self._tracks:
            cx, cy = t.mean[0], t.mean[1]
            new_center = linear @ np.array([cx, cy]) + translation
            t.mean[0], t.mean[1] = new_center[0], new_center[1]
            # Rotate/scale the center velocity components by the same linear block.
            vel = linear @ np.array([t.mean[4], t.mean[5]])
            t.mean[4], t.mean[5] = vel[0], vel[1]


def _box(det: Detection) -> tuple[float, float, float, float]:
    return det.box_xyxy
