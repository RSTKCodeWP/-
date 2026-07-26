"""Robust silhouette extent — the target's true angular span, immune to top-hat interior suppression.

WHY THIS EXISTS
===============
Subtense ranging needs the target's PHYSICAL extent in pixels. The obvious source — the detector's
thresholded bbox — is corrupted for a resolved target: the white top-hat (``f - opening(f)``) SUPPRESSES
the interior of anything larger than its structuring element, so the detected foreground is a rim, and
``bbox``/``area_px`` UNDER-report the true span exactly when the target fills the FOV (the terminal, where
range matters most). ``detect._extended_area_px`` already recovers the un-suppressed FOOTPRINT AREA by
flood-filling the half-max contour on the RAW frame; this module takes the same footprint and, from its
SECOND MOMENTS, recovers the MAJOR/MINOR AXIS LENGTHS — the elongated silhouette's span (which maps to the
known wingspan), not an isotropic diameter.

METHOD
======
1. Half-max iso-contour on the raw frame patch:  thr = base + level_frac·(peak - base),
   base = the patch-border median (a local background), matching ``_extended_area_px``.
2. Flood-fill: keep ONLY the connected component containing the centroid (a disconnected hot region
   elsewhere in the window is ignored).
3. Equivalent-ellipse axes from the binary component's central second moments (the scikit-image
   convention): with λ₁ ≥ λ₂ the eigenvalues of the second-moment covariance,
        major_px = 4·√λ₁,   minor_px = 4·√λ₂,   orientation = ½·atan2(2·μ₁₁, μ₂₀ − μ₀₂).
   (For a uniform disc of diameter d these give major = minor = d; verified on a known ellipse.)

HONESTY
=======
The half-max footprint is a THERMAL iso-contour, not the geometric edge; for a resolved target against a
cold sky the two nearly coincide, but the mapping ``major_px ≈ f·wingspan/R`` carries a calibration factor
that folds into the subtense size prior σ_S (and is pinned by a ToF self-cal). At true saturation (target
fills the window, no clean border background) the footprint is genuinely unobservable — ``resolved`` goes
False and the caller must fall back (bbox) or coast, never fabricate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy import ndimage as ndi


@dataclass(frozen=True)
class SilhouetteExtent:
    """Second-moment silhouette extent of the target footprint.

    Attributes
    ----------
    major_px, minor_px:
        Equivalent-ellipse major / minor axis lengths (pixels).  ``major_px`` is the span used for
        subtense ranging (paired with the known wingspan).
    area_px:
        Half-max footprint area (pixels) of the flood-filled component — the un-suppressed footprint.
    orientation_rad:
        Angle of the major axis (radians), for aspect / foreshortening reasoning.
    resolved:
        True iff a clean footprint of at least ``min_area_px`` was found containing the centroid.  False
        ⇒ acquisition-small or saturated: the caller must fall back / coast, not trust these numbers.
    """

    major_px: float
    minor_px: float
    area_px: float
    orientation_rad: float
    resolved: bool


def silhouette_extent(
    frame: npt.NDArray,
    cx: float,
    cy: float,
    peak: float,
    *,
    half_win: int = 90,
    level_frac: float = 0.5,
    min_area_px: int = 6,
    background: float | None = None,
) -> SilhouetteExtent:
    """Recover the target's major/minor silhouette axes from the raw-frame half-max footprint.

    Parameters
    ----------
    frame:
        Raw thermal frame (uint16 or float); read-only.
    cx, cy:
        Target centroid in absolute frame pixels.
    peak:
        Target peak counts (``ThermalBlob.peak_counts``), for the half-max level.
    half_win:
        Half-width of the analysis window around the centroid (px).
    level_frac:
        Iso-contour fraction between background and peak (0.5 = half-max).
    min_area_px:
        Footprint below this ⇒ ``resolved=False`` (acquisition regime; moments unreliable).
    background:
        Optional explicit background level; default = the window-border median (local background).
    """
    f = np.asarray(frame, dtype=np.float64)
    h, w = f.shape
    icx, icy = int(round(cx)), int(round(cy))
    x0 = max(0, icx - half_win)
    x1 = min(w, icx + half_win)
    y0 = max(0, icy - half_win)
    y1 = min(h, icy + half_win)
    patch = f[y0:y1, x0:x1]
    if patch.size == 0:
        return SilhouetteExtent(0.0, 0.0, 0.0, 0.0, False)

    if background is None:
        border = np.concatenate([patch[0, :], patch[-1, :], patch[:, 0], patch[:, -1]])
        base = float(np.median(border))
    else:
        base = float(background)
    if not (float(peak) > base):
        return SilhouetteExtent(0.0, 0.0, 0.0, 0.0, False)     # no contrast -> unresolved

    thr = base + level_frac * (float(peak) - base)
    above = patch >= thr
    labeled, _ = ndi.label(above)
    ly, lx = icy - y0, icx - x0
    if not (0 <= ly < labeled.shape[0] and 0 <= lx < labeled.shape[1] and labeled[ly, lx] > 0):
        return SilhouetteExtent(0.0, 0.0, 0.0, 0.0, False)     # centroid below the contour -> unresolved

    ys, xs = np.nonzero(labeled == labeled[ly, lx])
    n = int(xs.size)
    if n < min_area_px:
        return SilhouetteExtent(0.0, 0.0, float(n), 0.0, False)

    # Central second moments of the binary component -> equivalent-ellipse axes.
    xf = xs.astype(np.float64)
    yf = ys.astype(np.float64)
    mx, my = xf.mean(), yf.mean()
    mu20 = float(((xf - mx) ** 2).mean())
    mu02 = float(((yf - my) ** 2).mean())
    mu11 = float(((xf - mx) * (yf - my)).mean())
    cov = np.array([[mu20, mu11], [mu11, mu02]], dtype=np.float64)
    ev = np.linalg.eigvalsh(cov)                                # ascending
    lam_max = float(max(ev[1], 0.0))
    lam_min = float(max(ev[0], 0.0))
    major = 4.0 * math.sqrt(lam_max)
    minor = 4.0 * math.sqrt(lam_min)
    orientation = 0.5 * math.atan2(2.0 * mu11, (mu20 - mu02))
    return SilhouetteExtent(major, minor, float(n), orientation, True)
