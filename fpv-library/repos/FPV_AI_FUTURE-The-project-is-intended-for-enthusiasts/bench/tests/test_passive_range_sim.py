"""Passive ranging by own-maneuver + EKF: observability, honest accuracy, and the anti-overconfidence gate.

The scientific claim under test: a bearings-only seeker cannot resolve range on a straight run, but the
interceptor's OWN maneuver creates parallax that makes range/Vc observable. The safety claim under test: the
EKF's own covariance is NOT a trustworthy confidence signal here (it falsely converges), so the trust decision
is made from the parallax we actually earned.
"""

from __future__ import annotations

import statistics as st

from fpv_ai.bench.passive_range_sim import PARALLAX_MIN_DEG, PassiveCfg, run_passive


def _mean(mode: str, g: float, maneuver: bool, attr: str, seeds: int = 6) -> float:
    runs = [run_passive(PassiveCfg(seed=s, maneuver_mode=mode, maneuver_g=g), maneuver=maneuver)
            for s in range(seeds)]
    return st.mean(getattr(r, attr) for r in runs)


def test_straight_run_cannot_resolve_range():
    """Bearings-only + constant-velocity observer = range unobservable; the estimate stays badly wrong."""
    err = _mean("weave", 0.6, False, "range_err_gate_pct")
    assert err > 50.0, f"a straight run should NOT resolve range, got {err:.1f}% error"


def test_own_maneuver_makes_range_observable():
    """The core result: our own lateral maneuver creates the parallax that resolves range and Vc."""
    straight = _mean("weave", 0.84, False, "range_err_gate_pct")
    weaving = _mean("weave", 0.84, True, "range_err_gate_pct")
    assert weaving < straight / 2.0, (
        f"maneuvering should at least halve the range error ({weaving:.1f}% vs straight {straight:.1f}%)")
    assert weaving < 40.0, f"on-course weave should give coarse-but-real range, got {weaving:.1f}%"


def test_accuracy_is_only_coarse_not_precise():
    """Honesty guard: this buys a COARSE range (~20-35%), not a precise one. If a future change claims
    better than 10% from an on-course weave, it is almost certainly cheating (or falsely converged)."""
    weaving = _mean("weave", 0.84, True, "range_err_gate_pct")
    assert weaving > 10.0, (
        f"on-course weave claiming {weaving:.1f}% range accuracy is too good -- check for a leak of truth")


def test_filter_covariance_is_overconfident_and_must_not_gate_commit():
    """NEGATIVE result, deliberately locked in: on the straight run the EKF's own sigma collapses far below
    its actual error (classic bearings-only false convergence). This is exactly why the commit is gated on
    earned parallax, not on the filter's covariance -- a confident-looking fabrication is worse than an
    admitted one."""
    err = _mean("weave", 0.6, False, "range_err_gate_pct")
    sigma = _mean("weave", 0.6, False, "sigma_r_gate_pct")
    assert sigma < err / 2.0, (
        f"expected the filter to be overconfident on a straight run (sigma {sigma:.1f}% vs error {err:.1f}%); "
        "if this no longer holds the estimator changed -- re-derive the trust gate before trusting sigma")


def test_trust_gate_refuses_range_without_maneuver_and_allows_it_with():
    """The honest gate: no earned parallax -> refuse the range (even though the filter sounds confident)."""
    for s in range(4):
        assert not run_passive(PassiveCfg(seed=s), maneuver=False).trust_range, "straight run must NOT be trusted"
        r = run_passive(PassiveCfg(seed=s, maneuver_g=0.84), maneuver=True)
        assert r.trust_range and r.parallax_deg >= PARALLAX_MIN_DEG, (
            f"a real maneuver should earn trust, parallax={r.parallax_deg:.1f}deg")


def test_more_parallax_gives_better_range_than_less():
    """Parallax is an HONEST predictor of accuracy (unlike the filter's sigma): more of it -> less error."""
    low = _mean("weave", 0.6, True, "range_err_gate_pct")
    high = _mean("turn", 0.6, True, "range_err_gate_pct")
    assert high < low, f"a larger-parallax maneuver should estimate range better ({high:.1f}% vs {low:.1f}%)"
