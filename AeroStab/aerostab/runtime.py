"""Main control loop."""

from __future__ import annotations

import csv
import logging
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2

from aerostab.camera import create_camera
from aerostab.config import AppConfig
from aerostab.estimator import OdometryIntegrator, OpticalFlowEstimator
from aerostab.gps_fusion import GpsFusion
from aerostab.health import evaluate
from aerostab.mavlink_bridge import MavlinkBridge
from aerostab.mask import CameraMask
from aerostab.rtl_path import RtlPathRecorder
from aerostab.state import SharedState

logger = logging.getLogger(__name__)


class AeroStabRuntime:
    def __init__(self, config: AppConfig, shared: SharedState, config_path: str = ""):
        self.config = config
        self.config_path = config_path
        self.shared = shared
        self._camera = None
        self._flow: Optional[OpticalFlowEstimator] = None
        self._odo: Optional[OdometryIntegrator] = None
        self._mavlink: Optional[MavlinkBridge] = None
        self._fusion: Optional[GpsFusion] = None
        self._rtl: Optional[RtlPathRecorder] = None
        self._mask = CameraMask(config.mask.cols, config.mask.rows)
        self._running = False
        self._csv_file = None
        self._csv_writer = None
        self._frame_times: list[float] = []
        self._last_armed = False
        self._last_send_slot = -1

    def reload_mask(self) -> None:
        if self.config.mask.enabled:
            self._mask = CameraMask.load(Path(self.config.mask.path))
            if self._flow:
                self._flow.mask = self._mask

    def start(self) -> None:
        cfg = self.config
        simulate = cfg.runtime.simulate
        self.reload_mask()
        self._camera = create_camera(cfg.camera, simulate=simulate)
        self._flow = OpticalFlowEstimator(cfg.camera, cfg.estimator, self._mask)
        self._odo = OdometryIntegrator(cfg.odometry.max_speed_m_s, cfg.estimator.use_visual_yaw)
        self._mavlink = MavlinkBridge(cfg.mavlink)
        gf = cfg.gps_fusion
        self._fusion = GpsFusion(
            enabled=gf.enabled,
            wait_timeout_s=gf.wait_timeout_s,
            accept_radius_km=gf.accept_radius_km,
            alignment_distance_m=gf.alignment_distance_m,
            default_lat=gf.default_lat,
            default_lon=gf.default_lon,
        )
        rc = cfg.rtl
        self._rtl = RtlPathRecorder(
            enabled=rc.enabled,
            min_dist_m=rc.min_dist_m,
            max_points=rc.max_points,
            save_path=rc.save_path,
        )
        if cfg.mavlink.enabled:
            try:
                self._mavlink.connect()
            except Exception as exc:
                logger.warning("MAVLink: %s (bench mode)", exc)
        if cfg.runtime.log_csv:
            self._open_log()
        self._running = True
        self.shared.update_status(running=True, simulate=simulate, config_path=self.config_path)

    def _open_log(self) -> None:
        log_dir = Path(self.config.runtime.log_dir)
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            log_dir = Path("logs")
            log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / (datetime.utcnow().strftime("%Y%m%d_%H%M%S") + ".csv")
        self._csv_file = open(path, "w", newline="", encoding="utf-8")
        self._csv_writer = csv.writer(self._csv_file)
        self._csv_writer.writerow(
            ["t", "x", "y", "vx", "vy", "alt", "quality", "points", "armed", "nav_valid"]
        )
        logger.info("Log %s", path)

    def _altitude(self) -> float:
        alt_cfg = self.config.altitude
        if alt_cfg.source == "static":
            return alt_cfg.static_m
        if self._mavlink and self._mavlink.connected:
            alt = self._mavlink.altitude_m
            if alt_cfg.min_m <= alt <= alt_cfg.max_m:
                return alt
        return alt_cfg.default_m

    def _analysis_roi(self, w: int, h: int) -> tuple[int, int, int, int]:
        s = self.config.mask.analysis_roi_scale
        roi_w, roi_h = int(w * s), int(h * s)
        return (w - roi_w) // 2, (h - roi_h) // 2, roi_w, roi_h

    def tick(self) -> None:
        if not self._running or not self._camera or not self._flow or not self._odo:
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

        armed = False
        if self._mavlink:
            self._mavlink.poll()
            armed = self._mavlink.armed
            if self._mavlink.last_gps and self._fusion:
                self._fusion.ingest_gps(self._mavlink.last_gps)

        if armed and not self._last_armed and self.config.odometry.reset_on_arm:
            self._odo.reset_origin()
        if self._rtl and armed != self._last_armed:
            self._rtl.on_arm(armed)
        self._last_armed = armed

        alt = self._altitude()
        flow = self._flow.update(gray, alt, dt)
        yaw_fc = self._mavlink.fc_yaw_rad() if self._mavlink else None
        state = self._odo.update(flow, dt, fc_yaw_rad=yaw_fc, armed=armed)

        if self._fusion:
            x, y, vx, vy = self._fusion.correct(state.x_m, state.y_m, state.vx_m_s, state.vy_m_s, dt)
            self._odo.set_position(x, y, vx, vy)
            state = self._odo.state

        h, w = gray.shape[:2]
        rx, ry, rw, rh = self._analysis_roi(w, h)
        mask_fill = self._mask.masked_fraction_in_roi(rx, ry, rw, rh, w, h)

        qcfg = self.config.quality
        nav_valid = (
            flow.quality >= qcfg.min_quality
            and flow.n_points >= qcfg.min_points_to_send
            and mask_fill < self.config.mask.max_roi_fill
        )
        nav_ready = self._fusion.nav_ready() if self._fusion else True
        state.nav_valid = nav_valid and nav_ready

        if self._rtl:
            self._rtl.sample(state.x_m, state.y_m, alt, state.nav_valid)

        fps = 0.0
        if len(self._frame_times) >= 2:
            fps = (len(self._frame_times) - 1) / (self._frame_times[-1] - self._frame_times[0])

        health = evaluate(
            self.config,
            camera_ok=True,
            mavlink_ok=bool(self._mavlink and self._mavlink.connected),
            quality=flow.quality,
            track_points=flow.n_points,
            fps=fps,
            nav_ready=nav_ready,
            mask_fill_ratio=mask_fill,
            simulate=self.config.runtime.simulate,
        )
        self.shared.set_health(health)

        slot = int(t0 * self.config.mavlink.rate_hz)
        if (
            self._mavlink
            and self._mavlink.connected
            and nav_valid
            and nav_ready
            and slot != self._last_send_slot
        ):
            self._mavlink.send_odometry(state, alt, nav_valid=True)
            self._last_send_slot = slot

        vis = self._flow.draw_tracks(bgr, show_grid=self.config.camera.show_grid)
        color = (0, 255, 0) if state.nav_valid else (0, 140, 255)
        status_txt = "NAV OK" if state.nav_valid else "NAV WAIT"
        if armed:
            status_txt += " ARMED"
        cv2.putText(
            vis,
            f"{status_txt} ALT{alt:.1f}m Q{flow.quality:.2f} P{flow.n_points}",
            (8, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
        )
        _, jpeg = cv2.imencode(
            ".jpg", vis, [int(cv2.IMWRITE_JPEG_QUALITY), self.config.web.mjpeg_quality]
        )
        self.shared.set_frame(vis, jpeg.tobytes())

        fusion = self._fusion.state() if self._fusion else None
        self.shared.update_status(
            fps=fps,
            mavlink_connected=bool(self._mavlink and self._mavlink.connected),
            mavlink_messages=self._mavlink._messages_sent if self._mavlink else 0,
            armed=armed,
            nav_ready=nav_ready,
            nav_valid=state.nav_valid,
            altitude_m=alt,
            vx_m_s=state.vx_m_s,
            vy_m_s=state.vy_m_s,
            x_m=state.x_m,
            y_m=state.y_m,
            yaw_deg=math.degrees(state.yaw_rad),
            quality=flow.quality,
            track_points=flow.n_points,
            gps_fix=self._mavlink.last_gps.fix_type if self._mavlink and self._mavlink.last_gps else 0,
            gps_sats=self._mavlink.last_gps.satellites if self._mavlink and self._mavlink.last_gps else 0,
            fusion_scale=fusion.scale if fusion else 1.0,
            mask_fill=mask_fill,
            rtl_recording=bool(self._rtl and self._rtl.recording),
            rtl_points=self._rtl.point_count if self._rtl else 0,
            rtl_length_m=self._rtl.path_length_m() if self._rtl else 0.0,
        )

        if self._csv_writer:
            self._csv_writer.writerow(
                [
                    time.time(),
                    state.x_m,
                    state.y_m,
                    state.vx_m_s,
                    state.vy_m_s,
                    alt,
                    flow.quality,
                    flow.n_points,
                    int(armed),
                    int(state.nav_valid),
                ]
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
                t = time.monotonic()
                self.tick()
                time.sleep(max(0, period - (time.monotonic() - t)))
        except KeyboardInterrupt:
            logger.info("Stop")
        finally:
            self.stop()
