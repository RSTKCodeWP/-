"""MAVLink bridge to ArduPilot (ExternalNav / vision messages)."""

from __future__ import annotations

import logging
import math
import time
from typing import Optional

from pymavlink import mavutil

from aerostab.config import MavlinkConfig
from aerostab.estimator import OdometryState

logger = logging.getLogger(__name__)

EARTH_RADIUS_M = 6378137.0


class MavlinkBridge:
    def __init__(self, cfg: MavlinkConfig):
        self.cfg = cfg
        self._conn: Optional[mavutil.mavfile] = None
        self._altitude_m: float = 2.0
        self._fc_yaw_rad: Optional[float] = None
        self._last_hb = 0.0
        self._messages_sent = 0

    @property
    def connected(self) -> bool:
        return self._conn is not None

    @property
    def altitude_m(self) -> float:
        return self._altitude_m

    def connect(self) -> None:
        if not self.cfg.enabled:
            logger.info("MAVLink disabled in config")
            return
        logger.info("Connecting MAVLink %s @ %d", self.cfg.port, self.cfg.baud)
        self._conn = mavutil.mavlink_connection(
            self.cfg.port,
            baud=self.cfg.baud,
            source_system=self.cfg.system_id,
            source_component=self.cfg.component_id,
        )
        self._conn.wait_heartbeat(timeout=10)
        logger.info(
            "Heartbeat from system %s component %s",
            self._conn.target_system,
            self._conn.target_component,
        )

    def poll(self) -> None:
        if self._conn is None:
            return
        while True:
            msg = self._conn.recv_match(blocking=False)
            if msg is None:
                break
            mtype = msg.get_type()
            if mtype == "ATTITUDE":
                self._fc_yaw_rad = float(msg.yaw)
            elif mtype == "GLOBAL_POSITION_INT":
                self._altitude_m = float(msg.relative_alt) / 1000.0
            elif mtype == "VFR_HUD":
                self._altitude_m = float(msg.alt)

        now = time.monotonic()
        if now - self._last_hb > 1.0 and self._conn is not None:
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

    @staticmethod
    def local_to_gps(
        x_m: float, y_m: float, alt_agl_m: float, home_lat: float, home_lon: float, home_alt_m: float
    ) -> tuple[float, float, float]:
        lat_off = y_m / EARTH_RADIUS_M * (180.0 / math.pi)
        lon_off = x_m / (EARTH_RADIUS_M * math.cos(math.radians(home_lat))) * (180.0 / math.pi)
        return home_lat + lat_off, home_lon + lon_off, home_alt_m + alt_agl_m

    def send_odometry(self, state: OdometryState, altitude_m: float) -> None:
        if self._conn is None:
            return
        use_alt = altitude_m if altitude_m > 0.1 else self._altitude_m
        ts_us = int(time.time() * 1e6)

        if self.cfg.send_vision_position:
            # NED: x north, y east, z down — map camera x=right,y=forward with yaw
            yaw = state.yaw_rad
            cos_y = math.cos(yaw)
            sin_y = math.sin(yaw)
            vn = state.vy_m_s * cos_y - state.vx_m_s * sin_y
            ve = state.vy_m_s * sin_y + state.vx_m_s * cos_y
            x_n = state.y_m * cos_y - state.x_m * sin_y
            y_e = state.y_m * sin_y + state.x_m * cos_y

            self._conn.mav.vision_position_estimate_send(
                ts_us,
                x_n,
                y_e,
                -use_alt,
                0,
                0,
                yaw,
                [0.0] * 21,
                0,
            )

        if self.cfg.send_optical_flow:
            quality = int(min(255, max(0, state.quality * 255)))
            flow_x = int(max(-32768, min(32767, state.vx_m_s * 100)))
            flow_y = int(max(-32768, min(32767, state.vy_m_s * 100)))
            self._conn.mav.optical_flow_rad_send(
                ts_us,
                0,
                flow_x,
                flow_y,
                0.0,
                0.0,
                quality,
                use_alt,
                0.0,
                0,
                0,
            )

        self._messages_sent += 1

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
