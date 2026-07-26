"""Tests for the CameraModel (Task 3.4).

`CameraModel` holds the fixed per-camera config the geometry needs: intrinsics K,
distortion, and the boresight `R_body_cam` (the fixed O4 mount rotation, DESIGN.md §3.3).
It is loadable from config and its boresight is a proper rotation (orthonormal, det +1).
The two reference mounts (nadir, forward) are verified against the analytic derivation.
"""

from __future__ import annotations

import numpy as np
import pytest

from hades.locate.camera_model import CameraModel


def test_camera_model_holds_intrinsics():
    cam = CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=540.0, mount="nadir")
    assert cam.fx == 1000.0
    assert cam.cy == 540.0
    K = cam.K
    assert K.shape == (3, 3)
    assert K[0, 0] == 1000.0  # fx
    assert K[1, 2] == 540.0  # cy
    assert K[2, 2] == 1.0


def test_boresight_is_proper_rotation():
    cam = CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=960.0, mount="nadir")
    R = cam.R_body_cam
    assert R.shape == (3, 3)
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-12)  # orthonormal
    assert np.isclose(np.linalg.det(R), 1.0)  # proper (det +1)


def test_nadir_mount_optical_z_maps_to_body_down():
    # Optical +z (into scene) → body +z (FRD down) for the nadir mount (analytic spec).
    cam = CameraModel(fx=1.0, fy=1.0, cx=0.0, cy=0.0, mount="nadir")
    optical_z = np.array([0.0, 0.0, 1.0])
    body = cam.R_body_cam @ optical_z
    assert np.allclose(body, [0.0, 0.0, 1.0])


def test_forward_mount_optical_z_maps_to_body_forward():
    # Optical +z → body +x (FRD forward) for the forward mount.
    cam = CameraModel(fx=1.0, fy=1.0, cx=0.0, cy=0.0, mount="forward")
    optical_z = np.array([0.0, 0.0, 1.0])
    body = cam.R_body_cam @ optical_z
    assert np.allclose(body, [1.0, 0.0, 0.0])


def test_unknown_mount_rejected():
    with pytest.raises((ValueError, KeyError)):
        CameraModel(fx=1.0, fy=1.0, cx=0.0, cy=0.0, mount="sideways")


def test_ray_cam_is_unprojected_pixel():
    # K⁻¹·pixel yields the optical-frame ray [(u−cx)/fx, (v−cy)/fy, 1] (DESIGN.md §3.3).
    cam = CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=960.0, mount="nadir")
    ray = cam.ray_cam(u_px=960.0 + 100.0, v_px=960.0)
    assert np.allclose(ray, [0.1, 0.0, 1.0])
