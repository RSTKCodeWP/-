"""Phase B (B3): multi-track manager with trajectory-continuity confirmation.

The single-target :class:`~fpv.seeker.track.ThermalLockTracker` holds the ONE committed lock.
This manager sits *beside* it as the look-down false-alarm BACKSTOP: it keeps several
lightweight constant-velocity tracklets and only ``CONFIRM``s one when it has been seen in
``confirm_hits`` of the last ``confirm_window`` frames AND its motion is trajectory-continuous
(low residual to its own CV prediction).

Why both conditions?  A single-frame **parallax flash** (a ground feature the ego-motion
mask failed to cancel for one frame) spawns a tracklet that dies before it can reach the
N-of-M hit count.  A flickering clutter blob that jumps to a new place every frame DOES
accumulate hits, but its CV-prediction residual is large, so the continuity test refuses it.
Only a genuinely-moving target -- persistent AND smooth -- is confirmed.  This never touches
the centroid/LOS/tracker spine (Invariant 2); it only decides which blobs are trustworthy
movers, which the pipeline uses to gate fresh acquisition.

Pure-python and numpy-free (mirrors ``track.py``); blobs are duck-typed on ``.centroid_px``.
"""

from __future__ import annotations

import itertools
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable

SCHEMA: str = "fpv_multitrack.v1"


@dataclass(frozen=True)
class MultiTrackConfig:
    """Thresholds for the multi-track manager and its N-of-M continuity confirmation.

    Attributes
    ----------
    gate_px:
        Nearest-neighbour association gate radius (pixels) around a tracklet's CV prediction.
    confirm_hits / confirm_window:
        N-of-M rule: a tracklet is eligible for confirmation once it has ``confirm_hits``
        associations within the last ``confirm_window`` frames.
    max_continuity_residual_px:
        Mean distance between a tracklet's observed centroid and its CV-predicted centroid,
        over its recent history, must stay at/below this for confirmation -- the
        trajectory-continuity (anti-parallax-flash) test.
    min_history_for_residual:
        Minimum number of residual samples before the continuity test is meaningful.
    max_misses:
        Consecutive missed frames before a tracklet is dropped.
    max_tracklets:
        Cap on simultaneously-maintained tracklets (clutter spam guard).
    """

    gate_px: float = 48.0
    confirm_hits: int = 3
    confirm_window: int = 5
    max_continuity_residual_px: float = 6.0
    min_history_for_residual: int = 3
    max_misses: int = 5
    max_tracklets: int = 12

    def __post_init__(self) -> None:
        if self.confirm_hits < 1:
            raise ValueError("confirm_hits must be >= 1")
        if self.confirm_window < self.confirm_hits:
            raise ValueError("confirm_window must be >= confirm_hits")
        if self.gate_px <= 0.0:
            raise ValueError("gate_px must be positive")
        if self.max_tracklets < 1:
            raise ValueError("max_tracklets must be >= 1")


@dataclass
class Tracklet:
    """One constant-velocity hypothesis maintained by :class:`MultiTrackManager`."""

    id: int
    centroid: tuple[float, float]
    velocity: tuple[float, float] = (0.0, 0.0)
    hits: int = 0
    misses: int = 0                                # consecutive misses
    age: int = 0
    confirmed: bool = False
    _window: deque[bool] = field(default_factory=lambda: deque(maxlen=5))
    _residual_sum: float = 0.0
    _residual_n: int = 0
    _last_centroid: tuple[float, float] | None = None

    def predict(self) -> tuple[float, float]:
        """CV prediction for the upcoming frame (advances by velocity per missed frame)."""
        cx, cy = self.centroid
        vx, vy = self.velocity
        step = self.misses + 1
        return (cx + vx * step, cy + vy * step)

    def mean_residual(self) -> float:
        return self._residual_sum / self._residual_n if self._residual_n else float("inf")

    def on_hit(self, centroid: tuple[float, float], predicted: tuple[float, float]) -> None:
        # Continuity residual: how far the observation fell from the CV prediction.
        self._residual_sum += math.hypot(centroid[0] - predicted[0], centroid[1] - predicted[1])
        self._residual_n += 1
        # Velocity from the last associated centroid (1-frame normalised).
        if self._last_centroid is not None:
            self.velocity = (centroid[0] - self._last_centroid[0],
                             centroid[1] - self._last_centroid[1])
        self._last_centroid = centroid
        self.centroid = centroid
        self.hits += 1
        self.misses = 0
        self.age += 1
        self._window.append(True)

    def on_miss(self) -> None:
        self.centroid = self.predict()             # coast on CV
        self.misses += 1
        self.age += 1
        self._window.append(False)

    def hits_in_window(self) -> int:
        return sum(self._window)


@dataclass(frozen=True)
class TrackletSnapshot:
    """Immutable per-frame view of a tracklet (what the pipeline consumes)."""

    id: int
    centroid_px: tuple[float, float]
    confirmed: bool
    hits: int
    misses: int
    mean_residual_px: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "id": self.id,
            "centroid_px": list(self.centroid_px),
            "confirmed": self.confirmed,
            "hits": self.hits,
            "misses": self.misses,
            "mean_residual_px": round(self.mean_residual_px, 3),
        }


class MultiTrackManager:
    """Greedy multi-hypothesis tracker with N-of-M trajectory-continuity confirmation."""

    def __init__(self, config: MultiTrackConfig | None = None) -> None:
        self._cfg = config or MultiTrackConfig()
        self._tracks: list[Tracklet] = []
        self._ids = itertools.count(1)

    @property
    def gate_px(self) -> float:
        """Association/match gate radius (pixels)."""
        return self._cfg.gate_px

    @property
    def tracklets(self) -> list[Tracklet]:
        return list(self._tracks)

    def confirmed_centroids(self) -> list[tuple[float, float]]:
        """Centroids of every currently-confirmed (trajectory-continuous) tracklet."""
        return [t.centroid for t in self._tracks if t.confirmed]

    def reset(self) -> None:
        self._tracks.clear()

    def update(self, blobs: Iterable[Any], frame_id: int = 0) -> list[TrackletSnapshot]:
        """Advance every tracklet one frame against this frame's blobs.

        Returns a snapshot per surviving tracklet (confirmed flag included).
        """
        cfg = self._cfg
        # Finite-guard the blob centroids (a NaN descriptor must not poison association).
        cents: list[tuple[float, float]] = []
        for b in blobs:
            cx, cy = b.centroid_px
            if math.isfinite(cx) and math.isfinite(cy):
                cents.append((float(cx), float(cy)))

        # 1. predict every tracklet
        preds = [t.predict() for t in self._tracks]

        # 2. greedy nearest-neighbour association within gate (each track/blob used once)
        pairs: list[tuple[float, int, int]] = []
        for ti, (px, py) in enumerate(preds):
            for bi, (bx, by) in enumerate(cents):
                d = math.hypot(bx - px, by - py)
                if d <= cfg.gate_px:
                    pairs.append((d, ti, bi))
        pairs.sort(key=lambda p: p[0])
        used_t: set[int] = set()
        used_b: set[int] = set()
        matched: dict[int, int] = {}
        for d, ti, bi in pairs:
            if ti in used_t or bi in used_b:
                continue
            used_t.add(ti)
            used_b.add(bi)
            matched[ti] = bi

        # 3. update matched tracklets / 4. coast the unmatched
        for ti, t in enumerate(self._tracks):
            if ti in matched:
                t.on_hit(cents[matched[ti]], preds[ti])
            else:
                t.on_miss()

        # 5. spawn a tracklet for each unmatched blob (respecting the cap)
        for bi, c in enumerate(cents):
            if bi in used_b:
                continue
            if len(self._tracks) >= cfg.max_tracklets:
                break
            tl = Tracklet(id=next(self._ids), centroid=c, _last_centroid=c)
            tl.hits = 1
            tl.age = 1
            tl._window = deque([True], maxlen=cfg.confirm_window)
            self._tracks.append(tl)

        # 6. confirm (N-of-M + continuity) and prune stale tracklets
        for t in self._tracks:
            self._maybe_confirm(t)
        self._tracks = [t for t in self._tracks if t.misses <= cfg.max_misses]

        return [
            TrackletSnapshot(
                id=t.id, centroid_px=t.centroid, confirmed=t.confirmed,
                hits=t.hits, misses=t.misses, mean_residual_px=t.mean_residual(),
            )
            for t in self._tracks
        ]

    def _maybe_confirm(self, t: Tracklet) -> None:
        cfg = self._cfg
        # Window may have been created with the default maxlen=5; normalise to config.
        if t._window.maxlen != cfg.confirm_window:
            t._window = deque(t._window, maxlen=cfg.confirm_window)
        if t.confirmed:
            return
        if (t.hits_in_window() >= cfg.confirm_hits
                and t._residual_n >= cfg.min_history_for_residual
                and t.mean_residual() <= cfg.max_continuity_residual_px):
            t.confirmed = True
