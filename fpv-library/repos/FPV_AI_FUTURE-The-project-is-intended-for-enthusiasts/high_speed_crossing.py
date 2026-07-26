"""High-speed crossing scene + track-holding study (high-speed regime characterisation).

The engagement briefing (threat 55-83 m/s, interceptor 150 m/s) puts a crossing target at
~10-20 px/frame at 60 Hz.  The existing closing sim keeps the target boresighted, so it never
stresses fast off-boresight motion.  This asset renders a small hot target sweeping across the
frame at a controlled px/frame rate and pushes it through the REAL seeker chain
(detect -> ThermalLockTracker -> ego -> LOS -> IMM) to measure where track-holding and LOS-rate
estimation break as a function of crossing speed.

Deterministic (pure function of frame index + seed).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from fpv.seeker.geometry import ft640_intrinsics
from fpv.guidance.pipeline import SeekerGuidancePipeline

_H, _W = 512, 640
_F_PX = 707.0                                   # FT640 wide lens (matches ft640_intrinsics default)
# Fixed hard-negative stars, kept off the target's horizontal sweep band (y ~ 256).
_STARS: tuple[tuple[int, int], ...] = ((90, 80), (210, 430), (540, 110), (300, 55), (480, 445))


def crossing_frame(
    k: int, *, v_px: float, x_start: float, y0: float,
    sigma: float = 1.6, target_peak: float = 1800.0, bg: float = 4096.0,
    noise: float = 12.0, star_frac: float = 0.55, seed: int = 0,
) -> tuple[npt.NDArray[np.uint16], tuple[float, float]]:
    """One frame: a small hot target at (x_start + v*k, y0) + static stars + read noise."""
    rng = np.random.default_rng((seed * 4099 + k) & 0xFFFFFFFF)
    cx = x_start + v_px * k
    cy = y0
    yy, xx = np.mgrid[0:_H, 0:_W]
    f = bg + rng.normal(0.0, noise, (_H, _W))
    f += target_peak * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma ** 2))
    for sx, sy in _STARS:
        f += star_frac * target_peak * np.exp(-((xx - sx) ** 2 + (yy - sy) ** 2) / (2.0 * sigma ** 2))
    return np.clip(f, 0, 65535).astype(np.uint16), (cx, cy)


def crossing_sequence(v_px: float, *, seed: int = 0):
    """Target starts centred (inside the acquisition basket) and sweeps +x until near the edge."""
    x_start = _W / 2.0
    y0 = _H / 2.0
    n = min(70, max(8, int((_W / 2.0 - 60.0) / max(v_px, 1e-6))))
    return [crossing_frame(k, v_px=v_px, x_start=x_start, y0=y0, seed=seed) for k in range(n)], n


def true_az_rate_radps(v_px: float, k: int) -> float:
    """The TRUE instantaneous az-rate at frame k for a target crossing at constant PIXEL velocity.

    The target starts at the principal point and sweeps +x, so dx_world = v_px*k px.  The seeker's
    az is the real angle atan2(dx_world, f), so the true angular rate is the pinhole derivative
    ``v_true_x * f / (f^2 + dx_world^2)`` (los.py:306) -- it DECREASES off boresight, it is NOT the
    small-angle constant ``v_px*60/f``.  Comparing the IMM against THIS is the honest reference.
    """
    v_true_x = v_px * 60.0                       # px/s
    dx = v_px * float(k)                          # px off the principal point at frame k
    return v_true_x * _F_PX / (_F_PX * _F_PX + dx * dx)


@dataclass(frozen=True)
class CrossingResult:
    v_px_per_frame: float
    mean_true_los_rate_radps: float   # mean of the TRUE per-frame az-rate over the settle window
    n_frames: int
    acquired_frame: int | None
    lock_retention: float             # fraction of post-acquisition frames still LOCKED
    centroid_rmse_px: float
    imm_azrate_rmse_vs_true: float    # |IMM az-rate - TRUE per-frame az-rate|, RMS  (the honest metric)
    imm_azrate_bias_vs_true: float    # signed mean of the same
    imm_azrate_bias_vs_smallangle: float  # signed mean vs the constant small-angle v*60/f (the ARTEFACT)
    mean_lock_quality: float


def run_crossing(v_px: float, *, seed: int = 0, roi_gating: bool = False,
                 settle_frames: int = 8) -> CrossingResult:
    """Run one crossing speed through the real pipeline and measure track-holding + LOS-rate."""
    frames, n = crossing_sequence(v_px, seed=seed)
    pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics(), roi_gating=roi_gating)
    dt = 1.0 / 60.0
    smallangle_rate = v_px * 60.0 / _F_PX        # the (wrong-off-boresight) small-angle reference

    acquired: int | None = None
    locked = 0
    cerr: list[float] = []
    err_true: list[float] = []
    signed_true: list[float] = []
    signed_smallangle: list[float] = []
    true_rates: list[float] = []
    lockq: list[float] = []

    for k, (frame, (tcx, tcy)) in enumerate(frames):
        out = pipe.step(now=k * dt, frame_u16=frame, gyro_omega_xyz=(0.0, 0.0, 0.0), dt=dt)
        if out.locked and out.centroid_px is not None:
            if acquired is None:
                acquired = k
            locked += 1
            cerr.append(math.hypot(out.centroid_px[0] - tcx, out.centroid_px[1] - tcy))
            if out.imm is not None and acquired is not None and k >= acquired + settle_frames:
                tr = true_az_rate_radps(v_px, k)
                true_rates.append(tr)
                err_true.append(abs(out.imm.az_rate_radps - tr))
                signed_true.append(out.imm.az_rate_radps - tr)
                signed_smallangle.append(out.imm.az_rate_radps - smallangle_rate)
                lockq.append(out.imm.lock_quality)

    post = (n - acquired) if acquired is not None else 0
    retention = (locked / post) if post > 0 else 0.0

    def _rmse(v: list[float]) -> float:
        return float(np.sqrt(np.mean(np.square(v)))) if v else float("nan")

    def _mean(v: list[float]) -> float:
        return float(np.mean(v)) if v else float("nan")

    return CrossingResult(
        v_px_per_frame=v_px,
        mean_true_los_rate_radps=_mean(true_rates),
        n_frames=n,
        acquired_frame=acquired,
        lock_retention=retention,
        centroid_rmse_px=_rmse(cerr),
        imm_azrate_rmse_vs_true=_rmse(err_true),
        imm_azrate_bias_vs_true=_mean(signed_true),
        imm_azrate_bias_vs_smallangle=_mean(signed_smallangle),
        mean_lock_quality=_mean(lockq),
    )


def format_study(results: list[CrossingResult]) -> str:
    lines = [
        "High-speed crossing track-holding  (real detect->track->ego->LOS->IMM, gyro=0, FT640 640x512)",
        "  az-rate error is vs the TRUE per-frame angular rate (atan geometry); the last column is the",
        "  bias vs the naive small-angle reference v*60/f -- that column is the OFF-BORESIGHT ARTEFACT.",
        f"  {'v px/fr':>7} {'true_lam':>8} {'acq':>4} {'retain':>7} {'cRMSE':>7} "
        f"{'azR_rmse':>9} {'azR_bias':>9} {'lockQ':>6} {'vs_smAng':>9}",
    ]
    for r in results:
        acq = "none" if r.acquired_frame is None else str(r.acquired_frame)
        lines.append(
            f"  {r.v_px_per_frame:>7.1f} {r.mean_true_los_rate_radps:>8.3f} {acq:>4} "
            f"{r.lock_retention:>7.2f} {r.centroid_rmse_px:>7.3f} "
            f"{r.imm_azrate_rmse_vs_true:>9.4f} {r.imm_azrate_bias_vs_true:>9.4f} "
            f"{r.mean_lock_quality:>6.2f} {r.imm_azrate_bias_vs_smallangle:>9.4f}")
    return "\n".join(lines)


if __name__ == "__main__":
    for roi in (False, True):
        print(f"\n== roi_gating={roi} ==")
        res = [run_crossing(v, roi_gating=roi) for v in (2.0, 5.0, 10.0, 15.0, 20.0)]
        print(format_study(res))
