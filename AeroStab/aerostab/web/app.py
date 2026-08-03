"""Flask application factory."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from flask import Flask, send_from_directory

from aerostab.web.routes import register_routes

STATIC_DIR = Path(__file__).resolve().parent / "static"
DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"


def create_web_app(shared, config, runtime=None, config_path: str = "") -> Flask:
    app = Flask(__name__, static_folder=str(STATIC_DIR))

    @app.route("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.route("/static/<path:filename>")
    def static_files(filename):
        return send_from_directory(STATIC_DIR, filename)

    register_routes(app, shared, config, runtime, config_path, DOCS_DIR)
    return app


def start_web_server(shared, config, runtime=None, config_path: str = "") -> threading.Thread:
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
