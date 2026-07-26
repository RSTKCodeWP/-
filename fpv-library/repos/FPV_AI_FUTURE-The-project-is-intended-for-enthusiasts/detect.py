"""CV detection pipeline for S1 thermal perception.

``detect_frame`` is the public entry point.  It turns a raw uint16 frame into
a sorted list of ``ThermalBlob`` objects and an updated ``ThresholdState``.

Pipeline
--------
1. **White top-hat morphology** with an elliptical (nearly circular)
   structuring element of diameter ~9–11 px.  This suppresses low-spatial-
   frequency warm background (ground-radiation gradient, cam-temp bias) while
   preserving small hot spots.

2. **Adaptive / relative threshold** = 99.5th-percentile + k·MAD of the
   top-hat residual image.  This is deliberately *relative* — it has no fixed
   physical-count meaning and naturally re-tracks through cam-temp drift.

3. **FFC re-base**: whenever the ``ffc_state`` transitions to ``"READY"``
   (i.e., the camera just completed a flat-field calibration shutter event),
   the threshold baseline history is cleared and the next frame establishes
   a fresh baseline.  This is required because FFC resets the camera's NUC
   correction tables and the absolute count level of the sky background can
   jump by hundreds of counts — without re-basing, the stale baseline would
   produce false alarms or miss the target.

4. **Connected-components labelling** (``scipy.ndimage.label``).

5. **Per-component features**:
   - Intensity-weighted sub-pixel centroid (moments of raw counts, not bbox
     centre).  This is the primary LOS angular-error proxy.
   - Area (pixel count), peak counts, mean counts.
   - SNR = (peak_counts − bg_mean) / bg_std, where bg statistics are drawn
     from the top-hat residual image.

6. Return blobs sorted descending by ``salience = snr * area_px``.

Dependencies
------------
* **numpy** — always required.
* **scipy.ndimage** — always required (``white_tophat``, ``label``,
  ``find_objects``, ``center_of_mass``).
* **cv2 (OpenCV)** — used for the elliptical structuring element if available
  (``cv2.getStructuringElement``), otherwise a numpy-based circular mask is
  used as fallback.  Not a hard requirement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy import ndimage as ndi

from .blob import ThermalBlob, TargetObservation, SCHEMA

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Morphological structuring element diameter (pixels).  Must be odd.
_SE_DIAMETER_PX: int = 11

#: Percentile for adaptive threshold (99.5th percentile of top-hat image).
_THRESHOLD_PERCENTILE: float = 99.5

#: Multiplier on MAD added to the percentile for the threshold.
_THRESHOLD_K_MAD: float = 2.5

#: Max pixels used to ESTIMATE the relative threshold (percentile + MAD).  The background
#: percentile/MAD are population statistics, so a large strided subsample is statistically
#: indistinguishable from the full frame yet ~Nx cheaper -- the dominant per-frame cost on the
#: Pi5 was the full-frame np.percentile/np.median (D1 HWIL profiling).  Detection still runs on
#: every pixel; only the scalar threshold is estimated from the subsample.
_THRESHOLD_MAX_SAMPLES: int = 40000

#: Compute the (diagnostic) extended-area footprint only for the top-K most salient blobs --
#: it never feeds guidance, so spending a flood-fill on all ~20 blobs/frame is wasted latency.
_EXTENDED_AREA_TOP_K: int = 3

#: Region-type k-multipliers on ``_THRESHOLD_K_MAD`` for the graduated look-down CFAR.
#: The ordering enforces the doctrine ``k_horizon < k_sky < k_ground``:
#:  * GROUND -- warm, textured terrain throws the most false alarms, so it gets the
#:    HIGHEST floor (least sensitive);
#:  * HORIZON -- the sky/ground transition is where a head-on look-down target first
#:    appears, so it gets the LOWEST floor (most sensitive);
#:  * SKY -- clean cold background, the nominal sensitivity, sits in between.
_REGION_K_SKY: float = 1.0
_REGION_K_HORIZON: float = 0.7
_REGION_K_GROUND: float = 1.6

#: Patch half-widths (px) for the multiscale MPCM local-contrast stage.  Small scales catch
#: a 1-2 px point target; the largest catches a small extended drone a few px across.
_MPCM_SCALES: tuple[int, ...] = (1, 2, 4)

#: Minimum local-contrast-to-intensity ratio for a candidate to survive the MPCM gate.
#: A compact target's min-directional contrast is a large fraction of its own top-hat height
#: (all neighbours are background), so the ratio is near 1; a streak/edge has near-zero
#: min-directional contrast against its own bright neighbour, so the ratio collapses toward 0.
#: A relative percentile+MAD threshold is unusable here -- the MPCM map is ~0 almost
#: everywhere, so its MAD collapses to 0 and the threshold lets noise spikes through.
_MPCM_RATIO: float = 0.3

#: Line length (px) for the directional max-median clutter filter.  A target spanning fewer
#: than ~half this length along any direction survives; a line filling the window is removed.
_DIRECTIONAL_MEDIAN_LEN: int = 9

#: Minimum blob area (pixels) to be reported.  Filters cosmic rays / single
#: hot pixels that are not physically consistent with a drone target.
_MIN_AREA_PX: int = 2

#: Minimum SNR for a blob to be included in the output list.
_MIN_SNR: float = 2.0

#: Maximum blobs to return per frame (cap prevents spam on cluttered scenes).
_MAX_BLOBS: int = 20


# ---------------------------------------------------------------------------
# Threshold state
# ---------------------------------------------------------------------------

@dataclass
class ThresholdState:
    """Mutable state carried between frames for the adaptive threshold.

    The caller holds one ``ThresholdState`` instance and passes it into each
    call to ``detect_frame``, receiving the updated state back.

    Attributes
    ----------
    prev_ffc_state:
        FFC state seen in the *previous* frame.  Used to detect
        ``"FREEZE" → "READY"`` transitions which require a re-base.
    baseline_percentile:
        The percentile value of the top-hat image from the most recent
        ``"READY"`` frame.  Carried forward for diagnostics.
    baseline_mad:
        The MAD of the top-hat image from the most recent ``"READY"`` frame.
    threshold_counts:
        The most recently computed threshold value (percentile + k·MAD).
    frames_since_rebase:
        Number of ``"READY"`` frames processed since the last re-base.
    """

    prev_ffc_state: str = "READY"
    baseline_percentile: float = 0.0
    baseline_mad: float = 0.0
    threshold_counts: float = 0.0
    frames_since_rebase: int = 0

    def needs_rebase(self, current_ffc_state: str) -> bool:
        """Return True when the camera just completed an FFC event.

        The transition ``FREEZE/RECOVERING → READY`` means the NUC tables have
        been refreshed and the old threshold baseline is stale.
        """
        was_not_ready = self.prev_ffc_state in ("FREEZE", "RECOVERING")
        is_ready_now = current_ffc_state == "READY"
        return was_not_ready and is_ready_now


# ---------------------------------------------------------------------------
# Structuring element
# ---------------------------------------------------------------------------

def _make_elliptical_se(diameter: int) -> npt.NDArray[np.uint8]:
    """Build a circular binary structuring element.

    Tries ``cv2.getStructuringElement`` first; falls back to a numpy
    circle mask so that OpenCV is not a hard dependency.
    """
    try:
        import cv2  # type: ignore[import]
        se = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (diameter, diameter)
        )
        return se.astype(np.uint8)
    except ImportError:
        pass

    # numpy fallback: draw a filled circle
    r = diameter // 2
    size = 2 * r + 1
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    mask = (xx * xx + yy * yy <= r * r).astype(np.uint8)
    return mask


# Precompute the SE once at module import (cheap, O(SE_area))
_STRUCT_ELEM: npt.NDArray[np.uint8] = _make_elliptical_se(_SE_DIAMETER_PX)


# Column order of the per-label stats array (matches cv2.CC_STAT_*).
_CC_LEFT, _CC_TOP, _CC_WIDTH, _CC_HEIGHT, _CC_AREA = 0, 1, 2, 3, 4


def _connected_components(
    binary_mask: npt.NDArray[np.bool_],
) -> tuple[int, npt.NDArray[np.int32], npt.NDArray[np.int64]]:
    """Label a binary mask and return ``(num_labels, labels, stats)``.

    ``num_labels`` includes the background (label 0).  ``stats[k]`` is
    ``(left, top, width, height, area)`` for label ``k`` -- the same layout
    cv2 uses, so the per-component loop is identical for both backends.

    Uses ``cv2.connectedComponentsWithStats`` (C, single pass -- ~10x faster on
    cluttered scenes than ``scipy.ndimage.label`` + ``find_objects`` + per-blob
    ``count_nonzero``) and falls back to scipy so cv2 stays a soft dependency.
    Both use 4-connectivity, so the component *set* is identical.
    """
    try:
        import cv2  # type: ignore[import]

        num, labels, stats, _ = cv2.connectedComponentsWithStats(
            binary_mask.view(np.uint8), connectivity=4
        )
        return num, labels.astype(np.int32, copy=False), stats.astype(np.int64, copy=False)
    except ImportError:
        labels, n = ndi.label(binary_mask)
        stats = np.zeros((n + 1, 5), dtype=np.int64)
        for k, sl in enumerate(ndi.find_objects(labels), start=1):
            if sl is None:
                continue
            sy, sx = sl
            comp = labels[sl] == k
            stats[k] = (sx.start, sy.start, sx.stop - sx.start, sy.stop - sy.start, int(comp.sum()))
        return n + 1, labels.astype(np.int32, copy=False), stats


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _extended_area_px(
    frame_f: npt.NDArray[np.float32],
    cx: float,
    cy: float,
    peak: float,
    area_px: int,
    half_win: int = 90,
    clamp_mult: int = 200,
) -> int:
    """Un-suppressed target footprint (DIAGNOSTIC subtense cue, not a looming input).

    The white top-hat suppresses the interior of a LARGE/extended target, so ``area_px``
    stops growing as the target fills the frame.  This counts the half-max FOOTPRINT around
    the centroid on the raw frame.  Two guards (Phase-B review C3) keep a look-down hot-ground
    plateau from inflating it: (1) FLOOD-FILL -- count only the connected component containing
    the centroid, so a disconnected hot region elsewhere in the window is ignored; (2) CLAMP --
    never exceed ``clamp_mult * area_px``.  The background is the window-border median, which is
    valid for small/medium targets; it is imperfect once the target fills the frame, which is
    why this is diagnostic-only (genuinely unobservable subtense at saturation).
    """
    h, w = frame_f.shape
    x0 = max(0, int(cx) - half_win)
    x1 = min(w, int(cx) + half_win)
    y0 = max(0, int(cy) - half_win)
    y1 = min(h, int(cy) + half_win)
    patch = frame_f[y0:y1, x0:x1]
    if patch.size == 0:
        return int(area_px)
    border = np.concatenate([patch[0, :], patch[-1, :], patch[:, 0], patch[:, -1]])
    base = float(np.median(border))
    thr = base + 0.5 * (float(peak) - base)           # half-max contour
    above = patch >= thr
    labeled, _ = ndi.label(above)
    ly, lx = int(cy) - y0, int(cx) - x0
    if 0 <= ly < labeled.shape[0] and 0 <= lx < labeled.shape[1] and labeled[ly, lx] > 0:
        count = int(np.count_nonzero(labeled == labeled[ly, lx]))
    else:
        count = int(area_px)                          # centroid below half-max -> top-hat area
    return int(min(count, max(int(area_px), 1) * clamp_mult))


def detect_frame(
    frame_u16: npt.NDArray[np.uint16],
    *,
    cam_temp_c: float,
    ffc_state: str,
    threshold_state: ThresholdState,
    frame_id: int = 0,
    t_capture_ns: int | None = None,
    min_area_px: int = _MIN_AREA_PX,
    min_snr: float = _MIN_SNR,
    max_blobs: int = _MAX_BLOBS,
    region_bands: int = 0,
    graduated_k: bool = False,
    use_mpcm: bool = False,
    directional_median: bool = False,
    roi: tuple[int, int, int, int] | None = None,
) -> tuple[list[ThermalBlob], ThresholdState]:
    """Run one frame through the S1 CV detection pipeline.

    Parameters
    ----------
    frame_u16:
        Raw 14-bit Y16 frame as a ``(H, W)`` uint16 array.
    cam_temp_c:
        Camera housing temperature in °C (from serial/SLA telemetry).
    ffc_state:
        FFC state for this frame: ``"READY" | "FREEZE" | "RECOVERING"``.
    threshold_state:
        Mutable threshold state from the previous frame.  Pass the returned
        ``new_threshold_state`` on the next call.
    frame_id:
        Monotonically increasing frame counter.
    t_capture_ns:
        CLOCK_MONOTONIC capture timestamp in nanoseconds, or ``None``.
    min_area_px:
        Blobs with fewer pixels are discarded.
    min_snr:
        Blobs below this SNR are discarded.
    max_blobs:
        Maximum number of blobs to return (sorted by salience).
    roi:
        Optional ``(x, y, w, h)`` region of interest in ABSOLUTE frame pixels.
        When given, the frame is cropped to the ROI ONCE and the entire heavy
        pipeline (top-hat / directional-median / threshold / region-CFAR / MPCM /
        connected-components / extended-area) runs only on the crop -- the
        on-target latency win on the Pi5, where the heavy stages scale with pixel
        count.  Every returned ``centroid_px`` and ``bbox`` is offset back by
        ``(x, y)`` so all outputs stay in ABSOLUTE frame coordinates.  The ROI is
        clamped to the frame bounds; an empty (off-frame) ROI yields no blobs.
        ``roi=None`` is bit-identical to the full-frame path.

    Returns
    -------
    (blobs, new_threshold_state)
        ``blobs`` is a list of ``ThermalBlob`` objects sorted descending by
        salience.  Empty during FFC freeze (no reliable pixel data).
        ``new_threshold_state`` carries the updated adaptive threshold for the
        next frame.
    """
    # ── 0. FFC FREEZE guard ───────────────────────────────────────────────
    # During a freeze the camera's shutter is closed / NUC is running —
    # pixel data is a stale copy of the previous frame and MUST NOT be
    # used to produce blobs.  Return empty immediately.
    new_state = ThresholdState(
        prev_ffc_state=ffc_state,
        baseline_percentile=threshold_state.baseline_percentile,
        baseline_mad=threshold_state.baseline_mad,
        threshold_counts=threshold_state.threshold_counts,
        frames_since_rebase=threshold_state.frames_since_rebase,
    )

    if ffc_state in ("FREEZE", "RECOVERING"):
        # Update prev_ffc_state but keep everything else frozen
        return [], new_state

    # ── 1. Re-base after FFC ──────────────────────────────────────────────
    # When the camera returns to READY after an FFC event (shutter closed and
    # NUC tables refreshed), the absolute count level can jump significantly.
    # We reset the threshold baseline so the very next READY frame re-learns
    # the current sky level.  Without this, a stale baseline would produce
    # false alarms against the new post-FFC background level.
    if threshold_state.needs_rebase(ffc_state):
        new_state.frames_since_rebase = 0
    else:
        new_state.frames_since_rebase = threshold_state.frames_since_rebase + 1

    # ── 1b. ROI gate ──────────────────────────────────────────────────────
    # Crop ONCE to the (clamped) ROI so every heavy stage below runs on the crop;
    # roi_x0/roi_y0 are the absolute-pixel offset added back to every centroid/bbox
    # at the end.  roi=None -> (0, 0) offset and the full frame, i.e. bit-identical.
    roi_x0, roi_y0 = 0, 0
    if roi is not None:
        h_full, w_full = frame_u16.shape
        rx, ry, rw, rh = (int(roi[0]), int(roi[1]), int(roi[2]), int(roi[3]))
        x0 = min(max(rx, 0), w_full)
        y0 = min(max(ry, 0), h_full)
        x1 = min(max(rx + rw, 0), w_full)
        y1 = min(max(ry + rh, 0), h_full)
        if x1 <= x0 or y1 <= y0:                  # ROI fully off-frame / degenerate -> no blobs
            return [], new_state
        roi_x0, roi_y0 = x0, y0
        frame_u16 = frame_u16[y0:y1, x0:x1]

    # ── 2. White top-hat morphology ───────────────────────────────────────
    # Convert to float32 for morphology (avoids uint16 underflow artefacts).
    frame_f = frame_u16.astype(np.float32)
    tophat = _white_tophat(frame_f, _STRUCT_ELEM)

    # ── 2b. Directional max-median clutter filter (look-down line rejection) ──
    # Strip linear structures (horizon edge, field boundaries, scan lines) from the top-hat
    # before thresholding so they never become candidate blobs; compact targets are preserved.
    if directional_median:
        tophat = _directional_max_median(tophat)

    # ── 3. Adaptive / relative threshold ──────────────────────────────────
    tophat_flat = tophat.ravel()
    threshold, pct_val, mad_val = _compute_threshold(tophat_flat)
    new_state.baseline_percentile = float(pct_val)
    new_state.baseline_mad = float(mad_val)
    new_state.threshold_counts = float(threshold)

    # ── 4. Binary mask & connected components ─────────────────────────────
    if region_bands > 0:
        # Look-down region-adaptive CFAR: per-horizontal-band floor so a hot ground band
        # gets its own (higher) threshold.  OR-ed with the GLOBAL threshold as a backstop so
        # region-CFAR can NEVER be LESS sensitive than global -- a real low-flyer over hot
        # terrain (whose own band would over-threshold it, C2) is still caught by the global
        # floor; the re-admitted static ground clutter is rejected downstream by MTI, not here.
        band_k = _classify_bands(frame_f, region_bands) if graduated_k else None
        thr_map = _region_adaptive_threshold(tophat, region_bands, band_k=band_k)
        binary_mask = (tophat > thr_map) | (tophat > threshold)
        # keep the GLOBAL threshold in threshold_counts (telemetry); the median band floor
        # hides the worst (ground) band, so report the global value consumers already expect.
    else:
        binary_mask = tophat > threshold

    # ── 4b. MPCM local-contrast gate (look-down clutter / edge rejection) ──
    # A candidate must be locally salient as well as bright: it must out-contrast ALL eight
    # neighbouring patches.  This drops bright edges and thin streaks (horizon, scan lines,
    # field boundaries) that pass the intensity threshold but are not compact targets.  The
    # gate is RELATIVE (percentile + k*MAD of the MPCM map) so it re-bases with the scene.
    if use_mpcm:
        mpcm = _mpcm(tophat)
        binary_mask = binary_mask & (mpcm > _MPCM_RATIO * tophat)

    num_labels, labeled, stats = _connected_components(binary_mask)

    if num_labels <= 1:                       # only the background label present
        return [], new_state

    # Background statistics from top-hat image (exclude threshold-passing pixels)
    bg_mask = ~binary_mask
    bg_vals = tophat[bg_mask]
    if bg_vals.size == 0:
        bg_mean = 0.0
        bg_std = 1.0
    else:
        bg_mean = float(np.mean(bg_vals))
        bg_std = float(np.std(bg_vals)) or 1.0

    # ── 5. Per-component features ─────────────────────────────────────────
    blobs: list[ThermalBlob] = []

    for label_val in range(1, num_labels):
        # Area gate first (from the C stats -- no per-blob mask needed to reject noise)
        area_px = int(stats[label_val, _CC_AREA])
        if area_px < min_area_px:
            continue

        # Bounding box (cv2/scipy stats: left, top, width, height)
        x0_bb = int(stats[label_val, _CC_LEFT])
        y0_bb = int(stats[label_val, _CC_TOP])
        w_bb = int(stats[label_val, _CC_WIDTH])
        h_bb = int(stats[label_val, _CC_HEIGHT])
        slices = (slice(y0_bb, y0_bb + h_bb), slice(x0_bb, x0_bb + w_bb))

        # Component mask within its bounding box, and the raw count patch
        comp_mask = labeled[slices] == label_val

        # Raw counts within component (from original frame, not top-hat)
        raw_patch = frame_f[slices]
        comp_counts = raw_patch[comp_mask]
        peak_counts = int(np.max(comp_counts))
        mean_counts = float(np.mean(comp_counts))

        # SNR from top-hat values
        tophat_patch = tophat[slices]
        tophat_comp = tophat_patch[comp_mask]
        peak_tophat = float(np.max(tophat_comp))
        snr = (peak_tophat - bg_mean) / bg_std

        if snr < min_snr:
            continue

        # Intensity-weighted sub-pixel centroid using LOCAL-BACKGROUND-SUBTRACTED
        # raw counts.  Estimate the local background floor as the minimum value
        # within the bounding-box patch (robust, fast, avoids bias from the
        # background pedestal shifting the centroid toward the patch corner).
        # Only use pixels within the component mask.
        comp_float = raw_patch.astype(np.float64)
        local_bg = float(np.min(comp_float[comp_mask]))  # background floor estimate
        bg_sub = np.maximum(comp_float - local_bg, 0.0)

        weighted_frame = bg_sub * comp_mask.astype(np.float64)
        total_weight = float(np.sum(weighted_frame))
        if total_weight <= 0.0:
            # Degenerate (all pixels equal local_bg): fall back to geometric centre
            centroid_x = x0_bb + w_bb / 2.0
            centroid_y = y0_bb + h_bb / 2.0
        else:
            yy_local = np.arange(y0_bb, y0_bb + h_bb, dtype=np.float64)[:, np.newaxis]
            xx_local = np.arange(x0_bb, x0_bb + w_bb, dtype=np.float64)[np.newaxis, :]
            centroid_y = float(np.sum(yy_local * weighted_frame) / total_weight)
            centroid_x = float(np.sum(xx_local * weighted_frame) / total_weight)

        blob = ThermalBlob(
            centroid_px=(centroid_x, centroid_y),
            area_px=area_px,
            peak_counts=peak_counts,
            mean_counts=mean_counts,
            snr=snr,
            bbox=(x0_bb, y0_bb, w_bb, h_bb),
            frame_id=frame_id,
            t_capture_ns=t_capture_ns,
            cam_temp_c=cam_temp_c,
            ffc_state=ffc_state,
            area_extended_px=0,
        )
        blobs.append(blob)

    # Sort descending by salience
    blobs.sort(key=lambda b: b.salience, reverse=True)
    blobs = blobs[:max_blobs]

    # Diagnostic extended-area footprint: compute only for the top-K salient blobs (D1 latency).
    # Runs on the (cropped) frame_f with crop-relative centroids -- BEFORE the ROI offset below.
    for i in range(min(_EXTENDED_AREA_TOP_K, len(blobs))):
        b = blobs[i]
        ae = _extended_area_px(frame_f, b.centroid_px[0], b.centroid_px[1],
                               float(b.peak_counts), b.area_px)
        blobs[i] = replace(b, area_extended_px=ae)

    # ── 6. ROI -> absolute coordinates ────────────────────────────────────
    # All blob geometry above is crop-relative; shift centroid + bbox by the ROI origin so
    # downstream LOS/IMM math stays in absolute frame px.  No-op when roi=None (offset 0,0).
    if roi_x0 or roi_y0:
        blobs = [
            replace(
                b,
                centroid_px=(b.centroid_px[0] + roi_x0, b.centroid_px[1] + roi_y0),
                bbox=(b.bbox[0] + roi_x0, b.bbox[1] + roi_y0, b.bbox[2], b.bbox[3]),
            )
            for b in blobs
        ]

    return blobs, new_state


def detect_frame_to_observation(
    frame_u16: npt.NDArray[np.uint16],
    *,
    cam_temp_c: float,
    ffc_state: str,
    threshold_state: ThresholdState,
    frame_id: int = 0,
    t_capture_ns: int | None = None,
) -> tuple[TargetObservation, ThresholdState]:
    """Convenience wrapper that returns a ``TargetObservation`` instead of a raw list.

    All parameters and return semantics are identical to ``detect_frame``,
    except the first element of the tuple is a ``TargetObservation``.
    """
    import time
    t0 = time.perf_counter()
    blobs, new_state = detect_frame(
        frame_u16,
        cam_temp_c=cam_temp_c,
        ffc_state=ffc_state,
        threshold_state=threshold_state,
        frame_id=frame_id,
        t_capture_ns=t_capture_ns,
    )
    budget_ms = (time.perf_counter() - t0) * 1e3

    obs = TargetObservation(
        frame_id=frame_id,
        t_capture_ns=t_capture_ns,
        cam_temp_c=cam_temp_c,
        ffc_state=ffc_state,
        blobs=blobs,
        threshold_baseline_counts=new_state.threshold_counts,
        detection_budget_ms=budget_ms,
    )
    return obs, new_state


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _white_tophat(
    frame_f: npt.NDArray[np.float32],
    struct_elem: npt.NDArray[np.uint8],
) -> npt.NDArray[np.float32]:
    """Apply a flat white top-hat:  f − opening(f, SE).

    Removes background structure larger than the (elliptical) SE, leaving only
    compact bright objects (hot spots).

    Uses OpenCV's morphology when available — C/NEON-vectorised, ~30x faster
    than ``scipy.ndimage`` on the Pi5 ARM cores — and falls back to scipy so
    cv2 stays a soft dependency.  Both paths compute the *flat elliptical*
    top-hat (cv2 kernel = flat footprint; scipy via ``footprint=``).

    On real thermal scenes (a compact hot target on a smooth background) the
    result is bit-identical to the previous ``ndi.white_tophat(structure=se)``
    call.  The two differ only on high-frequency noise, where the flat ellipse
    is the correct isotropic operator: the old ``structure=`` path silently used
    the SE's bounding *square* as the footprint plus a spurious 1-count height
    bias, so the elliptical shape was never actually applied.
    """
    try:
        import cv2  # type: ignore[import]

        frame_c = np.ascontiguousarray(frame_f, dtype=np.float32)
        result = np.asarray(
            cv2.morphologyEx(
                frame_c, cv2.MORPH_TOPHAT, struct_elem, borderType=cv2.BORDER_REFLECT
            ),
            dtype=np.float32,
        )
    except ImportError:
        result = ndi.white_tophat(frame_f, footprint=(struct_elem > 0)).astype(np.float32)

    # Clip negatives that arise from numerical noise
    np.clip(result, 0.0, None, out=result)
    return result


def _compute_threshold(
    tophat_flat: npt.NDArray[np.float32],
    percentile: float = _THRESHOLD_PERCENTILE,
    k_mad: float = _THRESHOLD_K_MAD,
    sigma_clip: float = 3.0,
    n_sigma_clip_iters: int = 2,
    max_samples: int = _THRESHOLD_MAX_SAMPLES,
) -> tuple[float, float, float]:
    """Compute the adaptive / relative threshold with iterative sigma-clipping.

    Returns
    -------
    (threshold, percentile_value, mad_value)

    The threshold is ``percentile_value + k_mad * mad_value``.  Both components
    are derived from the *background-only* pixels after iterative sigma-clip —
    hot sources (target, stars) are masked out so that the percentile and MAD
    anchor to the sky background, not to the sources themselves.

    Algorithm
    ---------
    1. Compute initial median + MAD over the full top-hat image.
    2. Mask pixels > median + sigma_clip * MAD (hot sources).
    3. Repeat (up to n_sigma_clip_iters) on the surviving background pixels.
    4. Compute percentile + MAD on the cleaned background pixel set.

    This is safe and fast: sigma-clip on a flat array costs O(N) per iteration
    and we do at most 2 passes — well within a 60 Hz budget.

    MAD (Median Absolute Deviation) is a robust estimate of the spread of the
    background residual.  Using MAD instead of standard deviation makes the
    threshold resilient to sparse bright pixels (stars, hot pixels) that would
    inflate the std.
    """
    bg = tophat_flat  # start with all pixels
    # Strided subsample for the SCALAR statistics only (percentile + MAD are population
    # estimates; detection below still uses every pixel).  Deterministic stride -> tests stay
    # reproducible.  This was the #1 per-frame cost on the Pi5 (D1 latency profiling).
    if bg.size > max_samples:
        bg = bg[:: bg.size // max_samples]

    # Iterative sigma-clip to isolate the background
    for _ in range(n_sigma_clip_iters):
        median_val = float(np.median(bg))
        mad_val_raw = float(np.median(np.abs(bg - median_val))) * 1.4826
        if mad_val_raw == 0.0:
            break  # degenerate (all same value); stop early
        clip_limit = median_val + sigma_clip * mad_val_raw
        bg = bg[bg <= clip_limit]
        if bg.size == 0:
            bg = tophat_flat  # safety fallback: revert to full image
            break

    # Compute final threshold statistics on the background-only pixel set
    pct_val = float(np.percentile(bg, percentile))
    median_bg = float(np.median(bg))
    mad_val = float(np.median(np.abs(bg - median_bg))) * 1.4826
    threshold = pct_val + k_mad * mad_val
    return threshold, pct_val, mad_val


def _band_bounds(h: int, n_bands: int) -> list[tuple[int, int]]:
    """Horizontal-band ``(y0, y1)`` slices -- shared by the threshold and the classifier so
    the per-band ``k`` array stays index-aligned with the per-band threshold loop."""
    n_bands = max(1, min(int(n_bands), h))            # C5: clamp so no band is empty
    band_h = max(1, h // n_bands)
    bounds: list[tuple[int, int]] = []
    for i in range(n_bands):
        y0 = i * band_h
        y1 = h if i == n_bands - 1 else (i + 1) * band_h
        if y1 > y0:                                   # C5: drop a degenerate empty band
            bounds.append((y0, y1))
    return bounds


def _classify_bands(
    frame_f: npt.NDArray[np.float32],
    n_bands: int,
) -> list[float]:
    """Classify each horizontal band sky / horizon / ground and return its ``k_mad``.

    Classification reads the RAW frame band statistics (the top-hat residual is
    background-suppressed and cannot tell sky from ground):

      * band background LEVEL (median) -- ground radiates warmer than the cold sky;
      * band internal VERTICAL structure (spread of per-row medians) -- the band that
        straddles the sky/ground boundary shows the largest internal vertical step and is
        the HORIZON, even when a uniformly-hot ground band sits below it.

    The single band whose internal vertical step is a meaningful fraction of the whole
    sky->ground contrast is the horizon (most sensitive); of the rest, the warmer half is
    ground (least sensitive) and the cooler half is sky.  When the scene has no horizon in
    view (uniform), every band falls back to a level-based sky/ground split.  The returned
    list is index-aligned with ``_band_bounds(h, n_bands)``.
    """
    h = frame_f.shape[0]
    bounds = _band_bounds(h, n_bands)
    medians = np.array([float(np.median(frame_f[y0:y1])) for (y0, y1) in bounds])
    vstep = np.array([
        float(np.ptp(np.median(frame_f[y0:y1], axis=1))) for (y0, y1) in bounds
    ])
    lo, hi = float(medians.min()), float(medians.max())
    contrast = hi - lo                                 # sky->ground band-median contrast

    # No horizon/ground split unless the band-to-band contrast clears the in-band noise
    # floor (``calm`` = the quietest band's row-median spread).  On a uniform sky ``contrast``
    # is a few tenths of a count -- far below the floor -- so every band stays SKY and the
    # detector never invents a spurious, over-sensitive "horizon".
    calm = float(np.min(vstep))
    has_structure = contrast > max(6.0 * calm, 2.0)
    if not has_structure:
        return [_THRESHOLD_K_MAD * _REGION_K_SKY] * len(bounds)

    # horizon = the band with the largest internal vertical step (the straddler), but only if
    # that step is a real fraction of the full sky->ground contrast.
    horizon_idx = int(np.argmax(vstep))
    has_horizon = float(vstep[horizon_idx]) > 0.25 * contrast

    ks: list[float] = []
    for i in range(len(bounds)):
        if has_horizon and i == horizon_idx:
            ks.append(_THRESHOLD_K_MAD * _REGION_K_HORIZON)
        else:
            warm = (medians[i] - lo) / max(contrast, 1.0)   # 0 = coolest (sky) .. 1 = ground
            ks.append(_THRESHOLD_K_MAD * (_REGION_K_GROUND if warm >= 0.5 else _REGION_K_SKY))
    return ks


def _shift2d(a: npt.NDArray[np.float32], dy: int, dx: int) -> npt.NDArray[np.float32]:
    """Edge-replicating 2-D shift: ``result[y, x] = a[clip(y+dy), clip(x+dx)]``.

    Used to fetch a neighbouring patch's value without wrap-around artefacts at the border
    (``np.roll`` would wrap the bottom band onto the top and fabricate motion/contrast there).

    Implemented as a single ``np.pad(mode='edge')`` + contiguous slice instead of the old
    double fancy-index ``a[ys][:, xs]``.  Edge-pad replicates the border exactly like the
    per-axis ``np.clip`` of the index arrays did, so the result is bit-identical, but it
    allocates one padded copy and a view rather than two gathered intermediates -- the
    dominant cost of ``_mpcm`` (8 dirs x 3 scales) on the Pi5.
    """
    h, w = a.shape
    py, px = abs(int(dy)), abs(int(dx))
    # Pad symmetrically by the shift magnitude on each axis, then slice the window that
    # corresponds to indices ``clip(arange+dy)`` / ``clip(arange+dx)``.
    padded = np.pad(a, ((py, py), (px, px)), mode="edge")
    y0 = py + int(dy)
    x0 = px + int(dx)
    return np.ascontiguousarray(padded[y0:y0 + h, x0:x0 + w])


def _mpcm(
    salience: npt.NDArray[np.float32],
    scales: tuple[int, ...] = _MPCM_SCALES,
) -> npt.NDArray[np.float32]:
    """Multiscale Patch-based Contrast Measure (local-contrast salience).

    For each pixel and scale ``s`` the central (2s+1) patch mean is compared against the
    eight non-overlapping neighbouring patch means (one patch-width away in each direction).
    The per-scale contrast is the MINIMUM over the eight directions: a compact target that is
    brighter than ALL its neighbours keeps a large positive minimum, while an edge or a thin
    streak -- bright as the neighbour along its own direction -- has a near-zero/negative
    minimum and is suppressed.  The multiscale response is the max over scales (clipped >= 0),
    so the stage fires for whichever scale matches the target and stays quiet on extended
    structure and the horizon line.

    Run on the top-hat residual (background already removed), so neighbouring patches of a
    point target sit at ~0 and the contrast is the target's own height.
    """
    out = np.zeros_like(salience, dtype=np.float32)
    for s in scales:
        size = 2 * int(s) + 1
        m0 = ndi.uniform_filter(salience, size=size, mode="reflect")
        shift = size                                  # neighbour patch is one patch-width away
        dirs = ((-shift, 0), (shift, 0), (0, -shift), (0, shift),
                (-shift, -shift), (-shift, shift), (shift, -shift), (shift, shift))
        min_contrast: npt.NDArray[np.float32] | None = None
        for dy, dx in dirs:
            d = m0 - _shift2d(m0, dy, dx)
            min_contrast = d if min_contrast is None else np.minimum(min_contrast, d)
        assert min_contrast is not None
        np.maximum(out, np.clip(min_contrast, 0.0, None), out=out)
    return out


def _directional_max_median(
    salience: npt.NDArray[np.float32],
    length: int = _DIRECTIONAL_MEDIAN_LEN,
) -> npt.NDArray[np.float32]:
    """Directional max-median clutter filter (Deshpande): suppress lines, keep point targets.

    The background at each pixel is estimated as the MAXIMUM over four directional 1-D medians
    (horizontal, vertical, and both diagonals) of length ``length``.  A LINEAR structure fills
    the window along its own direction, so the median along that direction equals the line
    level and the max-median captures it -> it is subtracted to ~0.  A COMPACT target occupies
    only a few of the ``length`` samples along every direction, so every directional median
    stays at the background level and the target survives the subtraction.  This is the classic
    backstop against the horizon edge, field boundaries and scan-line artefacts that a point
    operator (top-hat) cannot tell from a real target.

    NOTE: a stack-and-median rewrite (bit-identical) was tried to replace the 4x
    ``scipy.ndimage.median_filter`` but profiled SLOWER on the RPi5 target (~237ms vs ~198ms):
    the (L,h,w) tap buffer + axis-0 ``np.partition`` is memory-bound and loses to scipy's
    in-place C median on ARM.  Kept the scipy form; the real-time win for this stage is
    architectural (ROI-gate / temporal decimation), not a micro-rewrite of the filter.
    """
    L = int(length) | 1                               # force odd so the window is centred
    med_h = ndi.median_filter(salience, size=(1, L), mode="reflect")
    med_v = ndi.median_filter(salience, size=(L, 1), mode="reflect")
    eye = np.eye(L, dtype=bool)
    med_d1 = ndi.median_filter(salience, footprint=eye, mode="reflect")
    med_d2 = ndi.median_filter(salience, footprint=eye[::-1], mode="reflect")
    background = np.maximum(np.maximum(med_h, med_v), np.maximum(med_d1, med_d2))
    return np.clip(salience - background, 0.0, None).astype(np.float32)


def _region_adaptive_threshold(
    tophat: npt.NDArray[np.float32],
    n_bands: int,
    percentile: float = _THRESHOLD_PERCENTILE,
    k_mad: float = _THRESHOLD_K_MAD,
    band_k: list[float] | None = None,
) -> npt.NDArray[np.float32]:
    """Per-horizontal-band relative-threshold map (look-down region-adaptive CFAR).

    A single global threshold is wrong looking DOWN: the hot ground band inflates the
    background statistics and shifts the threshold across the WHOLE frame, so a small
    target in the cool sky band is missed (or the ground band false-alarms).  Thresholding
    each horizontal band by its OWN background gives the ground band a higher floor while
    the sky band stays sensitive.  Each band reuses the same sigma-clipped percentile+MAD.

    When ``band_k`` is supplied (from :func:`_classify_bands`) each band uses its own
    region-graduated ``k`` instead of the uniform ``k_mad``; the list is index-aligned with
    :func:`_band_bounds`.  Omitting it keeps the original uniform-k behaviour unchanged.
    """
    h, w = tophat.shape
    thr_map = np.empty((h, w), dtype=np.float32)
    for i, (y0, y1) in enumerate(_band_bounds(h, n_bands)):
        k = float(band_k[i]) if (band_k is not None and i < len(band_k)) else k_mad
        thr, _, _ = _compute_threshold(tophat[y0:y1].ravel(), percentile, k)
        thr_map[y0:y1] = np.float32(thr)
    return thr_map
