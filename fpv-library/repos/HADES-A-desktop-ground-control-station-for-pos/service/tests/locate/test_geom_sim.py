"""Tests for the geometric simulator (Task 4.2; research gate §6).

The simulator's `world_to_pixel` is the FORWARD-collinearity equation (world -> pixel). It
is the ground-truth generator for the meter-error metric, so its independence from
`ray_to_ground` is the anti-circularity guarantee for meter error (§4 Risk A):

  > `world_to_pixel` MUST NOT call, import, or invert `ray_to_ground`. It shares ONLY the
  > convention builders (`geometry.R_world_body`, `CameraModel.K`, `CameraModel.R_body_cam`).

The proof is NOT the round-trip alone (a shared rotation bug would cancel in a round-trip
and still pass). It is that each path is pinned to its OWN hand-derived analytic fixtures.
So this module anchors `world_to_pixel` against similar-triangle truth with NO reference to
any `ray_to_ground` output — the independent anchor. The round-trip below is a necessary
sanity check on top, not the guarantee.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from hades.ingest.telemetry_source import Pose
from hades.locate.camera_model import CameraModel
from hades.locate.error_model import SensorErrorModel
from hades.locate.geom_sim import (
    GeomSim,
    OrbitPath,
    StraightPass,
    world_to_pixel,
)
from hades.locate.geometry import ray_to_ground

_M_PER_DEG = 111320.0


def _nadir_cam() -> CameraModel:
    # Square pinhole, principal point at image center; nadir mount (optical +z = down).
    return CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=540.0, mount="nadir")


def _level_pose(lat: float, lon: float, agl: float) -> Pose:
    # Level + north-facing, REL_TAKEOFF alt == AGL (ground_elev 0). Full attitude present.
    return Pose(
        t=0.0, lat=lat, lon=lon, alt=agl, alt_datum="REL_TAKEOFF",
        roll=0.0, pitch=0.0, yaw=0.0,
    )


# --- world_to_pixel: INDEPENDENT analytic anchors (similar-triangle truth) ---------


def test_nadir_target_directly_below_lands_at_principal_point():
    cam = _nadir_cam()
    pose = _level_pose(40.0, -74.0, 100.0)
    # Target exactly at the drone's ground nadir -> image center, by symmetry.
    u, v = world_to_pixel(pose, cam, target_latlon=(40.0, -74.0), ground_elev=0.0)
    assert u == pytest.approx(cam.cx, abs=1e-6)
    assert v == pytest.approx(cam.cy, abs=1e-6)


def test_target_10m_east_at_h100_lands_at_hand_computed_pixel():
    # Hand truth (similar triangles, nadir mount, level pose): a point 10 m East at
    # H=100 subtends x/z = 10/100 = 0.1 in the optical frame; the nadir boresight maps
    # body-East to optical +x, so u = cx + fx*0.1, v = cy. NO reference to ray_to_ground.
    cam = _nadir_cam()
    pose = _level_pose(40.0, -74.0, 100.0)
    east_deg = 10.0 / (_M_PER_DEG * math.cos(math.radians(40.0)))
    target = (40.0, -74.0 + east_deg)
    u, v = world_to_pixel(pose, cam, target_latlon=target, ground_elev=0.0)
    assert u == pytest.approx(cam.cx + cam.fx * 0.1, abs=1e-4)
    assert v == pytest.approx(cam.cy, abs=1e-4)


def test_target_north_lands_above_center_for_nadir_mount():
    # Nadir boresight maps top-of-image to forward/North (camera_model docstring), so a
    # target to the North must land ABOVE the principal point (smaller v). Independent of
    # ray_to_ground; just checks the forward map's sign convention.
    cam = _nadir_cam()
    pose = _level_pose(40.0, -74.0, 100.0)
    north_deg = 10.0 / _M_PER_DEG
    u, v = world_to_pixel(pose, cam, target_latlon=(40.0 + north_deg, -74.0), ground_elev=0.0)
    assert u == pytest.approx(cam.cx, abs=1e-4)
    assert v < cam.cy  # North is up in the image


def test_target_behind_camera_returns_none():
    # A nadir camera cannot see a point ABOVE its horizon. Use a forward mount tilted so
    # the target is behind the lens -> r_cam[2] <= 0 -> None (not visible), never a
    # phantom pixel. Here: forward mount, target directly below = behind a forward lens.
    cam = CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=540.0, mount="forward")
    pose = _level_pose(40.0, -74.0, 100.0)
    assert world_to_pixel(pose, cam, target_latlon=(40.0, -74.0), ground_elev=0.0) is None


# --- world_to_pixel does NOT depend on ray_to_ground (the architectural rule) -------


def test_geom_sim_module_does_not_import_ray_to_ground():
    # Static guarantee: the forward path shares only the convention builders, never the
    # solver. Parse the module's AST and assert ray_to_ground is never IMPORTED (a prose
    # mention in the docstring explaining the rule is fine; an import/call is not).
    import ast
    import inspect

    import hades.locate.geom_sim as gs

    tree = ast.parse(inspect.getsource(gs))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert "ray_to_ground" not in imported, (
        "geom_sim must not import ray_to_ground (the solver) — only the convention "
        "builders (R_world_body, K, R_body_cam). §4 Risk A."
    )
    # And it must not be referenced by name anywhere in the code (call sites).
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "ray_to_ground" not in called


# --- zero-noise round-trip (NECESSARY sanity check, NOT the proof) ------------------


@pytest.mark.parametrize(
    "lat,lon,agl,roll,pitch,yaw",
    [
        (40.0, -74.0, 100.0, 0.0, 0.0, 0.0),
        (40.0, -74.0, 80.0, 0.0, 10.0, 30.0),  # oblique + yawed
        (-33.9, 18.4, 120.0, 2.0, -15.0, 200.0),  # southern hemisphere, rolled
    ],
)
def test_zero_noise_round_trip_recovers_target(lat, lon, agl, roll, pitch, yaw):
    cam = _nadir_cam()
    pose = Pose(
        t=0.0, lat=lat, lon=lon, alt=agl, alt_datum="REL_TAKEOFF",
        roll=roll, pitch=pitch, yaw=yaw,
    )
    # Pick a target on the ground in front of/below the camera by projecting a known pixel
    # offset is circular; instead place a target a few meters away and require the forward
    # then inverse map to return it. Use a small offset that stays in front of a nadir lens.
    north_deg = 7.0 / _M_PER_DEG
    east_deg = -4.0 / (_M_PER_DEG * math.cos(math.radians(lat)))
    target = (lat + north_deg, lon + east_deg)
    px = world_to_pixel(pose, cam, target_latlon=target, ground_elev=0.0)
    assert px is not None, "target should be visible for these geometries"
    back = ray_to_ground(pose, cam, pixel=px, ground_elev=0.0, ground_elev_datum="REL_TAKEOFF")
    # Convert the recovered (lat,lon) error to meters and assert < 1e-6 m.
    dlat_m = (back[0] - target[0]) * _M_PER_DEG
    dlon_m = (back[1] - target[1]) * _M_PER_DEG * math.cos(math.radians(lat))
    assert math.hypot(dlat_m, dlon_m) < 1e-6


# --- flight paths: analytic, closed-form, geometry computed exactly -----------------


def test_straight_pass_yields_full_attitude_poses_over_the_target():
    target = (40.0, -74.0)
    path = StraightPass(target_latlon=target, agl_m=80.0, speed_mps=15.0, n_frames=20)
    frames = list(path.frames())
    assert len(frames) == 20
    # Every pose carries full attitude (the synthetic full-attitude mode) and a seq index.
    for i, gt in enumerate(frames):
        assert gt.pose_true.roll is not None
        assert gt.pose_true.pitch is not None
        assert gt.pose_true.yaw is not None
        assert gt.pose_true.seq == i
        assert gt.slant_range_m > 0.0
        assert 0.0 <= gt.nadir_angle_deg <= 90.0
    # A straight pass over the target has near-zero aspect diversity: the bearing to the
    # target barely changes sign-spread. (Used by the §2 single-pass-floor validation.)
    bearings = [gt.target_bearing_deg for gt in frames]
    spread = max(bearings) - min(bearings)
    assert spread < 200.0  # not a full orbit; one-sided pass


def test_orbit_path_sweeps_aspect_diversity():
    # An orbit observes the target from a SPREAD of azimuths — the geometry that lets the
    # §2 bias floor relax. Bearings must span a wide arc.
    target = (40.0, -74.0)
    path = OrbitPath(target_latlon=target, agl_m=80.0, radius_m=120.0, n_frames=36)
    frames = list(path.frames())
    assert len(frames) == 36
    bearings = np.array([gt.target_bearing_deg for gt in frames])
    # A full orbit covers ~360 deg of bearing to the target.
    assert bearings.max() - bearings.min() > 270.0


def test_orbit_nadir_angle_matches_atan_radius_over_height():
    # Camera pitch from nadir on an orbit is set by geometry: atan2(radius, height).
    target = (40.0, -74.0)
    path = OrbitPath(target_latlon=target, agl_m=100.0, radius_m=100.0, n_frames=8)
    expected = math.degrees(math.atan2(100.0, 100.0))  # 45 deg
    for gt in path.frames():
        assert gt.nadir_angle_deg == pytest.approx(expected, abs=2.0)


# --- the sim: ground truth is the INPUT target, never derived from ray_to_ground ----


def test_sim_run_emits_measured_and_true_per_frame():
    target = (40.0, -74.0)
    path = StraightPass(target_latlon=target, agl_m=80.0, speed_mps=15.0, n_frames=10)
    sim = GeomSim(camera=_nadir_cam(), ground_elev=0.0)
    null = SensorErrorModel(
        gps_horiz_sigma_m=0.0, gps_vert_sigma_m=0.0, roll_sigma_deg=0.0,
        pitch_sigma_deg=0.0, yaw_jitter_sigma_deg=0.0, heading_bias_sigma_deg=0.0,
        crab_angle_deg=0.0, boresight_sigma_deg=0.0, t_sync_offset_ms=0.0,
        t_sync_jitter_ms=0.0, sigma_h_m=0.0, pixel_sigma_px=0.0,
    )
    frames = sim.run(path, error_model=null, seed=0)
    assert len(frames) == 10
    for sf in frames:
        # Ground truth is the input target — NEVER derived from ray_to_ground.
        assert sf.target_latlon == target
        # With a null error model, measured == true (no noise injected).
        assert sf.pose_meas.lat == pytest.approx(sf.pose_true.lat)
        assert sf.pixel_meas[0] == pytest.approx(sf.pixel_true[0])
        assert sf.pixel_meas[1] == pytest.approx(sf.pixel_true[1])


def test_time_sync_offset_injects_systematic_downtrack_displacement():
    # §5 headline: a constant t_sync_offset displaces the reported pose DOWN-TRACK by
    # velocity * Delta, a systematic same-direction bias (not zero-mean). On a North-bound
    # straight pass at 15 m/s with a 100 ms offset, the measured latitude should sit ~1.5 m
    # North of truth on average, with no other noise present.
    import dataclasses

    target = (40.0, -74.0)
    path = StraightPass(target_latlon=target, agl_m=80.0, speed_mps=15.0, n_frames=20)
    sim = GeomSim(camera=_nadir_cam(), ground_elev=0.0)
    only_tsync = SensorErrorModel(
        gps_horiz_sigma_m=0.0, gps_vert_sigma_m=0.0, roll_sigma_deg=0.0,
        pitch_sigma_deg=0.0, yaw_jitter_sigma_deg=0.0, heading_bias_sigma_deg=0.0,
        crab_angle_deg=0.0, boresight_sigma_deg=0.0, t_sync_jitter_ms=0.0,
        sigma_h_m=0.0, pixel_sigma_px=0.0,
    )
    only_tsync = dataclasses.replace(only_tsync, t_sync_offset_ms=100.0)
    frames = sim.run(path, error_model=only_tsync, seed=0)
    # Mean North displacement of measured vs true, in meters.
    dnorth_m = np.mean([
        (sf.pose_meas.lat - sf.pose_true.lat) * _M_PER_DEG for sf in frames
    ])
    assert dnorth_m == pytest.approx(15.0 * 0.1, abs=0.2)  # v * Delta = 1.5 m, same sign


def test_sim_run_injects_noise_with_nonnull_model():
    target = (40.0, -74.0)
    path = StraightPass(target_latlon=target, agl_m=80.0, speed_mps=15.0, n_frames=30)
    sim = GeomSim(camera=_nadir_cam(), ground_elev=0.0)
    frames = sim.run(path, error_model=SensorErrorModel(), seed=42)
    # Noise was injected: measured poses differ from true (at least one field moved).
    moved = any(
        abs((sf.pose_meas.lat or 0) - (sf.pose_true.lat or 0)) > 0 for sf in frames
    )
    assert moved
    # Deterministic under a fixed seed: re-running gives identical draws.
    frames2 = sim.run(path, error_model=SensorErrorModel(), seed=42)
    assert frames[0].pose_meas.lat == pytest.approx(frames2[0].pose_meas.lat)
