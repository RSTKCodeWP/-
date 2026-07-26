"""Mode B (pixel-in-the-loop) vision-tick bridge for the closed-loop sim.

OVERVIEW
--------
This module provides ``run_pixel_vision_tick`` — a drop-in replacement for the
Mode A analytic vision tick in ``closed_loop.py``.

When ``mode='pixel'`` the *entire* seeker pipeline is exercised each vision tick:

    1. geometry  -> project true body-frame bearing to a camera pixel
    2. thermal_sim -> render a synthetic thermal frame (hot blob + stars + noise)
    3. detect    -> S1 blob detection on the rendered frame
    4. egomotion -> gyro de-rotation driven by REAL quad body rates (NOT scripted)
    5. los       -> LOSComputer ego-compensated bearing + LOS-rate
    6. track     -> ThermalLockTracker lock/coast/reacquire FSM
    7. imm       -> IMMFilter filtered LOS-rate (fed to guidance as λ̇)
    8. delay     -> DelayBuffer injects the Boson >25 ms sensor delay

BODY / CAMERA FRAME AND EGO-COMPENSATION
------------------------------------------
The closed-loop quad_sim uses the VELOCITY DIRECTION as the camera boresight.
This means the camera is effectively gimballed to always point along the velocity
vector — the bearing (az, el) computed by ``compute_bearing_from_states`` already
reflects the full body attitude (roll, pitch, yaw) via the velocity direction.

Consequence for ego-compensation
    The bearing rendered to a pixel already accounts for the body attitude.
    Between frames, the change in the bearing pixel IS the true LOS motion
    (target own motion relative to the velocity-aligned boresight).
    Unlike a rigidly-body-fixed camera, the body rotation does NOT cause
    additional apparent pixel motion on top of the true LOS motion.

    HOWEVER: for the star rendering, we DO apply ego shift to stars because stars
    are WORLD-FIXED and their positions shift in the image due to both the
    velocity-direction change AND the body roll.  The ego shift applied to stars
    drives the LOSComputer to produce a non-zero ego estimate, which it uses to
    compensate apparent star motion.  For the TARGET, which is computed from
    geometry, its pixel position already reflects the true bearing — so the ego
    compensation applied by LOSComputer to the target centroid will slightly
    over-compensate.

    FIX (Mode B specific): We feed body rates to gyro_derotation as in S2 tests,
    but we ONLY apply the ego to star rendering (to make KLT honest) and NOT
    to the LOSComputer's bearing computation.  Instead, the LOSComputer input
    centroid is passed as-is (the detected centroid), and the ego estimate is
    passed so that the rate computation is ego-corrected.  This correctly
    computes the relative LOS rate (target own angular motion) while leaving the
    bearing accurate.

    In practice: for a velocity-aligned boresight, the pitch/yaw body rates
    cause the velocity direction to change, which is already captured in the
    changing target pixel position.  The ego shift is zero for a velocity-aligned
    camera.  We therefore pass omega=(0,0,roll_rate_only) to the gyro derotation,
    where roll_rate is the boresight-axis rotation rate (the only ego that is NOT
    captured by the velocity-direction change).

    Simplified implementation: pass ego with zero pitch/yaw rates (only roll
    from the boresight axis change) so that the LOSComputer's ego-compensation
    only corrects the in-plane roll, not pitch/yaw which are already in the pixel.

GEOMETRY -> PIXEL PROJECTION (sign-exact derivation)
------------------------------------------------------
Given the true 3-D geometry (quad position + ATTITUDE + target position):
1. Compute body-frame bearing (az_true, el_true) using compute_bearing_from_states.
   This function uses boresight = velocity direction, body_right = boresight × world_up,
   body_up = body_right × boresight.
2. Project to pixel using geometry.bearing_to_pixel:
       px = cx + f * tan(az_true)       (right is +x in image = positive az)
       py = cy - f * tan(el_true)       (up is -y in image = positive el is up → py < cy)
3. If (px, py) is outside [0, W) x [0, H), the target is OFF-FOV — do NOT render
   a target blob; the seeker will coast/reacquire.

IMPORTANT: When mode='pixel', the analytic true bearing az_true / el_true is used
ONLY to compute the target pixel for rendering.  The bearing that drives guidance
is ALWAYS the output of detect->los->imm, never az_true/el_true.

LATENCY
-------
The Boson >25 ms delay is injected via the same _DelayBuffer from closed_loop.py.
The bearing pushed into the delay buffer is the IMM estimate, not az_true.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np
import numpy.typing as npt

from fpv.seeker.detect import detect_frame, ThresholdState
from fpv.seeker.egomotion import gyro_derotation
from fpv.seeker.los import LOSComputer, LOSObservation
from fpv.seeker.track import ThermalLockTracker, ThermalLockConfig, TrackingState
from fpv.seeker.blob import TargetObservation
from fpv.seeker.imm import IMMFilter, IMMConfig, IMMEstimate
from fpv.seeker.silhouette import silhouette_extent
from fpv.seeker.geometry import (
    CameraIntrinsics,
    bearing_to_pixel,
    focal_length_from_hfov,
    ft640_intrinsics,
)

from fpv.guidance.quad_sim import QuadState, TargetState, compute_bearing_from_states


def _wide_fpv_intrinsics() -> CameraIntrinsics:
    """Return camera intrinsics for the fielded FPV thermal seeker.

    WAVE-3: reconciled to the FOXEER FT640 V2 wide lens (HFOV 48.7°,
    f_px ≈ 707 px, ≈1.41 mrad/px) — the camera actually fielded on the Block-3
    interceptor and the one the DETECT-envelope budget assumes.  Previously this
    returned a hand-rolled "Boson 640 9 mm @ 50° HFOV" model (f_px ≈ 686); the
    geometry was already in the right wide ballpark, but ft640_intrinsics() is
    the single source of truth so the pixel-in-the-loop optics match the budget
    and the Mode-A looming f_px exactly.

    A 48.7° HFOV gives VFOV ≈ 39.8° at 640×512, so the target stays on-sensor
    for pitch / yaw excursions up to ~±20 deg — consistent with the 40 deg
    theta_max in the dynamics model.
    """
    return ft640_intrinsics()


# ---------------------------------------------------------------------------
# Thermal frame renderer (inline, no dependency on ThermalSimulator.generate)
# ---------------------------------------------------------------------------

def _render_one_frame(
    *,
    target_px: float,
    target_py: float,
    target_in_fov: bool,
    cum_ego_dx: float,
    cum_ego_dy: float,
    intrinsics: CameraIntrinsics,
    star_positions: list[tuple[float, float]],
    rng: np.random.Generator,
    sky_base_counts: int = 4096,
    sky_gradient_amplitude: float = 200.0,
    read_noise_sigma: float = 12.0,
    target_peak_above_bg: float = 1800.0,
    target_sigma_px: float = 1.5,
    star_peak_fraction: float = 0.55,
    cam_temp_c: float = 25.0,
    cam_temp_additive: float = 0.0,
    star_sigma_px: Optional[float] = None,
) -> npt.NDArray[np.uint16]:
    """Render one synthetic thermal frame.

    Mirrors seeker_sim.SeekerSim._render_thermal_frame but is driven by the
    live geometry rather than a scripted trajectory.

    Stars are placed at (sx + cum_ego_dx, sy + cum_ego_dy) so that
    world-fixed stars shift in the image with the cumulative ego — this is
    what makes KLT honest (stars move with ego).

    If target_in_fov is False, the target blob is omitted (off-FOV lock-loss
    scenario).
    """
    H = intrinsics.height
    W = intrinsics.width

    # Cold sky + gradient + read noise
    yy = np.linspace(0.0, 1.0, H)[:, np.newaxis]
    sky_grad = sky_gradient_amplitude * (0.6 * yy)
    sky_grad = np.broadcast_to(sky_grad, (H, W)).copy()
    noise = rng.normal(0.0, read_noise_sigma, size=(H, W))
    frame_f = (np.full((H, W), float(sky_base_counts), dtype=np.float64)
               + sky_grad + noise + cam_temp_additive)

    yy_idx = np.arange(H, dtype=np.float64)[:, np.newaxis]
    xx_idx = np.arange(W, dtype=np.float64)[np.newaxis, :]

    # Target hot spot — only if in FOV
    if target_in_fov:
        dx = xx_idx - target_px
        dy = yy_idx - target_py
        r2 = dx * dx + dy * dy
        frame_f += target_peak_above_bg * np.exp(-r2 / (2.0 * target_sigma_px ** 2))

    # Stars: world-fixed features translated by cumulative ego shift.  Their size is a fixed PSF
    # feature (world features do not grow with the TARGET's range) -- use the explicit star_sigma_px
    # when given (range-dependent target mode), else the legacy derivation (bit-identical when off).
    star_peak = target_peak_above_bg * star_peak_fraction
    star_sigma = max(0.8, target_sigma_px * 0.8) if star_sigma_px is None else star_sigma_px
    for sx, sy in star_positions:
        star_img_x = sx + cum_ego_dx
        star_img_y = sy + cum_ego_dy
        dx_s = xx_idx - star_img_x
        dy_s = yy_idx - star_img_y
        r2_s = dx_s * dx_s + dy_s * dy_s
        frame_f += star_peak * np.exp(-r2_s / (2.0 * star_sigma ** 2))

    return np.clip(frame_f, 0.0, 16383.0).astype(np.uint16)


# ---------------------------------------------------------------------------
# Persistent per-engagement pixel-loop state
# ---------------------------------------------------------------------------

@dataclass
class PixelLoopState:
    """Mutable state for one Mode B engagement.

    Held by the caller (ClosedLoop.run) and updated each vision tick.
    Encapsulates all S1/S2 pipeline state so the per-engagement harness is
    clean.

    Attributes
    ----------
    intrinsics:
        Camera intrinsics (FOXEER FT640 V2 wide lens by default — see
        _wide_fpv_intrinsics; was a 50-deg "Boson 9 mm" model pre-Wave-3).
    star_positions:
        Fixed world star positions (set at construction, stable across frames).
    rng:
        Per-engagement RNG for render noise (seeded deterministically).
    threshold_state:
        S1 adaptive threshold state (carried across frames).
    tracker:
        ThermalLockTracker FSM.
    los_computer:
        LOSComputer (S2 ego-compensated bearing + rate).
    imm:
        IMMFilter for LOS-rate smoothing.
    prev_attitude_rad:
        Previous frame's quad attitude_rad [roll, pitch, yaw] for finite-
        difference body-rate estimation.
    cum_ego_dx, cum_ego_dy:
        Cumulative translational ego shift (pixels) for star rendering.
    cum_roll_rad:
        Cumulative roll angle (radians) for star rendering.
    frame_count:
        Number of frames rendered (for FFC injection spacing).
    last_los_obs:
        Most recent LOSObservation from the real pipeline (for hold-on-drop).
    last_imm_est:
        Most recent IMMEstimate (for hold-on-drop).
    n_off_fov_frames:
        Counter for consecutive off-FOV frames (diagnostic).
    lock_states_seen:
        Set of TrackingState values observed (for Gate P assertion).
    """

    intrinsics: CameraIntrinsics = field(
        default_factory=_wide_fpv_intrinsics
    )
    star_positions: list[tuple[float, float]] = field(default_factory=list)
    rng: np.random.Generator = field(
        default_factory=lambda: np.random.default_rng(0)
    )
    threshold_state: ThresholdState = field(default_factory=ThresholdState)
    tracker: ThermalLockTracker = field(
        default_factory=lambda: ThermalLockTracker(ThermalLockConfig(
            stable_frame_count=3,
            max_gate_px=60.0,           # slightly wider than default for sim
            predictive_track_frames=18,
            reacquire_frames=90,
        ))
    )
    los_computer: LOSComputer = field(init=False)
    imm: IMMFilter = field(init=False)
    prev_attitude_rad: Optional[npt.NDArray[np.float64]] = None
    cum_ego_dx: float = 0.0
    cum_ego_dy: float = 0.0
    cum_roll_rad: float = 0.0
    frame_count: int = 0
    last_los_obs: Optional[LOSObservation] = None
    last_imm_est: Optional[IMMEstimate] = None
    n_off_fov_frames: int = 0
    lock_states_seen: set = field(default_factory=set)
    # Mode-B cam<->IMU / gyro scale-factor residual on the roll de-rotation (0 -> bit-identical).
    gyro_scale_error: float = 0.0
    # Real detected blob area (px) from the last detected frame, for honest looming/tau.
    last_detected_area_px: Optional[float] = None
    # RANGE-DEPENDENT target rendering (default None -> fixed psf_sigma_px blob, bit-identical). When a
    # physical span is set, the rendered blob GROWS as the target closes: the silhouette major axis
    # (~2.3548*sigma for a gaussian) tracks f_px*span/range, and the psf floor keeps a far target a point
    # source (unresolved) until it resolves -- so a closing target is finally OBSERVABLE in Mode B (the
    # fixed-1.5px blob never grew, which is why subtense ranging could not be exercised in the loop).
    target_span_m: Optional[float] = None
    psf_sigma_px: float = 1.5             # point-spread floor: a far/point target renders at this sigma
    last_rendered_sigma_px: Optional[float] = None   # diagnostic: the sigma used for the last render
    # Robust silhouette major axis (px) of the last detected target, for honest subtense ranging (only
    # populated when target_span_m is set and the footprint resolves; None otherwise).  Top-hat-immune.
    last_silhouette_major_px: Optional[float] = None

    def __post_init__(self) -> None:
        self.los_computer = LOSComputer(self.intrinsics)
        # IMMConfig with slightly looser noise to tolerate detection quantization
        imm_cfg = IMMConfig(
            sigma_meas_az=2e-3,
            sigma_meas_el=2e-3,
            sigma_meas_az_rate=0.02,
            sigma_meas_el_rate=0.02,
            q_cv_rate=0.01,
            q_maneuver_rate=0.8,
            ego_gate_radps=0.1,
        )
        self.imm = IMMFilter(imm_cfg)

    def seed_tracker(self, intrinsics: CameraIntrinsics) -> None:
        """Seed the lock tracker over the full sensor area.

        In the closed-loop sim the target starts near the image centre
        (boresight-aligned head-on geometry) but may move anywhere in the FOV.
        Using the full-image acquisition box avoids spurious CANDIDATE→NO_TARGET
        resets during the initial frames where the centroid may drift slightly.
        """
        self.tracker.seed(acquisition_box=(
            0.0, 0.0,
            float(intrinsics.width),
            float(intrinsics.height),
        ))


def make_pixel_loop_state(
    sim_seed: int,
    imm_cfg: Optional[IMMConfig] = None,
    gyro_scale_error: float = 0.0,
) -> PixelLoopState:
    """Construct a fresh PixelLoopState for one Mode B engagement.

    Parameters
    ----------
    sim_seed:
        Engagement random seed.  Stars are placed deterministically from this.
    imm_cfg:
        Optional IMMConfig override (uses Mode B defaults if None).
    """
    intr = _wide_fpv_intrinsics()

    # Fixed star positions (world frame, stable across the engagement)
    rng_stars = np.random.default_rng(sim_seed * 1000 + 7)
    margin = 30
    xs = rng_stars.uniform(margin, intr.width - margin, size=12).tolist()
    ys = rng_stars.uniform(margin, intr.height - margin, size=12).tolist()
    stars = list(zip(xs, ys))

    state = PixelLoopState(
        intrinsics=intr,
        star_positions=stars,
        rng=np.random.default_rng(sim_seed * 31337 + 13),
        gyro_scale_error=float(gyro_scale_error),
    )

    if imm_cfg is not None:
        state.imm = IMMFilter(imm_cfg)

    state.seed_tracker(intr)
    return state


# ---------------------------------------------------------------------------
# Public: one Mode B vision tick
# ---------------------------------------------------------------------------

def run_pixel_vision_tick(
    *,
    q_state: QuadState,
    tgt_state: TargetState,
    pixel_state: PixelLoopState,
    frame_id: int,
    t_sim: float,
    dt_vision: float,
    range_m: float,
) -> tuple[Optional[LOSObservation], Optional[IMMEstimate], bool]:
    """Execute one Mode B vision tick.

    Geometry -> render -> detect -> ego -> los -> track -> imm.

    This function has NO path from which the analytic bearing (computed from
    q_state/tgt_state) reaches the returned LOSObservation or IMMEstimate.
    The analytic bearing is used ONLY to determine the target pixel for
    rendering.  After rendering, the pipeline is fully data-driven.

    Parameters
    ----------
    q_state:
        Current interceptor state (position, velocity, attitude_rad).
    tgt_state:
        Current target state.
    pixel_state:
        Mutable per-engagement state (updated in place).
    frame_id:
        Monotonically increasing frame counter.
    t_sim:
        Current simulation time (seconds).
    dt_vision:
        Time elapsed since the previous vision tick (seconds).
    range_m:
        Current slant range (for blob area scaling, informational only).

    Returns
    -------
    (los_obs, imm_est, target_detected)
        los_obs:   LOSObservation from S2, or None if target not detected/locked.
        imm_est:   IMMEstimate from the filter, or None if no observation.
        target_detected: True if the target was detected and associated this frame.
    """
    intr = pixel_state.intrinsics
    ps = pixel_state

    # ------------------------------------------------------------------
    # STEP 1: Compute true body-frame bearing (ONLY for rendering pixel)
    # ------------------------------------------------------------------
    az_true, el_true, _ = compute_bearing_from_states(
        q_state.pos, q_state.vel, tgt_state.pos
    )

    # ------------------------------------------------------------------
    # STEP 2: Project to pixel and check FOV
    # ------------------------------------------------------------------
    px_true, py_true = bearing_to_pixel(az_true, el_true, intr)

    # FOV check: target must project onto sensor [0,W) x [0,H)
    target_in_fov = (
        0.0 <= px_true < intr.width
        and 0.0 <= py_true < intr.height
    )

    if not target_in_fov:
        ps.n_off_fov_frames += 1

    # ------------------------------------------------------------------
    # STEP 3: Estimate body angular rates from attitude finite-differences.
    #
    # QuadSim attitude_rad = [roll, pitch, yaw].
    # Convention mapping to seeker egomotion.py:
    #   omega_x = pitch rate = d(attitude[1])/dt  (about body +X rightward)
    #   omega_y = yaw rate   = d(attitude[2])/dt  (about body +Y upward)
    #   omega_z = roll rate  = d(attitude[0])/dt  (about body +Z boresight)
    #
    # EGO COMPENSATION DESIGN FOR VELOCITY-ALIGNED BORESIGHT
    # --------------------------------------------------------
    # The quad_sim compute_bearing_from_states uses the VELOCITY direction as the
    # camera boresight.  This means pitch and yaw body rates already change the
    # boresight direction and are reflected in the target pixel position change
    # from frame to frame.  Passing pitch/yaw rates to gyro_derotation would
    # cause LOSComputer to DOUBLE-COMPENSATE (the pixel already moved due to
    # pitch/yaw; subtracting the ego would subtract it twice).
    #
    # For STAR rendering: stars are world-fixed.  Their image positions shift due
    # to BOTH velocity-direction change (pitch/yaw body motion → boresight rotates
    # → stars move in the image) AND body roll (in-plane rotation of the image).
    # We apply the full ego shift to stars to make them move realistically in the
    # rendered frame (so KLT tracks them correctly).
    #
    # For LOSComputer INPUT: we pass omega_x=0, omega_y=0 (pitch/yaw already in
    # pixel), and omega_z=roll_rate (roll is NOT captured by velocity direction;
    # it causes in-plane image rotation).  This means LOSComputer only
    # compensates for the roll component.
    #
    # For STAR RENDERING: use the full (omega_x, omega_y, omega_z) to shift stars
    # so that KLT on stars is honest.
    # ------------------------------------------------------------------
    att_now = q_state.attitude_rad.copy()  # [roll, pitch, yaw]

    if ps.prev_attitude_rad is not None and dt_vision > 0.0:
        att_prev = ps.prev_attitude_rad
        omega_x_full = (att_now[1] - att_prev[1]) / dt_vision   # pitch rate
        omega_y_full = (att_now[2] - att_prev[2]) / dt_vision   # yaw rate
        omega_z_full = (att_now[0] - att_prev[0]) / dt_vision   # roll rate
    else:
        omega_x_full = omega_y_full = omega_z_full = 0.0

    ps.prev_attitude_rad = att_now

    # Full ego for star rendering (apply to stars so they move with body rotation)
    ego_for_stars = gyro_derotation(
        omega_xyz_radps=(omega_x_full, omega_y_full, omega_z_full),
        dt=max(dt_vision, 1e-4),
        intrinsics=intr,
    )

    # Roll-only ego for LOSComputer (avoid double-compensating pitch/yaw)
    # Only omega_z (roll) causes in-plane image rotation not captured by the
    # velocity-aligned boresight.
    #
    # DESIGN NOTE — ego_for_los.shift_px is intentionally (0, 0):
    #   The shift_px field of an EgoEstimate encodes the TRANSLATIONAL shift of
    #   the image principal point due to pitching/yawing body motion.  Here we
    #   pass omega_x=0, omega_y=0, so gyro_derotation computes zero translational
    #   shift — only the roll_rad field is non-zero.
    #
    #   This is CORRECT for a velocity-aligned boresight: pitch and yaw body
    #   rates rotate the boresight and are already captured by the changing target
    #   pixel position (compute_bearing_from_states uses the velocity direction).
    #   Passing a non-zero shift_px for pitch/yaw would cause LOSComputer to
    #   SUBTRACT the ego shift from the centroid, double-compensating those axes.
    #
    #   CAVEAT — OFF-BORESIGHT CAMERA MOUNT:
    #   If the camera is mounted off-boresight (e.g., canted forward by 5 deg for
    #   a downward-looking configuration), this shortcut breaks down.  In that case
    #   the body pitch/yaw rates DO cause a translational shift of the camera image
    #   that is NOT captured by the velocity-direction change.  The full omega_xyz
    #   vector must be passed to gyro_derotation and ego_for_los, and
    #   compute_bearing_from_states must use the true camera boresight (not the
    #   velocity direction) as its reference frame.
    #   THIS MUST BE REASSESSED before any off-boresight mount is fielded.
    # Cam<->IMU / gyro scale-factor residual: the seeker's de-rotation uses an erroneous gyro
    # reading (omega_z_full * (1+err)), while the world (stars, above) rotated by the TRUE rate.
    # The mismatch leaves a residual in-plane rotation the LOSComputer cannot remove -> a correlated
    # LOS-rate error, the dominant strapdown defect.  err=0 -> bit-identical.
    omega_z_los = omega_z_full * (1.0 + ps.gyro_scale_error)
    ego_for_los = gyro_derotation(
        omega_xyz_radps=(0.0, 0.0, omega_z_los),
        dt=max(dt_vision, 1e-4),
        intrinsics=intr,
    )

    # Update cumulative ego for star placement in render (full rotation)
    ps.cum_ego_dx += ego_for_stars.shift_px[0]
    ps.cum_ego_dy += ego_for_stars.shift_px[1]
    ps.cum_roll_rad += ego_for_stars.roll_rad

    # ------------------------------------------------------------------
    # STEP 5: Render thermal frame
    #
    # cam_temp_additive: small sinusoidal to exercise adaptive threshold re-base
    # FFC freeze is NOT injected here (would need FFC-aware guidance coast path).
    # The REACQUIRE path is exercised by the off-FOV scenario instead.
    # ------------------------------------------------------------------
    cam_temp_additive = 30.0 * math.sin(2.0 * math.pi * t_sim / 5.0)
    # Range-dependent target size: silhouette major (~2.3548*sigma) tracks f_px*span/range, with the PSF
    # floor keeping a far target a point source.  None -> fixed psf_sigma_px blob (bit-identical legacy).
    if ps.target_span_m is not None:
        sigma_geom = intr.f_px * ps.target_span_m / (2.3548 * max(range_m, 1.0))
        render_sigma = math.hypot(ps.psf_sigma_px, sigma_geom)
        star_sigma = max(0.8, ps.psf_sigma_px * 0.8)   # stars stay a fixed PSF feature, not target-range
    else:
        render_sigma = ps.psf_sigma_px
        star_sigma = None                               # legacy derivation inside _render_one_frame
    ps.last_rendered_sigma_px = render_sigma
    frame_u16 = _render_one_frame(
        target_px=px_true,
        target_py=py_true,
        target_in_fov=target_in_fov,
        cum_ego_dx=ps.cum_ego_dx,
        cum_ego_dy=ps.cum_ego_dy,
        intrinsics=intr,
        star_positions=ps.star_positions,
        rng=ps.rng,
        target_sigma_px=render_sigma,
        star_sigma_px=star_sigma,
        cam_temp_additive=cam_temp_additive,
    )
    ps.frame_count += 1

    # ------------------------------------------------------------------
    # STEP 6: S1 detect
    # ------------------------------------------------------------------
    blobs, ps.threshold_state = detect_frame(
        frame_u16,
        cam_temp_c=25.0 + cam_temp_additive * 0.1,
        ffc_state="READY",
        threshold_state=ps.threshold_state,
        frame_id=frame_id,
        t_capture_ns=int(t_sim * 1e9),
    )

    obs = TargetObservation(
        frame_id=frame_id,
        t_capture_ns=int(t_sim * 1e9),
        cam_temp_c=25.0,
        ffc_state="READY",
        blobs=blobs,
        threshold_baseline_counts=ps.threshold_state.threshold_counts,
        detection_budget_ms=0.0,
    )

    # ------------------------------------------------------------------
    # STEP 7: Tracker update
    # ------------------------------------------------------------------
    snap = ps.tracker.update(obs)
    ps.lock_states_seen.add(snap.tracking_state)

    # When target is off-FOV and not detected, tracker will coast/reacquire.
    # In coast state, we hold the last valid LOS from the pipeline.
    if snap.associated_blob is None:
        # No detection — guidance will hold the last-valid LOS (coasting)
        return None, ps.last_imm_est, False

    # ------------------------------------------------------------------
    # STEP 8: S2 LOS computation (ego-compensated)
    # ------------------------------------------------------------------
    centroid_px: tuple[float, float] = snap.centroid_px
    # Stash the REAL detected blob area so the harness can drive looming/tau from what the sensor
    # actually saw (honest), instead of the true-range-derived area (a tautology).
    ps.last_detected_area_px = float(snap.associated_blob.area_px)
    # Robust silhouette major axis (top-hat-immune) for subtense ranging, when a physical span is set.
    ps.last_silhouette_major_px = None
    if ps.target_span_m is not None:
        _sil = silhouette_extent(frame_u16, centroid_px[0], centroid_px[1],
                                 float(snap.associated_blob.peak_counts))
        if _sil.resolved:
            ps.last_silhouette_major_px = _sil.major_px

    los_obs = ps.los_computer.update(
        centroid_px=centroid_px,
        ego=ego_for_los,          # roll-only ego (pitch/yaw already in pixel)
        dt=max(dt_vision, 1e-4),
        frame_id=frame_id,
        t_capture_ns=int(t_sim * 1e9),
    )

    # ------------------------------------------------------------------
    # STEP 9: IMM filter update
    # ------------------------------------------------------------------
    imm_est = ps.imm.update(los_obs, dt=max(dt_vision, 1e-4))

    # Cache for hold-on-drop
    ps.last_los_obs = los_obs
    ps.last_imm_est = imm_est

    return los_obs, imm_est, True
