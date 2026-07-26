"""Tests for image-GMC ego-motion compensation (Task 3.2).

GMC estimates the dominant camera-induced image motion (a 2D partial-affine warp)
between consecutive frames so the tracker can compensate track predictions before IoU
association. The two required behaviors:
  (a) on a synthetically panned sequence, GMC recovers the known motion and
      GMC-compensated association keeps IDs stable where raw-IoU fails;
  (b) a low-feature (uniform) frame is flagged low-confidence — over open water / uniform
      debris there is no texture to track, so GMC must DETECT that and fall back to
      identity rather than emit a garbage warp.

All synthetic numpy — no real video, fully deterministic.
"""

from __future__ import annotations

import cv2
import numpy as np

from hades.detect.detector import Detection
from hades.track.gmc import GMC, GmcResult
from hades.track.tracker import ByteTracker, TrackState


def _textured(h: int = 240, w: int = 320, seed: int = 0) -> np.ndarray:
    """A realistic smooth-textured gray frame for optical flow.

    Pure per-pixel noise is pathological for LK — it has no multi-scale coherence, so it
    aliases and cannot be tracked across a large pan (real aerial frames have smooth,
    structured texture). We sum a few low-frequency sinusoids with blurred noise to give
    rich corners that LK locks onto across pyramid levels, the way terrain does.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    img = np.zeros((h, w), np.float32)
    for f in (13.0, 23.0, 37.0):
        img += np.sin(xx / f + seed) * np.cos(yy / (f * 0.8) + seed)
    noise = cv2.GaussianBlur(rng.integers(0, 255, (h, w)).astype(np.float32), (0, 0), 3)
    img = img / np.ptp(img) * 120 + noise / np.ptp(noise) * 120
    return np.clip(img, 0, 255).astype(np.uint8)


# --- (a) recovers a known global translation --------------------------------


def test_gmc_recovers_known_translation():
    # Slide a window across a larger background by (dx, dy): the CONTENT in the frame then
    # moves by (-dx, -dy), so the prev→curr warp must recover (-dx, -dy). A window slide
    # (vs warpAffine) keeps every frame fully textured — no synthetic black border to
    # starve the corner tracker.
    dx, dy = 40, 25
    big = _textured(240 + dy, 320 + dx, seed=0)
    prev = np.ascontiguousarray(big[0:240, 0:320])
    curr = np.ascontiguousarray(big[dy : dy + 240, dx : dx + 320])

    gmc = GMC()
    primed = gmc.apply(prev)  # first call primes state
    assert not primed.ok  # nothing to compare against yet → identity, not ok
    res = gmc.apply(curr)

    assert res.ok
    assert abs(res.warp[0, 2] - (-dx)) < 1.0
    assert abs(res.warp[1, 2] - (-dy)) < 1.0


def test_gmc_recovers_known_rotation():
    # Rotate a larger background and crop the same central window from both, so the frame
    # is fully textured (no black wedge from rotating in-place).
    big = _textured(320, 400, seed=0)
    center = (big.shape[1] / 2, big.shape[0] / 2)
    m_true = cv2.getRotationMatrix2D(center, angle=5.0, scale=1.0)
    rotated_big = cv2.warpAffine(big, m_true, (big.shape[1], big.shape[0]))
    # Crop a central window away from the rotation-induced border.
    prev = np.ascontiguousarray(big[40:280, 40:360])
    curr = np.ascontiguousarray(rotated_big[40:280, 40:360])

    gmc = GMC()
    gmc.apply(prev)
    res = gmc.apply(curr)

    assert res.ok
    # The recovered 2×2 linear block must encode ~5° of rotation. Compare the rotation
    # magnitude directly (convention-free): |off-diagonal| ≈ sin(5°).
    assert abs(abs(res.warp[1, 0]) - np.sin(np.radians(5.0))) < 0.02


# --- (b) low-feature frame flagged low-confidence ---------------------------


def test_gmc_flags_uniform_frame_low_confidence():
    flat = np.full((240, 320), 127, dtype=np.uint8)  # zero texture → no corners
    gmc = GMC()
    gmc.apply(flat)  # prime (also low-feature)
    res = gmc.apply(flat)

    assert not res.ok
    assert res.confidence == 0.0
    # Fallback is the identity warp — never a garbage transform.
    assert np.allclose(res.warp, np.float32([[1, 0, 0], [0, 1, 0]]))


def test_gmc_flags_too_few_features_low_confidence():
    # A near-flat frame with only a handful of dots squeaks past nothing useful: too few
    # correspondences to support an affine fit → still flagged (the inlier-floor guard).
    sparse = np.full((240, 320), 127, dtype=np.uint8)
    for (x, y) in [(50, 50), (60, 200), (250, 80), (300, 220)]:
        sparse[y, x] = 255
    gmc = GMC()
    gmc.apply(sparse)
    res = gmc.apply(sparse)
    assert not res.ok
    assert res.confidence == 0.0


# --- resolution-change resilience (CLAUDE.md tolerate mid-stream resize) -----


def test_gmc_resets_on_resolution_change():
    gmc = GMC()
    gmc.apply(_textured(240, 320))
    res = gmc.apply(_textured(480, 640, seed=1))  # different shape
    assert not res.ok  # treated as a re-prime, identity returned
    assert np.allclose(res.warp, np.float32([[1, 0, 0], [0, 1, 0]]))


# --- end-to-end: GMC keeps IDs stable where raw-IoU fails --------------------


def _pan_sequence():
    """A stationary survivor under a hard global pan: the box moves a lot in pixels.

    Returns a list of (frame_gray, detections) where the survivor sits at the SAME world
    spot but the camera pans, so its pixel box translates by `pan` each frame — enough
    that consecutive boxes do NOT overlap (raw IoU == 0). To keep the scene trackable and
    the survivor on-screen, we render from a LARGER background and slide a window across
    it (a real pan keeps content in-frame), so every frame is full of features and the
    survivor box never leaves the visible region.
    """
    h, w = 240, 320
    pan = 60  # px/frame — larger than the 30px box, so consecutive boxes are disjoint
    n = 4
    # Background wide enough that the window never runs off either edge.
    big = _textured(h, w + pan * n, seed=7)
    frames = []
    survivor_cx = 160  # survivor stays put on-screen (center column) the whole time
    for k in range(n):
        x0 = pan * k  # window slides right across the static background → camera pans
        frame = np.ascontiguousarray(big[:, x0 : x0 + w])
        # The survivor sits at a FIXED screen column, but to make it a moving-box case for
        # the tracker we anchor it to background content: it shifts left by `pan` per frame
        # exactly like the rest of the scene, so GMC's warp is what realigns it.
        sx = survivor_cx - pan * k
        det = Detection(box_xyxy=(float(sx), 100.0, float(sx + 30), 150.0), conf=0.9)
        frames.append((frame, [det]))
    return frames


def test_gmc_keeps_id_stable_under_pan_where_raw_iou_fails():
    seq = _pan_sequence()

    # Without GMC: the disjoint boxes break association → the id changes (raw-IoU fails).
    trk_raw = ByteTracker(min_hits=1)
    raw_ids = []
    for _frame, dets in seq:
        out = trk_raw.update(dets)
        confirmed = [t for t in out if t.state is TrackState.CONFIRMED]
        if confirmed:
            raw_ids.append(confirmed[0].track_id)
    assert len(set(raw_ids)) > 1  # the id was NOT stable without compensation

    # With GMC: warp track predictions by the estimated camera motion → id stays stable.
    trk_gmc = ByteTracker(min_hits=1)
    gmc = GMC()
    gmc_ids = []
    for frame, dets in seq:
        # Drive GMC with each frame in order (apply primes on the first call → identity).
        res = gmc.apply(frame)
        warp = res.warp if res.ok else None
        out = trk_gmc.update(dets, gmc_warp=warp)
        confirmed = [t for t in out if t.state is TrackState.CONFIRMED]
        if confirmed:
            gmc_ids.append(confirmed[0].track_id)
    assert len(set(gmc_ids)) == 1  # ONE id the whole way, thanks to ego-motion comp


def test_gmcresult_is_a_value_object():
    r = GmcResult(
        warp=np.float32([[1, 0, 0], [0, 1, 0]]), confidence=0.0, ok=False, n_inliers=0
    )
    assert r.confidence == 0.0
    assert r.ok is False
    assert r.n_inliers == 0
