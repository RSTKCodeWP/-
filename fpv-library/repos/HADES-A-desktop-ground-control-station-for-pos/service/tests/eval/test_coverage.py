"""Tests for coverage validation (Task 4.5; research gate §5).

Coverage is the flagship's CREDIBILITY check, and its honesty rests entirely on being
anti-circular. The split:

- C1 (matched) proves only the propagation ARITHMETIC: when the fuser's assumed noise equals
  the noise reality injects, ~95% of trials' truth falls in the 95% ellipse.
- C2 (mismatched) proves the uncertainty is HONEST under model error: when reality carries an
  error the fuser does NOT model, coverage degrades in the predicted direction.

The teeth (research gate §5):
1. ONE geometry — sim and fuser both use the same `ray_to_ground` (structural, not tested by
   value here).
2. NO LEAKAGE — the fuser is never handed the sim's realized draws, only a config object.
3. The TIME-SYNC mismatch (out-of-schema) drops coverage and, being systematic, gets WORSE
   with more fused frames: cov(N=30) < cov(N=1). This is the non-tautology proof.
4. The suite must contain an out-of-schema row AND an over-estimate (upward) row, or it is
   back to "mis-tuned Gaussians."

These tests run SMALL trial counts (the matrix in `run_coverage_matrix` uses the full count);
the assertions are on DIRECTION + threshold bands, not exact numbers (which are
measure-then-lock).
"""

from __future__ import annotations

import dataclasses

from hades.eval.coverage import coverage_trial, run_coverage_matrix
from hades.locate.error_model import SensorErrorModel

# --- matched control: ~95% coverage, mean NEES ~ 2 ----------------------------------


def test_matched_coverage_is_about_95_percent():
    # Sim and fuser share the SAME error_model -> the 95% ellipse must cover ~95% of trials.
    row = coverage_trial(
        sim_model=SensorErrorModel(),
        fuser_model=SensorErrorModel(),
        n_frames=20,
        n_trials=200,
        seed=0,
    )
    assert 0.90 <= row.coverage <= 0.99
    # Mean NEES should sit near the state dimension (2) under a correct model.
    assert 1.3 <= row.mean_nees <= 3.0


# --- no leakage: the fuser only ever sees a CONFIG, never the sim's realized draws ---


def test_no_leakage_fuser_takes_only_a_config_object():
    # coverage_trial must accept the fuser's model as a SensorErrorModel (a config), never a
    # realized noise array. Introspect the signature to lock this contract.
    import inspect

    sig = inspect.signature(coverage_trial)
    assert "fuser_model" in sig.parameters
    ann = sig.parameters["fuser_model"].annotation
    # The annotation is the config type (string or class), not an ndarray.
    assert "SensorErrorModel" in str(ann)


# --- sigma underestimate -> coverage DROPS (ellipse too small) ----------------------


def test_sigma_underestimate_drops_coverage():
    # Reality injects 3x the heading jitter the fuser assumes -> the fuser's ellipse is too
    # small -> truth falls outside more often -> coverage strictly below the matched control.
    sim = dataclasses.replace(SensorErrorModel(), yaw_jitter_sigma_deg=60.0)
    fuser = SensorErrorModel()  # assumes 20
    matched = coverage_trial(
        sim_model=fuser, fuser_model=fuser, n_frames=20, n_trials=150, seed=0
    )
    row = coverage_trial(sim_model=sim, fuser_model=fuser, n_frames=20, n_trials=150, seed=1)
    assert row.coverage < matched.coverage - 0.05  # clearly under-covered vs the control


# --- sigma OVERestimate -> coverage rises toward 100% (the two-sided detection row) --


def test_sigma_overestimate_stays_over_covered():
    # Reality is calmer than the fuser assumes -> over-covered (honest-but-useless: R95 too
    # big, but the survivor IS inside). Including this proves the metric is TWO-SIDED, not just
    # "fails downward": over-conservatism reads as ~100% coverage, distinguishable from
    # honest-and-tight. The check is that it is NOT below the matched control and stays high.
    fuser = SensorErrorModel()  # assumes 20
    sim = dataclasses.replace(fuser, yaw_jitter_sigma_deg=12.0)
    matched = coverage_trial(fuser, fuser, n_frames=20, n_trials=200, seed=0)
    row = coverage_trial(sim_model=sim, fuser_model=fuser, n_frames=20, n_trials=200, seed=2)
    assert row.coverage >= matched.coverage - 0.02  # not under-covered; over-conservative
    assert row.coverage >= 0.95


# --- THE HEADLINE: time-sync mismatch drops coverage AND fusion makes it worse -------


def test_time_sync_mismatch_drops_and_worsens_with_fusion():
    # Sim injects a 100 ms pose-behind-video offset; the fuser models none (out-of-schema).
    # The offset is a systematic down-track bias -> coverage drops, and because fusion shrinks
    # the random ellipse while preserving the offset, it gets WORSE with more frames:
    # cov(N=30) < cov(N=1). That monotone signature is the non-tautology proof.
    sim = dataclasses.replace(SensorErrorModel(), t_sync_offset_ms=150.0)
    fuser = SensorErrorModel()  # t_sync_offset_ms = 0 (models no offset)
    cov_n1 = coverage_trial(sim, fuser, n_frames=1, n_trials=150, seed=3).coverage
    cov_n30 = coverage_trial(sim, fuser, n_frames=30, n_trials=150, seed=4).coverage
    # The load-bearing assertion is the MONOTONE fusion-worsens signature: a systematic offset
    # the MC cannot model shrinks the ellipse while the bias persists, so coverage at N=30 is
    # strictly worse than at N=1. This is what distinguishes a bias from a variance error and
    # proves the metric is non-tautological.
    assert cov_n30 < cov_n1
    assert cov_n30 < 0.85  # 150 ms @ 20 m/s = 3 m systematic offset vs ~3 m R95 -> clear drop


# --- the full matrix runs and enforces the meta-assertions --------------------------


def test_matrix_has_required_rows_and_passes_conditions():
    rows = run_coverage_matrix(n_trials=120, seed=10)
    names = {r.name for r in rows}
    # Meta-assertion (§5 tooth 4): an out-of-schema row AND an upward row must be present.
    assert any("time_sync" in n for n in names)
    assert "sigma_overestimate" in names
    assert "matched_control" in names
    by_name = {r.name: r for r in rows}
    # The control passes (arithmetic correct); the out-of-schema time-sync offset collapses
    # coverage (the non-tautology proof). The 200 ms row is the unambiguous collapse; the
    # 100 ms row drops more mildly at this fast near-nadir geometry, and that monotone
    # 50 -> 100 -> 200 ms degradation is itself the signature.
    assert by_name["matched_control"].coverage >= 0.90
    assert by_name["time_sync_200ms"].coverage < 0.50
    assert (
        by_name["time_sync_200ms"].coverage
        < by_name["time_sync_100ms"].coverage
        < by_name["time_sync_50ms"].coverage
    )
