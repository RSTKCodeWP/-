"""Seeker -> guidance pipeline (Block-3 piece #1): a thermal frame + gyro -> AICommand.

This is the real onboard perception+guidance chain, wired from the VERIFIED component
modules (S1 detect, S2 ego/los/imm/looming, S3 bearing-rate guidance + pilot). It is what
feeds the OnboardRuntime's ``guidance_command`` input -- replacing the test stub with the
actual pipeline, so the whole Block-3 system runs end to end: pixels in, RC out.

Per frame:
    detect_frame (S1)            -> hot blobs
    ThermalLockTracker.update    -> single-target lock / coast / reacquire
    gyro_derotation + LOSComputer-> ego-compensated bearing + LOS-rate (S2)
    IMMFilter.update             -> filtered lambda-dot
    LoomingEstimator.update      -> tau / closing confidence (weak cue)
    BearingRateGuidance.compute  -> lateral accel command (or ROEAbort)
    LosGuidancePilot             -> bounded AICommand (roll/pitch/yaw/throttle)

EGO MODEL (sim-matched): like the verified Mode B pixel loop, only the ROLL rate is fed to
the LOS ego-compensation, because the seeker_sim renders a velocity-aligned boresight where
pitch/yaw already move the target pixel (passing them would double-compensate). For a real
body-fixed camera the full body-rate ego model is finalized at S0/B1 calibration; that is the
one piece of this chain that is mounting-dependent and not yet hardware-validated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from fpv.seeker.blob import TargetObservation
from fpv.seeker.detect import ThresholdState, detect_frame
from fpv.seeker.egomotion import gyro_derotation
from fpv.seeker.geometry import CameraIntrinsics, ft640_intrinsics, bearing_to_pixel
from fpv.seeker.imm import IMMConfig, IMMEstimate, IMMFilter
from fpv.seeker.looming import LoomingEstimate, LoomingEstimator
from fpv.seeker.los import LOSComputer
from fpv.seeker.mti import MotionGate
from fpv.seeker.track import ThermalLockConfig, ThermalLockTracker
from fpv.seeker.track_manager import MultiTrackManager
from fpv.seeker.aimpoint import migrate_aimpoint
from fpv.seeker.event_channel import EventChannel
from fpv.seeker.correlation import CorrelationChannel, extract_chip, warp_chip
from fpv.seeker.silhouette import silhouette_extent
from fpv.seeker.subtense_range import (
    RangeRateEstimate,
    SubtenseRangeRateFilter,
    bbox_major_extent_px,
)

from fpv.guidance.bearing_rate import BearingRateGuidance, GuidanceConfig, ROEAbort
from fpv.guidance.command_map import LosGuidancePilot, PilotConfig


@dataclass(frozen=True)
class RangeAiding:
    """The honest decision of whether the MEASURED range/closing is trustworthy enough to steer PN.

    ``vc_override_mps`` is the Vc handed to the guidance law: the MEASURED closing when the estimate is
    confident, else ``None`` (guidance falls back to its SCHEDULED Vc — graceful degradation). ``t_go_s`` is
    the measured time-to-go (only when finite/closing). ``source`` is one of ``"measured"``, ``"fallback"``,
    ``"inactive"`` for observability.
    """

    vc_override_mps: float | None
    t_go_s: float | None
    range_m: float | None
    closing_mps: float | None
    source: str


def range_aiding_from_estimate(
    rr: RangeRateEstimate | None,
    *,
    min_closing_mps: float = 3.0,
    max_closing_rel_sigma: float = 0.5,
) -> RangeAiding:
    """Gate a range/closing estimate into a PN Vc override — honestly, or decline and fall back.

    The MEASURED Vc steers PN ONLY when the estimate is initialized, resolved, genuinely closing
    (``Vc >= min_closing_mps``) AND its TOTAL relative uncertainty (random + systematic size) is within
    ``max_closing_rel_sigma``. Otherwise we return ``None`` — the guidance law keeps its scheduled Vc.
    This is the graceful-degradation contract: a weak/opening/uncertain range never poisons the gain, and
    the estimate can never fabricate closing (an un-initialized filter sits at Vc≈0 → declines).
    """
    if rr is None:
        return RangeAiding(None, None, None, None, "inactive")
    range_m = rr.range_m if rr.initialized else None
    if rr.initialized and rr.resolved:
        Vc = rr.closing_mps
        rel_sigma = rr.sigma_closing_total_mps / Vc if Vc > 1e-6 else float("inf")
        if Vc >= min_closing_mps and rel_sigma <= max_closing_rel_sigma:
            t_go = rr.t_go_s if math.isfinite(rr.t_go_s) else None
            return RangeAiding(Vc, t_go, range_m, Vc, "measured")
    closing = rr.closing_mps if rr.initialized else None
    return RangeAiding(None, None, range_m, closing, "fallback")


@dataclass(frozen=True)
class PipelineOutput:
    command: object | None        # AICommand when locked & not aborted, else None
    locked: bool                  # a fresh ego-compensated LOS was produced this frame
    tracking_state: str
    roe_abort: bool
    reason: str
    imm: IMMEstimate | None = None
    # A4: engagement-permission gate output.  The IMM's sustained model-wrong alarm DROPS this
    # to False (default-deny on doubt) without touching the LOS/tracker/command spine (Inv 2):
    # it is the live "model-wrong abort" signal the commit-gate / operator consumes.
    engage_permitted: bool = True
    # --- observability (populated by step(); never read by guidance/control) ---
    blobs: tuple = ()                                  # all detected ThermalBlobs this frame
    centroid_px: tuple[float, float] | None = None     # tracked target centroid (px)
    bbox: tuple[int, int, int, int] | None = None      # tracked target bbox (x,y,w,h)
    area_px: float | None = None
    snr: float | None = None
    threshold_counts: float = 0.0                       # adaptive detection threshold
    # --- subtense range aiding (populated when target_span_m is set) ---
    range_m: float | None = None                        # measured range to target (m); None if inactive
    closing_mps: float | None = None                    # measured closing velocity Vc (m/s)
    t_go_s: float | None = None                         # measured time-to-go R/Vc (s); None if not closing
    vc_used_mps: float | None = None                    # Vc actually handed to PN (measured, or None=scheduled)
    range_aiding_source: str = "inactive"               # "measured" | "fallback" | "inactive"
    extent_px: float | None = None                      # silhouette major span fed to the range filter (px)
    extent_minor_px: float | None = None                # silhouette minor axis (px) -- for aspect / reference
    extent_orientation_rad: float | None = None         # silhouette major-axis orientation (rad)
    signature_peak: float | None = None                 # tracked target peak counts (thermal signature)


def _default_looming(area_px: float) -> LoomingEstimate:
    # Used before the looming estimator has enough history: no closing confidence.
    return LoomingEstimate(tau_s=float("inf"), tau_confidence=0.0, closing_sign=0,
                           area_smoothed_px=area_px, d_area_dt_px_per_s=0.0)


class SeekerGuidancePipeline:
    def __init__(self, *, intrinsics: CameraIntrinsics | None = None,
                 acquisition_box: tuple[float, float, float, float] | None = None,
                 guidance_config: GuidanceConfig | None = None,
                 pilot_config: PilotConfig | None = None,
                 min_snr: float = 2.0, min_area_px: int = 2, max_blobs: int = 20,
                 acquisition_basket_fraction: float = 0.5, region_bands: int = 0,
                 motion_gate: bool = False, graduated_k: bool = False, use_mpcm: bool = False,
                 directional_median: bool = False, trajectory_continuity: bool = False,
                 use_imm_coast: bool = False, use_peak_relative_deletion: bool = False,
                 use_tau_terminal: bool = False, regime_enabled: bool = False,
                 aimpoint_migration: bool = False, aimpoint_forward_bias_px: float = 0.0,
                 event_channel: bool = False, require_consensus_for_lock: bool = False,
                 correlation: bool = False, correlation_psr_ref: float = 12.0,
                 prewarp: bool = False, jpda_enabled: bool = False,
                 reacq_min_snr_fraction: float = 0.0, occlusion_coast_frames: int = 0,
                 roi_gating: bool = False, roi_margin_px: float = 24.0,
                 heavy_stage_decimation: int = 1,
                 discriminator=None,
                 use_terminal_hold: bool = False, terminal_hold_subtense_px: float = 240.0,
                 full_ego_compensation: bool = False,
                 target_span_m: float | None = None, target_span_sigma_m: float = 0.0,
                 range_extent_sigma_px: float = 1.5,
                 range_aiding_min_closing_mps: float = 3.0,
                 range_aiding_max_rel_sigma: float = 0.5) -> None:
        # Detection gates -- live-tunable (the bench mutates these); defaults match detect_frame.
        self.min_snr = float(min_snr)
        self.min_area_px = int(min_area_px)
        self.max_blobs = int(max_blobs)
        self.region_bands = int(region_bands)   # >0 = look-down region-adaptive CFAR
        self.graduated_k = bool(graduated_k)    # region-classified k_horizon<k_sky<k_ground (B1)
        self.use_mpcm = bool(use_mpcm)          # MPCM local-contrast gate (B1)
        self.directional_median = bool(directional_median)  # directional max-median (B1)
        # Look-down MTI: gate detections by ego-compensated motion (drop static clutter).
        self._mti = MotionGate() if motion_gate else None
        # B3 trajectory-continuity backstop: only blobs belonging to a CONFIRMED (persistent +
        # CV-consistent) tracklet may seed a fresh lock, so a single-frame parallax flash that
        # slips past MTI can never acquire.  The manager observes every blob (so it still builds
        # confirmation); the gate only restricts what the single-target tracker is allowed to
        # acquire, and -- like MTI -- it never prunes the already-established lock.
        self._mtm = MultiTrackManager() if trajectory_continuity else None
        # R6 synthetic-event log-contrast channel: an AGC/background-invariant motion locator
        # (default-off). It runs every frame to keep its history and stores the latest event
        # centroid for R7's intensity^motion consensus; it does not (yet) feed the LOS spine.
        # R7 consensus needs an independent motion measurement, so it forces the event channel on.
        self._require_consensus = bool(require_consensus_for_lock)
        self._event = EventChannel() if (event_channel or self._require_consensus) else None
        self._last_event_centroid: tuple[float, float] | None = None
        # R8 MOSSE correlation channel: a structural-track confidence (PSR) that modulates the
        # lock-score (lifecycle) only -- never the live centroid/LOS (Inv 2). Default-off.
        self._corr = CorrelationChannel() if correlation else None
        self._corr_psr_ref = float(correlation_psr_ref)
        self._last_psr: float | None = None
        # R9 anticipatory pre-warp: scale the correlation chip by exp(-dt/tau) (range-free looming)
        # so a closing/grown target matches the template; confidence-gated, default-off.
        self._prewarp = bool(prewarp)
        self._last_looming: LoomingEstimate | None = None
        # WAVE-3: default to the FOXEER FT640 V2 wide lens (HFOV 48.7°, f_px ≈ 707 px,
        # ≈1.41 mrad/px) — the camera actually fielded and the one the DETECT-envelope
        # budget assumes.  The old default was the narrow Boson 640 24 mm (f_px ≈ 2130);
        # the hardware bench (observer.py / onboard_openloop.py) already passes FT640.
        self.intrinsics = intrinsics or ft640_intrinsics()
        self._threshold = ThresholdState()
        self._base_gate_px = 60.0
        # WAVE 2: ROI-gated perception (default-OFF -> roi=None -> bit-identical). When ON and an
        # established track exists, crop detect_frame to a box around the tracker's PREDICTED
        # centroid sized by the (covariance-widened) association gate + a margin, so the heavy
        # look-down stages only touch the on-target neighbourhood and fit the frame budget. In
        # ACQUIRE / reacquire-from-scratch (no established track) it falls back to the full frame.
        self._roi_gating = bool(roi_gating)
        self._roi_margin_px = float(roi_margin_px)
        # WAVE 2: temporal decimation of the heavy directional-median + MTI stages. 1 -> run every
        # frame (bit-identical). >1 -> run them only every Nth frame, reusing the last MTI mask
        # between, so the per-frame heavy budget amortizes over N frames.
        self._heavy_decimation = max(1, int(heavy_stage_decimation))
        self._last_mti_mask = None
        self._heavy_phase = 0
        # R1: consume the IMM hardening (default-off -> bit-identical). When on, the pipeline feeds
        # the IMM model-based coast state + lock-quality to the tracker after each IMM update.
        self._use_imm_coast = bool(use_imm_coast)
        self._use_peak_relative_deletion = bool(use_peak_relative_deletion)
        # R4: hysteretic regime state machine (default-OFF -> bit-identical to today).
        # R5 aimpoint migration needs the regime, so enabling it forces the regime machine on.
        self._aimpoint_migration = bool(aimpoint_migration)
        self._aimpoint_forward_bias_px = float(aimpoint_forward_bias_px)
        self._regime_enabled = bool(regime_enabled) or self._aimpoint_migration
        self._tracker = ThermalLockTracker(ThermalLockConfig(
            stable_frame_count=3, max_gate_px=self._base_gate_px,
            predictive_track_frames=18, reacquire_frames=90,
            use_imm_coast=self._use_imm_coast,
            use_peak_relative_deletion=self._use_peak_relative_deletion,
            regime_enabled=self._regime_enabled,
            require_consensus_for_lock=self._require_consensus,
            jpda_enabled=bool(jpda_enabled),
            reacq_min_snr_fraction=float(reacq_min_snr_fraction),
            occlusion_coast_frames=int(occlusion_coast_frames),
        ))
        # Handover basket: only targets near boresight can lock (A1).  A full-frame box
        # is the documented acquisition bug -- it lets the seeker lock the most-salient
        # clutter anywhere in a cluttered look-down scene.  Default to a centred basket;
        # an explicit acquisition_box (or designate()) overrides it with the operator aim.
        self._basket_fraction = float(acquisition_basket_fraction)
        if not (math.isfinite(self._basket_fraction) and 0.0 < self._basket_fraction <= 1.0):
            raise ValueError("acquisition_basket_fraction must be finite and in (0, 1]")
        box = acquisition_box if acquisition_box is not None else self._centered_basket(self._basket_fraction)
        self._tracker.seed(acquisition_box=box)
        self._los = LOSComputer(self.intrinsics)
        self._imm = IMMFilter(IMMConfig(
            sigma_meas_az=2e-3, sigma_meas_el=2e-3, sigma_meas_az_rate=0.02, sigma_meas_el_rate=0.02,
            q_cv_rate=0.01, q_maneuver_rate=0.8, ego_gate_radps=0.1,
        ))
        self._looming = LoomingEstimator()
        self._guidance = BearingRateGuidance(guidance_config or GuidanceConfig())
        # R3: tau-driven terminal commit (default-off). Only feed estimated_tau_s when on, so the
        # OFF path passes tau=None exactly as before (bit-identical; the legacy terminal switch
        # never fired in the pipeline because neither range nor tau was passed).
        self._use_tau_terminal = bool(use_tau_terminal)
        self._pilot = LosGuidancePilot(
            config=pilot_config or PilotConfig(use_tau_terminal=self._use_tau_terminal))
        self._seq = 0
        self._last_imm: IMMEstimate | None = None
        # AI-firewall discriminator: optional callable(frame_u16, centroid_px)->bool that can only
        # WITHDRAW engage-permission (default-deny). Kept optional so torch stays out of the
        # classical seeker path; an optional TRUSTED engage-permission veto plugs in here (the learned
        # drone-vs-not classifier was removed 2026-07-11; default None -> the machine never classifies).
        self._discriminator = discriminator
        # Ten-tau wall (W4): freeze the guidance course once the target subtense (largest bbox dim)
        # crosses this many px -- a range-free "very close" proxy. Default-off -> bit-identical.
        self._full_ego = bool(full_ego_compensation)
        self._use_terminal_hold = bool(use_terminal_hold)
        self._terminal_hold_subtense_px = float(terminal_hold_subtense_px)
        # SUBTENSE RANGE AIDING (default-OFF -> target_span_m None -> no filter -> scheduled Vc, bit-identical).
        # When the target's physical span is known (classifier + operator enrollment, LOBL), the resolved
        # silhouette's pixel extent gives absolute range + MEASURED closing velocity, so PN runs on a
        # measured Vc / real t_go instead of the scheduled scalar. Confidence-gated: a weak/opening/uncertain
        # estimate declines and the law keeps its scheduled Vc (graceful degradation).
        self._range_filter: SubtenseRangeRateFilter | None = (
            SubtenseRangeRateFilter(float(target_span_m), self.intrinsics,
                                    size_sigma_m=float(target_span_sigma_m))
            if target_span_m is not None else None)
        self._range_extent_sigma_px = float(range_extent_sigma_px)
        self._range_aiding_min_closing_mps = float(range_aiding_min_closing_mps)
        self._range_aiding_max_rel_sigma = float(range_aiding_max_rel_sigma)

    def _centered_basket(self, fraction: float) -> tuple[float, float, float, float]:
        """A fraction-of-frame acquisition box centred on the boresight."""
        w = float(self.intrinsics.width)
        h = float(self.intrinsics.height)
        bw, bh = w * fraction, h * fraction
        return ((w - bw) / 2.0, (h - bh) / 2.0, bw, bh)

    def _detect_roi(self) -> tuple[int, int, int, int] | None:
        """WAVE 2: derive the detect_frame ROI from the tracker's predicted state, or None.

        Returns ``None`` (=> full frame) unless ROI-gating is on AND the tracker holds an
        ESTABLISHED track (LOCKED / PREDICTIVE_TRACK / REACQUIRE).  In ACQUIRE / reacquire-from-
        scratch there is no reliable predicted position, so we must search the whole frame.

        The box is centred on the tracker's PREDICTED centroid (``active_centroid()`` -- the same
        coast prediction the association gate is centred on) with half-width = the current gate
        radius (``gate_px`` already absorbs the REACQUIRE expansion and the A4 covariance-sized
        ``set_search_radius`` floor) plus a fixed margin.  Clamped to the frame; detect_frame
        clamps again, so an off-frame box is harmless.
        """
        if not self._roi_gating:
            return None
        center = self._tracker.active_centroid()
        if center is None:
            return None                                   # no established track -> full frame
        cx, cy = center
        if not (math.isfinite(cx) and math.isfinite(cy)):
            return None
        half = float(self._tracker.gate_px) + self._roi_margin_px
        w = float(self.intrinsics.width)
        h = float(self.intrinsics.height)
        x0 = int(math.floor(max(0.0, cx - half)))
        y0 = int(math.floor(max(0.0, cy - half)))
        x1 = int(math.ceil(min(w, cx + half)))
        y1 = int(math.ceil(min(h, cy + half)))
        if x1 <= x0 or y1 <= y0:
            return None
        return (x0, y0, x1 - x0, y1 - y0)

    def designate(self, center_px: tuple[float, float], basket_px: float | None = None) -> None:
        """Operator designation: re-seed acquisition on a basket centred at ``center_px``.

        Resets the tracker to re-acquire the designated target only (the operator-cued
        LOBL aim).  ``basket_px`` defaults to 40% of the smaller image dimension.
        """
        w = float(self.intrinsics.width)
        h = float(self.intrinsics.height)
        bp = float(basket_px) if basket_px is not None else min(w, h) * 0.4
        if not (math.isfinite(bp) and bp > 0.0):
            raise ValueError("basket_px must be finite and > 0")
        bp = min(bp, min(w, h))                       # never larger than the frame (C9)
        cx, cy = float(center_px[0]), float(center_px[1])
        if not (math.isfinite(cx) and math.isfinite(cy)):
            raise ValueError("designation center must be finite")
        # clamp so the basket stays fully on-screen (a real aim box, not a full-frame default)
        x0 = min(max(cx - bp / 2.0, 0.0), w - bp)
        y0 = min(max(cy - bp / 2.0, 0.0), h - bp)
        self._tracker.seed(acquisition_box=(x0, y0, bp, bp))

    def step(self, now: float, frame_u16, gyro_omega_xyz: tuple[float, float, float], dt: float,
             *, cam_temp_c: float = 25.0, ffc_state: str = "READY",
             committed: bool = False) -> PipelineOutput:
        if self._full_ego:
            # GYRO-AIDED ASSOCIATION -- set BEFORE detection/tracking runs this frame.
            # The LOS de-rotation later in this method cleans the bearing, but it runs AFTER the tracker,
            # and on a strapdown head the tracker breaks first: the image sweeps up to ~100 px per frame
            # against a 48 px association gate, so the target lands outside the gate and the track coasts
            # away for good. Give the tracker the same known shift so its gate travels with the scene.
            _f = self.intrinsics.f_px
            self._tracker.set_ego_shift_px(-_f * float(gyro_omega_xyz[1]) * dt,
                                           -_f * float(gyro_omega_xyz[0]) * dt)
        frame_id = self._seq
        t_ns = int(now * 1e9)
        dt_eff = max(dt, 1e-4)

        # WAVE 2: ROI gate -- crop detection to the predicted-target neighbourhood once an
        # established track exists (None -> full frame, bit-identical). All blob outputs come back
        # in ABSOLUTE px, so every downstream LOS/IMM/tracker computation is unchanged.
        roi = self._detect_roi()
        # WAVE 2: temporal decimation -- run the heavy directional-median stage only on heavy
        # frames; the OFF (decimation==1) path is every frame, exactly as before.
        heavy_this_frame = (self._heavy_phase % self._heavy_decimation) == 0
        self._heavy_phase += 1                          # advance once per frame (any exit path)
        directional_median = self.directional_median and heavy_this_frame

        # S1 detection
        blobs, self._threshold = detect_frame(
            frame_u16, cam_temp_c=cam_temp_c, ffc_state=ffc_state,
            threshold_state=self._threshold, frame_id=frame_id, t_capture_ns=t_ns,
            min_area_px=self.min_area_px, min_snr=self.min_snr, max_blobs=self.max_blobs,
            region_bands=self.region_bands, graduated_k=self.graduated_k,
            use_mpcm=self.use_mpcm, directional_median=directional_median,
            roi=roi,
        )
        # R6: synthetic-event channel -- run every frame to maintain history; store the AGC-
        # invariant motion centroid for R7's consensus. FFC frames reset it (stale shutter pixels).
        if self._event is not None:
            if ffc_state != "READY":
                self._event.reset()
                self._last_event_centroid = None
            else:
                ev_ego = gyro_derotation(omega_xyz_radps=(0.0, 0.0, float(gyro_omega_xyz[2])),
                                         dt=dt_eff, intrinsics=self.intrinsics)
                self._last_event_centroid = self._event.update(frame_u16, ev_ego.shift_px)
        # Look-down MTI gate -- motion as a SOFT preference that NEVER prunes the established
        # track.  FFC frames are not ingested (stale -> reset history).  A blob is a "mover"
        # if any pixel of its BBOX is in the ego-compensated motion mask (not a single
        # centroid pixel, which a flat-topped target leaves still).  When movers exist we drop
        # static NEW candidates but ALWAYS retain the currently-tracked blob; when nothing
        # moves we keep all blobs so a HOVERING target is not erased.
        if self._mti is not None:
            if ffc_state != "READY":
                self._mti.reset()
                self._last_mti_mask = None
                mask = None
            elif heavy_this_frame:
                # Heavy frame: recompute the ego-compensated motion mask and cache it.
                mask = self._mti.update(frame_u16)
                self._last_mti_mask = mask
            else:
                # WAVE 2 decimation: reuse the last computed mask between heavy frames. The
                # cached mask is in absolute frame px (full-frame MTI), so it still indexes
                # the blob bboxes correctly.
                mask = self._last_mti_mask
            if mask is not None and blobs:
                mh, mw = mask.shape

                def _is_mover(b: object) -> bool:
                    bx, by, bw, bh = b.bbox  # type: ignore[attr-defined]
                    x0, x1 = min(max(bx, 0), mw), min(max(bx + bw, 0), mw)
                    y0, y1 = min(max(by, 0), mh), min(max(by + bh, 0), mh)
                    return x1 > x0 and y1 > y0 and bool(mask[y0:y1, x0:x1].any())

                movers = [b for b in blobs if _is_mover(b)]
                if movers:
                    tracked = self._tracker.active_centroid()
                    if tracked is None:
                        blobs = movers                       # fresh acquisition: prefer movers
                    else:
                        tcx, tcy = tracked
                        gate = self._tracker.gate_px
                        blobs = [b for b in blobs if _is_mover(b) or (
                            math.isfinite(b.centroid_px[0]) and math.isfinite(b.centroid_px[1])
                            and math.hypot(b.centroid_px[0] - tcx, b.centroid_px[1] - tcy) <= gate)]

        # B3 trajectory-continuity backstop -- the parallax/false-alarm gate.  The manager
        # observes EVERY post-MTI blob (so a real mover still accrues confirmation), but only
        # blobs near a CONFIRMED tracklet -- or the already-tracked target -- are allowed to
        # reach the single-target tracker.  A one-frame flash never reaches N-of-M, so it can
        # never seed a lock; acquisition of a genuine target is delayed only by the few frames
        # it takes to confirm.  FFC frames reset the manager (stale pixels).
        if self._mtm is not None:
            if ffc_state != "READY":
                self._mtm.reset()
            else:
                snaps = self._mtm.update(blobs, frame_id)
                confirmed = [s.centroid_px for s in snaps if s.confirmed]
                tracked = self._tracker.active_centroid()
                mgate = self._mtm.gate_px

                def _continuous(b: object) -> bool:
                    bx, by = b.centroid_px  # type: ignore[attr-defined]
                    if not (math.isfinite(bx) and math.isfinite(by)):
                        return False
                    if any(math.hypot(bx - cx, by - cy) <= mgate for cx, cy in confirmed):
                        return True
                    return tracked is not None and math.hypot(
                        bx - tracked[0], by - tracked[1]) <= self._tracker.gate_px

                blobs = [b for b in blobs if _continuous(b)]
        obs = TargetObservation(
            frame_id=frame_id, t_capture_ns=t_ns, cam_temp_c=cam_temp_c, ffc_state=ffc_state,
            blobs=blobs, threshold_baseline_counts=self._threshold.threshold_counts,
            detection_budget_ms=0.0,
        )
        # R7: feed the independent motion measurement so the tracker can require intensity^motion
        # consensus before LOCKED (no-op unless require_consensus_for_lock is set on the tracker).
        if self._require_consensus:
            self._tracker.set_motion_centroid(self._last_event_centroid)
        snap = self._tracker.update(obs)

        # R8: MOSSE structural confidence on the locked target. Seed the immutable LOBL reference on
        # first lock; thereafter feed the PSR-normalized confidence to the tracker lock-score for the
        # NEXT frame (like the IMM quality feed). The peak offset is for same-track re-detection only;
        # PSR is a lock-quality signal -- neither moves the live centroid/LOS (Inv 2).
        if self._corr is not None and ffc_state == "READY" and snap.associated_blob is not None:
            chip = extract_chip(frame_u16, snap.centroid_px[0], snap.centroid_px[1])
            if not self._corr.seeded:
                self._corr.seed(chip)
            else:
                # R9: pre-warp the chip to the predicted scale (exp(-dt/tau)) when looming is
                # confident, so a closing target matches the template; else use the chip as-is.
                if (self._prewarp and self._last_looming is not None
                        and self._last_looming.tau_confidence >= 0.5
                        and math.isfinite(self._last_looming.tau_s) and self._last_looming.tau_s > 0.0):
                    chip = warp_chip(chip, content_scale=math.exp(-dt_eff / self._last_looming.tau_s))
                _dx, _dy, psr = self._corr.measure(chip)
                self._last_psr = psr
                self._tracker.set_correlation_confidence(
                    min(psr / max(self._corr_psr_ref, 1e-6), 1.0))

        dbg = dict(blobs=tuple(blobs), threshold_counts=float(self._threshold.threshold_counts))

        # No detection this frame -> guidance coasts upstream; no fresh LOS.
        if snap.associated_blob is None:
            self._seq += 1
            return PipelineOutput(None, False, snap.tracking_state.name, False, "no_lock",
                                  self._last_imm, centroid_px=snap.centroid_px, **dbg)

        # S2 ego-compensated LOS (roll-only ego; see module docstring) + IMM filter
        # Ego-compensation. ROLL-ONLY by default (historical): only omega_z, the in-plane image rotation,
        # was removed -- the TRANSLATIONAL shift (-f*omega_y*dt, -f*omega_x*dt) from boresight pitch/yaw was
        # discarded. On a STRAPDOWN head that is the dominant disturbance: 1 deg of body tilt shifts the
        # image ~12 px while the target itself is ~14 px at 100 m, so an uncompensated tilt reads as target
        # motion and corrupts the very lambda-dot guidance steers on. full_ego_compensation=True uses all
        # three gyro axes; it needs the caller to actually supply a real body rate.
        _omega = (tuple(float(w) for w in gyro_omega_xyz) if self._full_ego
                  else (0.0, 0.0, float(gyro_omega_xyz[2])))
        ego = gyro_derotation(omega_xyz_radps=_omega, dt=dt_eff, intrinsics=self.intrinsics)
        # R5: migrate the LOS-feeding aimpoint hotspot->silhouette in RESOLVED/FILL (DETERMINISTIC
        # geometry, never a quality signal -> Inv 2). OFF or POINT -> the unchanged hotspot centroid.
        los_centroid = snap.centroid_px
        if self._aimpoint_migration and snap.associated_blob is not None:
            los_centroid = migrate_aimpoint(
                frame_u16, snap.centroid_px, float(snap.associated_blob.peak_counts),
                self._tracker.velocity_px_per_frame, snap.regime,
                forward_bias_px=self._aimpoint_forward_bias_px)
        los_obs = self._los.update(centroid_px=los_centroid, ego=ego, dt=dt_eff,
                                   frame_id=frame_id, t_capture_ns=t_ns)
        imm_est = self._imm.update(
            los_obs, dt=dt_eff,
            pixel_extent_px=float(snap.associated_blob.area_extended_px or snap.associated_blob.area_px),
        )
        self._last_imm = imm_est

        # A4 covariance-sized search box: project the IMM's predicted bearing-innovation std to
        # pixels and hand it to the tracker as an EXPAND-ONLY gate floor for the next frame
        # (capped at 3x the fixed gate so a covariance blow-up can't open an unbounded window).
        f_px = float(self.intrinsics.f_px)
        gate_sigma = max(float(imm_est.gate_sigma_az_rad), float(imm_est.gate_sigma_el_rad))
        self._tracker.set_search_radius(min(3.0 * gate_sigma * f_px, 3.0 * self._base_gate_px))

        # A4 NIS consumer: a SUSTAINED true-NIS "model-wrong" alarm withdraws engage-permission
        # (default-deny) -- the real consumer of the alarm, feeding the commit-gate, NOT the
        # centroid/LOS/tracker spine.  A single jink does not trip it (true NIS uses S).
        engage_permitted = not imm_est.model_wrong_alarm
        # AI-firewall: a learned discriminator (drone-vs-not CNN) can only WITHDRAW engage-permission
        # (default-deny), never grant it against the kinematic gate, and never touch the
        # centroid/LOS/tracker (Inv 2). Runs only on a held lock; optional -> no torch in the OFF path.
        if self._discriminator is not None and engage_permitted and snap.centroid_px is not None:
            engage_permitted = bool(self._discriminator(frame_u16, snap.centroid_px))

        # R1: feed the IMM hardening into the tracker for the NEXT frame (used only when the
        # respective flag is on). set_imm_state is a KINEMATIC coast prediction (where the target
        # is); set_quality is an OUTPUT-only lifecycle signal -- neither moves the centroid (Inv 2).
        if self._use_imm_coast:
            ic = bearing_to_pixel(imm_est.az_rad, imm_est.el_rad, self.intrinsics)
            ic_next = bearing_to_pixel(imm_est.az_rad + imm_est.az_rate_radps * dt_eff,
                                       imm_est.el_rad + imm_est.el_rate_radps * dt_eff, self.intrinsics)
            self._tracker.set_imm_state(ic, (ic_next[0] - ic[0], ic_next[1] - ic[1]))
        if self._use_peak_relative_deletion:
            self._tracker.set_quality(imm_est.lock_quality, imm_est.model_ok)

        # Looming is driven by area_px (Phase-B review C3): area_extended_px is on a different
        # (180x180-window) scale than the LoomingConfig saturation thresholds, and its
        # look-down border-background artefact can both fabricate and suppress closing cues.
        # area_extended_px is kept as a separate diagnostic subtense cue, NOT a looming input,
        # until a window-scale-matched looming config + the local-background fix are validated.
        blob = snap.associated_blob
        looming_est = self._looming.update(float(blob.area_px), dt_eff)
        if looming_est is None:
            looming_est = _default_looming(float(blob.area_px))
        self._last_looming = looming_est               # R9: feed the next frame's pre-warp

        # S3 guidance law + pilot mapping
        self._seq += 1
        blob = snap.associated_blob
        track_dbg = dict(centroid_px=snap.centroid_px, bbox=blob.bbox,
                         area_px=float(blob.area_px), snr=float(blob.snr), **dbg)

        # SUBTENSE RANGE AIDING: measure R + closing from the resolved silhouette extent, then decide
        # (honestly) whether the closing is trustworthy enough to steer PN or we fall back to schedule.
        # EXTENT = the robust second-moment silhouette MAJOR axis (immune to top-hat interior suppression,
        # which collapses the detector bbox as the target fills the FOV -- exactly the terminal). Falls
        # back to the bbox major only when the silhouette footprint is unresolved (acquisition / saturated).
        aiding = RangeAiding(None, None, None, None, "inactive")
        extent_used: float | None = None
        extent_minor_px: float | None = None
        extent_orientation_rad: float | None = None
        if self._range_filter is not None and blob.bbox is not None:
            sil = silhouette_extent(frame_u16, snap.centroid_px[0], snap.centroid_px[1],
                                    float(blob.peak_counts))
            extent_used = sil.major_px if sil.resolved else bbox_major_extent_px(blob.bbox)
            if sil.resolved:
                extent_minor_px = sil.minor_px
                extent_orientation_rad = sil.orientation_rad
            rr = self._range_filter.update(extent_used, dt_eff,
                                           extent_sigma_px=self._range_extent_sigma_px)
            aiding = range_aiding_from_estimate(
                rr, min_closing_mps=self._range_aiding_min_closing_mps,
                max_closing_rel_sigma=self._range_aiding_max_rel_sigma)
        range_dbg = dict(range_m=aiding.range_m, closing_mps=aiding.closing_mps,
                         t_go_s=aiding.t_go_s, vc_used_mps=aiding.vc_override_mps,
                         range_aiding_source=aiding.source, extent_px=extent_used,
                         extent_minor_px=extent_minor_px, extent_orientation_rad=extent_orientation_rad,
                         signature_peak=float(blob.peak_counts))

        # Ten-tau wall trigger (range-free): the target's largest bbox dimension crossing the
        # threshold means it fills the FOV -> very close -> freeze the course (see bearing_rate).
        terminal_hold = (self._use_terminal_hold and blob.bbox is not None
                         and max(blob.bbox[2], blob.bbox[3]) >= self._terminal_hold_subtense_px)
        try:
            g_cmd = self._guidance.compute(imm_est, looming_est, committed=committed,
                                           terminal_hold=terminal_hold,
                                           Vc_override_mps=aiding.vc_override_mps)
        except ROEAbort as abort:
            return PipelineOutput(None, True, snap.tracking_state.name, True, abort.reason,
                                  imm_est, engage_permitted=engage_permitted, **track_dbg, **range_dbg)

        # Prefer the MEASURED t_go for the pilot's terminal switch; else the looming-tau path (as before).
        est_tau = aiding.t_go_s
        if est_tau is None:
            est_tau = (g_cmd.t_go_s if (self._use_tau_terminal and g_cmd.t_go_source == "looming"
                                        and math.isfinite(g_cmd.t_go_s)) else None)
        ai_cmd = self._pilot.command_from_guidance(
            g_cmd, az_rad=imm_est.az_rad, el_rad=imm_est.el_rad,
            sequence_id=frame_id, timestamp_ms=int(now * 1e3),
            estimated_tau_s=est_tau,
        )
        return PipelineOutput(ai_cmd, True, snap.tracking_state.name, False, "locked",
                              imm_est, engage_permitted=engage_permitted, **track_dbg, **range_dbg)
