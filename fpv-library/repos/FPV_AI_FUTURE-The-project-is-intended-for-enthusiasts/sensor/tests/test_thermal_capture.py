"""Tests for thermal capture (Block-3 hardware phase). Hardware-free: SyntheticSource.

The key test proves the 8-bit AGC analog-camera path (FT640 class) actually feeds the S1
detector and yields a lock + guidance -- i.e. our relative-threshold detector tolerates the
loss of 16-bit radiometry.
"""

from __future__ import annotations

import numpy as np

from fpv.seeker.thermal_sim import ThermalSceneConfig, ThermalSimulator
from fpv.guidance.pipeline import SeekerGuidancePipeline

from fpv_ai.sensor.thermal_capture import (
    CaptureConfig,
    SyntheticSource,
    ThermalCapture,
    ft640_intrinsics,
)

DT = 1.0 / 60.0


def _agc_8bit(frame_u16: np.ndarray) -> np.ndarray:
    """Mimic the camera's per-frame 8-bit AGC contrast stretch."""
    f = frame_u16.astype(np.float64)
    lo, hi = f.min(), f.max()
    if hi <= lo:
        return np.zeros_like(f, dtype=np.uint8)
    return (255.0 * (f - lo) / (hi - lo)).astype(np.uint8)


def test_8bit_agc_camera_path_feeds_detector_and_locks():
    sim = ThermalSimulator(ThermalSceneConfig(ffc_freeze_interval=0, n_stars=3))
    frames8 = [_agc_8bit(frame) for frame, _gt in sim.generate(10)]   # 8-bit, like the FT640 analog feed
    cap = ThermalCapture(SyntheticSource(frames8))
    pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics())

    commands = 0
    i = 0
    while True:
        f = cap.frame_u16()
        if f is None:
            break
        assert f.dtype == np.uint16 and f.shape == (512, 640)
        out = pipe.step(now=i * DT, frame_u16=f, gyro_omega_xyz=(0.0, 0.0, 0.0), dt=DT)
        commands += int(out.command is not None)
        i += 1
    assert commands >= 1            # the 8-bit analog path produced real guidance from pixels


def test_ft640_intrinsics_wide_fov():
    intr = ft640_intrinsics()
    assert intr.width == 640 and intr.height == 512
    # wide FOV -> much shorter focal length than the narrow Boson 24mm (~2130 px)
    assert intr.f_px < 800.0


def test_roi_crop_and_grayscale():
    raw = np.zeros((576, 720, 3), dtype=np.uint8)   # CVBS-grabber-like BGR frame
    raw[300:340, 400:440, :] = 200                  # a hot patch inside the active area
    cap = ThermalCapture(SyntheticSource([raw]),
                         CaptureConfig(roi=(380, 280, 80, 80), out_width=80, out_height=80))
    g = cap.frame_u16()
    assert g.shape == (80, 80) and g.dtype == np.uint16
    assert g.max() > 100                            # the hot patch survived crop+grayscale


def test_invert_palette():
    raw = np.full((512, 640), 240, dtype=np.uint8)
    raw[100:110, 100:110] = 10                       # black-hot: target is DARK
    cap = ThermalCapture(SyntheticSource([raw]), CaptureConfig(invert=True))
    g = cap.frame_u16()
    assert g[105, 105] > g[0, 0]                      # after invert the target is BRIGHT


def test_resize_fallback_without_cv2():
    raw = np.zeros((576, 720), dtype=np.uint8)
    raw[288, 360] = 255
    cap = ThermalCapture(SyntheticSource([raw]), CaptureConfig(out_width=640, out_height=512))
    g = cap.frame_u16()
    assert g.shape == (512, 640)


def test_source_exhaustion_returns_none():
    cap = ThermalCapture(SyntheticSource([np.zeros((512, 640), np.uint8)]))
    assert cap.frame_u16() is not None
    assert cap.frame_u16() is None
