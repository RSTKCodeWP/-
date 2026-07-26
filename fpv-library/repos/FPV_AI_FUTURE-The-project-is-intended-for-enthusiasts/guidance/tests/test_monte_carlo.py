"""A5: honest Monte-Carlo -- per-seed plant/target randomization."""

from __future__ import annotations

import pytest

# Monte-Carlo acceptance engagements: acceptance tier, not the fast gate.
pytestmark = pytest.mark.slow

from fpv.guidance.closed_loop import ClosedLoopConfig, EngagementGeometry, run_monte_carlo

_COMMON = dict(
    n_seeds=3,
    N_values=(3.0,),
    geometries=(EngagementGeometry.HEAD_ON,),
    sensor_delays_s=(0.03,),
    smith_predictor_values=(True,),
)


def test_randomize_changes_outcomes_vs_fixed_plant():
    base = ClosedLoopConfig()
    det = run_monte_carlo(base, randomize=False, **_COMMON)
    rnd = run_monte_carlo(base, randomize=True, **_COMMON)
    # randomization must actually perturb the runs (otherwise the robustness numbers are
    # measured against a single fixed plant -- the A5 dishonesty the brief flagged)
    assert det[0].miss_distances_m.tolist() != rnd[0].miss_distances_m.tolist()


def test_randomize_off_is_unchanged_default():
    # default behaviour (randomize=False) must be deterministic and identical run-to-run
    base = ClosedLoopConfig()
    a = run_monte_carlo(base, randomize=False, **_COMMON)
    b = run_monte_carlo(base, randomize=False, **_COMMON)
    assert a[0].miss_distances_m.tolist() == b[0].miss_distances_m.tolist()
