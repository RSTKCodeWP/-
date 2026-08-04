"""Main control loop — production flight path."""

from __future__ import annotations

import csv
import logging
import math
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2

from aerostab.camera import create_camera
from aerostab.config import AppConfig
from aerostab.estimator import FlowResult, OdometryIntegrator, OpticalFlowEstimator
from aerostab.gps_fusion import GpsFusion
from aerostab.health import evaluate
from aerostab.mavlink_bridge import MavlinkBridge
from aerostab.mask import CameraMask
from aerostab.quality_gate import GateInputs, GateState, flight_ok, step_gate
from aerostab.rtl_path import RtlPathRecorder
from aerostab.sensors.pmw3901 import FlowSensor, create_pmw_sensor
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
        self._pmw: Optional[FlowSensor] = None
        self._mask = CameraMask(config.mask.cols, config.mask.rows)
        self._running = False
        self._csv_file = None
        self._csv_writer = None
        self._frame_times: list[float] = []
        self._last_armed = False
        self._last_send_slot = -1
        self._camera_fail_streak = 0
        self._gate = GateState(nav_valid=False, holding=False, nav_valid_since=0.0, zero_fps_since=0.0)
        self._was_holding = False
        self._last_good_state = None
        self._alt_source_used = "default"
        self._config_lock = threading.Lock()
        self._simulate = config.runtime.simulate

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
        self._flow = OpticalFlowEstimator(
            cfg.camera, cfg.estimator, self._mask, roi_scale=cfg.mask.analysis_roi_scale
        )
        self._odo = OdometryIntegrator(cfg.odometry.max_speed_m_s, cfg.estimator.use_visual_yaw)
        self._mavlink = MavlinkBridge(cfg.mavlink)
        gf = cfg.gps_fusion
        self._fusion = None
        if gf.enabled:
            self._fusion = GpsFusion(
                enabled=True,
                wait_timeout_s=gf.wait_timeout_s,
                accept_radius_km=gf.accept_radius_km,
                alignment_distance_m=gf.alignment_distance_m,
                default_lat=gf.default_lat,
                default_lon=gf.default_lon,
            )
        rc = cfg.rtl
        self._rtl = None
        if rc.enabled:
            self._rtl = RtlPathRecorder(
                enabled=True,
                min_dist_m=rc.min_dist_m,
                max_points=rc.max_points,
                save_path=rc.save_path,
            )
        self._pmw = None
        if cfg.pmw3901.enabled:
            try:
                self._pmw = create_pmw_sensor(cfg.pmw3901, simulate=simulate)
            except Exception as exc:
                logger.warning("PMW3901: %s", exc)
                self._pmw = None
        if cfg.mavlink.enabled:
            try:
                self._mavlink.connect()
            except Exception as exc:
                logger.warning("MAVLink: %s (will retry)", exc)
        if cfg.runtime.log_csv:
            self._open_log()
        self._running = True
        q = cfg.quality
        self.shared.update_status(
            running=True,
            simulate=simulate,
            config_path=self.config_path,
            min_quality=q.min_quality,
            min_points=q.min_points_to_send,
            min_fps=q.min_fps,
        )

    def _restart_camera(self) -> bool:
        """Re-open camera after repeated capture failures."""
        if self._simulate:
            return True
        try:
            if self._camera:
                self._camera.stop()
            self._camera = create_camera(self.config.camera, simulate=False)
            self._camera_fail_streak = 0
            logger.info("Camera restarted")
            return True
        except Exception as exc:
            logger.error("Camera restart failed: %s", exc)
            self._camera = None
            return False

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
            ["t", "x", "y", "vx", "vy", "alt", "quality", "points", "armed", "nav_valid", "holding"]
        )
        logger.info("Log %s", path)

    def _altitude(self) -> float:
        alt_cfg = self.config.altitude
        src = alt_cfg.source
        if src == "static":
            self._alt_source_used = "static"
            return alt_cfg.static_m
        if self._mavlink and self._mavlink.connected:
            if src in ("auto", "rangefinder") and self._mavlink.rangefinder_m is not None:
                rf = self._mavlink.rangefinder_m
                if alt_cfg.min_m <= rf <= alt_cfg.max_m:
                    self._alt_source_used = "rangefinder"
                    return rf
            if src in ("auto", "baro_relative"):
                rel = self._mavlink.relative_baro_m
                if rel is not None and alt_cfg.min_m <= rel <= alt_cfg.max_m:
                    self._alt_source_used = "baro_relative"
                    return max(rel, alt_cfg.min_m)
            if src in ("auto", "mavlink_baro"):
                alt = self._mavlink.altitude_m
                if alt_cfg.min_m <= alt <= alt_cfg.max_m:
                    self._alt_source_used = "relative_alt"
                    return alt
        self._alt_source_used = "default"
        return alt_cfg.default_m

    def _altitude_source_label(self) -> str:
        return getattr(self, "_alt_source_used", self.config.altitude.source)

    def _blend_pmw(self, flow: FlowResult, alt: float) -> FlowResult:
        if not self._pmw:
            return flow
        motion = self._pmw.read_motion()
        pvx, pvy = self._pmw.velocity_m_s(motion, alt)
        w = max(0.0, min(1.0, self.config.pmw3901.blend_weight))
        if flow.quality < self.config.quality.min_quality:
            w = max(w, 0.7)
        vx = flow.vx_m_s * (1 - w) + pvx * w
        vy = flow.vy_m_s * (1 - w) + pvy * w
        q = max(flow.quality, motion.quality * w)
        return FlowResult(
            vx_m_s=vx,
            vy_m_s=vy,
            quality=q,
            n_points=max(flow.n_points, 1 if motion.quality > 0.2 else 0),
            flow_x_px=flow.flow_x_px,
            flow_y_px=flow.flow_y_px,
            yaw_rate_rad_s=flow.yaw_rate_rad_s,
        )

    def _analysis_roi(self, w: int, h: int) -> tuple[int, int, int, int]:
        s = self.config.mask.analysis_roi_scale
        roi_w, roi_h = int(w * s), int(h * s)
        return (w - roi_w) // 2, (h - roi_h) // 2, roi_w, roi_h

    def _draw_metric_grid(self, vis, alt: float) -> None:
        """Overlay ~1 m ground-scale grid at current altitude (FOV-aware)."""
        if not self.config.camera.show_grid or not self._flow:
            return
        h, w = vis.shape[:2]
        focal = self._flow._focal_px
        # meters → pixels at altitude: px = (m / alt) * focal
        if alt < 0.3:
            return
        step_px = max(8, int((1.0 / alt) * focal))
        cx, cy = w // 2, h // 2
        color = (60, 90, 60)
        for x in range(cx % step_px, w, step_px):
            cv2.line(vis, (x, 0), (x, h), color, 1)
        for y in range(cy % step_px, h, step_px):
            cv2.line(vis, (0, y), (w, y), color, 1)
        cv2.putText(vis, "1m grid", (8, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    def tick(self) -> None:
        if not self._running or not self._flow or not self._odo:
            return
        if not self._camera:
            return
        t0 = time.monotonic()

        with self._config_lock:
            cfg = self.config

        if self._mavlink and cfg.mavlink.enabled:
            self._mavlink.poll()

        ok, gray, bgr = self._camera.read_pair()
        if not ok or gray is None:
            self._camera_fail_streak += 1
            if self._mavlink and cfg.mavlink.enabled:
                self._mavlink.poll()
            if self._camera_fail_streak >= 3:
                if self._camera_fail_streak == 3:
                    self._restart_camera()
                self._gate = step_gate(
                    self._gate,
                    GateInputs(
                        tracking_ok=False,
                        nav_ready=False,
                        armed=bool(self._mavlink and self._mavlink.armed),
                        hold_last_on_drop=cfg.quality.hold_last_on_drop,
                        warmup_s=cfg.quality.nav_valid_warmup_s,
                        now=t0,
                        nav_valid_since=0.0,
                        fps=0.0,
                        camera_ok=False,
                    ),
                )
                mav_ok = bool(self._mavlink and self._mavlink.connected)
                health = evaluate(
                    cfg,
                    camera_ok=False,
                    mavlink_ok=mav_ok,
                    quality=0.0,
                    track_points=0,
                    fps=0.0,
                    nav_ready=False,
                    mask_fill_ratio=1.0,
                    simulate=cfg.runtime.simulate,
                    heartbeat_age_s=self._mavlink.heartbeat_age_s if self._mavlink else 999.0,
                    altitude_m=cfg.altitude.default_m,
                    holding=self._gate.holding,
                    nav_valid=False,
                    altitude_source="n/a",
                )
                self.shared.set_health(health)
                self.shared.update_status(
                    fps=0.0,
                    flight_ok=False,
                    nav_valid=False,
                    holding=self._gate.holding,
                )
            return
        self._camera_fail_streak = 0
        if bgr is None:
            bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        dt = 1.0 / max(cfg.runtime.control_hz, 1)
        if self._frame_times:
            dt = max(1e-3, min(0.1, t0 - self._frame_times[-1]))
        self._frame_times.append(t0)
        if len(self._frame_times) > 30:
            self._frame_times.pop(0)

        armed = bool(self._mavlink and self._mavlink.armed)
        if self._mavlink and self._mavlink.last_gps and self._fusion:
            self._fusion.ingest_gps(self._mavlink.last_gps)

        if armed and not self._last_armed and cfg.odometry.reset_on_arm:
            self._odo.reset_origin()
        if self._rtl and armed != self._last_armed:
            self._rtl.on_arm(armed)
        self._last_armed = armed

        alt = self._altitude()
        flow = self._flow.update(gray, alt, dt)
        flow = self._blend_pmw(flow, alt)

        h, w = gray.shape[:2]
        rx, ry, rw, rh = self._analysis_roi(w, h)
        mask_fill = self._mask.masked_fraction_in_roi(rx, ry, rw, rh, w, h)

        qcfg = cfg.quality
        tracking_ok = (
            flow.quality >= qcfg.min_quality
            and flow.n_points >= qcfg.min_points_to_send
            and mask_fill < cfg.mask.max_roi_fill
        )
        nav_ready = self._fusion.nav_ready() if self._fusion else True

        fps = 0.0
        if len(self._frame_times) >= 2:
            fps = (len(self._frame_times) - 1) / (self._frame_times[-1] - self._frame_times[0])

        self._gate = step_gate(
            self._gate,
            GateInputs(
                tracking_ok=tracking_ok,
                nav_ready=nav_ready,
                armed=armed,
                hold_last_on_drop=qcfg.hold_last_on_drop,
                warmup_s=qcfg.nav_valid_warmup_s,
                now=t0,
                nav_valid_since=self._gate.nav_valid_since,
                fps=fps,
                camera_ok=True,
            ),
        )
        nav_valid = self._gate.nav_valid
        holding = self._gate.holding

        if holding and not self._was_holding and self._mavlink:
            self._mavlink.send_status("AeroStab HOLD LAST — texture lost", severity=4)
        elif not holding and self._was_holding and self._mavlink and nav_valid:
            self._mavlink.send_status("AeroStab NAV OK restored", severity=6)
        self._was_holding = holding

        yaw_fc = self._mavlink.fc_yaw_rad() if self._mavlink else None
        state = self._odo.update(
            flow, dt, fc_yaw_rad=yaw_fc, armed=armed, hold=holding
        )
        if self._fusion and not holding:
            x, y, vx, vy = self._fusion.correct(
                state.x_m, state.y_m, state.vx_m_s, state.vy_m_s, dt
            )
            self._odo.set_position(x, y, vx, vy)
            state = self._odo.state

        state.nav_valid = nav_valid and not holding
        if state.nav_valid:
            self._last_good_state = (
                state.x_m,
                state.y_m,
                state.vx_m_s,
                state.vy_m_s,
                state.yaw_rad,
                state.quality,
            )

        if self._rtl:
            self._rtl.sample(state.x_m, state.y_m, alt, state.nav_valid or holding)

        camera_ok = self._camera_fail_streak == 0
        mav_ok = bool(self._mavlink and self._mavlink.connected)
        health = evaluate(
            cfg,
            camera_ok=camera_ok,
            mavlink_ok=mav_ok,
            quality=flow.quality,
            track_points=flow.n_points,
            fps=fps,
            nav_ready=nav_ready,
            mask_fill_ratio=mask_fill,
            simulate=cfg.runtime.simulate,
            heartbeat_age_s=self._mavlink.heartbeat_age_s if self._mavlink else 999.0,
            altitude_m=alt,
            holding=holding,
            nav_valid=state.nav_valid,
            altitude_source=self._altitude_source_label(),
        )
        self.shared.set_health(health)
        ok_to_fly = flight_ok(
            health_ready=health.ready,
            nav_valid=state.nav_valid,
            armed=armed,
            holding=holding,
        )

        slot = int(t0 * cfg.mavlink.rate_hz)
        if self._mavlink and self._mavlink.connected and slot != self._last_send_slot:
            send = False
            send_state = state
            if state.nav_valid:
                send = True
            elif holding and qcfg.hold_send_last_pose and self._last_good_state:
                # Keep feeding last pose so EKF does not lose ExternalNav abruptly
                from aerostab.estimator import OdometryState

                lx, ly, lvx, lvy, lyaw, lq = self._last_good_state
                send_state = OdometryState(
                    x_m=lx, y_m=ly, vx_m_s=0.0, vy_m_s=0.0,
                    yaw_rad=lyaw, quality=lq * 0.5, armed=armed, nav_valid=True,
                )
                send = True
            if send:
                self._mavlink.send_odometry(send_state, alt, nav_valid=True)
                self._last_send_slot = slot

        vis = self._flow.draw_tracks(bgr, show_grid=False)
        self._draw_metric_grid(vis, alt)
        if any(self._mask.cells):
            vis = self._mask.draw_overlay(vis)
        if armed and self._mavlink and self._mavlink.fc_yaw_rad() is not None:
            # Nose arrow from FC yaw
            yaw = self._mavlink.fc_yaw_rad()
            cx, cy = w // 2, h // 2
            L = 40
            ex = int(cx + L * math.sin(yaw))
            ey = int(cy - L * math.cos(yaw))
            cv2.arrowedLine(vis, (cx, cy), (ex, ey), (0, 255, 255), 2, tipLength=0.3)

        if holding:
            status_txt, color = "HOLD LAST", (0, 165, 255)
        elif state.nav_valid:
            status_txt, color = "NAV OK", (0, 255, 0)
        else:
            status_txt, color = "NAV WAIT", (0, 140, 255)
        if armed:
            status_txt += " ARMED"
        if not health.ready and not armed:
            status_txt = "DO NOT ARM — " + status_txt
            color = (0, 0, 255)
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
            ".jpg", vis, [int(cv2.IMWRITE_JPEG_QUALITY), cfg.web.mjpeg_quality]
        )
        self.shared.set_frame(vis, jpeg.tobytes())

        fusion = self._fusion.state() if self._fusion else None
        self.shared.update_status(
            fps=fps,
            mavlink_connected=mav_ok,
            mavlink_messages=self._mavlink._messages_sent if self._mavlink else 0,
            armed=armed,
            nav_ready=nav_ready,
            nav_valid=state.nav_valid,
            holding=holding,
            flight_ok=ok_to_fly,
            min_quality=qcfg.min_quality,
            min_points=qcfg.min_points_to_send,
            min_fps=qcfg.min_fps,
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
            heartbeat_age_s=self._mavlink.heartbeat_age_s if self._mavlink else 999.0,
            altitude_source=self._altitude_source_label(),
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
                    int(holding),
                ]
            )

    def stop(self) -> None:
        self._running = False
        self.shared.update_status(running=False)
        if self._camera:
            self._camera.stop()
        if self._pmw:
            self._pmw.stop()
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
