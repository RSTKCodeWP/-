"""The ONE ray→ground recipe (DESIGN.md §3.4) — single source of truth (Task 3.4).

`ray_to_ground` is imported by BOTH the Projector (Task 3.5) and Fuse (Phase 4) and is
NEVER re-implemented — that discipline is what prevents the coordinate-convention
divergence the design fears. Every convention from DESIGN.md §3.1-§3.4 is explicit here:

  undistort(pixel) → K⁻¹·pixel               # optical-frame ray, +z into scene
    → R_world_body · R_body_cam · ray        # active rotate optical → ENU world
    → require ray·Up < 0, else REJECT        # no phantom ground pin behind the drone
    → intersect flat-earth plane at the operator ground elevation (AGL)
    → ENU offset → (lat, lon)                # WGS84, (lat, lon) degrees order

Frames (§3.1-§3.3): world = ENU (East, North, Up), +z up, flat-earth, origin at the
drone's ground-nadir for this frame. Body = FRD (x-forward, y-right, z-down). Attitude
(roll, pitch, yaw) degrees with +pitch nose-up, +roll right-wing-down, yaw clockwise from
true North. Composition is the active rotation of column vectors:
``v_world = R_world_body · R_body_cam · v_cam``.

`R_world_body` is the aerospace ZYX (yaw→pitch→roll) intrinsic Euler giving FRD→NED, then
the fixed NED→ENU axis adapter. **+pitch needs NO sign flip** — the adapter already maps
scipy's +pitch (nose forward-up in NED) to a positive ENU up-component (the named sign
trap). Degrees are converted to radians only inside this module, never across a boundary
(§3.1).
"""

from __future__ import annotations

import math

import numpy as np
from scipy.spatial.transform import Rotation

from hades.ingest.telemetry_source import Pose
from hades.locate.camera_model import CameraModel

_METERS_PER_DEG_LAT = 111320.0  # flat-earth small-angle scale (§3.1)

# Fixed NED→ENU axis adapter: NED=[N,E,D] → ENU=[E,N,U] with E=E_ned, N=N_ned, U=−D_ned.
# det = +1 (a proper axis swap+flip, not a reflection).
_P_NED_ENU = np.array(
    [
        [0.0, 1.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0],
    ]
)

# Datums HADES recognises. A subtraction is allowed ONLY between two IDENTICAL, non-UNKNOWN
# datums (DESIGN.md §3.1/§3.5). HAE and MSL are NOT mutually subtractable even though both
# are "absolute": they differ by the geoid undulation (~−25 to −35 m on hurricane coasts),
# and HADES has no geoid-normalization, so mixing them injects the very ~30 m AGL error the
# alt_datum tag exists to prevent. UNKNOWN never feeds a subtraction, even against itself —
# two UNKNOWN tags are by definition of possibly-different datums (the tag means "we could
# not determine it"). REL_TAKEOFF subtracts only against REL_TAKEOFF.
_KNOWN_DATUMS = frozenset({"HAE", "MSL", "REL_TAKEOFF", "UNKNOWN"})


def R_world_body(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    """Rotation mapping a BODY (FRD) vector to a WORLD (ENU) vector: ``v_enu = R · v_frd``.

    Aerospace ZYX (yaw, pitch, roll) intrinsic Euler (FRD→NED) composed with the fixed
    NED→ENU adapter. +pitch = nose-up requires no sign flip (the adapter handles it).
    """
    r_ned_body = Rotation.from_euler(
        "ZYX", [yaw_deg, pitch_deg, roll_deg], degrees=True
    ).as_matrix()
    return _P_NED_ENU @ r_ned_body


def _agl(pose: Pose, ground_elev: float, ground_elev_datum: str) -> float:
    """Height of the drone above the ground plane (AGL), refusing to mix vertical datums.

    H = drone_alt − ground_elev, valid ONLY when both carry the SAME, KNOWN, non-UNKNOWN
    datum. Refuses HAE↔MSL (geoid undulation, no normalization here), REL_TAKEOFF↔absolute,
    any UNKNOWN — even UNKNOWN↔UNKNOWN — and any UNRECOGNISED/empty tag (an `==`-equal but
    meaningless datum like "" or a typo is not a license to subtract). Subtracting across
    any of these silently injects a ~30 m offset (DESIGN.md §3.5).
    """
    if pose.alt is None:
        raise ValueError("ray_to_ground: pose.alt is None (no altitude to form AGL)")
    drone_datum = pose.alt_datum

    # Allowed iff identical AND a RECOGNISED, non-UNKNOWN datum. (HAE/MSL differ by the
    # geoid; UNKNOWN is unknowable; an unrecognised/empty tag is not a real datum.)
    subtractable = {d for d in _KNOWN_DATUMS if d != "UNKNOWN"}
    if drone_datum != ground_elev_datum or drone_datum not in subtractable:
        raise ValueError(
            f"ray_to_ground: refusing to subtract across vertical datums "
            f"(drone={drone_datum!r}, ground={ground_elev_datum!r}) — would inject a "
            f"geoid/takeoff offset (DESIGN.md §3.5); only identical, non-UNKNOWN datums "
            f"may be subtracted"
        )
    return pose.alt - ground_elev


def ray_to_ground(
    pose: Pose,
    camera: CameraModel,
    pixel: tuple[float, float],
    ground_elev: float,
    ground_elev_datum: str = "REL_TAKEOFF",
) -> tuple[float, float]:
    """Project one image pixel to a ground (lat, lon), WGS84 degrees (DESIGN.md §3.4).

    Args:
        pose: drone pose; needs a GPS fix (lat/lon) and full attitude (roll/pitch/yaw) —
            a position-only pose is refused rather than projected as level/north.
        camera: intrinsics + boresight (the fixed mount).
        pixel: ``(u_px, v_px)`` in original-frame pixels (top-left origin, +x right/+y
            down, §3.2).
        ground_elev: operator-set ground-plane elevation, in `ground_elev_datum`.
        ground_elev_datum: vertical datum of `ground_elev`; must be compatible with the
            pose's `alt_datum` (see `_agl`).

    Returns:
        ``(lat, lon)`` degrees, WGS84, (lat, lon) order.

    Raises:
        ValueError: no GPS fix; missing attitude; mixed/unknown vertical datums;
            non-positive AGL; or a ray at/above the horizon (the phantom-pin reject).
    """
    # Refuse rather than fabricate: no GPS origin, or a partial/None attitude.
    if pose.lat is None or pose.lon is None or not pose.gps_valid:
        raise ValueError("ray_to_ground: no GPS fix (lat/lon) — cannot set an ENU origin")
    if pose.roll is None or pose.pitch is None or pose.yaw is None:
        raise ValueError(
            "ray_to_ground: pose attitude is None — refusing to assume level/north"
        )

    # A None check is not enough — a NaN/inf lat/alt/attitude/ground_elev would flow through
    # `None`-only guards and out to a silent (nan, nan) pin (cos(nan)=nan, t=H/nan=nan). The
    # cardinal silently-wrong-coordinate sin; refuse non-finite pose/ground inputs too.
    finite_inputs = (
        pose.lat, pose.lon, pose.alt, pose.roll, pose.pitch, pose.yaw, ground_elev
    )
    if not all(math.isfinite(v) for v in finite_inputs):
        raise ValueError(
            "ray_to_ground: non-finite pose/ground input (lat/lon/alt/attitude/ground_elev)"
        )

    height = _agl(pose, ground_elev, ground_elev_datum)
    if height <= 0.0:
        raise ValueError(
            f"ray_to_ground: AGL must be positive (drone above ground), got {height:.2f} m"
        )

    # A non-finite pixel must not slip through: NaN fails `d_up >= 0` (so the horizon
    # reject below wouldn't fire) and would yield a silent (nan, nan) coordinate that
    # `fusable` then accepts (nan is not None) — the cardinal silently-wrong-pin sin.
    if not (math.isfinite(pixel[0]) and math.isfinite(pixel[1])):
        raise ValueError(f"ray_to_ground: non-finite pixel {pixel!r}")

    # Optical-frame ray → active-rotate optical → body → ENU world.
    ray_cam = camera.ray_cam(pixel[0], pixel[1])
    d = R_world_body(pose.roll, pose.pitch, pose.yaw) @ camera.R_body_cam @ ray_cam
    d_east, d_north, d_up = d[0], d[1], d[2]

    # Ray must point toward the ground (down). A ray at/above the horizon would produce a
    # phantom pin behind the drone (t≤0 or ∞) — REJECT (DESIGN.md §3.4). Strict `>=`.
    if d_up >= 0.0:
        raise ValueError(
            "ray_to_ground: REJECT — ray points at/above the horizon (d_up >= 0); "
            "no valid ground intersection"
        )

    # Drone at ENU (0,0,H); intersect the ground plane z=0: H + t·d_up = 0 → t = H/|d_up|.
    t = -height / d_up
    east, north = t * d_east, t * d_north

    lat = pose.lat + north / _METERS_PER_DEG_LAT
    lon = pose.lon + east / (_METERS_PER_DEG_LAT * np.cos(np.radians(pose.lat)))
    return lat, lon
