"""R5: aimpoint migration -- hotspot (POINT) -> silhouette-centroid (RESOLVED/FILL).

As the target resolves, the white top-hat suppresses its interior, so the detector's
intensity-weighted centroid collapses onto the AGC-saturating hot pixel (motor glow) -- which
WALKS across the airframe as aspect rotates head-on->beam.  That is a silent lambda-dot
disturbance at the worst moment (glint error ~ L/R GROWS as range closes).

The fix is a SILHOUETTE centroid: the intensity-weighted centre of the whole WARM REGION on the
RAW frame (everything a few sigma above the local background), where the body's many pixels
dominate the single hot pixel, so the aimpoint sits on the body centre and stops walking.

DOCTRINE (Inv 2): this is DETERMINISTIC geometry on the raw frame -- the same kind of
measurement as the existing centroid, NOT a learned/appearance-classifier or quality signal.
It takes no lock-quality / model-wrong / PSR input, so a quality perturbation cannot move it.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
from scipy import ndimage as ndi

from .track import RegimeState


def silhouette_centroid(
    frame_f: npt.NDArray[np.float32],
    cx: float,
    cy: float,
    peak: float,
    *,
    half_win: int = 90,
    k_sigma: float = 5.0,
) -> tuple[float, float]:
    """Intensity-weighted centroid of the warm body region connected to ``(cx, cy)``.

    Thresholds at ``base + k_sigma * border_std`` (just above the local background), so the
    DIM extended body -- not the bright hot pixel -- defines the footprint.  The luminance-
    weighted centroid of that connected region is the body centre; the hot pixel contributes
    only its (small) share of the total weight.  Falls back to ``(cx, cy)`` on a degenerate
    footprint.
    """
    frame_f = np.asarray(frame_f, dtype=np.float64)   # accept uint16 frames directly
    h, w = frame_f.shape
    x0 = max(0, int(cx) - half_win)
    x1 = min(w, int(cx) + half_win)
    y0 = max(0, int(cy) - half_win)
    y1 = min(h, int(cy) + half_win)
    patch = frame_f[y0:y1, x0:x1]
    if patch.size == 0:
        return float(cx), float(cy)
    border = np.concatenate([patch[0, :], patch[-1, :], patch[:, 0], patch[:, -1]])
    base = float(np.median(border))
    border_std = max(float(np.std(border)), 1.0)
    thr = base + k_sigma * border_std
    above = patch >= thr
    labeled, _ = ndi.label(above)
    ly, lx = int(cy) - y0, int(cx) - x0
    if not (0 <= ly < labeled.shape[0] and 0 <= lx < labeled.shape[1] and labeled[ly, lx] > 0):
        return float(cx), float(cy)
    region = labeled == labeled[ly, lx]
    wts = np.maximum(patch.astype(np.float64) - base, 0.0) * region
    total = float(wts.sum())
    if total <= 0.0:
        return float(cx), float(cy)
    yy = np.arange(y0, y1, dtype=np.float64)[:, None]
    xx = np.arange(x0, x1, dtype=np.float64)[None, :]
    sx = float((xx * wts).sum() / total)
    sy = float((yy * wts).sum() / total)
    return sx, sy


def migrate_aimpoint(
    frame_f: npt.NDArray[np.float32],
    centroid_px: tuple[float, float],
    peak: float,
    velocity_px_per_frame: tuple[float, float],
    regime: RegimeState,
    *,
    forward_bias_px: float = 0.0,
) -> tuple[float, float]:
    """Return the aimpoint for the current regime.

    POINT     -> the hotspot centroid unchanged (our current, correct behaviour at long range).
    RESOLVED/ -> the silhouette centroid, optionally shifted ``forward_bias_px`` toward the
    FILL         leading edge along the target's motion vector (a winged body is best aimed
                 slightly ahead of its geometric centre).
    """
    if regime == RegimeState.POINT:
        return float(centroid_px[0]), float(centroid_px[1])
    sx, sy = silhouette_centroid(frame_f, centroid_px[0], centroid_px[1], peak)
    if forward_bias_px > 0.0:
        vx, vy = velocity_px_per_frame
        vmag = math.hypot(vx, vy)
        if vmag > 1e-6:
            sx += forward_bias_px * vx / vmag
            sy += forward_bias_px * vy / vmag
    return sx, sy
