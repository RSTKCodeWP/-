"""Body-frame LOS (line-of-sight) bearing and LOS-rate with ego-motion subtracted.

THIS IS THE CORE OF S2 — GET THE SIGNS RIGHT.

PHYSICAL IDENTITY (the whole point of S2)
------------------------------------------
Raw pixel motion of target centroid = TRUE target LOS motion + ego-rotation-induced motion

Rearranging:
    true_target_LOS_motion = raw_pixel_motion - ego_rotation_motion

The ego_rotation_motion is what ``egomotion.gyro_derotation`` predicts as
``EgoEstimate.shift_px``.

SIGN CHAIN (trace carefully)
------------------------------
Let:
    px_k = target pixel centroid at frame k  (image-x right, image-y down)
    ego_shift_k = EgoEstimate.shift_px at frame k = (-f·omega_y·dt, -f·omega_x·dt)

    This is the shift the SCENE appears to move in the image due to the camera
    rotating.  ego_shift_k is CUMULATIVE-incremental: it only represents the
    movement in the single interval [k-1, k].

WORLD-POSITION REPRESENTATION:
    Define "world pixel" W_k = px_k - SUM_{i=1}^{k} ego_shift_i
    This is the target's pixel coordinate in a frame fixed to the world (no ego).

    The true LOS-rate pixel velocity:
        v_true = (W_k - W_{k-1}) / dt
               = (px_k - SUM_ego_k - (px_{k-1} - SUM_ego_{k-1})) / dt
               = ((px_k - px_{k-1}) - ego_shift_k) / dt

    So:  v_true_x = (px_k - px_{k-1} - ego_dx_k) / dt
         v_true_y = (py_k - py_{k-1} - ego_dy_k) / dt

    This is NOT the same as diffing per-frame-subtracted positions
    (comp_px = px - ego_shift), because that gives:
        (px_k - ego_shift_k) - (px_{k-1} - ego_shift_{k-1})
        = (px_k - px_{k-1}) - (ego_shift_k - ego_shift_{k-1})  ← WRONG: diff of shifts

    The CORRECT approach is to diff the raw positions then subtract the ego shift:
        v_true_x = (px_k - px_{k-1}) / dt  -  ego_dx_k / dt

BEARING:
    The bearing is computed from the COMPENSATED position in the current frame.
    We maintain a running "world reference" pixel W_ref and compute:
        comp_px = px_k - cumulative_ego (maintained across frames)
    Then az, el = pixel_to_bearing(comp_px).

    For bearing: comp_px_k = px_k - cumulative_shift
    For rate: v_true = (raw_pixel_diff - ego_increment) / dt

CRITICAL NOTE ON SIGN OF el-RATE:
    If the target moves DOWN in the image (v_true_y > 0), the target is moving
    toward lower elevation (el is decreasing), so del/dt < 0.
    Formula: del/dt = -v_true_y / f correctly gives negative del/dt for downward motion.
    This is consistent with pixel_to_bearing(py) = atan2(-(py - cy), f).

OUTPUT CONTRACT (per frame)
----------------------------
LOSObservation:
    az_rad          — ego-compensated azimuth bearing (rad)
    el_rad          — ego-compensated elevation bearing (rad)
    az_rate_radps   — ego-corrected azimuth LOS-rate (rad/s), positive = target moving right
    el_rate_radps   — ego-corrected elevation LOS-rate (rad/s), positive = target moving up
    ego_quality     — EgoEstimate.quality [0, 1]
    ego_source      — 'gyro' | 'gyro+klt'
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .geometry import CameraIntrinsics, pixel_to_bearing
from .egomotion import EgoEstimate
from .derotate import world_pixel


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LOSObservation:
    """Per-frame ego-compensated LOS bearing and rate.

    Attributes
    ----------
    az_rad:
        Azimuth bearing in body frame (radians).  Positive = target right.
        Derived from ego-compensated centroid position.
    el_rad:
        Elevation bearing in body frame (radians).  Positive = target above boresight.
    az_rate_radps:
        Ego-corrected azimuth LOS-rate (rad/s).  Positive = target moving right
        in body frame.
    el_rate_radps:
        Ego-corrected elevation LOS-rate (rad/s).  Positive = target moving up.
    ego_quality:
        Ego estimate quality [0, 1] from EgoEstimate.
    ego_source:
        'gyro' or 'gyro+klt'.
    frame_id:
        Frame counter.
    t_capture_ns:
        CLOCK_MONOTONIC capture timestamp, nanoseconds.  None if unavailable.
    """

    az_rad: float
    el_rad: float
    az_rate_radps: float
    el_rate_radps: float
    ego_quality: float
    ego_source: Literal["gyro", "gyro+klt"]
    frame_id: int
    t_capture_ns: int | None = None


# ---------------------------------------------------------------------------
# LOS computer
# ---------------------------------------------------------------------------

class LOSComputer:
    """Stateful per-frame LOS bearing + rate computer with ego compensation.

    Ego-compensation algorithm
    --------------------------
    We maintain a running cumulative ego that accumulates both:
      (a) the translational shift from pitch/yaw (_cum_ego_x, _cum_ego_y)
      (b) the cumulative in-plane roll angle (_cum_roll_rad) from omega_z

    Per frame:
        1. Accumulate:  _cum_ego_x/y += ego.shift_px  (translation from pitch/yaw)
                        _cum_roll_rad += ego.roll_rad  (roll angle)
        2. World pixel: un-rotate THEN un-translate.
           The simulator applies rotation THEN translation:
               cam_px = cx + (dx_w * cos(theta) + dy_w * sin(theta)) + cum_trans_x
           Inverting: dx_w_rot = cam_px - cx - cum_trans_x
                      (dx_w, dy_w) = inv_rotate(dx_w_rot, dy_w_rot, cum_theta)
                      world_px = (cx + dx_w, cy + dy_w)
           For the world_px (no rotation needed for comparing frame to frame if
           we use the *rotated* world coords consistently), we use:
               world_px_x = (cam_px - cx - cum_trans_x) * cos(-theta) - (cam_py - cy - cum_trans_y) * sin(-theta) + cx
           This gives a coordinate in the un-rotated world frame.
        3. Bearing: az, el = pixel_to_bearing(world_px)
        4. Rate:    v_true = (world_px - prev_world_px) / dt
        5. Convert pixel velocity to angular rate.

    WHY TRACK ROLL SEPARATELY (not as incremental translation)?
    -----------------------------------------------------------
    Roll (omega_z) is an in-plane IMAGE ROTATION, not a translation.
    Accumulating incremental tangential shifts introduces errors that grow with
    the cumulative rotation angle (small-angle approximation breaks down over
    many frames).  Instead we track the cumulative roll angle and apply it as
    a full rotation to invert the sim's exact rotation.

    Usage
    -----
    ::

        computer = LOSComputer(intrinsics)
        for frame_data in stream:
            centroid_px = ...          # from S1 detect
            ego = gyro_derotation(...)  # from S2 egomotion
            los_obs = computer.update(centroid_px, ego, dt, frame_id)

    The first frame produces a LOS observation with zero LOS-rate (no previous
    world pixel to diff against).
    """

    def __init__(self, intrinsics: CameraIntrinsics) -> None:
        self._intrinsics = intrinsics
        # Cumulative translational ego shift from pitch/yaw (pixels)
        self._cum_ego_x: float = 0.0
        self._cum_ego_y: float = 0.0
        # Cumulative roll angle (radians) — body CCW rotation about boresight
        self._cum_roll_rad: float = 0.0
        # Previous WORLD pixel (centroid with all cumulative ego removed)
        self._prev_world_px: tuple[float, float] | None = None
        self._prev_frame_id: int | None = None

    def reset(self) -> None:
        """Reset state (e.g., after a track loss).

        After reset, the cumulative ego is zeroed.  The next call to update()
        establishes a new world-frame reference.
        """
        self._cum_ego_x = 0.0
        self._cum_ego_y = 0.0
        self._cum_roll_rad = 0.0
        self._prev_world_px = None
        self._prev_frame_id = None

    def update(
        self,
        centroid_px: tuple[float, float],
        ego: EgoEstimate,
        dt: float,
        frame_id: int,
        t_capture_ns: int | None = None,
    ) -> LOSObservation:
        """Compute one frame of ego-compensated LOS bearing and rate.

        Parameters
        ----------
        centroid_px:
            Raw observed target pixel centroid (x, y) from S1 detect.
        ego:
            Ego-motion estimate for this frame interval.
            ego.shift_px = (-f*omega_y*dt, -f*omega_x*dt) — translational shift
            from pitch/yaw.
            ego.roll_rad = omega_z * dt — in-plane rotation angle (positive = CCW
            body rotation about boresight = CW scene rotation in image).
        dt:
            Elapsed time since the previous frame (seconds).  Must be > 0.
        frame_id:
            Current frame index.
        t_capture_ns:
            Capture timestamp in nanoseconds (optional).

        Returns
        -------
        LOSObservation
            Ego-compensated bearing and LOS-rate.  LOS-rate is zero on the
            first call (no previous world pixel available).

        Roll handling (FIX 2026-06-17)
        --------------------------------
        Body roll omega_z causes an in-plane IMAGE ROTATION about the principal
        point — not a pure translation.  This is handled by tracking the
        cumulative roll angle (self._cum_roll_rad) and applying the INVERSE
        rotation to the camera pixel (after removing the translational ego) to
        recover the world-frame pixel.  This avoids the error accumulation that
        would result from approximating the rotation as incremental translations.
        """
        if dt <= 0.0:
            dt = 1e-3  # defensive: avoid division by zero; 1 ms fallback

        px, py = centroid_px
        ego_dx, ego_dy = ego.shift_px

        cx = self._intrinsics.cx
        cy = self._intrinsics.cy

        # STEP 1: Accumulate cumulative ego (translation from pitch/yaw + roll angle).
        # ego.shift_px = (-f*omega_y*dt, -f*omega_x*dt)  — translation from pitch/yaw.
        # ego.roll_rad = omega_z * dt                     — in-plane rotation angle.
        #
        # ROLL is tracked as an accumulated ANGLE (not as incremental translations).
        # Accumulating incremental tangential pixel shifts introduces second-order
        # errors that grow with total rotation angle.  We instead maintain the exact
        # cumulative angle and apply a full rotation inversion below.
        self._cum_ego_x += ego_dx
        self._cum_ego_y += ego_dy
        self._cum_roll_rad += ego.roll_rad

        # STEP 2: Compute the "world pixel" — the target position in the un-rotated,
        # un-translated world frame.
        #
        # The simulator (seeker_sim.py) generates target camera pixels as:
        #   cam_px = cx + (dx_w * cos(theta) + dy_w * sin(theta)) + cum_trans_x
        #   cam_py = cy + (-dx_w * sin(theta) + dy_w * cos(theta)) + cum_trans_y
        # where (dx_w, dy_w) is the world offset and theta = cumulative_roll_rad.
        #
        # Inverting to recover (dx_w, dy_w):
        #   dx_t_trans = (cam_px - cx) - cum_trans_x = dx_w*cos(theta) + dy_w*sin(theta)
        #   dy_t_trans = (cam_py - cy) - cum_trans_y = -dx_w*sin(theta)+dy_w*cos(theta)
        #   dx_w = dx_t_trans * cos(theta) - dy_t_trans * sin(theta)   [by inverse rot]
        #   dy_w = dx_t_trans * sin(theta) + dy_t_trans * cos(theta)
        # World pixel = (cx + dx_w, cy + dy_w).
        # Ego de-rotation -> world pixel. Extracted to derotate.world_pixel so the synthetic-event
        # motion channel (R6) reuses the exact same inversion; bit-identical to the prior inline math.
        world_px_x, world_px_y = world_pixel(
            px, py, self._cum_ego_x, self._cum_ego_y, self._cum_roll_rad, cx, cy)

        # STEP 3: Convert world pixel to body-frame bearing.
        # The world pixel is the target position as if the camera hadn't rotated.
        az, el = pixel_to_bearing(world_px_x, world_px_y, self._intrinsics)

        # STEP 4: Compute LOS-rate from successive world pixels.
        az_rate = 0.0
        el_rate = 0.0

        if self._prev_world_px is not None:
            prev_wx, prev_wy = self._prev_world_px
            # True pixel velocity in the world frame
            v_true_x = (world_px_x - prev_wx) / dt   # px/s, positive = right
            v_true_y = (world_px_y - prev_wy) / dt   # px/s, positive = down

            # Convert pixel velocity to angular rate using pinhole formula.
            # az  = atan2(dx_world, f)  where dx_world = world_px_x - cx
            # daz/dt = (f / (f² + dx_world²)) · d(dx_world)/dt
            #        = f * v_true_x / (f² + dx_world²)
            #
            # el  = atan2(-dy_world, f)  where dy_world = world_px_y - cy
            # del/dt = -(f / (f² + dy_world²)) · d(dy_world)/dt
            #        = -f * v_true_y / (f² + dy_world²)
            # The MINUS on el is critical: downward pixel motion → decreasing el.
            f = self._intrinsics.f_px
            dx_world = world_px_x - self._intrinsics.cx
            dy_world = world_px_y - self._intrinsics.cy

            az_rate = v_true_x * f / (f * f + dx_world * dx_world)
            el_rate = -v_true_y * f / (f * f + dy_world * dy_world)

        self._prev_world_px = (world_px_x, world_px_y)
        self._prev_frame_id = frame_id

        return LOSObservation(
            az_rad=az,
            el_rad=el,
            az_rate_radps=az_rate,
            el_rate_radps=el_rate,
            ego_quality=ego.quality,
            ego_source=ego.source,
            frame_id=frame_id,
            t_capture_ns=t_capture_ns,
        )
