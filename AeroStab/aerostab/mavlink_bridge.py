"""MAVLink bridge to ArduPilot — reconnect, altitude sources, vision+speed."""

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
        self._baro_alt_m: Optional[float] = None
        self._arm_baro_alt_m: Optional[float] = None
        self._rangefinder_m: Optional[float] = None
        self._fc_yaw_rad: Optional[float] = None
        self._armed = False
        self._was_armed = False
        self._last_hb = 0.0
        self._messages_sent = 0
        self._last_gps: Optional[GpsFix] = None
        self._hb_time = 0.0
        self._last_reconnect = 0.0
        self._connect_failures = 0

    @property
    def connected(self) -> bool:
        return self._conn is not None and (time.monotonic() - self._hb_time) < 5.0

    @property
    def altitude_m(self) -> float:
        return self._altitude_m

    @property
    def rangefinder_m(self) -> Optional[float]:
        return self._rangefinder_m

    @property
    def relative_baro_m(self) -> Optional[float]:
        if self._baro_alt_m is None or self._arm_baro_alt_m is None:
            return None
        return self._baro_alt_m - self._arm_baro_alt_m

    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def last_gps(self) -> Optional[GpsFix]:
        return self._last_gps

    @property
    def heartbeat_age_s(self) -> float:
        if self._hb_time <= 0:
            return 999.0
        return time.monotonic() - self._hb_time

    def connect(self) -> None:
        if not self.cfg.enabled:
            return
        from aerostab.serial_detect import resolve_mavlink_port

        port = resolve_mavlink_port(self.cfg.port)
        self.cfg.port = port
        logger.info("MAVLink %s", port)
        kwargs = {
            "source_system": self.cfg.system_id,
            "source_component": self.cfg.component_id,
        }
        if port.startswith(("tcp:", "tcpin:", "udp:", "udpin:")):
            self._conn = mavutil.mavlink_connection(port, **kwargs)
        else:
            self._conn = mavutil.mavlink_connection(port, baud=self.cfg.baud, **kwargs)
        self._conn.wait_heartbeat(timeout=10)
        self._hb_time = time.monotonic()
        self._connect_failures = 0
        logger.info("FC heartbeat OK (sys=%s)", self._conn.target_system)

    def ensure_connected(self) -> bool:
        """Reconnect with backoff if link is down."""
        if not self.cfg.enabled:
            return False
        if self.connected:
            return True
        now = time.monotonic()
        backoff = min(30.0, 2.0 ** min(self._connect_failures, 4))
        if now - self._last_reconnect < backoff:
            return False
        self._last_reconnect = now
        try:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
            self.connect()
            return True
        except Exception as exc:
            self._connect_failures += 1
            logger.warning("MAVLink reconnect failed (%s): %s", self._connect_failures, exc)
            return False

    def poll(self) -> None:
        if self._conn is None:
            self.ensure_connected()
            return
        while True:
            try:
                msg = self._conn.recv_match(blocking=False)
            except Exception:
                self._conn = None
                break
            if msg is None:
                break
            mtype = msg.get_type()
            if mtype == "HEARTBEAT" and msg.get_srcComponent() != self.cfg.component_id:
                self._hb_time = time.monotonic()
                base_mode = int(msg.base_mode)
                self._armed = bool(base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                if self._armed and not self._was_armed:
                    if self._baro_alt_m is not None:
                        self._arm_baro_alt_m = self._baro_alt_m
                    elif self._altitude_m:
                        self._arm_baro_alt_m = self._altitude_m
                self._was_armed = self._armed
            elif mtype == "ATTITUDE":
                self._fc_yaw_rad = float(msg.yaw)
            elif mtype == "GLOBAL_POSITION_INT":
                # relative_alt is AGL when home set — preferred over AMSL
                rel = float(msg.relative_alt) / 1000.0
                if -5.0 < rel < 500.0:
                    self._altitude_m = rel
            elif mtype == "VFR_HUD":
                # Keep as baro altitude reference only (often AMSL) — do NOT overwrite AGL
                self._baro_alt_m = float(msg.alt)
            elif mtype == "DISTANCE_SENSOR":
                # Prefer downward-facing rangefinder (orientation 25 / MAV_SENSOR_ROTATION_PITCH_270)
                orient = int(getattr(msg, "orientation", 25))
                dist_cm = float(getattr(msg, "current_distance", 0))
                if orient in (25, 0) and dist_cm > 0:
                    self._rangefinder_m = dist_cm / 100.0
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
        if self._conn is not None and now - self._last_hb > 1.0:
            try:
                self._conn.mav.heartbeat_send(
                    mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
                    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                    0,
                    0,
                    0,
                )
                self._last_hb = now
            except Exception:
                self._conn = None

    def fc_yaw_rad(self) -> Optional[float]:
        return self._fc_yaw_rad

    def send_odometry(self, state: OdometryState, altitude_m: float, nav_valid: bool) -> bool:
        if self._conn is None or not nav_valid:
            return False
        use_alt = altitude_m if altitude_m > 0.1 else self._altitude_m
        ts_us = int(time.time() * 1e6)
        # Prefer FC yaw for NED transform (visual yaw is noisy for heading)
        yaw = self._fc_yaw_rad if self._fc_yaw_rad is not None else state.yaw_rad
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        # Body: +x right, +y forward (camera looking down) → NED
        x_n = state.y_m * cos_y - state.x_m * sin_y
        y_e = state.y_m * sin_y + state.x_m * cos_y
        vn = state.vy_m_s * cos_y - state.vx_m_s * sin_y
        ve = state.vy_m_s * sin_y + state.vx_m_s * cos_y

        if self.cfg.send_vision_position:
            self._conn.mav.vision_position_estimate_send(
                ts_us, x_n, y_e, -use_alt, 0.0, 0.0, yaw
            )

        # Also send velocity for EK3_SRC1_VELXY=6 (ExternalNav)
        try:
            self._conn.mav.vision_speed_estimate_send(ts_us, vn, ve, 0.0)
        except Exception:
            pass

        self._messages_sent += 1
        return True

    def send_status(self, text: str, severity: int = 6) -> None:
        """MAV_SEVERITY: 4=WARNING, 6=INFO."""
        if self._conn is None:
            return
        try:
            payload = text.encode("utf-8")[:50]
            self._conn.mav.statustext_send(severity, payload)
        except Exception:
            pass

    def _command_long(self, command: int, *params: float, timeout_s: float = 3.0) -> tuple[bool, str]:
        if self._conn is None:
            return False, "MAVLink not connected"
        if not self.connected:
            return False, "FC heartbeat missing"
        p = list(params) + [0.0] * (7 - len(params))
        try:
            self._conn.mav.command_long_send(
                self._conn.target_system,
                self._conn.target_component,
                command,
                0,
                p[0],
                p[1],
                p[2],
                p[3],
                p[4],
                p[5],
                p[6],
            )
            ack = self._conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=timeout_s)
            if ack is None:
                return True, "command sent (no ACK)"
            result = int(ack.result)
            if result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                return True, "accepted"
            if result == mavutil.mavlink.MAV_RESULT_IN_PROGRESS:
                return True, "in progress"
            return False, f"FC rejected (result={result})"
        except Exception as exc:
            logger.warning("MAVLink command %s failed: %s", command, exc)
            return False, str(exc)

    def arm(self, force: bool = False) -> tuple[bool, str]:
        """Arm FC via MAV_CMD_COMPONENT_ARM_DISARM."""
        if not self.ensure_connected():
            return False, "MAVLink not connected"
        param2 = 21196.0 if force else 0.0  # magic force arm (ArduPilot)
        return self._command_long(
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            1.0,
            param2,
        )

    def disarm(self) -> tuple[bool, str]:
        if not self.ensure_connected():
            return False, "MAVLink not connected"
        return self._command_long(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0.0)

    def calibrate_level(self) -> tuple[bool, str]:
        """Board level calibration (drone on flat surface, disarmed)."""
        if not self.ensure_connected():
            return False, "MAVLink not connected"
        if self._armed:
            return False, "disarm before calibration"
        # param5=2 — board level calibration on ArduPilot
        return self._command_long(
            mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION,
            0.0,
            0.0,
            0.0,
            0.0,
            2.0,
            timeout_s=8.0,
        )

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
