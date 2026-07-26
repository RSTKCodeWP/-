"""R2 — robust lambda-dot: NIS-scheduled smoothing + Huber state-update + R pixel-extent inflation.

All behind default-off flags; OFF is bit-identical (the existing suite proves it). These tests
exercise the ON paths: smoothing kills glint jitter while staying responsive; Huber limits a
single-frame state jump without blinding the likelihood; R-extent inflates the bearing channel.
"""

from __future__ import annotations

import statistics

from fpv.seeker.imm import IMMConfig, IMMEstimate, IMMFilter
from fpv.seeker.looming import LoomingEstimate
from fpv.seeker.los import LOSObservation
from fpv.guidance.bearing_rate import BearingRateGuidance, GuidanceConfig


def _imm(az_rate=0.0, fid=0, nis=0.0, alarm=False):
    return IMMEstimate(az_rad=0.0, el_rad=0.0, az_rate_radps=az_rate, el_rate_radps=0.0,
                       mode_probs=(0.9, 0.1), maneuver_detected=False, frame_id=fid,
                       nis=nis, model_wrong_alarm=alarm)


def _looming(tau=2.0, conf=0.8):
    return LoomingEstimate(tau_s=tau, tau_confidence=conf, closing_sign=1,
                           area_smoothed_px=100.0, d_area_dt_px_per_s=10.0)


def _los(az_rate=0.01, fid=0):
    return LOSObservation(az_rad=0.02, el_rad=0.0, az_rate_radps=az_rate, el_rate_radps=0.0,
                          ego_quality=1.0, ego_source="gyro", frame_id=fid)


# ── NIS-scheduled lambda-dot smoothing ───────────────────────────────────────

def test_smoothing_reduces_glint_jitter_when_quiet():
    g_on = BearingRateGuidance(GuidanceConfig(Vc_sched_mps=20.0, nis_lambda_smoothing=True,
                                              lambda_smooth_alpha_quiet=0.2))
    g_off = BearingRateGuidance(GuidanceConfig(Vc_sched_mps=20.0, nis_lambda_smoothing=False))
    a_on, a_off = [], []
    for i in range(30):
        imm = _imm(az_rate=(0.02 if i % 2 == 0 else -0.02), fid=i)   # glint oscillation, quiet NIS
        a_on.append(g_on.compute(imm, _looming()).a_cmd_az_mps2)
        a_off.append(g_off.compute(imm, _looming()).a_cmd_az_mps2)
    assert statistics.pstdev(a_on[6:]) < 0.5 * statistics.pstdev(a_off[6:])


def test_smoothing_opens_loop_on_model_wrong_alarm():
    # with the alarm set, the EMA weight snaps to 1.0 -> the command follows the raw rate (no lag).
    g = BearingRateGuidance(GuidanceConfig(Vc_sched_mps=20.0, nis_lambda_smoothing=True,
                                           lambda_smooth_alpha_quiet=0.05))
    for i in range(10):
        g.compute(_imm(az_rate=0.01, fid=i), _looming())            # settle the EMA at ~0.01
    a_alarm = g.compute(_imm(az_rate=0.05, fid=10, alarm=True), _looming()).a_cmd_az_mps2
    a_ref = BearingRateGuidance(GuidanceConfig(Vc_sched_mps=20.0)).compute(
        _imm(az_rate=0.05, fid=0), _looming()).a_cmd_az_mps2
    assert abs(a_alarm - a_ref) < 1e-9                              # alarm -> raw rate, no smoothing lag


# ── Huber state-update clipping ──────────────────────────────────────────────

def test_huber_limits_state_jump_on_a_glint_spike():
    def run(huber):
        f = IMMFilter(IMMConfig(huber_enabled=huber))
        for i in range(8):
            f.update(_los(az_rate=0.01, fid=i), dt=1 / 60.0)
        return f.update(_los(az_rate=5.0, fid=8), dt=1 / 60.0).az_rate_radps  # huge innovation
    huber_rate = run(True)
    raw_rate = run(False)
    assert abs(huber_rate - 0.01) < abs(raw_rate - 0.01)           # Huber moves the state less


# ── R inflation with pixel extent ────────────────────────────────────────────

def test_r_extent_inflates_bearing_gate_sigma():
    def run(extent):
        f = IMMFilter(IMMConfig(r_extent_k=2.0, r_extent_ref_px=50.0))
        e = None
        for i in range(6):
            e = f.update(_los(fid=i), dt=1 / 60.0, pixel_extent_px=extent)
        return e.gate_sigma_az_rad
    assert run(500.0) > run(10.0)                                  # bigger footprint -> noisier bearing


def test_r_extent_off_is_a_noop():
    # r_extent_k=0 (default): passing a huge extent must not change the gate sigma.
    def run(extent):
        f = IMMFilter(IMMConfig())
        e = None
        for i in range(6):
            e = f.update(_los(fid=i), dt=1 / 60.0, pixel_extent_px=extent)
        return e.gate_sigma_az_rad
    assert run(500.0) == run(10.0)
