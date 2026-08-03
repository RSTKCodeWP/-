"""Lightweight MAVLink flight-controller simulator for AeroStab integration tests.

Listens on TCP (``tcpin``) like ArduPilot SITL serial endpoint and emits the
messages AeroStab expects: HEARTBEAT, ATTITUDE, VFR_HUD, GPS_RAW_INT.
Records inbound VISION_POSITION_ESTIMATE / OPTICAL_FLOW_RAD for assertions.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

from pymavlink import mavutil

logger = logging.getLogger(__name__)


@dataclass
class MockFcStats:
    vision_count: int = 0
    optical_flow_count: int = 0
    heartbeat_count: int = 0
    client_connected: bool = False
    last_vision: Optional[tuple] = None  # (x, y, z, yaw)


@dataclass
class MockFlightController:
  """Minimal ArduPilot-like MAVLink peer for hardware-in-the-loop simulation."""

  port: int = 5760
  bind_host: str = "0.0.0.0"
  altitude_m: float = 2.0
  yaw_rad: float = 0.0
  lat: float = 50.0
  lon: float = 30.0
  gps_fix_type: int = 3
  gps_sats: int = 12
  armed: bool = False
  system_id: int = 1
  component_id: int = 1
  rate_hz: float = 50.0

  _thread: Optional[threading.Thread] = field(default=None, init=False, repr=False)
  _stop: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
  _conn: Optional[mavutil.mavfile] = field(default=None, init=False, repr=False)
  _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
  stats: MockFcStats = field(default_factory=MockFcStats, init=False)

  @property
  def endpoint(self) -> str:
    return f"tcp:127.0.0.1:{self.port}"

  @property
  def listen_uri(self) -> str:
    return f"tcpin:{self.bind_host}:{self.port}"

  def start(self) -> None:
    if self._thread and self._thread.is_alive():
      return
    self._stop.clear()
    self._thread = threading.Thread(target=self._run, name="mock-fc", daemon=True)
    self._thread.start()

  def wait_client(self, timeout_s: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
      if self.stats.client_connected:
        return
      time.sleep(0.05)
    raise TimeoutError(f"Mock FC: no client on {self.listen_uri} within {timeout_s}s")

  def stop(self) -> None:
    self._stop.set()
    if self._thread:
      self._thread.join(timeout=3.0)
      self._thread = None
    if self._conn is not None:
      try:
        self._conn.close()
      except Exception:
        pass
      self._conn = None

  def _wait_client(self) -> bool:
    deadline = time.monotonic() + 30.0
    while not self._stop.is_set() and time.monotonic() < deadline:
      # recv() on tcpin accepts the TCP client without requiring MAVLink data first
      self._conn.recv_match(blocking=False)
      if getattr(self._conn, "port", None) is not None:
        return True
      time.sleep(0.01)
    return False

  def _run(self) -> None:
    logger.info("Mock FC listening %s", self.listen_uri)
    self._conn = mavutil.mavlink_connection(
      self.listen_uri,
      source_system=self.system_id,
      source_component=self.component_id,
    )
    if not self._wait_client():
      logger.warning("Mock FC: no TCP client within timeout")
      return

    with self._lock:
      self.stats.client_connected = True
    logger.info("Mock FC client connected")

    for _ in range(10):
      self._send_telemetry()
      time.sleep(0.05)

    period = 1.0 / max(self.rate_hz, 1.0)
    next_tx = time.monotonic()
    while not self._stop.is_set():
      now = time.monotonic()
      while True:
        msg = self._conn.recv_match(blocking=False)
        if msg is None:
          break
        self._handle_inbound(msg)

      if now >= next_tx:
        self._send_telemetry()
        next_tx = now + period
      time.sleep(0.002)

  def _handle_inbound(self, msg) -> None:
    mtype = msg.get_type()
    with self._lock:
      if mtype == "VISION_POSITION_ESTIMATE":
        self.stats.vision_count += 1
        self.stats.last_vision = (
          float(msg.x),
          float(msg.y),
          float(msg.z),
          float(msg.yaw),
        )
      elif mtype == "OPTICAL_FLOW_RAD":
        self.stats.optical_flow_count += 1
      elif mtype == "HEARTBEAT":
        pass

  def _send_telemetry(self) -> None:
    if self._conn is None or getattr(self._conn, "port", None) is None:
      return
    mav = self._conn.mav
    boot_ms = int(time.monotonic() * 1000) & 0xFFFFFFFF
    base_mode = mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
    if self.armed:
      base_mode |= mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED

    mav.heartbeat_send(
      mavutil.mavlink.MAV_TYPE_QUADROTOR,
      mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
      base_mode,
      0,
      mavutil.mavlink.MAV_STATE_ACTIVE,
    )
    mav.attitude_send(boot_ms, 0.0, 0.0, self.yaw_rad, 0.0, 0.0, 0.0)
    mav.vfr_hud_send(
      0.0,
      0.0,
      int(self.altitude_m),
      0,
      self.altitude_m,
      0.0,
    )
    mav.global_position_int_send(
      boot_ms,
      int(self.lat * 1e7),
      int(self.lon * 1e7),
      int(self.altitude_m * 1000),
      int(self.altitude_m * 1000),
      0,
      0,
      0,
      int(math.degrees(self.yaw_rad) * 100),
    )
    mav.gps_raw_int_send(
      int(time.time() * 1e6),
      self.gps_fix_type,
      int(self.lat * 1e7),
      int(self.lon * 1e7),
      int(self.altitude_m * 1000),
      65535,
      65535,
      0,
      0,
      self.gps_sats,
    )
    with self._lock:
      self.stats.heartbeat_count += 1
