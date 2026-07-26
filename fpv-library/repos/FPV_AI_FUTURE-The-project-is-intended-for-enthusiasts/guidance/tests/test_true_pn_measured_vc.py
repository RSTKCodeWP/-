"""TRUE PN in the closed loop: PN steered by the MEASURED closing velocity, not the scheduled scalar.

The subtense range filter (fpv.seeker.subtense_range), fed the resolved silhouette extent of a
RANGE-DEPENDENT (closing) rendered target, OBSERVES range + closing velocity Vc in Mode B.  With
``SimConfig.measured_vc`` on, guidance runs on that measured Vc instead of ``schedule_Vc_mps``.  This is
the payoff of the whole passive-range channel, demonstrated end-to-end in the loop.
"""

from __future__ import annotations

import math

import pytest

from fpv.guidance.bearing_rate import GuidanceConfig
from fpv.guidance.closed_loop import ClosedLoop, ClosedLoopConfig
from fpv.guidance.command_map import PilotConfig
from fpv.guidance.quad_sim import EngagementGeometry, SimConfig
from fpv.seeker.imm import IMMConfig


def _cfg(*, measured_vc: bool, geometry=EngagementGeometry.HEAD_ON) -> ClosedLoopConfig:
    sim = SimConfig(
        seed=1, guidance_rate_hz=250.0, vision_rate_hz=60.0, sensor_delay_s=0.030, loop_delay_s=0.010,
        theta_max_rad=math.radians(40.0), capture_radius_m=0.75, target_geometry=geometry,
        target_speed_mps=5.0, interceptor_speed_mps=15.0, initial_range_m=200.0, max_sim_time_s=20.0,
        smith_predictor=True, bearing_noise_sigma_rad=3e-4, looming_from_detected_area=True,
        measured_vc=measured_vc, target_span_m=4.0)
    guidance = GuidanceConfig(N=3.0, Vc_sched_mps=20.0, theta_max_rad=math.radians(40.0), abort_g_margin=1.0)
    return ClosedLoopConfig(sim=sim, guidance=guidance,
                            pilot=PilotConfig(theta_max_rad=math.radians(40.0)),
                            imm=IMMConfig(), mode="pixel")


def test_measured_vc_drives_true_pn_head_on():
    r = ClosedLoop(_cfg(measured_vc=True)).run()
    # Fail-safe doctrine: a head-on engagement must HIT (or abort) -- never a wild miss.
    assert r.hit or r.roe_abort
    # The range channel ACTUALLY observed the closing and drove PN (not a silent fallback to schedule).
    assert r.n_measured_vc_ticks > 20, f"measured Vc should have driven PN (ticks={r.n_measured_vc_ticks})"
    # The measured closing velocity is a real, physical closing speed (own airspeed + target, ~15-30 m/s
    # head-on) -- observed, not the assumed scalar.
    assert r.measured_vc_final_mps is not None
    assert 8.0 < r.measured_vc_final_mps < 90.0, f"measured Vc={r.measured_vc_final_mps} implausible"
    assert r.hit, f"true-PN head-on should close the intercept (miss={r.miss_distance_m:.3f} m)"


def test_off_path_keeps_scheduled_vc():
    # measured_vc off -> the range channel is inactive, PN keeps the scheduled Vc (legacy behaviour).
    r = ClosedLoop(_cfg(measured_vc=False)).run()
    assert r.range_source_final == "inactive"
    assert r.n_measured_vc_ticks == 0
    assert r.measured_vc_final_mps is None
    assert r.hit or r.roe_abort
