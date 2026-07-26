"""A3 honesty tests for the bearing-rate / PN guidance law."""

from __future__ import annotations

import math

import pytest

from fpv.guidance.bearing_rate import BearingRateGuidance, GuidanceConfig, ROEAbort
from fpv.seeker.imm import IMMEstimate
from fpv.seeker.looming import LoomingEstimate


def _imm(az_rate: float = 0.01, el_rate: float = 0.0, az: float = 0.02, el: float = 0.0,
         maneuver: bool = False, mp: tuple[float, float] = (0.9, 0.1)) -> IMMEstimate:
    return IMMEstimate(az_rad=az, el_rad=el, az_rate_radps=az_rate, el_rate_radps=el_rate,
                       mode_probs=mp, maneuver_detected=maneuver, frame_id=0)


def _loom(tau: float = 2.0, conf: float = 0.9, sign: int = 1) -> LoomingEstimate:
    return LoomingEstimate(tau_s=tau, tau_confidence=conf, closing_sign=sign,
                           area_smoothed_px=50.0, d_area_dt_px_per_s=10.0)


def test_n_effective_slides_pursuit_to_pn():
    full = BearingRateGuidance(GuidanceConfig()).compute(_imm(), _loom(conf=0.95))
    pursuit = BearingRateGuidance(GuidanceConfig()).compute(_imm(), _loom(conf=0.05))
    assert full.N_effective == pytest.approx(GuidanceConfig().N, abs=1e-6)   # full BRN -> N
    assert pursuit.N_effective == pytest.approx(1.0, abs=1e-6)               # pursuit -> N'=1
    assert pursuit.N_effective < full.N_effective


def test_t_go_from_looming_when_confident():
    cmd = BearingRateGuidance(GuidanceConfig()).compute(_imm(), _loom(tau=2.5, conf=0.9))
    assert cmd.t_go_source == "looming"
    assert cmd.t_go_s == pytest.approx(2.5)


def test_t_go_unobservable_when_confidence_low():
    cmd = BearingRateGuidance(GuidanceConfig()).compute(_imm(), _loom(tau=2.5, conf=0.2))
    assert cmd.t_go_source == "unobservable"
    assert not math.isfinite(cmd.t_go_s)


def test_maneuver_ceiling_is_third_of_achievable():
    cfg = GuidanceConfig()
    cmd = BearingRateGuidance(cfg).compute(_imm(), _loom())
    assert cmd.target_maneuver_ceiling_g == pytest.approx(cfg.achievable_g() / 3.0)


def test_high_crossing_abort_cites_overmatch_rule():
    g = BearingRateGuidance(GuidanceConfig())
    for _ in range(130):                                  # warm past the crossing-warmup guard
        g.compute(_imm(az_rate=0.001), _loom(conf=0.9))
    with pytest.raises(ROEAbort, match="overmatch"):
        g.compute(_imm(az_rate=0.5), _loom(conf=0.1, tau=float("inf")))


def test_non_finite_los_rate_aborts():
    # C6: a malformed IMM LOS rate must fail safe to a labelled ABORT, not poison the command
    g = BearingRateGuidance(GuidanceConfig())
    with pytest.raises(ROEAbort, match="non-finite"):
        g.compute(_imm(az_rate=float("nan")), _loom())


def test_nan_tau_confidence_classified_high_crossing():
    # C6: NaN tau_confidence must read as not-closing -> HIGH_CROSSING (not mislabel/bypass)
    from fpv.guidance.bearing_rate import GeometryClass
    g = BearingRateGuidance(GuidanceConfig())
    for _ in range(130):
        g.compute(_imm(az_rate=0.001), _loom(conf=0.9))
    with pytest.raises(ROEAbort) as exc:
        g.compute(_imm(az_rate=0.5), _loom(conf=float("nan"), tau=float("inf")))
    assert exc.value.geometry == GeometryClass.HIGH_CROSSING


def test_committed_completes_instead_of_aborting():
    # Axis II (mature doctrine): the SAME out-of-envelope geometry that ABORTS pre-commit
    # COMPLETES post-commit -- push through with the clamped best-effort command, don't abort.
    cfg = GuidanceConfig()
    g = BearingRateGuidance(cfg)
    for _ in range(130):                                   # warm past the crossing-warmup guard
        g.compute(_imm(az_rate=0.001), _loom(conf=0.9))
    hot_imm, hot_loom = _imm(az_rate=0.5), _loom(conf=0.1, tau=float("inf"))
    with pytest.raises(ROEAbort):                          # pre-commit: strict gate holds
        g.compute(hot_imm, hot_loom, committed=False)
    cmd = g.compute(hot_imm, hot_loom, committed=True)      # post-commit: no abort
    mag = math.hypot(cmd.a_cmd_az_mps2, cmd.a_cmd_el_mps2)
    assert mag <= cfg.effective_max_a_cmd() + 1e-6         # pushed through, clamped to achievable


def test_committed_still_aborts_on_non_finite():
    # A genuine fault (non-finite LOS) is a HARD self-safe in BOTH phases -- never "push through".
    g = BearingRateGuidance(GuidanceConfig())
    with pytest.raises(ROEAbort, match="non-finite"):
        g.compute(_imm(az_rate=float("nan")), _loom(), committed=True)


def test_terminal_hold_freezes_the_established_course():
    # Ten-tau wall (W4): inside the terminal window the command is FROZEN to the last established
    # collision course, NOT recomputed from the blowing-up lambda_dot (which would saturate/miss).
    g = BearingRateGuidance(GuidanceConfig())
    established = g.compute(_imm(az_rate=0.03), _loom(conf=0.9))       # establish a course
    frozen = g.compute(_imm(az_rate=0.9), _loom(conf=0.9), terminal_hold=True)   # endgame blowup
    assert frozen.terminal_hold is True
    assert frozen.a_cmd_az_mps2 == established.a_cmd_az_mps2           # flew the frozen course
    assert frozen.a_cmd_el_mps2 == established.a_cmd_el_mps2


def test_terminal_hold_failsafe_without_prior_course():
    # No established course yet -> terminal_hold falls through to a normal (non-frozen) compute.
    g = BearingRateGuidance(GuidanceConfig())
    cmd = g.compute(_imm(az_rate=0.03), _loom(conf=0.9), terminal_hold=True)
    assert cmd.terminal_hold is False


def test_latency_lead_advances_the_pursuit_bearing():
    # W5: with a positive lead time the pursuit command aims AHEAD (az + az_rate*lead), so a target
    # drifting right gets a LARGER rightward command than the un-led (stale-bearing) case.
    imm, loom = _imm(az=0.02, az_rate=0.05), _loom(conf=0.05)          # low conf -> pursuit-dominant
    no_lead = BearingRateGuidance(GuidanceConfig(lead_time_s=0.0)).compute(imm, loom)
    led = BearingRateGuidance(GuidanceConfig(lead_time_s=0.1)).compute(imm, loom)
    assert led.a_cmd_az_mps2 > no_lead.a_cmd_az_mps2                    # aims ahead, not at the stale bearing
