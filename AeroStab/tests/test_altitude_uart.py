"""UART auto-detect and rangefinder altitude path."""

import socket
import time
from pathlib import Path

from aerostab.config import load_config
from aerostab.runtime import AeroStabRuntime
from aerostab.serial_detect import resolve_mavlink_port
from aerostab.sitl.mock_fc import MockFlightController
from aerostab.state import SharedState


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_resolve_tcp_passthrough():
    assert resolve_mavlink_port("tcp:127.0.0.1:5760") == "tcp:127.0.0.1:5760"


def test_rangefinder_altitude_preferred():
    port = _free_port()
    fc = MockFlightController(port=port, altitude_m=3.5, send_rangefinder=True)
    fc.start()
    cfg = load_config(str(Path(__file__).resolve().parents[1] / "config" / "sitl.yaml"))
    cfg.mavlink.port = f"tcp:127.0.0.1:{port}"
    cfg.altitude.source = "auto"
    cfg.altitude.default_m = 1.0
    cfg.web.enabled = False
    shared = SharedState()
    rt = AeroStabRuntime(cfg, shared)
    rt.start()
    fc.wait_client(timeout_s=15)
    for _ in range(50):
        rt.tick()
        time.sleep(0.03)
    snap = shared.snapshot()
    rt.stop()
    fc.stop()
    assert snap["mavlink_connected"]
    assert snap["altitude_source"] == "rangefinder"
    assert abs(snap["altitude_m"] - 3.5) < 0.2
