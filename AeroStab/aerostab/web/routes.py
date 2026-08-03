"""Flask route blueprints."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from flask import Blueprint, Response, jsonify, request

from aerostab.web.config_schema import CONFIG_SCHEMA, SECTION_LABELS
from aerostab.web.config_service import apply_config_patch, apply_runtime_hot_reload, config_to_dict

if TYPE_CHECKING:
    from aerostab.config import AppConfig
    from aerostab.runtime import AeroStabRuntime
    from aerostab.state import SharedState


def register_routes(
    app,
    shared: "SharedState",
    config: "AppConfig",
    runtime: Optional["AeroStabRuntime"],
    config_path: str,
    docs_dir: Path,
) -> None:
    bp = Blueprint("api", __name__)

    @bp.route("/api/status")
    def status():
        return jsonify(shared.snapshot())

    @bp.route("/api/config/schema")
    def config_schema():
        return jsonify({"sections": SECTION_LABELS, "fields": CONFIG_SCHEMA})

    @bp.route("/api/config", methods=["GET", "POST"])
    def api_config():
        if request.method == "GET":
            return jsonify(config_to_dict(config))

        patch = request.get_json(force=True)
        if not isinstance(patch, dict):
            return jsonify({"ok": False, "error": "expected object"}), 400
        changed = apply_config_patch(config, patch)
        if config_path:
            from aerostab.config import save_config

            save_config(config, config_path)
        if runtime:
            apply_runtime_hot_reload(runtime, changed)
        return jsonify({"ok": True, "changed": changed})

    @bp.route("/api/mask", methods=["GET", "POST"])
    def api_mask():
        from aerostab.mask import CameraMask

        mask_path = Path(config.mask.path)
        if request.method == "GET":
            m = CameraMask.load(mask_path)
            return jsonify({"cols": m.cols, "rows": m.rows, "cells": m.cells})
        data = request.get_json(force=True)
        m = CameraMask(config.mask.cols, config.mask.rows)
        m.cells = [bool(x) for x in data.get("cells", [])]
        try:
            m.save(mask_path)
        except PermissionError:
            m.save(Path("mask.json"))
        if runtime:
            runtime.reload_mask()
        return jsonify({"ok": True})

    @bp.route("/api/reset_odometry", methods=["POST"])
    def reset_odo():
        if runtime and runtime._odo:
            runtime._odo.reset_origin()
        return jsonify({"ok": True})

    @bp.route("/api/rtl_path")
    def rtl_path():
        if runtime and runtime._rtl:
            return jsonify(runtime._rtl.to_dict())
        return jsonify({"recording": False, "points": 0, "path": []})

    DOC_TITLES = {
        "FLASH": "Запис SD-карти",
        "INSTALL": "Встановлення на Pi",
        "WIRE": "Проводка та ArduPilot",
        "SETTINGS": "Довідник налаштувань",
        "FLIGHT": "Картка польоту",
    }

    @bp.route("/api/docs")
    def docs_list():
        items = []
        if docs_dir.is_dir():
            for p in sorted(docs_dir.glob("*.md")):
                stem = p.stem.upper()
                items.append({"id": p.stem, "title": DOC_TITLES.get(stem, p.stem.replace("-", " ").title())})
        return jsonify(items)

    @bp.route("/api/docs/<doc_id>")
    def docs_get(doc_id: str):
        path = docs_dir / f"{doc_id}.md"
        if not path.exists():
            return jsonify({"error": "not found"}), 404
        return jsonify({"id": doc_id, "markdown": path.read_text(encoding="utf-8")})

    @bp.route("/api/serial_ports")
    def serial_ports():
        from aerostab.serial_detect import list_serial_candidates

        return jsonify({"ports": list_serial_candidates(), "configured": config.mavlink.port})

    @bp.route("/video.mjpg")
    def video():
        def generate():
            import time

            while True:
                frame = shared.get_jpeg()
                if frame:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                time.sleep(0.04)

        return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

    app.register_blueprint(bp)
