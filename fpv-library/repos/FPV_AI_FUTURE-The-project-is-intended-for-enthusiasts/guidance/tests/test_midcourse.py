"""Tests for midcourse lead establishment with a reserve, near-ballistic terminal (midcourse.py)."""

from __future__ import annotations

import math

from fpv.guidance.midcourse import MidcourseConfig, MidcourseGuidance, MidcoursePhase

CFG = MidcourseConfig()   # N_mid=4, theta_max=40deg, margin=3, handover t_go 1.5 / range 60, trim 0.15
A_MAX = CFG.a_max_mps2()   # ~8.23 m/s^2


def _c(az_rate, el_rate=0.0, vc=200.0, t_go=5.0, range_m=300.0):
    return MidcourseGuidance(CFG).compute(az_rate_radps=az_rate, el_rate_radps=el_rate,
                                          vc_mps=vc, t_go_s=t_go, range_m=range_m)


def test_gwall_and_margin_physics():
    r = _c(0.05)
    assert r.lambda_dot_wall_radps == A_MAX / (CFG.N_mid * 200.0)         # a_max/(N*Vc)
    assert r.lead_margin == r.lambda_dot_wall_radps / 0.05                # wall / |lambda_dot|
    assert r.lead_established is False                                     # 0.05 >> wall -> no reserve yet


def test_midcourse_far_uses_full_authority_to_set_the_lead():
    r = _c(0.05, t_go=5.0, range_m=300.0)      # far, high LOS rate
    assert r.phase is MidcoursePhase.MIDCOURSE
    # PN demand N*Vc*lambda_dot = 40 m/s^2 is clamped to the full airframe a_max (aggressive lead-null).
    assert math.isclose(abs(r.a_cmd_az_mps2), A_MAX, rel_tol=1e-9)


def test_ballistic_terminal_when_lead_established_with_reserve():
    # lambda_dot below wall/3 -> reserve met; close -> BALLISTIC terminal with only a tiny trim.
    wall = A_MAX / (CFG.N_mid * 200.0)
    lam = wall / 5.0                            # margin 5 >= 3
    r = _c(lam, t_go=0.5, range_m=50.0)
    assert r.phase is MidcoursePhase.BALLISTIC_TERMINAL and r.lead_established is True
    # command capped to the tiny ballistic trim (terminal_trim_frac * a_max), NOT full authority.
    assert abs(r.a_cmd_az_mps2) <= CFG.terminal_trim_frac * A_MAX + 1e-9


def test_terminal_best_effort_when_lead_not_established_is_honest():
    # close but the lead was NOT nulled to the reserve -> honest push-through at full authority.
    r = _c(0.05, t_go=0.5, range_m=50.0)
    assert r.phase is MidcoursePhase.TERMINAL_BEST_EFFORT and r.lead_established is False
    assert math.isclose(abs(r.a_cmd_az_mps2), A_MAX, rel_tol=1e-9)        # not the tiny trim -- pushes through


def test_command_nulls_the_los_rate_and_vanishes_at_collision_course():
    # a_cmd = N*Vc*lambda_dot: same sign as the LOS rate (matches target angular motion) and -> 0 as
    # lambda_dot -> 0, i.e. it converges to the collision course.
    big = _c(0.02)
    small = _c(0.002)
    assert abs(small.a_cmd_az_mps2) < abs(big.a_cmd_az_mps2)              # smaller residual -> smaller command
    assert (big.a_cmd_az_mps2 > 0) == (0.02 > 0)                          # sign follows the LOS rate


def test_high_speed_shrinks_the_gwall_so_more_reserve_is_needed():
    # At higher Vc the g-wall LOS rate is smaller -> the SAME lambda_dot has less reserve (harder).
    slow = _c(0.01, vc=50.0)
    fast = _c(0.01, vc=250.0)
    assert fast.lambda_dot_wall_radps < slow.lambda_dot_wall_radps
    assert fast.lead_margin < slow.lead_margin


def test_closed_loop_establishes_lead_with_reserve_before_ballistic_terminal():
    # Deterministic 2D closing engagement (Vi=150, Vt=80, 150 m cross-offset). The midcourse must NULL the
    # LOS rate and establish the reserve WHILE STILL IN MIDCOURSE, so the near-ballistic terminal inherits a
    # tiny residual -- the whole point of "set the lead with a large reserve, treat the terminal as ballistic".
    import numpy as np
    g = MidcourseGuidance(MidcourseConfig())
    Vi, Vt, dt = 150.0, 80.0, 0.005
    ip = np.array([0.0, 0.0]); iv = np.array([0.0, Vi])
    tp = np.array([150.0, 1600.0]); tv = np.array([0.0, -Vt])
    prev = None
    established_in_midcourse = False
    ballistic_at_terminal = False
    for _ in range(4000):
        rel = tp - ip; rng = float(np.linalg.norm(rel))
        if rng < 3.0:
            break
        vc = Vi + Vt; t_go = rng / vc
        bearing = math.atan2(rel[0], rel[1])
        lam = (bearing - prev) / dt if prev is not None else 0.0
        prev = bearing
        c = g.compute(az_rate_radps=lam, el_rate_radps=0.0, vc_mps=vc, t_go_s=t_go, range_m=rng)
        if c.phase is MidcoursePhase.MIDCOURSE and c.lead_established:
            established_in_midcourse = True
        if c.phase is MidcoursePhase.BALLISTIC_TERMINAL:
            ballistic_at_terminal = True
        iv[0] += c.a_cmd_az_mps2 * dt
        iv = iv / np.linalg.norm(iv) * Vi          # cruise: hold speed (fixed-wing/rocket)
        ip = ip + iv * dt; tp = tp + tv * dt
    assert established_in_midcourse, "the lead must be set with reserve while the airframe can still turn"
    assert ballistic_at_terminal, "with the lead established, the terminal must be ballistic (tiny trim)"
    assert rng < 5.0, f"the established collision course must close (closest approach {rng:.1f} m)"
