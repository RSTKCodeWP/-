"""Moving-Target Indication (MTI) for look-down -- the master clutter discriminator.

Looking DOWN, a small drone is NOT the brightest thing; it is the thing that moves
INDEPENDENTLY of the ground.  But the ground also moves in the image because the
interceptor moves (ego-motion + parallax).  So:

  1. estimate ego-motion as an image-domain homography (ORB keypoints + RANSAC) -- the
     moving target is a RANSAC outlier, so the homography registers the BACKGROUND;
  2. warp the older frame into the current frame and difference -- the registered
     background cancels, only independently-moving things leave a residual;
  3. do this at TWO intervals (fast Dt and slow Dt) and INTERSECT the masks -- the
     cheapest, highest-leverage filter against single-frame noise and parallax flashes.

A candidate detection survives only if it is BOTH locally salient (top-hat) AND moving
(this mask).  Falls back to identity (raw frame difference) when too few keypoints match
(a textureless night sky), which is the correct behaviour for a near-static look-up scene.

cv2 is lazy-imported; the module degrades to a numpy frame-difference if cv2 is absent.
"""

from __future__ import annotations

from collections import deque

import numpy as np
import numpy.typing as npt
from scipy import ndimage as ndi


def _to_u8(frame_f: npt.NDArray[np.float32]) -> npt.NDArray[np.uint8]:
    """Percentile-normalize to uint8 for feature matching (AGC/scale invariant-ish)."""
    lo = float(np.percentile(frame_f, 1.0))
    hi = float(np.percentile(frame_f, 99.5))
    g = (frame_f - lo) / max(hi - lo, 1.0) * 255.0
    return np.clip(g, 0, 255).astype(np.uint8)


class MotionGate:
    """Maintains a short frame history and produces an ego-compensated motion mask."""

    # Ego-motion is estimated on a downscaled copy of the frames (ORB on a quarter-area
    # image is ~3-4x cheaper) and the homography is rescaled back to full resolution for
    # the final full-res warp.  0.5x => the diff stays full-res; the registration cost
    # (ORB + match + RANSAC), which dominates on the RPi5 (~205 ms/frame), shrinks sharply.
    _REG_SCALE = 0.6

    def __init__(self, *, fast_interval: int = 1, slow_interval: int = 5,
                 diff_k_mad: float = 5.0, min_inliers: int = 25, dilate: int = 2,
                 ransac_reproj_px: float = 3.0, max_shift_frac: float = 0.15) -> None:
        if slow_interval <= fast_interval:
            raise ValueError("slow_interval must exceed fast_interval")
        self._fast = int(fast_interval)
        self._slow = int(slow_interval)
        self._diff_k = float(diff_k_mad)
        self._min_inliers = int(min_inliers)
        self._dilate = int(dilate)
        self._reproj = float(ransac_reproj_px)
        self._max_shift_frac = float(max_shift_frac)
        self._hist: deque[npt.NDArray[np.float32]] = deque(maxlen=self._slow + 1)
        self._orb = None
        self._bf = None

    # ---- public ---------------------------------------------------------------
    def reset(self) -> None:
        """Flush the frame history (call on an FFC event so stale shutter frames are not
        differenced against live frames after recovery)."""
        self._hist.clear()

    def update(self, frame_u16: npt.NDArray[np.uint16]) -> npt.NDArray[np.bool_] | None:
        """Push a frame; return the intersected fast/slow motion mask, or None until warm."""
        f = frame_u16.astype(np.float32)
        self._hist.append(f)
        if len(self._hist) <= self._slow:
            return None
        cur = self._hist[-1]
        fast_prev = self._hist[-1 - self._fast]
        slow_prev = self._hist[-1 - self._slow]
        m_fast = self._motion_mask(cur, fast_prev)
        m_slow = self._motion_mask(cur, slow_prev)
        return m_fast & m_slow

    # ---- internals ------------------------------------------------------------
    def _motion_mask(self, cur: npt.NDArray[np.float32],
                     prev: npt.NDArray[np.float32]) -> npt.NDArray[np.bool_]:
        warped = self._register(prev, cur)
        diff = np.abs(cur - warped)
        med = float(np.median(diff))
        mad = float(np.median(np.abs(diff - med))) * 1.4826 or 1.0
        mask = diff > (med + self._diff_k * mad)
        if self._dilate > 0:
            mask = ndi.binary_dilation(mask, iterations=self._dilate)
        return mask

    def _register(self, prev: npt.NDArray[np.float32],
                  cur: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
        """Warp ``prev`` into ``cur``'s frame via an ORB+RANSAC homography (identity fallback).

        Detection/matching/homography run on a ``_REG_SCALE`` downscale of the frames (ORB on a
        quarter-area image is ~3-4x cheaper -- the registration stage dominates RPi5 latency); the
        small-image homography is rescaled to full resolution, ``H_full = inv(S) @ H_small @ S``
        with ``S = diag([s, s, 1])``, and the final warp stays full-res (the diff is full-res).
        """
        try:
            import cv2  # type: ignore[import]
        except ImportError:
            return prev
        if self._orb is None:
            self._orb = cv2.ORB_create(nfeatures=500)
            self._bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        p8, c8 = _to_u8(prev), _to_u8(cur)
        # Downscale for feature work; INTER_AREA is the correct decimation filter.
        s = self._REG_SCALE
        ps = cv2.resize(p8, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        cs = cv2.resize(c8, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        kp1, des1 = self._orb.detectAndCompute(ps, None)
        kp2, des2 = self._orb.detectAndCompute(cs, None)
        if des1 is None or des2 is None or len(kp1) < self._min_inliers or len(kp2) < self._min_inliers:
            return prev
        matches = self._bf.match(des1, des2)
        if len(matches) < self._min_inliers:
            return prev
        src = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        dst = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
        # RANSAC threshold lives in small-image pixels, so scale the reprojection tolerance too.
        hmat_s, inliers = cv2.findHomography(src, dst, cv2.RANSAC, self._reproj * s)
        if hmat_s is None or inliers is None or int(inliers.sum()) < self._min_inliers:
            return prev
        # Rescale the small-image homography to full resolution: H_full = inv(S) @ H_small @ S.
        # With uniform scale s, inv(S) = diag([1/s, 1/s, 1]).
        s_mat = np.diag([s, s, 1.0]).astype(np.float64)
        s_inv = np.diag([1.0 / s, 1.0 / s, 1.0]).astype(np.float64)
        hmat = s_inv @ hmat_s @ s_mat
        h, w = cur.shape
        # Near-identity guard (review C6): real frame-to-frame ego-motion is a SMALL global
        # shift; a homography that warps the frame CORNERS by more than a fraction of the frame
        # is almost certainly registering the MOVING target (weak-texture background out-voted),
        # which would invert the gate -- flag clutter as motion and drop the real mover.  Fall
        # back to identity (raw frame difference) when the warp is implausibly large.  Evaluated
        # at full resolution on the rescaled homography so the fraction is of the full frame.
        corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
        warped_c = cv2.perspectiveTransform(corners, hmat).reshape(-1, 2)
        max_disp = float(np.linalg.norm(warped_c - corners.reshape(-1, 2), axis=1).max())
        if not np.isfinite(max_disp) or max_disp > self._max_shift_frac * float(np.hypot(w, h)):
            return prev
        return cv2.warpPerspective(prev, hmat, (w, h), flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_REPLICATE)
