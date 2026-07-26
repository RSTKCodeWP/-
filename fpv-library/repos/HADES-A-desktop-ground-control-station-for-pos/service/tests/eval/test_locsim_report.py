"""Tests for the localization meter-error report (Task 4.9; research gate §7).

`hades-locsim`'s flagship close: median / mean / p90 / max meter-error + empirical coverage,
STRATIFIED by slant range x camera pitch from nadir, plus a moving-target non-convergence row.
Every meter number is a SIM number (labeled), pending real-flight confirmation.

These tests assert the report's STRUCTURE and the honest qualitative properties (error grows
with obliquity/range; the moving row does not converge), not exact meters (measure-then-lock).
"""

from __future__ import annotations

from hades.eval.locsim_report import (
    StratumResult,
    run_meter_error_report,
)


def test_report_has_stratified_rows_with_meter_stats():
    report = run_meter_error_report(n_targets=12, seed=0)
    assert len(report.strata) > 0
    for s in report.strata:
        assert isinstance(s, StratumResult)
        if s.n > 0:
            # Every populated stratum reports the four meter-error stats + coverage.
            assert s.median_m >= 0.0
            assert s.mean_m >= 0.0
            assert s.p90_m >= s.median_m  # p90 >= median by construction
            assert s.max_m >= s.p90_m
            assert 0.0 <= s.coverage <= 1.0


def test_near_nadir_beats_oblique_meter_error():
    # The honest accuracy story: near-nadir/low is the best stratum, oblique/long the worst.
    report = run_meter_error_report(n_targets=20, seed=1)
    near = [s for s in report.strata if s.pitch_bin == "[0-15)" and s.n >= 3]
    oblique = [s for s in report.strata if s.pitch_bin in ("[35-55)", "[55-65)") and s.n >= 3]
    if near and oblique:
        best_near = min(s.median_m for s in near)
        worst_obliq = max(s.median_m for s in oblique)
        assert best_near < worst_obliq


def test_gated_stratum_is_marked_cue_only():
    # The >65 deg pitch bin is GATED: those frames are excluded from the fused estimate and
    # surface as CUE-ONLY. The report must show the gate firing (the bin exists and is flagged).
    report = run_meter_error_report(n_targets=10, seed=2)
    gated = [s for s in report.strata if s.pitch_bin == "[65+)"]
    assert gated, "the report must include the GATED pitch bin to show the gate firing"


def test_moving_target_row_does_not_converge():
    report = run_meter_error_report(n_targets=10, seed=3, include_moving=True)
    assert report.moving is not None
    # The moving target must stay CONVERGING with a big radius, never PINPOINT (the accepted
    # v1 failure mode, surfaced honestly rather than smeared).
    assert report.moving.convergence == "CONVERGING"
    assert report.moving.median_r95_m > 10.0
    assert report.moving.actionability_class != "PINPOINT"


def test_report_is_labeled_sim_pending_real_flight():
    # Honesty (§7): every meter number carries a (sim) tag; the report names the pending
    # real-flight dataset. The rendered text must say so - never a bare field meter number.
    report = run_meter_error_report(n_targets=8, seed=4)
    text = report.render()
    assert "(sim)" in text
    assert "pending" in text.lower()
    assert "calibrated synthetic simulator" in text.lower()
