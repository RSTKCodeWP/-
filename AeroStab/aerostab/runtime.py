"""Main control loop."""

from __future__ import annotations

import csv
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2

from aerostab.camera import create_camera
from aerostab.config import AppConfig
from aerostab.estimator import OdometryIntegrator, OpticalFlowEstimator
from aerostab.mavlink_bridge import MavlinkBridge
from aerostab.state import SharedState

logger = logging.getLogger(__name__)


class AeroStabRuntime:
    def __init__(self, config: AppConfig, shared: SharedState):
        self.config = config
        self.shared = shared
        self._camera = None
        self._flow: Optional[OpticalFlowEstimator] = None
        self._odo: Optional[OdometryIntegrator] = None
        self._mavlink: Optional[MavlinkBridge] = None
        self._running = False
        self._csv_file = None
        self._csv_writer = None
        self._frame_times: list[float] = []

    def start(self) -> None:
        cfg = self.config
        simulate = cfg.runtime.simulate
        self._camera = create_camera(cfg.camera, simulate=simulate)
        self._flow = OpticalFlowEstimator(cfg.camera, cfg.estimator)
        self._odo = OdometryIntegrator(cfg.odometry.max_speed_m_s, cfg.odometry.position_lpf_alpha)
        self._mavlink = MavlinkBridge(cfg.mavlink)
        if cfg.mavlink.enabled and not simulate:
            try:
                self._mavlink.connect()
            except Exception as exc:
                logger.warning("MAVLink connect failed (continuing without FC): %s", exc)
        if cfg.runtime.log_csv:
            self._open_log()
        self._running = True
        self.shared.update_status(running=True, simulate=simulate)

    def _open_log(self) -> None:
        log_dir = Path(self.config.runtime.log_dir)
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            log_dir = Path("logs")
            log_dir.mkdir(parents=True, exist_ok=True)
        name = datetime.utcnow().strftime("%Y%m%d_%H%M%S") + ".csv"
        path = log_dir / name
        self._csv_file = open(path, "w", newline="", encoding="utf-8")
        self._csv_writer = csv.writer(self._csv_file)
        self._csv_writer.writerow(["t", "x", "y", "vx", "vy", "alt", "quality", "points"])
        logger.info("Logging to %s", path)

    def _altitude(self) -> float:
        alt_cfg = self.config.altitude
        if alt_cfg.source == "static":
            return alt_cfg.static_m
        if self._mavlink and self._mavlink.connected:
            alt = self._mavlink.altitude_m
            if alt_cfg.min_m <= alt <= alt_cfg.max_m:
                return alt
        return alt_cfg.default_m

    def tick(self) -> None:
        if not self._running or self._camera is None or self._flow is None or self._odo is None:
            return
        t0 = time.monotonic()
        ok, gray = self._camera.read_gray()
        if not ok or gray is None:
            return
        ok_bgr, bgr = self._camera.read_bgr()
        if not ok_bgr or bgr is None:
            bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        dt = 1.0 / max(self.config.runtime.control_hz, 1)
        if self._frame_times:
            dt = max(1e-3, min(0.1, t0 - self._frame_times[-1]))
        self._frame_times.append(t0)
        if len(self._frame_times) > 30:
            self._frame_times.pop(0)

        if self._mavlink:
            self._mavlink.poll()

        alt = self._altitude()
        flow = self._flow.update(gray, alt, dt)
        yaw = self._mavlink.fc_yaw_rad() if self._mavlink else None
        state = self._odo.update(flow, dt, fc_yaw_rad=yaw)

        mavlink_rate = self.config.mavlink.rate_hz
        if self._mavlink and self._mavlink.connected:
            if int(t0 * mavlink_rate) != int((t0 - dt) * mavlink_rate):
                self._mavlink.send_odometry(state, alt)

        vis = self._flow.draw_tracks(bgr)
        cv2.putText(
            vis,
            f"ALT {alt:.1f}m Q {flow.quality:.2f} P {flow.n_points}",
            (8, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 0),
            1,
        )
        _, jpeg = cv2.imencode(
            ".jpg", vis, [int(cv2.IMWRITE_JPEG_QUALITY), self.config.web.mjpeg_quality]
        )
        self.shared.set_frame(vis, jpeg.tobytes())

        fps = 0.0
        if len(self._frame_times) >= 2:
            fps = (len(self._frame_times) - 1) / (self._frame_times[-1] - self._frame_times[0])

        self.shared.update_status(
            fps=fps,
            mavlink_connected=bool(self._mavlink and self._mavlink.connected),
            mavlink_messages=self._mavlink._messages_sent if self._mavlink else 0,
            altitude_m=alt,
            vx_m_s=state.vx_m_s,
            vy_m_s=state.vy_m_s,
            x_m=state.x_m,
            y_m=state.y_m,
            quality=state.quality,
            track_points=flow.n_points,
        )

        if self._csv_writer:
            self._csv_writer.writerow(
                [time.time(), state.x_m, state.y_m, state.vx_m_s, state.vy_m_s, alt, flow.quality, flow.n_points]
            )

    def stop(self) -> None:
        self._running = False
        self.shared.update_status(running=False)
        if self._camera:
            self._camera.stop()
        if self._mavlink:
            self._mavlink.close()
        if self._csv_file:
            self._csv_file.close()

    def run_loop(self) -> None:
        self.start()
        period = 1.0 / max(self.config.runtime.control_hz, 1)
        try:
            while self._running:
                loop_start = time.monotonic()
                self.tick()
                elapsed = time.monotonic() - loop_start
                time.sleep(max(0, period - elapsed))
        except KeyboardInterrupt:
            logger.info("Interrupted")
        finally:
            self.stop()
