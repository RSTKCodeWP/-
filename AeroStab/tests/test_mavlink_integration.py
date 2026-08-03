"""MAVLink integration tests with mock flight controller."""

import socket
import time
from pathlib import Path

import pytest

from aerostab.config import load_config
from aerostab.runtime import AeroStabRuntime
from aerostab.sitl.mock_fc import MockFlightController
from aerostab.state import SharedState


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def sitl_port():
    port = _free_port()
    fc = MockFlightController(port=port)
    fc.start()
    yield port, fc
    fc.stop()


def test_mock_fc_heartbeat(sitl_port):
    port, fc = sitl_port
    from pymavlink import mavutil

    conn = mavutil.mavlink_connection(f"tcp:127.0.0.1:{port}")
    conn.wait_heartbeat(timeout=10)
    fc.wait_client(timeout_s=10)
    time.sleep(0.5)
    assert fc.stats.client_connected
    assert fc.stats.heartbeat_count > 0
    conn.close()


def test_aerostab_mavlink_hil(sitl_port):
    port, fc = sitl_port
    cfg_path = Path(__file__).resolve().parents[1] / "config" / "sitl.yaml"
    config = load_config(str(cfg_path))
    config.mavlink.port = f"tcp:127.0.0.1:{port}"
    config.runtime.simulate = True
    config.web.enabled = False
    config.runtime.log_csv = False

    shared = SharedState()
    rt = AeroStabRuntime(config, shared)
    rt.start()
    fc.wait_client(timeout_s=15.0)

    deadline = time.monotonic() + 6.0
    try:
        while time.monotonic() < deadline:
            rt.tick()
            time.sleep(1.0 / config.runtime.control_hz)
    finally:
        rt.stop()

    snap = shared.snapshot()
    assert snap["mavlink_connected"], "expected MAVLink heartbeat from mock FC"
    assert snap["mavlink_messages"] > 0, "AeroStab should send odometry"
    assert fc.stats.vision_count > 0, "mock FC should receive VISION_POSITION_ESTIMATE"
    assert snap["track_points"] > 0
    assert snap["fps"] > 5


def test_gps_fusion_nav_ready(sitl_port):
    port, fc = sitl_port
    cfg_path = Path(__file__).resolve().parents[1] / "config" / "sitl.yaml"
    config = load_config(str(cfg_path))
    config.mavlink.port = f"tcp:127.0.0.1:{port}"
    config.gps_fusion.enabled = True
    config.gps_fusion.wait_timeout_s = 1.0

    shared = SharedState()
    rt = AeroStabRuntime(config, shared)
    rt.start()
    fc.wait_client(timeout_s=15.0)
    for _ in range(40):
        rt.tick()
        time.sleep(0.05)
    rt.stop()

    snap = shared.snapshot()
    assert snap["nav_ready"]
    assert snap["gps_fix"] >= 3
