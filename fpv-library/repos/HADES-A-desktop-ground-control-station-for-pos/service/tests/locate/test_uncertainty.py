"""Tests for Monte Carlo uncertainty propagation (Task 4.4; research gate §4).

The MC is the FINAL reported uncertainty for a confirmed contact (the cheap linearized
Sigma_i in fuse.py is for the per-frame weight only). It samples the input sigmas from the
error_model, pushes each draw through the SAME `ray_to_ground`, and forms a 2x2 ground
covariance + an HONEST R95. The invariants that matter:

- R95 is the EMPIRICAL 95th-percentile sample radius, NOT the major semi-axis (§4: the
  semi-axis over-states the equal-coverage circle -> false pessimism).
- The 95% ellipse uses scale sqrt(chi^2(2)=5.991).
- The common-mode heading BIAS is drawn ONCE per contact (shared across the frames), the
  jitter per frame -> drawing the bias i.i.d. per frame would fake an error reduction fusion
  cannot achieve (the smug filter, inside the MC).
- Per-sample above-horizon rejection runs; a near-horizon-unstable contact (high reject
  fraction) is forced to CUE_ONLY with a floor radius, never a tight false number.
- The heading-limited oblique case yields a LARGE cross-range-elongated ellipse that a
  linearized method would miss.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from hades.ingest.telemetry_source import Pose
from hades.locate.camera_model import CameraModel
from hades.locate.error_model import SensorErrorModel
from hades.locate.uncertainty import MonteCarloUncertainty, UncertaintyResult

_M_PER_DEG = 111320.0


def _nadir_cam() -> CameraModel:
    return CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=540.0, mount="nadir")


def _pose(agl: float, pitch: float = 0.0, yaw: float = 0.0) -> Pose:
    return Pose(
        t=0.0, lat=40.0, lon=-74.0, alt=agl, alt_datum="REL_TAKEOFF",
        roll=0.0, pitch=pitch, yaw=yaw,
    )


def _center_pixel(cam: CameraModel) -> tuple[float, float]:
    return (cam.cx, cam.cy)


# --- basic shape -------------------------------------------------------------------


def test_returns_covariance_ellipse_and_r95():
    mc = MonteCarloUncertainty(error_model=SensorErrorModel(), n_draws=1000, seed=0)
    res = mc.propagate(_pose(80.0), _nadir_cam(), _center_pixel(_nadir_cam()))
    assert isinstance(res, UncertaintyResult)
    assert res.cov.shape == (2, 2)
    assert res.r95_m > 0.0
    assert res.semi_major_m >= res.semi_minor_m > 0.0


def test_ellipse_scale_is_sqrt_chi2_2_95():
    # The semi-axes are sqrt(5.991)*sqrt(eigenvalue). Verify against the sample covariance.
    mc = MonteCarloUncertainty(error_model=SensorErrorModel(), n_draws=4000, seed=1)
    res = mc.propagate(_pose(80.0), _nadir_cam(), _center_pixel(_nadir_cam()))
    vals = np.sort(np.linalg.eigvalsh(res.cov))[::-1]
    expected_major = math.sqrt(5.991) * math.sqrt(vals[0])
    assert res.semi_major_m == pytest.approx(expected_major, rel=0.02)


# --- R95 is the EMPIRICAL sample quantile, NOT the major semi-axis (§4) -------------


def test_r95_is_empirical_quantile_not_major_semi_axis():
    # On a heading-limited oblique point the cloud is a cross-range arc; the major semi-axis
    # over-states the equal-coverage circle. R95 (the equal-coverage radius) must be
    # STRICTLY LESS than the major semi-axis there (the whole point of §4's honesty fix).
    cam = _nadir_cam()
    mc = MonteCarloUncertainty(error_model=SensorErrorModel(), n_draws=4000, seed=2)
    # Oblique: pitch the airframe so the camera looks well off nadir at long range.
    res = mc.propagate(_pose(80.0, pitch=45.0), cam, _center_pixel(cam))
    assert res.r95_m < res.semi_major_m
    # And R95 must actually contain ~95% of the sampled radii (it's the 95th pct by defn).
    assert 0.90 < res.coverage_of_own_r95 < 1.0


# --- heading-limited oblique -> large, elongated ellipse ----------------------------


def test_heading_limited_oblique_is_large_and_elongated():
    cam = _nadir_cam()
    mc = MonteCarloUncertainty(error_model=SensorErrorModel(), n_draws=2000, seed=3)
    near = mc.propagate(_pose(40.0, pitch=0.0), cam, _center_pixel(cam))  # near-nadir, low
    obliq = mc.propagate(_pose(120.0, pitch=50.0), cam, _center_pixel(cam))  # oblique, high
    assert obliq.r95_m > near.r95_m  # oblique/long is much worse
    # Elongated: the oblique ellipse is far from circular (aspect ratio well above 1).
    assert obliq.semi_major_m / obliq.semi_minor_m > 1.5


# --- common-mode bias drawn ONCE per contact (not per frame) ------------------------


def test_heading_bias_widens_the_cloud():
    # Isolate the heading terms (jitter OFF) so the bias contribution is the only heading
    # noise. A large crab bias must widen the MC cloud (bigger R95) vs no heading error at
    # all. This is the MC side of the §2 bias floor: the common-mode bias is real dispersion,
    # not something averaging removed.
    cam = _nadir_cam()
    quiet = SensorErrorModel(
        gps_horiz_sigma_m=0.0, gps_vert_sigma_m=0.0, roll_sigma_deg=0.0,
        pitch_sigma_deg=0.0, yaw_jitter_sigma_deg=0.0, boresight_sigma_deg=0.0,
        sigma_h_m=0.0, pixel_sigma_px=0.0, t_sync_jitter_ms=0.0,
        heading_bias_sigma_deg=0.0, crab_angle_deg=0.0,
    )
    with_bias = SensorErrorModel(
        gps_horiz_sigma_m=0.0, gps_vert_sigma_m=0.0, roll_sigma_deg=0.0,
        pitch_sigma_deg=0.0, yaw_jitter_sigma_deg=0.0, boresight_sigma_deg=0.0,
        sigma_h_m=0.0, pixel_sigma_px=0.0, t_sync_jitter_ms=0.0,
        heading_bias_sigma_deg=15.0, crab_angle_deg=10.0, crab_sign_random=True,
    )
    r_quiet = MonteCarloUncertainty(quiet, n_draws=2000, seed=7).propagate(
        _pose(80.0, pitch=30.0), cam, _center_pixel(cam)
    ).r95_m
    r_bias = MonteCarloUncertainty(with_bias, n_draws=2000, seed=7).propagate(
        _pose(80.0, pitch=30.0), cam, _center_pixel(cam)
    ).r95_m
    assert r_bias > r_quiet + 1.0


# --- near-horizon instability -> CUE_ONLY + reject fraction reported -----------------


def test_near_horizon_high_reject_fraction_forces_cue_only():
    cam = _nadir_cam()
    # Pitch the camera to look NEAR the horizon (well past the 65 deg gate): the large yaw/
    # pitch jitter tips a big fraction of MC rays at/above the horizon -> they reject, and the
    # contact is near-horizon-unstable -> forced CUE_ONLY with a floor, never a tight number.
    mc = MonteCarloUncertainty(error_model=SensorErrorModel(), n_draws=2000, seed=4)
    res = mc.propagate(_pose(80.0, pitch=88.0), cam, _center_pixel(cam))
    assert res.reject_fraction > 0.05
    assert res.actionability_class == "CUE_ONLY"
    assert res.r95_m >= res.floor_radius_m  # floored, never a tight false number


def test_stable_geometry_has_low_reject_fraction():
    cam = _nadir_cam()
    mc = MonteCarloUncertainty(error_model=SensorErrorModel(), n_draws=2000, seed=5)
    res = mc.propagate(_pose(80.0, pitch=0.0), cam, _center_pixel(cam))
    assert res.reject_fraction < 0.01


# --- determinism + sample-count stability -------------------------------------------


def test_deterministic_under_fixed_seed():
    cam = _nadir_cam()
    a = MonteCarloUncertainty(error_model=SensorErrorModel(), n_draws=1000, seed=11)
    b = MonteCarloUncertainty(error_model=SensorErrorModel(), n_draws=1000, seed=11)
    ra = a.propagate(_pose(80.0, pitch=20.0), cam, _center_pixel(cam))
    rb = b.propagate(_pose(80.0, pitch=20.0), cam, _center_pixel(cam))
    assert ra.r95_m == pytest.approx(rb.r95_m)
