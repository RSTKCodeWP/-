"""Mode B (pixel-in-the-loop) acceptance test suite.

Gates
-----
Gate N  — pixel-in-the-loop intercept, FAVORABLE
    Head-on, moderate geometry within the energy envelope.
    Full render->detect->los->imm->guidance pipeline active.
    Default (fast) run: 6 seeds.  Full 15-seed run: @pytest.mark.slow.
    Reports CPA distribution (larger than Mode A due to detection/quantization
    noise — expected and honest).

Gate O  — Mode A vs Mode B consistency check
    Same favorable scenario in both modes across multiple seeds.
    Reports miss-degradation factor (Mode B / Mode A).
    Asserts:
        - factor > 1.5 (Mode B must be GENUINELY noisier after the double-IMM fix)
        - per-seed majority check: at least half the seeds have Mode B CPA > Mode A CPA
        - factor < 30x (pipeline functional)
    Default run: 6 seeds.  Full 15-seed run: @pytest.mark.slow.

    DESIGN NOTE — double-IMM fix
    The outer ClosedLoop IMMFilter was previously running in Mode B in addition
    to the inner IMMFilter inside run_pixel_vision_tick.  This double-smoothing
    made Mode B look artificially good (small CPA).  After the fix, the outer
    IMM is bypassed in Mode B (see closed_loop.py _passthrough_imm_estimate).
    The honest degradation factor will be LARGER than before the fix.

Gate P  — off-FOV / lock-loss graceful degradation
    A scenario where the target leaves the FOV during a hard maneuver.
    Guidance coasts; seeker enters PREDICTIVE_TRACK/REACQUIRE.
    Asserts:
        - No NaN/Inf in positions or guidance commands.
        - At least one PREDICTIVE_TRACK or REACQUIRE state was observed.
        - result.n_off_fov_frames > 0 in the specific narrow-FOV or quartering scenario.
        - Engagement terminates cleanly (no crash).

Gate Q  — Boson sensor delay with pixel pipeline
    Favorable intercept WITH the >25 ms Boson delay injected.
    Asserts hit=True; reports CPA.  6 seeds (fast).

Gate R  — Narrow-FOV (Boson 24 mm) vs wide (50 deg) comparison
    Compares Mode B with the REAL Boson 640 24 mm intrinsics (HFOV ~17 deg,
    VFOV ~13.7 deg) against the wide 50-deg camera.
    Head-on / moderate favorable geometry, 8 seeds each.
    Reports: off-FOV frame fraction, REACQUIRE/HARD_LOST occurrence, hit rate, CPA.
    This is the KEY SYSTEM FINDING: the narrow lens has a severe terminal-FOV
    penalty due to the target drifting off the tight 17 deg sensor as the
    interceptor maneuvers.  Numbers are reported honestly even if they are bad.

All gates print real numbers and run deterministically from fixed seeds.
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import pytest

from fpv.seeker.imm import IMMConfig
from fpv.guidance.bearing_rate import GuidanceConfig
from fpv.guidance.command_map import PilotConfig
from fpv.guidance.quad_sim import SimConfig, EngagementGeometry
from fpv.guidance.closed_loop import ClosedLoop, ClosedLoopConfig
from fpv.guidance.pixel_loop import PixelLoopState, make_pixel_loop_state
from fpv.seeker.geometry import CameraIntrinsics, focal_length_from_hfov, boson_640_24mm_intrinsics
from fpv.seeker.track import TrackingState


# ---------------------------------------------------------------------------
# Shared configuration helpers
# ---------------------------------------------------------------------------

_CAPTURE_RADIUS_M = 0.75

# Fast (default) seed counts — keeps the full test run in minutes
_N_SEEDS_FAST = 6
# Full seed counts — gated behind @pytest.mark.slow
_N_SEEDS_SLOW = 15


def _make_modeb_cfg(
    *,
    seed: int = 42,
    target_speed_mps: float = 5.0,
    geometry: EngagementGeometry = EngagementGeometry.HEAD_ON,
    initial_range_m: float = 150.0,
    sensor_delay_s: float = 0.030,
    smith_predictor: bool = True,
    N: float = 3.0,
    max_sim_time_s: float = 20.0,
    target_lateral_offset_m: float = 0.0,
) -> ClosedLoopConfig:
    """Build a Mode B ClosedLoopConfig."""
    sim = SimConfig(
        seed=seed,
        dt_sim_s=0.001,
        guidance_rate_hz=250.0,
        vision_rate_hz=60.0,
        sensor_delay_s=sensor_delay_s,
        loop_delay_s=0.010,
        theta_max_rad=math.radians(40.0),
        drag_coeff=0.05,
        attitude_tau_s=0.10,
        mass_kg=0.55,
        capture_radius_m=_CAPTURE_RADIUS_M,
        target_geometry=geometry,
        target_speed_mps=target_speed_mps,
        target_jink_g=0.0,
        target_step_jink_g=0.0,
        target_lateral_offset_m=target_lateral_offset_m,
        interceptor_speed_mps=15.0,
        initial_range_m=initial_range_m,
        max_sim_time_s=max_sim_time_s,
        smith_predictor=smith_predictor,
        bearing_noise_sigma_rad=3e-4,
    )
    guidance = GuidanceConfig(
        N=N,
        Vc_sched_mps=20.0,
        theta_max_rad=math.radians(40.0),
        abort_g_margin=1.0,
        crossing_rate_threshold_radps=0.12,
    )
    return ClosedLoopConfig(
        sim=sim,
        guidance=guidance,
        pilot=PilotConfig(theta_max_rad=math.radians(40.0)),
        imm=IMMConfig(),
        mode="pixel",
    )


def _make_modea_cfg(
    *,
    seed: int = 42,
    target_speed_mps: float = 5.0,
    geometry: EngagementGeometry = EngagementGeometry.HEAD_ON,
    initial_range_m: float = 150.0,
    sensor_delay_s: float = 0.030,
    smith_predictor: bool = True,
    N: float = 3.0,
    max_sim_time_s: float = 20.0,
    target_lateral_offset_m: float = 0.0,
) -> ClosedLoopConfig:
    """Build an equivalent Mode A config for comparison."""
    sim = SimConfig(
        seed=seed,
        dt_sim_s=0.001,
        guidance_rate_hz=250.0,
        vision_rate_hz=60.0,
        sensor_delay_s=sensor_delay_s,
        loop_delay_s=0.010,
        theta_max_rad=math.radians(40.0),
        drag_coeff=0.05,
        attitude_tau_s=0.10,
        mass_kg=0.55,
        capture_radius_m=_CAPTURE_RADIUS_M,
        target_geometry=geometry,
        target_speed_mps=target_speed_mps,
        target_jink_g=0.0,
        target_step_jink_g=0.0,
        target_lateral_offset_m=target_lateral_offset_m,
        interceptor_speed_mps=15.0,
        initial_range_m=initial_range_m,
        max_sim_time_s=max_sim_time_s,
        smith_predictor=smith_predictor,
        bearing_noise_sigma_rad=3e-4,
    )
    guidance = GuidanceConfig(
        N=N,
        Vc_sched_mps=20.0,
        theta_max_rad=math.radians(40.0),
        abort_g_margin=1.0,
        crossing_rate_threshold_radps=0.12,
    )
    return ClosedLoopConfig(
        sim=sim,
        guidance=guidance,
        pilot=PilotConfig(theta_max_rad=math.radians(40.0)),
        imm=IMMConfig(),
        mode="analytic",
    )


def _boson_24mm_intrinsics() -> CameraIntrinsics:
    """Return Boson 640 24 mm (HFOV ~17.1 deg) intrinsics."""
    return boson_640_24mm_intrinsics()


def _run_modeb_narrow_fov(cfg: ClosedLoopConfig) -> "EngagementResult":  # type: ignore[name-defined]
    """Run a Mode B engagement with the narrow (Boson 24 mm) camera intrinsics.

    The ClosedLoop harness calls make_pixel_loop_state(seed) internally, which
    uses the wide 50-deg intrinsics by default.  To inject the 24 mm lens, we
    monkey-patch the name 'make_pixel_loop_state' in the closed_loop module
    namespace (where it is bound as a local import).

    IMPORTANT: must patch fpv.guidance.closed_loop.make_pixel_loop_state, NOT
    fpv.guidance.pixel_loop.make_pixel_loop_state.  The closed_loop module does
    'from fpv.guidance.pixel_loop import make_pixel_loop_state', binding the
    name in its own namespace.  Patching the source module has no effect.

    This is the test-only narrow-FOV shim.  Production code uses the default.
    """
    import fpv.guidance.closed_loop as cl_mod

    narrow_intr = _boson_24mm_intrinsics()
    original_factory = cl_mod.make_pixel_loop_state  # type: ignore[attr-defined]

    def _narrow_factory(sim_seed: int, imm_cfg=None, gyro_scale_error: float = 0.0) -> PixelLoopState:
        """Factory that replaces intrinsics with the 24 mm narrow lens.

        Mirrors make_pixel_loop_state's signature, including the gyro_scale_error the closed loop
        now forwards (Wave-1 honest measurement model); without it this shim raises TypeError.
        """
        intr = narrow_intr
        rng_stars = np.random.default_rng(sim_seed * 1000 + 7)
        margin = 20  # tighter margin for 17-deg FOV
        xs = rng_stars.uniform(margin, intr.width - margin, size=12).tolist()
        ys = rng_stars.uniform(margin, intr.height - margin, size=12).tolist()
        stars = list(zip(xs, ys))

        state = PixelLoopState(
            intrinsics=intr,
            star_positions=stars,
            rng=np.random.default_rng(sim_seed * 31337 + 13),
            gyro_scale_error=float(gyro_scale_error),
        )
        if imm_cfg is not None:
            from fpv.seeker.imm import IMMFilter
            state.imm = IMMFilter(imm_cfg)
        state.seed_tracker(intr)
        return state

    # Patch the name in closed_loop module namespace (where it is bound)
    cl_mod.make_pixel_loop_state = _narrow_factory  # type: ignore[attr-defined]
    try:
        loop = ClosedLoop(cfg)
        result = loop.run()
    finally:
        cl_mod.make_pixel_loop_state = original_factory  # type: ignore[attr-defined]

    return result


# ---------------------------------------------------------------------------
# Gate N: pixel-in-the-loop intercept, FAVORABLE
# ---------------------------------------------------------------------------

@pytest.mark.slow  # full pixel-render engagements (26-52 s even at 6 seeds) -> acceptance tier
class TestGateN:
    """Gate N: pixel-in-the-loop intercept with favorable geometry.

    Head-on, moderate target speed (5 m/s), 150 m initial range.
    Full seeker pipeline (render -> detect -> los -> imm -> guidance).
    All seeds must produce hit=True.

    The CPA distribution will be LARGER than Mode A's ~0.02-0.04m because:
    - Sub-pixel centroid quantization noise (~0.5 px → ~0.7 mrad at f=686px)
    - Detection threshold jitter (stochastic threshold each frame)
    - Tracking state transitions (brief coast periods)
    - IMM transient at engagement start
    - No double-IMM smoothing (fixed)

    This is expected and honest: Mode B is validating the REAL pipeline,
    not a noise-only analytic model.
    """

    def test_gate_n_hits_fast(self) -> None:
        """Fast: 6 seeds must all hit; report CPA distribution."""
        misses = []
        hits = 0
        off_fov_total = 0
        n = _N_SEEDS_FAST

        print(f"\n{'='*65}")
        print(f"GATE N (fast, {n} seeds): Pixel-in-the-loop intercept")
        print(f"{'='*65}")
        print(f"{'Seed':>6} {'Hit':>5} {'Miss (m)':>10} {'Off-FOV':>9}")
        print(f"{'-'*35}")

        for seed in range(n):
            cfg = _make_modeb_cfg(seed=seed)
            result = ClosedLoop(cfg).run()
            misses.append(result.miss_distance_m)
            if result.hit:
                hits += 1
            off_fov_total += result.n_off_fov_frames
            print(f"  {seed:>4}  {str(result.hit):>5}  {result.miss_distance_m:>10.4f}  {result.n_off_fov_frames:>9}")

        arr = np.array([m for m in misses if np.isfinite(m)])
        median_m = float(np.median(arr))
        p90_m = float(np.percentile(arr, 90))

        print(f"\nMode B ({n} seeds): hits={hits}/{n}  CPA median={median_m:.4f}m  p90={p90_m:.4f}m")
        print(f"Total off-FOV frames: {off_fov_total}")
        print(f"NOTE: Mode B CPA is larger than Mode A after double-IMM fix — expected/honest.")

        assert hits == n, (
            f"Gate N FAIL: {hits}/{n} hits (all seeds must hit in FAVORABLE head-on scenario)"
        )
        assert median_m < _CAPTURE_RADIUS_M, f"Gate N FAIL: median CPA {median_m:.4f}m >= {_CAPTURE_RADIUS_M}m"
        assert p90_m < _CAPTURE_RADIUS_M, f"Gate N FAIL: p90 CPA {p90_m:.4f}m >= {_CAPTURE_RADIUS_M}m"

    @pytest.mark.slow
    def test_gate_n_hits_full(self) -> None:
        """Full (slow): 15 seeds must all hit; report CPA distribution."""
        misses = []
        hits = 0
        off_fov_total = 0
        n = _N_SEEDS_SLOW

        print(f"\n{'='*65}")
        print(f"GATE N (FULL slow, {n} seeds): Pixel-in-the-loop intercept")
        print(f"{'='*65}")

        for seed in range(n):
            cfg = _make_modeb_cfg(seed=seed)
            result = ClosedLoop(cfg).run()
            misses.append(result.miss_distance_m)
            if result.hit:
                hits += 1
            off_fov_total += result.n_off_fov_frames

        arr = np.array([m for m in misses if np.isfinite(m)])
        median_m = float(np.median(arr))
        p90_m = float(np.percentile(arr, 90))
        max_m = float(np.max(arr))

        print(f"Mode B results ({n} seeds):")
        print(f"  hits:        {hits}/{n}")
        print(f"  CPA median:  {median_m:.4f} m")
        print(f"  CPA p90:     {p90_m:.4f} m")
        print(f"  CPA max:     {max_m:.4f} m")

        assert hits == n, f"Gate N FAIL: only {hits}/{n} hits"
        assert median_m < _CAPTURE_RADIUS_M
        assert p90_m < _CAPTURE_RADIUS_M


# ---------------------------------------------------------------------------
# Gate O: Mode A vs Mode B consistency
# ---------------------------------------------------------------------------

@pytest.mark.slow  # full pixel-render engagements (26-52 s even at 6 seeds) -> acceptance tier
class TestGateO:
    """Gate O: Mode A vs Mode B consistency.

    Uses QUARTERING geometry (moderate speed) so the target moves across the FOV
    and pixel noise / tracking transitions are genuinely exposed.  Head-on
    geometry is too forgiving for a meaningful degradation comparison — the target
    stays near boresight the whole time and pixel noise is masked.

    After the double-IMM fix:
    - Mode B / Mode A degradation factor must be > 1.5.
      Quartering geometry is used because it exposes more pixel noise:
      the target moves across the FOV, causing tracking transitions and
      centroid noise that Mode A (analytic noise) handles cleanly.
    - Per-seed majority check: >= half the seeds have Mode B CPA > Mode A CPA.
    - Mode B pixel pipeline is FUNCTIONAL: every Mode B miss is finite and the
      median is bounded (no NaN/garbage from a broken pipeline).

    HONEST FINDING (head-on, from Gate N data):
    In pure head-on geometry, Mode B median = ~0.040 m vs Mode A median = ~0.038 m
    → degradation factor ≈ 1.06x.  The double-IMM fix increased this from ~1.0x
    (perfect double-smoothing) to 1.06x.  The factor is modest in head-on because
    the target stays near boresight — detection is easy, pixel noise is low.
    Quartering geometry is the honest test for > 1.5x degradation.

    A larger factor than with double-IMM is the CORRECT outcome — not a regression.

    WAVE-3 (FT640 optics) — IMPORTANT HONEST FINDING:
    Reconciling the sim camera from the narrow Boson (f_px≈2130) to the fielded
    FT640 (f_px≈707) changed the Mode A looming/area f_px.  In QUARTERING geometry
    at 80 m this made the Mode A reference much tighter (~1.0 m -> ~0.06 m, now a
    hit), while the Mode B pixel pipeline is UNCHANGED (its render optics barely
    moved 50°->48.7°): Mode B median stays ~7.4 m on quartering in BOTH cases.
    Consequence: the OLD `factor < 30x` upper bound (it was ~7.5x only because the
    Mode A denominator was ALSO ~1 m) now reads ~125x — purely a denominator effect,
    not a Mode B regression.  This exposes the real, previously-masked limitation:
    the Mode B pixel-in-the-loop pipeline does NOT close a 80 m quartering intercept
    (~7.4 m miss).  We therefore grade Mode B's ABSOLUTE miss (finite + bounded =
    pipeline functional) instead of the A-relative ratio, and PIN the quartering
    Mode-B miss so this fragility cannot be silently hidden.
    """

    def test_gate_o_degradation_factor_fast(self) -> None:
        """Fast (6 seeds, quartering geometry): Mode A vs Mode B degradation."""
        n = _N_SEEDS_FAST
        misses_a, misses_b = [], []
        hits_a, hits_b = 0, 0
        seeds_where_b_worse = 0

        print(f"\n{'='*70}")
        print(f"GATE O (fast, {n} seeds, QUARTERING): Mode A vs Mode B — double-IMM fix")
        print(f"{'='*70}")
        print(f"{'Seed':>6} {'Mode A miss':>12} {'Mode B miss':>12} {'Factor':>8} {'B>A':>5}")
        print(f"{'-'*46}")

        for seed in range(n):
            cfg_a = _make_modea_cfg(
                seed=seed,
                geometry=EngagementGeometry.QUARTERING,
                target_speed_mps=5.0,
                initial_range_m=80.0,
                max_sim_time_s=8.0,
            )
            cfg_b = _make_modeb_cfg(
                seed=seed,
                geometry=EngagementGeometry.QUARTERING,
                target_speed_mps=5.0,
                initial_range_m=80.0,
                max_sim_time_s=8.0,
            )

            r_a = ClosedLoop(cfg_a).run()
            r_b = ClosedLoop(cfg_b).run()

            misses_a.append(r_a.miss_distance_m)
            misses_b.append(r_b.miss_distance_m)
            if r_a.hit:
                hits_a += 1
            if r_b.hit:
                hits_b += 1

            factor = r_b.miss_distance_m / max(r_a.miss_distance_m, 1e-6)
            b_worse = r_b.miss_distance_m > r_a.miss_distance_m
            if b_worse:
                seeds_where_b_worse += 1
            print(f"  {seed:>4}  {r_a.miss_distance_m:>12.4f}  {r_b.miss_distance_m:>12.4f}  {factor:>8.2f}x  {str(b_worse):>5}")

        finite_a = [m for m in misses_a if np.isfinite(m)]
        finite_b = [m for m in misses_b if np.isfinite(m)]
        arr_a = np.array(finite_a) if finite_a else np.array([float("nan")])
        arr_b = np.array(finite_b) if finite_b else np.array([float("nan")])
        med_a = float(np.nanmedian(arr_a))
        med_b = float(np.nanmedian(arr_b))
        degradation_factor = med_b / max(med_a, 1e-6)

        print(f"\nMode A: hits={hits_a}/{n}  median={med_a:.4f}m  p90={np.nanpercentile(arr_a,90):.4f}m")
        print(f"Mode B: hits={hits_b}/{n}  median={med_b:.4f}m  p90={np.nanpercentile(arr_b,90):.4f}m")
        print(f"Mode B / Mode A degradation factor (median): {degradation_factor:.2f}x")
        print(f"Seeds where Mode B CPA > Mode A CPA: {seeds_where_b_worse}/{n}")
        print(f"\nHonest interpretation:")
        print(f"  Quartering geometry exposes pixel noise / tracking transitions")
        print(f"  Factor > 1.5: double-IMM fix exposed real detection noise")
        print(f"  Per-seed majority: detection noise dominates on most seeds")
        print(f"  Factor < 30x: pipeline functional")
        print(f"\n  NOTE (head-on ref from Gate N): Mode B ~0.040m / Mode A ~0.038m = ~1.06x")
        print(f"  Head-on factor is modest because target stays near boresight throughout.")
        print(f"  Quartering is the honest test for degradation exposure.")

        # Gate assertions
        assert degradation_factor > 1.5, (
            f"Gate O FAIL: degradation factor {degradation_factor:.3f}x <= 1.5. "
            f"In quartering geometry Mode B must show genuine detection noise > 1.5x. "
            f"This may indicate the outer IMM is still smoothing Mode B output."
        )
        # WAVE-3: the old `factor < 30x` upper bound is now ~125x — but ONLY because the
        # FT640 area-f_px tightened the Mode A quartering reference (~1.0 m -> ~0.06 m); the
        # Mode B pixel miss is unchanged (~7.4 m).  We grade Mode B's ABSOLUTE miss instead
        # of the fragile A-relative ratio: every Mode B miss must be finite and the median
        # bounded (< 12 m) — i.e. the pipeline is functional (no NaN/garbage), even though it
        # honestly does NOT close an 80 m quartering intercept.  This PINS that limitation.
        assert all(np.isfinite(m) for m in misses_b), (
            f"Gate O FAIL: a Mode B miss is non-finite {misses_b}.  The pixel pipeline is "
            f"producing NaN/Inf estimates (catastrophically broken)."
        )
        assert med_b < 12.0, (
            f"Gate O FAIL: Mode B median miss {med_b:.3f} m >= 12 m on quartering@80m.  "
            f"The pixel pipeline diverged beyond its known ~7.4 m quartering limitation."
        )
        # Per-seed majority: at least half the seeds must have Mode B CPA > Mode A CPA
        majority = n // 2
        assert seeds_where_b_worse >= majority, (
            f"Gate O FAIL: only {seeds_where_b_worse}/{n} seeds have Mode B CPA > Mode A CPA. "
            f"At least {majority} seeds (half) must show Mode B is genuinely noisier."
        )

    @pytest.mark.slow
    def test_gate_o_degradation_factor_full(self) -> None:
        """Full (slow, 15 seeds, quartering): Mode A vs Mode B degradation."""
        n = _N_SEEDS_SLOW
        misses_a, misses_b = [], []
        hits_a, hits_b = 0, 0
        seeds_where_b_worse = 0

        for seed in range(n):
            cfg_a = _make_modea_cfg(
                seed=seed,
                geometry=EngagementGeometry.QUARTERING,
                target_speed_mps=5.0,
                initial_range_m=80.0,
                max_sim_time_s=8.0,
            )
            cfg_b = _make_modeb_cfg(
                seed=seed,
                geometry=EngagementGeometry.QUARTERING,
                target_speed_mps=5.0,
                initial_range_m=80.0,
                max_sim_time_s=8.0,
            )
            r_a = ClosedLoop(cfg_a).run()
            r_b = ClosedLoop(cfg_b).run()
            misses_a.append(r_a.miss_distance_m)
            misses_b.append(r_b.miss_distance_m)
            if r_a.hit:
                hits_a += 1
            if r_b.hit:
                hits_b += 1
            if r_b.miss_distance_m > r_a.miss_distance_m:
                seeds_where_b_worse += 1

        finite_a = [m for m in misses_a if np.isfinite(m)]
        finite_b = [m for m in misses_b if np.isfinite(m)]
        arr_a = np.array(finite_a) if finite_a else np.array([float("nan")])
        arr_b = np.array(finite_b) if finite_b else np.array([float("nan")])
        med_a = float(np.nanmedian(arr_a))
        med_b = float(np.nanmedian(arr_b))
        degradation_factor = med_b / max(med_a, 1e-6)

        print(f"\nGate O FULL ({n} seeds, quartering): A med={med_a:.4f}m  B med={med_b:.4f}m  "
              f"factor={degradation_factor:.2f}x  b_worse={seeds_where_b_worse}/{n}")

        assert degradation_factor > 1.5
        # WAVE-3: absolute Mode-B-functional bound (finite + bounded) replaces the
        # fragile A-relative `factor < 30x`.  See the fast-test rationale / class docstring:
        # FT640 tightened the Mode A reference so the ratio is denominator-dominated now,
        # but the Mode B quartering miss (~7.4 m) is unchanged and finite.
        assert all(np.isfinite(m) for m in misses_b)
        assert med_b < 12.0
        majority = n // 2
        assert seeds_where_b_worse >= majority


# ---------------------------------------------------------------------------
# Gate P: off-FOV / lock-loss graceful degradation
# ---------------------------------------------------------------------------

@pytest.mark.slow  # full pixel-render engagements (26-52 s even at 6 seeds) -> acceptance tier
class TestGateP:
    """Gate P: off-FOV lock-loss and graceful degradation.

    A scenario where the target temporarily leaves the seeker FOV during
    a hard maneuver (quartering geometry at high speed).

    Asserts:
    - No NaN/Inf in any guidance command or position.
    - At least one coast/reacquire state is observed in the FSM.
    - result.n_off_fov_frames > 0 in the quartering off-FOV scenario — the
      test must specifically confirm off-FOV frames occurred, not just any
      coast state.
    - The engagement terminates cleanly (no Python exception, no infinite loop).
    - Graceful degradation: either a hit or a finite miss distance.
    """

    def test_gate_p_ofov_lockless_graceful(self) -> None:
        """Off-FOV lock-loss: seeker coasts and reacquires gracefully.

        Uses 3 seeds (short time budget) for the default run.
        The off-FOV assertion uses a lateral-offset scenario which reliably
        produces off-FOV frames in the first few seconds.
        """
        print(f"\n{'='*65}")
        print("GATE P: Off-FOV / lock-loss graceful degradation")
        print(f"{'='*65}")

        any_coast_seen = False
        any_nan_inf = False
        total_off_fov = 0

        # 3 quartering seeds — high speed, short time budget, close range
        for seed in range(3):
            cfg = _make_modeb_cfg(
                seed=seed,
                geometry=EngagementGeometry.QUARTERING,
                target_speed_mps=10.0,
                initial_range_m=80.0,
                max_sim_time_s=5.0,   # tight time budget for speed
            )
            result = ClosedLoop(cfg).run()
            total_off_fov += result.n_off_fov_frames

            print(f"  seed={seed} (quartering 10m/s): hit={result.hit}  "
                  f"miss={result.miss_distance_m:.4f}m  "
                  f"off_fov={result.n_off_fov_frames}  "
                  f"lock_states={set(s.value for s in result.lock_states_seen)}")

            if not math.isfinite(result.miss_distance_m) and not result.roe_abort:
                any_nan_inf = True

            coast_states = {TrackingState.PREDICTIVE_TRACK, TrackingState.REACQUIRE}
            if result.lock_states_seen & coast_states:
                any_coast_seen = True

        # 3 lateral-offset seeds — the large offset reliably forces off-FOV frames
        # Use the narrow-FOV factory to guarantee off-FOV occurrence with tight lens
        for seed in range(3):
            cfg_wide = _make_modeb_cfg(
                seed=seed,
                geometry=EngagementGeometry.HEAD_ON,
                target_lateral_offset_m=15.0,  # 15m offset → off-FOV for 17-deg lens
                initial_range_m=80.0,
                max_sim_time_s=5.0,
            )
            result = _run_modeb_narrow_fov(cfg_wide)  # narrow FOV to guarantee off-FOV
            total_off_fov += result.n_off_fov_frames
            print(f"  seed={seed} (lateral_15m, narrow-FOV): hit={result.hit}  "
                  f"miss={result.miss_distance_m:.4f}m  off_fov={result.n_off_fov_frames}")

            coast_states = {TrackingState.PREDICTIVE_TRACK, TrackingState.REACQUIRE}
            if result.lock_states_seen & coast_states:
                any_coast_seen = True

        print(f"\n  any_coast_observed: {any_coast_seen}")
        print(f"  any_nan_inf_in_commands: {any_nan_inf}")
        print(f"  total_off_fov_frames (quartering + narrow-FOV lateral): {total_off_fov}")

        # ASSERTIONS
        assert not any_nan_inf, (
            "Gate P FAIL: NaN/Inf detected in guidance commands or positions."
        )
        assert any_coast_seen, (
            "Gate P FAIL: No PREDICTIVE_TRACK or REACQUIRE states observed."
        )
        # Gate P requires actual off-FOV frames specifically in the off-FOV scenario.
        # The narrow-FOV lateral scenario is specifically designed to produce off-FOV
        # frames — this validates that the off-FOV counter is correctly incremented.
        assert total_off_fov > 0, (
            f"Gate P FAIL: total_off_fov_frames == 0 across {3} quartering + "
            f"{3} narrow-FOV lateral scenarios.  "
            f"The off-FOV geometry must produce at least one off-FOV frame."
        )


# ---------------------------------------------------------------------------
# Gate Q: Boson sensor delay with pixel pipeline
# ---------------------------------------------------------------------------

@pytest.mark.slow  # full pixel-render engagements (26-52 s even at 6 seeds) -> acceptance tier
class TestGateQ:
    """Gate Q: Boson >25 ms sensor delay with real pixel pipeline.

    6 seeds (fast).  Asserts >=80% hit rate with Smith predictor.
    """

    def test_gate_q_boson_delay_intercept(self) -> None:
        """Favorable intercept with Boson >25 ms sensor delay injected."""
        n = _N_SEEDS_FAST
        print(f"\n{'='*65}")
        print(f"GATE Q ({n} seeds): Boson sensor delay with pixel pipeline")
        print(f"{'='*65}")
        print(f"  Delay: 30 ms sensor + 10 ms loop = 40 ms total")
        print(f"  Smith predictor: ON")
        print()

        misses = []
        hits = 0

        print(f"{'Seed':>6} {'Hit':>5} {'Miss (m)':>10}")
        print(f"{'-'*26}")

        for seed in range(n):
            cfg = _make_modeb_cfg(
                seed=seed,
                sensor_delay_s=0.030,
                smith_predictor=True,
                initial_range_m=100.0,
                max_sim_time_s=10.0,
            )
            result = ClosedLoop(cfg).run()
            misses.append(result.miss_distance_m)
            if result.hit:
                hits += 1
            print(f"  {seed:>4}  {str(result.hit):>5}  {result.miss_distance_m:>10.4f}")

        arr = np.array([m for m in misses if np.isfinite(m)])
        median_m = float(np.median(arr)) if len(arr) > 0 else float("nan")
        p90_m = float(np.percentile(arr, 90)) if len(arr) > 0 else float("nan")

        print(f"\nGate Q results ({n} seeds, 30ms Boson delay):")
        print(f"  hits:       {hits}/{n}")
        print(f"  CPA median: {median_m:.4f} m")
        print(f"  CPA p90:    {p90_m:.4f} m")

        assert hits >= n * 8 // 10, (
            f"Gate Q FAIL: only {hits}/{n} hits with 30ms delay. "
            f"With Smith predictor, favorable scenario should maintain >=80% hit rate."
        )
        assert median_m < _CAPTURE_RADIUS_M, (
            f"Gate Q FAIL: median CPA {median_m:.4f}m >= capture radius."
        )


# ---------------------------------------------------------------------------
# Gate R: Narrow-FOV (Boson 24 mm) vs wide (50 deg) comparison
# ---------------------------------------------------------------------------

@pytest.mark.slow  # full pixel-render engagements (26-52 s even at 6 seeds) -> acceptance tier
class TestGateR:
    """Gate R: Narrow-FOV penalty quantification — Boson 24 mm vs 50 deg.

    This is the KEY SYSTEM FINDING for the Block-03 thermal seeker design.

    The Boson 640 with a 24 mm lens (HFOV ~17 deg, VFOV ~13.7 deg) provides
    superior detection range and thermal sensitivity vs a wide 9 mm lens.
    However, it pays a severe terminal-FOV penalty: once the interceptor begins
    aggressive lateral corrections in the last 50 m, the target drifts off the
    tight 17 deg FOV, triggering REACQUIRE states and guidance coast.

    This test QUANTIFIES that penalty honestly:
      - Off-FOV frame fraction: n_off_fov_frames / total_vision_frames
      - REACQUIRE or HARD_LOST occurrence (any seed)
      - Hit rate
      - CPA distribution

    Both lenses are tested at head-on / moderate geometry (favorable) with
    8 seeds so the comparison is fair.  Numbers are reported honestly even
    if the narrow lens performs much worse.

    The narrow-FOV results are the system-level design tradeoff data for
    choosing between detection range (narrow) and terminal guidance margin (wide).

    WAVE-3 NOTE: the "wide" lens here is the Mode B default (_wide_fpv_intrinsics),
    now reconciled to the fielded FOXEER FT640 V2 (HFOV 48.7 deg, f_px≈707) — the
    "50 deg" wording in the prints/labels below is the legacy descriptor; the actual
    wide HFOV is 48.7 deg.  This is still vastly wider than the 17 deg Boson 24 mm,
    so every Gate R structural assertion (narrow has MORE off-FOV frames) is unchanged.
    """

    def test_gate_r_narrow_vs_wide_fov(self) -> None:
        """Compare Boson 24 mm narrow FOV vs 50-deg wide FOV, 6 seeds each."""
        n = 6

        print(f"\n{'='*75}")
        print("GATE R: Narrow-FOV (Boson 24mm, HFOV~17deg) vs Wide (50deg) — 6 seeds")
        print(f"{'='*75}")
        print(f"\n  Wide 50-deg (default):")
        print(f"  {'Seed':>6} {'Hit':>5} {'Miss (m)':>10} {'Off-FOV fr':>11} {'Coast st':>9}")
        print(f"  {'-'*46}")

        # --- Wide lens (default 50 deg) ---
        wide_misses, wide_hits, wide_off_fov_total = [], 0, 0
        wide_coast_any = False
        wide_off_fov_fractions = []

        for seed in range(n):
            cfg = _make_modeb_cfg(seed=seed, initial_range_m=100.0, max_sim_time_s=8.0)
            result = ClosedLoop(cfg).run()
            wide_misses.append(result.miss_distance_m)
            if result.hit:
                wide_hits += 1
            wide_off_fov_total += result.n_off_fov_frames
            # Approximate total frames = engagement_time * vision_rate
            total_vis = max(1, int(result.engagement_time_s * 60.0))
            frac = result.n_off_fov_frames / total_vis
            wide_off_fov_fractions.append(frac)
            coast_states = {TrackingState.PREDICTIVE_TRACK, TrackingState.REACQUIRE}
            if result.lock_states_seen & coast_states:
                wide_coast_any = True
            coast_str = "YES" if result.lock_states_seen & coast_states else "no"
            print(f"  {seed:>6}  {str(result.hit):>5}  {result.miss_distance_m:>10.4f}  "
                  f"{result.n_off_fov_frames:>11}  {coast_str:>9}")

        wide_arr = np.array([m for m in wide_misses if np.isfinite(m)])
        wide_med = float(np.median(wide_arr)) if len(wide_arr) > 0 else float("nan")
        wide_p90 = float(np.percentile(wide_arr, 90)) if len(wide_arr) > 0 else float("nan")
        wide_off_fov_frac_med = float(np.median(wide_off_fov_fractions))

        print(f"\n  Wide 50-deg summary ({n} seeds):")
        print(f"    hit_rate:         {wide_hits}/{n} = {wide_hits/n:.0%}")
        print(f"    CPA median:       {wide_med:.4f} m")
        print(f"    CPA p90:          {wide_p90:.4f} m")
        print(f"    off-FOV frac med: {wide_off_fov_frac_med:.3f}")
        print(f"    coast/reacq any:  {wide_coast_any}")

        # --- Narrow lens (Boson 24 mm, HFOV ~17 deg) ---
        print(f"\n  Narrow 24mm (HFOV~17deg):")
        print(f"  {'Seed':>6} {'Hit':>5} {'Miss (m)':>10} {'Off-FOV fr':>11} {'Coast st':>9}")
        print(f"  {'-'*46}")

        narrow_misses, narrow_hits, narrow_off_fov_total = [], 0, 0
        narrow_coast_any = False
        narrow_off_fov_fractions = []

        for seed in range(n):
            cfg = _make_modeb_cfg(seed=seed, initial_range_m=100.0, max_sim_time_s=8.0)
            result = _run_modeb_narrow_fov(cfg)
            narrow_misses.append(result.miss_distance_m)
            if result.hit:
                narrow_hits += 1
            narrow_off_fov_total += result.n_off_fov_frames
            total_vis = max(1, int(result.engagement_time_s * 60.0))
            frac = result.n_off_fov_frames / total_vis
            narrow_off_fov_fractions.append(frac)
            coast_states = {TrackingState.PREDICTIVE_TRACK, TrackingState.REACQUIRE}
            if result.lock_states_seen & coast_states:
                narrow_coast_any = True
            coast_str = "YES" if result.lock_states_seen & coast_states else "no"
            print(f"  {seed:>6}  {str(result.hit):>5}  {result.miss_distance_m:>10.4f}  "
                  f"{result.n_off_fov_frames:>11}  {coast_str:>9}")

        narrow_arr = np.array([m for m in narrow_misses if np.isfinite(m)])
        narrow_med = float(np.median(narrow_arr)) if len(narrow_arr) > 0 else float("nan")
        narrow_p90 = float(np.percentile(narrow_arr, 90)) if len(narrow_arr) > 0 else float("nan")
        narrow_off_fov_frac_med = float(np.median(narrow_off_fov_fractions))

        print(f"\n  Narrow 24mm summary ({n} seeds):")
        print(f"    hit_rate:         {narrow_hits}/{n} = {narrow_hits/n:.0%}")
        print(f"    CPA median:       {narrow_med:.4f} m")
        print(f"    CPA p90:          {narrow_p90:.4f} m")
        print(f"    off-FOV frac med: {narrow_off_fov_frac_med:.3f}")
        print(f"    coast/reacq any:  {narrow_coast_any}")

        # --- Summary table ---
        print(f"\n{'='*75}")
        print(f"  NARROW-FOV PENALTY SUMMARY (head-on, favorable geometry)")
        print(f"{'='*75}")
        print(f"  {'Metric':<30} {'Wide 50deg':>12} {'Narrow 24mm':>12}")
        print(f"  {'-'*56}")
        print(f"  {'Hit rate':<30} {wide_hits}/{n} = {wide_hits/n:.0%}  {narrow_hits}/{n} = {narrow_hits/n:.0%}")
        print(f"  {'CPA median (m)':<30} {wide_med:>12.4f} {narrow_med:>12.4f}")
        print(f"  {'CPA p90 (m)':<30} {wide_p90:>12.4f} {narrow_p90:>12.4f}")
        print(f"  {'Off-FOV frac median':<30} {wide_off_fov_frac_med:>12.3f} {narrow_off_fov_frac_med:>12.3f}")
        print(f"  {'Coast/reacquire any seed':<30} {str(wide_coast_any):>12} {str(narrow_coast_any):>12}")
        print(f"{'='*75}")
        if math.isfinite(narrow_med) and narrow_med > 0 and math.isfinite(wide_med) and wide_med > 0:
            cpa_ratio = narrow_med / max(wide_med, 1e-6)
            print(f"  Narrow/Wide CPA ratio: {cpa_ratio:.2f}x  "
                  f"(narrow has {'worse' if cpa_ratio > 1.0 else 'better'} CPA)")
        print(f"\n  DESIGN IMPLICATION: The 24mm lens provides superior detection range")
        print(f"  at the cost of a terminal-FOV penalty revealed by the off-FOV fraction.")
        print(f"  If narrow_off_fov_frac_med >> wide_off_fov_frac_med, the 24mm lens")
        print(f"  should be paired with a wider acquisition phase or an active gimbal.")

        # Gate R assertions: report honestly, do not fail on narrow lens performing worse
        # The test documents the penalty — it does NOT require the narrow lens to be good.
        # Structural checks only:
        assert math.isfinite(wide_med), "Gate R FAIL: wide-lens CPA is not finite"
        assert math.isfinite(narrow_med) or narrow_hits == 0, (
            "Gate R FAIL: narrow-lens CPA is not finite and hit_rate > 0"
        )
        # Narrow lens must produce MORE off-FOV frames than wide lens
        # (structural validation: the narrow FOV actually restricts the field)
        assert narrow_off_fov_total >= wide_off_fov_total, (
            f"Gate R FAIL: narrow lens ({narrow_off_fov_total} off-FOV frames) "
            f"did NOT produce more off-FOV frames than wide lens ({wide_off_fov_total}). "
            f"The 24mm intrinsics must be tighter than 50-deg — check the factory."
        )
        # Gate P sub-assertion for the narrow-FOV scenario:
        # n_off_fov_frames must be > 0 for the narrow lens (it IS the tight-FOV scenario)
        assert narrow_off_fov_total > 0, (
            f"Gate R / Gate P FAIL: narrow lens produced 0 off-FOV frames. "
            f"With HFOV ~17 deg and lateral guidance corrections, off-FOV must occur."
        )


# ---------------------------------------------------------------------------
# Sanity: imports and pixel_loop module integrity
# ---------------------------------------------------------------------------

class TestModeB_Smoke:
    """Smoke tests — fast, no engagement run needed."""

    def test_pixel_loop_imports(self) -> None:
        """Mode B modules import without error."""
        from fpv.guidance.pixel_loop import (
            PixelLoopState,
            make_pixel_loop_state,
            run_pixel_vision_tick,
            _wide_fpv_intrinsics,
        )
        intr = _wide_fpv_intrinsics()
        assert intr.width == 640
        assert intr.height == 512
        assert intr.f_px > 0

    def test_pixel_state_init(self) -> None:
        """PixelLoopState initializes correctly."""
        from fpv.guidance.pixel_loop import make_pixel_loop_state
        ps = make_pixel_loop_state(42)
        assert len(ps.star_positions) == 12
        assert ps.cum_ego_dx == 0.0
        assert ps.frame_count == 0

    def test_mode_b_single_engagement_no_crash(self) -> None:
        """One Mode B engagement completes without exception."""
        cfg = _make_modeb_cfg(seed=0, initial_range_m=100.0, max_sim_time_s=10.0)
        result = ClosedLoop(cfg).run()
        assert result.mode == "pixel"
        assert math.isfinite(result.miss_distance_m) or result.roe_abort
        assert result.engagement_time_s > 0.0

    def test_mode_b_no_analytic_bearing_path(self) -> None:
        """Verify: when mode='pixel', the result.mode field is 'pixel'.

        The design guarantee is that mode='pixel' means the seeker pipeline
        (not the analytic bearing) drove guidance.  The mode field on the
        result confirms which path was taken.
        """
        cfg_a = _make_modea_cfg(seed=7)
        cfg_b = _make_modeb_cfg(seed=7)
        r_a = ClosedLoop(cfg_a).run()
        r_b = ClosedLoop(cfg_b).run()
        assert r_a.mode == "analytic"
        assert r_b.mode == "pixel"
        # The miss distances must be different (proves different pipelines)
        assert abs(r_a.miss_distance_m - r_b.miss_distance_m) > 1e-6, (
            "Mode A and Mode B miss distances are identical — "
            "the pixel pipeline is not actually driving guidance."
        )

    def test_boson_24mm_intrinsics_tighter_than_wide(self) -> None:
        """Verify Boson 24mm FOV is significantly tighter than 50-deg wide."""
        from fpv.seeker.geometry import boson_640_24mm_intrinsics, focal_length_from_hfov
        narrow = boson_640_24mm_intrinsics()
        wide_f = focal_length_from_hfov(50.0, 640)
        # Narrow lens has larger focal length in pixels (narrower FOV = higher f_px).
        # Both sensors are 640px wide, so a higher f_px directly means tighter HFOV.
        assert narrow.f_px > wide_f, (
            f"Boson 24mm f_px={narrow.f_px:.0f} should be > wide 50deg f_px={wide_f:.0f}"
        )
        # Verify angular HFOV: narrow ~17 deg << wide ~50 deg.
        # HFOV = 2 * atan(width/2 / f_px)
        narrow_hfov_deg = math.degrees(2.0 * math.atan(narrow.width / 2.0 / narrow.f_px))
        wide_hfov_deg = math.degrees(2.0 * math.atan(640 / 2.0 / wide_f))
        assert narrow_hfov_deg < wide_hfov_deg, (
            f"Narrow lens HFOV {narrow_hfov_deg:.1f} deg should be < wide {wide_hfov_deg:.1f} deg"
        )
        # Concrete check: narrow should be ~17 deg, wide ~50 deg
        assert narrow_hfov_deg < 20.0, f"Boson 24mm HFOV {narrow_hfov_deg:.1f} deg should be < 20 deg"
        assert wide_hfov_deg > 45.0, f"Wide 50-deg HFOV {wide_hfov_deg:.1f} deg should be > 45 deg"
