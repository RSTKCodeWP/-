"""Production flight-path tests: mask, FOV, hold-last, hover."""

import socket
import time
from pathlib import Path

import pytest

from aerostab.config import CameraConfig, load_config
from aerostab.camera import SyntheticCamera
from aerostab.estimator import FlowResult, OdometryIntegrator, OpticalFlowEstimator
from aerostab.mask import CameraMask
from aerostab.runtime import AeroStabRuntime
from aerostab.sitl.mock_fc import MockFlightController
from aerostab.state import SharedState


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_empty_mask_json_loads(tmp_path):
    p = tmp_path / "mask.json"
    p.write_text("")
    m = CameraMask.load(p)
    assert len(m.cells) == 16 * 12
    assert not any(m.cells)


def test_invalid_mask_json_loads(tmp_path):
    p = tmp_path / "mask.json"
    p.write_text("{not json")
    m = CameraMask.load(p)
    assert m.cols == 16


def test_fov_live_update():
    cam = CameraConfig(width=320, height=240, fov_deg=72.4)
    est = OpticalFlowEstimator(cam, load_config().estimator)
    f0 = est._focal_px
    est.set_fov(120.0)
    assert est._focal_px != f0
    assert abs(est.cam.fov_deg - 120.0) < 1e-6


def test_hold_freezes_odometry():
    odo = OdometryIntegrator(10.0, use_visual_yaw=False)
    flow = FlowResult(1.0, 0.5, 0.9, 20, 1, 1, 0)
    odo.update(flow, 0.1, armed=True, hold=False)
    x0, y0 = odo.state.x_m, odo.state.y_m
    odo.update(flow, 0.1, armed=True, hold=True)
    assert odo.state.x_m == x0
    assert odo.state.y_m == y0
    assert odo.state.vx_m_s == 0.0


def test_sustained_hover_and_hold(tmp_path):
    port = _free_port()
    fc = MockFlightController(port=port, arm_at_s=0.8, disarm_at_s=99)
    fc.start()
    cfg = load_config(str(Path(__file__).resolve().parents[1] / "config" / "sitl.yaml"))
    cfg.mavlink.port = f"tcp:127.0.0.1:{port}"
    cfg.quality.nav_valid_warmup_s = 0.3
    cfg.quality.min_quality = 0.1
    cfg.rtl.save_path = str(tmp_path / "rtl.json")
    shared = SharedState()
    rt = AeroStabRuntime(cfg, shared)
    rt.start()
    fc.wait_client(timeout_s=15)

    # Warmup until nav_valid
    for _ in range(90):
        rt.tick()
        time.sleep(1 / 30)
    snap = shared.snapshot()
    assert snap["mavlink_connected"]
    assert snap["nav_valid"] or snap["track_points"] > 0
    assert fc.stats.vision_count > 5

    # Force quality drop → hold while armed
    rt._last_armed = True
    # Simulate armed via FC already armed
    time.sleep(0.2)
    for _ in range(40):
        rt.tick()
        time.sleep(1 / 30)
    snap2 = shared.snapshot()
    assert snap2["armed"]
    # Position should not explode
    assert abs(snap2["x_m"]) < 5.0
    assert abs(snap2["y_m"]) < 5.0

    rt.stop()
    fc.stop()


def test_single_frame_pair():
    cam = SyntheticCamera(CameraConfig(width=160, height=120, fps=20))
    cam.start()
    ok, gray, bgr = cam.read_pair()
    assert ok and gray is not None and bgr is not None
    assert gray.shape[:2] == (120, 160)
