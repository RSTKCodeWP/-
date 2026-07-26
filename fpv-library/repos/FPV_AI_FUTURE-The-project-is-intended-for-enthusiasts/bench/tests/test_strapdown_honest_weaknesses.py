"""Honest CHARACTERIZATION tests for the STRAPDOWN seeker (NO gimbal).

These tests pin each known weakness of the strapdown thermal FPV to a named, reproducible,
deterministic (seed=11) closed-loop run of the honest sim. They are written to PASS while the
weakness is PRESENT -- a passing test here documents a real deficiency, not a success. When a fix
lands (gimbal, cam<->IMU HW-timestamp, ToF range, tighter attitude loop) the corresponding test
should START FAILING; that is the signal the weakness is closed -- update the threshold then.

Body-to-body means CPA within the capture radius (cfg.cap_m = 1.5 m). The strapdown misses named
below are all several times that -- unambiguous, not borderline.

Decomposition of the head_on maneuvering miss these tests lock in (seeds 11/7/23):
    straight + truth lambda-dot ...... ~4.6 m   irreducible geometry floor at g=6
    + maneuver (point-mass) .......... ~7.0 m   the route change itself
    + attitude lag ................... ~11  m   FPV must ROTATE to redirect thrust
    + raw seeker lambda-dot (W1) ..... ~22  m   ego-motion corrupts the LOS rate
Each layer is individually significant; they stack. The gimbal (tested elsewhere) collapses all of
this to ~1.1 m because it holds the target in FOV and measures a clean inertial lambda-dot.

CAVEAT (not enshrined as a test): in the maneuvering regime a LARGER modeled timestamp skew can
LOWER the CPA -- an artifact of the guidance noise incidentally improving FOV retention, NOT a real
"skew helps" effect. We deliberately do not assert timestamp-skew monotonicity.
"""

from __future__ import annotations

from functools import lru_cache

import pytest

from fpv_ai.bench.sim3d import Sim3DConfig
from fpv_ai.bench.sim3d_honest import run_honest

pytestmark = pytest.mark.slow  # each scenario is a full MuJoCo closing engagement (~3-4 s)

SEED = 11
CAP_M = Sim3DConfig().cap_m  # 1.5 m capture radius == the body-to-body bar
_HARD = dict(acquisition_box=(0.0, 0.0, 640.0, 360.0), trajectory_continuity=True)  # W6 lock-hardening
_MAN = dict(target_turn_g=1.5, target_turn_period_s=1.5, attitude_ego_gain=0.08)     # route-changing target


def _cfg(geometry: str, *, maneuver: bool, attitude_tau_s: float) -> Sim3DConfig:
    extra = dict(_MAN, attitude_tau_s=attitude_tau_s) if maneuver else {}
    return Sim3DConfig(geometry=geometry, g_max=6.0, committed=True, seed=SEED, **extra)


@lru_cache(maxsize=None)
def _scenario(name: str) -> dict:
    """Run (and cache) one named strapdown scenario. Cached so shared runs execute once."""
    if name == "straight_truth":
        return run_honest(_cfg("head_on", maneuver=False, attitude_tau_s=0.0), guidance_source="geometry")
    if name == "straight_raw":
        return run_honest(_cfg("head_on", maneuver=False, attitude_tau_s=0.0), guidance_source="seeker")
    if name == "straight_egocomp":
        return run_honest(_cfg("head_on", maneuver=False, attitude_tau_s=0.0),
                          guidance_source="seeker", sync_error_ms=1.0)
    if name == "maneuver_truth":
        return run_honest(_cfg("head_on", maneuver=True, attitude_tau_s=0.15),
                          guidance_source="geometry", pipeline_kwargs=dict(_HARD))
    if name == "maneuver_truth_nolag":
        return run_honest(_cfg("head_on", maneuver=True, attitude_tau_s=0.0),
                          guidance_source="geometry", pipeline_kwargs=dict(_HARD))
    if name == "maneuver_strapdown_headon":
        return run_honest(_cfg("head_on", maneuver=True, attitude_tau_s=0.15),
                          guidance_source="seeker", sync_error_ms=1.0, pipeline_kwargs=dict(_HARD))
    if name == "maneuver_strapdown_quartering":
        return run_honest(_cfg("quartering", maneuver=True, attitude_tau_s=0.15),
                          guidance_source="seeker", sync_error_ms=1.0, pipeline_kwargs=dict(_HARD))
    raise KeyError(name)


def test_geometry_floor_cannot_reach_body_to_body():
    """FLOOR: even with a PERFECT lambda-dot against a STRAIGHT target, the strapdown point-mass
    leaves ~4.6 m at g=6 -- it never reaches CPA<=cap_m. Body-to-body is not free even in the ideal
    case; the envelope/geometry alone is a wall."""
    cpa = _scenario("straight_truth")["cpa"]
    assert cpa > CAP_M, f"expected an ideal-case miss above the {CAP_M} m capture radius, got {cpa:.2f}"
    assert cpa > 2.0, f"floor unexpectedly tight ({cpa:.2f} m) -- has the envelope/geometry changed?"


def test_W1_raw_seeker_lambda_dot_roughly_doubles_the_miss():
    """W1 (cam<->IMU ego-motion): feeding the RAW strapdown seeker LOS rate into guidance blows the
    miss up to ~12 m vs ~4.6 m for the truth lambda-dot -- the ego motion corrupts lambda-dot."""
    raw = _scenario("straight_raw")["cpa"]
    truth = _scenario("straight_truth")["cpa"]
    assert raw > 9.0, f"raw-seeker miss unexpectedly small ({raw:.2f} m) -- is ego-motion still modeled?"
    assert raw > truth + 4.0, f"raw ({raw:.2f}) should dwarf truth ({truth:.2f}) -- gap collapsed"


def test_W1_modeled_ego_comp_helps_but_still_misses_body_to_body():
    """W1 fix DIRECTION: a modeled cam<->IMU ego-comp (1 ms skew) recovers most of the truth
    lambda-dot -- much better than raw -- but still lands ~5 m out, above the capture radius. The
    ego-comp is necessary and not sufficient for body-to-body."""
    ego = _scenario("straight_egocomp")["cpa"]
    raw = _scenario("straight_raw")["cpa"]
    assert ego < raw - 3.0, f"ego-comp ({ego:.2f}) should clearly beat raw ({raw:.2f})"
    assert ego > CAP_M, f"ego-comp alone should still miss body-to-body, got {ego:.2f} m"


def test_maneuvering_target_defeats_strapdown_body_to_body():
    """HEADLINE: against a route-changing target, the BEST strapdown effort (ego-comp + lock-harden +
    attitude lag) misses by ~10 m in BOTH head_on and quartering -- many times the capture radius.
    Strapdown cannot do body-to-body against a maneuvering winged UAV."""
    for name in ("maneuver_strapdown_headon", "maneuver_strapdown_quartering"):
        cpa = _scenario(name)["cpa"]
        assert cpa > 5.0, f"{name}: expected a clear body-to-body miss, got {cpa:.2f} m"


def test_W6_detects_target_but_cannot_hold_lock_under_clutter():
    """W6 (ground clutter): the strapdown DETECTS the target almost every frame yet HOLDS lock only a
    minority of frames -- clutter + body rotation keep breaking the lock. Detection is not the
    bottleneck; lock retention is."""
    r = _scenario("maneuver_strapdown_headon")
    assert r["det_rate"] > 0.8, f"detection should stay high, got {r['det_rate']:.2f}"
    assert r["lock_rate"] < 0.6, f"lock should be intermittent (<0.6), got {r['lock_rate']:.2f}"


def test_maneuver_miss_persists_even_with_a_perfect_seeker():
    """W-FOV core: the maneuver miss is NOT merely a lambda-dot problem. Even with the TRUTH
    lambda-dot the strapdown still lands ~11 m out against the maneuvering target -- because the body
    must rotate to chase the route change, throwing the target out of the narrow FOV. This is why a
    GIMBAL (holds FOV) fixes it and a better lambda-dot alone does not."""
    cpa = _scenario("maneuver_truth")["cpa"]
    assert cpa > 5.0, f"a perfect seeker should still miss the maneuvering target, got {cpa:.2f} m"


def test_attitude_lag_adds_several_meters_of_miss():
    """FPV attitude lag: the airframe must ROTATE to redirect thrust, so the lateral acceleration
    lags the command. Isolating it (truth lambda-dot, maneuver, lag vs point-mass) shows the lag
    alone adds a few meters of miss."""
    lagged = _scenario("maneuver_truth")["cpa"]        # attitude_tau_s = 0.15
    point_mass = _scenario("maneuver_truth_nolag")["cpa"]  # attitude_tau_s = 0.0
    assert lagged > point_mass + 1.5, (
        f"attitude lag should cost real meters: lagged {lagged:.2f} vs point-mass {point_mass:.2f}")
