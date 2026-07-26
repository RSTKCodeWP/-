"""Optical looming: tau = A / (dA/dt) as a gated, weak closing-sign cue.

PURPOSE AND LIMITATIONS (honest, per design §3.2 and §3.3)
------------------------------------------------------------
tau = A / (dA/dt) estimates time-to-impact from the observed rate of blob-area
growth.  This is a WEAK, GATED cue used only as a cross-check on the sign and
rough order-of-magnitude of closing velocity.  It is NOT used as a reliable
range or Vc estimate.

The design §3.3 is explicit:
    «Vc = РАСПИСАННЫЙ/предполагаемый скаляр из SpeedPolicy, НЕ доверяем τ»
    «Looming-τ используется только как confidence-gated cross-check знака/порядка»

Why tau is unreliable:
    (1) ACQUISITION (small blob, 1-3 px): dA/dt is dominated by detection noise
        (sub-pixel centroid jitter produces huge fractional area changes).
        tau_confidence → 0 in this regime.
    (2) SATURATION (large blob near impact, blob fills ROI): dA/dt underestimates
        the true rate because the blob is clipped by the sensor boundary.
        tau_confidence → 0 as blob area approaches saturation.
    (3) CROSSING GEOMETRY: dA/dt → 0 when the interceptor is not closing.
        tau → infinity.  Correctly reflected by low tau_confidence.

tau_confidence IS the primary output — callers should gate on it before using tau.

ALGORITHM
---------
1. Maintain a rolling exponential moving average of blob area to suppress
   single-frame detection noise.
2. Estimate dA/dt from the smoothed area history (linear regression over a
   short window, or finite difference when the window is short).
3. Compute tau = A_smoothed / dA_dt.  Reject negative tau (diverging target).
4. Compute tau_confidence as a product of three factors:
   - blob_size_factor:    0 when area < min_area_threshold (too few pixels)
                          ramps to 1 above a larger min threshold
   - saturation_factor:   0 when area > max_area_threshold (near sensor edge)
                          ramps to 0 above a saturation threshold
   - rate_snr_factor:     0 when |dA/dt| < noise floor (area barely changing)
                          ramps to 1 for clear area growth

closing_sign is derived from the sign of dA/dt:
    +1  — area growing   (closing)
    -1  — area shrinking (opening)
     0  — no clear trend (tau_confidence too low)
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LoomingEstimate:
    """Per-frame optical looming estimate.

    Attributes
    ----------
    tau_s:
        Estimated time-to-impact in seconds.  Positive = closing.
        Invalid / infinity when tau_confidence is low.
    tau_confidence:
        Scalar in [0, 1].  Collapses at small blob (acquisition) and at
        blob saturation (impact).  Only trust tau when this is > 0.5.
    closing_sign:
        +1 = closing, -1 = opening, 0 = indeterminate.
    area_smoothed_px:
        Exponentially-smoothed blob area estimate (pixels).
    d_area_dt_px_per_s:
        Estimated rate of area change (pixels per second).
    """

    tau_s: float
    tau_confidence: float
    closing_sign: int
    area_smoothed_px: float
    d_area_dt_px_per_s: float


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LoomingConfig:
    """Configuration for the LoomingEstimator.

    Attributes
    ----------
    area_ema_alpha:
        Exponential moving average coefficient for area smoothing.
        0 = no smoothing, 1 = instant tracking.  Default 0.3 (moderate).
    min_area_px:
        Minimum area (pixels) below which tau_confidence is set to 0 (blob
        too small — acquisition regime, 1-3 px).
    min_area_confident_px:
        Area above which the blob-size factor reaches 1.0.  Ramps linearly
        between min_area_px and this value.
    max_area_saturating_px:
        Area above which the saturation factor starts ramping down.
    max_area_saturated_px:
        Area above which tau_confidence contribution from saturation = 0.
    min_rate_px_per_s:
        Minimum |dA/dt| (pixels/s) to register as a meaningful rate.
        Below this → rate_snr_factor = 0.
    confident_rate_px_per_s:
        |dA/dt| above which rate_snr_factor = 1.0.  Ramps between min and this.
    window_frames:
        Number of frames to use for the dA/dt linear regression.
    max_tau_s:
        Maximum credible tau (seconds).  If the computed tau exceeds this cap,
        tau_confidence is set to 0 and closing_sign is set to 0 (indeterminate).
        Physically: tau > 30 s means the blob is barely growing — the estimate
        is noise-dominated and should not be trusted.  Default 30 s.
        Set to math.inf to disable the cap.
    """

    area_ema_alpha: float = 0.3
    min_area_px: float = 2.0
    min_area_confident_px: float = 8.0
    max_area_saturating_px: float = 500.0
    max_area_saturated_px: float = 1000.0
    min_rate_px_per_s: float = 0.5
    confident_rate_px_per_s: float = 5.0
    window_frames: int = 8
    max_tau_s: float = 30.0   # cap: tau > this → confidence = 0, closing_sign = 0


# ---------------------------------------------------------------------------
# Estimator
# ---------------------------------------------------------------------------

class LoomingEstimator:
    """Stateful per-frame looming estimator.

    Usage
    -----
    ::

        estimator = LoomingEstimator()
        for blob, dt in ...:
            est = estimator.update(blob.area_px, dt)
            if est.tau_confidence > 0.5:
                use_tau(est.tau_s, est.closing_sign)
    """

    def __init__(self, config: LoomingConfig | None = None) -> None:
        self._cfg = config or LoomingConfig()
        self._area_smoothed: float | None = None
        # Circular buffer of (area_smoothed, elapsed_time) for regression
        self._area_history: deque[tuple[float, float]] = deque(
            maxlen=self._cfg.window_frames
        )
        self._total_time: float = 0.0

    def reset(self) -> None:
        """Reset state (e.g., after track loss)."""
        self._area_smoothed = None
        self._area_history.clear()
        self._total_time = 0.0

    def update(self, area_px: float, dt: float) -> LoomingEstimate:
        """Process one frame's blob area.

        Parameters
        ----------
        area_px:
            Observed blob area in pixels (e.g., ``ThermalBlob.area_px``).
        dt:
            Elapsed time since the previous frame (seconds).

        Returns
        -------
        LoomingEstimate
        """
        cfg = self._cfg
        dt = max(dt, 1e-6)

        # ── EMA smoothing ──────────────────────────────────────────────────
        if self._area_smoothed is None:
            self._area_smoothed = area_px
        else:
            a = cfg.area_ema_alpha
            self._area_smoothed = a * area_px + (1.0 - a) * self._area_smoothed

        self._total_time += dt
        self._area_history.append((self._area_smoothed, self._total_time))

        area_s = self._area_smoothed

        # ── Estimate dA/dt ─────────────────────────────────────────────────
        d_area_dt = self._estimate_rate()

        # ── Compute tau ────────────────────────────────────────────────────
        if d_area_dt > 0.0 and area_s > 0.0:
            tau = area_s / d_area_dt
        else:
            tau = float("inf")

        # ── Closing sign ───────────────────────────────────────────────────
        if d_area_dt > cfg.min_rate_px_per_s:
            closing_sign = 1
        elif d_area_dt < -cfg.min_rate_px_per_s:
            closing_sign = -1
        else:
            closing_sign = 0

        # ── tau_confidence (product of three factors) ─────────────────────
        # Factor 1: blob too small (acquisition noise dominates)
        if area_s < cfg.min_area_px:
            size_factor = 0.0
        elif area_s < cfg.min_area_confident_px:
            size_factor = (area_s - cfg.min_area_px) / (
                cfg.min_area_confident_px - cfg.min_area_px
            )
        else:
            size_factor = 1.0

        # Factor 2: blob approaching saturation (near impact)
        if area_s > cfg.max_area_saturated_px:
            sat_factor = 0.0
        elif area_s > cfg.max_area_saturating_px:
            sat_factor = 1.0 - (area_s - cfg.max_area_saturating_px) / (
                cfg.max_area_saturated_px - cfg.max_area_saturating_px
            )
        else:
            sat_factor = 1.0

        # Factor 3: area rate too small (no clear approach trend)
        abs_rate = abs(d_area_dt)
        if abs_rate < cfg.min_rate_px_per_s:
            rate_factor = 0.0
        elif abs_rate < cfg.confident_rate_px_per_s:
            rate_factor = (abs_rate - cfg.min_rate_px_per_s) / (
                cfg.confident_rate_px_per_s - cfg.min_rate_px_per_s
            )
        else:
            rate_factor = 1.0

        tau_confidence = size_factor * sat_factor * rate_factor

        # Cap tau at a sensible maximum to avoid garbage values.
        # (a) Infinite or negative tau → zero confidence.
        if not math.isfinite(tau) or tau < 0.0:
            tau = float("inf")
            tau_confidence *= 0.0

        # (b) Excessively large tau → noise-dominated, zero confidence (Fix 5).
        #     max_tau_s is configurable; default 30 s.
        if math.isfinite(tau) and tau > cfg.max_tau_s:
            tau_confidence *= 0.0

        # (c) When tau_confidence == 0, set closing_sign = 0 (indeterminate).
        #     Per the documented API: 0 = indeterminate.  Callers MUST NOT act
        #     on a directional cue when confidence is zero.
        if tau_confidence == 0.0:
            closing_sign = 0

        return LoomingEstimate(
            tau_s=tau,
            tau_confidence=float(tau_confidence),
            closing_sign=closing_sign,
            area_smoothed_px=float(area_s),
            d_area_dt_px_per_s=float(d_area_dt),
        )

    def _estimate_rate(self) -> float:
        """Estimate dA/dt from the area history.

        Uses linear least-squares regression over the window when enough
        samples are available; falls back to a simple 2-point difference.
        """
        history = list(self._area_history)
        if len(history) < 2:
            return 0.0

        areas = [h[0] for h in history]
        times = [h[1] for h in history]

        if len(history) >= 3:
            # Linear regression: area = a*t + b, return slope a
            import numpy as np  # local import to keep the module lightweight
            t_arr = np.array(times, dtype=np.float64)
            a_arr = np.array(areas, dtype=np.float64)
            t_mean = t_arr.mean()
            a_mean = a_arr.mean()
            t_var = float(np.sum((t_arr - t_mean) ** 2))
            if t_var < 1e-12:
                return 0.0
            slope = float(np.sum((t_arr - t_mean) * (a_arr - a_mean)) / t_var)
            return slope

        # 2-point fallback
        dt = times[-1] - times[0]
        if dt < 1e-9:
            return 0.0
        return (areas[-1] - areas[0]) / dt
