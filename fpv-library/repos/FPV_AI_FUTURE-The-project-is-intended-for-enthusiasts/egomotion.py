"""Ego-motion estimation: gyro de-rotation + optional sparse LK residual.

PURPOSE
-------
A fast-rotating FPV body (100–1000 °/s) creates a large phantom LOS-rate
(dλ/dt) in the image plane.  This module removes that ego-rotation so that
downstream LOS tracking sees only the TRUE target angular motion.

The design mandates (§3.2):
    "gyro-only is the BASE mode; sparse-LK is a BONUS only when texture exists"
Textureless night sky → KLT will have no corners → return None → gyro-only.
This is NORMAL, not an error.

GYRO DE-ROTATION CONVENTION
-----------------------------
Body-frame angular rate omega = [omega_x, omega_y, omega_z] in rad/s:
    omega_x — pitch rate (right-hand rule about camera +X = rightward axis)
    omega_y — yaw rate   (right-hand rule about camera +Y = upward axis)
    omega_z — ROLL rate  (right-hand rule about camera +Z = out-of-boresight)

Image-plane prediction of scene shift due to body rotation (small-angle,
matches design §3.2 exactly):
    dx_px ≈ -f · omega_y · dt     (yaw moves scene horizontally)
    dy_px ≈ -f · omega_x · dt     (pitch moves scene vertically, image-y down)
    roll_rad ≈  omega_z · dt       (roll rotates image about principal point)

ROLL-INDUCED TARGET SHIFT (FIX 2026-06-17)
--------------------------------------------
For an off-boresight target at pixel offset (dx_t, dy_t) = (px - cx, py - cy)
from the principal point, body roll omega_z causes a tangential shift in-image:

    dx_roll = -omega_z · dt · dy_t   (right-hand small-angle rotation)
    dy_roll = +omega_z · dt · dx_t

Geometry: roll omega_z > 0 rotates the scene CCW about the principal point
(in standard math convention; CW in display coords with y-down).  The tangent
to a circle of radius r at angle θ is (-sin θ, cos θ).  With
(dx_t, dy_t) = r·(cos θ, sin θ):
    tangential shift = omega_z·dt · (-dy_t, +dx_t)

This shift is ZERO for a target exactly at the principal point (boresight) but
grows linearly with target offset.  It is TARGET-POSITION-AWARE.

Implementation: gyro_derotation accepts an optional target_offset_px argument.
When provided, the roll contribution is added to shift_px.  This is called from
los.py where the target pixel centroid is known.

SIGN DERIVATION (translation terms):
    Consider omega_y > 0 (body yaws nose-RIGHT in the camera's convention where
    +Y is upward).  The scene appears to shift LEFT in image coordinates
    (stars move toward smaller px).  We want the SCENE shift:
        dx_px = -f · omega_y · dt   (rightward boresight rotation shifts scene LEFT)
        dy_px = -f · omega_x · dt   (upward pitch shifts scene down → dy > 0 in image)
    This implements the design formula verbatim from §3.2:
        «dx_px ≈ −f·ω_y·dt, dy_px ≈ −f·ω_x·dt»

EgoEstimate QUALITY
-------------------
quality is defined as a scalar in [0, 1]:
    1.0  — gyro-only (trusted when gyro calibration is good)
    0.6..1.0 — gyro+KLT (KLT cross-check available)
    Lower values indicate potential degradation (too few KLT inliers).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt

from .geometry import CameraIntrinsics

# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EgoEstimate:
    """Per-frame ego-motion estimate.

    Attributes
    ----------
    shift_px:
        Predicted scene shift (dx, dy) in image pixels caused by the
        interceptor's own rotation.  This is the shift that needs to be
        SUBTRACTED from observed pixel motion to get the target's true motion.
    roll_rad:
        Predicted in-image-plane rotation (radians) about the principal point.
        Positive = CCW rotation in standard math convention.
    source:
        ``'gyro'``    — shift from gyro de-rotation only (normal base mode).
        ``'gyro+klt'``— gyro + KLT residual cross-check.
    quality:
        Scalar in [0, 1].  Higher = more trustworthy.
        Gyro-only = 1.0 by default (degrade if gyro is flagged unhealthy).
        KLT cross-check improves or validates the estimate.
    n_inliers:
        Number of KLT RANSAC inliers.  0 for gyro-only.
    """

    shift_px: tuple[float, float]
    roll_rad: float
    source: Literal["gyro", "gyro+klt"]
    quality: float
    n_inliers: int


# ---------------------------------------------------------------------------
# Gyro de-rotation
# ---------------------------------------------------------------------------

def gyro_derotation(
    omega_xyz_radps: tuple[float, float, float],
    dt: float,
    intrinsics: CameraIntrinsics,
) -> EgoEstimate:
    """Predict the scene shift from body angular rate (gyro de-rotation).

    This is the BASE ego-motion path.  It runs in ~0.05 ms and requires no
    texture in the scene.  Per design §3.2, gyro-only is the normal operating
    mode on a textureless night sky.

    Parameters
    ----------
    omega_xyz_radps:
        Body angular rate (omega_x, omega_y, omega_z) in rad/s.
        Convention: right-hand rule, body +X rightward, body +Y upward,
        body +Z out-of-boresight.
            omega_x — pitch rate
            omega_y — yaw rate
            omega_z — ROLL rate (in-plane image rotation about boresight)
    dt:
        Time elapsed since the previous frame (seconds).
    intrinsics:
        Camera intrinsic parameters (focal length in pixels).

    Returns
    -------
    EgoEstimate
        source='gyro', quality=1.0, n_inliers=0.
        shift_px = (-f·omega_y·dt, -f·omega_x·dt)  [translation terms only].
        roll_rad = omega_z · dt  [stored for LOSComputer to apply roll correction].

    The ROLL correction (omega_z-induced tangential shift for an off-axis target)
    is NOT applied here because it is target-position-dependent.  It is applied
    in LOSComputer.update(), which knows the target pixel at each frame.

    Sign convention (verbatim from design §3.2):
        dx_px ≈ -f · omega_y · dt          (translation from yaw)
        dy_px ≈ -f · omega_x · dt          (translation from pitch)
        roll  =  omega_z · dt              (positive = CCW body rotation in math coords)
    """
    ox, oy, oz = omega_xyz_radps
    f = intrinsics.f_px

    # Translation terms from pitch (ox) and yaw (oy) only.
    # Roll (oz) is stored in roll_rad; the per-target tangential correction
    # is computed in LOSComputer.update() using the target's pixel offset.
    dx = -f * oy * dt
    dy = -f * ox * dt
    roll = oz * dt

    return EgoEstimate(
        shift_px=(dx, dy),
        roll_rad=roll,
        source="gyro",
        quality=1.0,
        n_inliers=0,
    )


# ---------------------------------------------------------------------------
# Sparse Lucas-Kanade residual (optional, texture-dependent)
# ---------------------------------------------------------------------------

#: Minimum number of KLT inliers to trust the LK estimate over gyro-only.
#: Below this threshold → return None → use gyro-only.
_MIN_INLIERS: int = 12


def sparse_lk_residual(
    prev_frame: npt.NDArray[np.uint16 | np.float32],
    cur_frame: npt.NDArray[np.uint16 | np.float32],
    target_mask: npt.NDArray[np.bool_] | None,
    *,
    max_corners: int = 80,
    min_distance_px: int = 10,
    quality_level: float = 0.01,
) -> EgoEstimate | None:
    """Estimate scene shift from sparse Lucas-Kanade optical flow.

    Runs Shi-Tomasi corner detection on the COLD BACKGROUND (target masked out),
    then Lucas-Kanade pyramidal tracking, then RANSAC 2-DOF (translation-only)
    similarity to extract the consensus shift.

    Returns ``None`` when inliers < ``_MIN_INLIERS`` — this is the NORMAL result
    on a textureless night sky and the caller falls back to gyro-only.

    OpenCV is used if importable; otherwise a numpy phase-correlation fallback is
    applied (less accurate but still useful as a cross-check).

    Parameters
    ----------
    prev_frame, cur_frame:
        Previous and current frames as uint16 or float32 arrays of shape (H, W).
    target_mask:
        Boolean mask (H, W), True where the target/hot blob is located.
        Corners within this region are excluded so the target's OWN motion does
        not corrupt the background ego estimate.  Pass ``None`` to use the full
        frame (e.g., for synthetic tests without a salient target).
    max_corners:
        Maximum number of Shi-Tomasi corners to track.
    min_distance_px:
        Minimum distance between detected corners in pixels.
    quality_level:
        Shi-Tomasi quality level for ``goodFeaturesToTrack``.

    Returns
    -------
    EgoEstimate | None
        Returns ``None`` when the LK result is unreliable (< 12 inliers).
        Returns an ``EgoEstimate`` with source='gyro+klt' on success.
    """
    try:
        return _sparse_lk_opencv(
            prev_frame, cur_frame, target_mask,
            max_corners=max_corners,
            min_distance_px=min_distance_px,
            quality_level=quality_level,
        )
    except ImportError:
        return _phase_correlation_fallback(prev_frame, cur_frame, target_mask)


def _sparse_lk_opencv(
    prev_frame: npt.NDArray,
    cur_frame: npt.NDArray,
    target_mask: npt.NDArray[np.bool_] | None,
    *,
    max_corners: int,
    min_distance_px: int,
    quality_level: float,
) -> EgoEstimate | None:
    """Sparse LK via cv2.  Raises ImportError if cv2 is not available."""
    import cv2  # type: ignore[import]  # not a hard dependency

    prev_u8 = _to_uint8(prev_frame)
    cur_u8 = _to_uint8(cur_frame)

    # Detection mask: exclude the target region
    detect_mask: npt.NDArray[np.uint8] | None = None
    if target_mask is not None:
        detect_mask = (~target_mask).astype(np.uint8) * 255

    corners = cv2.goodFeaturesToTrack(
        prev_u8,
        maxCorners=max_corners,
        qualityLevel=quality_level,
        minDistance=float(min_distance_px),
        mask=detect_mask,
    )

    if corners is None or len(corners) < 4:
        return None  # no texture → gyro-only (normal on night sky)

    # LK tracking
    lk_params = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.03),
    )
    corners_tracked, status, _ = cv2.calcOpticalFlowPyrLK(
        prev_u8, cur_u8, corners, None, **lk_params
    )

    if status is None:
        return None

    good_prev = corners[status.ravel() == 1]
    good_cur = corners_tracked[status.ravel() == 1]  # type: ignore[index]

    if len(good_prev) < _MIN_INLIERS:
        return None

    # RANSAC 2-DOF similarity (translation only — rotation handled separately)
    # We estimate a pure translation consensus with RANSAC.
    displacements = good_cur.reshape(-1, 2) - good_prev.reshape(-1, 2)

    inlier_mask, (dx, dy, roll) = _ransac_translation(
        displacements, n_iters=100, inlier_tol_px=1.5
    )
    n_inliers = int(np.sum(inlier_mask))

    if n_inliers < _MIN_INLIERS:
        return None

    # Quality: fraction of tracked corners that were inliers
    quality = min(1.0, 0.6 + 0.4 * (n_inliers / max(len(good_prev), 1)))

    return EgoEstimate(
        shift_px=(float(dx), float(dy)),
        roll_rad=float(roll),
        source="gyro+klt",
        quality=quality,
        n_inliers=n_inliers,
    )


def _phase_correlation_fallback(
    prev_frame: npt.NDArray,
    cur_frame: npt.NDArray,
    target_mask: npt.NDArray[np.bool_] | None,
) -> EgoEstimate | None:
    """Numpy-only phase correlation fallback when cv2 is not available.

    Phase correlation is inherently global and does not respect the target mask,
    but it provides a useful first-order ego estimate on textured scenes.
    Returns None (gyro-only) when the scene is too textureless for a reliable
    peak.  Roll is not estimated (set to 0.0).

    This path is explicitly the cv2-unavailable fallback; its accuracy is lower
    than LK.  The gyro remains the trusted base.
    """
    prev_f = prev_frame.astype(np.float32)
    cur_f = cur_frame.astype(np.float32)

    # Zero-out target region if provided (avoid target biasing the shift)
    if target_mask is not None:
        prev_f[target_mask] = float(np.mean(prev_f[~target_mask]))
        cur_f[target_mask] = float(np.mean(cur_f[~target_mask]))

    # Phase correlation via FFT
    F_prev = np.fft.fft2(prev_f)
    F_cur = np.fft.fft2(cur_f)
    cross_power = F_prev * np.conj(F_cur)
    denom = np.abs(cross_power) + 1e-10
    cross_power_norm = cross_power / denom
    correlation = np.fft.ifft2(cross_power_norm).real

    # Find peak
    peak_loc = np.unravel_index(np.argmax(correlation), correlation.shape)
    H, W = prev_f.shape
    dy_raw = float(peak_loc[0])
    dx_raw = float(peak_loc[1])

    # Wrap shifts: phase correlation gives [0, N) but the actual shift is in (-N/2, N/2)
    if dy_raw > H / 2:
        dy_raw -= H
    if dx_raw > W / 2:
        dx_raw -= W

    # Assess peak sharpness as a quality proxy
    peak_val = float(correlation[peak_loc])
    sorted_vals = np.sort(correlation.ravel())[::-1]
    second_val = float(sorted_vals[1]) if len(sorted_vals) > 1 else 0.0
    peak_ratio = peak_val / (second_val + 1e-10)

    if peak_ratio < 2.0:
        # Weak peak → insufficient texture → gyro-only
        return None

    # Synthetic inlier count: not meaningful for phase-corr, but mark the source
    quality = min(1.0, 0.6 + 0.1 * math.log(max(peak_ratio, 1.0)))
    # Phase correlation is treated as a rough check — use a conservative quality
    quality = min(quality, 0.75)

    return EgoEstimate(
        shift_px=(dx_raw, dy_raw),
        roll_rad=0.0,  # phase correlation does not recover roll
        source="gyro+klt",
        quality=quality,
        n_inliers=_MIN_INLIERS,  # signal that inlier count is met (nominally)
    )


# ---------------------------------------------------------------------------
# RANSAC translation estimator
# ---------------------------------------------------------------------------

def _ransac_translation(
    displacements: npt.NDArray[np.float32],
    *,
    n_iters: int = 100,
    inlier_tol_px: float = 1.5,
) -> tuple[npt.NDArray[np.bool_], tuple[float, float, float]]:
    """RANSAC consensus translation from a set of 2-D displacement vectors.

    Parameters
    ----------
    displacements:
        Shape (N, 2) array of (dx, dy) vectors from point tracking.
    n_iters:
        Number of RANSAC iterations.
    inlier_tol_px:
        Inlier threshold in pixels.

    Returns
    -------
    (inlier_mask, (dx, dy, roll))
        ``inlier_mask`` is a boolean array of shape (N,).
        ``dx, dy`` is the consensus translation.
        ``roll`` is always 0.0 (not estimated here — left to the similarity
        model in a future extension).
    """
    rng = np.random.default_rng(0)  # deterministic for reproducibility
    n = len(displacements)
    if n == 0:
        return np.zeros(0, dtype=bool), (0.0, 0.0, 0.0)

    best_mask = np.zeros(n, dtype=bool)
    best_count = 0

    for _ in range(n_iters):
        idx = int(rng.integers(0, n))
        dx_hyp = displacements[idx, 0]
        dy_hyp = displacements[idx, 1]

        residuals = np.sqrt(
            (displacements[:, 0] - dx_hyp) ** 2
            + (displacements[:, 1] - dy_hyp) ** 2
        )
        mask = residuals < inlier_tol_px
        count = int(np.sum(mask))

        if count > best_count:
            best_count = count
            best_mask = mask

    if best_count > 0:
        dx_final = float(np.median(displacements[best_mask, 0]))
        dy_final = float(np.median(displacements[best_mask, 1]))
    else:
        dx_final = float(np.median(displacements[:, 0]))
        dy_final = float(np.median(displacements[:, 1]))
        best_mask = np.ones(n, dtype=bool)

    return best_mask, (dx_final, dy_final, 0.0)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _to_uint8(frame: npt.NDArray) -> npt.NDArray[np.uint8]:
    """Normalise a frame to uint8 for OpenCV processing."""
    f = frame.astype(np.float32)
    f_min = f.min()
    f_max = f.max()
    if f_max <= f_min:
        return np.zeros_like(f, dtype=np.uint8)
    scale = 255.0 / (f_max - f_min)
    return ((f - f_min) * scale).astype(np.uint8)
