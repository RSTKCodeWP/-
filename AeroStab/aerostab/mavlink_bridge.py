"""MAVLink bridge to ArduPilot."""

from __future__ import annotations

import logging
import math
import time
from typing import Optional

from pymavlink import mavutil

from aerostab.config import MavlinkConfig
from aerostab.estimator import OdometryState
from aerostab.gps_fusion import GpsFix

logger = logging.getLogger(__name__)


class MavlinkBridge:
    def __init__(self, cfg: MavlinkConfig):
        self.cfg = cfg
        self._conn: Optional[mavutil.mavfile] = None
        self._altitude_m: float = 2.0
        self._fc_yaw_rad: Optional[float] = None
        self._armed = False
        self._last_hb = 0.0
        self._messages_sent = 0
        self._last_gps: Optional[GpsFix] = None
        self._hb_time = 0.0

    @property
    def connected(self) -> bool:
        return self._conn is not None and (time.monotonic() - self._hb_time) < 5.0

    @property
    def altitude_m(self) -> float:
        return self._altitude_m

    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def last_gps(self) -> Optional[GpsFix]:
        return self._last_gps

    def connect(self) -> None:
        if not self.cfg.enabled:
            return
        logger.info("MAVLink %s @ %d", self.cfg.port, self.cfg.baud)
        self._conn = mavutil.mavlink_connection(
            self.cfg.port,
            baud=self.cfg.baud,
            source_system=self.cfg.system_id,
            source_component=self.cfg.component_id,
        )
        self._conn.wait_heartbeat(timeout=10)
        self._hb_time = time.monotonic()
        logger.info("FC heartbeat OK (sys=%s)", self._conn.target_system)

    def poll(self) -> None:
        if self._conn is None:
            return
        while True:
            msg = self._conn.recv_match(blocking=False)
            if msg is None:
                break
            mtype = msg.get_type()
            if mtype == "HEARTBEAT" and msg.get_srcComponent() != self.cfg.component_id:
                self._hb_time = time.monotonic()
                base_mode = int(msg.base_mode)
                self._armed = bool(base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            elif mtype == "ATTITUDE":
                self._fc_yaw_rad = float(msg.yaw)
            elif mtype == "GLOBAL_POSITION_INT":
                self._altitude_m = float(msg.relative_alt) / 1000.0
            elif mtype == "VFR_HUD":
                self._altitude_m = float(msg.alt)
            elif mtype == "GPS_RAW_INT":
                self._last_gps = GpsFix(
                    lat=msg.lat / 1e7,
                    lon=msg.lon / 1e7,
                    alt_m=msg.alt / 1000.0,
                    fix_type=int(msg.fix_type),
                    satellites=int(msg.satellites_visible),
                    time_monotonic=time.monotonic(),
                )

        now = time.monotonic()
        if now - self._last_hb > 1.0:
            self._conn.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                0,
                0,
                0,
            )
            self._last_hb = now

    def fc_yaw_rad(self) -> Optional[float]:
        return self._fc_yaw_rad

    def send_odometry(self, state: OdometryState, altitude_m: float, nav_valid: bool) -> bool:
        if self._conn is None or not nav_valid:
            return False
        use_alt = altitude_m if altitude_m > 0.1 else self._altitude_m
        ts_us = int(time.time() * 1e6)
        yaw = state.yaw_rad
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        x_n = state.y_m * cos_y - state.x_m * sin_y
        y_e = state.y_m * sin_y + state.x_m * cos_y
        vn = state.vy_m_s * cos_y - state.vx_m_s * sin_y
        ve = state.vy_m_s * sin_y + state.vx_m_s * cos_y

        if self.cfg.send_vision_position:
            self._conn.mav.vision_position_estimate_send(
                ts_us, x_n, y_e, -use_alt, 0, 0, yaw, [0.0] * 21, 0
            )

        if self.cfg.send_optical_flow:
            q = int(min(255, max(0, state.quality * 255)))
            self._conn.mav.optical_flow_rad_send(
                ts_us, 0, int(vn * 100), int(ve * 100), 0.0, 0.0, q, use_alt, 0.0, 0, 0
            )

        self._messages_sent += 1
        return True

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
