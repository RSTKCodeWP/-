"""Tests for AeroStab."""

import time
from pathlib import Path

import numpy as np

from aerostab.config import load_config, save_config
from aerostab.estimator import OdometryIntegrator, OpticalFlowEstimator, FlowResult
from aerostab.camera import SyntheticCamera, CameraConfig
from aerostab.mask import CameraMask
from aerostab.gps_fusion import GpsFusion, GpsFix
from aerostab.health import evaluate


def test_config_roundtrip(tmp_path):
    cfg = load_config()
    p = tmp_path / "cfg.yaml"
    save_config(cfg, str(p))
    cfg2 = load_config(str(p))
    assert cfg2.camera.fov_deg == cfg.camera.fov_deg


def test_mask_save_load(tmp_path):
    m = CameraMask(4, 3)
    m.set_cell(1, 1, True)
    p = tmp_path / "mask.json"
    m.save(p)
    m2 = CameraMask.load(p)
    assert m2.cells[1 * 4 + 1]


def test_mask_opencv():
    m = CameraMask(8, 6)
    m.set_cell(0, 0, True)
    mask = m.build_opencv_mask(640, 480)
    assert mask[0, 0] == 0
    assert mask[100, 100] == 255


def test_optical_flow_motion():
    cam_cfg = CameraConfig(width=320, height=240, fps=20)
    flow_est = OpticalFlowEstimator(cam_cfg, load_config().estimator)
    cam = SyntheticCamera(cam_cfg)
    cam.start()
    dt = 1 / 20.0
    qualities = []
    for _ in range(50):
        ok, gray = cam.read_gray()
        assert ok
        r = flow_est.update(gray, 2.0, dt)
        qualities.append(r.quality)
    assert max(qualities) > 0.2


def test_gps_fusion_origin():
    gf = GpsFusion(enabled=True, wait_timeout_s=0.1, default_lat=50.0, default_lon=30.0)
    gf.ingest_gps(GpsFix(50.001, 30.001, 100, 3, 10, time.monotonic()))
    assert gf.nav_ready()


def test_health_evaluate():
    cfg = load_config()
    r = evaluate(
        cfg,
        camera_ok=True,
        mavlink_ok=True,
        quality=0.5,
        track_points=20,
        fps=15,
        nav_ready=True,
        mask_fill_ratio=0.1,
        simulate=True,
        heartbeat_age_s=0.1,
        altitude_m=2.0,
        holding=False,
        nav_valid=True,
    )
    assert r.ready
