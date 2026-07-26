"""Fixed-point reference model for the PL detect centroid datapath (M0).

WHY THE CENTROID
----------------
The intensity-weighted centroid is the PRIMARY LOS measurement (S1 budget < 0.10 px on the clean
14-bit sim).  Everything downstream -- ego de-rotation, LOS-rate, IMM, guidance -- is driven by it,
so its quantisation error is the first thing an FPGA datapath must be sized for.

THE KEY STRUCTURAL FACT (read out of ``detect.py``)
--------------------------------------------------
In the float detector the centroid is::

    local_bg = min(raw_counts within component)          # integer
    w        = max(raw_counts - local_bg, 0)             # integer weights
    cx       = Σ (x · w) / Σ w                           # Σ are EXACT integers
    cy       = Σ (y · w) / Σ w

Because the raw counts are integers and the pixel indices are integers, the moment SUMS
``num_x = Σ x·w``, ``num_y = Σ y·w`` and ``den = Σ w`` are **exact integers** -- there is no
rounding anywhere in the accumulation.  The ONLY quantisation point in the whole centroid is the
final DIVISION.  So the fixed-point design question reduces to two concrete numbers:

  1. how many FRACTIONAL bits ``F`` the divider must keep so the sub-pixel result stays in budget;
  2. how many INTEGER bits the ``num``/``den`` accumulators must hold so they never overflow.

This module answers both by modelling the divider in fixed-point and replaying it over the golden
scenes, after first proving the model reproduces the float detector bit-for-bit (validation).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import numpy.typing as npt

from fpv.seeker.detect import (
    _CC_HEIGHT,
    _CC_LEFT,
    _CC_TOP,
    _CC_WIDTH,
    _STRUCT_ELEM,
    _connected_components,
    _white_tophat,
    detect_frame,
)
from fpv.seeker.thermal_sim import ThermalSimulator

from fpga.ref_model.golden_vectors import GoldenScene


# ── fixed-point primitives ────────────────────────────────────────────────────
def fx_divide(num: int, den: int, frac_bits: int, *, round_mode: str = "trunc") -> float:
    """Model a fixed-point divider producing ``frac_bits`` fractional bits.

    ``num``, ``den`` are non-negative integers (the exact moment sums).  ``trunc`` models a plain
    restoring divider (floor); ``round`` adds a half-LSB before the shift (round-half-up).  The
    result carries exactly ``frac_bits`` fractional bits, so its worst-case error vs the real
    quotient is < ``2**-frac_bits`` px (trunc) or <= ``2**-(frac_bits+1)`` px (round).
    """
    if den <= 0:
        raise ValueError("den must be > 0")
    shifted = num << frac_bits
    if round_mode == "round":
        q = (shifted + (den >> 1)) // den
    elif round_mode == "trunc":
        q = shifted // den
    else:
        raise ValueError(f"round_mode must be 'trunc' or 'round', got {round_mode!r}")
    return q / float(1 << frac_bits)


@dataclass(frozen=True)
class CentroidResult:
    cx: float
    cy: float
    num_x: int
    num_y: int
    den: int
    degenerate: bool  # total weight <= 0 -> geometric-centre fallback (matches detect.py)

    @property
    def num_bits(self) -> int:
        """Integer bits needed to hold the larger moment accumulator (unsigned)."""
        return max(int(self.num_x).bit_length(), int(self.num_y).bit_length(), 1)

    @property
    def den_bits(self) -> int:
        return max(int(self.den).bit_length(), 1)


def weighted_centroid(
    raw_patch: npt.NDArray[np.integer],
    comp_mask: npt.NDArray[np.bool_],
    x0: int,
    y0: int,
    *,
    frac_bits: Optional[int] = None,
    round_mode: str = "trunc",
) -> CentroidResult:
    """Intensity-weighted centroid, EXACT-integer moments + (optional) fixed-point division.

    ``frac_bits=None`` -> exact float division (the faithful replica of ``detect.py``).
    ``frac_bits=F``    -> the moment sums are still exact integers; only the final divide is
                          quantised to F fractional bits (the PL datapath model).
    """
    patch = raw_patch.astype(np.int64)
    masked = patch[comp_mask]
    if masked.size == 0:
        return CentroidResult(x0, y0, 0, 0, 0, degenerate=True)

    local_bg = int(masked.min())
    bg_sub = np.maximum(patch - local_bg, 0)
    w = (bg_sub * comp_mask.astype(np.int64))          # integer weights, 0 outside the component

    den = int(w.sum())
    h, wd = patch.shape
    ys = np.arange(y0, y0 + h, dtype=np.int64)[:, None]
    xs = np.arange(x0, x0 + wd, dtype=np.int64)[None, :]
    num_x = int((xs * w).sum())
    num_y = int((ys * w).sum())

    if den <= 0:                                        # all-equal patch: detect.py falls back here
        return CentroidResult(x0 + wd / 2.0, y0 + h / 2.0, num_x, num_y, den, degenerate=True)

    if frac_bits is None:
        cx = num_x / den
        cy = num_y / den
    else:
        cx = fx_divide(num_x, den, frac_bits, round_mode=round_mode)
        cy = fx_divide(num_y, den, frac_bits, round_mode=round_mode)
    return CentroidResult(cx, cy, num_x, num_y, den, degenerate=False)


# ── bit-faithful extraction of a blob's centroid inputs from a frame ──────────
def reconstruct_blob_inputs(
    frame_u16: npt.NDArray[np.uint16],
    threshold_counts: float,
    bbox: tuple[int, int, int, int],
) -> Optional[tuple[npt.NDArray[np.uint16], npt.NDArray[np.bool_], int, int]]:
    """Rebuild ``(raw_patch, comp_mask, x0, y0)`` for the blob at ``bbox``, bit-faithful to detect.

    Reuses detect.py's OWN top-hat / threshold / connected-components helpers, so the reconstructed
    component mask is identical to the one detect used internally (default path: no ROI / region /
    MPCM / directional).  ``threshold_counts`` is the value detect computed for this frame.
    """
    frame_f = frame_u16.astype(np.float32)
    tophat = _white_tophat(frame_f, _STRUCT_ELEM)
    binary = tophat > threshold_counts
    num_labels, labeled, stats = _connected_components(binary)

    x0, y0, w, h = bbox
    match = None
    for lab in range(1, num_labels):
        if (int(stats[lab, _CC_LEFT]), int(stats[lab, _CC_TOP]),
                int(stats[lab, _CC_WIDTH]), int(stats[lab, _CC_HEIGHT])) == (x0, y0, w, h):
            match = lab
            break
    if match is None:
        return None
    sl = (slice(y0, y0 + h), slice(x0, x0 + w))
    comp_mask = labeled[sl] == match
    raw_patch = frame_u16[sl]
    return raw_patch, comp_mask, x0, y0


# ── quantisation study over a golden scene ────────────────────────────────────
@dataclass(frozen=True)
class QuantStats:
    frac_bits: int
    rmse_vs_float_px: float     # fixed vs the float detector (pure quantisation error)
    rmse_vs_truth_px: float     # fixed vs physical ground truth (what actually matters)
    max_abs_err_px: float       # worst single-frame |fixed - float|


@dataclass(frozen=True)
class StudyResult:
    scene: str
    n_frames: int
    float_rmse_vs_truth_px: float
    per_frac: tuple[QuantStats, ...]
    num_accum_bits: int         # integer bits the Σ x·w accumulator must hold (observed max)
    den_accum_bits: int         # integer bits the Σ w accumulator must hold (observed max)
    min_frac_bits_in_budget: Optional[int]
    budget_px: float


def run_centroid_study(
    scene: GoldenScene,
    frac_bits_sweep: tuple[int, ...] = (2, 4, 6, 8, 10, 12),
    *,
    round_mode: str = "trunc",
) -> StudyResult:
    """Replay the best-blob centroid over the scene at each ``frac_bits`` and size the datapath."""
    sim = ThermalSimulator(scene.cfg)
    frames = sim.generate(scene.n_frames)

    from fpv.seeker.detect import ThresholdState
    ts = ThresholdState()

    float_errs_truth: list[float] = []
    fx_err_float: dict[int, list[float]] = {f: [] for f in frac_bits_sweep}
    fx_err_truth: dict[int, list[float]] = {f: [] for f in frac_bits_sweep}
    max_num_bits = 1
    max_den_bits = 1
    n_used = 0

    for frame_u16, gt in frames:
        blobs, ts = detect_frame(
            frame_u16, cam_temp_c=gt.cam_temp_c, ffc_state=gt.ffc_state,
            threshold_state=ts, frame_id=gt.frame_id,
            min_snr=scene.min_snr, min_area_px=scene.min_area_px)
        if gt.ffc_state != "READY" or not gt.is_target_visible or not blobs:
            continue
        best = blobs[0]
        rec = reconstruct_blob_inputs(frame_u16, ts.threshold_counts, best.bbox)
        if rec is None:
            continue
        raw_patch, comp_mask, x0, y0 = rec

        flt = weighted_centroid(raw_patch, comp_mask, x0, y0, frac_bits=None)
        # validation: the float replica must equal detect's own centroid (proves faithfulness)
        if (abs(flt.cx - best.centroid_px[0]) > 1e-6 or abs(flt.cy - best.centroid_px[1]) > 1e-6):
            # mask mismatch (e.g. two components in bbox) -> skip rather than pollute the study
            continue
        n_used += 1
        max_num_bits = max(max_num_bits, flt.num_bits)
        max_den_bits = max(max_den_bits, flt.den_bits)

        gx, gy = gt.target_centroid_px
        float_errs_truth.append(np.hypot(flt.cx - gx, flt.cy - gy))

        for f in frac_bits_sweep:
            fx = weighted_centroid(raw_patch, comp_mask, x0, y0, frac_bits=f, round_mode=round_mode)
            fx_err_float[f].append(np.hypot(fx.cx - flt.cx, fx.cy - flt.cy))
            fx_err_truth[f].append(np.hypot(fx.cx - gx, fx.cy - gy))

    def _rmse(v: list[float]) -> float:
        return float(np.sqrt(np.mean(np.square(v)))) if v else float("nan")

    per_frac = tuple(
        QuantStats(
            frac_bits=f,
            rmse_vs_float_px=_rmse(fx_err_float[f]),
            rmse_vs_truth_px=_rmse(fx_err_truth[f]),
            max_abs_err_px=(max(fx_err_float[f]) if fx_err_float[f] else float("nan")),
        )
        for f in frac_bits_sweep
    )
    min_in_budget = next((q.frac_bits for q in per_frac
                          if q.rmse_vs_truth_px <= scene.centroid_rmse_gate_px), None)

    return StudyResult(
        scene=scene.name,
        n_frames=n_used,
        float_rmse_vs_truth_px=_rmse(float_errs_truth),
        per_frac=per_frac,
        num_accum_bits=max_num_bits,
        den_accum_bits=max_den_bits,
        min_frac_bits_in_budget=min_in_budget,
        budget_px=scene.centroid_rmse_gate_px,
    )


def format_study(res: StudyResult) -> str:
    lines = [
        f"[{res.scene}] centroid datapath sizing  (n={res.n_frames} frames, budget "
        f"{res.budget_px} px, round=trunc)",
        f"  float detector RMSE vs truth : {res.float_rmse_vs_truth_px:.5f} px",
        f"  accumulator width            : num(Σx·w) {res.num_accum_bits} bits, "
        f"den(Σw) {res.den_accum_bits} bits",
        f"  {'F bits':>6} {'RMSE vs float':>14} {'RMSE vs truth':>14} {'max|Δ| vs float':>16}",
    ]
    for q in res.per_frac:
        lines.append(f"  {q.frac_bits:>6} {q.rmse_vs_float_px:>14.6f} "
                     f"{q.rmse_vs_truth_px:>14.6f} {q.max_abs_err_px:>16.6f}")
    lines.append(f"  minimal F within budget      : {res.min_frac_bits_in_budget}")
    return "\n".join(lines)


def _main() -> None:
    from fpga.ref_model.golden_vectors import GOLDEN_SCENES
    for scene in GOLDEN_SCENES:
        print(format_study(run_centroid_study(scene)))
        print()


if __name__ == "__main__":
    _main()
