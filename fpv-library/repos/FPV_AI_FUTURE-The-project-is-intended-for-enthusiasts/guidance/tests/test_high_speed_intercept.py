"""High-speed closed-loop intercept acceptance (the capstone of the high-speed regime work).

Runs the closed loop at the briefing kinematics (interceptor 150 m/s, threat 83 m/s) with the plant
forward SPEED-HOLD on (so it cruises at 150 instead of the legacy ~56 m/s runaway) and the Vc-SCALED
crossing threshold on, under the honest measurement model (correlated lambda-dot bias + noisy looming
+ per-frame latency jitter + sustained step-jink), reported by the FAIL-SAFE doctrine metric:

    hit OR abort = PASS      (an abort of an infeasible shot is correct)
    wild wrong-miss = HARD-FAIL

Expected envelope (from engagement_regime + the decision gates): HEAD_ON engages and closes;
QUARTERING and HIGH_CROSSING are geometrically infeasible at these speeds (the ~0.84 g airframe wall
is blown past by 5-40x) and must resolve to a safe ABORT, never a silent miss.
"""

from __future__ import annotations

import math

import pytest

# High-speed Monte-Carlo intercept engagements: acceptance tier, not the fast gate.
pytestmark = pytest.mark.slow

from fpv.guidance.closed_loop import ClosedLoopConfig, run_monte_carlo
from fpv.guidance.quad_sim import SimConfig, EngagementGeometry
from fpv.guidance.bearing_rate import GuidanceConfig
from fpv.guidance.command_map import PilotConfig
from fpv.seeker.imm import IMMConfig

_VI, _TGT = 150.0, 83.0
_GEOMS = (EngagementGeometry.HEAD_ON, EngagementGeometry.QUARTERING, EngagementGeometry.HIGH_CROSSING)


def _hs_base() -> ClosedLoopConfig:
    """High-speed base config: speed-hold + Vc-scaled crossing threshold + honest measurement."""
    sim = SimConfig(
        target_speed_mps=_TGT, interceptor_speed_mps=_VI, initial_range_m=250.0,
        capture_radius_m=1.0, sensor_delay_s=0.010, smith_predictor=True,
        speed_hold=True,                              # cruise at 150, not the ~56 m/s runaway
        bearing_noise_sigma_rad=3e-4,
        los_rate_bias_sigma_radps=1e-3, area_noise_frac=0.10, max_sim_time_s=6.0)
    g = GuidanceConfig(
        N=4.0, Vc_sched_mps=_VI + _TGT, theta_max_rad=math.radians(40.0),
        abort_g_margin=1.0, crossing_rate_threshold_radps=0.15,
        vc_scaled_crossing_threshold=True)            # crossing wall scales with Vc
    return ClosedLoopConfig(sim=sim, guidance=g, pilot=PilotConfig(theta_max_rad=math.radians(40.0)),
                            imm=IMMConfig(), mode="analytic", los_hold_decay=0.97, smith_predictor=True)


@pytest.fixture(scope="module")
def envelope():
    res = run_monte_carlo(
        _hs_base(), n_seeds=6, N_values=(4.0,), geometries=_GEOMS,
        sensor_delays_s=(0.010,), smith_predictor_values=(True,),
        randomize=True, latency_jitter_max_s=0.006, target_step_jink_max_g=0.20)
    by = {r.geometry: r for r in res}
    print("\n[high-speed fail-safe envelope] vi=150 tgt=83, speed_hold+vc_scaled, honest knobs:")
    for g in _GEOMS:
        r = by[g.value]
        safe = min(r.n_runs, r.n_hits + r.n_aborts)
        print(f"  {g.value:14} hit={r.n_hits} abort={r.n_aborts} safe={safe}/{r.n_runs} "
              f"miss_med={r.miss_median_m:.3f} m")
    return by


def test_high_speed_is_fail_safe_every_geometry(envelope):
    """HARD gate: no geometry produces a wild wrong-miss -- each run hits or safely aborts."""
    for g in _GEOMS:
        r = envelope[g.value]
        assert r.n_hits + r.n_aborts >= r.n_runs - 1, (
            f"{g.value}: only {r.n_hits + r.n_aborts}/{r.n_runs} hit-or-abort -> a wild wrong-miss "
            f"leaked through (the HARD-FAIL direction the doctrine forbids)")


def test_high_speed_envelope_shape(envelope):
    """HEAD_ON engages and closes; QUARTERING / HIGH_CROSSING resolve to safe ABORT."""
    head = envelope[EngagementGeometry.HEAD_ON.value]
    quart = envelope[EngagementGeometry.QUARTERING.value]
    cross = envelope[EngagementGeometry.HIGH_CROSSING.value]
    assert head.n_hits >= head.n_runs - 1, "HEAD_ON must engage and close at 150 m/s"
    assert head.n_hits >= quart.n_hits and head.n_hits >= cross.n_hits, \
        "envelope shape lost: head-on must engage at least as often as crossing geometry"
    assert quart.n_aborts >= quart.n_runs - 1, "QUARTERING must safely ABORT (infeasible at 150 m/s)"
    assert cross.n_aborts >= cross.n_runs - 1, "HIGH_CROSSING must safely ABORT (infeasible at 150 m/s)"
