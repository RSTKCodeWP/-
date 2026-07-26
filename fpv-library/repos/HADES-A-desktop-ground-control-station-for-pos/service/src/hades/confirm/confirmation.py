"""Confirmation rule + world-clustering (Task 3.6).

Promotes each track's DISPLAY-PRIORITY TIER (contact → candidate → strong) from
persistence + accumulated confidence + world-location clustering. It NEVER gates
visibility: any detected track is at least a CONTACT. Promotion to STRONG is what makes a
contact eligible for the expensive Localizer (Phase 4) and, ultimately, dispatch — so a
false STRONG is the cardinal sin and the design is hardened against flicker accordingly.

Design (hardened by adversarial red-team — see the test module docstring):

- **Promotion driver = a leaky-integrator decay score**, not a raw N-of-M count. Every
  frame `score *= decay`; on a hit `score += conf`. Sparse/periodic flicker engineered to
  hit exactly N-of-M is starved by the decay between bursts (the resonant-aliasing attack
  a pure count cannot reject). A human-legible `hits in last M` is kept as a floor/UI
  number, not the driver.

- **Schmitt hysteresis**: promote at `θ_up`, demote only below `θ_down < θ_up`, and the
  decay coast carries a STRONG contact through a short occlusion. A demote never deletes
  the contact (recall-first applies on the way down too).

- **World-cluster corroboration counts ONE centroid vote per track** (never per-frame
  points — that is fake self-corroboration), and DROPS duplicate detector firings (two
  track IDs whose boxes co-occur with high IoU are one source, not two corroborators). Two
  *distinct, de-duplicated* tracks whose centroids fall within a range-scaled radius
  corroborate — the ego-motion-fragmented-survivor win. Only gate-PASSING points vote.

KNOWN LIMITATION (documented, not handled): this is a temporal/spatial CONSISTENCY filter,
not a semantic classifier. A reliably-detected non-person (AC unit, sun glint) produces a
stable, persistent, tight track and WILL reach STRONG — possibly more confidently than a
marginal real survivor. Mitigation is upstream (detector precision) and downstream
(mandatory operator confirmation before dispatch). STRONG means "worth a human look,"
never autonomous dispatch.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum

from hades.locate.frame_gate import GateVerdict
from hades.locate.projector import GroundPoint

_METERS_PER_DEG = 111320.0


class Tier(IntEnum):
    """Display-priority tier. Ordered (IntEnum) so promote/demote comparisons read simply."""

    CONTACT = 0  # ≥1 detection; always visible (recall-first)
    CANDIDATE = 1  # persistence/confidence over the candidate threshold
    STRONG = 2  # very-persistent high-conf OR world-cluster corroborated


@dataclass
class _TrackState:
    """Per-track sliding-window state. The public output is just the tier."""

    window: deque = field(default_factory=lambda: deque(maxlen=_WINDOW_M))
    score: float = 0.0  # leaky-integrator decay score (the promotion driver)
    tier: Tier = Tier.CONTACT
    operator_locked: bool = False
    last_seen_frame: int = 0  # frame index of the most recent hit (for eviction)
    # Per-frame record kept for cluster de-dup: (lat, lon, conf, verdict, box, seen_frame).
    points: list = field(default_factory=list)

    def centroid(self) -> tuple[float, float] | None:
        """Confidence-weighted mean of this track's gate-PASSING points (one cluster vote).

        None when the track has no fusable point — it then casts no corroboration vote
        (but stays visible). Mean (not median) keeps it numpy-free and cheap; jitter
        averages out, which is the intended within-track smoothing.
        """
        passing = [
            (lat, lon, conf)
            for (lat, lon, conf, verdict, _box, _f) in self.points
            if verdict is not GateVerdict.REJECT and lat is not None
        ]
        if not passing:
            return None
        wsum = sum(c for _, _, c in passing)
        if wsum <= 0:
            return None
        lat = sum(lat * c for lat, _, c in passing) / wsum
        lon = sum(lon * c for _, lon, c in passing) / wsum
        return lat, lon


# --- tunable constants (module-level, not a config object — solo-maintainer simplicity) --
_WINDOW_M = 30  # sliding window length (frames) ≈ 3 s at 10 fps detection cadence
_DECAY = 0.9  # leaky-integrator decay per frame; gaps multiply this, starving flicker
# Schmitt thresholds on the decay score (up > down so tiers don't flap at the boundary).
_CAND_UP, _CAND_DOWN = 1.5, 0.8
_STRONG_UP, _STRONG_DOWN = 4.5, 2.5
_SOLO_STRONG = 6.5  # a lone very-persistent high-conf track reaches strong without a cluster
# World-cluster corroboration radius grows with slant range (scatter grows with range /
# obliquity; a fixed radius mis-handles one regime). R = base + k·range, in meters. The
# disk-overlap-of-uncertainty upgrade is deferred to Phase 4 where per-track σ exists.
_CLUSTER_R_BASE_M = 8.0
_CLUSTER_R_PER_RANGE = 0.05  # +5 m radius per 100 m of slant range
_SLANT_RANGE_CEIL_M = 5000.0  # clamp a pathological slant_range so the radius can't explode
_DUP_IOU = 0.5  # boxes co-occurring above this IoU = one detector source, de-duplicated
_DUP_WORLD_M = 10.0  # ...AND centroids within this — else they are distinct close survivors
_EVICT_AFTER = 2 * _WINDOW_M  # frames silent before a dead track is evicted (no ghosts/leak)


def _iou(a: tuple, b: tuple) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def _ground_dist_m(p: tuple[float, float], q: tuple[float, float]) -> float:
    """Flat-earth meters between two (lat, lon) — small-angle, matches the geometry §3.1."""
    dlat = (p[0] - q[0]) * _METERS_PER_DEG
    dlon = (p[1] - q[1]) * _METERS_PER_DEG * math.cos(math.radians(p[0]))
    return math.hypot(dlat, dlon)


class Confirmation:
    """Stateful confirmation rule. `update` once per frame returns {track_id: Tier}."""

    def __init__(self) -> None:
        self._tracks: dict[int, _TrackState] = {}
        self._frame = 0
        self._last_vote_count = 0
        # Persistent record of track-id pairs proven to be ONE detector source (they
        # co-occurred with overlapping boxes at the same world point). Kept beyond the
        # sliding window so de-dup does not "forget" and let a duplicate fake-corroborate
        # once the co-occurrence frames age out (review H2). Symmetric set of frozensets.
        self._duplicate_pairs: set[frozenset[int]] = set()

    def update(
        self, ground_points: dict[int, GroundPoint], *, slant_range: float = 100.0
    ) -> dict[int, Tier]:
        """Advance one frame. `ground_points` maps track_id → its GroundPoint this frame
        (absent track_ids are misses). `slant_range` (m) scales the cluster radius."""
        self._frame += 1
        seen = set(ground_points)

        # 1. Decay every known track; add this frame's hit (conf) to seen ones.
        for tid, st in self._tracks.items():
            st.score *= _DECAY
            hit = tid in seen
            st.window.append(hit)
            if hit:
                gp = ground_points[tid]
                st.score += gp.conf
                st.last_seen_frame = self._frame
                st.points.append(
                    (gp.lat, gp.lon, gp.conf, gp.verdict, gp.detection.box_xyxy, self._frame)
                )
                self._prune(st)

        # 2. Initiate states for newly-seen tracks.
        for tid in seen:
            if tid not in self._tracks:
                st = _TrackState()
                gp = ground_points[tid]
                st.score += gp.conf
                st.window.append(True)
                st.last_seen_frame = self._frame
                st.points.append(
                    (gp.lat, gp.lon, gp.conf, gp.verdict, gp.detection.box_xyxy, self._frame)
                )
                self._tracks[tid] = st

        # 3. Record duplicate-source pairs seen THIS frame (persists beyond the window).
        self._record_duplicates(seen)

        # 4. Evict tracks silent past the eviction horizon (no memory leak / dead ghosts).
        self._evict_dead()

        # 5. World-cluster corroboration (de-duplicated, one vote per track).
        corroborated = self._corroborated_tracks(slant_range)
        self._last_vote_count = sum(
            1 for st in self._tracks.values() if st.centroid() is not None
        )

        # 6. Re-evaluate each track's tier with Schmitt hysteresis.
        out: dict[int, Tier] = {}
        for tid, st in self._tracks.items():
            st.tier = self._tier_for(st, corroborated=tid in corroborated)
            out[tid] = st.tier
        return out

    def operator_promote(self, track_id: int) -> None:
        """Human-as-confirmer (M6): lock a contact at STRONG, immune to auto-demote."""
        st = self._tracks.setdefault(track_id, _TrackState())
        st.last_seen_frame = self._frame  # a human touch keeps it from being evicted
        st.operator_locked = True
        st.tier = Tier.STRONG

    def cluster_vote_count(self) -> int:
        """Number of tracks that cast a corroboration vote on the last frame (for tests)."""
        return self._last_vote_count

    def live_track_count(self) -> int:
        """Number of tracks currently retained (dead tracks are evicted — review H1)."""
        return len(self._tracks)

    # --- internals ---

    def _prune(self, st: _TrackState) -> None:
        # Keep only points within the recent window so a long-dead point can't corroborate.
        cutoff = self._frame - _WINDOW_M
        st.points = [p for p in st.points if p[5] > cutoff]

    def _evict_dead(self) -> None:
        """Drop tracks silent past the eviction horizon — bounds memory and stops a dead
        STRONG track from emitting/voting forever (review H1). Operator-locked tracks are
        kept (a human decision is sticky). Their duplicate-pair records are dropped too."""
        dead = [
            tid
            for tid, st in self._tracks.items()
            if not st.operator_locked
            and self._frame - st.last_seen_frame > _EVICT_AFTER
        ]
        for tid in dead:
            del self._tracks[tid]
        if dead:
            dead_set = set(dead)
            self._duplicate_pairs = {
                pair for pair in self._duplicate_pairs if not (pair & dead_set)
            }

    def _tier_for(self, st: _TrackState, *, corroborated: bool) -> Tier:
        if st.operator_locked:
            return Tier.STRONG

        current = st.tier
        # A track may only be promoted to (or held at) STRONG if it has a VALID fused
        # coordinate. A track whose points are all gate-REJECT or un-projectable (lat None)
        # accrues score but has nothing to dispatch to — promoting it would send a team to
        # a coordinate that does not exist (Codex P1). It stays visible at a lower tier.
        has_coord = st.centroid() is not None

        # STRONG: corroborated cluster at/above the strong threshold, OR a lone track at the
        # higher solo bar. Schmitt: once STRONG, only demote below θ_down.
        strong_ok = has_coord and (
            (st.score >= _STRONG_UP and corroborated) or st.score >= _SOLO_STRONG
        )
        if current is Tier.STRONG:
            if has_coord and st.score >= _STRONG_DOWN:
                return Tier.STRONG  # coast (decay carries it through short occlusion)
        elif strong_ok:
            return Tier.STRONG

        # CANDIDATE with hysteresis.
        if current >= Tier.CANDIDATE:
            if st.score >= _CAND_DOWN:
                return Tier.CANDIDATE
        elif st.score >= _CAND_UP:
            return Tier.CANDIDATE

        return Tier.CONTACT

    def _corroborated_tracks(self, slant_range: float) -> set[int]:
        """Track ids whose centroid is within the range-scaled radius of ≥1 OTHER distinct,
        de-duplicated track's centroid. The radius grows with slant range (scatter grows
        with range/obliquity) but is CLAMPED so a pathological pose can't explode it into a
        map-spanning radius that corroborates everything (review M3). A pair proven to be
        one detector source (review H2) never corroborates."""
        clamped = min(max(slant_range, 0.0), _SLANT_RANGE_CEIL_M)
        radius = _CLUSTER_R_BASE_M + _CLUSTER_R_PER_RANGE * clamped
        votes = {
            tid: c
            for tid, st in self._tracks.items()
            if (c := st.centroid()) is not None
        }
        corroborated: set[int] = set()
        ids = list(votes)
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                if frozenset((a, b)) in self._duplicate_pairs:
                    continue  # one detector source (persisted), not two corroborators
                dist = _ground_dist_m(votes[a], votes[b])
                if dist > radius:
                    continue  # too far apart on the ground to corroborate
                if self._flickering_same_source(a, b, dist):
                    continue  # one flickering source churning ids at one spot, not a relay
                corroborated.add(a)
                corroborated.add(b)
        return corroborated

    def _flickering_same_source(self, a: int, b: int, dist_m: float) -> bool:
        """True when two ids are ONE flickering source masquerading as corroboration.

        The flicker signature is specific: the two ids sit at the SAME world point
        (`dist_m` ≈ 0) AND their active frames INTERLEAVE (alternating, never co-occurring,
        never a clean sequential hand-off). We must NOT reject the two legitimate cases that
        also land within the cluster radius:
          - two DISTINCT concurrent survivors → different centroids (`dist_m` > _DUP_WORLD_M);
          - a genuine fragmented-survivor RELAY → same spot but DISJOINT spans (a hand-off).
        So only a same-spot, interleaved (not disjoint) pair is the flicker."""
        if dist_m > _DUP_WORLD_M:
            return False  # distinct world points → genuinely separate sources, allow

        frames_a = sorted(p[5] for p in self._tracks[a].points)
        frames_b = sorted(p[5] for p in self._tracks[b].points)
        if not frames_a or not frames_b:
            return False
        # Disjoint spans (A entirely before B, or vice-versa) = a clean relay → allow.
        if frames_a[-1] < frames_b[0] or frames_b[-1] < frames_a[0]:
            return False
        # Spans overlap in time but the tracks never share a frame → they interleave, i.e.
        # one source alternating between two ids. That is the flicker; reject corroboration.
        return not (set(frames_a) & set(frames_b))

    def _record_duplicates(self, seen: set[int]) -> None:
        """Persist track-id pairs that are one detector source: tracks seen THIS frame whose
        boxes overlap above `_DUP_IOU` AND whose centroids are within `_DUP_WORLD_M`.

        The box-IoU gate alone is two-sided wrong: it FORGETS once co-occurrence ages out
        of the window (review H2 — fixed by persisting the pair here), and it wrongly merges
        two genuinely-distinct close survivors whose boxes happen to overlap (review M4 —
        fixed by also requiring world-point proximity). A SEQUENTIAL relay never co-occurs,
        so it is never recorded as a duplicate — the fragmented-survivor corroboration win
        is preserved."""
        present = sorted(seen)
        for i, a in enumerate(present):
            box_a = self._last_box(a)
            cen_a = self._tracks[a].centroid()
            if box_a is None:
                continue
            for b in present[i + 1 :]:
                box_b = self._last_box(b)
                cen_b = self._tracks[b].centroid()
                if box_b is None or _iou(box_a, box_b) <= _DUP_IOU:
                    continue
                # Distinct close survivors (overlapping boxes, separated on the ground) are
                # NOT one source — require world-point proximity to call it a duplicate.
                if cen_a is not None and cen_b is not None:
                    if _ground_dist_m(cen_a, cen_b) > _DUP_WORLD_M:
                        continue
                self._duplicate_pairs.add(frozenset((a, b)))

    def _last_box(self, tid: int) -> tuple | None:
        """Most recent box for a track this frame (from its point history)."""
        pts = self._tracks[tid].points
        for (_lat, _lon, _c, _v, box, f) in reversed(pts):
            if f == self._frame:
                return box
        return None
