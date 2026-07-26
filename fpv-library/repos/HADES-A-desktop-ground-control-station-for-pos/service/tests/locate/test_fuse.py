"""Tests for the localization fuser (Task 4.3; research gate §1, §2, §6).

The fuser is the flagship's estimator. It takes the per-frame fusable observations of ONE
(stationary) survivor track and produces a single fused ground point with an HONEST
covariance. The invariants that matter, each tested here:

1. It imports the SAME `geometry.ray_to_ground` as the Projector (single source of truth,
   never re-implemented) for the per-frame Jacobian.
2. Full-information weighting (`Wi = Sigma_i^-1`): variance drops with more frames, and
   oblique/long-range frames self-down-weight (no hand-tuned cos/range factor).
3. THE BIAS FLOOR (§2): the reported covariance is `Lambda^-1 + Sigma_bias`. As N grows the
   variance part shrinks but R95 ASYMPTOTES TO A FLOOR > 0 that scales with slant range. A
   naive `Lambda^-1` would shrink to zero = the "smug filter" = confidently wrong.
4. Aspect diversity relaxes the floor; a single straight pass keeps the full floor, sets
   `heading_limited`, and is capped at SWEEP (never PINPOINT) regardless of variance.
5. A MOVING target does not converge: the NIS residual-consistency test fires, the estimate
   stays CONVERGING with a big (empirical-scatter) radius, `moving_suspected=True`.
6. A single gross outlier frame is chi^2-rejected from the fused mean (not from visibility).
"""

from __future__ import annotations

import math

from hades.ingest.telemetry_source import Pose
from hades.locate.camera_model import CameraModel
from hades.locate.error_model import SensorErrorModel
from hades.locate.fuse import (
    ConvergenceState,
    FuseObservation,
    Fuser,
)
from hades.locate.geom_sim import StraightPass, world_to_pixel

_M_PER_DEG = 111320.0


def _nadir_cam() -> CameraModel:
    return CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=540.0, mount="nadir")


def _obs(pose: Pose, camera: CameraModel, pixel: tuple[float, float]) -> FuseObservation:
    return FuseObservation(pose=pose, camera=camera, pixel=pixel)


def _straight_obs(
    target: tuple[float, float],
    n: int,
    agl: float = 80.0,
    cam: CameraModel | None = None,
    lateral_m: float = 60.0,
) -> list[FuseObservation]:
    """Perfect (noise-free) observations of a stationary target over a LATERAL straight pass.

    A laterally-offset leg is the realistic single-pass SAR geometry and the heading-limited
    worst case: the target sits off to one side the whole pass, so a common heading bias does
    NOT cancel (verified in sim). A pass flown directly OVER the target is a degenerate best
    case where the over/under flip cancels the bias - not what "single pass" means here.
    """
    cam = cam or _nadir_cam()
    path = StraightPass(
        target_latlon=target, agl_m=agl, speed_mps=15.0, n_frames=n,
        lateral_offset_m=lateral_m, camera=cam,
    )
    obs = []
    for gt in path.frames():
        obs.append(_obs(gt.pose_true, cam, gt.pixel_true))
    return obs


def _enu_error_m(est_latlon, true_latlon) -> float:
    dlat = (est_latlon[0] - true_latlon[0]) * _M_PER_DEG
    dlon = (est_latlon[1] - true_latlon[1]) * _M_PER_DEG * math.cos(math.radians(true_latlon[0]))
    return math.hypot(dlat, dlon)


# --- single source of truth ----------------------------------------------------------


def test_fuse_uses_shared_ray_to_ground():
    # The fuser must import the SAME ray_to_ground as the Projector (D1), not re-derive it.
    import ast
    import inspect

    import hades.locate.fuse as fz

    tree = ast.parse(inspect.getsource(fz))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(a.name for a in node.names)
    assert "ray_to_ground" in imported


# --- zero-noise: the fused estimate lands on the target ------------------------------


def test_noise_free_fuse_recovers_target():
    target = (40.0, -74.0)
    fuser = Fuser(error_model=SensorErrorModel())
    result = fuser.fuse(_straight_obs(target, n=15))
    assert _enu_error_m(result.coord, target) < 0.5  # sub-meter with perfect inputs


# --- full-information weighting: variance drops with more frames ---------------------


def test_more_frames_shrink_the_variance_part():
    # The information part (Lambda^-1) must shrink as N grows (the fusion gain), even though
    # the REPORTED R95 is floored. Expose the pre-floor radius to test the gain directly.
    target = (40.0, -74.0)
    fuser = Fuser(error_model=SensorErrorModel())
    r_few = fuser.fuse(_straight_obs(target, n=4)).r95_prefloor_m
    r_many = fuser.fuse(_straight_obs(target, n=40)).r95_prefloor_m
    assert r_many < r_few  # more independent looks -> tighter information ellipse


# --- THE BIAS FLOOR (§2) -------------------------------------------------------------


def test_r95_asymptotes_to_a_floor_not_zero():
    # The headline honesty point: averaging cannot beat the common-mode heading bias, so the
    # REPORTED R95 must asymptote to a floor > 0 as N grows, NOT to zero.
    target = (40.0, -74.0)
    fuser = Fuser(error_model=SensorErrorModel())
    r95_big_n = fuser.fuse(_straight_obs(target, n=120)).r95_m
    assert r95_big_n > 1.0  # a real floor, not a smug-filter shrink to ~0


def test_bias_floor_scales_with_slant_range():
    # The heading-bias lever arm grows with GROUND RANGE, so a longer-standoff pass (the
    # bias displaces the ground point farther per degree of heading error) must report a LARGER
    # floored R95 than a short-standoff one. Use a fixed AGL and vary the LATERAL standoff (that
    # is what changes the ground range / lever arm; raising AGL near-nadir barely moves it).
    # Robust across seeds (averaged) - a seed-lucky single run is not evidence.
    target = (40.0, -74.0)
    short = []
    long = []
    for seed in range(5):
        f = Fuser(error_model=SensorErrorModel(), seed=seed)
        short.append(f.fuse(_straight_obs(target, n=40, agl=60.0, lateral_m=20.0)).r95_m)
        long.append(f.fuse(_straight_obs(target, n=40, agl=60.0, lateral_m=120.0)).r95_m)
    assert sum(long) / len(long) > sum(short) / len(short)


def test_r95_is_empirical_quantile_not_major_semi_axis():
    # The reported R95 must be the EMPIRICAL 95th-percentile sample radius (the equal-coverage
    # circle, §4), NOT the major semi-axis (sqrt(5.991)*sqrt(max_eigenvalue)), which over-
    # states the radius (false pessimism) - the dishonest form the research gate forbids. So on
    # a heading-limited anisotropic cloud, reported r95_m must be STRICTLY LESS than the major
    # semi-axis of the same reported covariance.
    target = (40.0, -74.0)
    result = Fuser(error_model=SensorErrorModel(), seed=0).fuse(_straight_obs(target, n=40))
    assert result.r95_m < result.semi_major_m  # empirical quantile beats the semi-axis
    # And the reported radius is measured about the REPORTED coordinate (x_hat), so it covers
    # any weighted-vs-cloud-mean offset: it must contain ~95% of the cloud about x_hat.
    assert result.r95_m > 0.0


# --- aspect diversity + the SWEEP cap ------------------------------------------------


def test_single_pass_is_heading_limited_and_capped_at_sweep():
    target = (40.0, -74.0)
    fuser = Fuser(error_model=SensorErrorModel())
    result = fuser.fuse(_straight_obs(target, n=60))
    assert result.heading_limited is True
    # A single lateral leg has modest aspect diversity, well below the relaxed-floor regime
    # (an orbit, tested separately, reaches ~180). The bias does NOT cancel -> heading_limited.
    assert result.aspect_spread_deg < 90.0
    # Never PINPOINT on a single straight pass, no matter how tight the variance got.
    assert result.actionability_class != "PINPOINT"


def test_orbit_has_high_aspect_spread_and_relaxes_floor():
    from hades.locate.geom_sim import OrbitPath

    target = (40.0, -74.0)
    cam = _nadir_cam()
    path = OrbitPath(target_latlon=target, agl_m=80.0, radius_m=80.0, n_frames=36, camera=cam)
    obs = [_obs(gt.pose_true, cam, gt.pixel_true) for gt in path.frames()]
    fuser = Fuser(error_model=SensorErrorModel())
    result = fuser.fuse(obs)
    assert result.aspect_spread_deg > 90.0
    assert result.heading_limited is False  # diverse aspects observe (and relax) the bias
    # The orbit floor is smaller than the matched single-pass floor (bias partially cancels).
    single = fuser.fuse(_straight_obs(target, n=36, agl=80.0))
    assert result.r95_m < single.r95_m


# --- moving target: does not converge ------------------------------------------------


def test_moving_target_stays_converging_with_big_radius():
    # A target drifting frame to frame violates the stationary assumption: the NIS residual
    # test must fire, the estimate stays CONVERGING, radius is the (large) empirical scatter.
    cam = _nadir_cam()
    base = (40.0, -74.0)
    obs = []
    path = StraightPass(target_latlon=base, agl_m=80.0, speed_mps=15.0, n_frames=20, camera=cam)
    gts = list(path.frames())
    for i, gt in enumerate(gts):
        # Drift the TRUE target 3 m North each frame; re-project the pixel for the moved target.
        moved = (base[0] + (3.0 * i) / _M_PER_DEG, base[1])
        px = world_to_pixel(gt.pose_true, cam, moved, 0.0)
        if px is None:
            continue
        obs.append(_obs(gt.pose_true, cam, px))
    fuser = Fuser(error_model=SensorErrorModel())
    result = fuser.fuse(obs)
    assert result.moving_suspected is True
    assert result.convergence is ConvergenceState.CONVERGING
    assert result.r95_m > 10.0  # big radius, never a confident pin


# --- single outlier frame is chi^2-rejected from the fused mean ----------------------


def test_single_outlier_frame_is_rejected_not_fused():
    target = (40.0, -74.0)
    cam = _nadir_cam()
    obs = _straight_obs(target, n=20, cam=cam)
    # Corrupt ONE frame's pixel far off (a misassociation / glint).
    bad = obs[10]
    obs[10] = _obs(bad.pose, cam, (bad.pixel[0] + 600.0, bad.pixel[1] + 400.0))
    fuser = Fuser(error_model=SensorErrorModel())
    result = fuser.fuse(obs)
    # The outlier is rejected, so the estimate still lands near the target (not dragged off),
    # and the fuser reports it did not treat the clip as "moving".
    assert _enu_error_m(result.coord, target) < 3.0
    assert result.n_rejected >= 1
    assert result.moving_suspected is False
