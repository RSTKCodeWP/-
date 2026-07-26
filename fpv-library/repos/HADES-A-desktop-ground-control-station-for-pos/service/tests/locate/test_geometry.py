"""Tests for the shared ray→ground geometry (Task 3.4) — the single source of truth.

`ray_to_ground` is THE one function imported by both the Projector (Task 3.5) and Fuse
(Phase 4) — never re-implemented (the discipline that prevents the coordinate-convention
divergence the design fears). It is verified here against ANALYTIC truth with every
DESIGN.md §3.1-§3.4 convention explicit:

  undistort(pixel) → K⁻¹·pixel (optical ray, +z into scene)
    → R_world_body · R_body_cam · ray  (active rotate optical → ENU world)
    → require ray·Up < 0 else REJECT   (no phantom pin behind the drone)
    → intersect flat-earth plane at the operator ground elevation (AGL)
    → ENU offset → (lat, lon) WGS84 degrees, (lat, lon) order.

The expected numbers below come from an independent scipy/numpy derivation (machine
precision), not hand math. R_world_body is built from the aerospace ZYX (yaw,pitch,roll)
Euler sequence then the fixed NED→ENU axis adapter; +pitch = nose-up needs NO sign flip
(the adapter handles it). Drone is at ENU (0,0,H) with H = AGL = drone_alt − ground_elev.
"""

from __future__ import annotations

import numpy as np
import pytest

from hades.ingest.telemetry_source import Pose
from hades.locate.camera_model import CameraModel
from hades.locate.geometry import R_world_body, ray_to_ground

_METERS_PER_DEG = 111320.0


# --- R_world_body sanity (ENU <- FRD), analytic checks ----------------------


def test_rwb_level_north_maps_forward_to_north():
    # (roll,pitch,yaw)=(0,0,0): body x-forward [1,0,0] → ENU North [0,1,0].
    R = R_world_body(0.0, 0.0, 0.0)
    assert np.allclose(R @ [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], atol=1e-12)


def test_rwb_yaw_90_maps_forward_to_east():
    R = R_world_body(0.0, 0.0, 90.0)
    assert np.allclose(R @ [1.0, 0.0, 0.0], [1.0, 0.0, 0.0], atol=1e-12)


def test_rwb_pitch_up_tilts_forward_axis_up():
    # +pitch = nose-up → body x-forward gains a POSITIVE up-component (no sign flip).
    R = R_world_body(0.0, 10.0, 0.0)
    fwd = R @ [1.0, 0.0, 0.0]
    assert fwd[2] > 0.0  # up-component positive
    assert np.allclose(fwd, [0.0, 0.98481, 0.17365], atol=1e-4)


def test_rwb_is_proper_rotation():
    R = R_world_body(15.0, -20.0, 47.0)
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-12)
    assert np.isclose(np.linalg.det(R), 1.0)


# --- full pipeline analytic cases (the canonical truth) ---------------------


def _pose(lat, lon, agl_alt, roll=0.0, pitch=0.0, yaw=0.0) -> Pose:
    # alt is REL_TAKEOFF here and ground_elev defaults to 0 in the same datum, so
    # H = AGL = alt - 0 = agl_alt. (Datum handling is tested separately below.)
    return Pose(
        t=0.0, lat=lat, lon=lon, alt=agl_alt, alt_datum="REL_TAKEOFF",
        roll=roll, pitch=pitch, yaw=yaw,
    )


def _nadir_cam(fx=1000.0, fy=1000.0, cx=960.0, cy=960.0) -> CameraModel:
    return CameraModel(fx=fx, fy=fy, cx=cx, cy=cy, mount="nadir")


def test_case_a_nadir_center_pixel_lands_directly_below():
    # NADIR, center pixel, H=100 → ground directly below drone → (lat,lon)=(0,0).
    pose = _pose(lat=0.0, lon=0.0, agl_alt=100.0)
    lat, lon = ray_to_ground(pose, _nadir_cam(), pixel=(960.0, 960.0), ground_elev=0.0)
    assert lat == pytest.approx(0.0, abs=1e-12)
    assert lon == pytest.approx(0.0, abs=1e-12)


def test_case_b_nadir_offcenter_pixel_lands_east():
    # NADIR, (u-cx)=+100px, fx=1000, H=100 → ray [0.1,0,1] → ENU (10,0,0) → 10 m East.
    pose = _pose(lat=0.0, lon=0.0, agl_alt=100.0)
    lat, lon = ray_to_ground(
        pose, _nadir_cam(), pixel=(960.0 + 100.0, 960.0), ground_elev=0.0
    )
    expected_lon = 10.0 / (_METERS_PER_DEG * np.cos(np.radians(0.0)))
    assert lat == pytest.approx(0.0, abs=1e-12)
    assert lon == pytest.approx(expected_lon, rel=1e-9)
    assert lon == pytest.approx(8.983111749910169e-05, rel=1e-9)


def test_case_c_forward_horizon_rejects():
    # FORWARD mount looking at the horizon (d_up >= 0) → REJECT (no phantom pin).
    forward = CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=960.0, mount="forward")
    pose = _pose(lat=0.0, lon=0.0, agl_alt=100.0, pitch=0.0)
    with pytest.raises(ValueError, match="REJECT|horizon|up"):
        ray_to_ground(pose, forward, pixel=(960.0, 960.0), ground_elev=0.0)


def test_case_c_forward_nose_up_rejects():
    # Nose-up makes a forward camera look ABOVE the horizon → still REJECT.
    forward = CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=960.0, mount="forward")
    pose = _pose(lat=0.0, lon=0.0, agl_alt=100.0, pitch=10.0)
    with pytest.raises(ValueError):
        ray_to_ground(pose, forward, pixel=(960.0, 960.0), ground_elev=0.0)


def test_forward_nose_down_hits_ground_north():
    # Forward camera pitched 30° down hits the ground 173.2 m due North (sanity it CAN hit).
    forward = CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=960.0, mount="forward")
    pose = _pose(lat=0.0, lon=0.0, agl_alt=100.0, pitch=-30.0)
    lat, lon = ray_to_ground(pose, forward, pixel=(960.0, 960.0), ground_elev=0.0)
    expected_lat = 173.20508 / _METERS_PER_DEG
    assert lat == pytest.approx(expected_lat, rel=1e-5)
    assert lon == pytest.approx(0.0, abs=1e-9)


def test_case_d_heading_rotates_ground_point():
    # NADIR off-center pixel: yaw=0 → 10 m East; yaw=90 → the same image-right offset now
    # points South (the whole frame rotates with heading).
    cam = _nadir_cam()
    pixel = (960.0 + 100.0, 960.0)

    pose0 = _pose(lat=0.0, lon=0.0, agl_alt=100.0, yaw=0.0)
    lat0, lon0 = ray_to_ground(pose0, cam, pixel=pixel, ground_elev=0.0)
    assert lon0 > 0.0  # East
    assert lat0 == pytest.approx(0.0, abs=1e-9)

    pose90 = _pose(lat=0.0, lon=0.0, agl_alt=100.0, yaw=90.0)
    lat90, lon90 = ray_to_ground(pose90, cam, pixel=pixel, ground_elev=0.0)
    assert lat90 < 0.0  # South
    assert lon90 == pytest.approx(0.0, abs=1e-9)


def test_image_lower_half_projects_behind_drone():
    # Sign trap 1: image +y is DOWN. A pixel BELOW center (v>cy) under the nadir mount,
    # level/North, projects BEHIND the drone (South). Guards the §3.2 mirror-bug class.
    pose = _pose(lat=0.0, lon=0.0, agl_alt=100.0)
    cam = _nadir_cam()
    lat, _lon = ray_to_ground(pose, cam, pixel=(960.0, 960.0 + 100.0), ground_elev=0.0)
    assert lat < 0.0  # South of the drone (behind, for a North-facing nadir frame)


# --- AGL / datum handling (DESIGN.md §3.1, §3.5) ----------------------------


def test_agl_subtracts_ground_elev_same_datum():
    # H = drone_alt − ground_elev when both share a datum. 150 m alt, 50 m ground → H=100.
    pose = Pose(
        t=0.0, lat=0.0, lon=0.0, alt=150.0, alt_datum="MSL", roll=0.0, pitch=0.0, yaw=0.0
    )
    # Off-center so range scales with H: H=100 with (u-cx)=+100px,fx=1000 → 10 m East.
    cam = _nadir_cam()
    _lat, lon = ray_to_ground(
        pose, cam, pixel=(960.0 + 100.0, 960.0), ground_elev=50.0, ground_elev_datum="MSL"
    )
    assert lon == pytest.approx(8.983111749910169e-05, rel=1e-6)


def test_refuses_to_mix_rel_takeoff_with_absolute_datum():
    # DESIGN.md §3.1/§3.5: ray_to_ground must REFUSE to subtract REL_TAKEOFF against an
    # absolute datum (or UNKNOWN) rather than silently inject a ~30 m geoid error.
    pose = _pose(lat=0.0, lon=0.0, agl_alt=100.0)  # REL_TAKEOFF
    cam = _nadir_cam()
    with pytest.raises(ValueError, match="datum"):
        ray_to_ground(
            pose, cam, pixel=(960.0, 960.0), ground_elev=50.0, ground_elev_datum="MSL"
        )


def test_refuses_hae_vs_msl_mixing():
    # Review F1: HAE and MSL differ by the geoid undulation (~−25 to −35 m on hurricane
    # coasts, DESIGN.md §3.5). Subtracting one against the other silently injects a ~30 m
    # AGL error. We have no geoid-normalization, so refuse rather than blind-subtract —
    # don't present a finished guard for a datum pair we can't actually reconcile.
    pose = Pose(
        t=0.0, lat=29.0, lon=-90.0, alt=120.0, alt_datum="HAE",
        roll=0.0, pitch=0.0, yaw=0.0,
    )
    cam = _nadir_cam()
    with pytest.raises(ValueError, match="datum|geoid|HAE|MSL"):
        ray_to_ground(
            pose, cam, pixel=(960.0, 960.0), ground_elev=0.0, ground_elev_datum="MSL"
        )


def test_same_absolute_datum_still_allowed():
    # The fix must NOT break same-datum subtraction: HAE/HAE and MSL/MSL still compute.
    for datum in ("HAE", "MSL"):
        pose = Pose(
            t=0.0, lat=0.0, lon=0.0, alt=150.0, alt_datum=datum,
            roll=0.0, pitch=0.0, yaw=0.0,
        )
        lat, _lon = ray_to_ground(
            _set := pose, _nadir_cam(), pixel=(960.0, 960.0),
            ground_elev=50.0, ground_elev_datum=datum,
        )
        assert lat == pytest.approx(0.0, abs=1e-12)


def test_refuses_unknown_vs_unknown():
    # Review F2: two UNKNOWN-tagged altitudes are by definition of possibly-different
    # datums (the tag exists because the datum couldn't be determined). Subtracting them
    # can implicitly mix HAE/MSL → wrong AGL. UNKNOWN must never feed a subtraction, even
    # against itself (matches the geometry docstring's stated contract).
    pose = Pose(
        t=0.0, lat=0.0, lon=0.0, alt=100.0, alt_datum="UNKNOWN",
        roll=0.0, pitch=0.0, yaw=0.0,
    )
    cam = _nadir_cam()
    with pytest.raises(ValueError, match="datum|UNKNOWN"):
        ray_to_ground(
            pose, cam, pixel=(960.0, 960.0), ground_elev=0.0, ground_elev_datum="UNKNOWN"
        )


def test_non_finite_pose_fields_refused():
    # Codex P1 (geometry:120): GPS/attitude/alt checked for None but NOT finiteness. A NaN
    # or inf lat/alt/attitude must be refused, not flowed through to a (nan, nan) pin.
    cam = _nadir_cam()
    for field in ("lat", "alt", "roll", "pitch", "yaw"):
        kw = dict(
            t=0.0, lat=0.0, lon=0.0, alt=100.0, alt_datum="REL_TAKEOFF",
            roll=0.0, pitch=0.0, yaw=0.0,
        )
        kw[field] = float("nan")
        with pytest.raises(ValueError):
            ray_to_ground(Pose(**kw), cam, pixel=(960.0, 960.0), ground_elev=0.0)


def test_non_finite_ground_elev_refused():
    pose = _pose(lat=0.0, lon=0.0, agl_alt=100.0)
    cam = _nadir_cam()
    with pytest.raises(ValueError):
        ray_to_ground(pose, cam, pixel=(960.0, 960.0), ground_elev=float("inf"))


def test_unrecognized_datum_tag_refused():
    # Codex P1 (geometry:83): the same UNRECOGNIZED tag on both sides must NOT subtract. An
    # empty string / typo'd datum is "same" by ==, but it is not a known datum, so the AGL
    # is meaningless — refuse rather than inject a silent offset.
    cam = _nadir_cam()
    for bad in ("", "WGS84_TYPO", "agl"):
        pose = Pose(
            t=0.0, lat=0.0, lon=0.0, alt=100.0, alt_datum=bad,
            roll=0.0, pitch=0.0, yaw=0.0,
        )
        with pytest.raises(ValueError, match="datum"):
            ray_to_ground(
                pose, cam, pixel=(960.0, 960.0), ground_elev=0.0, ground_elev_datum=bad
            )


def test_non_finite_pixel_is_unprojectable_not_nan_pin():
    # Review F3: a NaN pixel must NOT produce a silent (nan, nan) coordinate. `nan >= 0` is
    # False so the horizon-reject doesn't fire; t = -H/nan = nan → (nan, nan), which would
    # then be marked fusable (nan is not None). That is the cardinal sin. Refuse instead.
    pose = _pose(lat=0.0, lon=0.0, agl_alt=100.0)
    cam = _nadir_cam()
    with pytest.raises(ValueError, match="finite|nan|NaN|pixel"):
        ray_to_ground(pose, cam, pixel=(float("nan"), 960.0), ground_elev=0.0)
    with pytest.raises(ValueError):
        ray_to_ground(pose, cam, pixel=(960.0, float("-inf")), ground_elev=0.0)


def test_rel_takeoff_with_zero_ground_elev_is_agl_directly():
    # The validation replay path: REL_TAKEOFF alt IS height-above-takeoff. With ground_elev
    # 0 in REL_TAKEOFF (takeoff point == ground reference), H = alt directly, no mixing.
    pose = _pose(lat=0.0, lon=0.0, agl_alt=80.0)
    cam = _nadir_cam()
    lat, lon = ray_to_ground(
        pose, cam, pixel=(960.0, 960.0), ground_elev=0.0, ground_elev_datum="REL_TAKEOFF"
    )
    assert lat == pytest.approx(0.0, abs=1e-12)


def test_missing_attitude_refuses_to_project():
    # A position-only Pose (roll/pitch/yaw None — the raw .srt path) must NOT be projected
    # by assuming level/north; the geometry refuses rather than fabricate an attitude.
    pose = Pose(
        t=0.0, lat=0.0, lon=0.0, alt=100.0, alt_datum="REL_TAKEOFF",
        roll=None, pitch=None, yaw=None,
    )
    cam = _nadir_cam()
    with pytest.raises(ValueError, match="attitude|None|pose"):
        ray_to_ground(pose, cam, pixel=(960.0, 960.0), ground_elev=0.0)


def test_no_gps_refuses_to_project():
    # No GPS fix (lat/lon None) → can't place an ENU origin → refuse, never plot at 0,0.
    pose = Pose(
        t=0.0, lat=None, lon=None, alt=100.0, alt_datum="REL_TAKEOFF",
        roll=0.0, pitch=0.0, yaw=0.0, gps_valid=False,
    )
    cam = _nadir_cam()
    with pytest.raises(ValueError, match="GPS|lat|position"):
        ray_to_ground(pose, cam, pixel=(960.0, 960.0), ground_elev=0.0)


def test_drone_below_ground_plane_rejects():
    # H must be > 0 (drone above the ground plane). A non-positive AGL is nonsensical input.
    pose = _pose(lat=0.0, lon=0.0, agl_alt=-5.0)
    cam = _nadir_cam()
    with pytest.raises(ValueError):
        ray_to_ground(pose, cam, pixel=(960.0, 960.0), ground_elev=0.0)
