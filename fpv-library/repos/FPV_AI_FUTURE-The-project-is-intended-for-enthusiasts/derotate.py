"""Ego-motion de-rotation primitive (extracted from los.py for reuse).

Given a raw camera pixel and the CUMULATIVE ego (translational shift from pitch/yaw + the
cumulative roll angle), recover the target's pixel in the un-rotated, un-translated WORLD
frame. The simulator forms the image as rotate-by-cum_roll THEN translate-by-cum_ego; this
inverts both. Kept as a pure function so the LOS path (los.py) and the future synthetic-event
motion channel (R6) share ONE verified de-rotation -- bit-identical to the prior inline math.
"""

from __future__ import annotations

import math


def world_pixel(
    px: float, py: float,
    cum_ego_x: float, cum_ego_y: float, cum_roll_rad: float,
    cx: float, cy: float,
) -> tuple[float, float]:
    """Map camera pixel ``(px, py)`` to its world-frame pixel, removing cumulative ego.

    Steps (identical to the formula previously inlined in ``LOSComputer.update``):
        dx_t = (px - cx) - cum_ego_x ;  dy_t = (py - cy) - cum_ego_y   (remove pitch/yaw shift)
        dx_w = dx_t*cos - dy_t*sin   ;  dy_w = dx_t*sin + dy_t*cos      (invert the roll rotation)
        world = (cx + dx_w, cy + dy_w)
    """
    c_th = math.cos(cum_roll_rad)
    s_th = math.sin(cum_roll_rad)
    dx_t = (px - cx) - cum_ego_x
    dy_t = (py - cy) - cum_ego_y
    dx_w = dx_t * c_th - dy_t * s_th
    dy_w = dx_t * s_th + dy_t * c_th
    return cx + dx_w, cy + dy_w
