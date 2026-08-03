"""Flask web dashboard (:8080)."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from flask import Flask, Response, jsonify, render_template_string

if TYPE_CHECKING:
    from aerostab.config import AppConfig
    from aerostab.state import SharedState

INDEX_HTML = """<!DOCTYPE html>
<html lang="uk">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>AeroStab</title>
  <style>
    :root { --bg:#0f1419; --card:#1a2332; --accent:#3d9eff; --text:#e8eef5; --muted:#8b9cb3; }
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 1rem; }
    h1 { font-size: 1.4rem; margin: 0 0 1rem; }
    .grid { display: grid; grid-template-columns: 1fr 280px; gap: 1rem; }
    @media (max-width: 800px) { .grid { grid-template-columns: 1fr; } }
    .card { background: var(--card); border-radius: 10px; padding: 1rem; }
    img { width: 100%; border-radius: 8px; background: #000; }
    .stat { display: flex; justify-content: space-between; padding: 0.35rem 0; border-bottom: 1px solid #2a3544; font-size: 0.9rem; }
    .stat span:last-child { color: var(--accent); font-variant-numeric: tabular-nums; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; }
    .ok { background: #1a4d2e; color: #6fcf97; }
    .warn { background: #4d3a1a; color: #f2c94c; }
    footer { margin-top: 1rem; color: var(--muted); font-size: 0.8rem; }
  </style>
</head>
<body>
  <h1>AeroStab <span id="mode" class="badge warn">...</span></h1>
  <div class="grid">
    <div class="card">
      <img src="/video.mjpg" alt="camera"/>
    </div>
    <div class="card">
      <div class="stat"><span>FPS</span><span id="fps">-</span></div>
      <div class="stat"><span>MAVLink</span><span id="mav">-</span></div>
      <div class="stat"><span>Висота</span><span id="alt">-</span></div>
      <div class="stat"><span>Vx / Vy</span><span id="vel">-</span></div>
      <div class="stat"><span>Позиція X/Y</span><span id="pos">-</span></div>
      <div class="stat"><span>Якість</span><span id="qual">-</span></div>
      <div class="stat"><span>Точки</span><span id="pts">-</span></div>
      <div class="stat"><span>Uptime</span><span id="up">-</span></div>
    </div>
  </div>
  <footer>Pi Zero 2W + Frank-S01 (OV5647) · ArduPilot ExternalNav</footer>
  <script>
    async function poll() {
      try {
        const r = await fetch('/api/status');
        const s = await r.json();
        document.getElementById('fps').textContent = s.fps;
        document.getElementById('mav').textContent = s.mavlink_connected ? 'OK' : 'OFF';
        document.getElementById('alt').textContent = s.altitude_m + ' m';
        document.getElementById('vel').textContent = s.vx_m_s + ' / ' + s.vy_m_s + ' m/s';
        document.getElementById('pos').textContent = s.x_m + ' / ' + s.y_m + ' m';
        document.getElementById('qual').textContent = s.quality;
        document.getElementById('pts').textContent = s.track_points;
        document.getElementById('up').textContent = s.uptime_s + ' s';
        const m = document.getElementById('mode');
        m.textContent = s.simulate ? 'SIM' : 'LIVE';
        m.className = 'badge ' + (s.simulate ? 'warn' : 'ok');
      } catch (e) {}
    }
    setInterval(poll, 500);
    poll();
  </script>
</body>
</html>"""


def create_web_app(shared: SharedState, config: AppConfig) -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template_string(INDEX_HTML)

    @app.route("/api/status")
    def status():
        return jsonify(shared.snapshot())

    @app.route("/video.mjpg")
    def video():
        def generate():
            import time

            while True:
                frame = shared.get_jpeg()
                if frame:
                    yield (
                        b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                    )
                time.sleep(0.05)

        return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

    return app


def start_web_server(shared: SharedState, config: AppConfig) -> threading.Thread:
    app = create_web_app(shared, config)
    thread = threading.Thread(
        target=lambda: app.run(
            host=config.web.host,
            port=config.web.port,
            threaded=True,
            use_reloader=False,
        ),
        daemon=True,
        name="aerostab-web",
    )
    thread.start()
    return thread
