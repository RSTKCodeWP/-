"""A5 — honest Monte-Carlo: per-frame latency jitter + swept sustained step-jink.

The delay buffer gains a per-frame uniform jitter (dedicated RNG, so it never perturbs the
plant-noise sequence -> zero jitter is bit-identical). run_monte_carlo's randomize branch now
sweeps latency_jitter_s and target_step_jink_g -- the two stressors the gate names but the old
sweep never exercised (the sinusoidal jink averages to zero).
"""

from __future__ import annotations

import numpy as np

from fpv.guidance.closed_loop import _DelayBuffer
from fpv.guidance.quad_sim import SimConfig


def test_delay_buffer_jitter_varies_effective_delay():
    buf = _DelayBuffer(0.030, jitter_s=0.010, rng=np.random.default_rng(0))
    effs = [buf._effective_delay() for _ in range(30)]
    assert len(set(effs)) > 1                                   # jitter actually varies the delay
    assert all(0.020 <= e <= 0.040 + 1e-9 for e in effs)        # within +/-10 ms of the 30 ms nominal


def test_delay_buffer_zero_jitter_is_constant_and_bit_identical():
    buf = _DelayBuffer(0.030, jitter_s=0.0, rng=np.random.default_rng(0))
    assert set(buf._effective_delay() for _ in range(5)) == {0.030}
    assert _DelayBuffer(0.030)._effective_delay() == 0.030      # no rng / no jitter -> nominal


def test_simconfig_exposes_a5_stressor_fields():
    c = SimConfig(latency_jitter_s=0.008, target_step_jink_g=0.2)
    assert c.latency_jitter_s == 0.008 and c.target_step_jink_g == 0.2
    assert SimConfig().latency_jitter_s == 0.0                  # default off -> bit-identical baseline
