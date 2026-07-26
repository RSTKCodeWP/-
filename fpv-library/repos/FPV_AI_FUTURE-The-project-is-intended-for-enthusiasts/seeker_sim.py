"""S2 ego-motion simulator: wraps ThermalSimulator with full body-rotation model.

WHAT THIS ADDS OVER thermal_sim.py
------------------------------------
thermal_sim.ThermalSimulator supports a ``ego_drift_fn`` that provides a
translational image shift.  That is sufficient for testing S1 (detection) but
not for S2 (ego-motion compensation), which needs:

    (1) A full body angular-rate time-series omega(t) = [ox, oy, oz] in rad/s,
        modelling FPV-realistic 100–1000 °/s roll/pitch/yaw.
    (2) The resulting image shift applied as a rotation (not just translation)
        — correctly captures both translation AND in-plane roll.
    (3) Ground truth:
          - true_target_bearing_rad: (az, el) of the target in body frame
          - true_lambda_dot_radps: (daz/dt, del/dt) — the TARGET's actual LOS
            rate in body frame (what guidance wants)
          - true_omega_radps: (ox, oy, oz) at each frame
    (4) Stressor injection:
          - cam_imu_sync_error_s: gyro samples offset by N ms (sign: positive =
            gyro lags camera; negative = gyro leads).
          - soft_mount_gain: scalar < 1 that attenuates the camera's rotation
            relative to the gyro-mounted rigid body.  Models a camera on
            vibration-isolation gel that moves less than the rigid frame.
            soft_mount_gain = 1.0 means rigid (ideal); 0.8 means camera only
            sees 80% of the body rotation.
          - soft_mount_lag_frames: integer — additional lag (frames) of soft-mount
            filtering on top of the gain attenuation.

COORDINATE CONVENTIONS
------------------------
Body-frame angular rate omega = [omega_x, omega_y, omega_z] (rad/s):
    omega_x — roll rate  (right-hand rule, body +X rightward)
    omega_y — pitch rate (right-hand rule, body +Y upward)
    omega_z — yaw   rate (right-hand rule, body +Z out-of-boresight)

Image shift from rotation (small-angle, from egomotion.py convention):
    dx_px = -f · omega_y · dt   (positive omega_y → scene moves left → dx < 0)
    dy_px = -f · omega_x · dt   (positive omega_x → scene moves up → dy < 0 in image)
    roll  =  omega_z · dt       (positive omega_z → scene rotates CCW in math coords)

TRUE TARGET BEARING AND LOS-RATE
----------------------------------
The target has an absolute world position defined by an initial bearing
(az0, el0) in body frame at t=0.  The body then ROTATES, so the target's
apparent bearing in the image changes due to BOTH:
  (a) the target's own motion (true angular velocity lambda_dot)
  (b) the body's rotation (omega)

We model the target position as a WORLD-FIXED point at (az0_world, el0_world).
The body frame rotates, so the target's bearing IN BODY FRAME changes.

For small angles and small dt, the body-frame bearing update per frame is:
    az_{k+1} = az_k - omega_z · dt · (...) + lambda_dot_az · dt
    el_{k+1} = el_k + omega_y · dt · (...) - omega_x · dt · (...) + lambda_dot_el · dt

For simplicity we implement the exact rotation-then-add approach:
    (a) Start with target at fixed world bearing (az_world, el_world).
    (b) The body frame rotates by omega · dt per step.  Equivalently, the
        target's body-frame bearing changes by -(omega in image plane) per frame:
            d(az)/dt|ego = -omega_z · cos(az) - omega_y · sin(az) ... (full formula)
        For small angles: d(az)/dt|ego ≈ -omega_y, d(el)/dt|ego ≈ omega_x
    (c) The target ALSO has its own true LOS-rate lambda_dot in world frame:
            d(az)/dt|true_target = lambda_dot_az
    (d) Total body-frame bearing rate = lambda_dot - ego_contribution

For a STATIONARY target in world frame (lambda_dot = 0), the bearing change is
purely due to ego rotation.  The test "ego rejection gate" sets lambda_dot = 0
and verifies that the S2 pipeline recovers near-zero lambda_dot_estimated.

IMPLEMENTATION APPROACH
------------------------
Rather than tracking 3-D rotations (which requires quaternion integration for
large angles), we track the target's position in image pixels using the same
small-angle pinhole model the real system uses.  This keeps the test geometry
self-consistent with the production code.

For each frame:
    target_px_world = (cx + f·tan(az_world), cy - f·tan(el_world))   [fixed world]
    image shifts by ego_shift_px = (-f·omega_y·dt, -f·omega_x·dt)
    target_px_in_camera = target_px_world + cumulative_ego_shift
                         + lambda_dot · f · dt   (target's own motion in px)

The TRUE body-frame bearing is:
    az = atan2(target_px_in_camera_x - cx, f)
    el = atan2(-(target_px_in_camera_y - cy), f)

The TRUE lambda_dot is the rate of change of these bearings due to the target's
OWN motion (not counting ego), which for a world-stationary target is exactly
the NEGATIVE of the ego bearing rate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import numpy.typing as npt

from .thermal_sim import ThermalSimulator, ThermalSceneConfig, GroundTruth
from .geometry import CameraIntrinsics, pixel_to_bearing


# ---------------------------------------------------------------------------
# Ego-motion time series
# ---------------------------------------------------------------------------

# A function from frame_id -> omega (omega_x, omega_y, omega_z) in rad/s
OmegaFn = Callable[[int], tuple[float, float, float]]


def fpv_roll_dominant_omega(
    *,
    roll_rate_radps: float = 5.0,    # ≈ 286 °/s
    pitch_rate_radps: float = 1.5,
    yaw_rate_radps: float = 1.0,
    period_frames: float = 60.0,
) -> OmegaFn:
    """FPV-like sinusoidal rotation: roll-dominant, all three axes active.

    Convention (matches egomotion.py §3.2):
        omega_x — pitch rate  (right-hand rule about body +X = rightward)
        omega_y — yaw rate    (right-hand rule about body +Y = upward)
        omega_z — ROLL rate   (right-hand rule about body +Z = out-of-boresight)

    FIX (2026-06-17): previously roll_rate_radps was driving omega_y (yaw),
    which is pitch-like in image space (horizontal scene shift).  Real FPV roll
    is in-plane image rotation about the boresight = omega_z.  Now roll_rate_radps
    correctly drives omega_z (dominant), with pitch/yaw on omega_x/omega_y at
    the lower rates supplied.

    Parameters
    ----------
    roll_rate_radps:
        Peak ROLL angular rate (rad/s) — drives omega_z (boresight axis).
        100-1000 °/s → 1.74–17.5 rad/s for FPV-realistic scenarios.
    pitch_rate_radps:
        Peak pitch rate (rad/s) — drives omega_x.
    yaw_rate_radps:
        Peak yaw rate (rad/s) — drives omega_y.
    period_frames:
        Period of the sinusoidal rotation in frames.
    """
    def _fn(frame_id: int) -> tuple[float, float, float]:
        phase = 2.0 * math.pi * frame_id / period_frames
        ox = pitch_rate_radps * math.sin(phase)           # pitch (omega_x)
        oy = yaw_rate_radps  * math.cos(phase * 0.7 + 1) # yaw   (omega_y)
        oz = roll_rate_radps * math.cos(phase * 1.3)      # ROLL  (omega_z) — dominant
        return ox, oy, oz

    return _fn


def constant_omega(ox: float, oy: float, oz: float) -> OmegaFn:
    """Constant angular rate (useful for simple tests)."""
    def _fn(_frame_id: int) -> tuple[float, float, float]:
        return ox, oy, oz
    return _fn


# ---------------------------------------------------------------------------
# S2 ground truth record
# ---------------------------------------------------------------------------

@dataclass
class S2GroundTruth:
    """Per-frame ground truth for S2 validation.

    Attributes
    ----------
    frame_id:
        Zero-based frame index.
    target_centroid_px:
        True sub-pixel centroid of the target IN THE CAMERA IMAGE (includes
        both target motion and ego shift applied to the image).
    true_az_rad, true_el_rad:
        True body-frame bearing of the target at this frame.
    true_az_rate_radps, true_el_rate_radps:
        TRUE target LOS-rate in body frame (target's OWN angular motion).
        For a world-stationary target, this is 0.
    true_omega_radps:
        True body angular rate (omega_x, omega_y, omega_z) at this frame.
        This is the CAMERA-frame angular rate (may differ from the rigid-body
        gyro rate when soft_mount_gain < 1).
    gyro_omega_radps:
        Angular rate as reported by the gyro (with time-sync error and
        soft-mount differences applied).  This is what the S2 pipeline sees.
    ego_shift_px:
        True image shift due to ego rotation this frame (dx, dy).
    ffc_state:
        'READY' | 'FREEZE' | 'RECOVERING'.
    cam_temp_c:
        Camera housing temperature (from the underlying ThermalSim).
    is_target_visible:
        False during FFC freeze.
    cam_imu_sync_error_s:
        The applied cam↔IMU sync error (seconds).
    soft_mount_gain:
        The applied soft-mount gain (1.0 = rigid).
    """

    frame_id: int
    target_centroid_px: tuple[float, float]
    true_az_rad: float
    true_el_rad: float
    true_az_rate_radps: float
    true_el_rate_radps: float
    true_omega_radps: tuple[float, float, float]
    gyro_omega_radps: tuple[float, float, float]
    ego_shift_px: tuple[float, float]
    ffc_state: str
    cam_temp_c: float
    is_target_visible: bool
    cam_imu_sync_error_s: float = 0.0
    soft_mount_gain: float = 1.0


# ---------------------------------------------------------------------------
# S2 simulator
# ---------------------------------------------------------------------------

@dataclass
class SeekerSimConfig:
    """Configuration for the S2 seeker simulator.

    Attributes
    ----------
    thermal_cfg:
        Underlying thermal scene config (passed to ThermalSimulator).
    intrinsics:
        Camera intrinsics (focal length, principal point).
    omega_fn:
        Body angular rate time series: frame_id → (ox, oy, oz) rad/s.
    fps:
        Camera frame rate (Hz).  Used to convert frame_id to time.
    target_lambda_dot_az_radps:
        True target LOS angular rate in az (rad/s).  0 = world-stationary.
    target_lambda_dot_el_radps:
        True target LOS angular rate in el (rad/s).  0 = world-stationary.
    target_az0_body_rad:
        Initial azimuth bearing of the target in body frame (radians).
    target_el0_body_rad:
        Initial elevation bearing of the target in body frame (radians).
    cam_imu_sync_error_s:
        Cam↔IMU time-sync error (seconds).  Positive = gyro lags behind camera.
        The gyro omega returned in S2GroundTruth.gyro_omega is sampled at
        time t - sync_error instead of time t.
    soft_mount_gain:
        Camera sees soft_mount_gain × body rotation (1.0 = rigid, ideal).
        The camera image shifts by soft_mount_gain × omega; the gyro reports
        omega (full body rate, unaffected).  This creates a mismatch.
    soft_mount_lag_frames:
        Additional lag of the soft-mount filtering (integer frames).
        The camera's effective omega is further delayed by this many frames.
    seed:
        Override random seed (None = use thermal_cfg.seed).
    """

    thermal_cfg: ThermalSceneConfig = field(default_factory=ThermalSceneConfig)
    intrinsics: CameraIntrinsics = field(
        default_factory=lambda: CameraIntrinsics(
            f_px=640.0,  # default: small sensor, ~HFOV 53°
            cx=128.0,
            cy=96.0,
            width=256,
            height=192,
        )
    )
    omega_fn: OmegaFn = field(default_factory=fpv_roll_dominant_omega)
    fps: float = 60.0

    # True target LOS-rate (independent of ego)
    target_lambda_dot_az_radps: float = 0.0
    target_lambda_dot_el_radps: float = 0.0

    # Initial target bearing in body frame
    target_az0_body_rad: float = 0.02    # ~1.1°, slightly off-boresight
    target_el0_body_rad: float = 0.01

    # Stressors
    cam_imu_sync_error_s: float = 0.0
    soft_mount_gain: float = 1.0
    soft_mount_lag_frames: int = 0


class SeekerSim:
    """S2 ego-motion simulator.

    Generates frames with body rotation applied, together with full ground truth
    for validating S2 ego-compensation.

    Usage
    -----
    ::

        cfg = SeekerSimConfig(
            thermal_cfg=ThermalSceneConfig(width=256, height=192, seed=42),
            intrinsics=CameraIntrinsics(f_px=640, cx=128, cy=96, width=256, height=192),
            omega_fn=fpv_roll_dominant_omega(roll_rate_radps=10.0),
            fps=60.0,
        )
        sim = SeekerSim(cfg)
        for frame_u16, gt_s2 in sim.generate(n_frames=300):
            ...
    """

    def __init__(self, config: SeekerSimConfig | None = None) -> None:
        self._cfg = config or SeekerSimConfig()
        cfg = self._cfg

        # Pre-generate the omega time-series for the full run (needed for sync-error lookup)
        # We generate a buffer of 600 frames; callers can request up to that.
        self._max_frames = 600
        self._omega_table: list[tuple[float, float, float]] = [
            cfg.omega_fn(i) for i in range(self._max_frames + 100)
        ]

    def generate(
        self, n_frames: int
    ) -> list[tuple[npt.NDArray[np.uint16], S2GroundTruth]]:
        """Generate ``n_frames`` frames with ego-motion applied.

        Returns
        -------
        list of (frame_u16, S2GroundTruth)
        """
        cfg = self._cfg
        dt = 1.0 / cfg.fps
        intr = cfg.intrinsics
        f = intr.f_px
        cx, cy = intr.cx, intr.cy

        # Accumulate the cumulative ego shift in image pixels.
        # This represents the total translation due to rotation since t=0.
        cumulative_ego_dx: float = 0.0
        cumulative_ego_dy: float = 0.0

        # Cumulative roll (in-plane rotation) accumulated since t=0.
        # Roll rotates world-fixed points about the principal point.
        cumulative_roll_rad: float = 0.0

        # Initial target position in image (at body-frame bearing az0, el0)
        # pixel_to_bearing is the inverse of:
        #   px = cx + f * tan(az)
        #   py = cy - f * tan(el)
        target_px0 = cx + f * math.tan(cfg.target_az0_body_rad)
        target_py0 = cy - f * math.tan(cfg.target_el0_body_rad)

        # Soft-mount omega history for lag simulation.
        # omega_history is a FIFO buffer of length (soft_mount_lag_frames).
        # When lag=0, cam_omega = current omega (no history needed).
        # When lag=N, cam_omega = omega from N frames ago.
        # We use a deque; new values are appended to the right.
        from collections import deque
        omega_history: deque[tuple[float, float, float]] = deque(
            maxlen=max(1, cfg.soft_mount_lag_frames + 1)
        )
        # Pre-fill with zeros to represent "before time 0"
        for _ in range(cfg.soft_mount_lag_frames):
            omega_history.append((0.0, 0.0, 0.0))

        results: list[tuple[npt.NDArray[np.uint16], S2GroundTruth]] = []

        for frame_id in range(n_frames):
            t_frame = frame_id * dt

            # ── True camera omega at this frame ───────────────────────────
            true_omega = self._omega_table[frame_id]
            ox, oy, oz = true_omega

            # Camera sees soft_mount_gain × omega (accounts for damping mount)
            cam_ox = ox * cfg.soft_mount_gain
            cam_oy = oy * cfg.soft_mount_gain
            cam_oz = oz * cfg.soft_mount_gain

            # Apply soft-mount lag:
            # With lag=0: cam_omega_lagged = current omega immediately.
            # With lag=N: cam_omega_lagged = omega from N frames ago.
            if cfg.soft_mount_lag_frames == 0:
                cam_ox_eff, cam_oy_eff, cam_oz_eff = cam_ox, cam_oy, cam_oz
            else:
                # Oldest entry in the deque is the lagged value
                cam_ox_eff, cam_oy_eff, cam_oz_eff = omega_history[0]
                omega_history.append((cam_ox, cam_oy, cam_oz))

            # ── True ego shift this frame (camera rotation) ────────────────
            # Translation terms from pitch (cam_ox_eff) and yaw (cam_oy_eff):
            #   dx_px = -f · omega_y · dt   (positive omega_y → scene shifts left)
            #   dy_px = -f · omega_x · dt   (positive omega_x → scene shifts up)
            ego_dx = -f * cam_oy_eff * dt
            ego_dy = -f * cam_ox_eff * dt

            # Roll contribution (omega_z = cam_oz_eff): in-plane rotation by dtheta.
            # Accumulated as cumulative_roll_rad; applied to target pixel below.
            dtheta = cam_oz_eff * dt  # positive = CCW in math convention

            cumulative_ego_dx += ego_dx
            cumulative_ego_dy += ego_dy
            cumulative_roll_rad += dtheta

            # ── Target's own motion (world LOS-rate, independent of ego) ──
            # Accumulate target's own angular motion
            target_own_az = cfg.target_az0_body_rad + cfg.target_lambda_dot_az_radps * t_frame
            target_own_el = cfg.target_el0_body_rad + cfg.target_lambda_dot_el_radps * t_frame

            # Target's pixel position from its own motion (no ego)
            target_own_px = cx + f * math.tan(target_own_az)
            target_own_py = cy - f * math.tan(target_own_el)

            # In the CAMERA frame, the target appears at:
            #   own motion position + cumulative translation ego shift
            #                       + cumulative roll rotation (about principal point)
            #
            # Roll rotation: a CCW rotation of the body about boresight (omega_z > 0)
            # rotates the SCENE clockwise in the image.  A world-fixed point at
            # image offset (dx_w, dy_w) = (target_own_px - cx, target_own_py - cy)
            # after roll angle theta appears at:
            #   dx_rot =  dx_w * cos(theta) + dy_w * sin(theta)   ← CW rotation of scene
            #   dy_rot = -dx_w * sin(theta) + dy_w * cos(theta)
            # (Body +Z out of boresight, positive omega_z → body rotates CCW →
            #  scene appears to rotate CW in image-y-down convention.)
            #
            # Shift due to roll alone: (dx_rot - dx_w, dy_rot - dy_w)
            #   ≈ (dy_w * theta, -dx_w * theta)  for small theta
            #   = (+dtheta * dy_w, -dtheta * dx_w)
            # Note sign: this is +theta * dy_w, -theta * dx_w  (CW scene rotation).
            dx_w = target_own_px - cx
            dy_w = target_own_py - cy
            theta = cumulative_roll_rad
            # Apply full rotation (not small-angle) for robustness:
            target_cam_px = cx + (dx_w * math.cos(theta) + dy_w * math.sin(theta)) + cumulative_ego_dx
            target_cam_py = cy + (-dx_w * math.sin(theta) + dy_w * math.cos(theta)) + cumulative_ego_dy

            # ── True body-frame bearing ────────────────────────────────────
            true_az, true_el = pixel_to_bearing(target_cam_px, target_cam_py, intr)

            # ── True target LOS-rate (target's OWN motion in body frame) ──
            # This is what guidance wants to null.
            # For a world-stationary target (lambda_dot = 0), the body-frame
            # bearing changes due to ego alone → true_lambda_dot = 0.
            true_az_rate = cfg.target_lambda_dot_az_radps
            true_el_rate = cfg.target_lambda_dot_el_radps

            # ── Gyro reading (with sync error and soft-mount differences) ─
            # Sync error: gyro samples are from time (t - sync_error).
            # Positive sync_error means the gyro LAGS the camera by that many seconds.
            #
            # sync_frame_offset = sync_error_s * fps  (fractional frames)
            # We want omega at time (frame_id - sync_frame_offset):
            #   floor_idx = floor(frame_id - sync_frame_offset)
            #   frac = fractional part beyond floor_idx
            #   omega = omega[floor_idx] + frac * (omega[floor_idx+1] - omega[floor_idx])
            #
            # Example: frame_id=5, sync_frame_offset=0.06
            #   floor_idx = floor(5 - 0.06) = floor(4.94) = 4
            #   frac = 4.94 - 4 = 0.94
            #   omega = omega[4] + 0.94*(omega[5] - omega[4])  ← 94% toward frame 5
            # This correctly gives omega at time 4.94, which is 0.06 frames before frame 5.
            sync_frame_offset = cfg.cam_imu_sync_error_s * cfg.fps
            t_sample = frame_id - sync_frame_offset   # fractional frame time to sample
            t_sample = max(0.0, t_sample)
            floor_idx = int(math.floor(t_sample))
            frac = t_sample - floor_idx   # in [0, 1)

            omega_floor = self._omega_table[min(floor_idx, len(self._omega_table) - 1)]
            if frac > 1e-9 and floor_idx + 1 < len(self._omega_table):
                omega_ceil = self._omega_table[floor_idx + 1]
                gyro_ox = omega_floor[0] + frac * (omega_ceil[0] - omega_floor[0])
                gyro_oy = omega_floor[1] + frac * (omega_ceil[1] - omega_floor[1])
                gyro_oz = omega_floor[2] + frac * (omega_ceil[2] - omega_floor[2])
            else:
                gyro_ox, gyro_oy, gyro_oz = omega_floor

            # Soft-mount: gyro reports FULL body rate (not attenuated)
            # — gyro is rigidly mounted to body, camera is soft-mounted
            gyro_omega: tuple[float, float, float] = (gyro_ox, gyro_oy, gyro_oz)

            # ── Build the ego_drift_fn for ThermalSimulator ────────────────
            # We pass the cumulative image shift as the ego drift for this frame.
            # But ThermalSimulator generates all frames at once, so we build
            # the thermal frame directly using the cumulative shift.

            # ── Render the thermal frame ───────────────────────────────────
            # Pass cumulative ego shift so world-fixed stars are correctly placed.
            thermal_frame, thermal_gt = self._render_thermal_frame(
                frame_id=frame_id,
                target_cam_px=target_cam_px,
                target_cam_py=target_cam_py,
                cum_ego_dx=cumulative_ego_dx,
                cum_ego_dy=cumulative_ego_dy,
            )

            gt_s2 = S2GroundTruth(
                frame_id=frame_id,
                target_centroid_px=(target_cam_px, target_cam_py),
                true_az_rad=float(true_az),
                true_el_rad=float(true_el),
                true_az_rate_radps=float(true_az_rate),
                true_el_rate_radps=float(true_el_rate),
                true_omega_radps=(float(cam_ox_eff), float(cam_oy_eff), float(cam_oz_eff)),
                gyro_omega_radps=gyro_omega,
                ego_shift_px=(float(ego_dx), float(ego_dy)),
                ffc_state=thermal_gt.ffc_state,
                cam_temp_c=thermal_gt.cam_temp_c,
                is_target_visible=thermal_gt.is_target_visible,
                cam_imu_sync_error_s=cfg.cam_imu_sync_error_s,
                soft_mount_gain=cfg.soft_mount_gain,
            )

            results.append((thermal_frame, gt_s2))

        return results

    def _render_thermal_frame(
        self,
        frame_id: int,
        target_cam_px: float,
        target_cam_py: float,
        cum_ego_dx: float = 0.0,
        cum_ego_dy: float = 0.0,
    ) -> tuple[npt.NDArray[np.uint16], GroundTruth]:
        """Render one thermal frame with the target at the given camera position.

        Parameters
        ----------
        cum_ego_dx, cum_ego_dy:
            Cumulative ego shift (pixels) applied to WORLD-FIXED features such as
            stars.  Stars are fixed in the world, so when the camera rotates by the
            cumulative ego shift, world-fixed features appear to translate in the
            image by the SAME cumulative ego shift.

        FIX (2026-06-17, Fix 3): previously stars were rendered at their initial
        pixel positions regardless of ego rotation (circular: KLT on starred scenes
        saw zero motion because stars didn't move with ego).  Now each star is
        placed at (sx + cum_ego_dx, sy + cum_ego_dy), matching the physics: a
        world-fixed feature appears to shift in the image by the cumulative ego
        shift just as the target does.
        """
        cfg = self._cfg
        tcfg = cfg.thermal_cfg
        intr = cfg.intrinsics

        H, W = intr.height, intr.width
        rng = np.random.default_rng(tcfg.seed if tcfg.seed is not None else 0)
        # Advance RNG to frame_id (use fixed per-frame seed for reproducibility)
        rng = np.random.default_rng((tcfg.seed or 0) + frame_id)

        # Cold sky background
        bg_mean = float(tcfg.sky_base_counts)
        yy = np.linspace(0.0, 1.0, H)[:, np.newaxis]
        sky_grad = tcfg.sky_gradient_amplitude * (0.6 * yy)
        sky_grad = np.broadcast_to(sky_grad, (H, W)).copy()
        noise = rng.normal(0.0, tcfg.read_noise_sigma, size=(H, W))
        frame_f = np.full((H, W), bg_mean, dtype=np.float64) + sky_grad + noise

        # Target hot spot
        yy_idx = np.arange(H, dtype=np.float64)[:, np.newaxis]
        xx_idx = np.arange(W, dtype=np.float64)[np.newaxis, :]
        target_psf = _gaussian2d(
            xx_idx, yy_idx,
            target_cam_px, target_cam_py,
            tcfg.target_sigma_px, tcfg.target_peak_above_bg,
        )
        frame_f += target_psf

        # Stars: world-fixed features appear to shift in the image by the cumulative
        # ego shift.  Apply (cum_ego_dx, cum_ego_dy) to each star's reference position
        # so that KLT correctly observes the ego-induced motion of background features.
        star_peak = tcfg.target_peak_above_bg * tcfg.star_peak_fraction
        star_sigma = max(0.8, tcfg.target_sigma_px * 0.8)
        for sx, sy in _get_star_positions(tcfg, H, W):
            # Star apparent position = world reference position + cumulative ego shift
            star_img_x = sx + cum_ego_dx
            star_img_y = sy + cum_ego_dy
            frame_f += _gaussian2d(xx_idx, yy_idx, star_img_x, star_img_y, star_sigma, star_peak)

        # FFC: simplified (no freeze simulation in this thin wrapper)
        ffc_state = "READY"
        cam_temp_c = tcfg.cam_temp_start_c

        frame_u16 = np.clip(frame_f, 0.0, 16383.0).astype(np.uint16)

        gt = GroundTruth(
            frame_id=frame_id,
            target_centroid_px=(target_cam_px, target_cam_py),
            target_area_px=math.pi * (2.355 * tcfg.target_sigma_px / 2.0) ** 2,
            ffc_state=ffc_state,
            cam_temp_c=cam_temp_c,
            star_positions_px=_get_star_positions(tcfg, H, W),
            is_target_visible=True,
        )
        return frame_u16, gt


# ---------------------------------------------------------------------------
# Star position cache (deterministic from scene config seed)
# ---------------------------------------------------------------------------

_star_cache: dict[int, list[tuple[float, float]]] = {}


def _get_star_positions(
    cfg: ThermalSceneConfig,
    H: int,
    W: int,
) -> list[tuple[float, float]]:
    """Return fixed star positions for the given scene config (cached)."""
    cache_key = id(cfg)
    if cache_key not in _star_cache:
        rng = np.random.default_rng(cfg.seed if cfg.seed is not None else 0)
        margin = 20
        xs = rng.uniform(margin, W - margin, size=cfg.n_stars).tolist()
        ys = rng.uniform(margin, H - margin, size=cfg.n_stars).tolist()
        _star_cache[cache_key] = list(zip(xs, ys))
    return _star_cache[cache_key]


# ---------------------------------------------------------------------------
# Utility (mirrors thermal_sim.py to avoid circular import)
# ---------------------------------------------------------------------------

def _gaussian2d(
    xx: npt.NDArray[np.float64],
    yy: npt.NDArray[np.float64],
    cx: float,
    cy: float,
    sigma: float,
    peak: float,
) -> npt.NDArray[np.float64]:
    """2-D circularly-symmetric Gaussian PSF."""
    dx = xx - cx
    dy = yy - cy
    r2 = dx * dx + dy * dy
    return peak * np.exp(-r2 / (2.0 * sigma * sigma))
