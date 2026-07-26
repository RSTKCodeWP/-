"""Tests for the Projector (Task 3.5).

The Projector turns each `Detection` into a cheap per-detection ground point by calling
`geometry.ray_to_ground` (the SAME shared function Fuse uses — never re-implemented). Per
DESIGN.md §3.2 it projects the box's **bottom-center** `((x_min+x_max)/2, y_max)` on the
feet-on-ground assumption (the seam the detector→localizer glue test, Task 4.8, guards).

Each ground point is **tagged with the frame-gate verdict** (Task 3.3) so Confirmation
(3.6) clusters only gate-passing points, while gated-out / un-projectable detections still
surface as CUE-ONLY contacts — a detection is NEVER dropped from visibility, only marked.
"""

from __future__ import annotations

import numpy as np
import pytest

from hades.detect.detector import Detection
from hades.ingest.telemetry_source import Pose
from hades.locate.camera_model import CameraModel
from hades.locate.frame_gate import GateVerdict
from hades.locate.projector import GroundPoint, Projector

_METERS_PER_DEG = 111320.0


def _nadir_cam() -> CameraModel:
    return CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=960.0, mount="nadir")


def _pose(**kw) -> Pose:
    base = dict(
        t=0.0, lat=0.0, lon=0.0, alt=100.0, alt_datum="REL_TAKEOFF",
        roll=0.0, pitch=0.0, yaw=0.0,
    )
    base.update(kw)
    return Pose(**base)


def test_projects_bottom_center_not_box_center():
    # The reference point is bottom-center (feet on ground), NOT the box center. A box
    # whose bottom-center is at the image center projects directly below the drone; if the
    # projector wrongly used the box CENTER the y-offset would shift the ground point.
    proj = Projector(camera=_nadir_cam())
    # Box bottom-center == image center (960, 960): x in [940,980] → cx=960; y_max=960.
    det = Detection(box_xyxy=(940.0, 900.0, 980.0, 960.0), conf=0.9)
    out = proj.project([det], _pose())
    assert len(out) == 1
    gp = out[0]
    assert gp.lat == pytest.approx(0.0, abs=1e-9)
    assert gp.lon == pytest.approx(0.0, abs=1e-9)


def test_ground_point_carries_detection_and_gate_verdict():
    proj = Projector(camera=_nadir_cam())
    det = Detection(box_xyxy=(940.0, 900.0, 980.0, 960.0), conf=0.85)
    out = proj.project([det], _pose())
    gp = out[0]
    assert isinstance(gp, GroundPoint)
    assert gp.detection is det
    assert gp.conf == 0.85
    assert gp.verdict in (GateVerdict.PASS, GateVerdict.PASS_UNVERIFIED, GateVerdict.REJECT)


def test_offcenter_box_projects_offset_east():
    # Bottom-center at (1060, 960) → (u-cx)=+100px → 10 m East at H=100, nadir.
    proj = Projector(camera=_nadir_cam())
    det = Detection(box_xyxy=(1040.0, 900.0, 1080.0, 960.0), conf=0.9)
    out = proj.project([det], _pose())
    gp = out[0]
    expected_lon = 10.0 / (_METERS_PER_DEG * np.cos(0.0))
    assert gp.lon == pytest.approx(expected_lon, rel=1e-6)
    assert gp.fusable is True  # nadir replay frame → PASS_UNVERIFIED, still fusable


def test_srt_replay_pose_yields_unverified_but_projectable():
    # The replay path: full attitude is supplied to the projector (a pitch source feeds it
    # — here a level/near-nadir pose), but no IMU → PASS_UNVERIFIED, still a ground point.
    proj = Projector(camera=_nadir_cam())
    det = Detection(box_xyxy=(940.0, 900.0, 980.0, 960.0), conf=0.9)
    out = proj.project([det], _pose())
    assert out[0].verdict is GateVerdict.PASS_UNVERIFIED
    assert out[0].fusable is True


def test_oblique_pose_gated_out_but_still_surfaced():
    # An oblique frame (camera pitched far from nadir) is REJECTED by the gate, but the
    # detection is NOT dropped — it surfaces as a non-fusable (CUE-ONLY) ground point.
    proj = Projector(camera=CameraModel(
        fx=1000.0, fy=1000.0, cx=960.0, cy=960.0, mount="forward"
    ), mount_angle_from_nadir_deg=85.0)
    det = Detection(box_xyxy=(940.0, 900.0, 980.0, 960.0), conf=0.9)
    out = proj.project([det], _pose(pitch=-10.0))  # forward+down, still very oblique
    assert len(out) == 1  # surfaced, not dropped
    assert out[0].verdict is GateVerdict.REJECT
    assert out[0].fusable is False


def test_unprojectable_detection_surfaces_without_coordinate():
    # A ray that REJECTs (points above the horizon) → the detection still surfaces, but
    # with no lat/lon (a CUE-ONLY contact). Never silently dropped.
    proj = Projector(camera=CameraModel(
        fx=1000.0, fy=1000.0, cx=960.0, cy=960.0, mount="forward"
    ), mount_angle_from_nadir_deg=0.0)
    det = Detection(box_xyxy=(940.0, 900.0, 980.0, 960.0), conf=0.9)
    out = proj.project([det], _pose(pitch=10.0))  # forward, nose-up → above horizon
    assert len(out) == 1
    gp = out[0]
    assert gp.lat is None and gp.lon is None
    assert gp.fusable is False


def test_position_only_pose_surfaces_all_unprojectable():
    # A raw position-only pose (attitude None) can't be projected; every detection still
    # surfaces (CUE-ONLY), none dropped — visibility is never gated.
    proj = Projector(camera=_nadir_cam())
    dets = [
        Detection(box_xyxy=(940.0, 900.0, 980.0, 960.0), conf=0.9),
        Detection(box_xyxy=(100.0, 100.0, 140.0, 180.0), conf=0.7),
    ]
    pose = Pose(
        t=0.0, lat=0.0, lon=0.0, alt=100.0, alt_datum="REL_TAKEOFF",
        roll=None, pitch=None, yaw=None,
    )
    out = proj.project(dets, pose)
    assert len(out) == 2
    assert all(gp.lat is None for gp in out)
    assert all(not gp.fusable for gp in out)


def test_empty_detections_yields_empty():
    proj = Projector(camera=_nadir_cam())
    assert proj.project([], _pose()) == []


def test_non_finite_projection_is_not_marked_fusable():
    # Review F3 (projector side): a detection that projects to a non-finite coordinate must
    # surface as CUE-ONLY (lat/lon None, not fusable), never as a fusable (nan, nan) pin
    # that would poison the fused estimate. A NaN box-center triggers the geometry refusal,
    # which the projector turns into an honest unprojectable.
    import math

    proj = Projector(camera=_nadir_cam())
    det = Detection(box_xyxy=(float("nan"), 900.0, float("nan") + 40.0, 960.0), conf=0.9)
    out = proj.project([det], _pose())
    gp = out[0]
    assert gp.lat is None and gp.lon is None
    assert gp.fusable is False
    # And belt-and-suspenders: fusable must reject a NaN coordinate even if one slipped in.
    bad = GroundPoint(detection=Detection(box_xyxy=(1, 1, 2, 2), conf=0.5),
                      lat=math.nan, lon=math.nan, conf=0.5,
                      verdict=out[0].verdict)
    assert bad.fusable is False


def test_camera_pitch_combines_mount_and_airframe():
    # camera pitch from nadir = mount_angle + |airframe pitch contribution|. A nadir mount
    # (0° from nadir) with a level airframe → ~0° from nadir → not oblique → gate evaluable
    # as good geometry. Verify the gate sees a near-nadir pitch (PASS_UNVERIFIED on replay).
    proj = Projector(camera=_nadir_cam(), mount_angle_from_nadir_deg=0.0)
    det = Detection(box_xyxy=(940.0, 900.0, 980.0, 960.0), conf=0.9)
    out = proj.project([det], _pose(pitch=0.0))
    assert out[0].verdict is GateVerdict.PASS_UNVERIFIED  # near-nadir, no IMU
