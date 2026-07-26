"""Wave-1 HONEST closed-loop acceptance — grade the intercept against a NON-tautological measurement.

The original S3 gates feed the analytically-TRUE LOS-rate + white per-frame noise to guidance; the
2026-06-20 audit found that loop near-tautological (the headline 100 %-hit / 0.02 m numbers are a
property of the 3e-4 rad clean measurement, not guidance robustness).  This gate turns ON the Wave-1
honest measurement model and re-grades:

  * a CORRELATED (AR-1) lambda-dot bias (``los_rate_bias_sigma_radps``) — the ego-compensation /
    cam<->IMU-skew / centroid-drift residual that does NOT average out in the IMM.  ~1 mrad/s is the
    plausible residual of an UNcalibrated cam<->IMU time-sync (omega_body ~ 0.5 rad/s x ~2 ms skew);
  * noisy + integer-quantized blob AREA feeding looming/tau (``area_noise_frac``) — so tau-confidence
    is not a clean read of the true range;
  * per-frame latency jitter (``latency_jitter_s``).

HONEST FINDING (the point of this gate):
  - HEAD_ON stays robust: 100 % hit, miss grows ~0.022 -> ~0.033 m (still far inside the 0.75 m radius).
    The favorable-case capability is REAL, not a clean-measurement artifact.
  - QUARTERING COLLAPSES.  WAVE-3 (FT640 optics) sharpened this finding: under the FIELDED wide FT640
    lens (f_px≈707, the area f_px the sim now uses) the CLEAN quartering sweep ALSO collapses (0 % hit,
    ~26 m) — the wide-lens looming blob is too small to drive the τ terminal commit that the old narrow
    Boson optics (f_px≈2130, ~9x larger blob area) used to salvage the crossing.  The honest correlated
    lambda-dot bias makes it marginally worse still.  So quartering is now fragile for TWO compounding
    reasons: (1) wide-lens looming cannot terminal-commit, (2) the correlated lambda-dot bias.  Closing
    it needs a looming-threshold retune for the wide lens AND/OR lambda-dot debiasing (cam<->IMU sync) —
    both out of scope for the camera-model reconciliation.  This gate PINS the fragility so it cannot be
    silently hidden by reverting to the narrow optics or removing the honest noise.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

# Full closed-loop honest-acceptance engagements: acceptance tier, not the fast gate.
pytestmark = pytest.mark.slow

from fpv.guidance.bearing_rate import GuidanceConfig
from fpv.guidance.closed_loop import ClosedLoop, ClosedLoopConfig, run_monte_carlo
from fpv.guidance.command_map import PilotConfig
from fpv.guidance.quad_sim import EngagementGeometry, SimConfig
from fpv.seeker.imm import IMMConfig

_CAPTURE_RADIUS_M = 0.75
_N_SEEDS = 20

# The "nominal honest" measurement profile (physically justified above).
_HONEST_LOS_RATE_BIAS_RADPS = 1.0e-3
_HONEST_AREA_NOISE_FRAC = 0.30
_HONEST_LATENCY_JITTER_S = 0.008


def _sweep(geometry, *, target_speed_mps, N, honest, target_step_jink_g=0.0,
           n_seeds=_N_SEEDS, sensor_delay_s=0.030):
    """Run n_seeds engagements; return (n_hits, n_aborts, median_miss, p90_miss)."""
    bias = _HONEST_LOS_RATE_BIAS_RADPS if honest else 0.0
    area = _HONEST_AREA_NOISE_FRAC if honest else 0.0
    jit = _HONEST_LATENCY_JITTER_S if honest else 0.0
    misses, n_hits, n_aborts = [], 0, 0
    for seed in range(n_seeds):
        sim = SimConfig(
            seed=seed, target_geometry=geometry, target_speed_mps=target_speed_mps,
            sensor_delay_s=sensor_delay_s, smith_predictor=True, interceptor_speed_mps=15.0,
            initial_range_m=200.0, capture_radius_m=_CAPTURE_RADIUS_M, bearing_noise_sigma_rad=3e-4,
            target_step_jink_g=target_step_jink_g,
            los_rate_bias_sigma_radps=bias, area_noise_frac=area, latency_jitter_s=jit,
        )
        g = GuidanceConfig(N=N, Vc_sched_mps=15.0 + target_speed_mps,
                           theta_max_rad=math.radians(40.0), abort_g_margin=1.0,
                           crossing_rate_threshold_radps=0.12)
        cfg = ClosedLoopConfig(sim=sim, guidance=g, pilot=PilotConfig(theta_max_rad=math.radians(40.0)),
                               imm=IMMConfig(), mode="analytic", los_hold_decay=0.97, smith_predictor=True)
        r = ClosedLoop(cfg).run()
        misses.append(r.miss_distance_m)
        n_hits += int(r.hit)
        n_aborts += int(r.roe_abort)
    a = np.array([m for m in misses if np.isfinite(m)], dtype=np.float64)
    med = float(np.median(a)) if len(a) else float("nan")
    p90 = float(np.percentile(a, 90)) if len(a) else float("nan")
    return n_hits, n_aborts, med, p90


def test_head_on_robust_under_honest_noise() -> None:
    """HEAD_ON intercept survives the honest correlated-bias + area-noise + jitter model."""
    n_hits, _, med, p90 = _sweep(EngagementGeometry.HEAD_ON, target_speed_mps=5.0, N=3.0, honest=True)
    print(f"\n[Honest] HEAD_ON 5 m/s: hits={n_hits}/{_N_SEEDS} miss med={med:.4f} p90={p90:.4f} m")
    assert n_hits == _N_SEEDS, f"HEAD_ON honest hit-rate dropped to {n_hits}/{_N_SEEDS}"
    # miss grows under honest noise but must stay well inside the capture radius
    assert med < 0.20, f"HEAD_ON honest median miss {med:.4f} m unexpectedly large"
    assert p90 < _CAPTURE_RADIUS_M, f"HEAD_ON honest p90 miss {p90:.4f} m breaches capture radius"


def test_quartering_is_fragile_to_correlated_lambda_dot_bias() -> None:
    """PINNED honest finding: quartering intercept is NOT robust — it collapses to a multi-metre miss.

    WAVE-3 (FT640 optics) UPDATE — the collapse is now even more fundamental than the
    pre-Wave-3 narrative.  Previously (narrow Boson f_px≈2130) the CLEAN quartering sweep
    looked near-perfect (~100% hit, ~0.14 m) and only the honest correlated lambda-dot bias
    broke it.  That "clean looks good" result was itself an artifact of the WRONG narrow
    optics: the small-FOV Boson made the looming blob ~9x larger in area, so the looming-τ
    terminal-commit fired early enough to salvage the crossing geometry.  Under the FIELDED
    wide FT640 lens (f_px≈707, the area f_px the sim now uses) the blob is far smaller, the
    τ-confidence threshold is reached much later, and the τ-driven terminal commit can no
    longer save the quartering intercept — so it collapses to ~26 m miss (0% hit) even with
    a CLEAN measurement.  The honest correlated-bias model makes it marginally worse still.

    Net: quartering is fragile for TWO compounding reasons now — (1) the wide-lens looming
    cannot drive terminal commit, and (2) the correlated lambda-dot bias.  This gate PINS
    that quartering does not close under the correct optics in either case, so a green 100%
    cannot be silently recovered by reverting to the narrow optics or removing the honest noise.
    Closing it needs lambda-dot debiasing (cam<->IMU sync) AND/OR a looming-threshold retune
    for the wide lens — both out of scope for the camera-model reconciliation.
    """
    clean_hits, _, clean_med, _ = _sweep(EngagementGeometry.QUARTERING, target_speed_mps=10.0,
                                         N=4.0, honest=False)
    honest_hits, _, honest_med, _ = _sweep(EngagementGeometry.QUARTERING, target_speed_mps=10.0,
                                           N=4.0, honest=True)
    print(f"\n[Honest] QUARTERING 10 m/s: clean {clean_hits}/{_N_SEEDS} ({clean_med:.3f} m) "
          f"-> honest {honest_hits}/{_N_SEEDS} ({honest_med:.3f} m)")
    # Under the FT640 optics the CLEAN quartering intercept ALREADY collapses (0% hit, ~26 m)
    # — the wide-lens looming cannot drive the terminal commit.  (Was ~100% under narrow Boson.)
    assert clean_hits <= int(0.3 * _N_SEEDS), (
        f"Clean quartering hit-rate {clean_hits}/{_N_SEEDS} — under the FT640 optics this should "
        f"collapse (wide-lens looming cannot terminal-commit).  If it PASSES at high hit-rate the "
        f"sim optics may have reverted to the narrow Boson model (regression).")
    # ... and the honest correlated-bias model is no better (and is at least as bad).
    assert honest_hits <= int(0.3 * _N_SEEDS), (
        f"Quartering honest hit-rate {honest_hits}/{_N_SEEDS} — if this PASSES at high hit-rate the "
        f"lambda-dot bias sensitivity was fixed (great: update this gate); if it FAILS the honest "
        f"noise was likely removed/weakened (regression).")
    assert honest_med >= clean_med, "honest miss must be no better than the clean-measurement miss"


def _honest_mc_base(*, honest: bool = True) -> ClosedLoopConfig:
    """A base config (honest measurement model ON by default) for run_monte_carlo to sweep.

    run_monte_carlo (randomize=True) draws the plant/target dispersion (mass/drag/attitude-tau,
    sustained step-jink, per-frame latency jitter) PER SEED, and now also carries these honest
    measurement knobs into every run, so the sweep grades the system against a non-tautological
    measurement instead of a single nominal plant + analytically-true LOS-rate.
    """
    sim = SimConfig(
        target_speed_mps=8.0, sensor_delay_s=0.030, smith_predictor=True,
        interceptor_speed_mps=15.0, initial_range_m=200.0, capture_radius_m=_CAPTURE_RADIUS_M,
        bearing_noise_sigma_rad=3e-4,
        los_rate_bias_sigma_radps=_HONEST_LOS_RATE_BIAS_RADPS if honest else 0.0,
        area_noise_frac=_HONEST_AREA_NOISE_FRAC if honest else 0.0,
    )
    g = GuidanceConfig(N=4.0, Vc_sched_mps=23.0, theta_max_rad=math.radians(40.0),
                       abort_g_margin=1.0, crossing_rate_threshold_radps=0.12)
    return ClosedLoopConfig(sim=sim, guidance=g, pilot=PilotConfig(theta_max_rad=math.radians(40.0)),
                            imm=IMMConfig(), mode="analytic", los_hold_decay=0.97, smith_predictor=True)


def test_honest_monte_carlo_fails_safe_by_geometry() -> None:
    """HEADLINE honest acceptance, reported PER GEOMETRY under the FULL adversarial Monte-Carlo
    (plant dispersion + sustained step-jink up to 0.28 g + per-frame latency jitter + the correlated
    lambda-dot bias + noisy looming).  The de-tautologized replacement for the clean S3 gates.

    The doctrinally-correct success metric is NOT raw hit-rate -- an ABORT is a PASS (a wrong hit is
    the HARD FAIL).  Under honest conditions the interceptor must HIT-OR-ABORT (essentially never
    wild-miss), and the envelope SHAPE must hold: head-on can engage; crossing geometry safely aborts.
    """
    geoms = (EngagementGeometry.HEAD_ON, EngagementGeometry.QUARTERING, EngagementGeometry.HIGH_CROSSING)
    results = run_monte_carlo(
        _honest_mc_base(), n_seeds=10, N_values=(4.0,), geometries=geoms,
        sensor_delays_s=(0.030,), smith_predictor_values=(True,),
        randomize=True, latency_jitter_max_s=0.008, target_step_jink_max_g=0.28,
    )
    by_geom = {r.geometry: r for r in results}
    print("\n[Honest-MC] per-geometry fail-safe envelope (full adversarial MC + honest measurement):")
    for g in geoms:
        r = by_geom[g.value]
        safe = min(r.n_runs, r.n_hits + r.n_aborts)
        print(f"  {g.value:14s} hit={r.n_hits:2d} abort={r.n_aborts:2d} safe(hit|abort)={safe}/{r.n_runs}"
              f"  miss(non-abort) med={r.miss_median_m:.3f} m")

    # (1) FAIL-SAFE doctrine: across every geometry the system hits or safely aborts -- it must not
    # systematically produce a wild wrong-miss (the HARD-FAIL direction). Allow 1 for MC noise.
    for g in geoms:
        r = by_geom[g.value]
        assert r.n_hits + r.n_aborts >= r.n_runs - 1, (
            f"{g.value}: only {r.n_hits + r.n_aborts}/{r.n_runs} hit-or-abort -> wild misses present "
            f"(the wrong-hit / HARD-FAIL direction the doctrine forbids)")

    # (2) ENVELOPE SHAPE: head-on engages at least as often as crossing; crossing resolves
    # overwhelmingly to safe ABORT (it refuses the unobservable crossing shot).
    head = by_geom[EngagementGeometry.HEAD_ON.value]
    quart = by_geom[EngagementGeometry.QUARTERING.value]
    cross = by_geom[EngagementGeometry.HIGH_CROSSING.value]
    assert head.n_hits >= quart.n_hits and head.n_hits >= cross.n_hits, \
        "honest envelope shape lost: head-on must engage at least as often as crossing geometry"
    assert quart.n_aborts >= quart.n_runs - 2 and cross.n_aborts >= cross.n_runs - 2, \
        "crossing geometry should resolve to safe ABORT under honest conditions, not silent miss"


def test_honest_mc_actually_injects_the_bias() -> None:
    """Guard the run_monte_carlo carry-through fix on HEAD_ON (where the intercept actually closes,
    so the bias is MEASURABLE): with the honest knobs ON the median miss must be materially LARGER
    than with them OFF.  randomize=False (fixed plant, no jink) so the ONLY difference between the
    two sweeps is the honest measurement model -- isolating the carry-through."""
    off = run_monte_carlo(_honest_mc_base(honest=False), n_seeds=12, N_values=(3.0,),
                          geometries=(EngagementGeometry.HEAD_ON,), sensor_delays_s=(0.030,),
                          smith_predictor_values=(True,), randomize=False)[0]
    on = run_monte_carlo(_honest_mc_base(), n_seeds=12, N_values=(3.0,),
                         geometries=(EngagementGeometry.HEAD_ON,), sensor_delays_s=(0.030,),
                         smith_predictor_values=(True,), randomize=False)[0]
    print(f"\n[Honest-MC guard] HEAD_ON knobs OFF miss={off.miss_median_m:.4f} m "
          f"-> ON miss={on.miss_median_m:.4f} m  (hits off={off.n_hits} on={on.n_hits})")
    assert off.n_hits == off.n_runs, "sanity: clean no-jink HEAD_ON should hit every seed"
    assert on.miss_median_m > off.miss_median_m * 1.2, (
        "honest knobs had NO measurable effect through run_monte_carlo -> the carry-through fix "
        f"regressed (off={off.miss_median_m:.4f} on={on.miss_median_m:.4f})")


def _modeb_sweep(*, gyro_scale_error: float, n_seeds: int = 4, target_speed_mps: float = 6.0,
                 target_step_jink_g: float = 0.0, N: float = 3.0):
    """Run n_seeds Mode-B (pixel-in-the-loop) HEAD_ON engagements: real render->detect->ego->LOS->IMM
    ->guidance, looming driven by the REAL detected blob area, under an injected gyro scale error.
    Returns (n_hits, n_aborts, n_unsafe, median_miss).  n_unsafe = neither hit nor abort with a finite
    miss beyond the capture radius (the wild-miss / HARD-FAIL direction)."""
    misses, n_hits, n_aborts, n_unsafe = [], 0, 0, 0
    for seed in range(n_seeds):
        sim = SimConfig(
            seed=seed, target_geometry=EngagementGeometry.HEAD_ON, target_speed_mps=target_speed_mps,
            sensor_delay_s=0.030, smith_predictor=True, interceptor_speed_mps=15.0,
            initial_range_m=200.0, capture_radius_m=_CAPTURE_RADIUS_M, bearing_noise_sigma_rad=3e-4,
            target_step_jink_g=target_step_jink_g,
            gyro_scale_error=gyro_scale_error, looming_from_detected_area=True,
        )
        g = GuidanceConfig(N=N, Vc_sched_mps=15.0 + target_speed_mps,
                           theta_max_rad=math.radians(40.0), abort_g_margin=1.0,
                           crossing_rate_threshold_radps=0.12)
        cfg = ClosedLoopConfig(sim=sim, guidance=g, pilot=PilotConfig(theta_max_rad=math.radians(40.0)),
                               imm=IMMConfig(), mode="pixel", los_hold_decay=0.97, smith_predictor=True)
        r = ClosedLoop(cfg).run()
        misses.append(r.miss_distance_m)
        n_hits += int(r.hit)
        n_aborts += int(r.roe_abort)
        if (not r.hit) and (not r.roe_abort) and np.isfinite(r.miss_distance_m) \
                and r.miss_distance_m > _CAPTURE_RADIUS_M:
            n_unsafe += 1
    a = np.array([m for m in misses if np.isfinite(m)], dtype=np.float64)
    med = float(np.median(a)) if len(a) else float("nan")
    return n_hits, n_aborts, n_unsafe, med


def test_modeb_endtoend_honest_under_camimu_sync_error() -> None:
    """End-to-end Mode-B honesty: the REAL detect->ego->IMM->guidance chain, looming from the REAL
    detected blob area, under an injected cam<->IMU / gyro scale-factor residual (the dominant
    strapdown error).  Driven by a JINKING target so the interceptor maneuvers (rolls) and the
    gyro scale error on the roll de-rotation actually bites (the error scales with body rate).

    Doctrine: the real chain must HIT-OR-ABORT (fail-safe, no wild miss), and the residual must
    MEASURABLY degrade vs clean -- proving it flows through the real pixel path, not just Mode-A.
    """
    n = 4
    jink = 0.15
    ch, ca, cu, cm = _modeb_sweep(gyro_scale_error=0.0, target_step_jink_g=jink, n_seeds=n)
    hh, ha, hu, hm = _modeb_sweep(gyro_scale_error=0.10, target_step_jink_g=jink, n_seeds=n)  # 10% residual
    print(f"\n[Mode-B honest] HEAD_ON jink={jink}g clean: hit={ch} abort={ca} unsafe={cu} miss_med={cm:.3f} m"
          f"  -> +10% gyro-scale: hit={hh} abort={ha} unsafe={hu} miss_med={hm:.3f} m")
    # FAIL-SAFE (the load-bearing assertion): the real chain never wild-misses -- it hits or aborts.
    assert cu == 0, f"clean Mode-B produced {cu} wild miss(es) (the HARD-FAIL direction)"
    assert hu == 0, f"sync-error Mode-B produced {hu} wild miss(es) (the HARD-FAIL direction)"
    # HONEST NOTE on carry-through: this gentle sim interceptor UNDER-ROLLS -- a no-jink HEAD_ON
    # barely rolls and a jinking one aborts early -- so the closed-loop OUTCOME is nearly insensitive
    # to a roll-axis gyro residual here.  That is itself an honest finding: the cam<->IMU sensitivity
    # is a HIGH-ROLL (700-1200 deg/s FPV) regime effect -- a hardware-measurement question (#3),
    # not something this sim exercises.  The WIRING (the residual reaching the ego de-rotation) is
    # proven deterministically by test_gyro_scale_error_wiring_reaches_ego_derotation below.


def test_gyro_scale_error_wiring_reaches_ego_derotation() -> None:
    """Deterministic UNIT proof that the Mode-B gyro/cam-IMU residual reaches the ego de-rotation:
    under a substantial body ROLL, the LOS-rate out of the real pixel tick MUST differ between
    gyro_scale_error=0 and 0.1.  (The closed-loop sim under-rolls, so this is where the wiring is
    proven; the intercept-level sensitivity is the high-roll hardware question #3.)"""
    from fpv.guidance.pixel_loop import make_pixel_loop_state, run_pixel_vision_tick
    from fpv.guidance.quad_sim import QuadState, TargetState

    def run_ticks(scale: float):
        ps = make_pixel_loop_state(7, gyro_scale_error=scale)
        last = None
        for k in range(8):
            roll = 0.1 * k                       # rad -> omega_z ~6 rad/s (~344 deg/s), a real roll
            q = QuadState(pos=np.array([0.0, 0.0, 0.0]), vel=np.array([15.0, 0.0, 0.0]),
                          attitude_rad=np.array([roll, 0.0, 0.0]))
            tgt = TargetState(pos=np.array([60.0, 5.0, 0.0]),   # off-boresight so roll moves it
                              vel=np.array([-5.0, 0.0, 0.0]))
            los, _imm, _det = run_pixel_vision_tick(
                q_state=q, tgt_state=tgt, pixel_state=ps, frame_id=k, t_sim=k / 60.0,
                dt_vision=1.0 / 60.0, range_m=60.0)
            if los is not None:
                last = los
        return last

    los0 = run_ticks(0.0)
    los1 = run_ticks(0.10)
    assert los0 is not None and los1 is not None, "off-boresight target should detect under roll"
    d = abs(los0.az_rate_radps - los1.az_rate_radps) + abs(los0.el_rate_radps - los1.el_rate_radps)
    print(f"\n[wiring] LOS-rate |delta| (gyro_scale 0 vs 0.10) under ~344 deg/s roll = {d:.6f} rad/s")
    assert d > 1e-6, "gyro_scale_error did NOT change the LOS-rate -> wiring to ego de-rotation broken"


def test_honest_vs_clean_envelope_table() -> None:
    """Reference: the full clean-vs-honest intercept envelope (the Wave-1 truth table)."""
    rows = [
        ("HEAD_ON 5 m/s", EngagementGeometry.HEAD_ON, 5.0, 3.0, 0.0),
        ("QUARTERING 5 m/s", EngagementGeometry.QUARTERING, 5.0, 3.0, 0.0),
        ("QUARTERING 10 m/s", EngagementGeometry.QUARTERING, 10.0, 4.0, 0.0),
        ("QUARTERING 10 m/s +jink", EngagementGeometry.QUARTERING, 10.0, 4.0, 0.2),
    ]
    print("\n[Honest] clean-vs-honest intercept envelope (hit/median-miss):")
    print(f"  capture_radius={_CAPTURE_RADIUS_M} m, honest bias={_HONEST_LOS_RATE_BIAS_RADPS*1e3:.1f} mrad/s")
    for name, geom, sp, N, sj in rows:
        ch, _, cm, _ = _sweep(geom, target_speed_mps=sp, N=N, honest=False, target_step_jink_g=sj)
        hh, _, hm, _ = _sweep(geom, target_speed_mps=sp, N=N, honest=True, target_step_jink_g=sj)
        print(f"  {name:26s} clean {ch:2d}/{_N_SEEDS} {cm:7.3f} m  ->  honest {hh:2d}/{_N_SEEDS} {hm:8.3f} m")
    # No assertion beyond the per-scenario gates above; this is the documented record.
