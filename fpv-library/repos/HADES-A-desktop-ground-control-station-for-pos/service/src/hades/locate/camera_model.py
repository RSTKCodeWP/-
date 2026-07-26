"""CameraModel — fixed per-camera config the ray→ground geometry consumes (Task 3.4).

Holds intrinsics `K`, distortion, and the boresight `R_body_cam` (CAMERA-OPTICAL →
BODY-FRD, DESIGN.md §3.3). For the O4's fixed (no-gimbal) mount the boresight is a full
axis permutation, NOT near-identity — the camera is hard-mounted, so camera pitch = fixed
mount angle + airframe pitch. Two reference mounts are provided and verified against the
analytic derivation:

- ``nadir``: optical axis straight DOWN. optical +z → body +z (down), +x → +y (right),
  +y (image-down) → body −x (backward), so top-of-image = forward/North.
- ``forward``: optical axis straight FORWARD. optical +z → body +x (forward).

The optical-frame ray for a pixel is ``K⁻¹·pixel = [(u−cx)/fx, (v−cy)/fy, 1]`` (+z into
the scene), per §3.3. Distortion is undistorted before forming the ray; v1 fixtures are
pinhole (k=0) so undistortion is identity until a calibrated O4 lens model lands.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Boresight matrices (CAMERA-OPTICAL → BODY-FRD), each orthonormal with det +1. Columns
# are the images of optical (+x, +y, +z). Verified against the independent derivation.
_R_BODY_CAM_NADIR = np.array(
    [
        [0.0, -1.0, 0.0],  # optical +x → body +y (right); +y → body −x (back); +z → +z (down)
        [1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
)
_R_BODY_CAM_FORWARD = np.array(
    [
        [0.0, 0.0, 1.0],  # optical +z → body +x (forward); +x → +y (right); +y → +z (down)
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ]
)
_MOUNTS = {"nadir": _R_BODY_CAM_NADIR, "forward": _R_BODY_CAM_FORWARD}


@dataclass(frozen=True)
class CameraModel:
    """Intrinsics + boresight for the fixed O4 mount. Loadable from config.

    Args:
        fx, fy: focal lengths in pixels.
        cx, cy: principal point in pixels.
        mount: ``"nadir"`` or ``"forward"`` — selects the fixed boresight `R_body_cam`.
        dist: radial/tangential distortion coeffs (OpenCV order); empty ⇒ pinhole.
    """

    fx: float
    fy: float
    cx: float
    cy: float
    mount: str = "nadir"
    dist: tuple[float, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.mount not in _MOUNTS:
            raise ValueError(
                f"unknown mount {self.mount!r}; expected one of {sorted(_MOUNTS)}"
            )

    @property
    def K(self) -> np.ndarray:
        """The 3×3 intrinsic matrix."""
        return np.array(
            [[self.fx, 0.0, self.cx], [0.0, self.fy, self.cy], [0.0, 0.0, 1.0]]
        )

    @property
    def R_body_cam(self) -> np.ndarray:
        """Boresight rotation CAMERA-OPTICAL → BODY-FRD for the configured mount."""
        return _MOUNTS[self.mount].copy()

    def ray_cam(self, u_px: float, v_px: float) -> np.ndarray:
        """Optical-frame ray for a pixel: ``[(u−cx)/fx, (v−cy)/fy, 1]`` (+z into scene).

        Distortion is removed first (identity for the pinhole v1 fixtures). The ray is
        unnormalized — magnitude is irrelevant to the ground intersection.
        """
        u_u, v_u = self._undistort(u_px, v_px)
        return np.array([(u_u - self.cx) / self.fx, (v_u - self.cy) / self.fy, 1.0])

    def _undistort(self, u_px: float, v_px: float) -> tuple[float, float]:
        # v1 fixtures are pinhole; a calibrated O4 lens model plugs in here later
        # (cv2.undistortPoints) without changing any caller.
        if not self.dist:
            return u_px, v_px
        import cv2  # lazy: only the distorted path needs opencv here

        pts = np.array([[[u_px, v_px]]], dtype=np.float64)
        undist = cv2.undistortPoints(pts, self.K, np.array(self.dist), P=self.K)
        return float(undist[0, 0, 0]), float(undist[0, 0, 1])
