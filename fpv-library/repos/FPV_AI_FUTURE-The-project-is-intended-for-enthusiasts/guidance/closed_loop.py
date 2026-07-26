"""Closed-loop intercept simulation harness for Block-03 S3.

OVERVIEW
--------
Two simulation modes:

Mode A (analytic, fast):
    Bearing is computed analytically from the true 3-D relative geometry plus
    ego-rotation noise and measurement noise.  Fast enough for Monte-Carlo sweeps.
    The full LOS pipeline (detect → los → imm) is bypassed; IMM is run on the
    analytic bearing.

Mode B (pixel-in-the-loop, integration validation):
    A synthetic thermal frame is rendered using fpv.seeker.thermal_sim + seeker_sim.
    The full S1+S2 pipeline (detect → los_computer → imm) is run on each frame.
    Slow (~0.5 s/frame); use for integration validation only, not Monte-Carlo.

DECOUPLED COMMAND-RATE MODEL
-----------------------------
Guidance ticks at guidance_rate_hz (default 250 Hz), independent of vision.
Vision runs at vision_rate_hz (default 60 Hz).
On frames where no new vision data is available (frame drops or low-rate vision),
guidance holds the last-valid LOS (with configurable decay) and continues
generating commands at the guidance rate.  The command stream is metronomic.

SMITH-PREDICTOR-STYLE LEAD
----------------------------
The bearing measurement is delayed by d_total = sensor_delay + loop_delay.
The Smith predictor compensates by advancing the bearing estimate forward by
d_total using the current LOS-rate estimate:

    az_lead = az_delayed + az_rate * d_total
    el_lead = el_delayed + el_rate * d_total

This effectively pre-corrects for the delay.  The improvement (miss WITH lead
vs WITHOUT lead) is quantified in Gate L.

MISS DISTANCE
-------------
Miss distance = minimum 3-D separation (closest approach) during the engagement.
Computed by finding the minimum over the continuous relative trajectory using
linear interpolation between consecutive sim steps.  For each pair of consecutive
positions, the closest approach on the line segment is found analytically:

    p(t) = p0 + t*(p1-p0),  q(t) = q0 + t*(q1-q0),  t in [0,1]
    d(t)^2 = |p(t)-q(t)|^2, minimized at t* = -dot(d0, dd) / dot(dd, dd)
    where d0 = p0-q0, dd = (p1-p0)-(q1-q0)

This avoids the discrete-step artifact where miss = capture_radius - one_step_width.
HIT if miss_distance < capture_radius_m.

UNITS / SIGNS
-------------
All in SI: meters, m/s, m/s^2, radians, rad/s, seconds.
Signs match bearing_rate.py and quad_sim.py conventions.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np
import numpy.typing as npt

from fpv.seeker.imm import IMMFilter, IMMConfig, IMMEstimate
from fpv.seeker.looming import LoomingEstimator, LoomingEstimate
from fpv.seeker.los import LOSComputer, LOSObservation
from fpv.seeker.geometry import CameraIntrinsics, ft640_intrinsics
from fpv.seeker.egomotion import EgoEstimate
from fpv.guidance.pixel_loop import PixelLoopState, make_pixel_loop_state, run_pixel_vision_tick
from fpv.seeker.subtense_range import SubtenseRangeRateFilter
from fpv.guidance.pipeline import range_aiding_from_estimate


def _passthrough_imm_estimate(
    az_rad: float,
    el_rad: float,
    az_rate_radps: float,
    el_rate_radps: float,
    frame_id: int,
    t_s: float,
) -> IMMEstimate:
    """Build a pass-through IMMEstimate without running the outer IMMFilter.

    Used in Mode B (pixel-in-the-loop) to bypass the outer IMM re-filter.
    The IMM has already been applied inside run_pixel_vision_tick (pixel_loop.py).
    Running the outer IMM a second time would double-smooth the detection noise
    and produce artificially tight CPA numbers — the double-IMM bug.

    In Mode B, the bearing/rate values here are already IMMFilter output from
    the inner pixel-loop IMMFilter.  We wrap them in an IMMEstimate directly
    so the guidance law (BearingRateGuidance) sees them without further smoothing.
    """
    return IMMEstimate(
        az_rad=az_rad,
        el_rad=el_rad,
        az_rate_radps=az_rate_radps,
        el_rate_radps=el_rate_radps,
        mode_probs=(0.5, 0.5),
        maneuver_detected=False,
        frame_id=frame_id,
        innovation_az=0.0,
        innovation_el=0.0,
        ego_gate_active=False,
    )

from fpv.guidance.bearing_rate import (
    BearingRateGuidance,
    GuidanceConfig,
    GuidanceCommand,
    GeometryClass,
    ROEAbort,
    schedule_Vc_mps,
)
from fpv.guidance.command_map import LosGuidancePilot, PilotConfig
from fpv.guidance.quad_sim import (
    QuadSim,
    QuadState,
    TargetSim,
    TargetState,
    SimConfig,
    EngagementGeometry,
    compute_bearing_from_states,
    compute_los_rates,
)


_G: float = 9.81

# WAVE-3 camera-model reconciliation.
# The closed-loop sim now uses the FOXEER FT640 V2 wide thermal lens — the camera
# actually fielded on the Block-3 interceptor and the one the Johnson DETECT-envelope
# budget is computed against.  Previously the looming/area approximation hard-coded the
# NARROW Boson 640 24 mm telephoto (f_px = 2130, 0.47 mrad/px), which did not match the
# wide pixel-loop optics nor the budget.  FT640: HFOV 48.7°, f_px ≈ 707 px, ≈1.41 mrad/px.
# This f_px scales the blob-radius/area used ONLY by the looming (τ) channel; it is ~3.0×
# smaller than the old 2130, so a target subtends ~3.0× fewer pixels at a given range.
_FT640_F_PX: float = float(ft640_intrinsics().f_px)   # ≈ 707.08 px (640 px / 2 / tan(48.7°/2))


# ---------------------------------------------------------------------------
# Closest-approach utility
# ---------------------------------------------------------------------------

def _segment_closest_approach(
    p0: npt.NDArray[np.float64],
    p1: npt.NDArray[np.float64],
    q0: npt.NDArray[np.float64],
    q1: npt.NDArray[np.float64],
) -> float:
    """Minimum 3-D separation between two moving objects over one time step.

    Models both objects as moving linearly from their previous to current
    positions.  Finds the parametric time t* in [0,1] that minimises
    |p(t) - q(t)|^2, then returns the minimum distance.

    This eliminates the discrete-step artifact (miss ~ capture_radius - step)
    and gives a true continuous miss that varies with geometry and seed.

    Parameters
    ----------
    p0, p1:
        Interceptor position at start and end of time step (m).
    q0, q1:
        Target position at start and end of time step (m).

    Returns
    -------
    float
        Minimum 3-D separation (m) achieved at any point on the segment.
    """
    d0 = p0 - q0                  # relative position at t=0
    dd = (p1 - p0) - (q1 - q0)   # relative velocity * dt

    # d(t) = d0 + t*dd, |d(t)|^2 = |d0|^2 + 2*t*dot(d0,dd) + t^2*|dd|^2
    # Minimise: d/dt = 2*dot(d0,dd) + 2*t*|dd|^2 = 0 -> t* = -dot(d0,dd)/|dd|^2
    dd_sq = float(np.dot(dd, dd))
    if dd_sq < 1e-18:
        # Relative velocity is zero; return fixed distance
        return float(np.linalg.norm(d0))

    t_star = -float(np.dot(d0, dd)) / dd_sq
    t_clamped = max(0.0, min(1.0, t_star))

    d_min = d0 + t_clamped * dd
    return float(np.linalg.norm(d_min))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClosedLoopConfig:
    """Closed-loop harness configuration.

    Attributes
    ----------
    sim:
        Quad/target dynamics configuration.
    guidance:
        Guidance law configuration.
    pilot:
        Command-map pilot configuration.
    imm:
        IMM filter configuration.
    mode:
        'analytic' (Mode A) or 'pixel_in_the_loop' (Mode B).
    los_hold_decay:
        Decay factor applied to the held LOS-rate per guidance tick when no new
        vision frame is available.  1.0 = no decay (hold forever).  0.95 = 5%
        decay per tick.  Default 0.97.
    smith_predictor:
        Override for Smith-predictor lead.  If None, uses sim.smith_predictor.
    print_progress_every_n_steps:
        Print a progress line every N sim steps.  0 = no printing.
    """
    sim: SimConfig = field(default_factory=SimConfig)
    guidance: GuidanceConfig = field(default_factory=GuidanceConfig)
    pilot: PilotConfig = field(default_factory=PilotConfig)
    imm: IMMConfig = field(default_factory=IMMConfig)
    mode: str = "analytic"
    los_hold_decay: float = 0.97
    smith_predictor: Optional[bool] = None
    print_progress_every_n_steps: int = 0


# ---------------------------------------------------------------------------
# Engagement result
# ---------------------------------------------------------------------------

@dataclass
class EngagementResult:
    """Result of one closed-loop engagement simulation.

    Attributes
    ----------
    hit:
        True if miss_distance_m < capture_radius_m.
    miss_distance_m:
        Minimum 3-D separation between interceptor and target (m).
    time_to_closest_approach_s:
        Simulation time of closest approach (s).
    roe_abort:
        True if a ROE_ABORT was raised (envelope exceeded or high-crossing).
    roe_abort_reason:
        ROE_ABORT reason string, or None if no abort.
    engagement_time_s:
        Total engagement time until hit/abort/timeout (s).
    config:
        The ClosedLoopConfig used.
    interceptor_trajectory:
        List of (t, x, y, z) interceptor positions.  May be empty if verbose=False.
    target_trajectory:
        List of (t, x, y, z) target positions.  May be empty if verbose=False.
    guidance_cmds:
        List of GuidanceCommand outputs (sampled at guidance rate).
    final_range_m:
        Slant range at end of simulation.
    n_frame_drops:
        Number of vision frame drops during the engagement.
    n_roe_abort_attempts:
        Number of ROE_ABORT exceptions raised (can exceed 1 if re-attempted).
    smith_predictor_used:
        Whether Smith-predictor lead was active.
    """
    hit: bool = False
    miss_distance_m: float = float("inf")
    time_to_closest_approach_s: float = 0.0
    roe_abort: bool = False
    roe_abort_reason: Optional[str] = None
    engagement_time_s: float = 0.0
    config: Optional[ClosedLoopConfig] = None
    interceptor_trajectory: list[tuple[float, float, float, float]] = field(default_factory=list)
    target_trajectory: list[tuple[float, float, float, float]] = field(default_factory=list)
    guidance_cmds: list[GuidanceCommand] = field(default_factory=list)
    final_range_m: float = float("inf")
    n_frame_drops: int = 0
    n_roe_abort_attempts: int = 0
    smith_predictor_used: bool = False
    # Mode B extras
    mode: str = "analytic"
    n_off_fov_frames: int = 0
    lock_states_seen: set = field(default_factory=set)
    # TRUE-PN diagnostics (measured_vc): whether/how much the MEASURED closing velocity drove PN.
    range_source_final: str = "inactive"      # last range-aiding verdict ("measured"|"fallback"|"inactive")
    n_measured_vc_ticks: int = 0              # vision ticks whose range estimate was confident ("measured")
    measured_vc_final_mps: Optional[float] = None   # last measured Vc handed to PN (m/s)


# ---------------------------------------------------------------------------
# Delay buffer
# ---------------------------------------------------------------------------

class _DelayBuffer:
    """FIFO buffer that delays observations by a fixed time.

    Stores (timestamp, data) tuples and returns data that is at least
    delay_s seconds old.
    """

    def __init__(self, delay_s: float, jitter_s: float = 0.0, rng: Any = None) -> None:
        self._delay_s = delay_s
        self._jitter_s = float(jitter_s)          # A5: per-frame latency jitter half-width (s)
        self._rng = rng                           # dedicated RNG so jitter never perturbs plant noise
        self._buf: deque[tuple[float, Any]] = deque()

    def _effective_delay(self) -> float:
        """Nominal delay, plus a per-frame uniform jitter when A5 latency jitter is active."""
        if self._jitter_s > 0.0 and self._rng is not None:
            return max(0.0, self._delay_s + float(self._rng.uniform(-self._jitter_s, self._jitter_s)))
        return self._delay_s

    def push(self, t: float, data: Any) -> None:
        self._buf.append((t, data))

    def pop_delayed(self, current_t: float) -> Optional[Any]:
        """Return the most recent data that is at least the (jittered) delay old."""
        result = None
        eff = self._effective_delay()
        while self._buf and current_t - self._buf[0][0] >= eff:
            _, data = self._buf.popleft()
            result = data
        return result

    def peek_delayed(self, current_t: float) -> Optional[Any]:
        """Same as pop_delayed but does not remove from buffer."""
        result = None
        for t_stored, data in self._buf:
            if current_t - t_stored >= self._delay_s:
                result = data
            else:
                break
        return result


# ---------------------------------------------------------------------------
# Closed-loop engine
# ---------------------------------------------------------------------------

class ClosedLoop:
    """Closed-loop intercept simulation engine.

    Runs the guidance/command-map/dynamics loop for one engagement.

    Usage
    -----
    ::
        cfg = ClosedLoopConfig(sim=SimConfig(target_geometry=EngagementGeometry.HEAD_ON))
        loop = ClosedLoop(cfg)
        result = loop.run(verbose=False)
        print(f"Miss: {result.miss_distance_m:.3f} m  Hit: {result.hit}")
    """

    def __init__(self, config: ClosedLoopConfig) -> None:
        self._cfg = config

    def run(self, verbose: bool = False) -> EngagementResult:
        """Run one complete engagement simulation.

        Parameters
        ----------
        verbose:
            If True, store full trajectories in the result.

        Returns
        -------
        EngagementResult
        """
        cfg = self._cfg
        sim_cfg = cfg.sim
        use_smith = cfg.smith_predictor if cfg.smith_predictor is not None else sim_cfg.smith_predictor

        rng = np.random.default_rng(sim_cfg.seed)

        use_pixel_mode = (cfg.mode == "pixel")

        # ── Mode B: construct per-engagement pixel-loop state ─────────────────
        pixel_state: Optional[PixelLoopState] = None
        if use_pixel_mode:
            pixel_state = make_pixel_loop_state(sim_cfg.seed, imm_cfg=cfg.imm,
                                                gyro_scale_error=sim_cfg.gyro_scale_error)

        # ── TRUE PN: subtense range filter (Mode B, measured_vc) ──────────────
        # When enabled, render a RANGE-DEPENDENT (closing) target and OBSERVE range + closing velocity
        # from its silhouette extent, so guidance runs on a MEASURED Vc instead of the scheduled scalar.
        range_filter: Optional[SubtenseRangeRateFilter] = None
        last_measured_vc: Optional[float] = None
        last_measured_tgo: Optional[float] = None
        last_range_source: str = "inactive"
        n_measured_vc_ticks: int = 0
        if use_pixel_mode and pixel_state is not None and sim_cfg.measured_vc:
            pixel_state.target_span_m = float(sim_cfg.target_span_m)
            range_filter = SubtenseRangeRateFilter(float(sim_cfg.target_span_m), pixel_state.intrinsics)

        # ── Initialize dynamics ────────────────────────────────────────────────
        quad = QuadSim(sim_cfg)
        target = TargetSim(sim_cfg)

        # ── Initialize guidance ────────────────────────────────────────────────
        guidance = BearingRateGuidance(cfg.guidance)
        pilot = LosGuidancePilot(config=cfg.pilot)
        imm = IMMFilter(cfg.imm)
        looming = LoomingEstimator()

        # ── Delay buffer (sensor + loop delay; A5 per-frame jitter) ──────────
        total_delay_s = sim_cfg.total_delay_s()
        # Dedicated RNG (seed-derived) so latency jitter never perturbs the plant/noise sequence:
        # with latency_jitter_s=0 this RNG is created but never drawn -> bit-identical baseline.
        delay_rng = np.random.default_rng((int(sim_cfg.seed) ^ 0x0DE1A4) & 0xFFFFFFFF)
        delay_buf: _DelayBuffer = _DelayBuffer(
            total_delay_s, jitter_s=sim_cfg.latency_jitter_s, rng=delay_rng)

        # Wave-1 honest-noise stream: SEPARATE RNG so the correlated lambda-dot bias and area noise
        # never perturb the plant/white-noise sequence.  With the honest terms at 0 it is created but
        # never drawn -> bit-identical to the pre-Wave-1 baseline.
        meas_rng = np.random.default_rng((int(sim_cfg.seed) ^ 0x10510B1A) & 0xFFFFFFFF)
        bias_az_rate: float = 0.0      # AR-1 lambda-dot bias state (persists across vision frames)
        bias_el_rate: float = 0.0

        # ── Timing setup ─────────────────────────────────────────────────────
        dt_sim = sim_cfg.dt_sim_s
        dt_guidance = 1.0 / sim_cfg.guidance_rate_hz
        dt_vision = 1.0 / sim_cfg.vision_rate_hz
        bias_rho = math.exp(-dt_vision / max(sim_cfg.los_rate_bias_tau_s, 1e-6))   # AR-1 retention/frame

        guidance_tick_counter = 0
        vision_tick_counter = 0
        next_guidance_t = 0.0
        next_vision_t = 0.0

        # ── State tracking ────────────────────────────────────────────────────
        t = 0.0
        min_range = float("inf")
        t_min_range = 0.0
        roe_abort = False
        roe_abort_reason: Optional[str] = None
        n_frame_drops = 0
        n_roe_abort_attempts = 0

        # Previous positions for segment-based closest-approach computation.
        # The continuous-minimum approach finds the exact closest approach on
        # each time-step segment [p0,p1] vs [q0,q1], not just at grid points.
        prev_int_pos: Optional[npt.NDArray[np.float64]] = None
        prev_tgt_pos: Optional[npt.NDArray[np.float64]] = None

        # Last-valid guidance bearing (for hold with decay)
        last_az: float = 0.0
        last_el: float = 0.0
        last_az_rate: float = 0.0
        last_el_rate: float = 0.0
        last_tau_conf: float = 0.0
        last_area_px: float = 4.0
        last_valid_guidance_cmd: Optional[GuidanceCommand] = None

        # Command to apply to the quad
        current_roll_cmd: float = 0.0
        current_pitch_cmd: float = cfg.pilot.forward_pitch_fraction
        current_yaw_cmd: float = 0.0
        current_throttle_cmd: float = cfg.pilot.throttle_hover

        # Trajectory storage
        interceptor_traj: list[tuple[float, float, float, float]] = []
        target_traj: list[tuple[float, float, float, float]] = []
        guidance_cmds_log: list[GuidanceCommand] = []
        frame_id: int = 0

        # ── Main simulation loop ──────────────────────────────────────────────
        # Track whether we have passed the closest-approach point.
        # Once range starts increasing after having been below a threshold,
        # we terminate (true closest approach has been captured).
        past_closest_approach: bool = False
        n_increasing_steps: int = 0    # consecutive steps where range is increasing
        _N_INC_TERM = 5               # terminate after this many increasing steps post-min
        prev_range_m: float = float("inf")

        while t <= sim_cfg.max_sim_time_s:
            q_state = quad.state
            tgt_state = target.state

            # ── Continuous closest-approach (segment minimum) ────────────────
            # For each pair of consecutive positions (p0→p1) and (q0→q1), find
            # the exact closest point on the line segment, using analytic linear
            # interpolation.  This removes the discrete-step artifact where
            # miss = capture_radius - one_step_closing_distance.
            #
            # When the relative trajectory is monotonically approaching (t* > 1),
            # the segment minimum is at the endpoint (same as grid sampling).
            # The TRUE benefit: when the relative trajectory turns around WITHIN
            # the segment (t* in [0,1]), we capture the exact minimum.  This
            # happens near actual closest approach (when range first starts to
            # increase), giving an accurate continuous miss distance.
            curr_int_pos = q_state.pos.copy()
            curr_tgt_pos = tgt_state.pos.copy()

            if prev_int_pos is not None and prev_tgt_pos is not None:
                seg_min = _segment_closest_approach(
                    prev_int_pos, curr_int_pos,
                    prev_tgt_pos, curr_tgt_pos,
                )
                if seg_min < min_range:
                    min_range = seg_min
                    t_min_range = t
            else:
                # First tick: just use point distance
                range_m0 = float(np.linalg.norm(curr_tgt_pos - curr_int_pos))
                if range_m0 < min_range:
                    min_range = range_m0
                    t_min_range = t

            prev_int_pos = curr_int_pos
            prev_tgt_pos = curr_tgt_pos

            # Current range (for guidance and early-termination logic)
            rel = tgt_state.pos - q_state.pos
            range_m = float(np.linalg.norm(rel))

            # Detect post-closest-approach: once range has been below a loose
            # threshold (3x capture_radius) and is now consistently increasing,
            # terminate — we have captured the true closest approach.
            if range_m < sim_cfg.capture_radius_m * 3.0:
                past_closest_approach = True

            if past_closest_approach:
                if range_m > prev_range_m:
                    n_increasing_steps += 1
                else:
                    n_increasing_steps = 0
                if n_increasing_steps >= _N_INC_TERM:
                    if verbose:
                        interceptor_traj.append((t, *q_state.pos.tolist()))
                        target_traj.append((t, *tgt_state.pos.tolist()))
                    break

            prev_range_m = range_m

            # ── Vision frame tick (at vision_rate_hz) ─────────────────────────
            if t >= next_vision_t:
                next_vision_t += dt_vision
                frame_id += 1

                if use_pixel_mode:
                    # ── MODE B: full seeker pipeline ──────────────────────────
                    # geometry -> render -> detect -> ego -> los -> imm
                    # IMPORTANT: the analytic bearing is used ONLY to position
                    # the rendered blob pixel.  The bearing/rate that enters
                    # the delay buffer and ultimately drives guidance is the
                    # output of the real detect->los->imm pipeline.
                    assert pixel_state is not None
                    los_obs_b, imm_est_b, detected = run_pixel_vision_tick(
                        q_state=q_state,
                        tgt_state=tgt_state,
                        pixel_state=pixel_state,
                        frame_id=frame_id,
                        t_sim=t,
                        dt_vision=dt_vision,
                        range_m=range_m,
                    )

                    # TRUE PN: feed the silhouette extent to the range filter (None on a miss -> coast);
                    # a resolved closing target yields a MEASURED Vc/t_go that replaces the scheduled Vc.
                    if range_filter is not None:
                        _ext = pixel_state.last_silhouette_major_px if detected else None
                        _rr = range_filter.update(_ext, dt_vision)
                        _aid = range_aiding_from_estimate(_rr)
                        last_range_source = _aid.source
                        if _aid.source == "measured":
                            last_measured_vc = _aid.vc_override_mps
                            last_measured_tgo = _aid.t_go_s
                            n_measured_vc_ticks += 1

                    if detected and los_obs_b is not None and imm_est_b is not None:
                        # Use IMM estimate from the real pipeline as the
                        # "measurement" to delay. This is what drives guidance.
                        if (sim_cfg.looming_from_detected_area
                                and pixel_state.last_detected_area_px is not None):
                            # HONEST: looming/tau from the REAL detected blob area (what the sensor
                            # actually saw this frame), not a clean read of the true range.
                            area_px_b = float(pixel_state.last_detected_area_px)
                        else:
                            # Legacy (bit-identical): area approximated from true range.
                            # WAVE-3: FT640 f_px (≈707), not the old Boson 2130.  The blob
                            # subtends ~3.0× fewer pixels at the same range under the wide lens.
                            f_px = _FT640_F_PX
                            target_size_m = 0.15
                            target_r_px = f_px * target_size_m / max(range_m, 1.0)
                            area_px_b = math.pi * target_r_px ** 2

                        # Push real pipeline outputs to delay buffer.
                        # az/el come from IMM (ego-compensated + filtered).
                        # az_rate/el_rate come from IMM.
                        # There is NO analytic bearing on this path.
                        delay_buf.push(t, (
                            imm_est_b.az_rad,
                            imm_est_b.el_rad,
                            imm_est_b.az_rate_radps,
                            imm_est_b.el_rate_radps,
                            area_px_b,
                            frame_id,
                        ))
                    # If not detected: no push; guidance holds last-valid on next tick

                else:
                    # ── MODE A: analytic bearing (original) ───────────────────
                    # Compute TRUE bearing from 3-D geometry
                    az_true, el_true, _ = compute_bearing_from_states(
                        q_state.pos, q_state.vel, tgt_state.pos
                    )
                    az_rate_true, el_rate_true = compute_los_rates(
                        q_state.pos, q_state.vel, tgt_state.pos, tgt_state.vel
                    )

                    # Analytic blob area (approximate): sigma=1.5 px, range-scaled
                    # area_px ≈ pi * r^2 where r = f * theta_target / range
                    # WAVE-3: FT640 f_px (≈707), not the old Boson 2130.  For a ~0.3 m drone:
                    # area ≈ pi * (707 * 0.15 / max(range_m, 1))^2 px — ~9× smaller area than
                    # the old narrow-lens approximation at the same range (f scales area as f^2).
                    f_px = _FT640_F_PX
                    target_size_m = 0.15
                    target_r_px = f_px * target_size_m / max(range_m, 1.0)
                    area_px = math.pi * target_r_px ** 2
                    # Wave-1 honest tau: the looming area is a NOISY/quantized pixel measurement, not a
                    # clean read of true range.  Default frac=0 -> area unchanged (bit-identical).
                    if sim_cfg.area_noise_frac > 0.0:
                        area_px = max(1.0, area_px * (1.0 + float(meas_rng.normal(0.0, sim_cfg.area_noise_frac))))
                        area_px = float(round(area_px))   # integer-pixel area for a few-px blob

                    # Measurement noise (white, per-frame independent)
                    noise_az = float(rng.normal(0.0, sim_cfg.bearing_noise_sigma_rad))
                    noise_el = float(rng.normal(0.0, sim_cfg.bearing_noise_sigma_rad))
                    noise_az_rate = float(rng.normal(0.0, sim_cfg.bearing_noise_sigma_rad * 3.0))
                    noise_el_rate = float(rng.normal(0.0, sim_cfg.bearing_noise_sigma_rad * 3.0))

                    # Wave-1 honest lambda-dot error: a CORRELATED AR-1 bias that does NOT average out
                    # in the IMM (ego / cam<->IMU-skew / centroid-drift residual).  Default sigma=0 ->
                    # no draw, no effect; meas_rng is a separate stream so the white sequence is intact.
                    if sim_cfg.los_rate_bias_sigma_radps > 0.0:
                        k = math.sqrt(max(1.0 - bias_rho * bias_rho, 0.0)) * sim_cfg.los_rate_bias_sigma_radps
                        bias_az_rate = bias_rho * bias_az_rate + k * float(meas_rng.normal())
                        bias_el_rate = bias_rho * bias_el_rate + k * float(meas_rng.normal())

                    az_meas = az_true + noise_az
                    el_meas = el_true + noise_el
                    az_rate_meas = az_rate_true + noise_az_rate + bias_az_rate
                    el_rate_meas = el_rate_true + noise_el_rate + bias_el_rate

                    # Push to delay buffer
                    delay_buf.push(t, (az_meas, el_meas, az_rate_meas, el_rate_meas,
                                       area_px, frame_id))

            # ── Guidance tick (at guidance_rate_hz) ────────────────────────────
            if t >= next_guidance_t:
                next_guidance_t += dt_guidance
                guidance_tick_counter += 1

                # Pop delayed bearing
                delayed_obs = delay_buf.pop_delayed(t)

                if delayed_obs is not None:
                    (az_d, el_d, az_rate_d, el_rate_d, area_d, fid_d) = delayed_obs

                    # Smith-predictor lead: advance BEARING by total_delay using the
                    # delayed rate as the prediction slope.
                    #
                    # SMITH IMPLEMENTATION (corrected):
                    #
                    # Prior attempt: recompute az_rate_guided from finite differences
                    # of consecutive advanced bearings.  This was WRONG: it amplified
                    # rate noise by (1/dt_vision) ≈ 60x per noise unit, causing spurious
                    # large commands that aborted the engagement.
                    #
                    # Correct approach: advance ONLY the bearing.  The rate fed to the
                    # IMM is the delayed rate (az_rate_d), which is the best available
                    # estimate of the current rate.  Under constant-rate assumption (the
                    # basis of the Smith prediction), the rate doesn't change over the
                    # delay period, so delayed rate == current rate.
                    #
                    # The (bearing, rate) pair is intentionally from slightly different
                    # time instants: bearing is predicted-present, rate is delayed.  The
                    # IMM handles this via its process noise model.  The improvement from
                    # advancing the bearing is in the DIRECTION of the command, not the
                    # magnitude.  This is the honest Smith predictor.
                    if use_smith:
                        az_guided = az_d + az_rate_d * total_delay_s
                        el_guided = el_d + el_rate_d * total_delay_s
                        # Rate: use delayed rate directly (NOT finite-differenced).
                        # Finite differencing amplifies noise; delayed rate is better.
                        az_rate_guided = az_rate_d
                        el_rate_guided = el_rate_d
                    else:
                        az_guided = az_d
                        el_guided = el_d
                        az_rate_guided = az_rate_d
                        el_rate_guided = el_rate_d

                    area_guided = area_d

                    last_az = az_guided
                    last_el = el_guided
                    last_az_rate = az_rate_guided
                    last_el_rate = el_rate_guided
                    last_area_px = area_guided
                else:
                    # Frame drop: hold last-valid with decay
                    n_frame_drops += 1
                    last_az_rate *= cfg.los_hold_decay
                    last_el_rate *= cfg.los_hold_decay
                    az_guided = last_az
                    el_guided = last_el
                    az_rate_guided = last_az_rate
                    el_rate_guided = last_el_rate
                    area_guided = last_area_px

                if use_pixel_mode:
                    # MODE B: bypass the outer IMM.
                    #
                    # The bearing/rate values (az_guided, el_guided, ...) are
                    # already the output of the IMMFilter inside run_pixel_vision_tick
                    # (pixel_loop.py step 9).  Running the outer IMM a second time
                    # here would double-smooth detection noise, making Mode B CPA
                    # look artificially tight — the double-IMM bug.
                    #
                    # Fix: wrap the values in a pass-through IMMEstimate without
                    # calling imm.update().  The outer IMM is Mode A only.
                    imm_est = _passthrough_imm_estimate(
                        az_rad=az_guided,
                        el_rad=el_guided,
                        az_rate_radps=az_rate_guided,
                        el_rate_radps=el_rate_guided,
                        frame_id=frame_id,
                        t_s=t,
                    )
                else:
                    # MODE A: build synthetic LOSObservation and run the outer IMM
                    los_obs = LOSObservation(
                        az_rad=az_guided,
                        el_rad=el_guided,
                        az_rate_radps=az_rate_guided,
                        el_rate_radps=el_rate_guided,
                        ego_quality=1.0,
                        ego_source="gyro",
                        frame_id=frame_id,
                        t_capture_ns=int(t * 1e9),
                    )
                    imm_est = imm.update(los_obs, dt_guidance)

                # Looming update
                looming_est = looming.update(area_guided, dt_guidance)
                last_tau_conf = looming_est.tau_confidence

                # Vc for PN: the MEASURED closing velocity (subtense range filter) when it is confident;
                # otherwise the scheduled scalar (graceful fallback).  This is TRUE PN in the loop.
                own_speed = float(np.linalg.norm(q_state.vel))
                if range_filter is not None and last_range_source == "measured" and last_measured_vc is not None:
                    Vc = last_measured_vc
                else:
                    Vc = schedule_Vc_mps(
                        own_speed,
                        target_speed_assumed_mps=sim_cfg.target_speed_mps,
                        geometry=GeometryClass.HEAD_ON,
                    )

                # Guidance law
                try:
                    g_cmd = guidance.compute(imm_est, looming_est, Vc_override_mps=Vc)
                    last_valid_guidance_cmd = g_cmd

                    # Map to quad commands
                    ai_cmd = pilot.command_from_guidance(
                        g_cmd,
                        az_rad=imm_est.az_rad,
                        el_rad=imm_est.el_rad,
                        sequence_id=guidance_tick_counter,
                        timestamp_ms=int(t * 1e3),
                        estimated_range_m=range_m,
                    )
                    current_roll_cmd = ai_cmd.roll_cmd
                    current_pitch_cmd = ai_cmd.pitch_cmd
                    current_yaw_cmd = ai_cmd.yaw_rate_cmd
                    current_throttle_cmd = ai_cmd.throttle_cmd

                    if verbose:
                        guidance_cmds_log.append(g_cmd)

                except ROEAbort as abort:
                    n_roe_abort_attempts += 1
                    if not roe_abort:
                        roe_abort = True
                        roe_abort_reason = abort.reason
                    # HONEST ABORT RESPONSE: zero lateral commands.
                    #
                    # Previous behaviour (hold last-valid command) created a
                    # SPURIOUS near-miss: the last command had already turned the
                    # interceptor toward the target, so coasting on that command
                    # produced a 1.27m 'miss' even for a genuinely uninterceptable
                    # crossing target.  This is false confidence.
                    #
                    # Correct behaviour: on abort, zero the lateral roll/yaw
                    # commands.  Maintain forward pitch and hover throttle so the
                    # interceptor continues forward without lateral correction.
                    # This produces an HONEST large miss for uninterceptable cases.
                    #
                    # Physical justification: in a real system, an ROE_ABORT
                    # triggers a safe-ditch / hold mode that cancels intercept
                    # guidance, not a frozen bank-angle that may still intercept.
                    current_roll_cmd = 0.0
                    current_pitch_cmd = cfg.pilot.forward_pitch_fraction
                    current_yaw_cmd = 0.0
                    current_throttle_cmd = cfg.pilot.throttle_hover

            # ── Physics integration step ─────────────────────────────────────
            quad.step(
                roll_cmd=current_roll_cmd,
                pitch_cmd=current_pitch_cmd,
                yaw_rate_cmd=current_yaw_cmd,
                throttle_cmd=current_throttle_cmd,
                dt=dt_sim,
            )
            target.step(dt_sim)

            # Store trajectory at vision rate for efficiency
            if verbose and frame_id % 1 == 0:
                interceptor_traj.append((t, *quad.state.pos.tolist()))
                target_traj.append((t, *target.state.pos.tolist()))

            t += dt_sim

        final_range = float(np.linalg.norm(target.state.pos - quad.state.pos))

        return EngagementResult(
            hit=(min_range < sim_cfg.capture_radius_m),
            miss_distance_m=min_range,
            time_to_closest_approach_s=t_min_range,
            roe_abort=roe_abort,
            roe_abort_reason=roe_abort_reason,
            engagement_time_s=t,
            config=cfg,
            interceptor_trajectory=interceptor_traj,
            target_trajectory=target_traj,
            guidance_cmds=guidance_cmds_log,
            final_range_m=final_range,
            n_frame_drops=n_frame_drops,
            n_roe_abort_attempts=n_roe_abort_attempts,
            smith_predictor_used=use_smith,
            mode=cfg.mode,
            n_off_fov_frames=pixel_state.n_off_fov_frames if pixel_state is not None else 0,
            lock_states_seen=pixel_state.lock_states_seen if pixel_state is not None else set(),
            range_source_final=last_range_source,
            n_measured_vc_ticks=n_measured_vc_ticks,
            measured_vc_final_mps=last_measured_vc,
        )


# ---------------------------------------------------------------------------
# Monte-Carlo runner
# ---------------------------------------------------------------------------

@dataclass
class MonteCarloResult:
    """Aggregated results from a Monte-Carlo miss-distance sweep.

    Attributes
    ----------
    n_runs:
        Total number of runs.
    n_hits:
        Number of HITs (miss_distance < capture_radius).
    n_aborts:
        Number of ROE_ABORTs.
    miss_distances_m:
        Array of miss distances for all runs (m).
    miss_median_m, miss_p90_m, miss_max_m:
        Percentile statistics of miss distances (m).
    hit_rate:
        n_hits / n_runs.
    N_value:
        Navigation ratio N used.
    geometry:
        Target engagement geometry.
    sensor_delay_s:
        Sensor delay used.
    smith_predictor:
        Whether Smith-predictor was used.
    """
    n_runs: int = 0
    n_hits: int = 0
    n_aborts: int = 0
    miss_distances_m: npt.NDArray[np.float64] = field(
        default_factory=lambda: np.array([], dtype=np.float64)
    )
    miss_median_m: float = float("nan")
    miss_p90_m: float = float("nan")
    miss_max_m: float = float("nan")
    hit_rate: float = 0.0
    N_value: float = 3.0
    geometry: str = "HEAD_ON"
    sensor_delay_s: float = 0.030
    smith_predictor: bool = True


def run_monte_carlo(
    base_cfg: ClosedLoopConfig,
    *,
    n_seeds: int = 50,
    N_values: Sequence[float] = (3.0, 4.0),
    geometries: Sequence[EngagementGeometry] = (
        EngagementGeometry.HEAD_ON,
        EngagementGeometry.QUARTERING,
    ),
    sensor_delays_s: Sequence[float] = (0.0, 0.025, 0.045),
    smith_predictor_values: Sequence[bool] = (True, False),
    randomize: bool = False,
    randomize_frac: float = 0.2,
    latency_jitter_max_s: float = 0.010,    # A5: per-frame delay jitter swept in [0, this] when randomize
    target_step_jink_max_g: float = 0.28,   # A5: sustained step-jink swept in [0, this] when randomize
    verbose: bool = False,
) -> list[MonteCarloResult]:
    """Run a Monte-Carlo sweep over seeds, geometries, N values, delays.

    Each combination of (N, geometry, sensor_delay, smith) is swept over
    n_seeds random seeds.

    Parameters
    ----------
    base_cfg:
        Base configuration.  N, geometry, sensor_delay, smith_predictor will
        be overridden by the sweep values.
    n_seeds:
        Number of random seeds per combination.
    N_values:
        Navigation ratios to sweep.
    geometries:
        Engagement geometries to sweep.
    sensor_delays_s:
        Sensor delays to sweep (seconds).
    smith_predictor_values:
        Whether to use Smith-predictor lead.
    verbose:
        Print progress.

    Returns
    -------
    list[MonteCarloResult]
        One result per (N, geometry, delay, smith) combination.
    """
    results = []

    for N in N_values:
        for geom in geometries:
            for delay_s in sensor_delays_s:
                for smith in smith_predictor_values:
                    misses = []
                    n_hits = 0
                    n_aborts = 0

                    for seed in range(n_seeds):
                        # A5 honest Monte-Carlo: when randomize, draw the plant/target params
                        # per seed so robustness is not measured against a single fixed plant.
                        # (Per-frame latency jitter is a deeper sim change -- noted in the plan.)
                        b = base_cfg.sim
                        if randomize:
                            r = np.random.default_rng((0xA5A50000 ^ (seed * 2654435761)) & 0xFFFFFFFF)
                            j = r.uniform(-randomize_frac, randomize_frac, size=4)
                            attitude_tau = float(b.attitude_tau_s * (1.0 + j[0]))
                            drag = float(b.drag_coeff * (1.0 + j[1]))
                            mass = float(b.mass_kg * (1.0 + j[2]))
                            bearing_noise = float(b.bearing_noise_sigma_rad * (1.0 + j[3]))
                            target_jink = float(r.uniform(0.0, max(b.target_jink_g, 0.28)))
                            # A5: sweep the two stressors the gate NAMES but never exercised --
                            # per-frame latency jitter and the SUSTAINED step-jink (the sinusoidal
                            # target_jink_g averages to zero; the step is what actually tests miss).
                            latency_jitter = float(r.uniform(0.0, latency_jitter_max_s))
                            target_step_jink = float(r.uniform(0.0, target_step_jink_max_g))
                        else:
                            attitude_tau, drag, mass = b.attitude_tau_s, b.drag_coeff, b.mass_kg
                            bearing_noise, target_jink = b.bearing_noise_sigma_rad, b.target_jink_g
                            latency_jitter, target_step_jink = b.latency_jitter_s, b.target_step_jink_g
                        # Override sim config
                        sim_cfg = SimConfig(
                            seed=seed,
                            target_geometry=geom,
                            sensor_delay_s=delay_s,
                            smith_predictor=smith,
                            # carry rest from base:
                            dt_sim_s=b.dt_sim_s,
                            guidance_rate_hz=b.guidance_rate_hz,
                            vision_rate_hz=b.vision_rate_hz,
                            loop_delay_s=b.loop_delay_s,
                            theta_max_rad=b.theta_max_rad,
                            drag_coeff=drag,
                            attitude_tau_s=attitude_tau,
                            mass_kg=mass,
                            capture_radius_m=b.capture_radius_m,
                            target_speed_mps=b.target_speed_mps,
                            target_jink_g=target_jink,
                            target_jink_freq_hz=b.target_jink_freq_hz,
                            target_step_jink_g=target_step_jink,
                            latency_jitter_s=latency_jitter,
                            interceptor_speed_mps=b.interceptor_speed_mps,
                            initial_range_m=b.initial_range_m,
                            max_sim_time_s=b.max_sim_time_s,
                            bearing_noise_sigma_rad=bearing_noise,
                            # Wave-1 honest measurement model: carry from base so an honest-MC
                            # sweep actually injects the correlated lambda-dot bias + noisy looming
                            # area.  Default 0 on the base -> these stay 0 -> bit-identical baseline.
                            los_rate_bias_sigma_radps=b.los_rate_bias_sigma_radps,
                            los_rate_bias_tau_s=b.los_rate_bias_tau_s,
                            area_noise_frac=b.area_noise_frac,
                            gyro_scale_error=b.gyro_scale_error,
                            looming_from_detected_area=b.looming_from_detected_area,
                            # High-speed regime: carry the forward speed-hold so a 150 m/s sweep
                            # actually cruises at the setpoint (default OFF -> bit-identical).
                            speed_hold=b.speed_hold,
                            speed_hold_gain_hz=b.speed_hold_gain_hz,
                        )
                        guidance_cfg = GuidanceConfig(
                            N=N,
                            Vc_sched_mps=base_cfg.guidance.Vc_sched_mps,
                            theta_max_rad=base_cfg.guidance.theta_max_rad,
                            abort_g_margin=base_cfg.guidance.abort_g_margin,
                            crossing_rate_threshold_radps=base_cfg.guidance.crossing_rate_threshold_radps,
                            vc_scaled_crossing_threshold=base_cfg.guidance.vc_scaled_crossing_threshold,
                            tau_confidence_pursuit_threshold=base_cfg.guidance.tau_confidence_pursuit_threshold,
                            tau_confidence_full_brn_threshold=base_cfg.guidance.tau_confidence_full_brn_threshold,
                            pursuit_gain_mps2_per_rad=base_cfg.guidance.pursuit_gain_mps2_per_rad,
                            maneuver_prob_threshold=base_cfg.guidance.maneuver_prob_threshold,
                            apn_accel_cap_mps2=base_cfg.guidance.apn_accel_cap_mps2,
                            max_a_cmd_mps2=base_cfg.guidance.max_a_cmd_mps2,
                        )
                        cl_cfg = ClosedLoopConfig(
                            sim=sim_cfg,
                            guidance=guidance_cfg,
                            pilot=base_cfg.pilot,
                            imm=base_cfg.imm,
                            mode=base_cfg.mode,
                            los_hold_decay=base_cfg.los_hold_decay,
                            smith_predictor=smith,
                        )
                        loop = ClosedLoop(cl_cfg)
                        result = loop.run(verbose=False)

                        misses.append(result.miss_distance_m)
                        if result.hit:
                            n_hits += 1
                        if result.roe_abort:
                            n_aborts += 1

                    miss_arr = np.array(misses, dtype=np.float64)
                    # Filter out inf for stats (ROE_ABORTs may have inf miss)
                    finite_misses = miss_arr[np.isfinite(miss_arr)]
                    if len(finite_misses) > 0:
                        median_m = float(np.median(finite_misses))
                        p90_m = float(np.percentile(finite_misses, 90))
                        max_m = float(np.max(finite_misses))
                    else:
                        median_m = p90_m = max_m = float("nan")

                    mc_result = MonteCarloResult(
                        n_runs=n_seeds,
                        n_hits=n_hits,
                        n_aborts=n_aborts,
                        miss_distances_m=miss_arr,
                        miss_median_m=median_m,
                        miss_p90_m=p90_m,
                        miss_max_m=max_m,
                        hit_rate=n_hits / n_seeds,
                        N_value=N,
                        geometry=geom.value,
                        sensor_delay_s=delay_s,
                        smith_predictor=smith,
                    )
                    results.append(mc_result)

                    if verbose:
                        print(
                            f"  N={N} geom={geom.value:<14} delay={delay_s*1e3:.0f}ms "
                            f"smith={str(smith):<5} "
                            f"hits={n_hits}/{n_seeds} "
                            f"miss: med={median_m:.2f}m p90={p90_m:.2f}m max={max_m:.2f}m "
                            f"aborts={n_aborts}"
                        )

    return results
