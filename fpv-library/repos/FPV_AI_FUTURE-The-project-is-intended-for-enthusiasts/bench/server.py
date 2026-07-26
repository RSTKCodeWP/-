"""Flask server for the seeker test bench.

Runs the SeekerObserver in a background worker thread and serves:
  GET  /            -> the dashboard (single page)
  GET  /stream      -> MJPEG of the annotated thermal view
  GET  /telemetry   -> latest telemetry JSON
  POST /control     -> update tunables / recalibrate / toggle recording

Read-only with respect to flight hardware: it never opens a UART or commands an FC.
"""

from __future__ import annotations

import threading
import time

from fpv_ai.bench.observer import COLORMAPS, ObserverConfig, SeekerObserver
from fpv_ai.bench.dashboard import DASHBOARD_HTML
from fpv.seeker.classify.collect import Y16ClipRecorder


class BenchServer:
    def __init__(self, observer: SeekerObserver, *, record_dir: str = "bench_recordings",
                 video_dir: str | None = None, current_video: str | None = None) -> None:
        self.obs = observer
        self._lock = threading.Lock()
        self._jpeg: bytes | None = None
        self._telem: dict = {"state": "STARTING"}
        self._frame = None              # latest (frame_u16, pipeline_output) for the renderer
        self._out = None
        self._stop = threading.Event()
        self._paused = threading.Event()   # set == seeker halted (used while swapping the video)
        self._video_dir = video_dir        # directory scanned for selectable clips
        self._current_video = current_video
        self._record_dir = record_dir
        self._writer = None
        self._recording = False
        # Y16 LOSSLESS dataset recording (separate from the lossy MP4 preview recorder): captures the RAW
        # uint16 frames the pipeline sees into labelled .npz clips for the classifier's heart.
        self._y16_rec: Y16ClipRecorder | None = None
        self._y16_dataset_dir = "y16_dataset"
        self._y16_last: str | None = None
        # Two threads: the seeker runs at full compute speed; rendering/JPEG is decoupled
        # onto its own core so drawing never slows the seeker (this is what fixed "~8 fps").
        self._seeker = threading.Thread(target=self._seeker_loop, name="seeker", daemon=True)
        self._renderer = threading.Thread(target=self._render_loop, name="renderer", daemon=True)

    # ---- workers --------------------------------------------------------------
    def _seeker_loop(self) -> None:
        while not self._stop.is_set():
            if self._paused.is_set():          # halted for a source swap / operator pause
                time.sleep(0.03)
                continue
            try:
                frame, out, telem = self.obs.step()
            except Exception as exc:  # keep the bench alive on transient errors
                with self._lock:
                    self._telem = {"state": "ERROR", "reason": repr(exc)}
                time.sleep(0.1)
                continue
            with self._lock:
                telem["recording"] = self._recording
                telem["y16_recording"] = self._y16_rec is not None
                telem["y16_last"] = self._y16_last
                self._telem = telem
                if frame is not None:
                    self._frame, self._out = frame, out
                    if self._y16_rec is not None:
                        try:
                            self._y16_rec.add(frame)          # LOSSLESS raw-u16 capture for the dataset
                        except ValueError:
                            pass                               # shape/dtype guard -> skip the odd frame
            if frame is None:
                time.sleep(0.02)

    def _render_loop(self) -> None:
        import cv2
        while not self._stop.is_set():
            with self._lock:
                frame, out, telem = self._frame, self._out, dict(self._telem)
            if frame is not None:
                try:
                    annotated = self.obs.render(frame, out, telem)
                    ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    with self._lock:
                        if ok:
                            self._jpeg = buf.tobytes()
                        if self._recording:
                            self._write(annotated)
                except Exception:
                    pass
            time.sleep(0.045)           # ~22 fps render cap; seeker runs faster underneath

    def _write(self, frame) -> None:
        import os
        import cv2
        if self._writer is None:
            os.makedirs(self._record_dir, exist_ok=True)
            h, w = frame.shape[:2]
            path = os.path.join(self._record_dir, f"rec_{int(time.monotonic())}.mp4")
            self._writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 15.0, (w, h))
            self._rec_path = path
        self._writer.write(frame)

    def _toggle_record(self, on: bool) -> None:
        with self._lock:
            self._recording = bool(on)
            if not on and self._writer is not None:
                self._writer.release()
                self._writer = None

    def _toggle_y16_record(self, on: bool, meta: dict) -> dict:
        """Start/stop LOSSLESS Y16 dataset recording of a labelled clip.

        ``meta`` carries the class label + provenance (sortie_id, sensor, is_radiometric_y16, range/aspect/
        conditions).  On stop, the clip is written to ``y16_dataset/IR_<CLASS>_<sortie>.npz`` + a manifest.
        Only a real radiometric-Y16 source should set ``is_radiometric_y16`` -- the current 8-bit CVBS bench
        records honestly-flagged transcodes that do NOT count toward the field-readiness budget.
        """
        with self._lock:
            if on:
                if self._y16_rec is not None:
                    return {"ok": False, "info": "already_recording"}
                cls = str(meta.get("class_label", "DRONE")).upper()
                sortie = str(meta.get("sortie_id") or f"bench_{int(time.monotonic())}")
                kw = {"sensor": str(meta.get("sensor", "FT640_CVBS_8bit")),
                      "is_radiometric_y16": bool(meta.get("is_radiometric_y16", False)),
                      "conditions": str(meta.get("conditions", ""))}
                for k in ("range_hint_m", "aspect_deg"):
                    if meta.get(k) is not None:
                        try:
                            kw[k] = float(meta[k])
                        except (TypeError, ValueError):
                            pass
                self._y16_rec = Y16ClipRecorder(self._y16_dataset_dir, cls, sortie, **kw)
                return {"ok": True, "info": f"recording {cls}/{sortie}"}
            # stop
            if self._y16_rec is None:
                return {"ok": False, "info": "not_recording"}
            rec, self._y16_rec = self._y16_rec, None
        try:
            path = rec.close()
            self._y16_last = path
            return {"ok": True, "info": path}
        except ValueError as exc:
            return {"ok": False, "info": repr(exc)}

    # ---- video source selection ----------------------------------------------
    def _list_videos(self) -> list[str]:
        import os
        if not self._video_dir or not os.path.isdir(self._video_dir):
            return []
        exts = (".mp4", ".avi", ".mov", ".mkv", ".m4v")
        return sorted(f for f in os.listdir(self._video_dir) if f.lower().endswith(exts))

    def _load_video(self, name: str) -> tuple[bool, str]:
        """Switch the running seeker onto ``name`` (a clip in ``video_dir``) and restart acquisition."""
        import os
        if not name or name not in self._list_videos():   # only names we actually listed -> no traversal
            return False, "unknown_video"
        path = os.path.join(self._video_dir, name)
        from fpv_ai.bench.video_source import VideoFileFrameSource
        self._paused.set()
        time.sleep(0.08)                                   # let any in-flight step() finish before the swap
        try:
            self.obs.set_source(VideoFileFrameSource(path, loop=True))
            self._current_video = name
            with self._lock:
                self._jpeg = None                          # drop the stale last frame of the old clip
            return True, name
        except Exception as exc:
            return False, repr(exc)
        finally:
            self._paused.clear()

    # ---- app ------------------------------------------------------------------
    def build_app(self):
        from flask import Flask, Response, jsonify, request

        app = Flask(__name__)

        @app.route("/")
        def index():
            return Response(DASHBOARD_HTML, mimetype="text/html")

        @app.route("/telemetry")
        def telemetry():
            with self._lock:
                t = dict(self._telem)
            t["colormaps"] = COLORMAPS
            t["paused"] = self._paused.is_set()
            t["video"] = self._current_video
            return jsonify(t)

        @app.route("/videos")
        def videos():
            return jsonify({"videos": self._list_videos(), "current": self._current_video,
                            "paused": self._paused.is_set()})

        @app.route("/stream")
        def stream():
            def gen():
                boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                while not self._stop.is_set():
                    with self._lock:
                        data = self._jpeg
                    if data is not None:
                        yield boundary + data + b"\r\n"
                    time.sleep(0.04)
            return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

        @app.route("/control", methods=["POST"])
        def control():
            d = request.get_json(force=True, silent=True) or {}
            extra: dict = {}
            if "load_video" in d:                          # switch to a different clip + restart acquisition
                ok, info = self._load_video(str(d.pop("load_video")))
                extra["load_video"] = {"ok": ok, "info": info}
            if "paused" in d:                              # operator start/stop of the running system
                if bool(d.pop("paused")):
                    self._paused.set()
                else:
                    self._paused.clear()
                extra["paused"] = self._paused.is_set()
            if "record" in d:
                self._toggle_record(bool(d.pop("record")))
            if "record_y16" in d:                          # LOSSLESS labelled dataset capture
                on = bool(d.pop("record_y16"))
                extra["record_y16"] = self._toggle_y16_record(on, d.pop("y16_meta", {}) or {})
            result = self.obs.apply_control(d) if d else {}
            result.update(extra)
            return jsonify({"ok": True, "state": result})

        return app

    def start_worker(self) -> None:
        self._seeker.start()
        self._renderer.start()

    def serve(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        self.start_worker()
        app = self.build_app()
        app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)

    def stop(self) -> None:
        self._stop.set()
        self._toggle_record(False)


def run(cfg: ObserverConfig | None = None, *, host: str = "0.0.0.0", port: int = 8080,
        source: object | None = None, video_dir: str | None = None,
        current_video: str | None = None) -> None:
    obs = SeekerObserver(cfg or ObserverConfig(), source=source)
    srv = BenchServer(obs, video_dir=video_dir, current_video=current_video)
    print(f"[bench] seeker observer ready; open http://<this-pi>:{port}")
    try:
        srv.serve(host=host, port=port)
    finally:
        srv.stop()
        obs.close()
