"""Detector -> localizer coordinate-seam test (Task 4.8, M4).

This is the one seam the type system cannot catch: does a real `Detection`'s `box_xyxy`
(top-left origin, +x right / +y down per DESIGN.md §3.2) arrive at `ray_to_ground`'s `pixel`
argument in that EXACT convention, and is the box's BOTTOM-CENTER (feet-on-ground), not its
center, used as the ground-contact pixel? A swap or a center-vs-bottom mistake here produces a
silently-wrong coordinate - the named wiring-bug class. Distinct from the in-isolation
Projector unit test and the full E2E: it tests the Detection -> Projector -> Fuse seam with a
real Detection object built the way the detector emits it.
"""

from __future__ import annotations

import math

from hades.detect.detector import Detection
from hades.ingest.telemetry_source import Pose
from hades.locate.camera_model import CameraModel
from hades.locate.error_model import SensorErrorModel
from hades.locate.fuse import FuseObservation, Fuser
from hades.locate.geom_sim import world_to_pixel
from hades.locate.projector import Projector

_M_PER_DEG = 111320.0


def _nadir_cam() -> CameraModel:
    return CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=540.0, mount="nadir")


def _level_pose(lat: float, lon: float, agl: float) -> Pose:
    return Pose(
        t=0.0, lat=lat, lon=lon, alt=agl, alt_datum="REL_TAKEOFF",
        roll=0.0, pitch=0.0, yaw=0.0, seq=0,
    )


def _enu_error_m(a, b) -> float:
    dlat = (a[0] - b[0]) * _M_PER_DEG
    dlon = (a[1] - b[1]) * _M_PER_DEG * math.cos(math.radians(b[0]))
    return math.hypot(dlat, dlon)


def test_detection_bottom_center_projects_to_the_right_ground_point():
    # Build the ground truth backwards: place a target, forward-project (independent of
    # ray_to_ground) to the pixel its FEET would occupy, then construct a Detection whose
    # BOTTOM-CENTER equals that pixel. The Projector must recover the target.
    cam = _nadir_cam()
    pose = _level_pose(40.0, -74.0, 100.0)
    target = (40.0 + 6.0 / _M_PER_DEG, -74.0 - 4.0 / (_M_PER_DEG * math.cos(math.radians(40.0))))
    feet_px = world_to_pixel(pose, cam, target_latlon=target, ground_elev=0.0)
    assert feet_px is not None

    # A Detection whose BOTTOM-CENTER ((x_min+x_max)/2, y_max) == feet_px. Give the box height
    # and width so its center is well ABOVE the feet - if the projector used the center instead
    # of the bottom, the recovered point would be wrong, and this test would catch it.
    half_w = 15.0
    box_h = 80.0
    x_min, x_max = feet_px[0] - half_w, feet_px[0] + half_w
    y_max = feet_px[1]
    y_min = feet_px[1] - box_h
    det = Detection(box_xyxy=(x_min, y_min, x_max, y_max), conf=0.9, cls="person")

    projector = Projector(camera=cam, ground_elev=0.0, ground_elev_datum="REL_TAKEOFF")
    gp = projector.project([det], pose)[0]
    assert gp.fusable
    assert _enu_error_m((gp.lat, gp.lon), target) < 0.01  # lands on the target's feet


def test_center_vs_bottom_would_be_wrong_guard():
    # Explicit guard: the projector must NOT use the box CENTER. Construct a tall box and show
    # the recovered point matches the BOTTOM-center projection, not the center projection.
    cam = _nadir_cam()
    pose = _level_pose(40.0, -74.0, 100.0)
    box = (940.0, 300.0, 980.0, 520.0)  # x in [940,980] -> center u=960; y_max=520
    det = Detection(box_xyxy=box, conf=0.9, cls="person")
    gp = Projector(camera=cam, ground_elev=0.0).project([det], pose)[0]

    bottom_center = ((box[0] + box[2]) / 2.0, box[3])  # (960, 520)
    box_center = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)  # (960, 410)
    from hades.locate.geometry import ray_to_ground

    expect_bottom = ray_to_ground(pose, cam, pixel=bottom_center, ground_elev=0.0)
    expect_center = ray_to_ground(pose, cam, pixel=box_center, ground_elev=0.0)
    # The projector's point matches the BOTTOM-center, and is distinguishable from the center.
    assert _enu_error_m((gp.lat, gp.lon), expect_bottom) < 1e-6
    assert _enu_error_m(expect_bottom, expect_center) > 1.0  # the two are meaningfully apart


def test_detection_through_fuse_lands_on_target():
    # The full seam: a real Detection per frame -> Projector ground points -> Fuse. The fused
    # coordinate must land on the target. Guards the box->pixel->ray->fuse chain end to end.
    cam = _nadir_cam()
    target = (40.0, -74.0)
    fuser = Fuser(error_model=SensorErrorModel())
    obs = []
    for i in range(12):
        # Drone tracks North, target stays put; build the feet pixel each frame.
        lat = target[0] - (40.0 - i * 6.0) / _M_PER_DEG
        pose = _level_pose(lat, target[1] + 50.0 / (_M_PER_DEG * math.cos(math.radians(40.0))), 80.0)
        feet_px = world_to_pixel(pose, cam, target_latlon=target, ground_elev=0.0)
        if feet_px is None:
            continue
        det = Detection(
            box_xyxy=(feet_px[0] - 10, feet_px[1] - 60, feet_px[0] + 10, feet_px[1]),
            conf=0.9, cls="person",
        )
        gp = Projector(camera=cam, ground_elev=0.0).project([det], pose)[0]
        assert gp.fusable
        obs.append(FuseObservation(pose=pose, camera=cam, pixel=((det.box_xyxy[0] + det.box_xyxy[2]) / 2, det.box_xyxy[3])))
    result = fuser.fuse(obs)
    assert _enu_error_m(result.coord, target) < 1.0
