"""R6: synthetic-event log-contrast motion channel (the DVS *algorithm*, not the hardware).

A DVS responds to d(log I)/dt.  The LOG makes the response invariant to the *multiplicative* AGC
gain; the temporal DIFFERENCE makes static background vanish from the data until it moves.  We
emulate this on the FT640 today -- per-pixel log-intensity temporal difference on ego-shift-
compensated frames -- to get a target locator (and hence a lambda-dot) that the four closing-
engagement nuisances (AGC gain pumping, background march, signature change, scale growth) are
BLIND to.

Honest framing: this is an INVARIANCE win, not a latency win -- the bolometer's ~10-15 ms thermal
time-constant caps any speed benefit; the value is robustness, not microsecond timing.

Doctrine (Inv 2): the output is a MOTION measurement (kinematic) -- the same class as the
intensity centroid -- not an appearance classifier or quality signal.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy import ndimage as ndi

#: A FT640 frame is uint16, so log I has only 65536 possible values.  Precomputing them in a LUT
#: turns the per-pixel float64 ``np.log`` (a top per-frame cost on the Pi5) into a single integer
#: gather -- BIT-IDENTICAL output (same float64 values, just table-driven).
_LOG_LUT: npt.NDArray[np.float64] = np.log(np.maximum(np.arange(65536, dtype=np.float64), 1.0))


class EventChannel:
    """Maintains one frame of log-intensity history and emits an AGC-invariant motion centroid."""

    def __init__(self, *, k_mad: float = 4.0, dilate: int = 1, min_pixels: int = 4) -> None:
        self._prev_logL: npt.NDArray[np.float64] | None = None
        self._k = float(k_mad)
        self._dilate = int(dilate)
        self._min_pixels = int(min_pixels)

    def reset(self) -> None:
        """Flush the history (call on an FFC event so stale shutter frames are not differenced)."""
        self._prev_logL = None

    def update(self, frame_u16: npt.NDArray[np.uint16],
               ego_shift_px: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float] | None:
        """Push a frame; return the |d(log I)/dt| motion-field centroid (px), or None.

        ``ego_shift_px`` is the gyro-derived per-frame scene shift (EgoEstimate.shift_px); the
        previous log-frame is registered by it so only INDEPENDENT motion survives the difference.
        """
        fu16 = np.asarray(frame_u16, dtype=np.uint16)
        # uint16 -> exact log via the module LUT (BIT-IDENTICAL to np.log(np.maximum(f, 1.0))).
        logL = _LOG_LUT[fu16]
        if self._prev_logL is None:
            self._prev_logL = logL
            return None
        prev = self._register(self._prev_logL, ego_shift_px)
        self._prev_logL = logL

        a = np.abs(logL - prev)
        # A constant log-gain step (AGC) shifts the whole field uniformly -> removed by the
        # MEDIAN-relative MAD threshold; only genuine local motion exceeds it.  Kept as a FULL-field
        # median (not subsampled): a strided subsample drifts the scalar threshold enough to flip a
        # lone boundary pixel and pull the emitted motion centroid a few px -- unacceptable noise to
        # inject into a kinematic (lambda-dot) measurement (Inv 2) to save a non-dominant ~10 ms.
        med = float(np.median(a))
        mad = float(np.median(np.abs(a - med))) * 1.4826 or 1e-6
        mask = a > (med + self._k * mad)
        if self._dilate > 0:
            mask = ndi.binary_dilation(mask, iterations=self._dilate)
        if int(mask.sum()) < self._min_pixels:
            return None
        w = a * mask
        total = float(w.sum())
        if total <= 0.0:
            return None
        h, wdt = logL.shape
        yy = np.arange(h, dtype=np.float64)[:, None]
        xx = np.arange(wdt, dtype=np.float64)[None, :]
        return float((xx * w).sum() / total), float((yy * w).sum() / total)

    @staticmethod
    def _register(logL_prev: npt.NDArray[np.float64],
                  ego_shift_px: tuple[float, float]) -> npt.NDArray[np.float64]:
        """Shift the previous log-frame by the ego scene-shift so static background cancels."""
        dx, dy = ego_shift_px
        if dx == 0.0 and dy == 0.0:
            return logL_prev
        return ndi.shift(logL_prev, (dy, dx), order=1, mode="nearest")
