"""Camera geometry — pixel ↔ body-frame bearing conversion.

FRAME AND SIGN CONVENTIONS
---------------------------
Image coordinates
    * Origin at the **top-left** corner of the sensor.
    * x increases to the **right** (column index).
    * y increases **downward** (row index) — standard computer-vision convention.

Body-frame bearing (az, el)
    * **Azimuth (az)**: angle in the horizontal (X-Z) body plane.
      Positive az = target is to the RIGHT of the boresight.
      Convention: az = atan2(px - cx, f_px)
      Because x increases right, (px - cx) > 0 means right → positive az.
    * **Elevation (el)**: angle in the vertical (Y-Z) body plane.
      Positive el = target is ABOVE the boresight.
      Because y increases DOWNWARD, (py - cy) > 0 means the pixel is below
      the centre → we negate to get positive-el-is-up:
          el = atan2(-(py - cy), f_px)

CRITICAL SIGN NOTE
    Negating (py - cy) in the elevation formula means:
        - A pixel ABOVE the image centre (py < cy)  →  el > 0  (up)   ✓
        - A pixel BELOW the image centre (py > cy)  →  el < 0  (down) ✓
    Getting this wrong would silently invert the el-axis and cause guidance to
    fly the interceptor in the wrong pitch direction.

FOCAL LENGTH FROM HFOV
    f_px = (width / 2) / tan(HFOV / 2)
    For a Boson 640 with 24 mm EFL and 12 µm pixel pitch:
        HFOV ≈ 2·atan(W·pitch/EFL) = 2·atan(640·12e-3/24) ≈ 17.1°
        f_px ≈ (640/2) / tan(8.55°) ≈ 2130 px

Design reference: Block-03 §3.2 «dx_px ≈ −f·ω_y·dt, dy_px ≈ −f·ω_x·dt»
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CameraIntrinsics:
    """Pinhole camera intrinsic parameters.

    Attributes
    ----------
    f_px:
        Focal length in pixels.  Same value used for both axes (square pixels
        assumed).  See module docstring for the HFOV→f_px helper.
    cx:
        Principal-point x coordinate (pixels).  Typically width / 2.
    cy:
        Principal-point y coordinate (pixels).  Typically height / 2.
    width:
        Sensor width in pixels.
    height:
        Sensor height in pixels.
    """

    f_px: float
    cx: float
    cy: float
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.f_px <= 0.0:
            raise ValueError(f"f_px must be positive, got {self.f_px}")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive integers")


def focal_length_from_hfov(hfov_deg: float, width_px: int) -> float:
    """Compute focal length in pixels from horizontal FOV and image width.

    Parameters
    ----------
    hfov_deg:
        Horizontal field of view in degrees.
    width_px:
        Sensor width in pixels.

    Returns
    -------
    float
        Focal length in pixels.

    Examples
    --------
    >>> focal_length_from_hfov(17.1, 640)
    2130.2...
    """
    if hfov_deg <= 0.0 or hfov_deg >= 180.0:
        raise ValueError(f"hfov_deg must be in (0, 180), got {hfov_deg}")
    return (width_px / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)


def boson_640_24mm_intrinsics() -> CameraIntrinsics:
    """Return nominal intrinsics for FLIR Boson 640 with 24 mm EFL.

    Pixel pitch = 12 µm, HFOV ≈ 17.1°, f_px ≈ 2130 px.

    NOTE: this is the NARROW telephoto lens.  It is NOT the lens actually
    fielded on the Block-3 interceptor.  The fielded camera is the Foxeer
    FT640 V2 (see ``ft640_intrinsics`` below); use that for the closed-loop
    sim and the DETECT-envelope budget.  This Boson model is retained for the
    legacy 24 mm bench / regression tests only.
    """
    width, height = 640, 512
    f_px = focal_length_from_hfov(17.1, width)
    return CameraIntrinsics(
        f_px=f_px,
        cx=width / 2.0,
        cy=height / 2.0,
        width=width,
        height=height,
    )


def ft640_intrinsics(
    width: int = 640,
    height: int = 512,
    hfov_deg: float = 48.7,
) -> CameraIntrinsics:
    """Return intrinsics for the FOXEER FT640 V2 wide FPV thermal seeker.

    This is the camera ACTUALLY fielded on the Block-3 interceptor and the
    one the Johnson DETECT-envelope budget (115–190 m) is computed against.

    Geometry (FT640 V2, 640×512 sensor):
        HFOV = 48.7°  (VFOV ≈ 39.8° at 4:5 / 640×512)
        f_px = (640/2) / tan(radians(48.7)/2) ≈ 707 px
        IFOV ≈ 1 / f_px ≈ 1.41 mrad/px  (≈ the quoted 1.33 mrad class)

    Compared with the narrow Boson 24 mm model (f_px ≈ 2128, 0.47 mrad/px),
    the FT640 has ~3.0× coarser angular resolution but a 2.85× wider FOV —
    which is what keeps a hard-maneuvering target on-sensor through terminal.

    Square pixels (single f_px), centred principal point, zero distortion —
    matching the ``CameraIntrinsics`` pinhole model.  Mirrors the hardware-path
    ``fpv_ai.sensor.thermal_capture.ft640_intrinsics`` so sim and bench agree.
    """
    f_px = focal_length_from_hfov(hfov_deg, width)
    return CameraIntrinsics(
        f_px=f_px,
        cx=width / 2.0,
        cy=height / 2.0,
        width=width,
        height=height,
    )


def pixel_to_bearing(
    px: float,
    py: float,
    intrinsics: CameraIntrinsics,
) -> tuple[float, float]:
    """Convert a pixel centroid to body-frame bearing (azimuth, elevation).

    Sign convention (see module docstring for full derivation):
        az = atan2(px - cx,  f_px)   — right is positive
        el = atan2(-(py - cy), f_px) — UP is positive (negates image-down y)

    Parameters
    ----------
    px, py:
        Sub-pixel centroid in image coordinates (origin = top-left, x right,
        y downward).
    intrinsics:
        Camera intrinsic parameters.

    Returns
    -------
    (az_rad, el_rad)
        Body-frame azimuth and elevation in radians.  Both are in the range
        (-π/2, π/2) for targets within the FOV.
    """
    dx = px - intrinsics.cx
    dy = py - intrinsics.cy  # positive = below centre (image convention)
    az = math.atan2(dx, intrinsics.f_px)
    el = math.atan2(-dy, intrinsics.f_px)  # negate: below-centre → negative el
    return az, el


def bearing_to_pixel(
    az_rad: float,
    el_rad: float,
    intrinsics: CameraIntrinsics,
) -> tuple[float, float]:
    """Inverse of ``pixel_to_bearing``: body-frame bearing → pixel centroid.

    Uses the small-angle-exact pinhole projection (tan, not sin).

    Parameters
    ----------
    az_rad, el_rad:
        Body-frame azimuth and elevation in radians.

    Returns
    -------
    (px, py)
        Pixel coordinates.  May be outside sensor bounds for off-axis directions.
    """
    f = intrinsics.f_px
    dx = math.tan(az_rad) * f
    dy = -math.tan(el_rad) * f  # negate: positive el (up) → negative dy (above centre)
    return intrinsics.cx + dx, intrinsics.cy + dy
