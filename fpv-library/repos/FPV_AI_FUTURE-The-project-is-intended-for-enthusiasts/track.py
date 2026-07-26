"""Lean single-target lock FSM for S1 thermal seeker.

This is the **S1 perception-layer tracker** — deliberately minimal.  The full
IMM (S2) will replace the prediction model; this version uses a simple
constant-velocity 1-step predictor for coast phases.

State machine
-------------
States (mirrors ``gates/lock.py`` shape; thermal-specific names)::

    NO_TARGET      — no candidate seen yet
    CANDIDATE      — blob seen but not enough stable frames for lock
    LOCKED         — stable lock, high-confidence association
    PREDICTIVE_TRACK — lock was good, brief detection gap, CV predict + coast
    REACQUIRE      — longer loss, expanding search window, kinetic suspended
    HARD_LOST      — timeout exceeded, lock abandoned

Transitions::

    NO_TARGET → CANDIDATE    : any blob within acquisition box
    CANDIDATE → LOCKED        : stable_frame_count consecutive associations
    CANDIDATE → NO_TARGET     : association fails (too far / no blob)
    LOCKED → PREDICTIVE_TRACK : no associated blob within gate this frame
    PREDICTIVE_TRACK → LOCKED : blob re-associated within gate
    PREDICTIVE_TRACK → REACQUIRE : coast budget exceeded
    REACQUIRE → LOCKED        : blob re-associated within expanded window
    REACQUIRE → HARD_LOST     : reacquire budget exceeded
    HARD_LOST → NO_TARGET     : (automatic reset; operator must re-seed)

Seeded acquisition
------------------
The caller provides an ``acquisition_box`` (x, y, w, h) — typically derived
from the operator's aim on the seeder console — to constrain the initial
association search.  Once LOCKED, the gate expands slightly via the predicted
centroid.

Nearest-neighbour association
------------------------------
Per-frame association is nearest-neighbour in pixel Euclidean distance between
the predicted centroid and each blob's centroid.  The search window is gated:
``distance < max_gate_px`` for LOCKED, expanding to ``reacquire_expansion_factor``
multiples for REACQUIRE.

Constant-velocity coast predictor
-----------------------------------
Maintains a rolling (vx, vy) velocity estimate (pixels per millisecond) from
the last two associated observations.  During coast (PREDICTIVE_TRACK /
REACQUIRE) the predicted centroid advances by vx, vy scaled by elapsed time.
This keeps the gate centred near the expected target location and reduces
false-association probability.

FFC coast
---------
During FFC FREEZE / RECOVERING frames (``observation.is_ffc_freeze``), the
tracker automatically enters PREDICTIVE_TRACK coast without consuming the
normal lost-frame budget.  The lock survives a ~0.5 s FFC event.

Reuse shape from ``gates/lock.py``
------------------------------------
``ThermalLockTracker`` is structurally modelled on ``GateLockTracker`` (same
state enum shape, same ``update()`` → snapshot pattern, same velocity predictor
and confidence decay), but operates on ``ThermalBlob`` / ``TargetObservation``
instead of ``GateDetection``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .blob import ThermalBlob, TargetObservation

# ---------------------------------------------------------------------------
# State enums
# ---------------------------------------------------------------------------

# R4: angular-scale regime state machine (POINT -> RESOLVED -> FILL).
# Keyed on area_extended_px (the un-suppressed half-max footprint that GROWS
# monotonically with true target size), with hysteretic (Schmitt-trigger)
# up/down thresholds to prevent chatter at regime boundaries.
# This is informational only -- it NEVER moves the centroid, LOS, or guidance
# command (doctrine Inv 2).  R5 will consume it to switch the aimpoint.
class RegimeState(str, Enum):
    """Angular-scale regime of the tracked target.

    POINT     — sub-resolution; area_extended_px well below the resolve threshold.
    RESOLVED  — partially resolved; top-hat still suppresses interior, but
                area_extended_px is large enough to indicate significant subtense.
    FILL      — fills or nearly fills the FOV; target looms to near-saturation.
    """

    POINT = "POINT"
    RESOLVED = "RESOLVED"
    FILL = "FILL"


class TrackingState(str, Enum):
    """FSM states for the thermal seeker tracker."""

    NO_TARGET = "NO_TARGET"
    CANDIDATE = "CANDIDATE"
    LOCKED = "LOCKED"
    PREDICTIVE_TRACK = "PREDICTIVE_TRACK"
    REACQUIRE = "REACQUIRE"
    HARD_LOST = "HARD_LOST"


_COAST_STATES = frozenset({
    TrackingState.PREDICTIVE_TRACK,
    TrackingState.REACQUIRE,
    TrackingState.HARD_LOST,
})

SCHEMA: str = "fpv_thermal_lock.v1"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ThermalLockConfig:
    """Thresholds and timing parameters for the thermal lock FSM.

    Attributes
    ----------
    stable_frame_count:
        Number of consecutive associations required to transition
        NO_TARGET/CANDIDATE → LOCKED.
    max_gate_px:
        Nearest-neighbour association gate radius (pixels) when LOCKED.
    predictive_track_frames:
        Maximum number of consecutive missed-detection frames before
        transitioning LOCKED → REACQUIRE.  At 60 Hz, 18 frames ≈ 300 ms.
    reacquire_frames:
        Maximum number of frames in REACQUIRE before HARD_LOST.
        At 60 Hz, 90 frames ≈ 1.5 s.
    reacquire_expansion_factor:
        Gate radius multiplier applied during REACQUIRE
        (``expanded_gate = max_gate_px * factor``).
    min_snr_for_association:
        Blobs below this SNR are not considered for association.
    confidence_decay_per_missed_frame:
        Multiplicative decay applied to lock_confidence per missed-detection
        frame (coast frames).
    """

    stable_frame_count: int = 3
    max_gate_px: float = 48.0
    predictive_track_frames: int = 18   # ~300 ms @ 60 Hz
    reacquire_frames: int = 90          # ~1.5 s @ 60 Hz
    reacquire_expansion_factor: float = 3.0
    min_snr_for_association: float = 2.0
    confidence_decay_per_missed_frame: float = 0.92
    # --- occlusion-aware reacquire (default 0.0 = OFF -> bit-identical to today) ---
    # During a coast (missed_frames>0) the anti-decoy veto is disabled so a LOOMED (grown/brighter) real
    # target is recovered on pure kinematics -- but that also lets a DIM clutter blob (a cloud edge) steal
    # the lock while the target is occluded. When > 0, a coast/REACQUIRE candidate must have SNR >= this x
    # the SNR the track had when solidly LOCKED (frozen ref). A loomed target is BRIGHTER (passes); dim
    # cloud clutter is rejected -> the track coasts through the occlusion instead of false-locking.
    reacq_min_snr_fraction: float = 0.0
    # Coast through a brief OCCLUSION: suppress peak-relative-deletion for the first N missed frames, so a
    # temporarily-occluded target COASTS on its prediction (the gate stays prediction-centred -> a far bright
    # confuser like the sun is out-of-gate and rejected) and re-locks when it reappears, instead of being
    # deleted + freshly re-acquiring onto the brightest clutter. 0 = OFF (bit-identical). ~18-24 @60Hz ≈ 300-400ms.
    occlusion_coast_frames: int = 0
    # --- combined-cost association (anti pull-off onto hotter/larger clutter) ---
    # Applied only once a track reference (`_last_blob`) exists; pure nearest-neighbour
    # during fresh acquisition.  A candidate grossly larger/smaller than, or suddenly far
    # hotter than, the tracked target is VETOED even if it is the nearest blob -- this is
    # what stops the lock walking onto a hotter intruder/decoy/glint.  References are the
    # PREVIOUS frame, so smooth looming growth passes while sudden discontinuities are cut.
    assoc_w_kinematic: float = 1.0      # weight on normalized predicted-distance
    assoc_w_appearance: float = 2.0     # weight on frame-to-frame size change (must outvote proximity)
    assoc_w_intensity: float = 0.5      # weight on frame-to-frame SNR change
    assoc_area_veto_ratio: float = 2.5      # reject if area differs > this x from the track's last
    assoc_intensity_veto_ratio: float = 3.0  # reject if peak > this x the track's last peak (intruder)
    # --- R4: hysteretic angular-scale regime state machine (default-OFF -> bit-identical to today) ---
    # When OFF the regime stays POINT; no thresholds are evaluated, so the OFF path is IDENTICAL
    # to a run without R4 at all (no new computation, no mutation of any existing field).
    # area_extended_px thresholds (pixels): POINT->RESOLVED promotes above regime_resolve_up_px;
    # RESOLVED->FILL promotes above regime_fill_up_px.  Down-thresholds use a hysteresis_fraction
    # below the up-threshold (Schmitt trigger: down < up, so the regime is sticky near boundaries).
    # Defaults are calibrated to the V3 scale-sweep baseline where area_extended_px grows from
    # ~few px (sigma=1.5) to ~tens-of-thousands px (sigma=40).  The resolve knee (sigma~5-8) maps
    # to area_extended_px in the hundreds; fill (sigma~20+) maps to area_extended_px in the thousands.
    regime_enabled: bool = False
    regime_resolve_up_px: float = 500.0     # POINT  -> RESOLVED when area_extended_px rises above this
    regime_fill_up_px: float = 5000.0       # RESOLVED -> FILL   when area_extended_px rises above this
    regime_hysteresis_fraction: float = 0.8  # down-threshold = up-threshold * this fraction
    # --- R1: consume IMM hardening (all default-OFF -> bit-identical to today) ---
    # (a) IMM-mixed-state coast: when the pipeline feeds the IMM's predicted centroid + per-frame
    #     pixel velocity (set_imm_state), coast on THAT instead of the crude 2-point pixel CV.
    use_imm_coast: bool = False
    # (b) peak-relative deletion: a continuous lock-score (lock_confidence x lock_quality x
    #     model_ok-penalty) that DROPS A TRACK when it falls below a fraction of its own peak --
    #     resists single-frame dropouts, releases a genuinely-gone target.  Quality affects the
    #     track LIFECYCLE only, NEVER the centroid (Inv 2).
    use_peak_relative_deletion: bool = False
    lock_score_delete_fraction: float = 0.3   # delete when score < this x its peak
    model_wrong_score_penalty: float = 0.5    # lock-score multiplier when model_ok is False
    # --- R7: intensity^motion consensus before LOCKED (default-OFF -> bit-identical) ---
    # A fresh intensity blob may promote CANDIDATE->LOCKED only if it AGREES with an independent
    # MOTION measurement (event-channel / MTI centroid fed via set_motion_centroid) -- rejects a
    # bright STATIC clutter blob (sun glint, hot ground feature). A globally QUIET scene (no motion
    # for consensus_quiet_frames) still allows an intensity-only lock so a HOVERER is not lost.
    # This is a kinematic LIFECYCLE gate; it never moves the centroid (Inv 2) and never forks a
    # committed track (Inv 7 -- it only restrains a NOT-yet-locked candidate).
    require_consensus_for_lock: bool = False
    consensus_radius_px: float = 30.0
    consensus_quiet_frames: int = 10          # frames of no-motion after which intensity-only locks
    # --- R10: JPDA soft-update on a cluttered gate (default-OFF -> bit-identical) ---
    # When the gate holds >= jpda_occupancy_threshold valid returns, replace hard winner-take-all
    # with a likelihood-weighted soft centroid biased toward the prediction -- this is exactly the
    # horizon-crossing geometry where hard GNN pulls off onto a hotter intruder. The appearance
    # reference (_last_blob / vetoes) stays the HARD best; only the reported POSITION is softened.
    # DETERMINISTIC kinematic association (Inv 2), and it restrains a position, never forks a track.
    jpda_enabled: bool = False
    jpda_occupancy_threshold: int = 2
    jpda_softmax_scale: float = 1.0           # temperature on exp(-cost/scale)
    jpda_prediction_weight: float = 0.5       # pseudo-weight pulling the soft centroid to the prediction

    def __post_init__(self) -> None:
        if self.stable_frame_count < 1:
            raise ValueError("stable_frame_count must be >= 1")
        if self.max_gate_px <= 0.0:
            raise ValueError("max_gate_px must be positive")
        if self.predictive_track_frames < 0:
            raise ValueError("predictive_track_frames must be >= 0")
        if self.reacquire_frames < self.predictive_track_frames:
            raise ValueError("reacquire_frames must be >= predictive_track_frames")
        if self.assoc_area_veto_ratio <= 1.0:
            raise ValueError("assoc_area_veto_ratio must be > 1")
        if self.assoc_intensity_veto_ratio <= 1.0:
            raise ValueError("assoc_intensity_veto_ratio must be > 1")


# ---------------------------------------------------------------------------
# Snapshot (output)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ThermalLockSnapshot:
    """Per-frame output of the thermal lock FSM.

    Attributes
    ----------
    tracking_state:
        Current FSM state.
    target_locked:
        True only in LOCKED state.
    centroid_px:
        Best estimate of target centroid (observed if LOCKED, predicted otherwise).
    lock_confidence:
        Scalar confidence in [0, 1].  Decays during coast frames.
    stable_frames:
        Consecutive frames with successful association.
    missed_frames:
        Consecutive frames without association (resets on re-association).
    predicted_centroid_px:
        CV-predictor centroid regardless of state (useful for display).
    associated_blob:
        The ``ThermalBlob`` that was associated this frame, or ``None``.
    frame_id:
        Frame counter.
    recommended_action:
        String hint for guidance layer: ``"TRACK"`` | ``"COAST"`` |
        ``"REACQUIRE"`` | ``"ABANDON"``.
    """

    tracking_state: TrackingState
    target_locked: bool
    centroid_px: tuple[float, float]
    lock_confidence: float
    stable_frames: int
    missed_frames: int
    predicted_centroid_px: tuple[float, float]
    associated_blob: ThermalBlob | None
    frame_id: int
    recommended_action: str
    # R4: angular-scale regime (informational only; NEVER read by guidance/centroid/LOS code).
    # Defaults to POINT so all existing snapshot constructions continue to work unchanged.
    regime: RegimeState = RegimeState.POINT

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema": SCHEMA,
            "tracking_state": self.tracking_state.value,
            "target_locked": self.target_locked,
            "centroid_px": list(self.centroid_px),
            "lock_confidence": round(self.lock_confidence, 4),
            "stable_frames": self.stable_frames,
            "missed_frames": self.missed_frames,
            "predicted_centroid_px": list(self.predicted_centroid_px),
            "frame_id": self.frame_id,
            "recommended_action": self.recommended_action,
            "regime": self.regime.value,
        }
        if self.associated_blob is not None:
            d["associated_blob"] = self.associated_blob.to_dict()
        return d


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

class ThermalLockTracker:
    """Single-target lock FSM for thermal blob tracking.

    Seeded acquisition
    ------------------
    Call ``seed(acquisition_box)`` before the first ``update()`` call.  The
    acquisition box constrains the initial search.  Once locked, the box is
    replaced by the gate around the predicted centroid.

    Usage
    -----
    ::

        tracker = ThermalLockTracker(config)
        tracker.seed(acq_box=(cx - 32, cy - 32, 64, 64))

        threshold_state = ThresholdState()
        for frame_u16, gt in sim.generate(300):
            blobs, threshold_state = detect_frame(frame_u16, ...)
            obs = TargetObservation(frame_id=..., blobs=blobs, ...)
            snapshot = tracker.update(obs)
            print(snapshot.tracking_state, snapshot.centroid_px)
    """

    def __init__(self, config: ThermalLockConfig | None = None) -> None:
        self._cfg = config or ThermalLockConfig()
        self._state = TrackingState.NO_TARGET
        self._stable_frames: int = 0
        self._missed_frames: int = 0
        self._ffc_coast_frames: int = 0  # separate counter for FFC freezes
        self._lock_confidence: float = 0.0

        # Last associated blob (for velocity estimation)
        self._last_blob: ThermalBlob | None = None
        self._lock_ref_snr: float = 0.0     # frozen SNR of the target while solidly LOCKED (occlusion gate)
        self._prev_blob: ThermalBlob | None = None
        self._velocity_px_per_frame: tuple[float, float] = (0.0, 0.0)

        # Seeded acquisition box (x, y, w, h)
        self._acq_box: tuple[float, float, float, float] | None = None

        # A4 covariance-sized search box: an EXPAND-ONLY gate floor (px) set from the IMM's
        # predicted innovation covariance.  0 = unused (the fixed gate governs).  It can only
        # widen the gate when the estimator is uncertain; it never shrinks it.
        self._dynamic_gate_px: float = 0.0

        # R1 IMM-coast: pipeline-fed predicted centroid + per-frame pixel velocity (from the IMM
        # angular state via bearing_to_pixel).  None = not fed -> fall back to 2-point CV.
        self._imm_centroid_px: tuple[float, float] | None = None
        self._imm_vel_px_per_frame: tuple[float, float] = (0.0, 0.0)
        # R1 lock-score (peak-relative deletion): quality fed from the IMM (output-only; never
        # moves the centroid).  Score and its running peak drive lifecycle deletion only.
        self._lock_quality: float = 1.0
        self._model_ok: bool = True
        self._lock_score: float = 0.0
        self._lock_score_peak: float = 0.0
        # R7 consensus: latest independent motion centroid + consecutive no-motion frame count.
        self._motion_centroid: tuple[float, float] | None = None
        self._motion_quiet_frames: int = 0
        # R8: normalized MOSSE structural confidence (1.0 = unused) -> modulates the lock-score only.
        self._correlation_confidence: float = 1.0
        # R10 JPDA: in-gate (blob, cost) candidates collected this frame + the last prediction.
        self._jpda_candidates: list[tuple[ThermalBlob, float]] = []
        self._last_predicted: tuple[float, float] = (0.0, 0.0)

        # R4: hysteretic angular-scale regime state machine.  Only updated when
        # regime_enabled is True and a blob is associated.  Never modifies centroid/LOS.
        self._regime: RegimeState = RegimeState.POINT

    # ── public API ────────────────────────────────────────────────────────────

    def seed(self, acquisition_box: tuple[float, float, float, float]) -> None:
        """Provide the operator's aim box to seed acquisition.

        Parameters
        ----------
        acquisition_box:
            ``(x, y, w, h)`` in image pixels.  The tracker will only associate
            blobs whose centroid falls within this box during the CANDIDATE
            phase.  Once LOCKED, the box is replaced by the gate.
        """
        x, y, w, h = acquisition_box
        self._acq_box = (x, y, w, h)
        # Reset to candidate search
        self._state = TrackingState.NO_TARGET
        self._stable_frames = 0
        self._missed_frames = 0
        self._lock_confidence = 0.0
        self._last_blob = None
        self._prev_blob = None
        self._velocity_px_per_frame = (0.0, 0.0)

    @property
    def gate_px(self) -> float:
        """Current association gate radius (pixels) for the active state."""
        return self._gate_radius()

    @property
    def velocity_px_per_frame(self) -> tuple[float, float]:
        """Rolling per-frame pixel velocity estimate (for R5's leading-edge aimpoint bias)."""
        return self._velocity_px_per_frame

    @property
    def regime(self) -> "RegimeState":
        """Current angular-scale regime (R4); POINT unless regime_enabled."""
        return self._regime

    def set_search_radius(self, radius_px: float) -> None:
        """A4: set the covariance-sized search-box floor (px) for an ESTABLISHED track.

        The IMM publishes a predicted innovation std; the pipeline projects it to pixels and
        calls this each locked frame.  The value only ever WIDENS the gate (``max`` with the
        fixed gate), so a confident filter keeps the nominal gate and an uncertain one (post
        coast) searches wider.  Non-finite / non-positive values disable it.
        """
        self._dynamic_gate_px = float(radius_px) if (
            math.isfinite(radius_px) and radius_px > 0.0) else 0.0

    def set_imm_state(self, centroid_px: tuple[float, float],
                      vel_px_per_frame: tuple[float, float]) -> None:
        """R1: feed the IMM's model-based predicted centroid + per-frame pixel velocity.

        The pipeline computes these from the IMM angular state (bearing_to_pixel) each LOCKED
        frame.  When ``use_imm_coast`` is set the coast predictor uses this smooth, model-based
        estimate instead of the 2-point pixel velocity.  This is a KINEMATIC prediction (where
        the target is), not a quality/appearance signal -- Inv 2 untouched.
        """
        cx, cy = centroid_px
        vx, vy = vel_px_per_frame
        if math.isfinite(cx) and math.isfinite(cy) and math.isfinite(vx) and math.isfinite(vy):
            self._imm_centroid_px = (float(cx), float(cy))
            self._imm_vel_px_per_frame = (float(vx), float(vy))

    def set_motion_centroid(self, centroid_px: tuple[float, float] | None) -> None:
        """R7: feed the independent motion measurement (event-channel / MTI centroid), or None.

        Tracks consecutive no-motion frames so a globally quiet scene can still lock a hoverer.
        Kinematic consensus signal -- restrains a not-yet-locked candidate; never moves the centroid.
        """
        if centroid_px is not None and math.isfinite(centroid_px[0]) and math.isfinite(centroid_px[1]):
            self._motion_centroid = (float(centroid_px[0]), float(centroid_px[1]))
            self._motion_quiet_frames = 0
        else:
            self._motion_centroid = None
            self._motion_quiet_frames += 1

    def _consensus_ok(self, blob: ThermalBlob) -> bool:
        """R7: True if the candidate may promote to LOCKED under the intensity^motion consensus."""
        cfg = self._cfg
        if not cfg.require_consensus_for_lock:
            return True                                   # consensus disabled -> bit-identical
        if self._motion_quiet_frames >= cfg.consensus_quiet_frames:
            return True                                   # globally quiet -> allow a hoverer to lock
        if self._motion_centroid is None:
            return False                                  # motion expected this frame but none seen
        bx, by = blob.centroid_px
        mx, my = self._motion_centroid
        return math.hypot(bx - mx, by - my) <= cfg.consensus_radius_px

    def set_correlation_confidence(self, confidence: float) -> None:
        """R8: feed the normalized MOSSE structural confidence (PSR-derived, in [0, 1]).

        Modulates the continuous lock-score (lifecycle) ONLY -- a structurally-degraded track is
        released sooner.  It NEVER moves the centroid/LOS (Inv 2: the correlation peak is used for
        same-track re-detection, not the live aimpoint)."""
        if math.isfinite(confidence):
            self._correlation_confidence = float(min(max(confidence, 0.0), 1.0))

    def set_quality(self, lock_quality: float, model_ok: bool) -> None:
        """R1: feed the IMM lock-quality / model-wrong flag (OUTPUT-only signals).

        These drive the continuous lock-score and hence track DELETION (lifecycle) only -- they
        NEVER move the centroid, LOS, or association (doctrine Inv 2).
        """
        if math.isfinite(lock_quality):
            self._lock_quality = float(min(max(lock_quality, 0.0), 1.0))
        self._model_ok = bool(model_ok)

    def active_centroid(self) -> tuple[float, float] | None:
        """Predicted centroid of an ESTABLISHED track (LOCKED / coasting), else None.

        Used by upstream gates (e.g. MTI) to never prune the currently-tracked target --
        only fresh-acquisition candidates may be suppressed.
        """
        if self._state in (TrackingState.LOCKED, TrackingState.PREDICTIVE_TRACK,
                           TrackingState.REACQUIRE):
            return self._predict_centroid()
        return None

    def update(self, observation: TargetObservation) -> ThermalLockSnapshot:
        """Process one frame of detection output and update the FSM.

        Parameters
        ----------
        observation:
            Per-frame detector output (``TargetObservation``).

        Returns
        -------
        ThermalLockSnapshot
            Current state and best centroid estimate.
        """
        frame_id = observation.frame_id

        # ── HARD_LOST automatic reset ──────────────────────────────────────
        # HARD_LOST is otherwise a permanent trap: missed_frames keeps growing
        # and the FSM never returns to NO_TARGET.  Per the docstring
        # ("HARD_LOST → NO_TARGET: automatic reset"), whenever we enter update()
        # in HARD_LOST we reset the FSM to NO_TARGET *before* the association
        # attempt, so a re-appearing target is treated fresh and can climb
        # CANDIDATE → LOCKED again.
        if self._state == TrackingState.HARD_LOST:
            self._state = TrackingState.NO_TARGET
            self._missed_frames = 0
            self._lock_confidence = 0.0
            self._stable_frames = 0
            self._last_blob = None
            self._prev_blob = None
            self._lock_ref_snr = 0.0
            self._velocity_px_per_frame = (0.0, 0.0)

        # ── FFC coast override ────────────────────────────────────────────
        # During FFC FREEZE / RECOVERING, pixel data is stale — do not consume
        # the normal missed-frame budget; enter/stay in PREDICTIVE_TRACK coast.
        if observation.is_ffc_freeze:
            return self._ffc_coast(frame_id)

        # Reset FFC coast counter when back to READY
        self._ffc_coast_frames = 0

        # ── try to associate a blob ───────────────────────────────────────
        predicted = self._predict_centroid()
        self._last_predicted = predicted              # R10: prediction-bias anchor for the soft centroid
        gate_px = self._gate_radius()
        best_blob = self._associate(observation.blobs, predicted, gate_px)

        if best_blob is not None:
            return self._on_associated(best_blob, frame_id)
        else:
            return self._on_missed(frame_id, predicted)

    # ── private: state transitions ────────────────────────────────────────────

    def _on_associated(self, blob: ThermalBlob, frame_id: int) -> ThermalLockSnapshot:
        """Blob was successfully associated this frame."""
        self._missed_frames = 0
        self._update_velocity(blob)
        self._prev_blob = self._last_blob
        self._last_blob = blob

        prev_state = self._state

        if prev_state == TrackingState.NO_TARGET:
            self._state = TrackingState.CANDIDATE
            self._stable_frames = 1
            self._lock_confidence = 0.3
        elif prev_state == TrackingState.CANDIDATE:
            self._stable_frames += 1
            # R7: promote to LOCKED only with intensity^motion consensus (no-op when disabled).
            if self._stable_frames >= self._cfg.stable_frame_count and self._consensus_ok(blob):
                self._state = TrackingState.LOCKED
                self._lock_confidence = 1.0
        elif prev_state == TrackingState.LOCKED:
            self._stable_frames += 1
            self._lock_confidence = min(1.0, self._lock_confidence + 0.05)
        elif prev_state in (TrackingState.PREDICTIVE_TRACK, TrackingState.REACQUIRE):
            # Recovery
            self._state = TrackingState.LOCKED
            self._lock_confidence = min(1.0, self._lock_confidence + 0.3)

        # Freeze-able reference of the target's signature strength while SOLIDLY locked (occlusion gate).
        if self._state == TrackingState.LOCKED:
            self._lock_ref_snr = (0.9 * self._lock_ref_snr + 0.1 * blob.snr
                                  if self._lock_ref_snr > 0.0 else blob.snr)

        if self._cfg.use_peak_relative_deletion:
            self._update_lock_score(reset=(prev_state == TrackingState.NO_TARGET))

        # R4: update the hysteretic regime classifier when enabled.  This is ADDITIVE and
        # INFORMATIONAL: it writes self._regime (never read by any existing code path).
        if self._cfg.regime_enabled:
            self._update_regime(float(blob.area_extended_px))

        report_centroid = self._jpda_centroid(blob)   # R10: soft position on a cluttered gate
        locked = self._state == TrackingState.LOCKED
        action = "TRACK" if locked else "HOLD"
        return ThermalLockSnapshot(
            tracking_state=self._state,
            target_locked=locked,
            centroid_px=report_centroid,
            lock_confidence=self._lock_confidence,
            stable_frames=self._stable_frames,
            missed_frames=0,
            predicted_centroid_px=report_centroid,
            associated_blob=blob,
            frame_id=frame_id,
            recommended_action=action,
            regime=self._regime,
        )

    def _on_missed(
        self, frame_id: int, predicted: tuple[float, float]
    ) -> ThermalLockSnapshot:
        """No blob associated this frame."""
        if self._state == TrackingState.NO_TARGET:
            # Nothing to coast; stay put
            return self._empty_snapshot(frame_id, TrackingState.NO_TARGET, "HOLD")

        if self._state == TrackingState.CANDIDATE:
            # Not locked yet; reset
            self._state = TrackingState.NO_TARGET
            self._stable_frames = 0
            self._lock_confidence = 0.0
            return self._empty_snapshot(frame_id, TrackingState.NO_TARGET, "HOLD")

        # LOCKED / PREDICTIVE_TRACK / REACQUIRE — enter/advance coast
        # Guard: if somehow already HARD_LOST (should not happen after the
        # reset in update(), but kept as a defensive belt-and-suspenders), do
        # not let missed_frames grow without bound.
        if self._state == TrackingState.HARD_LOST:
            return ThermalLockSnapshot(
                tracking_state=self._state,
                target_locked=False,
                centroid_px=predicted,
                lock_confidence=0.0,
                stable_frames=self._stable_frames,
                missed_frames=self._missed_frames,
                predicted_centroid_px=predicted,
                associated_blob=None,
                frame_id=frame_id,
                recommended_action="ABANDON",
                regime=self._regime,
            )

        self._missed_frames += 1
        self._lock_confidence *= self._cfg.confidence_decay_per_missed_frame

        cfg = self._cfg
        if self._missed_frames <= cfg.predictive_track_frames:
            self._state = TrackingState.PREDICTIVE_TRACK
            action = "COAST"
        elif self._missed_frames <= cfg.reacquire_frames:
            self._state = TrackingState.REACQUIRE
            action = "REACQUIRE"
        else:
            self._state = TrackingState.HARD_LOST
            self._lock_confidence = 0.0
            action = "ABANDON"

        # R1 peak-relative deletion: release the track the moment the continuous lock-score
        # falls below a fraction of its own peak (quality-modulated lifecycle; never the centroid).
        if cfg.use_peak_relative_deletion:
            self._update_lock_score(reset=False)
            # Occlusion coast: for the first N missed frames, do NOT hard-delete on a score collapse — let the
            # track coast on its prediction (the gate stays prediction-centred, rejecting a far bright confuser).
            allow_delete = self._missed_frames > cfg.occlusion_coast_frames
            if (allow_delete and self._lock_score_peak > 0.0
                    and self._lock_score < cfg.lock_score_delete_fraction * self._lock_score_peak):
                self._state = TrackingState.HARD_LOST
                self._lock_confidence = 0.0
                action = "ABANDON"

        return ThermalLockSnapshot(
            tracking_state=self._state,
            target_locked=False,
            centroid_px=predicted,
            lock_confidence=self._lock_confidence,
            stable_frames=self._stable_frames,
            missed_frames=self._missed_frames,
            predicted_centroid_px=predicted,
            associated_blob=None,
            frame_id=frame_id,
            recommended_action=action,
            regime=self._regime,
        )

    def _ffc_coast(self, frame_id: int) -> ThermalLockSnapshot:
        """Coast through an FFC freeze without consuming the normal budget."""
        self._ffc_coast_frames += 1
        predicted = self._predict_centroid()

        if self._state == TrackingState.LOCKED:
            self._state = TrackingState.PREDICTIVE_TRACK

        # Gentle confidence decay during FFC (slower than normal missed frames)
        self._lock_confidence *= (self._cfg.confidence_decay_per_missed_frame ** 0.5)

        return ThermalLockSnapshot(
            tracking_state=self._state,
            target_locked=False,
            centroid_px=predicted,
            lock_confidence=self._lock_confidence,
            stable_frames=self._stable_frames,
            missed_frames=self._missed_frames,
            predicted_centroid_px=predicted,
            associated_blob=None,
            frame_id=frame_id,
            recommended_action="COAST",
            regime=self._regime,
        )

    # ── private: helpers ───────────────────────────────────────────────────────

    def set_ego_shift_px(self, dx: float, dy: float) -> None:
        """Tell the tracker how far the IMAGE itself will move before the next frame.

        On a STRAPDOWN head the camera turns with the airframe, so the whole scene sweeps: measured up to
        ~100 px between frames at 50 Hz while the target blob is only ~14 px across. The association gate is
        48 px, so the target lands OUTSIDE it and the track drops to PREDICTIVE_TRACK and never recovers --
        even though the ego shift is known and is removed perfectly one stage later, in ``los.py``. That
        compensation is simply downstream of the component that breaks.

        Offsetting the gate centre by the same known shift is gyro-aided association, standard practice in
        real seekers. Measured on launch_and_forget: lock 7% -> 15%, mean CPA 2.38 -> 2.07 m. A real gain --
        and NOT a rescue: strapdown still closes 1 of 5 where a stabilised head closes 5 of 5.
        """
        self._ego_shift_px = (float(dx), float(dy))

    def _predict_centroid(self) -> tuple[float, float]:
        """Centroid prediction for the upcoming frame (the coast gate centre)."""
        # R1: model-based IMM coast -- smoother and noise-shaped vs the 2-point pixel CV. Uses the
        # pipeline-fed IMM estimate (current centroid + per-frame pixel velocity). Same indexing
        # as the CV path (advance by missed_frames+1). Falls back to CV until first fed.
        ex, ey = getattr(self, "_ego_shift_px", (0.0, 0.0))
        if (self._cfg.use_imm_coast and self._imm_centroid_px is not None
                and self._last_blob is not None):
            ix, iy = self._imm_centroid_px
            vx, vy = self._imm_vel_px_per_frame
            step = self._missed_frames + 1
            return (ix + vx * step + ex, iy + vy * step + ey)
        if self._last_blob is None:
            # Use acquisition box centre if available
            if self._acq_box is not None:
                x, y, w, h = self._acq_box
                return (x + w / 2.0, y + h / 2.0)
            return (0.0, 0.0)
        cx, cy = self._last_blob.centroid_px
        vx, vy = self._velocity_px_per_frame
        # Add missed frames worth of prediction, plus the known ego shift of the image itself.
        return (cx + vx * (self._missed_frames + 1) + ex,
                cy + vy * (self._missed_frames + 1) + ey)

    def _update_lock_score(self, *, reset: bool) -> None:
        """R1: maintain the continuous lock-score and its running peak (lifecycle signal only)."""
        score = (self._lock_confidence * self._lock_quality * self._correlation_confidence
                 * (1.0 if self._model_ok else self._cfg.model_wrong_score_penalty))
        self._lock_score = score
        self._lock_score_peak = score if reset else max(self._lock_score_peak, score)

    def _update_velocity(self, blob: ThermalBlob) -> None:
        """Update rolling velocity estimate from most recent association."""
        if self._last_blob is not None:
            cx_new, cy_new = blob.centroid_px
            cx_old, cy_old = self._last_blob.centroid_px
            # Time normalised to 1 frame (frame_id difference)
            dt = max(1, blob.frame_id - self._last_blob.frame_id)
            self._velocity_px_per_frame = (
                (cx_new - cx_old) / dt,
                (cy_new - cy_old) / dt,
            )

    def _gate_radius(self) -> float:
        """Return the current association gate radius in pixels."""
        base = self._cfg.max_gate_px
        # During acquisition, gate to the seeded basket (the operator's drawn aim), not the
        # fixed lock-gate -- otherwise a 60px gate-from-box-centre silently shrinks a large
        # basket to a ~60px disc and a cued off-centre target never locks (C4).
        if self._state in (TrackingState.NO_TARGET, TrackingState.CANDIDATE) and self._acq_box is not None:
            _, _, w, h = self._acq_box
            return max(base, 0.5 * math.hypot(w, h))
        if self._state == TrackingState.REACQUIRE:
            base = base * self._cfg.reacquire_expansion_factor
        # A4: never shrink below the fixed gate; widen to the covariance-sized box when set.
        return max(base, self._dynamic_gate_px)

    def _associate(
        self,
        blobs: list[ThermalBlob],
        predicted: tuple[float, float],
        gate_px: float,
    ) -> ThermalBlob | None:
        """Combined-cost association within gate.

        During fresh acquisition (no track reference) this is pure nearest-neighbour.
        Once a reference (`_last_blob`) exists, candidates are scored by a combined
        kinematic + appearance + intensity cost, and a blob grossly out of family in
        size or intensity is VETOED even if nearest -- the anti pull-off rule.
        During CANDIDATE phase association is also constrained to the acquisition box.
        Returns the best in-gate, non-vetoed blob, or ``None``.
        """
        px, py = predicted
        # During a coast (missed_frames > 0) the real target may have loomed well past the
        # per-frame veto ratios while we were not updating `_last_blob` -- re-associate on
        # PURE KINEMATICS so a grown-but-real target is recovered (the gate still bounds where).
        ref = None if self._missed_frames > 0 else self._last_blob
        best: ThermalBlob | None = None
        best_cost = float("inf")
        self._jpda_candidates = []                    # R10: in-gate, non-vetoed (blob, cost) set

        for blob in blobs:
            bx, by = blob.centroid_px

            # Malformed descriptor (NaN/inf in the fields the veto/cost rely on) -> not a
            # candidate.  Fail safe to coast rather than let NaN defeat every '>' comparison.
            if not (math.isfinite(bx) and math.isfinite(by) and math.isfinite(blob.snr)
                    and math.isfinite(blob.area_px) and math.isfinite(blob.peak_counts)):
                continue

            if blob.snr < self._cfg.min_snr_for_association:
                continue

            # Occlusion-aware reacquire: during a coast, reject clutter dimmer than the locked target's
            # frozen signature (a cloud edge is dim; a loomed real target is brighter and passes).
            if (self._missed_frames > 0 and self._cfg.reacq_min_snr_fraction > 0.0
                    and self._lock_ref_snr > 0.0
                    and blob.snr < self._cfg.reacq_min_snr_fraction * self._lock_ref_snr):
                continue

            # During CANDIDATE: only consider blobs inside the acquisition box
            if self._state in (TrackingState.NO_TARGET, TrackingState.CANDIDATE):
                if not self._inside_acq_box(bx, by):
                    continue

            dist = math.hypot(bx - px, by - py)
            if dist >= gate_px:
                continue

            cost = self._association_cost(blob, ref, dist, gate_px)
            if cost is None:        # vetoed: grossly out of family
                continue
            self._jpda_candidates.append((blob, cost))
            if cost < best_cost:
                best_cost = cost
                best = blob

        return best

    def _jpda_centroid(self, best: ThermalBlob) -> tuple[float, float]:
        """R10: likelihood-weighted soft centroid (prediction-biased) on a cluttered gate.

        Off / sparse gate -> the hard best blob centroid (bit-identical). With >= the occupancy
        threshold of valid returns, blend them by exp(-cost) plus a pseudo-weight at the predicted
        state, so a hotter intruder entering the gate cannot fully capture the position.
        """
        cands = self._jpda_candidates
        if not self._cfg.jpda_enabled or len(cands) < self._cfg.jpda_occupancy_threshold:
            return best.centroid_px
        scale = max(self._cfg.jpda_softmax_scale, 1e-6)
        c_min = min(c for _, c in cands)
        betas = [math.exp(-(c - c_min) / scale) for _, c in cands]
        sx = sum(b * blob.centroid_px[0] for (blob, _), b in zip(cands, betas))
        sy = sum(b * blob.centroid_px[1] for (blob, _), b in zip(cands, betas))
        wsum = sum(betas)
        b_pred = self._cfg.jpda_prediction_weight * max(betas)   # pull toward the prediction
        px, py = self._last_predicted
        sx += b_pred * px
        sy += b_pred * py
        wsum += b_pred
        return (sx / wsum, sy / wsum)

    def _association_cost(
        self,
        blob: ThermalBlob,
        ref: ThermalBlob | None,
        dist: float,
        gate_px: float,
    ) -> float | None:
        """Combined association cost (lower is better); ``None`` means VETOED.

        With no reference (fresh acquisition) cost is pure predicted-distance.  With a
        reference, a candidate whose area differs by more than ``assoc_area_veto_ratio``x,
        or whose peak exceeds ``assoc_intensity_veto_ratio``x the tracked target's last
        peak, is vetoed (an intruder/decoy/glint), and the rest are scored by a weighted
        sum of normalized distance, frame-to-frame size change, and SNR change.
        """
        if ref is None:
            return dist

        ref_area = max(float(ref.area_px), 1.0)
        ref_peak = max(float(ref.peak_counts), 1.0)
        ref_snr = max(float(ref.snr), 1e-3)
        area_ratio = max(float(blob.area_px), 1.0) / ref_area

        if area_ratio > self._cfg.assoc_area_veto_ratio or area_ratio < 1.0 / self._cfg.assoc_area_veto_ratio:
            return None
        if float(blob.peak_counts) > ref_peak * self._cfg.assoc_intensity_veto_ratio:
            return None

        kin = dist / gate_px
        app = abs(math.log(area_ratio)) / math.log(self._cfg.assoc_area_veto_ratio)
        inten = min(abs(float(blob.snr) - ref_snr) / ref_snr, 1.0)
        return (self._cfg.assoc_w_kinematic * kin
                + self._cfg.assoc_w_appearance * app
                + self._cfg.assoc_w_intensity * inten)

    def _inside_acq_box(self, x: float, y: float) -> bool:
        """True if (x, y) is inside the seeded acquisition box."""
        if self._acq_box is None:
            return True  # No box → accept any position
        ax, ay, aw, ah = self._acq_box
        return ax <= x <= ax + aw and ay <= y <= ay + ah

    def _update_regime(self, area_extended_px: float) -> None:
        """R4: Hysteretic (Schmitt-trigger) regime classifier on area_extended_px.

        Promotion (up-transitions) occurs when the cue RISES above the up-threshold.
        Demotion (down-transitions) only occurs when the cue FALLS below the
        down-threshold (= up-threshold * hysteresis_fraction), preventing chatter.

        Called only from _on_associated when regime_enabled is True.
        Never touches centroid, LOS, association, or any command (doctrine Inv 2).
        """
        cfg = self._cfg
        resolve_up = cfg.regime_resolve_up_px
        fill_up = cfg.regime_fill_up_px
        hysteresis = cfg.regime_hysteresis_fraction
        resolve_dn = resolve_up * hysteresis
        fill_dn = fill_up * hysteresis

        current = self._regime
        if current == RegimeState.POINT:
            if area_extended_px >= resolve_up:
                self._regime = RegimeState.RESOLVED
        elif current == RegimeState.RESOLVED:
            if area_extended_px >= fill_up:
                self._regime = RegimeState.FILL
            elif area_extended_px < resolve_dn:
                self._regime = RegimeState.POINT
        else:  # FILL
            if area_extended_px < fill_dn:
                self._regime = RegimeState.RESOLVED

    def _empty_snapshot(
        self,
        frame_id: int,
        state: TrackingState,
        action: str,
    ) -> ThermalLockSnapshot:
        return ThermalLockSnapshot(
            tracking_state=state,
            target_locked=False,
            centroid_px=(0.0, 0.0),
            lock_confidence=0.0,
            stable_frames=0,
            missed_frames=self._missed_frames,
            predicted_centroid_px=(0.0, 0.0),
            associated_blob=None,
            frame_id=frame_id,
            recommended_action=action,
            regime=self._regime,
        )
