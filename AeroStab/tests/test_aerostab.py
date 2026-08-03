"""Tests for AeroStab (no hardware required)."""

import time

import numpy as np

from aerostab.config import CameraConfig, EstimatorConfig, load_config
from aerostab.estimator import OpticalFlowEstimator, OdometryIntegrator
from aerostab.camera import SyntheticCamera


def test_config_loads():
    cfg = load_config()
    assert cfg.camera.fov_deg == 72.4
    assert cfg.mavlink.baud == 230400


def test_synthetic_camera_frames():
    cam_cfg = CameraConfig(width=320, height=240, fps=20)
    cam = SyntheticCamera(cam_cfg)
    cam.start()
    ok, gray = cam.read_gray()
    assert ok and gray is not None
    assert gray.shape == (240, 320)


def test_optical_flow_detects_motion():
    cam_cfg = CameraConfig(width=320, height=240, fps=20, fov_deg=72.4)
    est_cfg = EstimatorConfig(max_corners=40, min_track_points=5)
    flow_est = OpticalFlowEstimator(cam_cfg, est_cfg)
    cam = SyntheticCamera(cam_cfg)
    cam.start()

    dt = 1 / 20.0
    velocities = []
    for _ in range(40):
        ok, gray = cam.read_gray()
        assert ok
        r = flow_est.update(gray, altitude_m=2.0, dt=dt)
        velocities.append((r.vx_m_s, r.vy_m_s, r.quality))
        time.sleep(0.001)

    # Synthetic texture moves — expect non-zero velocity or decent quality eventually
    max_q = max(v[2] for v in velocities)
    assert max_q > 0.1


def test_odometry_integrates():
    odo = OdometryIntegrator(max_speed=10.0, position_lpf=0.2)
    from aerostab.estimator import FlowResult

    f = FlowResult(vx_m_s=1.0, vy_m_s=0.5, quality=0.8, n_points=20, flow_x_px=1, flow_y_px=1)
    s = odo.update(f, dt=0.1)
    assert s.x_m != 0 or s.y_m != 0
