"""seeker_core tracker stage — a gimbaled tracker: bearing from the gimbal + LOS rate from the head gyro.

The cheap-genius insight wired in: on a stabilized head, the inertial LOS rate is the head gyro
(GimbalState.los_rate), so the tracker doesn't need strapdown de-rotation. Bearing = the gimbal pointing
angles + the residual centroid offset. Range/t_go stay None — a bench (or a passive seeker) has no
range observable, and the contract forbids fabricating one.
"""
from __future__ import annotations

import math
from typing import Optional

from seeker_core.contracts import Blob, Detections, GimbalState, ImuSample, Track


def _dominant_blob(detections: Detections) -> Optional[Blob]:
    if not detections.blobs:
        return None
    return max(detections.blobs, key=lambda b: (b.area_px, b.snr))


class GimbaledTracker:
    """Track from the gimbal state + detections. LOS rate = head gyro; range = None (unobservable)."""

    def __init__(self, f_px: float = 730.0, img_w: int = 640, img_h: int = 512,
                 lock_min_snr: float = 4.0) -> None:
        self.f_px, self.img_w, self.img_h, self.lock_min_snr = f_px, img_w, img_h, lock_min_snr

    def update(self, detections: Detections, imu: Optional[ImuSample],
               gimbal: Optional[GimbalState], dt: float) -> Track:
        prov = detections.provenance
        blob = _dominant_blob(detections)
        if blob is None or gimbal is None:
            return Track(locked=False, az_rad=0.0, el_rad=0.0, los_rate_az=0.0, los_rate_el=0.0,
                         range_m=None, t_go_s=None, quality=0.0, provenance=prov)
        ex = blob.centroid_px[0] - self.img_w / 2.0
        ey = blob.centroid_px[1] - self.img_h / 2.0
        az = gimbal.pan_setpoint_rad + math.atan2(ex, self.f_px)      # gimbal pointing + residual offset
        el = gimbal.tilt_setpoint_rad - math.atan2(ey, self.f_px)
        quality = min(1.0, blob.snr / 20.0)
        locked = bool(gimbal.tracking and blob.snr >= self.lock_min_snr)
        return Track(locked=locked, az_rad=az, el_rad=el,
                     los_rate_az=gimbal.los_rate_yaw, los_rate_el=gimbal.los_rate_pitch,
                     range_m=None, t_go_s=None, quality=quality, provenance=prov)
