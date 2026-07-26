"""SeekerObserver -- the engine behind the test bench.

Captures thermal frames, runs the real seeker pipeline, and produces (a) an
annotated BGR image for the live view and (b) a JSON-serialisable telemetry dict.
It also owns the two bench-validated pre-stages -- CVBS border crop and a calibrated
static-clutter mask -- as live-tunable parameters.

The observer is hardware-agnostic: pass a ``device`` string for a real V4L2 grabber,
or inject any ``FrameSource`` (e.g. ``SyntheticSource``) for tests.  Nothing here
touches a flight controller; the seeker command is computed and displayed only.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import numpy as np

from fpv_ai.sensor.thermal_capture import (
    CaptureConfig,
    FrameSource,
    ThermalCapture,
    ft640_intrinsics,
)
from fpv.seeker.detect import ThresholdState, detect_frame  # noqa: F401  (kept for parity/tests)
from fpv.guidance.pipeline import SeekerGuidancePipeline
from fpv_ai.betaflight_link.mission_fsm import MissionController, MissionInputs, MissionPhase

# Colormaps exposed in the UI -> cv2 constant names (resolved lazily so cv2 stays optional at import).
COLORMAPS = ["INFERNO", "JET", "HOT", "TURBO", "VIRIDIS", "BONE"]

# Raw grabber geometry (MacroSilicon MS2109 / FT640 CVBS).
_RAW_W, _RAW_H = 720, 480


@dataclass
class ObserverConfig:
    device: str | int = "/dev/video0"
    width: int = _RAW_W
    height: int = _RAW_H
    fourcc: str = "MJPG"
    deinterlace: bool = False      # CVBS is interlaced; take the even field (kills comb artifacts)
    hfov_deg: float = 48.7
    border_crop: int = 24          # symmetric px cropped off the raw frame (CVBS edge clutter)
    invert: bool = False           # black-hot palette
    mask_on: bool = True           # apply the static-clutter mask
    mask_percentile: float = 99.8  # clutter = persistently brighter than this percentile
    mask_min_counts: float = 150.0 # ...and above this absolute level
    mask_dilate: int = 3
    min_snr: float = 2.0
    min_area: int = 2
    colormap: str = "INFERNO"
    warmup_frames: int = 25
    designation_box_px: int = 240   # operator aim reticle: only targets inside lock
    # R1/R4/R5 lock-robustness -- help hold a lock through movement / a large deforming target
    imm_coast: bool = True          # coast on the IMM prediction through brief detection gaps
    peak_deletion: bool = True      # release only a genuinely-gone target; resist single-frame dropouts
    regime: bool = True             # classify POINT/RESOLVED/FILL
    aimpoint: bool = True           # migrate the LOS centroid to the silhouette for a large target


@dataclass
class _Fps:
    """Exponential-moving-average frame-rate meter."""
    ema_ms: float = 0.0
    alpha: float = 0.1

    def update(self, dt_ms: float) -> None:
        self.ema_ms = dt_ms if self.ema_ms == 0.0 else (1 - self.alpha) * self.ema_ms + self.alpha * dt_ms

    @property
    def fps(self) -> float:
        return 1000.0 / self.ema_ms if self.ema_ms > 0 else 0.0


class SeekerObserver:
    """Owns capture + pipeline + clutter mask; produces annotated frame + telemetry."""

    def __init__(self, cfg: ObserverConfig | None = None, *, source: FrameSource | None = None) -> None:
        self.cfg = cfg or ObserverConfig()
        self._lock = threading.Lock()
        self._src = source or self._open_v4l2()
        self.cap = ThermalCapture(self._src, self._capture_config())
        self.pipe = self._build_pipe()
        self._clutter: np.ndarray | None = None
        self._mask_fill = 0.0
        self._fps_total = _Fps()
        self._fps_cap = _Fps()
        self._fps_det = _Fps()
        self._frame_id = 0
        self._t0 = time.monotonic()
        self._last = self._t0
        # Operator-cued engagement state.  STANDBY: observe only; ENGAGED: launch authorized.
        self.engaged = False
        self.armed = False
        self._last_out = None
        # Mission supervisor (DISPLAY ONLY on the bench): surfaces the live phase
        # IDLE->ACQUIRE->STUDY->READY->ENGAGING from the same pipeline output + the operator cue.
        self._mission = MissionController()
        self._lock_frames = 0
        self._class_frames = 0
        self._prev_engaged = False
        self.mission_phase = MissionPhase.IDLE
        if self.cfg.mask_on:
            self.calibrate_clutter()
        self._seed_designation()   # only targets inside the centre reticle can lock

    # ---- operator-cued engagement --------------------------------------------
    def _designation_box(self) -> tuple[float, float, float, float]:
        w = float(self.pipe.intrinsics.width)
        h = float(self.pipe.intrinsics.height)
        b = float(self.cfg.designation_box_px)
        return ((w - b) / 2.0, (h - b) / 2.0, b, b)

    def _seed_designation(self) -> None:
        w = float(self.pipe.intrinsics.width)
        h = float(self.pipe.intrinsics.height)
        self.pipe.designate((w / 2.0, h / 2.0), basket_px=float(self.cfg.designation_box_px))

    def launch(self) -> tuple[bool, str]:
        """Operator pressed LAUNCH: authorise engagement of the locked target."""
        out = self._last_out
        if out is None or not out.locked:
            return False, "no_lock"
        self.armed = True
        self.engaged = True
        return True, "engaged"

    def safe(self) -> tuple[bool, str]:
        """Operator pressed SAFE/ABORT: disarm and re-arm acquisition on the reticle."""
        self.engaged = False
        self.armed = False
        self._seed_designation()
        self._mission = MissionController()   # supervisor back to IDLE (re-acquire)
        self._lock_frames = self._class_frames = 0
        return True, "standby"

    # ---- construction helpers -------------------------------------------------
    def _build_pipe(self) -> SeekerGuidancePipeline:
        return SeekerGuidancePipeline(
            intrinsics=ft640_intrinsics(hfov_deg=self.cfg.hfov_deg),
            min_snr=self.cfg.min_snr, min_area_px=self.cfg.min_area,
            use_imm_coast=self.cfg.imm_coast, use_peak_relative_deletion=self.cfg.peak_deletion,
            regime_enabled=self.cfg.regime, aimpoint_migration=self.cfg.aimpoint,
            target_span_m=4.0)   # range-aided: silhouette extent + measured range for the reference

    def set_source(self, src: FrameSource) -> None:
        """Swap the frame source live (switch to a different clip) and restart acquisition on it.

        The caller MUST guarantee no concurrent ``step()`` while this runs (the bench pauses its
        seeker thread first) -- an OpenCV VideoCapture is not safe to read from two threads.
        """
        old = self.cap.source
        self.cap.source = src
        if old is not None and old is not src:
            try:
                old.close()
            except Exception:
                pass
        # fresh acquisition on the new stream: new pipeline/track state, back to STANDBY
        self.pipe = self._build_pipe()
        self._frame_id = 0
        self._t0 = time.monotonic()
        self._last = self._t0
        self.engaged = False
        self.armed = False
        self._last_out = None
        self._mission = MissionController()   # supervisor back to IDLE on a new clip
        self._lock_frames = self._class_frames = 0
        self._prev_engaged = False
        self._clutter = None
        self._seed_designation()
        if self.cfg.mask_on:
            self.calibrate_clutter()

    def _open_v4l2(self) -> FrameSource:
        from fpv_ai.sensor.thermal_capture import V4L2Source
        return V4L2Source(self.cfg.device, width=self.cfg.width, height=self.cfg.height,
                          fourcc=self.cfg.fourcc)

    def _capture_config(self) -> CaptureConfig:
        c = max(0, int(self.cfg.border_crop))
        roi = (c, c, self.cfg.width - 2 * c, self.cfg.height - 2 * c) if c > 0 else None
        return CaptureConfig(roi=roi, invert=self.cfg.invert, deinterlace=self.cfg.deinterlace)

    # ---- calibration ----------------------------------------------------------
    def calibrate_clutter(self, n: int | None = None) -> int:
        """Learn the static-clutter mask from N warmup frames (persistently bright px)."""
        import scipy.ndimage as ndi
        n = n or self.cfg.warmup_frames
        frames = []
        for _ in range(n):
            f = self.cap.frame_u16()
            if f is not None:
                frames.append(f.astype(np.float32))
        if not frames:
            return 0
        wm = np.mean(np.stack(frames), axis=0)
        thr = max(float(np.percentile(wm, self.cfg.mask_percentile)), self.cfg.mask_min_counts)
        mask = wm > thr
        if self.cfg.mask_dilate > 0:
            mask = ndi.binary_dilation(mask, iterations=self.cfg.mask_dilate)
        with self._lock:
            self._clutter = mask
            self._mask_fill = float(np.median(wm))   # static fill -> no per-frame median
        return int(mask.sum())

    # ---- live control ---------------------------------------------------------
    def apply_control(self, d: dict) -> dict:
        """Update tunables from a control dict; returns the resulting state summary."""
        if d.pop("launch", False):
            self.launch()
        if d.pop("safe", False):
            self.safe()
        if "designation_box_px" in d:
            self.cfg.designation_box_px = int(d.pop("designation_box_px"))
            if not self.engaged:
                self._seed_designation()
        recapture = False
        recalibrate = bool(d.pop("recalibrate_mask", False))
        for k in ("invert", "border_crop"):
            if k in d:
                setattr(self.cfg, k, type(getattr(self.cfg, k))(d[k]))
                recapture = True
        for k in ("mask_on", "min_snr", "min_area", "colormap", "mask_percentile", "mask_min_counts"):
            if k in d:
                setattr(self.cfg, k, type(getattr(self.cfg, k))(d[k]))
        # push detection gates into the live pipeline so calibration actually bites
        self.pipe.min_snr = float(self.cfg.min_snr)
        self.pipe.min_area_px = int(self.cfg.min_area)
        if recapture:
            self.cap.cfg = self._capture_config()
            recalibrate = recalibrate or self.cfg.mask_on
        if recalibrate and self.cfg.mask_on:
            self.calibrate_clutter()
        if not self.cfg.mask_on:
            with self._lock:
                self._clutter = None
        return {"mask_on": self.cfg.mask_on, "border_crop": self.cfg.border_crop,
                "invert": self.cfg.invert, "min_snr": self.cfg.min_snr,
                "min_area": self.cfg.min_area, "colormap": self.cfg.colormap,
                "mode": "ENGAGED" if self.engaged else "STANDBY"}

    # ---- per-frame processing -------------------------------------------------
    def step(self) -> tuple[np.ndarray | None, object, dict]:
        """Capture + mask + seeker pipeline (NO annotation).

        Returns ``(frame_u16, pipeline_output, telemetry)``.  This is the hot path;
        annotation/JPEG is split into ``render()`` so a separate thread can draw
        without slowing the seeker.
        """
        t_a = time.monotonic()
        frame = self.cap.frame_u16()
        t_b = time.monotonic()
        if frame is None:
            return None, None, {"error": "no_frame", "t": round(t_b - self._t0, 1)}

        if self.cfg.mask_on and self._clutter is not None and self._clutter.shape == frame.shape:
            frame = frame.copy()
            frame[self._clutter] = self._mask_fill

        now = time.monotonic()
        dt = max(now - self._last, 1e-4)
        self._last = now
        out = self.pipe.step(now, frame, (0.0, 0.0, 0.0), dt)
        t_c = time.monotonic()

        self._frame_id += 1
        self._fps_cap.update((t_b - t_a) * 1000.0)
        self._fps_det.update((t_c - t_b) * 1000.0)
        self._fps_total.update((t_c - t_a) * 1000.0)
        self._last_out = out
        # ENGAGED requires a live lock -- a dropped lock auto-reverts to STANDBY (safe).
        if self.engaged and not out.locked:
            self.engaged = False
            self.armed = False
        self._update_mission(out, now)
        return frame, out, self._telemetry(out, frame)

    def _update_mission(self, out, now: float) -> None:
        """Drive the DISPLAY-ONLY mission supervisor from the pipeline output + operator engage state.

        This surfaces the doctrine phase (ACQUIRE->STUDY->READY->ENGAGING) live; it does NOT change the
        bench's engage/command logic (the bench is a read-only preview).  The operator LAUNCH is the
        trigger and, being a preview, is treated as authorised; SAFE resets the supervisor to IDLE.
        """
        locked = bool(out.locked) and out.tracking_state == "LOCKED"
        self._lock_frames = self._lock_frames + 1 if locked else 0
        lock_stable = self._lock_frames >= 5
        class_ok = locked and bool(out.engage_permitted)     # the CNN firewall (or default-permit) as the class cue
        self._class_frames = self._class_frames + 1 if class_ok else 0
        class_asserted = self._class_frames >= 5
        reference_ready = lock_stable and class_asserted and out.extent_px is not None
        snapshot = ({"class_label": "winged_uav", "silhouette_major_px": float(out.extent_px or 0.0),
                     "range_m": float(out.range_m or 0.0), "closing_mps": float(out.closing_mps or 0.0)}
                    if reference_ready else None)
        cancel = self._prev_engaged and not self.engaged     # SAFE just pressed -> veto
        self._prev_engaged = self.engaged
        dec = self._mission.step(MissionInputs(
            now=now, cued=True, in_fov=bool(out.locked), lock_stable=lock_stable,
            class_asserted=class_asserted, reference_ready=reference_ready, reference_snapshot=snapshot,
            operator_trigger=self.engaged, authorization_valid=self.engaged, operator_cancel=cancel,
            launched=self.engaged, link_healthy=True, guidance_age_s=0.0 if out.locked else None,
            t_go_s=out.t_go_s if out.t_go_s is not None else float("inf"),
            range_to_target_m=out.range_m if out.range_m is not None else float("inf"),
            guidance_abort=bool(out.roe_abort), model_wrong=not out.engage_permitted))
        self.mission_phase = dec.phase

    def render(self, frame: np.ndarray, out, telem: dict) -> np.ndarray:
        """Annotate a frame produced by ``step()`` -- safe on a separate thread."""
        return self._annotate(frame, out, telem)

    def process_one(self) -> tuple[np.ndarray | None, dict]:
        """Convenience: step + render in one call (used by tests / simple loops)."""
        frame, out, telem = self.step()
        if frame is None:
            return None, telem
        return self.render(frame, out, telem), telem

    # ---- telemetry ------------------------------------------------------------
    def _telemetry(self, out, frame: np.ndarray) -> dict:
        imm = out.imm
        blobs = out.blobs or ()
        top = None
        if blobs:
            b = blobs[0]
            top = {"x": round(float(b.centroid_px[0]), 1), "y": round(float(b.centroid_px[1]), 1),
                   "area": int(b.area_px), "area_ext": int(b.area_extended_px),
                   "snr": round(float(b.snr), 1)}
        cmd = None
        c = out.command
        if c is not None:
            cmd = {"roll": round(float(c.roll_cmd), 3), "pitch": round(float(c.pitch_cmd), 3),
                   "yaw": round(float(c.yaw_rate_cmd), 3), "throttle": round(float(c.throttle_cmd), 3),
                   "confidence": round(float(c.target_confidence), 2), "speed_mode": str(c.speed_mode.name)}
        h, w = frame.shape
        return {
            "frame_id": self._frame_id,
            "t": round(time.monotonic() - self._t0, 1),
            "state": out.tracking_state,
            "mission_phase": self.mission_phase.value,   # supervisor phase: ACQUIRE/STUDY/READY/ENGAGING
            "locked": bool(out.locked),
            "roe_abort": bool(out.roe_abort),
            "reason": out.reason,
            "lam_az": None if imm is None else round(float(imm.az_rate_radps), 4),
            "lam_el": None if imm is None else round(float(imm.el_rate_radps), 4),
            "lock_quality": None if imm is None else round(float(imm.lock_quality), 3),
            "model_ok": None if imm is None else bool(imm.model_ok),
            "az_deg": None if imm is None else round(float(np.degrees(imm.az_rad)), 2),
            "el_deg": None if imm is None else round(float(np.degrees(imm.el_rad)), 2),
            "fps_total": round(self._fps_total.fps, 1),
            "fps_capture": round(self._fps_cap.fps, 1),
            "fps_detect": round(self._fps_det.fps, 1),
            "n_blobs": len(blobs),
            "top": top,
            "threshold": round(float(out.threshold_counts), 1),
            "command": cmd,
            "centroid": None if out.centroid_px is None else [round(float(out.centroid_px[0]), 1),
                                                              round(float(out.centroid_px[1]), 1)],
            "mask_on": self.cfg.mask_on,
            "mask_px": 0 if self._clutter is None else int(self._clutter.sum()),
            "border_crop": self.cfg.border_crop,
            "invert": self.cfg.invert,
            "colormap": self.cfg.colormap,
            "min_snr": self.cfg.min_snr,
            "min_area": self.cfg.min_area,
            "resolution": [int(w), int(h)],
            "mode": "ENGAGED" if self.engaged else "STANDBY",
            "engaged": self.engaged,
            "armed": self.armed,
            "can_launch": bool(out.locked and not self.engaged),
            "designation_box": [round(v, 1) for v in self._designation_box()],
        }

    # ---- annotation -----------------------------------------------------------
    def _annotate(self, frame: np.ndarray, out, telem: dict) -> np.ndarray:
        import cv2
        # Percentile auto-stretch to 8-bit: works for an 8-bit AGC camera AND a 14-bit
        # synthetic/radiometric source (a raw clip(0,255) would saturate the latter).
        g = frame.astype(np.float32)
        lo = float(np.percentile(g, 1.0))
        hi = float(np.percentile(g, 99.5))
        gray = np.clip((g - lo) / max(hi - lo, 1.0) * 255.0, 0.0, 255.0).astype(np.uint8)
        cmap = getattr(cv2, f"COLORMAP_{self.cfg.colormap}", cv2.COLORMAP_INFERNO)
        img = cv2.applyColorMap(gray, cmap)
        h, w = gray.shape

        # boresight crosshair (frame centre)
        cx, cy = w // 2, h // 2
        cv2.drawMarker(img, (cx, cy), (90, 90, 90), cv2.MARKER_CROSS, 18, 1)

        # operator aim reticle (acquisition box) -- only targets inside this lock
        bx, by, bw_, bh_ = (int(v) for v in self._designation_box())
        ret_col = (60, 230, 60) if self.engaged else (190, 190, 90)
        cv2.rectangle(img, (bx, by), (bx + bw_, by + bh_), ret_col, 1)

        # all candidate blobs -> thin boxes
        for b in (out.blobs or ()):
            x, y, bw, bh = b.bbox
            cv2.rectangle(img, (x, y), (x + bw, y + bh), (120, 120, 120), 1)

        locked = out.locked or out.tracking_state in ("LOCKED", "TRACKING")
        col = (60, 230, 60) if locked else (60, 200, 255)
        if out.bbox is not None:
            x, y, bw, bh = out.bbox
            cv2.rectangle(img, (x, y), (x + bw, y + bh), col, 2)
        if out.centroid_px is not None:
            tx, ty = int(out.centroid_px[0]), int(out.centroid_px[1])
            cv2.drawMarker(img, (tx, ty), col, cv2.MARKER_CROSS, 26, 2)
            cv2.line(img, (cx, cy), (tx, ty), col, 1)

        # guidance command vector (read-only preview): roll -> x, throttle dev -> y.
        # Bright when ENGAGED (committed), dim in STANDBY (just a preview).
        if out.command is not None:
            c = out.command
            ex = int(cx + c.roll_cmd * 90)
            ey = int(cy - (c.throttle_cmd - 0.5) * 2 * 90)
            acol = (0, 255, 255) if self.engaged else (110, 130, 130)
            cv2.arrowedLine(img, (cx, cy), (ex, ey), acol, 2 if self.engaged else 1, tipLength=0.25)

        # engagement banner (top-right)
        if self.engaged:
            cv2.rectangle(img, (w - 150, 6), (w - 6, 28), (40, 40, 200), -1)
            cv2.putText(img, "ENGAGED", (w - 138, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        else:
            cv2.putText(img, "STANDBY", (w - 120, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (160, 160, 160), 2, cv2.LINE_AA)

        self._draw_hud(img, telem)
        return img

    @staticmethod
    def _draw_hud(img: np.ndarray, t: dict) -> None:
        import cv2
        lines = [
            f"STATE {t['state']}  {'LOCK' if t['locked'] else '----'}",
            f"lam_az {t['lam_az']}  lam_el {t['lam_el']}",
            f"fps {t['fps_total']} (cap {t['fps_capture']} / det {t['fps_detect']})",
            f"blobs {t['n_blobs']}  thr {t['threshold']}",
        ]
        y = 20
        for ln in lines:
            cv2.putText(img, ln, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(img, ln, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (235, 235, 235), 1, cv2.LINE_AA)
            y += 18

    def close(self) -> None:
        try:
            self.cap.close()
        except Exception:
            pass
