"""R8: MOSSE correlation channel -- a structural track confined to the IMM gate.

The detector+association+centroid spine is the literature's MOST FRAGILE family for our closing
endgame (top-hat suppresses the resolved body, the centroid walks onto the AGC-saturating hot
pixel).  A correlation filter holds STRUCTURE through that transition.  We run a lightweight
MOSSE (Bolme 2010) filter on a small chip in the IMM gate and expose:

  * a PEAK-TO-SIDELOBE RATIO (PSR) -- an image-space track-health confidence, and
  * the response-peak OFFSET -- a structural position for RE-DETECTING the SAME track.

DOCTRINE (Inv 2): the PSR is a QUALITY signal and feeds lock-quality / engage-permission ONLY;
the structural offset is used for same-track re-detection (Inv 7), NOT to move the live aimpoint
-- the geometric centroid remains the LOS source.  A FEAR dual template keeps an IMMUTABLE LOBL
reference (the committed target) alongside a slow-adapting dynamic filter, so appearance drift
can never walk the structural track off the originally-confirmed target.

Pure-numpy FFT; the chip is small (default 32x32) so the whole channel fits the per-frame budget.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
from scipy import ndimage as ndi


def extract_chip(frame: npt.NDArray[np.uint16], cx: float, cy: float,
                 size: int = 32) -> npt.NDArray[np.float64]:
    """Crop a ``size x size`` chip centred on ``(cx, cy)``, zero-padded at the frame border."""
    n = int(size)
    h2 = n // 2
    h, w = frame.shape
    x0, y0 = int(round(cx)) - h2, int(round(cy)) - h2
    chip = np.zeros((n, n), dtype=np.float64)
    fx0, fy0 = max(0, x0), max(0, y0)
    fx1, fy1 = min(w, x0 + n), min(h, y0 + n)
    if fx1 > fx0 and fy1 > fy0:
        chip[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0] = frame[fy0:fy1, fx0:fx1]
    return chip


def warp_chip(chip: npt.NDArray[np.float64], content_scale: float,
              angle_rad: float = 0.0) -> npt.NDArray[np.float64]:
    """R9 anticipatory pre-warp: scale (+rotate) a chip's content about its centre.

    ``content_scale`` > 1 MAGNIFIES the content (zoom in); < 1 shrinks it.  The pipeline shrinks a
    closing (grown) target back toward the template scale by content_scale = exp(-dt/tau) using the
    range-free looming tau, and rotates by the IMM cross-LOS aspect rate -- so the correlation runs
    against a SCALE/ASPECT-PREDICTED appearance and the structural residual stays small exactly when
    raw appearance changes fastest.  Confidence-gated by the caller (falls back to the immutable
    template when tau confidence is low).
    """
    n = chip.shape[0]
    c = (n - 1) / 2.0
    s = max(float(content_scale), 1e-3)
    cos, sin = math.cos(angle_rad), math.sin(angle_rad)
    matrix = np.array([[cos, -sin], [sin, cos]], dtype=np.float64) / s
    offset = np.array([c, c]) - matrix @ np.array([c, c])
    return ndi.affine_transform(chip.astype(np.float64), matrix, offset=offset, order=1, mode="nearest")


def _cosine_window(n: int) -> npt.NDArray[np.float64]:
    w = np.hanning(n)
    return np.outer(w, w)


def _gaussian_peak(n: int, sigma: float) -> npt.NDArray[np.float64]:
    """Desired correlation output: a centred unit Gaussian (peak at the chip centre)."""
    ax = np.arange(n) - n // 2
    xx, yy = np.meshgrid(ax, ax)
    g = np.exp(-(xx ** 2 + yy ** 2) / (2.0 * sigma ** 2))
    return g / (g.sum() + 1e-12)


class MosseFilter:
    """One MOSSE correlation filter (online-adaptable)."""

    def __init__(self, size: int = 32, sigma: float = 2.0, lr: float = 0.125, eps: float = 1e-3) -> None:
        self._n = int(size)
        self._lr = float(lr)
        self._eps = float(eps)
        self._win = _cosine_window(self._n)
        self._G = np.fft.fft2(_gaussian_peak(self._n, sigma))
        self._num: npt.NDArray[np.complex128] | None = None   # G * conj(F)
        self._den: npt.NDArray[np.complex128] | None = None   # F * conj(F)

    @property
    def initialized(self) -> bool:
        return self._num is not None

    def _preprocess(self, patch: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        p = np.log(np.maximum(patch.astype(np.float64), 1.0))   # log -> AGC/illumination robust
        p = (p - p.mean()) / (p.std() + self._eps)              # normalise
        return p * self._win                                    # cosine window (kill edge effects)

    def init(self, chip: npt.NDArray[np.float64]) -> None:
        F = np.fft.fft2(self._preprocess(chip))
        self._num = self._G * np.conj(F)
        self._den = F * np.conj(F)

    def update(self, chip: npt.NDArray[np.float64]) -> None:
        """Online-adapt the filter toward the new appearance (skip for an immutable reference)."""
        if self._num is None:
            self.init(chip)
            return
        F = np.fft.fft2(self._preprocess(chip))
        self._num = (1.0 - self._lr) * self._num + self._lr * (self._G * np.conj(F))
        self._den = (1.0 - self._lr) * self._den + self._lr * (F * np.conj(F))

    def correlate(self, chip: npt.NDArray[np.float64]) -> tuple[float, float, float]:
        """Return (dx, dy, psr): peak offset from the chip centre (px) and peak-to-sidelobe ratio."""
        assert self._num is not None and self._den is not None
        H = self._num / (self._den + self._eps)
        F = np.fft.fft2(self._preprocess(chip))
        # The desired output G is already centred at n//2, so the response peak sits at the chip
        # centre for the trained patch and shifts with target motion -- no fftshift needed.
        resp = np.real(np.fft.ifft2(H * F))
        py, px = np.unravel_index(int(np.argmax(resp)), resp.shape)
        psr = _psr(resp, (py, px))
        return float(px - self._n // 2), float(py - self._n // 2), psr


def _psr(resp: npt.NDArray[np.float64], peak: tuple[int, int], exclude: int = 5) -> float:
    """Peak-to-sidelobe ratio: (peak - sidelobe_mean) / sidelobe_std, excluding an 11x11 window."""
    py, px = peak
    pk = float(resp[py, px])
    mask = np.ones_like(resp, dtype=bool)
    y0, y1 = max(0, py - exclude), min(resp.shape[0], py + exclude + 1)
    x0, x1 = max(0, px - exclude), min(resp.shape[1], px + exclude + 1)
    mask[y0:y1, x0:x1] = False
    side = resp[mask]
    return (pk - float(side.mean())) / (float(side.std()) + 1e-6)


class CorrelationChannel:
    """FEAR dual-filter wrapper: an IMMUTABLE LOBL reference + a slow-adapting dynamic filter.

    ``confidence()`` returns the max PSR of the two; ``offset()`` returns the dynamic-filter peak
    offset (for same-track re-detection).  The immutable reference anchors the structural track to
    the originally-confirmed target so adaptation drift cannot walk it off (Inv 7).
    """

    def __init__(self, size: int = 32, dynamic_lr: float = 0.125) -> None:
        self._size = int(size)
        self._ref = MosseFilter(size=size, lr=0.0)       # immutable LOBL reference (never adapts)
        self._dyn = MosseFilter(size=size, lr=dynamic_lr)
        self._seeded = False

    @property
    def seeded(self) -> bool:
        return self._seeded

    def seed(self, chip: npt.NDArray[np.float64]) -> None:
        self._ref.init(chip)
        self._dyn.init(chip)
        self._seeded = True

    def measure(self, chip: npt.NDArray[np.float64], *, adapt: bool = True) -> tuple[float, float, float]:
        """Return (dx, dy, confidence_psr) for the chip; optionally adapt the dynamic filter."""
        dx, dy, psr_dyn = self._dyn.correlate(chip)
        _, _, psr_ref = self._ref.correlate(chip)
        if adapt:
            self._dyn.update(chip)
        return dx, dy, max(psr_dyn, psr_ref)
