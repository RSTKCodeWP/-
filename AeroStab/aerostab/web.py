"""Production web dashboard."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from flask import Flask, Response, jsonify, request, send_from_directory

if TYPE_CHECKING:
    from aerostab.config import AppConfig
    from aerostab.runtime import AeroStabRuntime
    from aerostab.state import SharedState

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_web_app(
    shared: SharedState,
    config: AppConfig,
    runtime: Optional[AeroStabRuntime] = None,
    config_path: str = "",
) -> Flask:
    app = Flask(__name__, static_folder=str(STATIC_DIR))

    @app.route("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.route("/static/<path:filename>")
    def static_files(filename):
        return send_from_directory(STATIC_DIR, filename)

    @app.route("/api/status")
    def status():
        return jsonify(shared.snapshot())

    @app.route("/api/config", methods=["GET", "POST"])
    def api_config():
        from dataclasses import asdict

        if request.method == "GET":
            return jsonify(
                {
                    "camera": asdict(config.camera),
                    "gps_fusion": asdict(config.gps_fusion),
                    "quality": asdict(config.quality),
                }
            )
        data = request.get_json(force=True)
        config.camera.fov_deg = float(data.get("fov_deg", config.camera.fov_deg))
        config.camera.rotation_deg = int(data.get("rotation_deg", config.camera.rotation_deg))
        config.camera.fps = int(data.get("fps", config.camera.fps))
        config.camera.show_grid = bool(data.get("show_grid", config.camera.show_grid))
        config.gps_fusion.enabled = bool(data.get("gps_fusion", config.gps_fusion.enabled))
        config.quality.min_quality = float(data.get("min_quality", config.quality.min_quality))
        if config_path:
            from aerostab.config import save_config

            save_config(config, config_path)
        if runtime and runtime._flow:
            runtime._flow.cam = config.camera
        return jsonify({"ok": True})

    @app.route("/api/mask", methods=["GET", "POST"])
    def api_mask():
        mask_path = Path(config.mask.path)
        if request.method == "GET":
            from aerostab.mask import CameraMask

            m = CameraMask.load(mask_path)
            return jsonify({"cols": m.cols, "rows": m.rows, "cells": m.cells})
        data = request.get_json(force=True)
        from aerostab.mask import CameraMask

        m = CameraMask(config.mask.cols, config.mask.rows)
        m.cells = [bool(x) for x in data.get("cells", [])]
        try:
            m.save(mask_path)
        except PermissionError:
            m.save(Path("mask.json"))
        if runtime:
            runtime.reload_mask()
        return jsonify({"ok": True})

    @app.route("/api/reset_odometry", methods=["POST"])
    def reset_odo():
        if runtime and runtime._odo:
            runtime._odo.reset_origin()
        return jsonify({"ok": True})

    @app.route("/api/rtl_path")
    def rtl_path():
        if runtime and runtime._rtl:
            return jsonify(runtime._rtl.to_dict())
        return jsonify({"recording": False, "points": 0, "path": []})

    @app.route("/video.mjpg")
    def video():
        def generate():
            import time

            while True:
                frame = shared.get_jpeg()
                if frame:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                time.sleep(0.04)

        return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

    return app


def start_web_server(
    shared: SharedState,
    config: AppConfig,
    runtime: Optional[AeroStabRuntime] = None,
    config_path: str = "",
) -> threading.Thread:
    app = create_web_app(shared, config, runtime, config_path)

    def run():
        try:
            from waitress import serve

            serve(app, host=config.web.host, port=config.web.port, threads=4)
        except ImportError:
            app.run(host=config.web.host, port=config.web.port, threaded=True, use_reloader=False)

    thread = threading.Thread(target=run, daemon=True, name="aerostab-web")
    thread.start()
    return thread
