"""MAVLink arm/disarm/calibrate command tests."""

import socket
import time
from pathlib import Path

import pytest

from aerostab.config import load_config
from aerostab.mavlink_bridge import MavlinkBridge
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


def test_mavlink_arm_disarm(sitl_port):
    port, fc = sitl_port
    from aerostab.config import MavlinkConfig

    bridge = MavlinkBridge(MavlinkConfig(enabled=True, port=f"tcp:127.0.0.1:{port}", baud=115200))
    bridge.connect()
    fc.wait_client(timeout_s=10)

    ok, msg = bridge.arm(force=True)
    assert ok, msg
    time.sleep(0.3)
    bridge.poll()
    assert bridge.armed

    ok, msg = bridge.disarm()
    assert ok, msg
    time.sleep(0.3)
    bridge.poll()
    assert not bridge.armed
    bridge.close()


def test_runtime_arm_requires_flight_ok(sitl_port):
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
    fc.wait_client(timeout_s=10)

    for _ in range(30):
        rt.tick()
        time.sleep(1.0 / config.runtime.control_hz)

    ok, msg = rt.mavlink_arm(force=True)
    assert ok, msg
    rt.stop()


def test_camstate_api_shape():
    cfg_path = Path(__file__).resolve().parents[1] / "config" / "sitl.yaml"
    config = load_config(str(cfg_path))
    config.runtime.simulate = True
    rt = AeroStabRuntime(config, SharedState())
    state = rt.camera_state()
    assert "cameras" in state
    assert "fov" in state
    assert "rotation" in state
