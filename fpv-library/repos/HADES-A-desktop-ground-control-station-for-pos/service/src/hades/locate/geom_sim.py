"""Geometric localization simulator (Task 4.2; research gate §6).

Generates calibrated synthetic ground truth for the meter-error metric and the coverage
validation: given a target lat/lon and an analytic flight path, it emits per frame a
ground-truth detection pixel (forward projection) plus a noisy pose (sensor errors injected
from a `SensorErrorModel`), so the downstream Fuse + Monte Carlo can be scored against a
known truth.

ANTI-CIRCULARITY (§4 Risk A) — the load-bearing architectural rule:

  `world_to_pixel` is the FORWARD-collinearity equation (world -> pixel). It MUST NOT call,
  import, or invert `geometry.ray_to_ground` (the inverse path). It shares ONLY the
  convention builders that are too sign-trap-loaded to re-derive safely:
  `geometry.R_world_body`, `CameraModel.K`, `CameraModel.R_body_cam`. Re-deriving the
  rotation here would just open a second home for a sign-flip bug.

The two paths are each pinned to their OWN hand-derived analytic fixtures (this module's
tests vs `test_geometry.py`); a shared rotation bug would have to satisfy both independent
anchors at once, which a sign error cannot. The zero-noise round-trip
(`world_to_pixel` then `ray_to_ground` recovers the target to < 1e-6 m) is a NECESSARY
sanity check, not the proof.

Ground truth is the INPUT `target_latlon` the sim was handed — never derived from any
projection. The forward map only produces the *pixel* a perfect detector would report.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterator

import numpy as np

from hades.ingest.telemetry_source import Pose
from hades.locate.camera_model import CameraModel
from hades.locate.error_model import SensorErrorModel
from hades.locate.geometry import R_world_body  # convention builder ONLY (NOT the solver)

_M_PER_DEG_LAT = 111320.0  # matches geometry.py's flat-earth scale (§3.1)


# --- ENU <-> geodetic offset (the INVERSE of geometry.py's ENU->latlon, written forward) ---
# geometry.py does:  lat = drone.lat + north/M ; lon = drone.lon + east/(M*cos(lat)).
# The forward direction (drone_latlon -> target_latlon => ENU offset in meters) is the
# algebraic inverse of those two lines. This is convention-sharing (the same flat-earth
# small-angle model and cos(lat) scaling), NOT solver-sharing.
def _enu_offset(drone_latlon: tuple[float, float], target_latlon: tuple[float, float]) -> np.ndarray:
    """ENU (east, north, up=0) meters from the drone's ground nadir to the target point."""
    dlat = target_latlon[0] - drone_latlon[0]
    dlon = target_latlon[1] - drone_latlon[1]
    north = dlat * _M_PER_DEG_LAT
    east = dlon * _M_PER_DEG_LAT * math.cos(math.radians(drone_latlon[0]))
    return np.array([east, north, 0.0])


def world_to_pixel(
    pose: Pose,
    camera: CameraModel,
    target_latlon: tuple[float, float],
    ground_elev: float,
) -> tuple[float, float] | None:
    """Forward-project a ground target to its image pixel (FORWARD collinearity).

    Returns ``(u_px, v_px)`` in original-frame pixels, or ``None`` when the target is
    behind the lens / outside the optical half-space (``r_cam.z <= 0``) — a "not visible"
    frame, never a phantom pixel. The math, written forward (NOT inverting ray_to_ground):

      p_enu = target_ENU - drone_ENU            # drone at (0,0,H) above its nadir
      r_cam = (R_world_body . R_body_cam)^T . p_enu   # world -> body -> optical (transpose)
      require r_cam.z > 0                        # in front of the lens
      u = fx * r_cam.x/r_cam.z + cx              # pinhole intrinsics, forward
      v = fy * r_cam.y/r_cam.z + cy
      then forward-distort (identity for the pinhole v1)
    """
    if pose.lat is None or pose.lon is None:
        raise ValueError("world_to_pixel: pose has no GPS fix")
    if pose.roll is None or pose.pitch is None or pose.yaw is None:
        raise ValueError("world_to_pixel: pose attitude is None — cannot project")
    if pose.alt is None:
        raise ValueError("world_to_pixel: pose.alt is None")

    height = pose.alt - ground_elev  # AGL; same-datum subtraction (sim controls both)
    # Drone sits at ENU (0, 0, H) above its own ground nadir; the target is on the plane.
    p_enu = _enu_offset((pose.lat, pose.lon), target_latlon)
    p_enu[2] = -height  # target is `height` below the drone (drone at +H, ground at 0)

    r_world_cam = R_world_body(pose.roll, pose.pitch, pose.yaw) @ camera.R_body_cam
    r_cam = r_world_cam.T @ p_enu  # world -> optical (active rotation transpose)

    if r_cam[2] <= 0.0:
        return None  # behind the lens / at-or-above the optical horizon: not visible

    u = camera.fx * (r_cam[0] / r_cam[2]) + camera.cx
    v = camera.fy * (r_cam[1] / r_cam[2]) + camera.cy
    u, v = _forward_distort(camera, u, v)
    return float(u), float(v)


def _forward_distort(camera: CameraModel, u: float, v: float) -> tuple[float, float]:
    # v1 fixtures are pinhole (no distortion) — identity. A calibrated O4 forward-distortion
    # model plugs in here later (the inverse of camera_model._undistort) without touching
    # any caller. Kept as a seam so the sim and the real lens model stay symmetric.
    if not camera.dist:
        return u, v
    raise NotImplementedError(
        "forward distortion not implemented for v1 (fixtures are pinhole)"
    )


# --- ground-truth frames + analytic flight paths ------------------------------------


@dataclass(frozen=True)
class GroundTruthFrame:
    """One frame of perfect ground truth: the true pose, the pixel a perfect detector sees,
    and the geometry (slant range, camera pitch from nadir, bearing to target)."""

    pose_true: Pose
    pixel_true: tuple[float, float]
    target_latlon: tuple[float, float]
    slant_range_m: float
    nadir_angle_deg: float  # camera optical-axis angle from straight-down
    target_bearing_deg: float  # compass bearing drone -> target (for aspect diversity)
    velocity_enu: tuple[float, float, float]  # (E, N, U) m/s — for the time-sync injection


@dataclass(frozen=True)
class SimFrame:
    """What the sim hands the localizer: a noisy pose + noisy pixel, plus the truth to
    score against. The localizer consumes `pose_meas`/`pixel_meas`; the meter-error report
    consumes `target_latlon`/`pose_true` as ground truth."""

    seq: int
    t: float
    pose_meas: Pose
    pose_true: Pose
    pixel_meas: tuple[float, float]
    pixel_true: tuple[float, float]
    target_latlon: tuple[float, float]
    slant_range_m: float
    nadir_angle_deg: float


def _geometry(
    camera: CameraModel,
    pose: Pose,
    target_latlon: tuple[float, float],
    ground_elev: float,
) -> tuple[float, float, float]:
    """(slant_range_m, nadir_angle_deg, target_bearing_deg) for one true pose + target."""
    p_enu = _enu_offset((pose.lat, pose.lon), target_latlon)
    height = pose.alt - ground_elev
    slant = math.hypot(math.hypot(p_enu[0], p_enu[1]), height)
    # Camera pitch from nadir: angle of the optical axis (+z into scene) from ENU-down.
    optical_axis = np.array([0.0, 0.0, 1.0])
    axis_world = R_world_body(pose.roll, pose.pitch, pose.yaw) @ camera.R_body_cam @ optical_axis
    down = np.array([0.0, 0.0, -1.0])
    nadir = math.degrees(math.acos(float(np.clip(np.dot(axis_world, down), -1.0, 1.0))))
    bearing = math.degrees(math.atan2(p_enu[0], p_enu[1])) % 360.0  # from North, clockwise
    return slant, nadir, bearing


def _velocity_enu(poses: list[Pose], i: int) -> tuple[float, float, float]:
    """Drone velocity (E, N, U) m/s at frame i, by central/one-sided finite difference.

    Feeds the time-sync injection: a pose lagged by Delta seconds is displaced by
    velocity * Delta along-track. With a single frame (no neighbor) velocity is zero.
    """
    if len(poses) < 2:
        return (0.0, 0.0, 0.0)
    j = i + 1 if i == 0 else i
    k = i if i == 0 else i - 1
    a, b = poses[k], poses[j]
    dt = b.t - a.t
    if dt <= 0:
        return (0.0, 0.0, 0.0)
    east = (
        (b.lon - a.lon) * _M_PER_DEG_LAT * math.cos(math.radians(a.lat)) / dt
    )
    north = (b.lat - a.lat) * _M_PER_DEG_LAT / dt
    up = ((b.alt or 0.0) - (a.alt or 0.0)) / dt
    return (east, north, up)


class FlightPath:
    """Base for analytic, closed-form flight paths. Each yields full-attitude ground-truth
    frames; geometry (slant/pitch/bearing) is computed EXACTLY, never estimated."""

    def __init__(self, camera: CameraModel | None = None, ground_elev: float = 0.0) -> None:
        # A default nadir camera lets paths compute pixels/geometry standalone in tests.
        self._camera = camera or CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=540.0)
        self._ground_elev = ground_elev

    def poses(self) -> Iterator[Pose]:
        raise NotImplementedError

    def target(self) -> tuple[float, float]:
        raise NotImplementedError

    def frames(self) -> Iterator[GroundTruthFrame]:
        tgt = self.target()
        # Materialize the poses so velocity (for the time-sync injection) can be computed by
        # finite difference of consecutive positions. Paths are short (tens of frames).
        poses = list(self.poses())
        for i, pose in enumerate(poses):
            px = world_to_pixel(pose, self._camera, tgt, self._ground_elev)
            if px is None:
                continue  # target not in view this frame (still a valid "no detection")
            slant, nadir, bearing = _geometry(self._camera, pose, tgt, self._ground_elev)
            yield GroundTruthFrame(
                pose_true=pose,
                pixel_true=px,
                target_latlon=tgt,
                slant_range_m=slant,
                nadir_angle_deg=nadir,
                target_bearing_deg=bearing,
                velocity_enu=_velocity_enu(poses, i),
            )


def _offset_latlon(
    origin: tuple[float, float], east_m: float, north_m: float
) -> tuple[float, float]:
    lat = origin[0] + north_m / _M_PER_DEG_LAT
    lon = origin[1] + east_m / (_M_PER_DEG_LAT * math.cos(math.radians(origin[0])))
    return lat, lon


class StraightPass(FlightPath):
    """A single straight, level pass at constant altitude that flies OVER the target.

    The realistic single-leg SAR geometry and the §2 worst case: aspect diversity is
    near-zero (the bearing to the target stays one-sided), so the heading bias is fully
    unobservable. Populates a spread of slant ranges as the target moves through the frame.
    Heading (yaw) is the course-over-ground of the pass (due North here).
    """

    def __init__(
        self,
        target_latlon: tuple[float, float],
        agl_m: float,
        speed_mps: float,
        n_frames: int,
        fps: float = 10.0,
        lateral_offset_m: float = 0.0,
        camera: CameraModel | None = None,
        ground_elev: float = 0.0,
    ) -> None:
        super().__init__(camera, ground_elev)
        self._target = target_latlon
        self._agl = agl_m
        self._speed = speed_mps
        self._n = n_frames
        self._fps = fps
        self._lateral = lateral_offset_m

    def target(self) -> tuple[float, float]:
        return self._target

    def poses(self) -> Iterator[Pose]:
        dt = 1.0 / self._fps
        span = self._speed * dt * (self._n - 1)
        for i in range(self._n):
            # Fly South -> North, passing over (or beside) the target at the midpoint.
            north = -span / 2.0 + self._speed * dt * i
            lat, lon = _offset_latlon(self._target, east_m=self._lateral, north_m=north)
            yield Pose(
                t=i * dt, lat=lat, lon=lon, alt=self._agl + self._ground_elev,
                alt_datum="REL_TAKEOFF", roll=0.0, pitch=0.0, yaw=0.0, seq=i,
            )


class OrbitPath(FlightPath):
    """A circular orbit of the target at constant radius + altitude, looking inward/down.

    Sweeps a controlled, near-constant slant range and camera pitch (`atan2(radius, agl)`),
    and crucially provides ASPECT DIVERSITY — the target is observed from a full spread of
    azimuths. This is the geometry that lets the §2 heading-bias floor RELAX; it is
    load-bearing for the honesty story, not scope creep. Yaw points toward the target
    (the drone looks inward) so the camera sees the target near frame center.
    """

    def __init__(
        self,
        target_latlon: tuple[float, float],
        agl_m: float,
        radius_m: float,
        n_frames: int,
        fps: float = 10.0,
        camera: CameraModel | None = None,
        ground_elev: float = 0.0,
    ) -> None:
        # The orbit needs a camera tilted toward the target; use a forward-ish nadir mount
        # but set yaw so the inward look-direction lands the target in view. A pure nadir
        # mount already sees a ground annulus, so nadir mount + look-toward-target yaw works.
        super().__init__(camera, ground_elev)
        self._target = target_latlon
        self._agl = agl_m
        self._radius = radius_m
        self._n = n_frames
        self._fps = fps

    def target(self) -> tuple[float, float]:
        return self._target

    def poses(self) -> Iterator[Pose]:
        dt = 1.0 / self._fps
        # Aim the nadir-mounted camera at the target by PITCHING the airframe. Yaw already
        # points body-forward at the target; a nose-up (+pitch, aerospace) rotation tilts the
        # straight-down optical axis toward body-forward, i.e. onto the target. The required
        # magnitude is the standoff look-down angle atan2(radius, agl), and the camera's
        # resulting pitch-from-nadir equals it. (Verified: this lands the target at the
        # principal point; nose-down tilts the axis the WRONG way, behind the lens.) This is
        # the realistic fixed-mount aim — the O4 has no gimbal, the airframe points it.
        aim_pitch = math.degrees(math.atan2(self._radius, self._agl))
        for i in range(self._n):
            theta = 2.0 * math.pi * i / self._n
            east = self._radius * math.cos(theta)
            north = self._radius * math.sin(theta)
            lat, lon = _offset_latlon(self._target, east_m=east, north_m=north)
            # Yaw = compass bearing FROM the drone TO the target (look inward).
            yaw = math.degrees(math.atan2(-east, -north)) % 360.0
            yield Pose(
                t=i * dt, lat=lat, lon=lon, alt=self._agl + self._ground_elev,
                alt_datum="REL_TAKEOFF", roll=0.0, pitch=aim_pitch, yaw=yaw, seq=i,
            )


# --- the sim: inject sensor noise onto each ground-truth frame ----------------------


class GeomSim:
    """Drives a flight path through a sensor-error model to produce `SimFrame`s.

    The error model is the SHARED SCHEMA (the sim's own instance). The sim turns its sigmas
    into per-frame perturbations; the heading BIAS is drawn ONCE per run (common-mode across
    the pass — drawing it i.i.d. per frame would fake an error reduction fusion cannot
    achieve, §2). GPS/attitude jitter is per frame.
    """

    def __init__(self, camera: CameraModel, ground_elev: float = 0.0) -> None:
        self.camera = camera
        self.ground_elev = ground_elev

    def run(
        self, path: FlightPath, error_model: SensorErrorModel, seed: int
    ) -> list[SimFrame]:
        rng = np.random.default_rng(seed)
        m = error_model
        # Bind the path's camera/ground_elev to ours so geometry + pixels agree.
        path._camera = self.camera
        path._ground_elev = self.ground_elev

        # Common-mode heading bias: ONE draw for the whole pass (§2). Sign optionally random.
        bias_sign = rng.choice([-1.0, 1.0]) if m.crab_sign_random else 1.0
        heading_bias_deg = bias_sign * (
            m.crab_angle_deg + rng.normal(0.0, m.heading_bias_sigma_deg)
        )

        out: list[SimFrame] = []
        for gt in path.frames():
            pose_meas = self._perturb_pose(
                gt.pose_true, m, heading_bias_deg, gt.velocity_enu, rng
            )
            pixel_meas = self._perturb_pixel(gt.pixel_true, m, rng)
            out.append(
                SimFrame(
                    seq=gt.pose_true.seq if gt.pose_true.seq is not None else 0,
                    t=gt.pose_true.t,
                    pose_meas=pose_meas,
                    pose_true=gt.pose_true,
                    pixel_meas=pixel_meas,
                    pixel_true=gt.pixel_true,
                    target_latlon=gt.target_latlon,
                    slant_range_m=gt.slant_range_m,
                    nadir_angle_deg=gt.nadir_angle_deg,
                )
            )
        return out

    def _perturb_pose(
        self,
        pose: Pose,
        m: SensorErrorModel,
        heading_bias_deg: float,
        velocity_enu: tuple[float, float, float],
        rng: np.random.Generator,
    ) -> Pose:
        # GPS horizontal noise in ENU meters -> back to degrees (per-frame, independent).
        if m.gps_dist == "studentt" and m.gps_horiz_sigma_m > 0:
            scale = m.gps_horiz_sigma_m * math.sqrt((m.gps_studentt_dof - 2.0) / m.gps_studentt_dof)
            de = float(rng.standard_t(m.gps_studentt_dof) * scale)
            dn = float(rng.standard_t(m.gps_studentt_dof) * scale)
        else:
            de = float(rng.normal(0.0, m.gps_horiz_sigma_m))
            dn = float(rng.normal(0.0, m.gps_horiz_sigma_m))
        dalt = float(rng.normal(0.0, m.gps_vert_sigma_m))

        # Time-sync offset (§5, the named dominant failure): the reported pose lags the video
        # frame by t_sync_offset_ms (constant) + per-frame jitter, so its POSITION is the true
        # position displaced DOWN-TRACK by velocity * Delta. This is a SYSTEMATIC, common-
        # direction bias the MC (which assumes zero offset) cannot model — exactly what makes
        # the coverage test non-tautological. Jitter is zero-mean per frame.
        delta_s = m.t_sync_offset_ms / 1000.0 + float(rng.normal(0.0, m.t_sync_jitter_ms / 1000.0))
        ve, vn, vu = velocity_enu
        de += ve * delta_s
        dn += vn * delta_s
        dalt += vu * delta_s

        lat = pose.lat + dn / _M_PER_DEG_LAT
        lon = pose.lon + de / (_M_PER_DEG_LAT * math.cos(math.radians(pose.lat)))

        droll = float(rng.normal(0.0, m.roll_sigma_deg))
        dpitch = float(rng.normal(0.0, m.pitch_sigma_deg))
        # Heading = true yaw + common-mode bias (whole pass) + per-frame zero-mean jitter.
        dyaw = heading_bias_deg + float(rng.normal(0.0, m.yaw_jitter_sigma_deg))

        return Pose(
            t=pose.t, lat=lat, lon=lon, alt=pose.alt + dalt, alt_datum=pose.alt_datum,
            roll=pose.roll + droll, pitch=pose.pitch + dpitch, yaw=pose.yaw + dyaw,
            seq=pose.seq,
        )

    def _perturb_pixel(
        self, pixel: tuple[float, float], m: SensorErrorModel, rng: np.random.Generator
    ) -> tuple[float, float]:
        du = float(rng.normal(0.0, m.pixel_sigma_px))
        dv = float(rng.normal(m.foot_bias_px, m.pixel_sigma_px))
        return pixel[0] + du, pixel[1] + dv
