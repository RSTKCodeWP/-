"""Image-GMC: global ego-motion compensation via sparse optical flow (Task 3.2).

The drone moves fast, so between detection frames the whole image translates/rotates and
a stationary survivor's box jumps in pixel space — raw-IoU association then breaks. GMC
estimates the dominant camera-induced image motion as a 2D **partial-affine** warp
(4-DOF: translation, rotation, uniform scale — exactly what a fixed-mount camera on a
moving airframe produces, and far more stable on low-texture terrain than an 8-DOF
homography). The tracker warps each track's predicted position by this transform before
association so IoU compares boxes in a motion-compensated frame.

Method (Ultralytics' `sparseOptFlow` mode, the cheap CPU pick over ORB):
`goodFeaturesToTrack` → `calcOpticalFlowPyrLK` → `estimateAffinePartial2D` (RANSAC), on a
downscaled grayscale frame.

**The low-confidence flag is the whole point over open water / uniform debris** (the named
failure mode): with no texture there is nothing to track, so a *two-stage* gate refuses to
emit a warp — (A) a raw feature-count floor catches the uniform frame before flow even
runs, and (B) a RANSAC inlier-count floor catches a degenerate fit that squeaks past (A).
When either fires, `apply` returns the **identity** warp with `ok=False`: a wrong warp is
worse than no warp, so the caller degrades to raw-IoU rather than corrupting every track.

Deterministic for CI: RANSAC's RNG is pinned with `cv2.setRNGSeed`.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

_IDENTITY_2x3 = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float64)


@dataclass(frozen=True)
class GmcResult:
    """One frame-to-frame ego-motion estimate.

    Attributes:
        warp: 2×3 partial-affine mapping the PREVIOUS frame's pixels into the CURRENT
            frame, at full (un-downscaled) resolution. Identity when `ok` is False.
        confidence: scalar in [0, 1]; 0.0 when `ok` is False.
        ok: False ⇒ low-confidence (low feature/inlier count) — caller must use identity.
        n_inliers: RANSAC inlier count (for the mission log / telemetry fusion / tests).
    """

    warp: np.ndarray
    confidence: float
    ok: bool
    n_inliers: int


class GMC:
    """Sparse-optical-flow global motion estimator. Holds the previous frame as state.

    Args:
        downscale: integer factor the frame is shrunk by before processing. Default 1
            (no resize) keeps motion recovery accurate; a caller can opt into `2`+ to
            trade accuracy for LK speed once a real clip shows the throughput is needed
            (premature downscaling aliases fine texture and corrupts the estimate). The
            recovered translation is scaled back to full resolution either way.
        min_features: feature-count floor (stage A). Below this the frame is declared
            low-texture (the uniform-water case) before any flow runs.
        min_inliers: RANSAC inlier-count floor (stage B). An affine fit is determined by 3
            correspondences, so a floor comfortably above that means "actually supported
            by the scene." Below it the fit is rejected.
        good_inliers: inlier count mapped to confidence 1.0 (a soft scale, not a gate).
    """

    def __init__(
        self,
        downscale: int = 1,
        min_features: int = 25,
        min_inliers: int = 12,
        good_inliers: int = 50,
    ) -> None:
        self.downscale = max(1, int(downscale))
        self.min_features = min_features
        self.min_inliers = min_inliers
        self.good_inliers = good_inliers
        self._prev_gray: np.ndarray | None = None
        # Pin RANSAC's RNG so the same frames give the same warp on CI every run.
        cv2.setRNGSeed(0)

    def reset(self) -> None:
        """Drop previous-frame state (call on link-loss / resolution change)."""
        self._prev_gray = None

    def apply(self, frame: np.ndarray) -> GmcResult:
        """Feed the next frame; estimate motion from the previous one.

        Accepts an HxW grayscale or HxWx3 frame. The first call (or any call after a
        reset / resolution change) primes state and returns the identity warp, ok=False.
        """
        gray = self._to_downscaled_gray(frame)

        # First frame, or a resolution change → re-prime, no estimate possible yet.
        if self._prev_gray is None or self._prev_gray.shape != gray.shape:
            self._prev_gray = gray
            return self._not_ok()

        prev = self._prev_gray
        self._prev_gray = gray

        # Stage A — feature floor: catches the uniform/water frame before flow runs.
        prev_pts = cv2.goodFeaturesToTrack(
            prev, maxCorners=1000, qualityLevel=0.01, minDistance=1, blockSize=3
        )
        if prev_pts is None or len(prev_pts) < self.min_features:
            return self._not_ok()

        # Track those corners forward into the current frame with pyramidal LK.
        curr_pts, status, _err = cv2.calcOpticalFlowPyrLK(
            prev, gray, prev_pts, None, maxLevel=3
        )
        if curr_pts is None or status is None:
            return self._not_ok()
        keep = status.ravel().astype(bool)
        prev_kept = prev_pts[keep].reshape(-1, 2)
        curr_kept = curr_pts[keep].reshape(-1, 2)
        if len(prev_kept) < self.min_features:
            return self._not_ok()

        # Estimate the partial-affine warp (prev→curr) with RANSAC.
        warp_small, inliers = cv2.estimateAffinePartial2D(
            prev_kept, curr_kept, method=cv2.RANSAC
        )
        n_inliers = int(inliers.sum()) if inliers is not None else 0

        # Stage B — inlier floor: catches a degenerate fit that passed the feature floor.
        if warp_small is None or n_inliers < self.min_inliers:
            return self._not_ok()

        warp = self._upscale_warp(warp_small)
        confidence = min(1.0, n_inliers / float(self.good_inliers))
        return GmcResult(warp=warp, confidence=confidence, ok=True, n_inliers=n_inliers)

    def _to_downscaled_gray(self, frame: np.ndarray) -> np.ndarray:
        gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        if self.downscale > 1:
            h, w = gray.shape[:2]
            gray = cv2.resize(
                gray, (w // self.downscale, h // self.downscale), interpolation=cv2.INTER_AREA
            )
        return np.ascontiguousarray(gray)

    def _upscale_warp(self, warp_small: np.ndarray) -> np.ndarray:
        """Map a warp estimated on the downscaled frame back to full resolution.

        Rotation/scale (the 2×2 linear block) are scale-invariant; only the translation
        column is in downscaled pixels and must be multiplied by the downscale factor.
        """
        warp = warp_small.astype(np.float64).copy()
        warp[:, 2] *= self.downscale
        return warp

    def _not_ok(self) -> GmcResult:
        return GmcResult(
            warp=_IDENTITY_2x3.copy(), confidence=0.0, ok=False, n_inliers=0
        )
