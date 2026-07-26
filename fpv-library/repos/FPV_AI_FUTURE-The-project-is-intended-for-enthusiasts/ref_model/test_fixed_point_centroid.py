"""Tests for the fixed-point centroid datapath model (M0).

Pins the two things the PL datapath must satisfy:
  * FAITHFULNESS -- the model's exact-integer float path reproduces detect.py's own centroid
    (so the quantisation numbers below are measured against the trusted detector, not a re-derivation);
  * BUDGET / SIZING -- a modest fixed-point divider (few fractional bits) + bounded accumulators
    keep the centroid inside the S1 sub-pixel budget, on BOTH the 14-bit sim and the 8-bit CVBS scene.
"""

from __future__ import annotations

import numpy as np
import pytest

from fpga.ref_model.golden_vectors import GOLDEN_SCENES
from fpga.ref_model.fixed_point import (
    fx_divide,
    run_centroid_study,
    format_study,
    weighted_centroid,
)


def test_fx_divide_matches_float_within_lsb():
    """The fixed-point divide is within one LSB (2**-F) of the true quotient, trunc <= round."""
    cases = [(12345, 97), (1, 3), (700 * 1800 * 40, 1800 * 40), (2, 7)]
    for num, den in cases:
        exact = num / den
        for f in (4, 8, 12):
            lsb = 2.0 ** (-f)
            t = fx_divide(num, den, f, round_mode="trunc")
            r = fx_divide(num, den, f, round_mode="round")
            assert 0.0 <= exact - t < lsb + 1e-12, f"trunc out of [0,LSB) num={num} den={den} F={f}"
            assert abs(exact - r) <= lsb / 2 + 1e-12, f"round exceeds LSB/2 num={num} den={den} F={f}"


def test_weighted_centroid_exact_on_symmetric_patch():
    """A symmetric weight patch centroids exactly at its geometric centre (sanity of the moments).

    The pedestal of 1 becomes the local background (min within the mask) and is subtracted, leaving
    a symmetric residual weight profile whose first moment is the centre pixel -> (x0+1, y0+1).
    """
    patch = np.array([[1, 2, 1], [2, 5, 2], [1, 2, 1]], dtype=np.uint16)
    mask = np.ones_like(patch, dtype=bool)
    r = weighted_centroid(patch, mask, x0=5, y0=7, frac_bits=None)
    assert not r.degenerate
    assert r.cx == pytest.approx(6.0) and r.cy == pytest.approx(8.0)


@pytest.mark.parametrize("scene", GOLDEN_SCENES, ids=lambda s: s.name)
def test_float_model_reproduces_detector(scene, capsys):
    """The exact-integer float centroid must equal detect.py's centroid (faithfulness).

    ``run_centroid_study`` skips any frame where the reconstructed mask does not reproduce the
    detector's centroid to 1e-6; this test asserts that ENOUGH frames survive that check, i.e.
    the model is faithful on the overwhelming majority of frames.
    """
    res = run_centroid_study(scene)
    with capsys.disabled():
        print("\n" + format_study(res))
    assert res.n_frames >= 20, (
        f"only {res.n_frames} frames reproduced the detector centroid exactly -- the fixed-point "
        f"model is not faithfully tracking detect.py")


@pytest.mark.parametrize("scene", GOLDEN_SCENES, ids=lambda s: s.name)
def test_fixed_point_meets_budget(scene):
    """A small fixed-point divider keeps the centroid in the S1 sub-pixel budget, and the pure
    quantisation error at F=8 is negligible vs the physics."""
    res = run_centroid_study(scene)
    by_f = {q.frac_bits: q for q in res.per_frac}

    # (1) at F=8 the quantisation error vs the float detector is < 1/100 px (well under 2**-8 slack).
    assert by_f[8].rmse_vs_float_px < 0.01, (
        f"{scene.name}: F=8 quantisation RMSE {by_f[8].rmse_vs_float_px:.5f} px too large")

    # (2) at F=8 the centroid still tracks ground truth within the scene budget.
    assert by_f[8].rmse_vs_truth_px <= scene.centroid_rmse_gate_px, (
        f"{scene.name}: F=8 RMSE-vs-truth {by_f[8].rmse_vs_truth_px:.5f} exceeds budget "
        f"{scene.centroid_rmse_gate_px}")

    # (3) the datapath is CHEAP: some F <= 8 already meets budget, accumulators fit in 32 bits.
    assert res.min_frac_bits_in_budget is not None and res.min_frac_bits_in_budget <= 8, (
        f"{scene.name}: needs {res.min_frac_bits_in_budget} fractional bits (expected <= 8)")
    assert res.num_accum_bits <= 32 and res.den_accum_bits <= 32, (
        f"{scene.name}: accumulators exceed 32 bits (num={res.num_accum_bits}, "
        f"den={res.den_accum_bits})")


@pytest.mark.parametrize("scene", GOLDEN_SCENES, ids=lambda s: s.name)
def test_more_fractional_bits_never_worse(scene):
    """Monotonicity sanity: increasing F does not increase the quantisation RMSE vs float."""
    res = run_centroid_study(scene)
    rmses = [q.rmse_vs_float_px for q in sorted(res.per_frac, key=lambda q: q.frac_bits)]
    for lo, hi in zip(rmses, rmses[1:]):
        assert hi <= lo + 1e-9, "adding fractional bits made the divide worse -- model bug"
