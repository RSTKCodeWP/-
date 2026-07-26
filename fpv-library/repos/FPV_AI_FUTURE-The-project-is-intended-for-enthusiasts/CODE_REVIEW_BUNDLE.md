# Real-time thermal-infrared detection, tracking and line-of-sight control — source bundle

*Single-file source bundle prepared for independent technical review.*

## What this is
A research codebase implementing a real-time image-processing and control pipeline that:

1. **Detects** small, dim, low-contrast objects in monocular thermal-infrared video (heavy sensor
   noise, cluttered warm backgrounds).
2. **Tracks** a detected object through clutter and brief dropouts with a multiple-model recursive
   estimator, holding a stable line-of-sight to it.
3. **Discriminates** object class with a small convolutional network (a permission signal only — it
   never writes to the tracker or the line-of-sight).
4. Computes a **closed-loop control command** for a body-mounted camera platform from the measured
   line-of-sight rate.

It is pure signal-processing / state-estimation / control: classical methods throughout, with a
single small neural network for class discrimination. Everything is deterministic and unit-tested
(tests not included in this bundle).

## Design tenets
- **Passive monocular thermal** — no active ranging; range is only weakly observable, which shapes the
  whole estimation/control design.
- **Default-deny permission gating** — the control output is suppressed unless an explicit, separately
  authorised permission is present; the learned classifier can only *withhold* permission.
- **Separation of concerns** — perception (detection/tracking) is strictly upstream of and isolated
  from the permission logic; the classifier cannot perturb the estimated line-of-sight.

## Data flow
    thermal frame
       -> detection            (top-hat / CFAR small-object detection, motion pre-filter)
       -> association + track   (correlation lock + IMM Kalman line-of-sight estimator)
       -> class discrimination  (small CNN -> GRANT / DENY / ABSTAIN permission vote)
       -> control law           (line-of-sight-rate command, time-to-contact scheduling)
       -> command               (bounded lateral command for the camera platform)

## How to read it
- Start with `control/pipeline.py` — the orchestrator that wires the stages together each frame.
- Then `tracker/imm.py` (the interacting-multiple-model line-of-sight estimator) and
  `control/bearing_rate.py` (the line-of-sight-rate control law).
- `tracker/detect.py` + `tracker/correlation.py` are the front-end perception.
- `tracker/classify/thermal_cnn.py` is the only learned component.

## Key algorithms a reviewer may want to scrutinise
- Small-dim-object detection: top-hat morphology + CFAR-style adaptive thresholding under clutter.
- Correlation lock (MOSSE-style) for frame-to-frame association.
- Interacting-Multiple-Model (IMM) Kalman filter for the line-of-sight state (constant-velocity vs
  manoeuvre models), with consistency (NEES) checks.
- Time-to-contact (tau) from apparent-size expansion (looming), as a range-free closure cue.
- A proportional-navigation-style line-of-sight-rate control law with gain scheduling (range is
  unobservable passively, so the closure speed is scheduled, not measured).
- Passive range-observability analysis.

## Honest limitations (from our own internal analysis)
- **Range is unobservable** from a single passive thermal camera, so the control law schedules the
  closure-speed gain rather than measuring it — a documented approximation, not a true range-based law.
- **Ego-motion of the camera platform corrupts the measured line-of-sight rate** unless a
  time-synchronised inertial measurement is fused; without a hardware timestamp this is the dominant
  error term.
- Validated on synthetic scenes and a public thermal dataset; **not** yet validated on the target
  embedded hardware in a closed loop.

## What is NOT in this bundle
Hardware I/O, platform/actuator integration, the simulation harnesses, and the test suite are omitted
to keep the review focused on the algorithmic core. They can be supplied on request.

## Terminology note
Comments and docstrings have been lightly normalised to neutral, application-agnostic wording. Some
long-standing class/identifier names retain their original spellings for internal consistency; read
them as generic technical labels (e.g. a "line-of-sight" is the bearing to the tracked object).

---

## Contents

1. **Sensor / capture**
   - `vision/platform/sensor/thermal_capture.py`
2. **Detection (small dim object in thermal-IR)**
   - `vision/tracker/detect.py`
   - `vision/tracker/mti.py`
   - `vision/tracker/blob.py`
   - `vision/tracker/egomotion.py`
   - `vision/tracker/derotate.py`
3. **Tracking & estimation**
   - `vision/tracker/correlation.py`
   - `vision/tracker/imm.py`
   - `vision/tracker/track.py`
   - `vision/tracker/track_manager.py`
   - `vision/tracker/aimpoint.py`
   - `vision/tracker/los.py`
   - `vision/tracker/looming.py`
   - `vision/tracker/range_observer.py`
   - `vision/tracker/geometry.py`
   - `vision/tracker/event_channel.py`
4. **Object-class discrimination (small CNN)**
   - `vision/tracker/classify/thermal_cnn.py`
   - `vision/tracker/classify/train.py`
5. **Closed-loop line-of-sight control**
   - `vision/control/bearing_rate.py`
   - `vision/control/pipeline.py`
   - `vision/control/command_map.py`
   - `vision/control/operation_regime.py`
   - `vision/control/closed_loop.py`
   - `vision/control/pixel_loop.py`

---


# Sensor / capture


## `vision/platform/sensor/thermal_capture.py`

```python
"""Thermal camera capture (Block-3 hardware phase) -- FT640 V2 / analog-CVBS class.

The Foxeer FT640 V2 outputs an ANALOG CVBS (8-bit, AGC) thermal video stream, not USB/Y16.
On the Pi5 it is captured through a CVBS->USB grabber, which presents as a standard V4L2/UVC
device. This module turns that stream into the uint16 frames the S1 detector consumes.

Key consequences of an 8-bit AGC analog source (vs a 16-bit radiometric Boson):
  * No absolute-temperature thresholding -- but the S1 detector already uses a RELATIVE
    (percentile + MAD, top-hat) threshold, which is scale-invariant, so an 8-bit AGC frame
    cast to uint16 works directly. The AGC's per-frame contrast stretch is the one caveat.
  * Wide FOV (FT640 V2 ~48.7x38.6 deg) -> good terminal FOV retention, shorter acquisition
    range. ``ft640_intrinsics()`` carries the correct geometry (not the narrow Boson lens).

The real V4L2 path lazily imports cv2 (OpenCV) and is exercised on the Pi; tests use a
SyntheticSource so the module is verifiable without hardware or cv2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

import numpy as np

from vision.tracker.geometry import CameraIntrinsics, focal_length_from_hfov


def ft640_intrinsics(width: int = 640, height: int = 512, hfov_deg: float = 48.7) -> CameraIntrinsics:
    """Intrinsics for the FT640 V2 wide vision thermal lens (HFOV ~48.7 deg)."""
    return CameraIntrinsics(
        f_px=focal_length_from_hfov(hfov_deg, width),
        cx=width / 2.0, cy=height / 2.0, width=width, height=height,
    )


class FrameSource(Protocol):
    def read(self) -> np.ndarray | None: ...
    def close(self) -> None: ...


class SyntheticSource:
    """A deterministic frame source for tests (any HxW uint8/uint16 frames)."""

    def __init__(self, frames: Iterable[np.ndarray]) -> None:
        self._frames = list(frames)
        self._i = 0

    def read(self) -> np.ndarray | None:
        if self._i >= len(self._frames):
            return None
        f = self._frames[self._i]
        self._i += 1
        return f

    def close(self) -> None:
        pass


class V4L2Source:
    """Real V4L2/UVC capture (a CVBS->USB grabber, or any USB thermal cam). cv2 lazy-imported."""

    def __init__(self, device: int | str = 0, *, width: int | None = None,
                 height: int | None = None, fourcc: str | None = None) -> None:
        try:
            import cv2  # type: ignore
        except ImportError as exc:  # pragma: no cover - hardware path
            raise RuntimeError("opencv-python is required for live capture (pip install opencv-python)") from exc
        self._cv2 = cv2
        self._cap = cv2.VideoCapture(device)
        if not self._cap.isOpened():  # pragma: no cover - hardware path
            raise RuntimeError(f"could not open capture device {device!r}")
        # ORDER MATTERS on V4L2 grabbers (e.g. MacroSilicon MS2109): set FOURCC first,
        # else cv2 negotiates the default (YUYV, low-res) and silently ignores the size.
        if fourcc:
            self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        if width:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height:
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def read(self) -> np.ndarray | None:  # pragma: no cover - hardware path
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:  # pragma: no cover - hardware path
        self._cap.release()


@dataclass(frozen=True)
class CaptureConfig:
    roi: tuple[int, int, int, int] | None = None   # (x, y, w, h) active thermal area in the grabbed frame
    deinterlace: bool = False                       # CVBS is interlaced; take even field if True
    invert: bool = False                            # set True for a black-hot palette (hot = dark)
    out_width: int = 640
    out_height: int = 512


class ThermalCapture:
    """Adapts a FrameSource into the uint16 frames the S1 detector expects."""

    def __init__(self, source: FrameSource, config: CaptureConfig | None = None) -> None:
        self.source = source
        self.cfg = config or CaptureConfig()

    def frame_u16(self) -> np.ndarray | None:
        raw = self.source.read()
        if raw is None:
            return None
        g = self._to_gray(raw)
        if self.cfg.roi is not None:
            x, y, w, h = self.cfg.roi
            g = g[y:y + h, x:x + w]
        if self.cfg.deinterlace:
            g = g[::2]                                   # keep even field; halves vertical res
        g = self._resize(g, self.cfg.out_width, self.cfg.out_height)
        if self.cfg.invert:
            g = 255.0 - g.astype(np.float64)             # 8-bit AGC palette flip
        return np.clip(g, 0, 65535).astype(np.uint16)

    @staticmethod
    def _to_gray(raw: np.ndarray) -> np.ndarray:
        if raw.ndim == 3:                                # BGR/YUV from the grabber -> luminance
            return raw.astype(np.float64).mean(axis=2)
        return raw.astype(np.float64)

    def _resize(self, g: np.ndarray, w: int, h: int) -> np.ndarray:
        if g.shape == (h, w):
            return g
        try:
            import cv2  # type: ignore
            return cv2.resize(g, (w, h), interpolation=cv2.INTER_AREA)
        except ImportError:                              # cv2-free nearest-neighbour fallback
            ys = (np.linspace(0, g.shape[0] - 1, h)).astype(int)
            xs = (np.linspace(0, g.shape[1] - 1, w)).astype(int)
            return g[np.ix_(ys, xs)]

    def close(self) -> None:
        self.source.close()

```


# Detection (small dim object in thermal-IR)


## `vision/tracker/detect.py`

```python
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
#: it never feeds control, so spending a flood-fill on all ~20 blobs/frame is wasted latency.
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
#: a 1-2 px point target; the largest catches a small extended object a few px across.
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
#: hot pixels that are not physically consistent with a object target.
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

```


## `vision/tracker/mti.py`

```python
"""Moving-Target Indication (MTI) for look-down -- the master clutter discriminator.

Looking DOWN, a small object is NOT the brightest thing; it is the thing that moves
INDEPENDENTLY of the ground.  But the ground also moves in the image because the
vehicle moves (ego-motion + parallax).  So:

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

```


## `vision/tracker/blob.py`

```python
"""Shared data contracts for the thermal tracker perception layer (S1).

``ThermalBlob`` is the elementary detector output for one connected component.
``TargetObservation`` bundles the per-frame list of blobs together with frame
metadata so that the downstream track FSM and control law can consume a single
typed object.

The ``SCHEMA`` constant names the contract version used for serialisation and
downstream validation (mirrors the naming convention in
``detector_output.py`` / Block-01).

Design notes
------------
* ``centroid_px`` is an **intensity-weighted sub-pixel centroid** (first-moment
  of raw counts), NOT the bbox centre.  This is the primary LOS measurement.
* ``cam_temp_c`` and ``ffc_state`` are passed through from the camera telemetry
  layer.  The adaptive threshold in ``detect.py`` re-bases itself on FFC
  transitions, so downstream code can track whether the current threshold
  baseline is fresh or stale.
* ``snr`` is defined as ``(peak_counts - background_mean) / background_std``
  computed over the top-hat residual image — a self-consistent within-frame SNR
  that does not depend on absolute count calibration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── contract version ──────────────────────────────────────────────────────────

SCHEMA: str = "vision_thermal_blob_sequence.v1"

#: Schema description used by downstream consumers for schema validation and
#: documentation.  The dict is intentionally minimal — add fields here as the
#: contract evolves.
SCHEMA_DESCRIPTOR: dict[str, Any] = {
    "schema": SCHEMA,
    "description": (
        "Per-frame sequence of thermal blobs detected by the S1 CV pipeline "
        "(top-hat + adaptive relative threshold + connected components). "
        "Designed for a non-radiometric FLIR Boson 640 Y16 source where raw "
        "counts drift with camera housing temperature and must be re-based "
        "after each FFC (flat-field calibration) shutter event."
    ),
    "fields": {
        "centroid_px": "(float, float) — intensity-weighted sub-pixel centroid in image coordinates (x, y)",
        "area_px": "int — area of the blob in pixels (number of connected pixels above threshold)",
        "peak_counts": "int — maximum raw count value within the blob",
        "mean_counts": "float — mean raw count value within the blob",
        "snr": (
            "float — signal-to-noise ratio: (peak_counts - bg_mean) / bg_std "
            "where bg statistics come from the top-hat residual image"
        ),
        "bbox": "(x, y, w, h) — bounding box in image pixels (top-left origin, integer pixel grid)",
        "frame_id": "int — monotonically increasing frame counter from capture thread",
        "t_capture_ns": "int | None — CLOCK_MONOTONIC capture timestamp in nanoseconds, or None if unavailable",
        "cam_temp_c": "float — camera housing temperature in degrees Celsius (from serial/SLA telemetry)",
        "ffc_state": (
            "str — FFC (flat-field calibration) state of the camera: "
            "'READY' | 'FREEZE' | 'RECOVERING'.  "
            "'FREEZE' means the camera shutter has fired and raw counts are "
            "unreliable; the threshold baseline must be re-set on the "
            "subsequent 'READY' transition."
        ),
    },
    "ffc_states": ["READY", "FREEZE", "RECOVERING"],
    "salience_sort": "Blobs are returned sorted descending by (snr * area_px) salience score.",
}


# ── primary detector product ───────────────────────────────────────────────────

@dataclass(frozen=True)
class ThermalBlob:
    """One connected hot region detected in a single thermal frame.

    All coordinate values are in pixel space (origin = top-left of image).
    ``centroid_px`` is the primary LOS angular-error proxy.

    Attributes
    ----------
    centroid_px:
        Intensity-weighted sub-pixel centroid ``(x, y)``.
    area_px:
        Number of connected pixels above the adaptive threshold.
    peak_counts:
        Maximum raw Y16 count within the blob.
    mean_counts:
        Mean raw Y16 count within the blob.
    snr:
        Within-frame SNR computed from the top-hat residual image.
        Dimensionless.  Higher = more salient.
    bbox:
        Bounding box ``(x, y, w, h)`` in integer pixel grid coordinates.
    frame_id:
        Monotonically increasing frame counter.
    t_capture_ns:
        CLOCK_MONOTONIC capture timestamp in nanoseconds, or ``None``.
    cam_temp_c:
        Camera housing temperature in °C from serial/SLA telemetry.  Used by
        the adaptive threshold to track count-level drift across cam-temp
        changes.
    ffc_state:
        FFC state string.  One of ``'READY'``, ``'FREEZE'``, ``'RECOVERING'``.
    """

    centroid_px: tuple[float, float]
    area_px: int
    peak_counts: int
    mean_counts: float
    snr: float
    bbox: tuple[int, int, int, int]   # (x, y, w, h)
    frame_id: int
    t_capture_ns: int | None
    cam_temp_c: float
    ffc_state: str
    # Extended (un-suppressed) half-max footprint in a bounded window around the centroid.
    # Unlike area_px (which the top-hat suppresses for large/extended targets), this GROWS
    # with the true target size -> a reliable looming / endgame-subtense signal at short range.
    area_extended_px: int = 0

    # ── derived ---------------------------------------------------------------

    @property
    def salience(self) -> float:
        """Composite salience score used for sorting.  Higher = more target-like."""
        return self.snr * float(self.area_px)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "centroid_px": list(self.centroid_px),
            "area_px": self.area_px,
            "peak_counts": self.peak_counts,
            "mean_counts": round(self.mean_counts, 3),
            "snr": round(self.snr, 4),
            "bbox": list(self.bbox),
            "frame_id": self.frame_id,
            "t_capture_ns": self.t_capture_ns,
            "cam_temp_c": round(self.cam_temp_c, 2),
            "ffc_state": self.ffc_state,
        }


# ── per-frame detector output ─────────────────────────────────────────────────

@dataclass
class TargetObservation:
    """Per-frame output of the S1 detection pipeline.

    Contains the ordered list of detected blobs (sorted descending by
    salience), plus frame-level metadata.  Downstream consumers (track FSM,
    control law) consume this type directly.

    Attributes
    ----------
    frame_id:
        Monotonically increasing frame counter.
    t_capture_ns:
        CLOCK_MONOTONIC capture timestamp in nanoseconds, or ``None``.
    cam_temp_c:
        Camera housing temperature in °C.
    ffc_state:
        FFC state at the time of this frame.  Used by the threshold state
        machine to decide when to re-base the adaptive baseline.
    blobs:
        Detected blobs, sorted descending by ``salience``.  Empty list if no
        blobs were detected (clean frame).
    threshold_baseline_counts:
        The adaptive threshold value (in top-hat residual counts) that was
        applied to produce this observation.  Logged for diagnostics.
    detection_budget_ms:
        Wall-clock time (milliseconds) taken by the CV pipeline for this frame.
        Used by the overrun monitor in the real-time loop.
    schema:
        Schema identifier; always ``SCHEMA``.
    """

    frame_id: int
    t_capture_ns: int | None
    cam_temp_c: float
    ffc_state: str
    blobs: list[ThermalBlob] = field(default_factory=list)
    threshold_baseline_counts: float = 0.0
    detection_budget_ms: float = 0.0
    schema: str = SCHEMA

    # ── convenience -----------------------------------------------------------

    @property
    def best_blob(self) -> ThermalBlob | None:
        """Return the highest-salience blob, or ``None`` if the frame is empty."""
        return self.blobs[0] if self.blobs else None

    @property
    def is_ffc_freeze(self) -> bool:
        """True when the camera shutter has fired and pixel data is unreliable.

        Covers both FREEZE (shutter closed) and RECOVERING (NUC tables being
        reloaded) so that both phases take the FFC coast path in the tracker
        and do NOT consume the normal missed-frame budget.
        """
        return self.ffc_state in ("FREEZE", "RECOVERING")

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "schema": self.schema,
            "frame_id": self.frame_id,
            "t_capture_ns": self.t_capture_ns,
            "cam_temp_c": round(self.cam_temp_c, 2),
            "ffc_state": self.ffc_state,
            "blobs": [b.to_dict() for b in self.blobs],
            "threshold_baseline_counts": round(self.threshold_baseline_counts, 2),
            "detection_budget_ms": round(self.detection_budget_ms, 3),
        }

```


## `vision/tracker/egomotion.py`

```python
"""Ego-motion estimation: gyro de-rotation + optional sparse LK residual.

PURPOSE
-------
A fast-rotating vision body (100–1000 °/s) creates a large phantom LOS-rate
(dλ/dt) in the image plane.  This module removes that ego-rotation so that
downstream LOS tracking sees only the TRUE target angular motion.

The design mandates (§3.2):
    "gyro-only is the BASE mode; sparse-LK is a BONUS only when texture exists"
Textureless night sky → KLT will have no corners → return None → gyro-only.
This is NORMAL, not an error.

GYRO DE-ROTATION CONVENTION
-----------------------------
Body-frame angular rate omega = [omega_x, omega_y, omega_z] in rad/s:
    omega_x — pitch rate (right-hand rule about camera +X = rightward axis)
    omega_y — yaw rate   (right-hand rule about camera +Y = upward axis)
    omega_z — ROLL rate  (right-hand rule about camera +Z = out-of-boresight)

Image-plane prediction of scene shift due to body rotation (small-angle,
matches design §3.2 exactly):
    dx_px ≈ -f · omega_y · dt     (yaw moves scene horizontally)
    dy_px ≈ -f · omega_x · dt     (pitch moves scene vertically, image-y down)
    roll_rad ≈  omega_z · dt       (roll rotates image about principal point)

ROLL-INDUCED TARGET SHIFT (FIX 2026-06-17)
--------------------------------------------
For an off-boresight target at pixel offset (dx_t, dy_t) = (px - cx, py - cy)
from the principal point, body roll omega_z causes a tangential shift in-image:

    dx_roll = -omega_z · dt · dy_t   (right-hand small-angle rotation)
    dy_roll = +omega_z · dt · dx_t

Geometry: roll omega_z > 0 rotates the scene CCW about the principal point
(in standard math convention; CW in display coords with y-down).  The tangent
to a circle of radius r at angle θ is (-sin θ, cos θ).  With
(dx_t, dy_t) = r·(cos θ, sin θ):
    tangential shift = omega_z·dt · (-dy_t, +dx_t)

This shift is ZERO for a target exactly at the principal point (boresight) but
grows linearly with target offset.  It is TARGET-POSITION-AWARE.

Implementation: gyro_derotation accepts an optional target_offset_px argument.
When provided, the roll contribution is added to shift_px.  This is called from
los.py where the target pixel centroid is known.

SIGN DERIVATION (translation terms):
    Consider omega_y > 0 (body yaws nose-RIGHT in the camera's convention where
    +Y is upward).  The scene appears to shift LEFT in image coordinates
    (stars move toward smaller px).  We want the SCENE shift:
        dx_px = -f · omega_y · dt   (rightward boresight rotation shifts scene LEFT)
        dy_px = -f · omega_x · dt   (upward pitch shifts scene down → dy > 0 in image)
    This implements the design formula verbatim from §3.2:
        «dx_px ≈ −f·ω_y·dt, dy_px ≈ −f·ω_x·dt»

EgoEstimate QUALITY
-------------------
quality is defined as a scalar in [0, 1]:
    1.0  — gyro-only (trusted when gyro calibration is good)
    0.6..1.0 — gyro+KLT (KLT cross-check available)
    Lower values indicate potential degradation (too few KLT inliers).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt

from .geometry import CameraIntrinsics

# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EgoEstimate:
    """Per-frame ego-motion estimate.

    Attributes
    ----------
    shift_px:
        Predicted scene shift (dx, dy) in image pixels caused by the
        vehicle's own rotation.  This is the shift that needs to be
        SUBTRACTED from observed pixel motion to get the target's true motion.
    roll_rad:
        Predicted in-image-plane rotation (radians) about the principal point.
        Positive = CCW rotation in standard math convention.
    source:
        ``'gyro'``    — shift from gyro de-rotation only (normal base mode).
        ``'gyro+klt'``— gyro + KLT residual cross-check.
    quality:
        Scalar in [0, 1].  Higher = more trustworthy.
        Gyro-only = 1.0 by default (degrade if gyro is flagged unhealthy).
        KLT cross-check improves or validates the estimate.
    n_inliers:
        Number of KLT RANSAC inliers.  0 for gyro-only.
    """

    shift_px: tuple[float, float]
    roll_rad: float
    source: Literal["gyro", "gyro+klt"]
    quality: float
    n_inliers: int


# ---------------------------------------------------------------------------
# Gyro de-rotation
# ---------------------------------------------------------------------------

def gyro_derotation(
    omega_xyz_radps: tuple[float, float, float],
    dt: float,
    intrinsics: CameraIntrinsics,
) -> EgoEstimate:
    """Predict the scene shift from body angular rate (gyro de-rotation).

    This is the BASE ego-motion path.  It runs in ~0.05 ms and requires no
    texture in the scene.  Per design §3.2, gyro-only is the normal operating
    mode on a textureless night sky.

    Parameters
    ----------
    omega_xyz_radps:
        Body angular rate (omega_x, omega_y, omega_z) in rad/s.
        Convention: right-hand rule, body +X rightward, body +Y upward,
        body +Z out-of-boresight.
            omega_x — pitch rate
            omega_y — yaw rate
            omega_z — ROLL rate (in-plane image rotation about boresight)
    dt:
        Time elapsed since the previous frame (seconds).
    intrinsics:
        Camera intrinsic parameters (focal length in pixels).

    Returns
    -------
    EgoEstimate
        source='gyro', quality=1.0, n_inliers=0.
        shift_px = (-f·omega_y·dt, -f·omega_x·dt)  [translation terms only].
        roll_rad = omega_z · dt  [stored for LOSComputer to apply roll correction].

    The ROLL correction (omega_z-induced tangential shift for an off-axis target)
    is NOT applied here because it is target-position-dependent.  It is applied
    in LOSComputer.update(), which knows the target pixel at each frame.

    Sign convention (verbatim from design §3.2):
        dx_px ≈ -f · omega_y · dt          (translation from yaw)
        dy_px ≈ -f · omega_x · dt          (translation from pitch)
        roll  =  omega_z · dt              (positive = CCW body rotation in math coords)
    """
    ox, oy, oz = omega_xyz_radps
    f = intrinsics.f_px

    # Translation terms from pitch (ox) and yaw (oy) only.
    # Roll (oz) is stored in roll_rad; the per-target tangential correction
    # is computed in LOSComputer.update() using the target's pixel offset.
    dx = -f * oy * dt
    dy = -f * ox * dt
    roll = oz * dt

    return EgoEstimate(
        shift_px=(dx, dy),
        roll_rad=roll,
        source="gyro",
        quality=1.0,
        n_inliers=0,
    )


# ---------------------------------------------------------------------------
# Sparse Lucas-Kanade residual (optional, texture-dependent)
# ---------------------------------------------------------------------------

#: Minimum number of KLT inliers to trust the LK estimate over gyro-only.
#: Below this threshold → return None → use gyro-only.
_MIN_INLIERS: int = 12


def sparse_lk_residual(
    prev_frame: npt.NDArray[np.uint16 | np.float32],
    cur_frame: npt.NDArray[np.uint16 | np.float32],
    target_mask: npt.NDArray[np.bool_] | None,
    *,
    max_corners: int = 80,
    min_distance_px: int = 10,
    quality_level: float = 0.01,
) -> EgoEstimate | None:
    """Estimate scene shift from sparse Lucas-Kanade optical flow.

    Runs Shi-Tomasi corner detection on the COLD BACKGROUND (target masked out),
    then Lucas-Kanade pyramidal tracking, then RANSAC 2-DOF (translation-only)
    similarity to extract the consensus shift.

    Returns ``None`` when inliers < ``_MIN_INLIERS`` — this is the NORMAL result
    on a textureless night sky and the caller falls back to gyro-only.

    OpenCV is used if importable; otherwise a numpy phase-correlation fallback is
    applied (less accurate but still useful as a cross-check).

    Parameters
    ----------
    prev_frame, cur_frame:
        Previous and current frames as uint16 or float32 arrays of shape (H, W).
    target_mask:
        Boolean mask (H, W), True where the target/hot blob is located.
        Corners within this region are excluded so the target's OWN motion does
        not corrupt the background ego estimate.  Pass ``None`` to use the full
        frame (e.g., for synthetic tests without a salient target).
    max_corners:
        Maximum number of Shi-Tomasi corners to track.
    min_distance_px:
        Minimum distance between detected corners in pixels.
    quality_level:
        Shi-Tomasi quality level for ``goodFeaturesToTrack``.

    Returns
    -------
    EgoEstimate | None
        Returns ``None`` when the LK result is unreliable (< 12 inliers).
        Returns an ``EgoEstimate`` with source='gyro+klt' on success.
    """
    try:
        return _sparse_lk_opencv(
            prev_frame, cur_frame, target_mask,
            max_corners=max_corners,
            min_distance_px=min_distance_px,
            quality_level=quality_level,
        )
    except ImportError:
        return _phase_correlation_fallback(prev_frame, cur_frame, target_mask)


def _sparse_lk_opencv(
    prev_frame: npt.NDArray,
    cur_frame: npt.NDArray,
    target_mask: npt.NDArray[np.bool_] | None,
    *,
    max_corners: int,
    min_distance_px: int,
    quality_level: float,
) -> EgoEstimate | None:
    """Sparse LK via cv2.  Raises ImportError if cv2 is not available."""
    import cv2  # type: ignore[import]  # not a hard dependency

    prev_u8 = _to_uint8(prev_frame)
    cur_u8 = _to_uint8(cur_frame)

    # Detection mask: exclude the target region
    detect_mask: npt.NDArray[np.uint8] | None = None
    if target_mask is not None:
        detect_mask = (~target_mask).astype(np.uint8) * 255

    corners = cv2.goodFeaturesToTrack(
        prev_u8,
        maxCorners=max_corners,
        qualityLevel=quality_level,
        minDistance=float(min_distance_px),
        mask=detect_mask,
    )

    if corners is None or len(corners) < 4:
        return None  # no texture → gyro-only (normal on night sky)

    # LK tracking
    lk_params = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.03),
    )
    corners_tracked, status, _ = cv2.calcOpticalFlowPyrLK(
        prev_u8, cur_u8, corners, None, **lk_params
    )

    if status is None:
        return None

    good_prev = corners[status.ravel() == 1]
    good_cur = corners_tracked[status.ravel() == 1]  # type: ignore[index]

    if len(good_prev) < _MIN_INLIERS:
        return None

    # RANSAC 2-DOF similarity (translation only — rotation handled separately)
    # We estimate a pure translation consensus with RANSAC.
    displacements = good_cur.reshape(-1, 2) - good_prev.reshape(-1, 2)

    inlier_mask, (dx, dy, roll) = _ransac_translation(
        displacements, n_iters=100, inlier_tol_px=1.5
    )
    n_inliers = int(np.sum(inlier_mask))

    if n_inliers < _MIN_INLIERS:
        return None

    # Quality: fraction of tracked corners that were inliers
    quality = min(1.0, 0.6 + 0.4 * (n_inliers / max(len(good_prev), 1)))

    return EgoEstimate(
        shift_px=(float(dx), float(dy)),
        roll_rad=float(roll),
        source="gyro+klt",
        quality=quality,
        n_inliers=n_inliers,
    )


def _phase_correlation_fallback(
    prev_frame: npt.NDArray,
    cur_frame: npt.NDArray,
    target_mask: npt.NDArray[np.bool_] | None,
) -> EgoEstimate | None:
    """Numpy-only phase correlation fallback when cv2 is not available.

    Phase correlation is inherently global and does not respect the target mask,
    but it provides a useful first-order ego estimate on textured scenes.
    Returns None (gyro-only) when the scene is too textureless for a reliable
    peak.  Roll is not estimated (set to 0.0).

    This path is explicitly the cv2-unavailable fallback; its accuracy is lower
    than LK.  The gyro remains the trusted base.
    """
    prev_f = prev_frame.astype(np.float32)
    cur_f = cur_frame.astype(np.float32)

    # Zero-out target region if provided (avoid target biasing the shift)
    if target_mask is not None:
        prev_f[target_mask] = float(np.mean(prev_f[~target_mask]))
        cur_f[target_mask] = float(np.mean(cur_f[~target_mask]))

    # Phase correlation via FFT
    F_prev = np.fft.fft2(prev_f)
    F_cur = np.fft.fft2(cur_f)
    cross_power = F_prev * np.conj(F_cur)
    denom = np.abs(cross_power) + 1e-10
    cross_power_norm = cross_power / denom
    correlation = np.fft.ifft2(cross_power_norm).real

    # Find peak
    peak_loc = np.unravel_index(np.argmax(correlation), correlation.shape)
    H, W = prev_f.shape
    dy_raw = float(peak_loc[0])
    dx_raw = float(peak_loc[1])

    # Wrap shifts: phase correlation gives [0, N) but the actual shift is in (-N/2, N/2)
    if dy_raw > H / 2:
        dy_raw -= H
    if dx_raw > W / 2:
        dx_raw -= W

    # Assess peak sharpness as a quality proxy
    peak_val = float(correlation[peak_loc])
    sorted_vals = np.sort(correlation.ravel())[::-1]
    second_val = float(sorted_vals[1]) if len(sorted_vals) > 1 else 0.0
    peak_ratio = peak_val / (second_val + 1e-10)

    if peak_ratio < 2.0:
        # Weak peak → insufficient texture → gyro-only
        return None

    # Synthetic inlier count: not meaningful for phase-corr, but mark the source
    quality = min(1.0, 0.6 + 0.1 * math.log(max(peak_ratio, 1.0)))
    # Phase correlation is treated as a rough check — use a conservative quality
    quality = min(quality, 0.75)

    return EgoEstimate(
        shift_px=(dx_raw, dy_raw),
        roll_rad=0.0,  # phase correlation does not recover roll
        source="gyro+klt",
        quality=quality,
        n_inliers=_MIN_INLIERS,  # signal that inlier count is met (nominally)
    )


# ---------------------------------------------------------------------------
# RANSAC translation estimator
# ---------------------------------------------------------------------------

def _ransac_translation(
    displacements: npt.NDArray[np.float32],
    *,
    n_iters: int = 100,
    inlier_tol_px: float = 1.5,
) -> tuple[npt.NDArray[np.bool_], tuple[float, float, float]]:
    """RANSAC consensus translation from a set of 2-D displacement vectors.

    Parameters
    ----------
    displacements:
        Shape (N, 2) array of (dx, dy) vectors from point tracking.
    n_iters:
        Number of RANSAC iterations.
    inlier_tol_px:
        Inlier threshold in pixels.

    Returns
    -------
    (inlier_mask, (dx, dy, roll))
        ``inlier_mask`` is a boolean array of shape (N,).
        ``dx, dy`` is the consensus translation.
        ``roll`` is always 0.0 (not estimated here — left to the similarity
        model in a future extension).
    """
    rng = np.random.default_rng(0)  # deterministic for reproducibility
    n = len(displacements)
    if n == 0:
        return np.zeros(0, dtype=bool), (0.0, 0.0, 0.0)

    best_mask = np.zeros(n, dtype=bool)
    best_count = 0

    for _ in range(n_iters):
        idx = int(rng.integers(0, n))
        dx_hyp = displacements[idx, 0]
        dy_hyp = displacements[idx, 1]

        residuals = np.sqrt(
            (displacements[:, 0] - dx_hyp) ** 2
            + (displacements[:, 1] - dy_hyp) ** 2
        )
        mask = residuals < inlier_tol_px
        count = int(np.sum(mask))

        if count > best_count:
            best_count = count
            best_mask = mask

    if best_count > 0:
        dx_final = float(np.median(displacements[best_mask, 0]))
        dy_final = float(np.median(displacements[best_mask, 1]))
    else:
        dx_final = float(np.median(displacements[:, 0]))
        dy_final = float(np.median(displacements[:, 1]))
        best_mask = np.ones(n, dtype=bool)

    return best_mask, (dx_final, dy_final, 0.0)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _to_uint8(frame: npt.NDArray) -> npt.NDArray[np.uint8]:
    """Normalise a frame to uint8 for OpenCV processing."""
    f = frame.astype(np.float32)
    f_min = f.min()
    f_max = f.max()
    if f_max <= f_min:
        return np.zeros_like(f, dtype=np.uint8)
    scale = 255.0 / (f_max - f_min)
    return ((f - f_min) * scale).astype(np.uint8)

```


## `vision/tracker/derotate.py`

```python
"""Ego-motion de-rotation primitive (extracted from los.py for reuse).

Given a raw camera pixel and the CUMULATIVE ego (translational shift from pitch/yaw + the
cumulative roll angle), recover the target's pixel in the un-rotated, un-translated WORLD
frame. The simulator forms the image as rotate-by-cum_roll THEN translate-by-cum_ego; this
inverts both. Kept as a pure function so the LOS path (los.py) and the future synthetic-event
motion channel (R6) share ONE verified de-rotation -- bit-identical to the prior inline math.
"""

from __future__ import annotations

import math


def world_pixel(
    px: float, py: float,
    cum_ego_x: float, cum_ego_y: float, cum_roll_rad: float,
    cx: float, cy: float,
) -> tuple[float, float]:
    """Map camera pixel ``(px, py)`` to its world-frame pixel, removing cumulative ego.

    Steps (identical to the formula previously inlined in ``LOSComputer.update``):
        dx_t = (px - cx) - cum_ego_x ;  dy_t = (py - cy) - cum_ego_y   (remove pitch/yaw shift)
        dx_w = dx_t*cos - dy_t*sin   ;  dy_w = dx_t*sin + dy_t*cos      (invert the roll rotation)
        world = (cx + dx_w, cy + dy_w)
    """
    c_th = math.cos(cum_roll_rad)
    s_th = math.sin(cum_roll_rad)
    dx_t = (px - cx) - cum_ego_x
    dy_t = (py - cy) - cum_ego_y
    dx_w = dx_t * c_th - dy_t * s_th
    dy_w = dx_t * s_th + dy_t * c_th
    return cx + dx_w, cy + dy_w

```


# Tracking & estimation


## `vision/tracker/correlation.py`

```python
"""R8: MOSSE correlation channel -- a structural track confined to the IMM gate.

The detector+association+centroid spine is the literature's MOST FRAGILE family for our closing
endgame (top-hat suppresses the resolved body, the centroid walks onto the AGC-saturating hot
pixel).  A correlation filter holds STRUCTURE through that transition.  We run a lightweight
MOSSE (Bolme 2010) filter on a small chip in the IMM gate and expose:

  * a PEAK-TO-SIDELOBE RATIO (PSR) -- an image-space track-health confidence, and
  * the response-peak OFFSET -- a structural position for RE-DETECTING the SAME track.

DOCTRINE (Inv 2): the PSR is a QUALITY signal and feeds lock-quality / activate-permission ONLY;
the structural offset is used for same-track re-detection (Inv 7), NOT to move the live aimpoint
-- the geometric centroid remains the LOS source.  A FEAR dual template keeps an IMMUTABLE LOBL
reference (the confirmed target) alongside a slow-adapting dynamic filter, so appearance drift
can never walk the structural track off the originally-confirmed target.

Pure-numpy FFT; the chip is small (default 32x32) so the whole channel fits the per-frame budget.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
from scipy import ndimage as ndi


def extract_chip(frame: npt.NDArray[np.uint16], cx: float, cy: float,
                 size: int = 32) -> npt.NDArray[np.float64]:
    """Crop a ``size x size`` chip centred on ``(cx, cy)``, zero-padded at the frame border."""
    n = int(size)
    h2 = n // 2
    h, w = frame.shape
    x0, y0 = int(round(cx)) - h2, int(round(cy)) - h2
    chip = np.zeros((n, n), dtype=np.float64)
    fx0, fy0 = max(0, x0), max(0, y0)
    fx1, fy1 = min(w, x0 + n), min(h, y0 + n)
    if fx1 > fx0 and fy1 > fy0:
        chip[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0] = frame[fy0:fy1, fx0:fx1]
    return chip


def warp_chip(chip: npt.NDArray[np.float64], content_scale: float,
              angle_rad: float = 0.0) -> npt.NDArray[np.float64]:
    """R9 anticipatory pre-warp: scale (+rotate) a chip's content about its centre.

    ``content_scale`` > 1 MAGNIFIES the content (zoom in); < 1 shrinks it.  The pipeline shrinks a
    closing (grown) target back toward the template scale by content_scale = exp(-dt/tau) using the
    range-free looming tau, and rotates by the IMM cross-LOS aspect rate -- so the correlation runs
    against a SCALE/ASPECT-PREDICTED appearance and the structural residual stays small exactly when
    raw appearance changes fastest.  Confidence-gated by the caller (falls back to the immutable
    template when tau confidence is low).
    """
    n = chip.shape[0]
    c = (n - 1) / 2.0
    s = max(float(content_scale), 1e-3)
    cos, sin = math.cos(angle_rad), math.sin(angle_rad)
    matrix = np.array([[cos, -sin], [sin, cos]], dtype=np.float64) / s
    offset = np.array([c, c]) - matrix @ np.array([c, c])
    return ndi.affine_transform(chip.astype(np.float64), matrix, offset=offset, order=1, mode="nearest")


def _cosine_window(n: int) -> npt.NDArray[np.float64]:
    w = np.hanning(n)
    return np.outer(w, w)


def _gaussian_peak(n: int, sigma: float) -> npt.NDArray[np.float64]:
    """Desired correlation output: a centred unit Gaussian (peak at the chip centre)."""
    ax = np.arange(n) - n // 2
    xx, yy = np.meshgrid(ax, ax)
    g = np.exp(-(xx ** 2 + yy ** 2) / (2.0 * sigma ** 2))
    return g / (g.sum() + 1e-12)


class MosseFilter:
    """One MOSSE correlation filter (online-adaptable)."""

    def __init__(self, size: int = 32, sigma: float = 2.0, lr: float = 0.125, eps: float = 1e-3) -> None:
        self._n = int(size)
        self._lr = float(lr)
        self._eps = float(eps)
        self._win = _cosine_window(self._n)
        self._G = np.fft.fft2(_gaussian_peak(self._n, sigma))
        self._num: npt.NDArray[np.complex128] | None = None   # G * conj(F)
        self._den: npt.NDArray[np.complex128] | None = None   # F * conj(F)

    @property
    def initialized(self) -> bool:
        return self._num is not None

    def _preprocess(self, patch: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        p = np.log(np.maximum(patch.astype(np.float64), 1.0))   # log -> AGC/illumination robust
        p = (p - p.mean()) / (p.std() + self._eps)              # normalise
        return p * self._win                                    # cosine window (cutoff edge effects)

    def init(self, chip: npt.NDArray[np.float64]) -> None:
        F = np.fft.fft2(self._preprocess(chip))
        self._num = self._G * np.conj(F)
        self._den = F * np.conj(F)

    def update(self, chip: npt.NDArray[np.float64]) -> None:
        """Online-adapt the filter toward the new appearance (skip for an immutable reference)."""
        if self._num is None:
            self.init(chip)
            return
        F = np.fft.fft2(self._preprocess(chip))
        self._num = (1.0 - self._lr) * self._num + self._lr * (self._G * np.conj(F))
        self._den = (1.0 - self._lr) * self._den + self._lr * (F * np.conj(F))

    def correlate(self, chip: npt.NDArray[np.float64]) -> tuple[float, float, float]:
        """Return (dx, dy, psr): peak offset from the chip centre (px) and peak-to-sidelobe ratio."""
        assert self._num is not None and self._den is not None
        H = self._num / (self._den + self._eps)
        F = np.fft.fft2(self._preprocess(chip))
        # The desired output G is already centred at n//2, so the response peak sits at the chip
        # centre for the trained patch and shifts with target motion -- no fftshift needed.
        resp = np.real(np.fft.ifft2(H * F))
        py, px = np.unravel_index(int(np.argmax(resp)), resp.shape)
        psr = _psr(resp, (py, px))
        return float(px - self._n // 2), float(py - self._n // 2), psr


def _psr(resp: npt.NDArray[np.float64], peak: tuple[int, int], exclude: int = 5) -> float:
    """Peak-to-sidelobe ratio: (peak - sidelobe_mean) / sidelobe_std, excluding an 11x11 window."""
    py, px = peak
    pk = float(resp[py, px])
    mask = np.ones_like(resp, dtype=bool)
    y0, y1 = max(0, py - exclude), min(resp.shape[0], py + exclude + 1)
    x0, x1 = max(0, px - exclude), min(resp.shape[1], px + exclude + 1)
    mask[y0:y1, x0:x1] = False
    side = resp[mask]
    return (pk - float(side.mean())) / (float(side.std()) + 1e-6)


class CorrelationChannel:
    """FEAR dual-filter wrapper: an IMMUTABLE LOBL reference + a slow-adapting dynamic filter.

    ``confidence()`` returns the max PSR of the two; ``offset()`` returns the dynamic-filter peak
    offset (for same-track re-detection).  The immutable reference anchors the structural track to
    the originally-confirmed target so adaptation drift cannot walk it off (Inv 7).
    """

    def __init__(self, size: int = 32, dynamic_lr: float = 0.125) -> None:
        self._size = int(size)
        self._ref = MosseFilter(size=size, lr=0.0)       # immutable LOBL reference (never adapts)
        self._dyn = MosseFilter(size=size, lr=dynamic_lr)
        self._seeded = False

    @property
    def seeded(self) -> bool:
        return self._seeded

    def seed(self, chip: npt.NDArray[np.float64]) -> None:
        self._ref.init(chip)
        self._dyn.init(chip)
        self._seeded = True

    def measure(self, chip: npt.NDArray[np.float64], *, adapt: bool = True) -> tuple[float, float, float]:
        """Return (dx, dy, confidence_psr) for the chip; optionally adapt the dynamic filter."""
        dx, dy, psr_dyn = self._dyn.correlate(chip)
        _, _, psr_ref = self._ref.correlate(chip)
        if adapt:
            self._dyn.update(chip)
        return dx, dy, max(psr_dyn, psr_ref)

```


## `vision/tracker/imm.py`

```python
"""Body-frame IMM (Interacting Multiple Model) filter for LOS tracking.

STATE VECTOR
------------
x = [az, el, az_rate, el_rate]  (4-D)
    az, el        — bearing in radians
    az_rate, el_rate — LOS angular rate in rad/s

TWO MODES
---------
Mode 0: CV (Constant Velocity)
    Target moves at constant angular velocity.
    Low process noise — trusts the prediction.
    Appropriate for steady approach geometry.

Mode 1: MANEUVER (Singer model / high process noise)
    Target may jink/manoeuvre.
    High process noise — trusts the measurement.
    Appropriate for evasive targets.

IMM ALGORITHM (standard formulation)
-------------------------------------
At each step:
    1. Mode-mixing: compute mixed initial conditions for each mode filter,
       using the current mode probability weights.
    2. Mode-matched Kalman update: run a separate Kalman prediction+update
       for each mode.
    3. Mode-probability update: update mode probabilities from the likelihood
       of each mode's innovation.
    4. Combined estimate: weighted sum of mode estimates (mean + covariance).

INNOVATION GATING (CRITICAL — read carefully)
----------------------------------------------
The design §3.2 states:
    "innovations are gated against the gyro-predicted motion so a de-rotation error does not look like object manoeuvre"

Implementation:
    The raw measured LOS-rate (az_rate_meas, el_rate_meas) from los.py has
    already had the ego-rotation subtracted.  However, there can be a residual
    ego error if the cam↔IMU time-sync is imperfect or the soft-mount transfers
    differently.

    We gate the INNOVATION (z - H·x_pred) against a threshold derived from:
        innovation_max = ego_uncertainty_radps   [rad/s]
    where ego_uncertainty_radps is a caller-supplied upper bound on the residual
    ego error (e.g. 0.05 rad/s for a 5 ms sync error at 10 rad/s body rate).

    If |innovation| > ego_gate_radps in EITHER az or el, the update weight
    for Mode 1 (MANEUVER) is NOT amplified by the innovation magnitude alone —
    instead the large innovation is interpreted as a potential ego residual, and
    the maneuver-probability update is DAMPED:
        likelihood_mode1 *= ego_gate_damping   (default 0.3)

    This prevents a time-sync spike from being misclassified as a target jink
    and wrongly raising the maneuver probability.

    HOWEVER: a REAL target maneuver produces a sustained innovation over
    multiple frames while an ego residual spike is transient (one or a few
    frames).  The sustained_maneuver_count tracks consecutive innovations that
    would raise the maneuver mode — only after N_SUSTAIN consecutive frames
    does the gate relaxation apply (i.e. after N_SUSTAIN frames we believe it's
    real maneuver).  This is the key temporal discriminator.

ALPHA-BETA FALLBACK (documented)
----------------------------------
A simple alpha-beta tracker is provided as a fallback when the full IMM is
considered over-engineered for a particular deployment.  It does NOT implement
mode mixing and has no maneuver detection.  Use it as a sanity check or for
resource-constrained situations.

    alpha = position gain (suggestion: 0.5 for smooth tracking)
    beta  = velocity gain  (suggestion: 0.1)

The fallback does NOT gate innovations against ego — use the full IMM for
production ego-rejection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import numpy.typing as npt

from .los import LOSObservation


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IMMEstimate:
    """Per-frame output of the IMM filter.

    Attributes
    ----------
    az_rad, el_rad:
        Filtered bearing estimate (radians).
    az_rate_radps, el_rate_radps:
        Filtered LOS-rate estimate (rad/s).
    mode_probs:
        Tuple (p_cv, p_maneuver) — mode probabilities summing to 1.
    maneuver_detected:
        True when mode_probs[1] (maneuver probability) exceeds 0.5 for at
        least N_SUSTAIN consecutive frames AND the innovation was NOT gated
        as a potential ego residual.
    frame_id:
        Frame index.
    innovation_az, innovation_el:
        Raw innovation (measurement residual) before gating (for diagnostics).
    ego_gate_active:
        True if the ego-residual gate was triggered this frame.
    """

    az_rad: float
    el_rad: float
    az_rate_radps: float
    el_rate_radps: float
    mode_probs: tuple[float, float]
    maneuver_detected: bool
    frame_id: int
    innovation_az: float = 0.0
    innovation_el: float = 0.0
    ego_gate_active: bool = False
    # A4 diagnostics (do NOT alter the filter): conservative NIS-proxy lock quality.
    nis: float = 0.0              # normalized innovation squared (rate channel, R-only scale)
    lock_quality: float = 1.0     # 1=consistent .. 0=model-wrong; 0.5 at the chi2 bound
    model_ok: bool = True         # False = "model-wrong" alarm (NIS above chi2 bound)
    # A4 estimator-hardening outputs:
    nis_true: float = 0.0         # TRUE NIS (rate channels) normalised by innovation covariance S
    model_wrong_alarm: bool = False  # SUSTAINED true-NIS exceedance -> live model-wrong alarm
    gate_sigma_az_rad: float = 0.0   # predicted 1-sigma az innovation (for a covariance-sized box)
    gate_sigma_el_rad: float = 0.0   # predicted 1-sigma el innovation


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IMMConfig:
    """Configuration for the IMM filter.

    Attributes
    ----------
    sigma_meas_az, sigma_meas_el:
        Measurement noise standard deviation for az and el (radians and rad/s).
        For az/el bearing: ~sub-pixel / f_px; for az_rate/el_rate: ~few mrad/s.
    q_cv_rate:
        Process noise on LOS-rate for CV mode (rad/s²).  Low = trusts constant
        velocity assumption.  Suggestion: 0.005 rad/s².
    q_maneuver_rate:
        Process noise on LOS-rate for MANEUVER mode (rad/s²).  High = allows
        large angular accelerations.  Suggestion: 0.5 rad/s².
    transition_prob_stay:
        Markov transition probability of staying in the same mode (0.95 = 5%
        chance of switching per frame).
    ego_gate_radps:
        Innovation magnitude (rad/s) above which a rate innovation is flagged
        as a potential ego residual.  Default 0.05 rad/s.  Represents the
        expected maximum residual ego error from a ~5 ms sync error at ~10 rad/s.
    ego_gate_damping:
        When ego gate is active, the maneuver-mode likelihood is multiplied by
        this factor.  0.3 = aggressively damp false maneuver detection.
    n_sustain_for_maneuver:
        Number of consecutive frames with maneuver-mode probability > 0.5
        before ``maneuver_detected`` is set True.
    init_mode_prob_cv:
        Initial probability for the CV mode.
    """

    # Measurement noise (1-sigma)
    sigma_meas_az: float = 5e-4       # rad (≈1 px at f=2000 px)
    sigma_meas_el: float = 5e-4       # rad
    sigma_meas_az_rate: float = 0.005  # rad/s  (only used by measurement_mode="diagonal_r")
    sigma_meas_el_rate: float = 0.005  # rad/s
    # Measurement model for the az/el RATE channels.
    #   "correlated_r" (default, CORRECT): the rate is a finite difference of the bearing, so its
    #     noise is ~2x the bearing noise scaled by 1/dt AND correlated with the bearing.  R is built
    #     per-frame as a per-axis block [[σ², σ²/dt],[σ²/dt, 2σ²/dt²]] from sigma_meas_az/el + dt.
    #     This removes the finite-diff DOUBLE-COUNT that made NIS≈2 and the posterior over-confident.
    #   "diagonal_r" (legacy): independent diagonal R using sigma_meas_*_rate (bit-identical to the
    #     pre-fix behaviour; kept for A/B comparison against the NEES/NIS consistency harness).
    measurement_mode: str = "correlated_r"

    # Process noise (LOS-rate acceleration)
    q_cv_rate: float = 0.005      # rad/s² — low, steady approach
    q_maneuver_rate: float = 0.5  # rad/s² — high, evasive jink

    # IMM transition matrix (Markov)
    transition_prob_stay: float = 0.95

    # Ego innovation gate
    ego_gate_radps: float = 0.05      # rad/s — flag potential ego residual
    ego_gate_damping: float = 0.3     # damp maneuver likelihood when gated
    n_sustain_for_maneuver: int = 3   # consecutive frames before maneuver_detected

    # Initial conditions
    init_mode_prob_cv: float = 0.9

    # A4: NIS-proxy "model-wrong" alarm bound (chi-square, 2 DOF: 5.99=95%, 9.21=99%)
    nis_chi2_bound: float = 9.21

    # A4 estimator hardening ------------------------------------------------------
    # Feed EgoEstimate.quality into R: when the ego-motion estimate is poor (quality<1),
    # the rate channels are less trustworthy, so inflate their measurement variance.
    # At quality=1 the factor is exactly 1.0 (a no-op -> nominal behaviour unchanged).
    ego_quality_r_inflation: float = 4.0   # R_rate *= 1 + this*(1-quality); 0 disables
    # TRUE NIS (rate channels, using the innovation covariance S, not R-only): a real
    # maneuver inflates S via the maneuver-mode P and stays bounded, so a SUSTAINED
    # exceedance is a genuine "model-wrong" event, not a jink.  This drives the live alarm.
    nis_gate_chi2: float = 9.21            # 2-DOF chi-square 99% bound for the true-NIS gate
    nis_sustain_for_alarm: int = 5         # consecutive true-NIS exceedances before the alarm
    # Covariance-sized association gate: chi-square scale on the predicted bearing innovation
    # std (sqrt of S diagonal) the pipeline turns into a px search box (replaces the fixed gate).
    gate_chi2_scale: float = 3.0           # ~3 sigma (chi ~ sqrt(9.21)) box half-width

    # R2 robust update (default-OFF -> bit-identical) -------------------------------
    # Huber-clip the STATE UPDATE for an in-gate tail innovation (glint), while the likelihood
    # stays RAW so the maneuver mode is never blinded; down-weights beyond huber_delta sigmas.
    huber_enabled: bool = False
    huber_delta: float = 3.0
    # Inflate the BEARING-channel R as the target's pixel extent grows (centroid/glint error
    # scales with the resolved footprint). r_extent_k default 0 = off (the magnitude is gated on
    # the V5 field measurement; only the mechanism ships now).
    r_extent_k: float = 0.0
    r_extent_ref_px: float = 100.0


# ---------------------------------------------------------------------------
# IMM filter
# ---------------------------------------------------------------------------

class IMMFilter:
    """Interacting Multiple Model filter on body-frame LOS state.

    See module docstring for full description of the algorithm and conventions.

    Parameters
    ----------
    config:
        IMMFilter configuration.
    """

    _N_MODES: int = 2   # 0=CV, 1=MANEUVER

    def __init__(self, config: IMMConfig | None = None) -> None:
        self._cfg = config or IMMConfig()
        cfg = self._cfg

        # Mode probabilities: [p_cv, p_maneuver]
        p0 = cfg.init_mode_prob_cv
        self._mode_probs: npt.NDArray[np.float64] = np.array(
            [p0, 1.0 - p0], dtype=np.float64
        )

        # Transition matrix (Markov)
        ps = cfg.transition_prob_stay
        self._trans: npt.NDArray[np.float64] = np.array(
            [[ps, 1.0 - ps],
             [1.0 - ps, ps]],
            dtype=np.float64,
        )

        # Per-mode state estimates (x: [az, el, az_rate, el_rate])
        self._x: list[npt.NDArray[np.float64]] = [
            np.zeros(4, dtype=np.float64),
            np.zeros(4, dtype=np.float64),
        ]

        # Per-mode covariance matrices (4x4)
        init_cov = np.diag([
            (0.01) ** 2,           # az (rad²)
            (0.01) ** 2,           # el
            (0.1) ** 2,            # az_rate (rad/s)²
            (0.1) ** 2,            # el_rate
        ])
        self._P: list[npt.NDArray[np.float64]] = [
            init_cov.copy(),
            init_cov.copy(),
        ]

        # Build measurement matrix H: we measure all 4 states
        self._H = np.eye(4, dtype=np.float64)

        # Per-mode measurement noise covariances
        self._R = np.diag([
            cfg.sigma_meas_az ** 2,
            cfg.sigma_meas_el ** 2,
            cfg.sigma_meas_az_rate ** 2,
            cfg.sigma_meas_el_rate ** 2,
        ]).astype(np.float64)

        # Per-mode process noise covariances
        self._Q: list[npt.NDArray[np.float64]] = [
            self._make_Q(cfg.q_cv_rate),
            self._make_Q(cfg.q_maneuver_rate),
        ]

        self._initialized: bool = False
        self._sustain_count: int = 0   # consecutive frames with p_maneuver > 0.5
        self._nis_bad_count: int = 0   # consecutive frames with true-NIS above the chi2 gate (A4)

    @staticmethod
    def _make_Q(q_rate: float) -> npt.NDArray[np.float64]:
        """Build 4x4 process noise matrix.

        Models random angular acceleration (jerk on the LOS-rate):
            Q = [[0, 0, 0, 0],
                 [0, 0, 0, 0],
                 [0, 0, q_rate, 0],
                 [0, 0, 0, q_rate]]
        The bearing states are driven by the rate states, not by direct noise.
        """
        Q = np.zeros((4, 4), dtype=np.float64)
        Q[2, 2] = q_rate
        Q[3, 3] = q_rate
        return Q

    @staticmethod
    def _make_F(dt: float) -> npt.NDArray[np.float64]:
        """Build 4x4 constant-velocity state transition matrix.

        x_{k+1} = F · x_k
            az_{k+1}      = az_k      + az_rate_k · dt
            el_{k+1}      = el_k      + el_rate_k · dt
            az_rate_{k+1} = az_rate_k
            el_rate_{k+1} = el_rate_k
        """
        return np.array([
            [1.0, 0.0, dt,  0.0],
            [0.0, 1.0, 0.0, dt ],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype=np.float64)

    def initialize(self, los: LOSObservation) -> None:
        """Initialize the filter state from the first LOS observation."""
        x0 = np.array([los.az_rad, los.el_rad, los.az_rate_radps, los.el_rate_radps],
                      dtype=np.float64)
        for i in range(self._N_MODES):
            self._x[i] = x0.copy()
        self._initialized = True

    def update(self, los: LOSObservation, dt: float,
               pixel_extent_px: float | None = None) -> IMMEstimate:
        """Run one IMM step with a new LOS observation.

        Parameters
        ----------
        los:
            Ego-compensated LOS observation from los.py.
        dt:
            Elapsed time since the previous frame (seconds).

        Returns
        -------
        IMMEstimate
            Filtered state estimate + mode probabilities.
        """
        if not self._initialized:
            self.initialize(los)
            return IMMEstimate(
                az_rad=los.az_rad,
                el_rad=los.el_rad,
                az_rate_radps=los.az_rate_radps,
                el_rate_radps=los.el_rate_radps,
                mode_probs=(float(self._mode_probs[0]), float(self._mode_probs[1])),
                maneuver_detected=False,
                frame_id=los.frame_id,
            )

        dt = max(dt, 1e-6)

        # Measurement vector from the LOS observation
        z = np.array([los.az_rad, los.el_rad, los.az_rate_radps, los.el_rate_radps],
                     dtype=np.float64)

        # ── STEP 1: Mode mixing ───────────────────────────────────────────────
        # Compute mixed initial conditions for each mode
        # c_j = sum_i(p(M_j | M_i) * mu_i)  — predicted mode probability
        # mu_ij = p(M_j | M_i) * mu_i / c_j  — mixing probability
        c = self._trans.T @ self._mode_probs  # shape (2,)
        c = np.maximum(c, 1e-300)             # avoid division by zero

        x_mix: list[npt.NDArray[np.float64]] = []
        P_mix: list[npt.NDArray[np.float64]] = []

        for j in range(self._N_MODES):
            mu_mix = self._trans[:, j] * self._mode_probs / c[j]  # shape (2,)
            xm = np.zeros(4, dtype=np.float64)
            for i in range(self._N_MODES):
                xm += mu_mix[i] * self._x[i]
            x_mix.append(xm)

            Pm = np.zeros((4, 4), dtype=np.float64)
            for i in range(self._N_MODES):
                diff = self._x[i] - xm
                Pm += mu_mix[i] * (self._P[i] + np.outer(diff, diff))
            P_mix.append(Pm)

        # ── STEP 2: Mode-matched Kalman prediction + update ──────────────────
        F = self._make_F(dt)

        # ── EGO GATE: compute a SINGLE gate decision from the combined prediction ─
        # Use x_pred_combined = Σ_j c[j]*x_mix[j] as the single best-effort
        # prediction for gating, so the gate decision is consistent and matches
        # the diagnostic output field ego_gate_active (Fix 4 — single gate flag).
        x_pred_combined_gate = np.zeros(4, dtype=np.float64)
        for j in range(self._N_MODES):
            x_pred_combined_gate += c[j] * x_mix[j]
        x_pred_combined_gate = F @ x_pred_combined_gate
        innov_gate = z - self._H @ x_pred_combined_gate
        ego_gate_active = (
            abs(innov_gate[2]) > self._cfg.ego_gate_radps
            or abs(innov_gate[3]) > self._cfg.ego_gate_radps
        )

        # ── A4: feed EgoEstimate.quality into R ───────────────────────────────
        # A poor ego-motion estimate corrupts the de-rotated rate measurement, so inflate the
        # RATE channels of R when los.ego_quality < 1.  At quality == 1 the factor is 1.0, so a
        # clean (gyro-only) frame is bit-identical to the previous behaviour.
        q_ego = min(max(float(los.ego_quality), 0.0), 1.0)
        r_infl = 1.0 + self._cfg.ego_quality_r_inflation * (1.0 - q_ego)
        # Base measurement-noise covariance for this frame.
        if self._cfg.measurement_mode == "correlated_r":
            # The az/el RATE "measurements" are finite differences of the bearing -> ~2x noisier
            # (scaled by 1/dt) AND correlated with the bearing.  Model the true per-axis covariance
            # [[σ², σ²/dt],[σ²/dt, 2σ²/dt²]] instead of pretending the rate is an independent,
            # over-precise measurement (the diagonal-R double-count that made NIS≈2).
            dt2 = dt * dt
            sb_az = self._cfg.sigma_meas_az ** 2
            sb_el = self._cfg.sigma_meas_el ** 2
            R_frame = np.zeros((4, 4), dtype=np.float64)
            R_frame[0, 0] = sb_az
            R_frame[1, 1] = sb_el
            R_frame[2, 2] = 2.0 * sb_az / dt2
            R_frame[3, 3] = 2.0 * sb_el / dt2
            R_frame[0, 2] = R_frame[2, 0] = sb_az / dt
            R_frame[1, 3] = R_frame[3, 1] = sb_el / dt
        else:  # "diagonal_r" — legacy independent-rate model (bit-identical to before)
            R_frame = self._R.copy()
        R_frame[2, 2] *= r_infl
        R_frame[3, 3] *= r_infl
        # R2: inflate the BEARING-channel measurement noise as the target's pixel extent grows
        # (a resolved/glinting target has a noisier centroid). r_extent_k=0 -> no-op.
        if self._cfg.r_extent_k > 0.0 and pixel_extent_px is not None and pixel_extent_px > 0.0:
            ext_infl = 1.0 + self._cfg.r_extent_k * max(
                float(pixel_extent_px) / max(self._cfg.r_extent_ref_px, 1e-9) - 1.0, 0.0)
            R_frame[0, 0] *= ext_infl
            R_frame[1, 1] *= ext_infl

        # ── A4: combined predicted innovation covariance S (for the TRUE NIS + covariance box) ─
        P_pred_combined = np.zeros((4, 4), dtype=np.float64)
        for j in range(self._N_MODES):
            P_pred_combined += c[j] * (F @ P_mix[j] @ F.T + self._Q[j])
        S_combined = self._H @ P_pred_combined @ self._H.T + R_frame

        x_upd: list[npt.NDArray[np.float64]] = []
        P_upd: list[npt.NDArray[np.float64]] = []
        log_likelihoods: list[float] = []

        for j in range(self._N_MODES):
            x_pred = F @ x_mix[j]
            P_pred = F @ P_mix[j] @ F.T + self._Q[j]

            # Innovation (per-mode, for Kalman update and likelihood)
            innov = z - self._H @ x_pred  # (4,)
            S = self._H @ P_pred @ self._H.T + R_frame  # (4, 4)

            # Kalman gain
            try:
                S_inv = np.linalg.inv(S)
            except np.linalg.LinAlgError:
                S_inv = np.linalg.pinv(S)

            K = P_pred @ self._H.T @ S_inv  # (4, 4)
            # R2 Huber: down-weight the STATE UPDATE for a large in-gate (tail-glint) innovation.
            # The likelihood below uses the RAW innovation, so the maneuver mode is NOT blinded.
            innov_upd = innov
            if self._cfg.huber_enabled:
                d = math.sqrt(max(float(innov @ S_inv @ innov), 0.0))
                if d > self._cfg.huber_delta:
                    innov_upd = innov * (self._cfg.huber_delta / d)
            x_new = x_pred + K @ innov_upd
            P_new = (np.eye(4) - K @ self._H) @ P_pred

            x_upd.append(x_new)
            P_upd.append(P_new)

            # Gaussian log-likelihood of the innovation under this mode.
            # Using log-space to avoid numerical underflow with large innovations.
            sign, logdet = np.linalg.slogdet(S)
            if sign <= 0:
                logdet = 30.0  # degenerate: assign low likelihood
            mahal = float(innov @ S_inv @ innov)
            log_like = -0.5 * (mahal + logdet + 4 * math.log(2 * math.pi))

            # EGO GATE: add a log-penalty to maneuver-mode log-likelihood
            # when the COMBINED-prediction innovation looks like an ego residual
            # AND the maneuver has NOT been sustained for N_SUSTAIN frames.
            # The gate flag is a SINGLE decision (computed above) — consistent
            # with the diagnostic output field and the live gating logic.
            # Using log-space: damping factor 0.3 → log(0.3) ≈ -1.20 penalty.
            if j == 1 and ego_gate_active and self._sustain_count < self._cfg.n_sustain_for_maneuver:
                log_like += math.log(max(self._cfg.ego_gate_damping, 1e-300))

            log_likelihoods.append(log_like)

        # ── STEP 3: Mode-probability update (log-space for numerical stability) ─
        # Compute log(c_j) = log(c[j]) + log_like[j], then normalise.
        log_c = np.log(np.maximum(c, 1e-300))
        log_c_prod = log_c + np.array(log_likelihoods, dtype=np.float64)

        # Subtract the max for numerical stability before exp
        log_c_prod_shifted = log_c_prod - np.max(log_c_prod)
        c_prod = np.exp(log_c_prod_shifted)
        total = float(np.sum(c_prod))
        if total < 1e-300:
            new_probs = self._mode_probs.copy()
        else:
            new_probs = c_prod / total

        # ── STEP 4: Combined estimate (Bar-Shalom & Li 1993, eq 11.6.6) ────────
        # Combined mean: weighted sum of per-mode updated states.
        x_combined = np.zeros(4, dtype=np.float64)
        for j in range(self._N_MODES):
            x_combined += new_probs[j] * x_upd[j]

        # Combined covariance: sum of per-mode covariances PLUS spread-of-means term.
        # P_combined = Σ_j μ_j * [P_upd[j] + (x_upd[j]-x_combined)⊗(x_upd[j]-x_combined)]
        # This prevents the next cycle's mixing from using an overconfident per-mode
        # posterior — the spread-of-means term inflates uncertainty appropriately
        # after a mode transition (e.g., post-maneuver back to CV).
        P_combined = np.zeros((4, 4), dtype=np.float64)
        for j in range(self._N_MODES):
            diff_j = x_upd[j] - x_combined
            P_combined += new_probs[j] * (P_upd[j] + np.outer(diff_j, diff_j))

        # Store combined covariance for BOTH modes so the next cycle's mixing
        # sees the correct combined uncertainty, not the raw per-mode posteriors.
        self._x = x_upd
        self._P = [P_combined.copy(), P_combined.copy()]
        self._mode_probs = new_probs

        # Track sustained maneuver detection
        p_maneuver = float(new_probs[1])
        if p_maneuver > 0.5:
            self._sustain_count += 1
        else:
            self._sustain_count = 0

        maneuver_detected = (
            p_maneuver > 0.5
            and self._sustain_count >= self._cfg.n_sustain_for_maneuver
        )

        # A4: conservative NIS-proxy lock-quality (DIAGNOSTIC ONLY -- never feeds the filter).
        # Normalize the rate innovation by the measurement noise R only (ignoring P), so it
        # OVER-estimates inconsistency -> fail-safe. A sustained large value is a "model-wrong"
        # alarm for the lock-quality / confirm gate.  (True NIS using the prior covariance S is
        # a later refinement; the R-only proxy is strictly more conservative.)
        sa = max(self._cfg.sigma_meas_az_rate, 1e-9)
        se = max(self._cfg.sigma_meas_el_rate, 1e-9)
        nis = (float(innov_gate[2]) / sa) ** 2 + (float(innov_gate[3]) / se) ** 2
        if not np.isfinite(nis):
            nis = float("inf")
        model_ok = bool(nis <= self._cfg.nis_chi2_bound)
        lock_quality = 1.0 / (1.0 + nis / self._cfg.nis_chi2_bound)   # 1@0, 0.5@bound, ->0

        # A4: TRUE NIS on the rate channels using the innovation covariance S (not R-only).
        # S inflates during a real maneuver (maneuver-mode P grows), so a genuine jink does NOT
        # trip this -- only a SUSTAINED exceedance (measurements the filter cannot explain) does,
        # which is what the live "model-wrong" alarm flags for the activate-permission gate.
        ir = innov_gate[2:4]
        Srr = S_combined[2:4, 2:4]
        try:
            nis_true = float(ir @ np.linalg.inv(Srr) @ ir)
        except np.linalg.LinAlgError:
            nis_true = float(ir @ np.linalg.pinv(Srr) @ ir)
        if not np.isfinite(nis_true):
            nis_true = float("inf")
        if nis_true > self._cfg.nis_gate_chi2:
            self._nis_bad_count += 1
        else:
            self._nis_bad_count = 0
        model_wrong_alarm = self._nis_bad_count >= self._cfg.nis_sustain_for_alarm
        # Predicted bearing innovation std (sqrt of S diagonal) -> covariance-sized search box.
        gate_sigma_az = math.sqrt(max(float(S_combined[0, 0]), 0.0))
        gate_sigma_el = math.sqrt(max(float(S_combined[1, 1]), 0.0))

        # ego_gate_active is already computed above from the COMBINED prediction.
        # Use innov_gate (indices 2,3) for the diagnostic innovation fields so
        # the live gate flag and the reported innovation are from the same source.
        return IMMEstimate(
            az_rad=float(x_combined[0]),
            el_rad=float(x_combined[1]),
            az_rate_radps=float(x_combined[2]),
            el_rate_radps=float(x_combined[3]),
            mode_probs=(float(new_probs[0]), float(new_probs[1])),
            maneuver_detected=maneuver_detected,
            frame_id=los.frame_id,
            innovation_az=float(innov_gate[2]),
            innovation_el=float(innov_gate[3]),
            ego_gate_active=ego_gate_active,
            nis=float(nis),
            lock_quality=float(lock_quality),
            model_ok=model_ok,
            nis_true=float(nis_true),
            model_wrong_alarm=model_wrong_alarm,
            gate_sigma_az_rad=float(gate_sigma_az),
            gate_sigma_el_rad=float(gate_sigma_el),
        )


# ---------------------------------------------------------------------------
# Alpha-beta fallback tracker (documented simpler alternative)
# ---------------------------------------------------------------------------

@dataclass
class AlphaBetaState:
    """Mutable state for the alpha-beta tracker."""

    az: float = 0.0
    el: float = 0.0
    az_rate: float = 0.0
    el_rate: float = 0.0
    initialized: bool = False


class AlphaBetaTracker:
    """Simple alpha-beta tracker on body-frame LOS.

    Alpha-beta is a fixed-gain 2-state tracker:
        prediction:
            az_pred = az + az_rate * dt
            az_rate_pred = az_rate
        correction:
            az       += alpha * (z_az - az_pred)
            az_rate  += beta  * (z_az - az_pred) / dt
        (and analogously for el)

    This is the classical «g-h filter».  It has no mode switching, no ego gate,
    and no maneuver detection.  It is documented as a fallback when the full IMM
    is over-engineered.

    IMPORTANT: This tracker does NOT gate innovations against ego-residuals.
    For production ego-residual rejection, use IMMFilter.

    Suggested parameters (Benedikt, 1992):
        alpha = 0.5   — moderate smoothing
        beta  = 0.1   — slow rate adaptation
    Faster target: increase both.  Noisier measurement: decrease alpha.
    """

    def __init__(self, alpha: float = 0.5, beta: float = 0.1) -> None:
        if not (0.0 < alpha < 1.0):
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        if not (0.0 < beta < 1.0):
            raise ValueError(f"beta must be in (0, 1), got {beta}")
        self._alpha = alpha
        self._beta = beta
        self._state = AlphaBetaState()

    def reset(self) -> None:
        """Reset to uninitialized state."""
        self._state = AlphaBetaState()

    def update(self, los: LOSObservation, dt: float) -> tuple[float, float, float, float]:
        """Update the alpha-beta tracker.

        Returns
        -------
        (az_rad, el_rad, az_rate_radps, el_rate_radps)
        """
        dt = max(dt, 1e-6)
        s = self._state

        if not s.initialized:
            s.az = los.az_rad
            s.el = los.el_rad
            s.az_rate = los.az_rate_radps
            s.el_rate = los.el_rate_radps
            s.initialized = True
            return s.az, s.el, s.az_rate, s.el_rate

        # Prediction
        az_pred = s.az + s.az_rate * dt
        el_pred = s.el + s.el_rate * dt

        # Innovation
        res_az = los.az_rad - az_pred
        res_el = los.el_rad - el_pred

        # Correction
        s.az = az_pred + self._alpha * res_az
        s.el = el_pred + self._alpha * res_el
        s.az_rate = s.az_rate + self._beta * res_az / dt
        s.el_rate = s.el_rate + self._beta * res_el / dt

        return s.az, s.el, s.az_rate, s.el_rate

```


## `vision/tracker/track.py`

```python
"""Lean single-target lock FSM for S1 thermal tracker.

This is the **S1 perception-layer tracker** — deliberately minimal.  The full
IMM (S2) will replace the prediction model; this version uses a simple
constant-velocity 1-step predictor for coast phases.

State machine
-------------
States (mirrors ``gates/lock.py`` shape; thermal-specific names)::

    NO_TARGET      — no candidate seen yet
    CANDIDATE      — blob seen but not enough stable frames for lock
    LOCKED         — stable lock, high-confidence association
    PREDICTIVE_TRACK — lock was good, brief detection gap, CV predict + coast
    REACQUIRE      — longer loss, expanding search window, active suspended
    HARD_LOST      — timeout exceeded, lock abandoned

Transitions::

    NO_TARGET → CANDIDATE    : any blob within acquisition box
    CANDIDATE → LOCKED        : stable_frame_count consecutive associations
    CANDIDATE → NO_TARGET     : association fails (too far / no blob)
    LOCKED → PREDICTIVE_TRACK : no associated blob within gate this frame
    PREDICTIVE_TRACK → LOCKED : blob re-associated within gate
    PREDICTIVE_TRACK → REACQUIRE : coast budget exceeded
    REACQUIRE → LOCKED        : blob re-associated within expanded window
    REACQUIRE → HARD_LOST     : reacquire budget exceeded
    HARD_LOST → NO_TARGET     : (automatic reset; operator must re-seed)

Seeded acquisition
------------------
The caller provides an ``acquisition_box`` (x, y, w, h) — typically derived
from the operator's aim on the seeder console — to constrain the initial
association search.  Once LOCKED, the gate expands slightly via the predicted
centroid.

Nearest-neighbour association
------------------------------
Per-frame association is nearest-neighbour in pixel Euclidean distance between
the predicted centroid and each blob's centroid.  The search window is gated:
``distance < max_gate_px`` for LOCKED, expanding to ``reacquire_expansion_factor``
multiples for REACQUIRE.

Constant-velocity coast predictor
-----------------------------------
Maintains a rolling (vx, vy) velocity estimate (pixels per millisecond) from
the last two associated observations.  During coast (PREDICTIVE_TRACK /
REACQUIRE) the predicted centroid advances by vx, vy scaled by elapsed time.
This keeps the gate centred near the expected target location and reduces
false-association probability.

FFC coast
---------
During FFC FREEZE / RECOVERING frames (``observation.is_ffc_freeze``), the
tracker automatically enters PREDICTIVE_TRACK coast without consuming the
normal lost-frame budget.  The lock survives a ~0.5 s FFC event.

Reuse shape from ``gates/lock.py``
------------------------------------
``ThermalLockTracker`` is structurally modelled on ``GateLockTracker`` (same
state enum shape, same ``update()`` → snapshot pattern, same velocity predictor
and confidence decay), but operates on ``ThermalBlob`` / ``TargetObservation``
instead of ``GateDetection``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .blob import ThermalBlob, TargetObservation

# ---------------------------------------------------------------------------
# State enums
# ---------------------------------------------------------------------------

# R4: angular-scale regime state machine (POINT -> RESOLVED -> FILL).
# Keyed on area_extended_px (the un-suppressed half-max footprint that GROWS
# monotonically with true target size), with hysteretic (Schmitt-trigger)
# up/down thresholds to prevent chatter at regime boundaries.
# This is informational only -- it NEVER moves the centroid, LOS, or control
# command (doctrine Inv 2).  R5 will consume it to switch the aimpoint.
class RegimeState(str, Enum):
    """Angular-scale regime of the tracked target.

    POINT     — sub-resolution; area_extended_px well below the resolve threshold.
    RESOLVED  — partially resolved; top-hat still suppresses interior, but
                area_extended_px is large enough to indicate significant subtense.
    FILL      — fills or nearly fills the FOV; target looms to near-saturation.
    """

    POINT = "POINT"
    RESOLVED = "RESOLVED"
    FILL = "FILL"


class TrackingState(str, Enum):
    """FSM states for the thermal tracker tracker."""

    NO_TARGET = "NO_TARGET"
    CANDIDATE = "CANDIDATE"
    LOCKED = "LOCKED"
    PREDICTIVE_TRACK = "PREDICTIVE_TRACK"
    REACQUIRE = "REACQUIRE"
    HARD_LOST = "HARD_LOST"


_COAST_STATES = frozenset({
    TrackingState.PREDICTIVE_TRACK,
    TrackingState.REACQUIRE,
    TrackingState.HARD_LOST,
})

SCHEMA: str = "vision_thermal_lock.v1"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ThermalLockConfig:
    """Thresholds and timing parameters for the thermal lock FSM.

    Attributes
    ----------
    stable_frame_count:
        Number of consecutive associations required to transition
        NO_TARGET/CANDIDATE → LOCKED.
    max_gate_px:
        Nearest-neighbour association gate radius (pixels) when LOCKED.
    predictive_track_frames:
        Maximum number of consecutive missed-detection frames before
        transitioning LOCKED → REACQUIRE.  At 60 Hz, 18 frames ≈ 300 ms.
    reacquire_frames:
        Maximum number of frames in REACQUIRE before HARD_LOST.
        At 60 Hz, 90 frames ≈ 1.5 s.
    reacquire_expansion_factor:
        Gate radius multiplier applied during REACQUIRE
        (``expanded_gate = max_gate_px * factor``).
    min_snr_for_association:
        Blobs below this SNR are not considered for association.
    confidence_decay_per_missed_frame:
        Multiplicative decay applied to lock_confidence per missed-detection
        frame (coast frames).
    """

    stable_frame_count: int = 3
    max_gate_px: float = 48.0
    predictive_track_frames: int = 18   # ~300 ms @ 60 Hz
    reacquire_frames: int = 90          # ~1.5 s @ 60 Hz
    reacquire_expansion_factor: float = 3.0
    min_snr_for_association: float = 2.0
    confidence_decay_per_missed_frame: float = 0.92
    # --- combined-cost association (anti pull-off onto hotter/larger clutter) ---
    # Applied only once a track reference (`_last_blob`) exists; pure nearest-neighbour
    # during fresh acquisition.  A candidate grossly larger/smaller than, or suddenly far
    # hotter than, the tracked target is VETOED even if it is the nearest blob -- this is
    # what stops the lock walking onto a hotter intruder/decoy/glint.  References are the
    # PREVIOUS frame, so smooth looming growth passes while sudden discontinuities are cut.
    assoc_w_kinematic: float = 1.0      # weight on normalized predicted-distance
    assoc_w_appearance: float = 2.0     # weight on frame-to-frame size change (must outvote proximity)
    assoc_w_intensity: float = 0.5      # weight on frame-to-frame SNR change
    assoc_area_veto_ratio: float = 2.5      # reject if area differs > this x from the track's last
    assoc_intensity_veto_ratio: float = 3.0  # reject if peak > this x the track's last peak (intruder)
    # --- R4: hysteretic angular-scale regime state machine (default-OFF -> bit-identical to today) ---
    # When OFF the regime stays POINT; no thresholds are evaluated, so the OFF path is IDENTICAL
    # to a run without R4 at all (no new computation, no mutation of any existing field).
    # area_extended_px thresholds (pixels): POINT->RESOLVED promotes above regime_resolve_up_px;
    # RESOLVED->FILL promotes above regime_fill_up_px.  Down-thresholds use a hysteresis_fraction
    # below the up-threshold (Schmitt trigger: down < up, so the regime is sticky near boundaries).
    # Defaults are calibrated to the V3 scale-sweep baseline where area_extended_px grows from
    # ~few px (sigma=1.5) to ~tens-of-thousands px (sigma=40).  The resolve knee (sigma~5-8) maps
    # to area_extended_px in the hundreds; fill (sigma~20+) maps to area_extended_px in the thousands.
    regime_enabled: bool = False
    regime_resolve_up_px: float = 500.0     # POINT  -> RESOLVED when area_extended_px rises above this
    regime_fill_up_px: float = 5000.0       # RESOLVED -> FILL   when area_extended_px rises above this
    regime_hysteresis_fraction: float = 0.8  # down-threshold = up-threshold * this fraction
    # --- R1: consume IMM hardening (all default-OFF -> bit-identical to today) ---
    # (a) IMM-mixed-state coast: when the pipeline feeds the IMM's predicted centroid + per-frame
    #     pixel velocity (set_imm_state), coast on THAT instead of the crude 2-point pixel CV.
    use_imm_coast: bool = False
    # (b) peak-relative deletion: a continuous lock-score (lock_confidence x lock_quality x
    #     model_ok-penalty) that DROPS A TRACK when it falls below a fraction of its own peak --
    #     resists single-frame dropouts, releases a genuinely-gone target.  Quality affects the
    #     track LIFECYCLE only, NEVER the centroid (Inv 2).
    use_peak_relative_deletion: bool = False
    lock_score_delete_fraction: float = 0.3   # delete when score < this x its peak
    model_wrong_score_penalty: float = 0.5    # lock-score multiplier when model_ok is False
    # --- R7: intensity^motion consensus before LOCKED (default-OFF -> bit-identical) ---
    # A fresh intensity blob may promote CANDIDATE->LOCKED only if it AGREES with an independent
    # MOTION measurement (event-channel / MTI centroid fed via set_motion_centroid) -- rejects a
    # bright STATIC clutter blob (sun glint, hot ground feature). A globally QUIET scene (no motion
    # for consensus_quiet_frames) still allows an intensity-only lock so a HOVERER is not lost.
    # This is a kinematic LIFECYCLE gate; it never moves the centroid (Inv 2) and never forks a
    # confirmed track (Inv 7 -- it only restrains a NOT-yet-locked candidate).
    require_consensus_for_lock: bool = False
    consensus_radius_px: float = 30.0
    consensus_quiet_frames: int = 10          # frames of no-motion after which intensity-only locks
    # --- R10: JPDA soft-update on a cluttered gate (default-OFF -> bit-identical) ---
    # When the gate holds >= jpda_occupancy_threshold valid returns, replace hard winner-take-all
    # with a likelihood-weighted soft centroid biased toward the prediction -- this is exactly the
    # horizon-crossing geometry where hard GNN pulls off onto a hotter intruder. The appearance
    # reference (_last_blob / vetoes) stays the HARD best; only the reported POSITION is softened.
    # DETERMINISTIC kinematic association (Inv 2), and it restrains a position, never forks a track.
    jpda_enabled: bool = False
    jpda_occupancy_threshold: int = 2
    jpda_softmax_scale: float = 1.0           # temperature on exp(-cost/scale)
    jpda_prediction_weight: float = 0.5       # pseudo-weight pulling the soft centroid to the prediction

    def __post_init__(self) -> None:
        if self.stable_frame_count < 1:
            raise ValueError("stable_frame_count must be >= 1")
        if self.max_gate_px <= 0.0:
            raise ValueError("max_gate_px must be positive")
        if self.predictive_track_frames < 0:
            raise ValueError("predictive_track_frames must be >= 0")
        if self.reacquire_frames < self.predictive_track_frames:
            raise ValueError("reacquire_frames must be >= predictive_track_frames")
        if self.assoc_area_veto_ratio <= 1.0:
            raise ValueError("assoc_area_veto_ratio must be > 1")
        if self.assoc_intensity_veto_ratio <= 1.0:
            raise ValueError("assoc_intensity_veto_ratio must be > 1")


# ---------------------------------------------------------------------------
# Snapshot (output)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ThermalLockSnapshot:
    """Per-frame output of the thermal lock FSM.

    Attributes
    ----------
    tracking_state:
        Current FSM state.
    target_locked:
        True only in LOCKED state.
    centroid_px:
        Best estimate of target centroid (observed if LOCKED, predicted otherwise).
    lock_confidence:
        Scalar confidence in [0, 1].  Decays during coast frames.
    stable_frames:
        Consecutive frames with successful association.
    missed_frames:
        Consecutive frames without association (resets on re-association).
    predicted_centroid_px:
        CV-predictor centroid regardless of state (useful for display).
    associated_blob:
        The ``ThermalBlob`` that was associated this frame, or ``None``.
    frame_id:
        Frame counter.
    recommended_action:
        String hint for control layer: ``"TRACK"`` | ``"COAST"`` |
        ``"REACQUIRE"`` | ``"ABANDON"``.
    """

    tracking_state: TrackingState
    target_locked: bool
    centroid_px: tuple[float, float]
    lock_confidence: float
    stable_frames: int
    missed_frames: int
    predicted_centroid_px: tuple[float, float]
    associated_blob: ThermalBlob | None
    frame_id: int
    recommended_action: str
    # R4: angular-scale regime (informational only; NEVER read by control/centroid/LOS code).
    # Defaults to POINT so all existing snapshot constructions continue to work unchanged.
    regime: RegimeState = RegimeState.POINT

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema": SCHEMA,
            "tracking_state": self.tracking_state.value,
            "target_locked": self.target_locked,
            "centroid_px": list(self.centroid_px),
            "lock_confidence": round(self.lock_confidence, 4),
            "stable_frames": self.stable_frames,
            "missed_frames": self.missed_frames,
            "predicted_centroid_px": list(self.predicted_centroid_px),
            "frame_id": self.frame_id,
            "recommended_action": self.recommended_action,
            "regime": self.regime.value,
        }
        if self.associated_blob is not None:
            d["associated_blob"] = self.associated_blob.to_dict()
        return d


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

class ThermalLockTracker:
    """Single-target lock FSM for thermal blob tracking.

    Seeded acquisition
    ------------------
    Call ``seed(acquisition_box)`` before the first ``update()`` call.  The
    acquisition box constrains the initial search.  Once locked, the box is
    replaced by the gate around the predicted centroid.

    Usage
    -----
    ::

        tracker = ThermalLockTracker(config)
        tracker.seed(acq_box=(cx - 32, cy - 32, 64, 64))

        threshold_state = ThresholdState()
        for frame_u16, gt in sim.generate(300):
            blobs, threshold_state = detect_frame(frame_u16, ...)
            obs = TargetObservation(frame_id=..., blobs=blobs, ...)
            snapshot = tracker.update(obs)
            print(snapshot.tracking_state, snapshot.centroid_px)
    """

    def __init__(self, config: ThermalLockConfig | None = None) -> None:
        self._cfg = config or ThermalLockConfig()
        self._state = TrackingState.NO_TARGET
        self._stable_frames: int = 0
        self._missed_frames: int = 0
        self._ffc_coast_frames: int = 0  # separate counter for FFC freezes
        self._lock_confidence: float = 0.0

        # Last associated blob (for velocity estimation)
        self._last_blob: ThermalBlob | None = None
        self._prev_blob: ThermalBlob | None = None
        self._velocity_px_per_frame: tuple[float, float] = (0.0, 0.0)

        # Seeded acquisition box (x, y, w, h)
        self._acq_box: tuple[float, float, float, float] | None = None

        # A4 covariance-sized search box: an EXPAND-ONLY gate floor (px) set from the IMM's
        # predicted innovation covariance.  0 = unused (the fixed gate governs).  It can only
        # widen the gate when the estimator is uncertain; it never shrinks it.
        self._dynamic_gate_px: float = 0.0

        # R1 IMM-coast: pipeline-fed predicted centroid + per-frame pixel velocity (from the IMM
        # angular state via bearing_to_pixel).  None = not fed -> fall back to 2-point CV.
        self._imm_centroid_px: tuple[float, float] | None = None
        self._imm_vel_px_per_frame: tuple[float, float] = (0.0, 0.0)
        # R1 lock-score (peak-relative deletion): quality fed from the IMM (output-only; never
        # moves the centroid).  Score and its running peak drive lifecycle deletion only.
        self._lock_quality: float = 1.0
        self._model_ok: bool = True
        self._lock_score: float = 0.0
        self._lock_score_peak: float = 0.0
        # R7 consensus: latest independent motion centroid + consecutive no-motion frame count.
        self._motion_centroid: tuple[float, float] | None = None
        self._motion_quiet_frames: int = 0
        # R8: normalized MOSSE structural confidence (1.0 = unused) -> modulates the lock-score only.
        self._correlation_confidence: float = 1.0
        # R10 JPDA: in-gate (blob, cost) candidates collected this frame + the last prediction.
        self._jpda_candidates: list[tuple[ThermalBlob, float]] = []
        self._last_predicted: tuple[float, float] = (0.0, 0.0)

        # R4: hysteretic angular-scale regime state machine.  Only updated when
        # regime_enabled is True and a blob is associated.  Never modifies centroid/LOS.
        self._regime: RegimeState = RegimeState.POINT

    # ── public API ────────────────────────────────────────────────────────────

    def seed(self, acquisition_box: tuple[float, float, float, float]) -> None:
        """Provide the operator's aim box to seed acquisition.

        Parameters
        ----------
        acquisition_box:
            ``(x, y, w, h)`` in image pixels.  The tracker will only associate
            blobs whose centroid falls within this box during the CANDIDATE
            phase.  Once LOCKED, the box is replaced by the gate.
        """
        x, y, w, h = acquisition_box
        self._acq_box = (x, y, w, h)
        # Reset to candidate search
        self._state = TrackingState.NO_TARGET
        self._stable_frames = 0
        self._missed_frames = 0
        self._lock_confidence = 0.0
        self._last_blob = None
        self._prev_blob = None
        self._velocity_px_per_frame = (0.0, 0.0)

    @property
    def gate_px(self) -> float:
        """Current association gate radius (pixels) for the active state."""
        return self._gate_radius()

    @property
    def velocity_px_per_frame(self) -> tuple[float, float]:
        """Rolling per-frame pixel velocity estimate (for R5's leading-edge aimpoint bias)."""
        return self._velocity_px_per_frame

    @property
    def regime(self) -> "RegimeState":
        """Current angular-scale regime (R4); POINT unless regime_enabled."""
        return self._regime

    def set_search_radius(self, radius_px: float) -> None:
        """A4: set the covariance-sized search-box floor (px) for an ESTABLISHED track.

        The IMM publishes a predicted innovation std; the pipeline projects it to pixels and
        calls this each locked frame.  The value only ever WIDENS the gate (``max`` with the
        fixed gate), so a confident filter keeps the nominal gate and an uncertain one (post
        coast) searches wider.  Non-finite / non-positive values disable it.
        """
        self._dynamic_gate_px = float(radius_px) if (
            math.isfinite(radius_px) and radius_px > 0.0) else 0.0

    def set_imm_state(self, centroid_px: tuple[float, float],
                      vel_px_per_frame: tuple[float, float]) -> None:
        """R1: feed the IMM's model-based predicted centroid + per-frame pixel velocity.

        The pipeline computes these from the IMM angular state (bearing_to_pixel) each LOCKED
        frame.  When ``use_imm_coast`` is set the coast predictor uses this smooth, model-based
        estimate instead of the 2-point pixel velocity.  This is a KINEMATIC prediction (where
        the target is), not a quality/appearance signal -- Inv 2 untouched.
        """
        cx, cy = centroid_px
        vx, vy = vel_px_per_frame
        if math.isfinite(cx) and math.isfinite(cy) and math.isfinite(vx) and math.isfinite(vy):
            self._imm_centroid_px = (float(cx), float(cy))
            self._imm_vel_px_per_frame = (float(vx), float(vy))

    def set_motion_centroid(self, centroid_px: tuple[float, float] | None) -> None:
        """R7: feed the independent motion measurement (event-channel / MTI centroid), or None.

        Tracks consecutive no-motion frames so a globally quiet scene can still lock a hoverer.
        Kinematic consensus signal -- restrains a not-yet-locked candidate; never moves the centroid.
        """
        if centroid_px is not None and math.isfinite(centroid_px[0]) and math.isfinite(centroid_px[1]):
            self._motion_centroid = (float(centroid_px[0]), float(centroid_px[1]))
            self._motion_quiet_frames = 0
        else:
            self._motion_centroid = None
            self._motion_quiet_frames += 1

    def _consensus_ok(self, blob: ThermalBlob) -> bool:
        """R7: True if the candidate may promote to LOCKED under the intensity^motion consensus."""
        cfg = self._cfg
        if not cfg.require_consensus_for_lock:
            return True                                   # consensus disabled -> bit-identical
        if self._motion_quiet_frames >= cfg.consensus_quiet_frames:
            return True                                   # globally quiet -> allow a hoverer to lock
        if self._motion_centroid is None:
            return False                                  # motion expected this frame but none seen
        bx, by = blob.centroid_px
        mx, my = self._motion_centroid
        return math.hypot(bx - mx, by - my) <= cfg.consensus_radius_px

    def set_correlation_confidence(self, confidence: float) -> None:
        """R8: feed the normalized MOSSE structural confidence (PSR-derived, in [0, 1]).

        Modulates the continuous lock-score (lifecycle) ONLY -- a structurally-degraded track is
        released sooner.  It NEVER moves the centroid/LOS (Inv 2: the correlation peak is used for
        same-track re-detection, not the live aimpoint)."""
        if math.isfinite(confidence):
            self._correlation_confidence = float(min(max(confidence, 0.0), 1.0))

    def set_quality(self, lock_quality: float, model_ok: bool) -> None:
        """R1: feed the IMM lock-quality / model-wrong flag (OUTPUT-only signals).

        These drive the continuous lock-score and hence track DELETION (lifecycle) only -- they
        NEVER move the centroid, LOS, or association (doctrine Inv 2).
        """
        if math.isfinite(lock_quality):
            self._lock_quality = float(min(max(lock_quality, 0.0), 1.0))
        self._model_ok = bool(model_ok)

    def active_centroid(self) -> tuple[float, float] | None:
        """Predicted centroid of an ESTABLISHED track (LOCKED / coasting), else None.

        Used by upstream gates (e.g. MTI) to never prune the currently-tracked target --
        only fresh-acquisition candidates may be suppressed.
        """
        if self._state in (TrackingState.LOCKED, TrackingState.PREDICTIVE_TRACK,
                           TrackingState.REACQUIRE):
            return self._predict_centroid()
        return None

    def update(self, observation: TargetObservation) -> ThermalLockSnapshot:
        """Process one frame of detection output and update the FSM.

        Parameters
        ----------
        observation:
            Per-frame detector output (``TargetObservation``).

        Returns
        -------
        ThermalLockSnapshot
            Current state and best centroid estimate.
        """
        frame_id = observation.frame_id

        # ── HARD_LOST automatic reset ──────────────────────────────────────
        # HARD_LOST is otherwise a permanent trap: missed_frames keeps growing
        # and the FSM never returns to NO_TARGET.  Per the docstring
        # ("HARD_LOST → NO_TARGET: automatic reset"), whenever we enter update()
        # in HARD_LOST we reset the FSM to NO_TARGET *before* the association
        # attempt, so a re-appearing target is treated fresh and can climb
        # CANDIDATE → LOCKED again.
        if self._state == TrackingState.HARD_LOST:
            self._state = TrackingState.NO_TARGET
            self._missed_frames = 0
            self._lock_confidence = 0.0
            self._stable_frames = 0
            self._last_blob = None
            self._prev_blob = None
            self._velocity_px_per_frame = (0.0, 0.0)

        # ── FFC coast override ────────────────────────────────────────────
        # During FFC FREEZE / RECOVERING, pixel data is stale — do not consume
        # the normal missed-frame budget; enter/stay in PREDICTIVE_TRACK coast.
        if observation.is_ffc_freeze:
            return self._ffc_coast(frame_id)

        # Reset FFC coast counter when back to READY
        self._ffc_coast_frames = 0

        # ── try to associate a blob ───────────────────────────────────────
        predicted = self._predict_centroid()
        self._last_predicted = predicted              # R10: prediction-bias anchor for the soft centroid
        gate_px = self._gate_radius()
        best_blob = self._associate(observation.blobs, predicted, gate_px)

        if best_blob is not None:
            return self._on_associated(best_blob, frame_id)
        else:
            return self._on_missed(frame_id, predicted)

    # ── private: state transitions ────────────────────────────────────────────

    def _on_associated(self, blob: ThermalBlob, frame_id: int) -> ThermalLockSnapshot:
        """Blob was successfully associated this frame."""
        self._missed_frames = 0
        self._update_velocity(blob)
        self._prev_blob = self._last_blob
        self._last_blob = blob

        prev_state = self._state

        if prev_state == TrackingState.NO_TARGET:
            self._state = TrackingState.CANDIDATE
            self._stable_frames = 1
            self._lock_confidence = 0.3
        elif prev_state == TrackingState.CANDIDATE:
            self._stable_frames += 1
            # R7: promote to LOCKED only with intensity^motion consensus (no-op when disabled).
            if self._stable_frames >= self._cfg.stable_frame_count and self._consensus_ok(blob):
                self._state = TrackingState.LOCKED
                self._lock_confidence = 1.0
        elif prev_state == TrackingState.LOCKED:
            self._stable_frames += 1
            self._lock_confidence = min(1.0, self._lock_confidence + 0.05)
        elif prev_state in (TrackingState.PREDICTIVE_TRACK, TrackingState.REACQUIRE):
            # Recovery
            self._state = TrackingState.LOCKED
            self._lock_confidence = min(1.0, self._lock_confidence + 0.3)

        if self._cfg.use_peak_relative_deletion:
            self._update_lock_score(reset=(prev_state == TrackingState.NO_TARGET))

        # R4: update the hysteretic regime classifier when enabled.  This is ADDITIVE and
        # INFORMATIONAL: it writes self._regime (never read by any existing code path).
        if self._cfg.regime_enabled:
            self._update_regime(float(blob.area_extended_px))

        report_centroid = self._jpda_centroid(blob)   # R10: soft position on a cluttered gate
        locked = self._state == TrackingState.LOCKED
        action = "TRACK" if locked else "HOLD"
        return ThermalLockSnapshot(
            tracking_state=self._state,
            target_locked=locked,
            centroid_px=report_centroid,
            lock_confidence=self._lock_confidence,
            stable_frames=self._stable_frames,
            missed_frames=0,
            predicted_centroid_px=report_centroid,
            associated_blob=blob,
            frame_id=frame_id,
            recommended_action=action,
            regime=self._regime,
        )

    def _on_missed(
        self, frame_id: int, predicted: tuple[float, float]
    ) -> ThermalLockSnapshot:
        """No blob associated this frame."""
        if self._state == TrackingState.NO_TARGET:
            # Nothing to coast; stay put
            return self._empty_snapshot(frame_id, TrackingState.NO_TARGET, "HOLD")

        if self._state == TrackingState.CANDIDATE:
            # Not locked yet; reset
            self._state = TrackingState.NO_TARGET
            self._stable_frames = 0
            self._lock_confidence = 0.0
            return self._empty_snapshot(frame_id, TrackingState.NO_TARGET, "HOLD")

        # LOCKED / PREDICTIVE_TRACK / REACQUIRE — enter/advance coast
        # Guard: if somehow already HARD_LOST (should not happen after the
        # reset in update(), but kept as a defensive belt-and-suspenders), do
        # not let missed_frames grow without bound.
        if self._state == TrackingState.HARD_LOST:
            return ThermalLockSnapshot(
                tracking_state=self._state,
                target_locked=False,
                centroid_px=predicted,
                lock_confidence=0.0,
                stable_frames=self._stable_frames,
                missed_frames=self._missed_frames,
                predicted_centroid_px=predicted,
                associated_blob=None,
                frame_id=frame_id,
                recommended_action="ABANDON",
                regime=self._regime,
            )

        self._missed_frames += 1
        self._lock_confidence *= self._cfg.confidence_decay_per_missed_frame

        cfg = self._cfg
        if self._missed_frames <= cfg.predictive_track_frames:
            self._state = TrackingState.PREDICTIVE_TRACK
            action = "COAST"
        elif self._missed_frames <= cfg.reacquire_frames:
            self._state = TrackingState.REACQUIRE
            action = "REACQUIRE"
        else:
            self._state = TrackingState.HARD_LOST
            self._lock_confidence = 0.0
            action = "ABANDON"

        # R1 peak-relative deletion: release the track the moment the continuous lock-score
        # falls below a fraction of its own peak (quality-modulated lifecycle; never the centroid).
        if cfg.use_peak_relative_deletion:
            self._update_lock_score(reset=False)
            if (self._lock_score_peak > 0.0
                    and self._lock_score < cfg.lock_score_delete_fraction * self._lock_score_peak):
                self._state = TrackingState.HARD_LOST
                self._lock_confidence = 0.0
                action = "ABANDON"

        return ThermalLockSnapshot(
            tracking_state=self._state,
            target_locked=False,
            centroid_px=predicted,
            lock_confidence=self._lock_confidence,
            stable_frames=self._stable_frames,
            missed_frames=self._missed_frames,
            predicted_centroid_px=predicted,
            associated_blob=None,
            frame_id=frame_id,
            recommended_action=action,
            regime=self._regime,
        )

    def _ffc_coast(self, frame_id: int) -> ThermalLockSnapshot:
        """Coast through an FFC freeze without consuming the normal budget."""
        self._ffc_coast_frames += 1
        predicted = self._predict_centroid()

        if self._state == TrackingState.LOCKED:
            self._state = TrackingState.PREDICTIVE_TRACK

        # Gentle confidence decay during FFC (slower than normal missed frames)
        self._lock_confidence *= (self._cfg.confidence_decay_per_missed_frame ** 0.5)

        return ThermalLockSnapshot(
            tracking_state=self._state,
            target_locked=False,
            centroid_px=predicted,
            lock_confidence=self._lock_confidence,
            stable_frames=self._stable_frames,
            missed_frames=self._missed_frames,
            predicted_centroid_px=predicted,
            associated_blob=None,
            frame_id=frame_id,
            recommended_action="COAST",
            regime=self._regime,
        )

    # ── private: helpers ───────────────────────────────────────────────────────

    def _predict_centroid(self) -> tuple[float, float]:
        """Centroid prediction for the upcoming frame (the coast gate centre)."""
        # R1: model-based IMM coast -- smoother and noise-shaped vs the 2-point pixel CV. Uses the
        # pipeline-fed IMM estimate (current centroid + per-frame pixel velocity). Same indexing
        # as the CV path (advance by missed_frames+1). Falls back to CV until first fed.
        if (self._cfg.use_imm_coast and self._imm_centroid_px is not None
                and self._last_blob is not None):
            ix, iy = self._imm_centroid_px
            vx, vy = self._imm_vel_px_per_frame
            step = self._missed_frames + 1
            return (ix + vx * step, iy + vy * step)
        if self._last_blob is None:
            # Use acquisition box centre if available
            if self._acq_box is not None:
                x, y, w, h = self._acq_box
                return (x + w / 2.0, y + h / 2.0)
            return (0.0, 0.0)
        cx, cy = self._last_blob.centroid_px
        vx, vy = self._velocity_px_per_frame
        # Add missed frames worth of prediction
        return (cx + vx * (self._missed_frames + 1),
                cy + vy * (self._missed_frames + 1))

    def _update_lock_score(self, *, reset: bool) -> None:
        """R1: maintain the continuous lock-score and its running peak (lifecycle signal only)."""
        score = (self._lock_confidence * self._lock_quality * self._correlation_confidence
                 * (1.0 if self._model_ok else self._cfg.model_wrong_score_penalty))
        self._lock_score = score
        self._lock_score_peak = score if reset else max(self._lock_score_peak, score)

    def _update_velocity(self, blob: ThermalBlob) -> None:
        """Update rolling velocity estimate from most recent association."""
        if self._last_blob is not None:
            cx_new, cy_new = blob.centroid_px
            cx_old, cy_old = self._last_blob.centroid_px
            # Time normalised to 1 frame (frame_id difference)
            dt = max(1, blob.frame_id - self._last_blob.frame_id)
            self._velocity_px_per_frame = (
                (cx_new - cx_old) / dt,
                (cy_new - cy_old) / dt,
            )

    def _gate_radius(self) -> float:
        """Return the current association gate radius in pixels."""
        base = self._cfg.max_gate_px
        # During acquisition, gate to the seeded basket (the operator's drawn aim), not the
        # fixed lock-gate -- otherwise a 60px gate-from-box-centre silently shrinks a large
        # basket to a ~60px disc and a cued off-centre target never locks (C4).
        if self._state in (TrackingState.NO_TARGET, TrackingState.CANDIDATE) and self._acq_box is not None:
            _, _, w, h = self._acq_box
            return max(base, 0.5 * math.hypot(w, h))
        if self._state == TrackingState.REACQUIRE:
            base = base * self._cfg.reacquire_expansion_factor
        # A4: never shrink below the fixed gate; widen to the covariance-sized box when set.
        return max(base, self._dynamic_gate_px)

    def _associate(
        self,
        blobs: list[ThermalBlob],
        predicted: tuple[float, float],
        gate_px: float,
    ) -> ThermalBlob | None:
        """Combined-cost association within gate.

        During fresh acquisition (no track reference) this is pure nearest-neighbour.
        Once a reference (`_last_blob`) exists, candidates are scored by a combined
        kinematic + appearance + intensity cost, and a blob grossly out of family in
        size or intensity is VETOED even if nearest -- the anti pull-off rule.
        During CANDIDATE phase association is also constrained to the acquisition box.
        Returns the best in-gate, non-vetoed blob, or ``None``.
        """
        px, py = predicted
        # During a coast (missed_frames > 0) the real target may have loomed well past the
        # per-frame veto ratios while we were not updating `_last_blob` -- re-associate on
        # PURE KINEMATICS so a grown-but-real target is recovered (the gate still bounds where).
        ref = None if self._missed_frames > 0 else self._last_blob
        best: ThermalBlob | None = None
        best_cost = float("inf")
        self._jpda_candidates = []                    # R10: in-gate, non-vetoed (blob, cost) set

        for blob in blobs:
            bx, by = blob.centroid_px

            # Malformed descriptor (NaN/inf in the fields the veto/cost rely on) -> not a
            # candidate.  Fail safe to coast rather than let NaN defeat every '>' comparison.
            if not (math.isfinite(bx) and math.isfinite(by) and math.isfinite(blob.snr)
                    and math.isfinite(blob.area_px) and math.isfinite(blob.peak_counts)):
                continue

            if blob.snr < self._cfg.min_snr_for_association:
                continue

            # During CANDIDATE: only consider blobs inside the acquisition box
            if self._state in (TrackingState.NO_TARGET, TrackingState.CANDIDATE):
                if not self._inside_acq_box(bx, by):
                    continue

            dist = math.hypot(bx - px, by - py)
            if dist >= gate_px:
                continue

            cost = self._association_cost(blob, ref, dist, gate_px)
            if cost is None:        # vetoed: grossly out of family
                continue
            self._jpda_candidates.append((blob, cost))
            if cost < best_cost:
                best_cost = cost
                best = blob

        return best

    def _jpda_centroid(self, best: ThermalBlob) -> tuple[float, float]:
        """R10: likelihood-weighted soft centroid (prediction-biased) on a cluttered gate.

        Off / sparse gate -> the hard best blob centroid (bit-identical). With >= the occupancy
        threshold of valid returns, blend them by exp(-cost) plus a pseudo-weight at the predicted
        state, so a hotter intruder entering the gate cannot fully capture the position.
        """
        cands = self._jpda_candidates
        if not self._cfg.jpda_enabled or len(cands) < self._cfg.jpda_occupancy_threshold:
            return best.centroid_px
        scale = max(self._cfg.jpda_softmax_scale, 1e-6)
        c_min = min(c for _, c in cands)
        betas = [math.exp(-(c - c_min) / scale) for _, c in cands]
        sx = sum(b * blob.centroid_px[0] for (blob, _), b in zip(cands, betas))
        sy = sum(b * blob.centroid_px[1] for (blob, _), b in zip(cands, betas))
        wsum = sum(betas)
        b_pred = self._cfg.jpda_prediction_weight * max(betas)   # pull toward the prediction
        px, py = self._last_predicted
        sx += b_pred * px
        sy += b_pred * py
        wsum += b_pred
        return (sx / wsum, sy / wsum)

    def _association_cost(
        self,
        blob: ThermalBlob,
        ref: ThermalBlob | None,
        dist: float,
        gate_px: float,
    ) -> float | None:
        """Combined association cost (lower is better); ``None`` means VETOED.

        With no reference (fresh acquisition) cost is pure predicted-distance.  With a
        reference, a candidate whose area differs by more than ``assoc_area_veto_ratio``x,
        or whose peak exceeds ``assoc_intensity_veto_ratio``x the tracked target's last
        peak, is vetoed (an intruder/decoy/glint), and the rest are scored by a weighted
        sum of normalized distance, frame-to-frame size change, and SNR change.
        """
        if ref is None:
            return dist

        ref_area = max(float(ref.area_px), 1.0)
        ref_peak = max(float(ref.peak_counts), 1.0)
        ref_snr = max(float(ref.snr), 1e-3)
        area_ratio = max(float(blob.area_px), 1.0) / ref_area

        if area_ratio > self._cfg.assoc_area_veto_ratio or area_ratio < 1.0 / self._cfg.assoc_area_veto_ratio:
            return None
        if float(blob.peak_counts) > ref_peak * self._cfg.assoc_intensity_veto_ratio:
            return None

        kin = dist / gate_px
        app = abs(math.log(area_ratio)) / math.log(self._cfg.assoc_area_veto_ratio)
        inten = min(abs(float(blob.snr) - ref_snr) / ref_snr, 1.0)
        return (self._cfg.assoc_w_kinematic * kin
                + self._cfg.assoc_w_appearance * app
                + self._cfg.assoc_w_intensity * inten)

    def _inside_acq_box(self, x: float, y: float) -> bool:
        """True if (x, y) is inside the seeded acquisition box."""
        if self._acq_box is None:
            return True  # No box → accept any position
        ax, ay, aw, ah = self._acq_box
        return ax <= x <= ax + aw and ay <= y <= ay + ah

    def _update_regime(self, area_extended_px: float) -> None:
        """R4: Hysteretic (Schmitt-trigger) regime classifier on area_extended_px.

        Promotion (up-transitions) occurs when the cue RISES above the up-threshold.
        Demotion (down-transitions) only occurs when the cue FALLS below the
        down-threshold (= up-threshold * hysteresis_fraction), preventing chatter.

        Called only from _on_associated when regime_enabled is True.
        Never touches centroid, LOS, association, or any command (doctrine Inv 2).
        """
        cfg = self._cfg
        resolve_up = cfg.regime_resolve_up_px
        fill_up = cfg.regime_fill_up_px
        hysteresis = cfg.regime_hysteresis_fraction
        resolve_dn = resolve_up * hysteresis
        fill_dn = fill_up * hysteresis

        current = self._regime
        if current == RegimeState.POINT:
            if area_extended_px >= resolve_up:
                self._regime = RegimeState.RESOLVED
        elif current == RegimeState.RESOLVED:
            if area_extended_px >= fill_up:
                self._regime = RegimeState.FILL
            elif area_extended_px < resolve_dn:
                self._regime = RegimeState.POINT
        else:  # FILL
            if area_extended_px < fill_dn:
                self._regime = RegimeState.RESOLVED

    def _empty_snapshot(
        self,
        frame_id: int,
        state: TrackingState,
        action: str,
    ) -> ThermalLockSnapshot:
        return ThermalLockSnapshot(
            tracking_state=state,
            target_locked=False,
            centroid_px=(0.0, 0.0),
            lock_confidence=0.0,
            stable_frames=0,
            missed_frames=self._missed_frames,
            predicted_centroid_px=(0.0, 0.0),
            associated_blob=None,
            frame_id=frame_id,
            recommended_action=action,
            regime=self._regime,
        )

```


## `vision/tracker/track_manager.py`

```python
"""Phase B (B3): multi-track manager with trajectory-continuity confirmation.

The single-target :class:`~vision.tracker.track.ThermalLockTracker` holds the ONE confirmed lock.
This manager sits *beside* it as the look-down false-alarm BACKSTOP: it keeps several
lightweight constant-velocity tracklets and only ``CONFIRM``s one when it has been seen in
``confirm_hits`` of the last ``confirm_window`` frames AND its motion is trajectory-continuous
(low residual to its own CV prediction).

Why both conditions?  A single-frame **parallax flash** (a ground feature the ego-motion
mask failed to cancel for one frame) spawns a tracklet that dies before it can reach the
N-of-M hit count.  A flickering clutter blob that jumps to a new place every frame DOES
accumulate hits, but its CV-prediction residual is large, so the continuity test refuses it.
Only a genuinely-moving target -- persistent AND smooth -- is confirmed.  This never touches
the centroid/LOS/tracker spine (Invariant 2); it only decides which blobs are trustworthy
movers, which the pipeline uses to gate fresh acquisition.

Pure-python and numpy-free (mirrors ``track.py``); blobs are duck-typed on ``.centroid_px``.
"""

from __future__ import annotations

import itertools
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable

SCHEMA: str = "vision_multitrack.v1"


@dataclass(frozen=True)
class MultiTrackConfig:
    """Thresholds for the multi-track manager and its N-of-M continuity confirmation.

    Attributes
    ----------
    gate_px:
        Nearest-neighbour association gate radius (pixels) around a tracklet's CV prediction.
    confirm_hits / confirm_window:
        N-of-M rule: a tracklet is eligible for confirmation once it has ``confirm_hits``
        associations within the last ``confirm_window`` frames.
    max_continuity_residual_px:
        Mean distance between a tracklet's observed centroid and its CV-predicted centroid,
        over its recent history, must stay at/below this for confirmation -- the
        trajectory-continuity (anti-parallax-flash) test.
    min_history_for_residual:
        Minimum number of residual samples before the continuity test is meaningful.
    max_misses:
        Consecutive missed frames before a tracklet is dropped.
    max_tracklets:
        Cap on simultaneously-maintained tracklets (clutter spam guard).
    """

    gate_px: float = 48.0
    confirm_hits: int = 3
    confirm_window: int = 5
    max_continuity_residual_px: float = 6.0
    min_history_for_residual: int = 3
    max_misses: int = 5
    max_tracklets: int = 12

    def __post_init__(self) -> None:
        if self.confirm_hits < 1:
            raise ValueError("confirm_hits must be >= 1")
        if self.confirm_window < self.confirm_hits:
            raise ValueError("confirm_window must be >= confirm_hits")
        if self.gate_px <= 0.0:
            raise ValueError("gate_px must be positive")
        if self.max_tracklets < 1:
            raise ValueError("max_tracklets must be >= 1")


@dataclass
class Tracklet:
    """One constant-velocity hypothesis maintained by :class:`MultiTrackManager`."""

    id: int
    centroid: tuple[float, float]
    velocity: tuple[float, float] = (0.0, 0.0)
    hits: int = 0
    misses: int = 0                                # consecutive misses
    age: int = 0
    confirmed: bool = False
    _window: deque[bool] = field(default_factory=lambda: deque(maxlen=5))
    _residual_sum: float = 0.0
    _residual_n: int = 0
    _last_centroid: tuple[float, float] | None = None

    def predict(self) -> tuple[float, float]:
        """CV prediction for the upcoming frame (advances by velocity per missed frame)."""
        cx, cy = self.centroid
        vx, vy = self.velocity
        step = self.misses + 1
        return (cx + vx * step, cy + vy * step)

    def mean_residual(self) -> float:
        return self._residual_sum / self._residual_n if self._residual_n else float("inf")

    def on_hit(self, centroid: tuple[float, float], predicted: tuple[float, float]) -> None:
        # Continuity residual: how far the observation fell from the CV prediction.
        self._residual_sum += math.hypot(centroid[0] - predicted[0], centroid[1] - predicted[1])
        self._residual_n += 1
        # Velocity from the last associated centroid (1-frame normalised).
        if self._last_centroid is not None:
            self.velocity = (centroid[0] - self._last_centroid[0],
                             centroid[1] - self._last_centroid[1])
        self._last_centroid = centroid
        self.centroid = centroid
        self.hits += 1
        self.misses = 0
        self.age += 1
        self._window.append(True)

    def on_miss(self) -> None:
        self.centroid = self.predict()             # coast on CV
        self.misses += 1
        self.age += 1
        self._window.append(False)

    def hits_in_window(self) -> int:
        return sum(self._window)


@dataclass(frozen=True)
class TrackletSnapshot:
    """Immutable per-frame view of a tracklet (what the pipeline consumes)."""

    id: int
    centroid_px: tuple[float, float]
    confirmed: bool
    hits: int
    misses: int
    mean_residual_px: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "id": self.id,
            "centroid_px": list(self.centroid_px),
            "confirmed": self.confirmed,
            "hits": self.hits,
            "misses": self.misses,
            "mean_residual_px": round(self.mean_residual_px, 3),
        }


class MultiTrackManager:
    """Greedy multi-hypothesis tracker with N-of-M trajectory-continuity confirmation."""

    def __init__(self, config: MultiTrackConfig | None = None) -> None:
        self._cfg = config or MultiTrackConfig()
        self._tracks: list[Tracklet] = []
        self._ids = itertools.count(1)

    @property
    def gate_px(self) -> float:
        """Association/match gate radius (pixels)."""
        return self._cfg.gate_px

    @property
    def tracklets(self) -> list[Tracklet]:
        return list(self._tracks)

    def confirmed_centroids(self) -> list[tuple[float, float]]:
        """Centroids of every currently-confirmed (trajectory-continuous) tracklet."""
        return [t.centroid for t in self._tracks if t.confirmed]

    def reset(self) -> None:
        self._tracks.clear()

    def update(self, blobs: Iterable[Any], frame_id: int = 0) -> list[TrackletSnapshot]:
        """Advance every tracklet one frame against this frame's blobs.

        Returns a snapshot per surviving tracklet (confirmed flag included).
        """
        cfg = self._cfg
        # Finite-guard the blob centroids (a NaN descriptor must not poison association).
        cents: list[tuple[float, float]] = []
        for b in blobs:
            cx, cy = b.centroid_px
            if math.isfinite(cx) and math.isfinite(cy):
                cents.append((float(cx), float(cy)))

        # 1. predict every tracklet
        preds = [t.predict() for t in self._tracks]

        # 2. greedy nearest-neighbour association within gate (each track/blob used once)
        pairs: list[tuple[float, int, int]] = []
        for ti, (px, py) in enumerate(preds):
            for bi, (bx, by) in enumerate(cents):
                d = math.hypot(bx - px, by - py)
                if d <= cfg.gate_px:
                    pairs.append((d, ti, bi))
        pairs.sort(key=lambda p: p[0])
        used_t: set[int] = set()
        used_b: set[int] = set()
        matched: dict[int, int] = {}
        for d, ti, bi in pairs:
            if ti in used_t or bi in used_b:
                continue
            used_t.add(ti)
            used_b.add(bi)
            matched[ti] = bi

        # 3. update matched tracklets / 4. coast the unmatched
        for ti, t in enumerate(self._tracks):
            if ti in matched:
                t.on_hit(cents[matched[ti]], preds[ti])
            else:
                t.on_miss()

        # 5. spawn a tracklet for each unmatched blob (respecting the cap)
        for bi, c in enumerate(cents):
            if bi in used_b:
                continue
            if len(self._tracks) >= cfg.max_tracklets:
                break
            tl = Tracklet(id=next(self._ids), centroid=c, _last_centroid=c)
            tl.hits = 1
            tl.age = 1
            tl._window = deque([True], maxlen=cfg.confirm_window)
            self._tracks.append(tl)

        # 6. confirm (N-of-M + continuity) and prune stale tracklets
        for t in self._tracks:
            self._maybe_confirm(t)
        self._tracks = [t for t in self._tracks if t.misses <= cfg.max_misses]

        return [
            TrackletSnapshot(
                id=t.id, centroid_px=t.centroid, confirmed=t.confirmed,
                hits=t.hits, misses=t.misses, mean_residual_px=t.mean_residual(),
            )
            for t in self._tracks
        ]

    def _maybe_confirm(self, t: Tracklet) -> None:
        cfg = self._cfg
        # Window may have been created with the default maxlen=5; normalise to config.
        if t._window.maxlen != cfg.confirm_window:
            t._window = deque(t._window, maxlen=cfg.confirm_window)
        if t.confirmed:
            return
        if (t.hits_in_window() >= cfg.confirm_hits
                and t._residual_n >= cfg.min_history_for_residual
                and t.mean_residual() <= cfg.max_continuity_residual_px):
            t.confirmed = True

```


## `vision/tracker/aimpoint.py`

```python
"""R5: aimpoint migration -- hotspot (POINT) -> silhouette-centroid (RESOLVED/FILL).

As the target resolves, the white top-hat suppresses its interior, so the detector's
intensity-weighted centroid collapses onto the AGC-saturating hot pixel (motor glow) -- which
WALKS across the airframe as aspect rotates head-on->beam.  That is a silent lambda-dot
disturbance at the worst moment (glint error ~ L/R GROWS as range closes).

The fix is a SILHOUETTE centroid: the intensity-weighted centre of the whole WARM REGION on the
RAW frame (everything a few sigma above the local background), where the body's many pixels
dominate the single hot pixel, so the aimpoint sits on the body centre and stops walking.

DOCTRINE (Inv 2): this is DETERMINISTIC geometry on the raw frame -- the same kind of
measurement as the existing centroid, NOT a learned/appearance-classifier or quality signal.
It takes no lock-quality / model-wrong / PSR input, so a quality perturbation cannot move it.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
from scipy import ndimage as ndi

from .track import RegimeState


def silhouette_centroid(
    frame_f: npt.NDArray[np.float32],
    cx: float,
    cy: float,
    peak: float,
    *,
    half_win: int = 90,
    k_sigma: float = 5.0,
) -> tuple[float, float]:
    """Intensity-weighted centroid of the warm body region connected to ``(cx, cy)``.

    Thresholds at ``base + k_sigma * border_std`` (just above the local background), so the
    DIM extended body -- not the bright hot pixel -- defines the footprint.  The luminance-
    weighted centroid of that connected region is the body centre; the hot pixel contributes
    only its (small) share of the total weight.  Falls back to ``(cx, cy)`` on a degenerate
    footprint.
    """
    frame_f = np.asarray(frame_f, dtype=np.float64)   # accept uint16 frames directly
    h, w = frame_f.shape
    x0 = max(0, int(cx) - half_win)
    x1 = min(w, int(cx) + half_win)
    y0 = max(0, int(cy) - half_win)
    y1 = min(h, int(cy) + half_win)
    patch = frame_f[y0:y1, x0:x1]
    if patch.size == 0:
        return float(cx), float(cy)
    border = np.concatenate([patch[0, :], patch[-1, :], patch[:, 0], patch[:, -1]])
    base = float(np.median(border))
    border_std = max(float(np.std(border)), 1.0)
    thr = base + k_sigma * border_std
    above = patch >= thr
    labeled, _ = ndi.label(above)
    ly, lx = int(cy) - y0, int(cx) - x0
    if not (0 <= ly < labeled.shape[0] and 0 <= lx < labeled.shape[1] and labeled[ly, lx] > 0):
        return float(cx), float(cy)
    region = labeled == labeled[ly, lx]
    wts = np.maximum(patch.astype(np.float64) - base, 0.0) * region
    total = float(wts.sum())
    if total <= 0.0:
        return float(cx), float(cy)
    yy = np.arange(y0, y1, dtype=np.float64)[:, None]
    xx = np.arange(x0, x1, dtype=np.float64)[None, :]
    sx = float((xx * wts).sum() / total)
    sy = float((yy * wts).sum() / total)
    return sx, sy


def migrate_aimpoint(
    frame_f: npt.NDArray[np.float32],
    centroid_px: tuple[float, float],
    peak: float,
    velocity_px_per_frame: tuple[float, float],
    regime: RegimeState,
    *,
    forward_bias_px: float = 0.0,
) -> tuple[float, float]:
    """Return the aimpoint for the current regime.

    POINT     -> the hotspot centroid unchanged (our current, correct behaviour at long range).
    RESOLVED/ -> the silhouette centroid, optionally shifted ``forward_bias_px`` toward the
    FILL         leading edge along the target's motion vector (a winged body is best aimed
                 slightly ahead of its geometric centre).
    """
    if regime == RegimeState.POINT:
        return float(centroid_px[0]), float(centroid_px[1])
    sx, sy = silhouette_centroid(frame_f, centroid_px[0], centroid_px[1], peak)
    if forward_bias_px > 0.0:
        vx, vy = velocity_px_per_frame
        vmag = math.hypot(vx, vy)
        if vmag > 1e-6:
            sx += forward_bias_px * vx / vmag
            sy += forward_bias_px * vy / vmag
    return sx, sy

```


## `vision/tracker/los.py`

```python
"""Body-frame LOS (line-of-sight) bearing and LOS-rate with ego-motion subtracted.

THIS IS THE CORE OF S2 — GET THE SIGNS RIGHT.

PHYSICAL IDENTITY (the whole point of S2)
------------------------------------------
Raw pixel motion of target centroid = TRUE target LOS motion + ego-rotation-induced motion

Rearranging:
    true_target_LOS_motion = raw_pixel_motion - ego_rotation_motion

The ego_rotation_motion is what ``egomotion.gyro_derotation`` predicts as
``EgoEstimate.shift_px``.

SIGN CHAIN (trace carefully)
------------------------------
Let:
    px_k = target pixel centroid at frame k  (image-x right, image-y down)
    ego_shift_k = EgoEstimate.shift_px at frame k = (-f·omega_y·dt, -f·omega_x·dt)

    This is the shift the SCENE appears to move in the image due to the camera
    rotating.  ego_shift_k is CUMULATIVE-incremental: it only represents the
    movement in the single interval [k-1, k].

WORLD-POSITION REPRESENTATION:
    Define "world pixel" W_k = px_k - SUM_{i=1}^{k} ego_shift_i
    This is the target's pixel coordinate in a frame fixed to the world (no ego).

    The true LOS-rate pixel velocity:
        v_true = (W_k - W_{k-1}) / dt
               = (px_k - SUM_ego_k - (px_{k-1} - SUM_ego_{k-1})) / dt
               = ((px_k - px_{k-1}) - ego_shift_k) / dt

    So:  v_true_x = (px_k - px_{k-1} - ego_dx_k) / dt
         v_true_y = (py_k - py_{k-1} - ego_dy_k) / dt

    This is NOT the same as diffing per-frame-subtracted positions
    (comp_px = px - ego_shift), because that gives:
        (px_k - ego_shift_k) - (px_{k-1} - ego_shift_{k-1})
        = (px_k - px_{k-1}) - (ego_shift_k - ego_shift_{k-1})  ← WRONG: diff of shifts

    The CORRECT approach is to diff the raw positions then subtract the ego shift:
        v_true_x = (px_k - px_{k-1}) / dt  -  ego_dx_k / dt

BEARING:
    The bearing is computed from the COMPENSATED position in the current frame.
    We maintain a running "world reference" pixel W_ref and compute:
        comp_px = px_k - cumulative_ego (maintained across frames)
    Then az, el = pixel_to_bearing(comp_px).

    For bearing: comp_px_k = px_k - cumulative_shift
    For rate: v_true = (raw_pixel_diff - ego_increment) / dt

CRITICAL NOTE ON SIGN OF el-RATE:
    If the target moves DOWN in the image (v_true_y > 0), the target is moving
    toward lower elevation (el is decreasing), so del/dt < 0.
    Formula: del/dt = -v_true_y / f correctly gives negative del/dt for downward motion.
    This is consistent with pixel_to_bearing(py) = atan2(-(py - cy), f).

OUTPUT CONTRACT (per frame)
----------------------------
LOSObservation:
    az_rad          — ego-compensated azimuth bearing (rad)
    el_rad          — ego-compensated elevation bearing (rad)
    az_rate_radps   — ego-corrected azimuth LOS-rate (rad/s), positive = target moving right
    el_rate_radps   — ego-corrected elevation LOS-rate (rad/s), positive = target moving up
    ego_quality     — EgoEstimate.quality [0, 1]
    ego_source      — 'gyro' | 'gyro+klt'
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .geometry import CameraIntrinsics, pixel_to_bearing
from .egomotion import EgoEstimate
from .derotate import world_pixel


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LOSObservation:
    """Per-frame ego-compensated LOS bearing and rate.

    Attributes
    ----------
    az_rad:
        Azimuth bearing in body frame (radians).  Positive = target right.
        Derived from ego-compensated centroid position.
    el_rad:
        Elevation bearing in body frame (radians).  Positive = target above boresight.
    az_rate_radps:
        Ego-corrected azimuth LOS-rate (rad/s).  Positive = target moving right
        in body frame.
    el_rate_radps:
        Ego-corrected elevation LOS-rate (rad/s).  Positive = target moving up.
    ego_quality:
        Ego estimate quality [0, 1] from EgoEstimate.
    ego_source:
        'gyro' or 'gyro+klt'.
    frame_id:
        Frame counter.
    t_capture_ns:
        CLOCK_MONOTONIC capture timestamp, nanoseconds.  None if unavailable.
    """

    az_rad: float
    el_rad: float
    az_rate_radps: float
    el_rate_radps: float
    ego_quality: float
    ego_source: Literal["gyro", "gyro+klt"]
    frame_id: int
    t_capture_ns: int | None = None


# ---------------------------------------------------------------------------
# LOS computer
# ---------------------------------------------------------------------------

class LOSComputer:
    """Stateful per-frame LOS bearing + rate computer with ego compensation.

    Ego-compensation algorithm
    --------------------------
    We maintain a running cumulative ego that accumulates both:
      (a) the translational shift from pitch/yaw (_cum_ego_x, _cum_ego_y)
      (b) the cumulative in-plane roll angle (_cum_roll_rad) from omega_z

    Per frame:
        1. Accumulate:  _cum_ego_x/y += ego.shift_px  (translation from pitch/yaw)
                        _cum_roll_rad += ego.roll_rad  (roll angle)
        2. World pixel: un-rotate THEN un-translate.
           The simulator applies rotation THEN translation:
               cam_px = cx + (dx_w * cos(theta) + dy_w * sin(theta)) + cum_trans_x
           Inverting: dx_w_rot = cam_px - cx - cum_trans_x
                      (dx_w, dy_w) = inv_rotate(dx_w_rot, dy_w_rot, cum_theta)
                      world_px = (cx + dx_w, cy + dy_w)
           For the world_px (no rotation needed for comparing frame to frame if
           we use the *rotated* world coords consistently), we use:
               world_px_x = (cam_px - cx - cum_trans_x) * cos(-theta) - (cam_py - cy - cum_trans_y) * sin(-theta) + cx
           This gives a coordinate in the un-rotated world frame.
        3. Bearing: az, el = pixel_to_bearing(world_px)
        4. Rate:    v_true = (world_px - prev_world_px) / dt
        5. Convert pixel velocity to angular rate.

    WHY TRACK ROLL SEPARATELY (not as incremental translation)?
    -----------------------------------------------------------
    Roll (omega_z) is an in-plane IMAGE ROTATION, not a translation.
    Accumulating incremental tangential shifts introduces errors that grow with
    the cumulative rotation angle (small-angle approximation breaks down over
    many frames).  Instead we track the cumulative roll angle and apply it as
    a full rotation to invert the sim's exact rotation.

    Usage
    -----
    ::

        computer = LOSComputer(intrinsics)
        for frame_data in stream:
            centroid_px = ...          # from S1 detect
            ego = gyro_derotation(...)  # from S2 egomotion
            los_obs = computer.update(centroid_px, ego, dt, frame_id)

    The first frame produces a LOS observation with zero LOS-rate (no previous
    world pixel to diff against).
    """

    def __init__(self, intrinsics: CameraIntrinsics) -> None:
        self._intrinsics = intrinsics
        # Cumulative translational ego shift from pitch/yaw (pixels)
        self._cum_ego_x: float = 0.0
        self._cum_ego_y: float = 0.0
        # Cumulative roll angle (radians) — body CCW rotation about boresight
        self._cum_roll_rad: float = 0.0
        # Previous WORLD pixel (centroid with all cumulative ego removed)
        self._prev_world_px: tuple[float, float] | None = None
        self._prev_frame_id: int | None = None

    def reset(self) -> None:
        """Reset state (e.g., after a track loss).

        After reset, the cumulative ego is zeroed.  The next call to update()
        establishes a new world-frame reference.
        """
        self._cum_ego_x = 0.0
        self._cum_ego_y = 0.0
        self._cum_roll_rad = 0.0
        self._prev_world_px = None
        self._prev_frame_id = None

    def update(
        self,
        centroid_px: tuple[float, float],
        ego: EgoEstimate,
        dt: float,
        frame_id: int,
        t_capture_ns: int | None = None,
    ) -> LOSObservation:
        """Compute one frame of ego-compensated LOS bearing and rate.

        Parameters
        ----------
        centroid_px:
            Raw observed target pixel centroid (x, y) from S1 detect.
        ego:
            Ego-motion estimate for this frame interval.
            ego.shift_px = (-f*omega_y*dt, -f*omega_x*dt) — translational shift
            from pitch/yaw.
            ego.roll_rad = omega_z * dt — in-plane rotation angle (positive = CCW
            body rotation about boresight = CW scene rotation in image).
        dt:
            Elapsed time since the previous frame (seconds).  Must be > 0.
        frame_id:
            Current frame index.
        t_capture_ns:
            Capture timestamp in nanoseconds (optional).

        Returns
        -------
        LOSObservation
            Ego-compensated bearing and LOS-rate.  LOS-rate is zero on the
            first call (no previous world pixel available).

        Roll handling (FIX 2026-06-17)
        --------------------------------
        Body roll omega_z causes an in-plane IMAGE ROTATION about the principal
        point — not a pure translation.  This is handled by tracking the
        cumulative roll angle (self._cum_roll_rad) and applying the INVERSE
        rotation to the camera pixel (after removing the translational ego) to
        recover the world-frame pixel.  This avoids the error accumulation that
        would result from approximating the rotation as incremental translations.
        """
        if dt <= 0.0:
            dt = 1e-3  # defensive: avoid division by zero; 1 ms fallback

        px, py = centroid_px
        ego_dx, ego_dy = ego.shift_px

        cx = self._intrinsics.cx
        cy = self._intrinsics.cy

        # STEP 1: Accumulate cumulative ego (translation from pitch/yaw + roll angle).
        # ego.shift_px = (-f*omega_y*dt, -f*omega_x*dt)  — translation from pitch/yaw.
        # ego.roll_rad = omega_z * dt                     — in-plane rotation angle.
        #
        # ROLL is tracked as an accumulated ANGLE (not as incremental translations).
        # Accumulating incremental tangential pixel shifts introduces second-order
        # errors that grow with total rotation angle.  We instead maintain the exact
        # cumulative angle and apply a full rotation inversion below.
        self._cum_ego_x += ego_dx
        self._cum_ego_y += ego_dy
        self._cum_roll_rad += ego.roll_rad

        # STEP 2: Compute the "world pixel" — the target position in the un-rotated,
        # un-translated world frame.
        #
        # The simulator (tracker_sim.py) generates target camera pixels as:
        #   cam_px = cx + (dx_w * cos(theta) + dy_w * sin(theta)) + cum_trans_x
        #   cam_py = cy + (-dx_w * sin(theta) + dy_w * cos(theta)) + cum_trans_y
        # where (dx_w, dy_w) is the world offset and theta = cumulative_roll_rad.
        #
        # Inverting to recover (dx_w, dy_w):
        #   dx_t_trans = (cam_px - cx) - cum_trans_x = dx_w*cos(theta) + dy_w*sin(theta)
        #   dy_t_trans = (cam_py - cy) - cum_trans_y = -dx_w*sin(theta)+dy_w*cos(theta)
        #   dx_w = dx_t_trans * cos(theta) - dy_t_trans * sin(theta)   [by inverse rot]
        #   dy_w = dx_t_trans * sin(theta) + dy_t_trans * cos(theta)
        # World pixel = (cx + dx_w, cy + dy_w).
        # Ego de-rotation -> world pixel. Extracted to derotate.world_pixel so the synthetic-event
        # motion channel (R6) reuses the exact same inversion; bit-identical to the prior inline math.
        world_px_x, world_px_y = world_pixel(
            px, py, self._cum_ego_x, self._cum_ego_y, self._cum_roll_rad, cx, cy)

        # STEP 3: Convert world pixel to body-frame bearing.
        # The world pixel is the target position as if the camera hadn't rotated.
        az, el = pixel_to_bearing(world_px_x, world_px_y, self._intrinsics)

        # STEP 4: Compute LOS-rate from successive world pixels.
        az_rate = 0.0
        el_rate = 0.0

        if self._prev_world_px is not None:
            prev_wx, prev_wy = self._prev_world_px
            # True pixel velocity in the world frame
            v_true_x = (world_px_x - prev_wx) / dt   # px/s, positive = right
            v_true_y = (world_px_y - prev_wy) / dt   # px/s, positive = down

            # Convert pixel velocity to angular rate using pinhole formula.
            # az  = atan2(dx_world, f)  where dx_world = world_px_x - cx
            # daz/dt = (f / (f² + dx_world²)) · d(dx_world)/dt
            #        = f * v_true_x / (f² + dx_world²)
            #
            # el  = atan2(-dy_world, f)  where dy_world = world_px_y - cy
            # del/dt = -(f / (f² + dy_world²)) · d(dy_world)/dt
            #        = -f * v_true_y / (f² + dy_world²)
            # The MINUS on el is critical: downward pixel motion → decreasing el.
            f = self._intrinsics.f_px
            dx_world = world_px_x - self._intrinsics.cx
            dy_world = world_px_y - self._intrinsics.cy

            az_rate = v_true_x * f / (f * f + dx_world * dx_world)
            el_rate = -v_true_y * f / (f * f + dy_world * dy_world)

        self._prev_world_px = (world_px_x, world_px_y)
        self._prev_frame_id = frame_id

        return LOSObservation(
            az_rad=az,
            el_rad=el,
            az_rate_radps=az_rate,
            el_rate_radps=el_rate,
            ego_quality=ego.quality,
            ego_source=ego.source,
            frame_id=frame_id,
            t_capture_ns=t_capture_ns,
        )

```


## `vision/tracker/looming.py`

```python
"""Optical looming: tau = A / (dA/dt) as a gated, weak closing-sign cue.

PURPOSE AND LIMITATIONS (honest, per design §3.2 and §3.3)
------------------------------------------------------------
tau = A / (dA/dt) estimates time-to-impact from the observed rate of blob-area
growth.  This is a WEAK, GATED cue used only as a cross-check on the sign and
rough order-of-magnitude of closing velocity.  It is NOT used as a reliable
range or Vc estimate.

The design §3.3 is explicit:
    "Vc is a SCHEDULED/assumed scalar from the speed policy; tau is not trusted"
    "looming-tau is used only as a confidence-gated cross-check of sign / order of magnitude"

Why tau is unreliable:
    (1) ACQUISITION (small blob, 1-3 px): dA/dt is dominated by detection noise
        (sub-pixel centroid jitter produces huge fractional area changes).
        tau_confidence → 0 in this regime.
    (2) SATURATION (large blob near impact, blob fills ROI): dA/dt underestimates
        the true rate because the blob is clipped by the sensor boundary.
        tau_confidence → 0 as blob area approaches saturation.
    (3) CROSSING GEOMETRY: dA/dt → 0 when the vehicle is not closing.
        tau → infinity.  Correctly reflected by low tau_confidence.

tau_confidence IS the primary output — callers should gate on it before using tau.

ALGORITHM
---------
1. Maintain a rolling exponential moving average of blob area to suppress
   single-frame detection noise.
2. Estimate dA/dt from the smoothed area history (linear regression over a
   short window, or finite difference when the window is short).
3. Compute tau = A_smoothed / dA_dt.  Reject negative tau (diverging target).
4. Compute tau_confidence as a product of three factors:
   - blob_size_factor:    0 when area < min_area_threshold (too few pixels)
                          ramps to 1 above a larger min threshold
   - saturation_factor:   0 when area > max_area_threshold (near sensor edge)
                          ramps to 0 above a saturation threshold
   - rate_snr_factor:     0 when |dA/dt| < noise floor (area barely changing)
                          ramps to 1 for clear area growth

closing_sign is derived from the sign of dA/dt:
    +1  — area growing   (closing)
    -1  — area shrinking (opening)
     0  — no clear trend (tau_confidence too low)
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LoomingEstimate:
    """Per-frame optical looming estimate.

    Attributes
    ----------
    tau_s:
        Estimated time-to-impact in seconds.  Positive = closing.
        Invalid / infinity when tau_confidence is low.
    tau_confidence:
        Scalar in [0, 1].  Collapses at small blob (acquisition) and at
        blob saturation (impact).  Only trust tau when this is > 0.5.
    closing_sign:
        +1 = closing, -1 = opening, 0 = indeterminate.
    area_smoothed_px:
        Exponentially-smoothed blob area estimate (pixels).
    d_area_dt_px_per_s:
        Estimated rate of area change (pixels per second).
    """

    tau_s: float
    tau_confidence: float
    closing_sign: int
    area_smoothed_px: float
    d_area_dt_px_per_s: float


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LoomingConfig:
    """Configuration for the LoomingEstimator.

    Attributes
    ----------
    area_ema_alpha:
        Exponential moving average coefficient for area smoothing.
        0 = no smoothing, 1 = instant tracking.  Default 0.3 (moderate).
    min_area_px:
        Minimum area (pixels) below which tau_confidence is set to 0 (blob
        too small — acquisition regime, 1-3 px).
    min_area_confident_px:
        Area above which the blob-size factor reaches 1.0.  Ramps linearly
        between min_area_px and this value.
    max_area_saturating_px:
        Area above which the saturation factor starts ramping down.
    max_area_saturated_px:
        Area above which tau_confidence contribution from saturation = 0.
    min_rate_px_per_s:
        Minimum |dA/dt| (pixels/s) to register as a meaningful rate.
        Below this → rate_snr_factor = 0.
    confident_rate_px_per_s:
        |dA/dt| above which rate_snr_factor = 1.0.  Ramps between min and this.
    window_frames:
        Number of frames to use for the dA/dt linear regression.
    max_tau_s:
        Maximum credible tau (seconds).  If the computed tau exceeds this cap,
        tau_confidence is set to 0 and closing_sign is set to 0 (indeterminate).
        Physically: tau > 30 s means the blob is barely growing — the estimate
        is noise-dominated and should not be trusted.  Default 30 s.
        Set to math.inf to disable the cap.
    """

    area_ema_alpha: float = 0.3
    min_area_px: float = 2.0
    min_area_confident_px: float = 8.0
    max_area_saturating_px: float = 500.0
    max_area_saturated_px: float = 1000.0
    min_rate_px_per_s: float = 0.5
    confident_rate_px_per_s: float = 5.0
    window_frames: int = 8
    max_tau_s: float = 30.0   # cap: tau > this → confidence = 0, closing_sign = 0


# ---------------------------------------------------------------------------
# Estimator
# ---------------------------------------------------------------------------

class LoomingEstimator:
    """Stateful per-frame looming estimator.

    Usage
    -----
    ::

        estimator = LoomingEstimator()
        for blob, dt in ...:
            est = estimator.update(blob.area_px, dt)
            if est.tau_confidence > 0.5:
                use_tau(est.tau_s, est.closing_sign)
    """

    def __init__(self, config: LoomingConfig | None = None) -> None:
        self._cfg = config or LoomingConfig()
        self._area_smoothed: float | None = None
        # Circular buffer of (area_smoothed, elapsed_time) for regression
        self._area_history: deque[tuple[float, float]] = deque(
            maxlen=self._cfg.window_frames
        )
        self._total_time: float = 0.0

    def reset(self) -> None:
        """Reset state (e.g., after track loss)."""
        self._area_smoothed = None
        self._area_history.clear()
        self._total_time = 0.0

    def update(self, area_px: float, dt: float) -> LoomingEstimate:
        """Process one frame's blob area.

        Parameters
        ----------
        area_px:
            Observed blob area in pixels (e.g., ``ThermalBlob.area_px``).
        dt:
            Elapsed time since the previous frame (seconds).

        Returns
        -------
        LoomingEstimate
        """
        cfg = self._cfg
        dt = max(dt, 1e-6)

        # ── EMA smoothing ──────────────────────────────────────────────────
        if self._area_smoothed is None:
            self._area_smoothed = area_px
        else:
            a = cfg.area_ema_alpha
            self._area_smoothed = a * area_px + (1.0 - a) * self._area_smoothed

        self._total_time += dt
        self._area_history.append((self._area_smoothed, self._total_time))

        area_s = self._area_smoothed

        # ── Estimate dA/dt ─────────────────────────────────────────────────
        d_area_dt = self._estimate_rate()

        # ── Compute tau ────────────────────────────────────────────────────
        if d_area_dt > 0.0 and area_s > 0.0:
            tau = area_s / d_area_dt
        else:
            tau = float("inf")

        # ── Closing sign ───────────────────────────────────────────────────
        if d_area_dt > cfg.min_rate_px_per_s:
            closing_sign = 1
        elif d_area_dt < -cfg.min_rate_px_per_s:
            closing_sign = -1
        else:
            closing_sign = 0

        # ── tau_confidence (product of three factors) ─────────────────────
        # Factor 1: blob too small (acquisition noise dominates)
        if area_s < cfg.min_area_px:
            size_factor = 0.0
        elif area_s < cfg.min_area_confident_px:
            size_factor = (area_s - cfg.min_area_px) / (
                cfg.min_area_confident_px - cfg.min_area_px
            )
        else:
            size_factor = 1.0

        # Factor 2: blob approaching saturation (near impact)
        if area_s > cfg.max_area_saturated_px:
            sat_factor = 0.0
        elif area_s > cfg.max_area_saturating_px:
            sat_factor = 1.0 - (area_s - cfg.max_area_saturating_px) / (
                cfg.max_area_saturated_px - cfg.max_area_saturating_px
            )
        else:
            sat_factor = 1.0

        # Factor 3: area rate too small (no clear approach trend)
        abs_rate = abs(d_area_dt)
        if abs_rate < cfg.min_rate_px_per_s:
            rate_factor = 0.0
        elif abs_rate < cfg.confident_rate_px_per_s:
            rate_factor = (abs_rate - cfg.min_rate_px_per_s) / (
                cfg.confident_rate_px_per_s - cfg.min_rate_px_per_s
            )
        else:
            rate_factor = 1.0

        tau_confidence = size_factor * sat_factor * rate_factor

        # Cap tau at a sensible maximum to avoid garbage values.
        # (a) Infinite or negative tau → zero confidence.
        if not math.isfinite(tau) or tau < 0.0:
            tau = float("inf")
            tau_confidence *= 0.0

        # (b) Excessively large tau → noise-dominated, zero confidence (Fix 5).
        #     max_tau_s is configurable; default 30 s.
        if math.isfinite(tau) and tau > cfg.max_tau_s:
            tau_confidence *= 0.0

        # (c) When tau_confidence == 0, set closing_sign = 0 (indeterminate).
        #     Per the documented API: 0 = indeterminate.  Callers MUST NOT act
        #     on a directional cue when confidence is zero.
        if tau_confidence == 0.0:
            closing_sign = 0

        return LoomingEstimate(
            tau_s=tau,
            tau_confidence=float(tau_confidence),
            closing_sign=closing_sign,
            area_smoothed_px=float(area_s),
            d_area_dt_px_per_s=float(d_area_dt),
        )

    def _estimate_rate(self) -> float:
        """Estimate dA/dt from the area history.

        Uses linear least-squares regression over the window when enough
        samples are available; falls back to a simple 2-point difference.
        """
        history = list(self._area_history)
        if len(history) < 2:
            return 0.0

        areas = [h[0] for h in history]
        times = [h[1] for h in history]

        if len(history) >= 3:
            # Linear regression: area = a*t + b, return slope a
            import numpy as np  # local import to keep the module lightweight
            t_arr = np.array(times, dtype=np.float64)
            a_arr = np.array(areas, dtype=np.float64)
            t_mean = t_arr.mean()
            a_mean = a_arr.mean()
            t_var = float(np.sum((t_arr - t_mean) ** 2))
            if t_var < 1e-12:
                return 0.0
            slope = float(np.sum((t_arr - t_mean) * (a_arr - a_mean)) / t_var)
            return slope

        # 2-point fallback
        dt = times[-1] - times[0]
        if dt < 1e-9:
            return 0.0
        return (areas[-1] - areas[0]) / dt

```


## `vision/tracker/range_observer.py`

```python
"""Tier-2 observability-gated inverse-range (rho = 1/r) observer — DIAGNOSTICS ONLY.

DOCTRINE (read before touching this file)
=========================================
This module implements the *Tier-2* range observer specified in
``docs/STATE_ESTIMATION_OBSERVABILITY_BRIEFING.md`` §3.2 and
``docs/BODY_AND_VV_BRIEFING.md``.  Its single, non-negotiable contract:

    The output of this observer feeds ONLY diagnostics, ``t_go`` shaping,
    the Vc_eff confidence blend, and the confirm-gate geometry term.
    IT MUST NEVER TOUCH THE PN NAVIGATION GAIN.

The PN gain stays ``Vc_sched`` from ``SpeedPolicy`` (design §3.3, control
briefing C3).  This separation is the *correct surrender* to a theorem we
cannot beat — the Fisher-information-matrix (FIM) rank-deficiency toward range
for a single passive monocular station holding a non-accelerating bearing
(briefing §1.1).  No filter, neural net, or amount of cleverness manufactures
range from a straight-line bearing history; the CRLB on range is infinite there.

The API encodes the doctrine: every estimate carries an ``observability`` index
and a ``valid`` flag.  When the geometry does not currently support range
(no own-maneuver parallax), the observer reports ``valid=False`` and
``range_m=None`` — *the estimator telling the truth about when it cannot see
range.*  Consumers MUST honour ``valid`` and the (wide) ``range_sigma``.

THE PHYSICS — WHY THESE THREE INPUTS, AND WHAT EACH OBSERVES
=============================================================
State: ``rho = 1/r`` (inverse range, metres⁻¹).  Inverse-range is the
quantity that stays bounded and near-Gaussian as ``r → ∞`` and whose Fisher
information is exactly what own-maneuver delivers (briefing §3.2).  Filtering
``1/r`` avoids the divergence a direct-range filter suffers when observability
lapses.

(a) LOOMING / τ  — the area-growth relation.
    A blob of a fixed-size target subtends an angular size ∝ 1/r, so its pixel
    AREA A ∝ (1/r)² = rho².  Differentiating:

        A_dot / A = 2 · rho_dot / rho            (the area-growth relation)
    ⇒   rho_dot / rho = A_dot / (2·A) = 1 / (2·τ)    since  τ = A / A_dot.

    This measures the *fractional* inverse-range rate (= closing-rate / range,
    i.e. Vc·rho).  It is an OBSERVABLE-SUBSPACE quantity (range-normalised
    closing rate); on its own it does NOT pin absolute rho without a size prior
    or maneuver.  It is the weak, gated closing-SIGN/ORDER cue of ``looming.py``.

(b) OWN LATERAL ACCELERATION ⟂ LOS — the parallax that makes range observable.
    For an inertial (non-maneuvering) target, an observer perpendicular
    acceleration ``a_perp`` curves the line of sight.  To first order the LOS
    rate acquires a term

        lambda_dot_induced  ≈  - a_perp · rho / Vc          (rad/s)

    i.e. the *change* in measured LOS-rate that our OWN maneuver injects is
    proportional to ``rho`` (and inversely to closing speed Vc).  Measuring how
    much our commanded ``a_perp`` bends the LOS gives a direct pseudo-measurement
    of ``rho`` — this is accelerated triangulation / baseline synthesis, the
    only passive range-recovery mechanism (briefing §1.2).  On a clean collision
    triangle ``a_perp → 0`` (PN nulls λ̇), the term vanishes, and range goes
    UNOBSERVABLE exactly as you close — the cruel catch the doctrine respects.

(c) IMM LOS-RATE  — supplies the measured ``lambda_dot`` (and Vc-context) for (b),
    and its innovation covariance bounds how much of an observed LOS-rate change
    we can attribute to our own maneuver vs. noise.

OBSERVABILITY INDEX (published, every frame)
============================================
The index is the instantaneous FIM-toward-range, accumulated over a window:

        Phi = Σ_window ( |a_perp| · dt / sigma_lambda_dot ) · rho_assumed

It is large when our perpendicular acceleration is large relative to the
LOS-rate noise floor (the parallax actually shows up above noise), and ~zero on
a clean collision triangle (a_perp ≈ 0).  When ``Phi < theta_obs`` the observer
COASTS on prior with inflated covariance and reports ``valid=False``.  The
looming channel alone NEVER raises observability — it is fused for the fractional
``rho_dot/rho`` consistency cross-check, not promoted to absolute range.

CPU: a 1-state EKF is single-digit microseconds.  Cheaper than one detection.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Output contract  (the API that encodes the doctrine)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RangeEstimate:
    """Per-frame Tier-2 inverse-range estimate.  DIAGNOSTICS / t_go / confirm ONLY.

    This estimate MUST NEVER feed the PN navigation gain.  Consumers must honour
    ``valid`` and the (wide) ``range_sigma``; treating a wide-covariance range as
    if it were tight is the failure mode the architecture forbids (briefing §5.6).

    Attributes
    ----------
    rho:
        Inverse-range estimate ``1/r`` in metres⁻¹.  Always populated (the filter
        state); but only meaningful when ``valid`` is True.
    range_m:
        Convenience ``1/rho`` in metres, or ``None`` when ``valid`` is False
        (range UNOBSERVABLE — the passive-monocular truth without maneuver/prior).
    range_sigma:
        1-sigma uncertainty on range (metres), propagated from the rho covariance.
        ``inf`` when unobservable.  ALWAYS wide on a passive station — honour it.
    rho_sigma:
        1-sigma uncertainty on the inverse-range state (metres⁻¹).
    observability:
        Published FIM-toward-range index (>= 0).  Range is reported only when this
        exceeds the configured threshold.  ~0 on a clean collision triangle.
    valid:
        True ⇔ ``observability`` cleared threshold this frame ⇒ a range may be
        read.  False ⇔ UNOBSERVABLE: coast on prior, ``range_m`` is None.
    closing_normalized:
        ``rho_dot / rho`` = Vc·rho = 1/(2·τ) from the looming channel — the
        observable-subspace fractional closing rate.  Sign/order cross-check only.
    frame_id:
        Frame index.
    """

    rho: float
    range_m: float | None
    range_sigma: float
    rho_sigma: float
    observability: float
    valid: bool
    closing_normalized: float = 0.0
    frame_id: int = 0


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RangeObserverConfig:
    """Configuration for the inverse-range observer.

    Attributes
    ----------
    rho_init:
        Initial inverse-range prior (m⁻¹).  Default 1/500 m — a deliberately
        weak, wide prior (we do not know range; this only seeds the filter).
    rho_init_sigma:
        Initial 1-sigma on rho (m⁻¹).  Wide by design.
    obs_threshold:
        Observability index threshold ``theta_obs``.  Below this, the observer
        reports ``valid=False`` (UNOBSERVABLE).  Dimensionless (accumulated
        |a_perp|·dt / sigma_lambda_dot · rho_assumed).
    obs_window_s:
        Sliding window (seconds) over which the observability index accumulates
        the perpendicular-acceleration parallax information.
    sigma_lambda_dot:
        LOS-rate measurement noise floor (rad/s) used both to scale the
        observability index and as the parallax pseudo-measurement noise.
    q_rho_rate:
        Process noise on rho per second (m⁻¹/√s)² — lets rho drift as we close.
    min_vc_mps:
        Floor on assumed closing speed (m/s) for the parallax model, to avoid a
        divide-by-zero when Vc is unknown/zero.
    min_a_perp_mps2:
        Minimum |a_perp| (m/s²) for a frame to contribute parallax information.
        Below this the maneuver is in the noise and is ignored for ranging.
    """

    rho_init: float = 1.0 / 500.0
    rho_init_sigma: float = 1.0 / 200.0
    obs_threshold: float = 1.0
    obs_window_s: float = 1.5
    sigma_lambda_dot: float = 0.005
    q_rho_rate: float = (1.0 / 2000.0) ** 2
    min_vc_mps: float = 1.0
    min_a_perp_mps2: float = 0.2


# ---------------------------------------------------------------------------
# Observer
# ---------------------------------------------------------------------------

class InverseRangeObserver:
    """1-state EKF on inverse-range ``rho = 1/r``, observability-gated.

    Diagnostics-only: the output feeds t_go / confirm-gate / Vc_eff blend, NEVER
    the PN gain.  See module docstring.

    Usage
    -----
    ::

        obs = InverseRangeObserver()
        for frame:
            est = obs.update(
                a_perp_mps2 = <own lateral accel perpendicular to LOS, m/s²>,
                lambda_dot_radps = <IMM LOS-rate magnitude, rad/s>,
                vc_mps = <assumed/scheduled closing speed, m/s>,
                tau_s = <looming tau, s>  (optional),
                tau_confidence = <looming confidence in [0,1]> (optional),
                dt = <seconds>,
            )
            if est.valid:
                use_for_diagnostics(est.range_m, est.range_sigma)  # NOT for PN
    """

    def __init__(self, config: RangeObserverConfig | None = None) -> None:
        self._cfg = config or RangeObserverConfig()
        self._rho: float = self._cfg.rho_init
        self._P: float = self._cfg.rho_init_sigma ** 2
        # Sliding window of (info_increment, dt) for the observability index.
        self._info_hist: deque[tuple[float, float]] = deque()
        self._window_time: float = 0.0
        self._frame_id: int = 0

    def reset(self) -> None:
        """Reset state (e.g., after track loss)."""
        self._rho = self._cfg.rho_init
        self._P = self._cfg.rho_init_sigma ** 2
        self._info_hist.clear()
        self._window_time = 0.0
        self._frame_id = 0

    def update(
        self,
        *,
        a_perp_mps2: float,
        lambda_dot_radps: float,
        vc_mps: float,
        dt: float,
        tau_s: float | None = None,
        tau_confidence: float = 0.0,
    ) -> RangeEstimate:
        """Process one frame and return a gated inverse-range estimate.

        Parameters
        ----------
        a_perp_mps2:
            Own lateral acceleration PROJECTED PERPENDICULAR TO THE LOS (m/s²).
            This is the maneuver that makes range observable; on a clean
            collision triangle it is ~0 and range stays UNOBSERVABLE.
        lambda_dot_radps:
            Magnitude of the IMM-filtered LOS-rate this frame (rad/s).  Used as
            the parallax pseudo-measurement: how much our a_perp bent the LOS.
        vc_mps:
            Assumed/scheduled closing speed (m/s) — from SpeedPolicy.  Context
            for the parallax model only; NOT an observed quantity.
        dt:
            Elapsed time since previous frame (s).
        tau_s, tau_confidence:
            Optional looming output.  Supplies the fractional ``rho_dot/rho``
            consistency cross-check.  Looming NEVER raises observability or pins
            absolute range on its own (no size prior).
        """
        cfg = self._cfg
        dt = max(dt, 1e-6)
        self._frame_id += 1

        # ── EKF predict: rho drifts (process noise), mean roughly constant over dt
        #    plus the deterministic closing drift rho_dot = rho²·Vc when known.
        vc = max(abs(vc_mps), cfg.min_vc_mps)
        rho_dot_closing = self._rho * self._rho * vc      # d(1/r)/dt = Vc/r² = rho²·Vc
        self._rho = self._rho + rho_dot_closing * dt
        self._rho = max(self._rho, 1e-9)
        self._P = self._P + cfg.q_rho_rate * dt

        # ── Observability index: instantaneous FIM-toward-range, windowed ──────
        #    info ∝ (|a_perp|·dt / sigma_lambda_dot) · rho_assumed
        a_perp = abs(a_perp_mps2)
        if a_perp >= cfg.min_a_perp_mps2:
            info_inc = (a_perp * dt / max(cfg.sigma_lambda_dot, 1e-9)) * self._rho
        else:
            info_inc = 0.0
        self._info_hist.append((info_inc, dt))
        self._window_time += dt
        while self._window_time > cfg.obs_window_s and len(self._info_hist) > 1:
            old_inc, old_dt = self._info_hist.popleft()
            self._window_time -= old_dt
        observability = sum(inc for inc, _ in self._info_hist)

        # ── Looming cross-check: rho_dot/rho = 1/(2τ) (the area-growth relation)
        closing_normalized = 0.0
        if tau_s is not None and tau_confidence > 0.0 and math.isfinite(tau_s) and tau_s > 1e-6:
            closing_normalized = 1.0 / (2.0 * tau_s)

        # ── EKF measurement update — PARALLAX (the only absolute-range info) ────
        #    Model: lambda_dot_induced = -a_perp · rho / Vc.  Measurement is the
        #    LOS-rate magnitude attributable to our own maneuver.  We only apply
        #    it when a_perp is above the maneuver floor (otherwise H≈0, no info).
        if a_perp >= cfg.min_a_perp_mps2:
            # h(rho) = a_perp · rho / Vc  (predicted induced LOS-rate magnitude)
            H = a_perp / vc                      # ∂h/∂rho
            z = abs(lambda_dot_radps)            # measured induced LOS-rate (mag)
            h = H * self._rho
            R = cfg.sigma_lambda_dot ** 2
            S = H * self._P * H + R
            K = self._P * H / S if S > 0.0 else 0.0
            self._rho = self._rho + K * (z - h)
            self._rho = max(self._rho, 1e-9)
            self._P = (1.0 - K * H) * self._P

        rho_sigma = math.sqrt(max(self._P, 0.0))

        # ── Gate on the published observability index ──────────────────────────
        valid = observability >= cfg.obs_threshold
        if valid and self._rho > 1e-9:
            range_m: float | None = 1.0 / self._rho
            # σ_range = σ_rho / rho²  (delta method on r = 1/rho)
            range_sigma = rho_sigma / (self._rho * self._rho)
        else:
            range_m = None
            range_sigma = float("inf")

        return RangeEstimate(
            rho=float(self._rho),
            range_m=(float(range_m) if range_m is not None else None),
            range_sigma=float(range_sigma),
            rho_sigma=float(rho_sigma),
            observability=float(observability),
            valid=bool(valid),
            closing_normalized=float(closing_normalized),
            frame_id=self._frame_id,
        )

```


## `vision/tracker/geometry.py`

```python
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
    Getting this wrong would silently invert the el-axis and cause control to
    fly the vehicle in the wrong pitch direction.

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
    fielded on the Block-3 vehicle.  The fielded camera is the Foxeer
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
    """Return intrinsics for the FOXEER FT640 V2 wide vision thermal tracker.

    This is the camera ACTUALLY fielded on the Block-3 vehicle and the
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
    ``platform.sensor.thermal_capture.ft640_intrinsics`` so sim and bench agree.
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

```


## `vision/tracker/event_channel.py`

```python
"""R6: synthetic-event log-contrast motion channel (the DVS *algorithm*, not the hardware).

A DVS responds to d(log I)/dt.  The LOG makes the response invariant to the *multiplicative* AGC
gain; the temporal DIFFERENCE makes static background vanish from the data until it moves.  We
emulate this on the FT640 today -- per-pixel log-intensity temporal difference on ego-shift-
compensated frames -- to get a target locator (and hence a lambda-dot) that the four closing-
operation nuisances (AGC gain pumping, background march, signature change, scale growth) are
BLIND to.

Honest framing: this is an INVARIANCE win, not a latency win -- the bolometer's ~10-15 ms thermal
time-constant caps any speed benefit; the value is robustness, not microsecond timing.

Doctrine (Inv 2): the output is a MOTION measurement (kinematic) -- the same class as the
intensity centroid -- not an appearance classifier or quality signal.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy import ndimage as ndi

#: A FT640 frame is uint16, so log I has only 65536 possible values.  Precomputing them in a LUT
#: turns the per-pixel float64 ``np.log`` (a top per-frame cost on the Pi5) into a single integer
#: gather -- BIT-IDENTICAL output (same float64 values, just table-driven).
_LOG_LUT: npt.NDArray[np.float64] = np.log(np.maximum(np.arange(65536, dtype=np.float64), 1.0))


class EventChannel:
    """Maintains one frame of log-intensity history and emits an AGC-invariant motion centroid."""

    def __init__(self, *, k_mad: float = 4.0, dilate: int = 1, min_pixels: int = 4) -> None:
        self._prev_logL: npt.NDArray[np.float64] | None = None
        self._k = float(k_mad)
        self._dilate = int(dilate)
        self._min_pixels = int(min_pixels)

    def reset(self) -> None:
        """Flush the history (call on an FFC event so stale shutter frames are not differenced)."""
        self._prev_logL = None

    def update(self, frame_u16: npt.NDArray[np.uint16],
               ego_shift_px: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float] | None:
        """Push a frame; return the |d(log I)/dt| motion-field centroid (px), or None.

        ``ego_shift_px`` is the gyro-derived per-frame scene shift (EgoEstimate.shift_px); the
        previous log-frame is registered by it so only INDEPENDENT motion survives the difference.
        """
        fu16 = np.asarray(frame_u16, dtype=np.uint16)
        # uint16 -> exact log via the module LUT (BIT-IDENTICAL to np.log(np.maximum(f, 1.0))).
        logL = _LOG_LUT[fu16]
        if self._prev_logL is None:
            self._prev_logL = logL
            return None
        prev = self._register(self._prev_logL, ego_shift_px)
        self._prev_logL = logL

        a = np.abs(logL - prev)
        # A constant log-gain step (AGC) shifts the whole field uniformly -> removed by the
        # MEDIAN-relative MAD threshold; only genuine local motion exceeds it.  Kept as a FULL-field
        # median (not subsampled): a strided subsample drifts the scalar threshold enough to flip a
        # lone boundary pixel and pull the emitted motion centroid a few px -- unacceptable noise to
        # inject into a kinematic (lambda-dot) measurement (Inv 2) to save a non-dominant ~10 ms.
        med = float(np.median(a))
        mad = float(np.median(np.abs(a - med))) * 1.4826 or 1e-6
        mask = a > (med + self._k * mad)
        if self._dilate > 0:
            mask = ndi.binary_dilation(mask, iterations=self._dilate)
        if int(mask.sum()) < self._min_pixels:
            return None
        w = a * mask
        total = float(w.sum())
        if total <= 0.0:
            return None
        h, wdt = logL.shape
        yy = np.arange(h, dtype=np.float64)[:, None]
        xx = np.arange(wdt, dtype=np.float64)[None, :]
        return float((xx * w).sum() / total), float((yy * w).sum() / total)

    @staticmethod
    def _register(logL_prev: npt.NDArray[np.float64],
                  ego_shift_px: tuple[float, float]) -> npt.NDArray[np.float64]:
        """Shift the previous log-frame by the ego scene-shift so static background cancels."""
        dx, dy = ego_shift_px
        if dx == 0.0 and dy == 0.0:
            return logL_prev
        return ndi.shift(logL_prev, (dy, dx), order=1, mode="nearest")

```


# Object-class discrimination (small CNN)


## `vision/tracker/classify/thermal_cnn.py`

```python
"""Small thermal object-vs-not CNN + the activate-permission vote (AI-firewall).

Trained on REAL thermal crops (PublicThermalDataset IR, object vs bird/plane/heli), clip-split:
test AUC 0.959, object recall 88.8%, distractor rejection 89.5%, 6% abstain. It converts the
tracker's "locks any hot flyer" behaviour (Gate-G-B: bird false-lock 0.78, plane 0.91) into a
default-deny activate-permission vote that blocks ~90% of those false-locks.

Wiring: `ObjectClassifier.vote(frame_u16, centroid_px)` -> PermitVote. The pipeline consumes it as an
AND-term of `activate_permitted` ONLY (never the centroid/LOS/tracker). torch is imported lazily so the
classical tracker has no hard torch dependency unless the learned vote is enabled.

CAVEATS (honest): trained on 8-bit display video (not Y16) with weak labels (strongest sky blob =
category), small clip-split test. Domain shift to the real Y16 sensor and novel/camouflaged targets
is UNVALIDATED — re-fit + re-measure on real-sensor data before trusting the vote in the field.
"""
from __future__ import annotations

import enum
import os
from dataclasses import dataclass

import cv2
import numpy as np

CROP = 48
OUT = 32
_WEIGHTS = os.path.join(os.path.dirname(__file__), "thermal_object_cnn.pt")


class PermitVote(str, enum.Enum):
    GRANT = "GRANT"       # confident object -> permits activate (still AND-ed with non-learned gates)
    DENY = "DENY"         # confident not-object -> withholds activate (default-deny)
    ABSTAIN = "ABSTAIN"   # low confidence -> withholds activate (default-deny)


@dataclass(frozen=True)
class ClassifierConfig:
    grant_above: float = 0.6      # p(object) above -> GRANT
    deny_below: float = 0.4       # p(object) below -> DENY; between -> ABSTAIN


def _build_net():
    import torch.nn as nn

    class ThermalObjectNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.f = nn.Sequential(
                nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(32, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2))
            self.head = nn.Sequential(
                nn.Flatten(), nn.Linear(32 * 4 * 4, 64), nn.ReLU(), nn.Dropout(0.3), nn.Linear(64, 1))

        def forward(self, x):
            return self.head(self.f(x)).squeeze(1)

    return ThermalObjectNet()


def crop_norm(frame_u16, cx, cy) -> np.ndarray:
    """Per-crop min-max normalized 32x32 patch around (cx,cy) — AGC-invariant appearance."""
    h, w = frame_u16.shape
    x0, y0 = int(round(cx)) - CROP // 2, int(round(cy)) - CROP // 2
    patch = np.zeros((CROP, CROP), np.float64)
    xs, ys = max(0, x0), max(0, y0)
    xe, ye = min(w, x0 + CROP), min(h, y0 + CROP)
    patch[ys - y0:ye - y0, xs - x0:xe - x0] = frame_u16[ys:ye, xs:xe]
    p = cv2.resize(patch, (OUT, OUT), interpolation=cv2.INTER_AREA)
    lo, hi = p.min(), p.max()
    return ((p - lo) / (hi - lo)).astype(np.float32) if hi > lo else np.zeros((OUT, OUT), np.float32)


class ObjectClassifier:
    """Learned object-vs-not vote. Consumes a locked-target crop, returns an activate-permission vote."""

    def __init__(self, weights_path: str = _WEIGHTS, config: ClassifierConfig | None = None):
        import torch
        self.cfg = config or ClassifierConfig()
        self.net = _build_net()
        if os.path.isfile(weights_path):
            self.net.load_state_dict(torch.load(weights_path, map_location="cpu"))
        self.net.eval()
        self._torch = torch

    def prob_object(self, frame_u16, centroid_px) -> float:
        x = self._torch.tensor(crop_norm(frame_u16, centroid_px[0], centroid_px[1]))[None, None]
        with self._torch.no_grad():
            return float(self._torch.sigmoid(self.net(x)).item())

    def vote(self, frame_u16, centroid_px) -> PermitVote:
        p = self.prob_object(frame_u16, centroid_px)
        if p >= self.cfg.grant_above:
            return PermitVote.GRANT
        if p <= self.cfg.deny_below:
            return PermitVote.DENY
        return PermitVote.ABSTAIN

    def permits(self, frame_u16, centroid_px) -> bool:
        """True ONLY on a confident GRANT; DENY and ABSTAIN both withhold (default-deny)."""
        return self.vote(frame_u16, centroid_px) == PermitVote.GRANT

    # Callable form so a ObjectClassifier can be passed straight as the pipeline's `discriminator`.
    def __call__(self, frame_u16, centroid_px) -> bool:
        return self.permits(frame_u16, centroid_px)

```


## `vision/tracker/classify/train.py`

```python
"""Reproducible training for the thermal object-vs-not CNN (Gate G-D recipe).

Given a directory of ``IR_{object,BIRD,HELICOPTER,object}_*.mp4`` thermal clips, this builds the
crop dataset (strongest sky-blob per sampled frame via the SAME detect_frame + crop_norm the
inference path uses), trains the SAME ThermalObjectNet architecture, reports a CLIP-SPLIT test AUC,
and writes weights loadable by ``ObjectClassifier``. When real Y16 sensor clips arrive, re-run this
to re-fit -- the recipe is in the repo, not a scratch notebook.

    PYTHONPATH=.:vision python3 -m vision.tracker.classify.train --clips /path/to/ir --out weights.pt
"""
from __future__ import annotations

import argparse
import glob
import os

import cv2
import numpy as np

from vision.tracker.detect import ThresholdState, detect_frame
from vision.tracker.classify.thermal_cnn import _build_net, crop_norm

CATS = {"object": 1, "BIRD": 0, "HELICOPTER": 0, "object": 0}
SKY_Y = 300.0


def _to_counts(frame) -> np.ndarray:
    """8-bit/colour or Y16 frame -> uint16 counts (hot=high); self-contained (no bench dependency)."""
    if frame.ndim == 2 and frame.dtype == np.uint16:
        return frame
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    gray = gray.astype(np.float64)
    if gray.max() > 255:
        gray = gray / gray.max() * 255.0
    return (4096.0 + gray * 42.0).clip(0, 65535).astype(np.uint16)


def build_dataset(clips_dir: str, per_clip: int = 12):
    crops, labels, clip_ids = [], [], []
    cid = 0
    for cat, lab in CATS.items():
        for p in sorted(glob.glob(os.path.join(clips_dir, f"IR_{cat}_*.mp4"))):
            cap = cv2.VideoCapture(p)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
            want = set(np.linspace(10, max(11, total - 5), per_clip).astype(int))
            ts = ThresholdState(); n = 0
            while True:
                ok, f = cap.read()
                if not ok:
                    break
                if n in want:
                    u16 = _to_counts(f)
                    if u16.shape != (512, 640):
                        u16 = cv2.resize(u16, (640, 512), interpolation=cv2.INTER_AREA)
                    blobs, ts = detect_frame(u16, cam_temp_c=25.0, ffc_state="READY", threshold_state=ts,
                                             frame_id=n, region_bands=4, graduated_k=True, max_blobs=30)
                    sky = [b for b in blobs if b.centroid_px[1] < SKY_Y]
                    if sky:
                        b = max(sky, key=lambda b: b.snr)
                        crops.append(crop_norm(u16, b.centroid_px[0], b.centroid_px[1]))
                        labels.append(lab); clip_ids.append(cid)
                n += 1
            cap.release(); cid += 1
    X = np.array(crops, np.float32)[:, None, :, :]
    return X, np.array(labels, np.int64), np.array(clip_ids, np.int64)


def _auc(scores, labels):
    order = np.argsort(scores); ranks = np.empty(len(order), float); ranks[order] = np.arange(1, len(scores) + 1)
    npos = labels.sum(); nneg = len(labels) - npos
    return (ranks[labels == 1].sum() - npos * (npos + 1) / 2) / max(npos * nneg, 1)


def train(X, y, clip, out_path: str, epochs: int = 40, seed: int = 0) -> float:
    import torch
    import torch.nn as nn
    torch.manual_seed(seed); np.random.seed(seed)
    rng = np.random.default_rng(1)
    clips = np.unique(clip); lab_of = {c: int(y[clip == c][0]) for c in clips}
    test = set()
    for lab in (0, 1):
        cs = [c for c in clips if lab_of[c] == lab]; rng.shuffle(cs)
        test.update(cs[:max(1, int(0.2 * len(cs)))])
    te = np.array([c in test for c in clip])
    net = _build_net(); opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-4)
    lossf = nn.BCEWithLogitsLoss()
    Xtr, ytr = torch.tensor(X[~te]), torch.tensor(y[~te], dtype=torch.float32)
    net.train()
    N = len(ytr)
    for _ in range(epochs):
        perm = torch.randperm(N)
        for i in range(0, N, 64):
            b = perm[i:i + 64]; opt.zero_grad(); lossf(net(Xtr[b]), ytr[b]).backward(); opt.step()
    net.eval()
    with torch.no_grad():
        p = torch.sigmoid(net(torch.tensor(X[te]))).numpy()
    auc = _auc(p, y[te])
    torch.save(net.state_dict(), out_path)
    print(f"trained on {int((~te).sum())} crops / {len(clips)-len(test)} clips; "
          f"test {int(te.sum())} crops / {len(test)} clips -> AUC {auc:.3f}  saved {out_path}")
    return auc


def main():
    ap = argparse.ArgumentParser(description="Train the thermal object-vs-not CNN (Gate G-D)")
    ap.add_argument("--clips", required=True)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "thermal_object_cnn.pt"))
    ap.add_argument("--per-clip", type=int, default=12)
    ap.add_argument("--epochs", type=int, default=40)
    a = ap.parse_args()
    X, y, clip = build_dataset(a.clips, a.per_clip)
    print(f"dataset: {len(y)} crops  object={int((y==1).sum())} not-object={int((y==0).sum())}  clips={len(set(clip.tolist()))}")
    train(X, y, clip, a.out, epochs=a.epochs)


if __name__ == "__main__":
    main()

```


# Closed-loop line-of-sight control


## `vision/control/bearing_rate.py`

```python
"""Bearing-rate-null control law for the Block-03 thermal vision vehicle.

HONEST PHYSICS — READ THIS FIRST
---------------------------------
The core law is:
    a_cmd = N * Vc_sched * lambda_dot

This is a BEARING-RATE NULLER, not a range-free PN miracle.

Why we schedule Vc (not measure it from tau):
    A passive monocular tracker WITHOUT own-maneuver parallax fundamentally cannot
    observe closing velocity Vc.  The only passive estimate is optical looming:
        tau = A / (dA/dt),  Vc_approx = range / tau
    But tau degenerates in three critical regimes:
        (1) ACQUISITION (1-3 px blob): dA/dt is noise-dominated.
        (2) CROSSING: dA/dt → 0 while lambda_dot is large → tau → inf.
        (3) IMPACT: blob fills FOV, dA/dt underestimates, tau collapses.
    These are EXACTLY the regimes where the control law runs.  So we SCHEDULE
    Vc from SpeedPolicy.  This is honest.  The law direction (sign of lambda_dot)
    comes from S2 IMM; the MAGNITUDE is set by Vc_sched.

Why N = 3 (not 4):
    Standard PN theory sets N in 3-5 for zero-lag control.  With sensor delay
    T_d > 25 ms and loop delay, the miss-distance term from delay scales as:
        miss ~ N * Vc * T_d^2 * a_T / 2
    Higher N amplifies BOTH the noise in lambda_dot AND the delay-induced
    oscillation.  Simulations (Gate L) confirm N=3 is more robust than N=4
    for sensor delays above ~30 ms.  The trade is: N=4 catches faster maneuvers
    but diverges sooner under delay.

Pure-pursuit blend:
    Pure pursuit points the vehicle toward the target, using ONLY the bearing
    (az, el), not the bearing rate or Vc.  It is Vc-free.  When tau_confidence
    is low (acquisition, crossing, impact-saturation), we blend toward pure pursuit
    to avoid Vc-blind failures.  The blend weight is:

        blend_factor = tau_confidence  (0 = pure pursuit, 1 = full bearing-rate-null)

    But note: the design says "tau_confidence" as a proxy for "do we trust the
    geometry well enough to use bearing-rate-null".  It is also low during crossing.
    This is correct behavior: at crossing, pure pursuit diverges less than an
    underscaled bearing-rate-null.

APN term:
    Augmented PN adds (N/2) * a_T to compensate for known target acceleration.
    a_T is estimated from the IMM maneuver mode.  We gate it strictly:
        - Only when IMM.maneuver_detected is True (sustained over N_SUSTAIN frames)
        - Only when the maneuver probability exceeds maneuver_prob_threshold
        - Magnitude capped at apn_accel_cap_mps2 to prevent noise amplification.

Envelope gate (policy safety):
    The platform's max achievable lateral acceleration:
        a_max = g * tan(theta_max_rad)
    At theta_max = 35 deg → a_max ≈ 6.87 m/s^2 ≈ 0.70 g
    At theta_max = 45 deg → a_max ≈ 9.81 m/s^2 ≈ 1.00 g

    The gate classifies geometry and raises POLICY_REJECT if:
        (a) High-crossing target: |lambda_dot| > crossing_rate_threshold AND the
            cross-range closing cue (from tau_confidence) is near-zero.
        (b) Required lateral-g exceeds achievable: |a_cmd| > a_max * halt_g_margin.

SIGN CONVENTIONS
-----------------
    az_rate_radps:  positive = target moving RIGHT in body frame.  Source: IMM.
    el_rate_radps:  positive = target moving UP in body frame.  Source: IMM.
    a_cmd_az_mps2:  positive = command vehicle to accelerate RIGHT.
                    This NULLS a rightward-moving target bearing: if target moves right
                    (lambda_dot_az > 0), we command rightward acceleration to follow it.
                    The LOS rate is nulled when the vehicle matches target motion.
    a_cmd_el_mps2:  positive = command vehicle to accelerate UP.
    Vc_sched:       positive = vehicle is closing on target (scalar).
    N:              positive (default 3).

UNITS
------
    All angles and rates: radians, rad/s.
    All accelerations: m/s^2.
    Vc: m/s.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Optional

import numpy as np

from vision.tracker.imm import IMMEstimate
from vision.tracker.looming import LoomingEstimate


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class GeometryClass(str, Enum):
    """Operation geometry classification."""
    HEAD_ON      = "HEAD_ON"       # |lambda_dot| < head_on_rate_threshold, closing
    QUARTERING   = "QUARTERING"    # Intermediate: oblique approach
    HIGH_CROSSING = "HIGH_CROSSING" # |lambda_dot| large, near-zero closing cue


class PolicyReject(Exception):
    """Raised when the operation geometry falls outside the achievable envelope.

    This is NOT a software error — it is a safety gate.  The caller must catch
    this and revert to a passive hold or safe-ditch depending on operation phase.

    Attributes
    ----------
    reason:
        Human-readable explanation.
    geometry:
        Classified operation geometry.
    required_g:
        The lateral acceleration (in g) the control law is demanding.
    achievable_g:
        The maximum lateral acceleration (in g) the platform can produce.
    """

    def __init__(
        self,
        reason: str,
        geometry: GeometryClass,
        required_g: float,
        achievable_g: float,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.geometry = geometry
        self.required_g = required_g
        self.achievable_g = achievable_g


@dataclass(frozen=True)
class ControlCommand:
    """Per-tick output of the control law.

    Attributes
    ----------
    a_cmd_az_mps2:
        Lateral acceleration command in the az (horizontal) plane (m/s^2).
        Positive = accelerate RIGHT to null a rightward-drifting target bearing.
    a_cmd_el_mps2:
        Lateral acceleration command in the el (vertical) plane (m/s^2).
        Positive = accelerate UP to null an upward-drifting target bearing.
    blend_factor:
        0.0 = pure pursuit only.  1.0 = full bearing-rate-null.
        Intermediate = weighted blend.
    geometry:
        Classified operation geometry.
    apn_active:
        True if the APN (Augmented PN) term was added this tick.
    Vc_sched_mps:
        Scheduled closing velocity used this tick (m/s).
    N_effective:
        Effective navigation ratio used (may differ from cfg.N if blended).
    required_g:
        Lateral demand in units of g (= a_total / 9.81).
    achievable_g:
        Achievable lateral limit in units of g (= a_max / 9.81).
    envelope_ok:
        True if required_g <= achievable_g * halt_g_margin (no halt raised).
    pursuit_az_mps2, pursuit_el_mps2:
        Pure-pursuit component of the command (for diagnostics).
    brn_az_mps2, brn_el_mps2:
        Bearing-rate-null component of the command (for diagnostics).
    """

    a_cmd_az_mps2: float
    a_cmd_el_mps2: float
    blend_factor: float
    geometry: GeometryClass
    apn_active: bool
    Vc_sched_mps: float
    N_effective: float
    required_g: float
    achievable_g: float
    envelope_ok: bool
    pursuit_az_mps2: float = 0.0
    pursuit_el_mps2: float = 0.0
    brn_az_mps2: float = 0.0
    brn_el_mps2: float = 0.0
    # --- A3 honesty fields (diagnostic; never feed back into the PN gain) ---
    t_go_s: float = float("inf")          # time-to-go (s); inf when unobservable
    t_go_source: str = "unobservable"     # "looming" | "unobservable"
    target_maneuver_ceiling_g: float = 0.0  # 3:1 overmatch rule: reliably-reachable target g
    terminal_hold: bool = False             # ten-tau wall: this command is a FROZEN impact course


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ControlConfig:
    """Configuration for the BearingRateController law.

    Attributes
    ----------
    N:
        Navigation ratio.  Default 3.  Range 3-4.
        Keep at 3 for sensor delays > 25 ms (see module docstring).
    Vc_sched_mps:
        Scheduled closing velocity (m/s).  This is the PRIMARY Vc source.
        Derived from own airspeed (SpeedPolicy) + assumed target speed.
        Typical value: own_speed + target_speed_assumed.
        Example: vehicle at 15 m/s vs target at 5 m/s head-on → Vc ≈ 20 m/s.
    theta_max_rad:
        Maximum tilt angle (radians).  a_max = g * tan(theta_max_rad).
        Design: 35 deg (0.611 rad) → 0.70 g; 45 deg (0.785 rad) → 1.00 g.
    halt_g_margin:
        Fraction of achievable_g above which POLICY_REJECT is raised.
        Default 0.90: halt if demand exceeds 90% of achievable lateral g.
    crossing_rate_threshold_radps:
        |lambda_dot| above which geometry is classified as HIGH_CROSSING.
        Default 0.15 rad/s (~8.6 deg/s).
    tau_confidence_pursuit_threshold:
        Below this tau_confidence, blend weight → pure pursuit.
        Default 0.3.
    tau_confidence_full_brn_threshold:
        Above this tau_confidence, blend weight → full bearing-rate-null.
        Default 0.7.
    pursuit_gain_mps2_per_rad:
        Gain for the pure-pursuit term (m/s^2 per radian of bearing error).
        Maps (az, el) bearing directly to lateral acceleration command.
        Physically: if target is at 0.1 rad (~5.7 deg) off-boresight and this
        gain is 10, the pursuit command is 1 m/s^2.
        Default: use Vc_sched as the gain (a = Vc * az/f ≈ Vc * az for small angles).
        Set to None to use Vc_sched dynamically.
    maneuver_prob_threshold:
        Minimum IMM maneuver probability for APN term to be active.
        Default 0.65.
    apn_accel_cap_mps2:
        Maximum |a_T| injected via APN term (m/s^2).  Prevents noise amplification.
        Default 3.0 m/s^2 (~0.3 g).
    max_a_cmd_mps2:
        Hard cap on the total lateral command magnitude (m/s^2).
        Safety floor below the POLICY_REJECT threshold.
        Default: g * tan(theta_max_rad) * halt_g_margin (set at runtime if 0).
    """

    N: float = 3.0
    Vc_sched_mps: float = 20.0           # vehicle ~15 m/s + target ~5 m/s head-on
    lead_time_s: float = 0.0             # W5: angular Smith-predictor lead (s); 0 = off (bit-identical)
    theta_max_rad: float = math.radians(40.0)  # 40 deg → ~0.84 g
    halt_g_margin: float = 1.0    # halt at 100% of achievable: command clamp is the real guard; margin > 1 silently saturates
    crossing_rate_threshold_radps: float = 0.15   # ~8.6 deg/s LOS rate → crossing
    # --- Vc-scaled crossing threshold (default-OFF -> bit-identical) ---
    # The fixed 0.15 rad/s was tuned for the OLD slow regime (Vc~20): at Vc=20 the airframe g-wall
    # a_lat = N*Vc*lambda_dot = a_max is reached at lambda_dot ~ a_max/(N*Vc) ~ 0.137 rad/s ~ 0.15.
    # At the high-speed regime (Vc~150-230) that same g-wall is hit at lambda_dot ~ 0.012-0.018 rad/s,
    # so a FIXED 0.15 threshold under-fires HIGH_CROSSING by ~8-12x and can leak a silent miss on a
    # non-closing crosser.  When ON, the crossing threshold IS the g-wall LOS rate lambda_dot_wall =
    # a_max/(N*Vc) -- the first-principles boundary where required_g == achievable_g -- so the
    # classifier tracks feasibility across the whole speed range (more permissive at low Vc where
    # crossings ARE achievable, more sensitive at high Vc where they are not).
    vc_scaled_crossing_threshold: bool = False
    tau_confidence_pursuit_threshold: float = 0.30
    tau_confidence_full_brn_threshold: float = 0.70
    pursuit_gain_mps2_per_rad: float = 0.0        # 0 = use Vc_sched dynamically
    maneuver_prob_threshold: float = 0.65
    apn_accel_cap_mps2: float = 3.0
    max_a_cmd_mps2: float = 0.0                   # 0 = derive from theta_max + margin
    # --- R2: NIS-scheduled lambda-dot smoothing (default-OFF -> bit-identical) ---
    # Smooth lambda-dot HARD when innovations are quiet (glint defence), and OPEN the loop as the
    # NIS rises / on a sustained model-wrong alarm (so a real jink is NOT lagged). The innovation
    # is the only honest glint-vs-maneuver discriminator. Purely an angular-rate filter -- no
    # range, state stays modified-polar (Inv 1/4).
    nis_lambda_smoothing: bool = False
    lambda_smooth_alpha_quiet: float = 0.3        # EMA weight when quiet (low = heavy smoothing)
    nis_chi2_open: float = 9.21                   # NIS at which the loop fully opens (alpha->1)
    # --- A1: ACQUIRE low-gain settling before full PN (default-OFF -> bit-identical) ---
    # Ramp the PN gain from a benign fraction to full N over the first ticks of the operation,
    # so the first commands after lock-on are gentle while the LOS estimate is still settling
    # (the falcon's feed-forward lock-on phase before terminal PN). 0 ticks = off.
    acquire_settle_ticks: int = 0
    acquire_settle_min_frac: float = 0.3          # starting gain fraction of N at tick 1

    def a_max_mps2(self) -> float:
        """Maximum achievable lateral acceleration (m/s^2)."""
        return 9.81 * math.tan(self.theta_max_rad)

    def effective_crossing_threshold(self, Vc_mps: float) -> float:
        """The LOS-rate threshold used to classify HIGH_CROSSING at this closing speed.

        OFF (default): the fixed ``crossing_rate_threshold_radps`` -> bit-identical to before.
        ON: the g-wall LOS rate ``lambda_dot_wall = a_max/(N*Vc)`` -- the rate at which the PN
        demand ``N*Vc*lambda_dot`` equals the achievable lateral accel ``a_max``.  This is the
        physical feasibility boundary, so it scales correctly with Vc.
        """
        if not self.vc_scaled_crossing_threshold:
            return self.crossing_rate_threshold_radps
        return self.a_max_mps2() / (self.N * max(Vc_mps, 0.1))

    def achievable_g(self) -> float:
        """Maximum achievable lateral acceleration in units of g."""
        return math.tan(self.theta_max_rad)

    def effective_max_a_cmd(self) -> float:
        """Effective hard cap on |a_cmd| (m/s^2).

        HONEST PHYSICS: the clamp must agree with the halt boundary.
        halt_g_margin=1.0 means we halt at a_max.  The clamp is set to
        a_max so that control and plant agree on the physical limit.
        With halt_g_margin=1.0 and the clamp at a_max, there is no silent
        20% saturation margin — what the halt sees is what the actuator sees.
        """
        if self.max_a_cmd_mps2 > 0.0:
            return self.max_a_cmd_mps2
        # Cap at true achievable a_max (NOT a_max * margin):
        return self.a_max_mps2()


# ---------------------------------------------------------------------------
# Control law
# ---------------------------------------------------------------------------

class BearingRateController:
    """Body-frame bearing-rate-null control law with pursuit blend.

    See module docstring for the honest physics description.

    State
    -----
    The law maintains a tick counter to implement a warmup guard before
    HIGH_CROSSING halt can fire.  The tracker needs several frames to
    establish geometry (distinguish "small blob approaching" from "crossing
    target").  During warmup, HIGH_CROSSING classification is suppressed.

    Usage
    -----
    ::
        cfg = ControlConfig(N=3, Vc_sched_mps=20.0, theta_max_rad=math.radians(40))
        control = BearingRateController(cfg)

        # Each tick (at control rate, decoupled from vision):
        try:
            cmd = control.compute(imm_estimate, looming_estimate)
        except PolicyReject as halt:
            handle_halt(halt)

    Thread safety
    -------------
    BearingRateController is NOT stateless — it tracks tick count for warmup.
    Use from a single control thread only.
    """

    # Minimum ticks before HIGH_CROSSING halt can fire.
    # At 250 Hz, 250 ticks = 1 second of operation data.
    # This prevents startup-noise and looming-uninitialized halts.
    # The physical justification: the tracker needs ~0.5s (typical: 30 vision frames)
    # to establish both bearing rate trend and looming signal.
    _CROSSING_WARMUP_TICKS: int = 125   # 0.5 s at 250 Hz

    def __init__(self, config: ControlConfig | None = None) -> None:
        self._cfg = config or ControlConfig()
        self._tick: int = 0   # monotonic tick counter for warmup guard
        # R2 NIS-scheduled lambda-dot EMA state (None until first tick).
        self._lambda_dot_az_ema: float | None = None
        self._lambda_dot_el_ema: float | None = None
        self._last_cmd: ControlCommand | None = None   # ten-tau wall: last established course

    @property
    def config(self) -> ControlConfig:
        return self._cfg

    def compute(
        self,
        imm: IMMEstimate,
        looming: LoomingEstimate,
        *,
        Vc_override_mps: float | None = None,
        confirmed: bool = False,
        terminal_hold: bool = False,
    ) -> ControlCommand:
        """Compute one control tick.

        Parameters
        ----------
        imm:
            Filtered LOS state from S2 IMMFilter (body-frame az/el/rates).
        looming:
            Looming estimate from S2 LoomingEstimator (tau, tau_confidence).
        Vc_override_mps:
            If supplied, override the configured Vc_sched.  Used for testing or
            SpeedPolicy integration where the outer loop provides a current speed.

        Returns
        -------
        ControlCommand
            Lateral acceleration commands in az and el.

        Raises
        ------
        PolicyReject
            If the operation geometry exceeds the achievable lateral-g envelope
            or is classified as HIGH_CROSSING.
        """
        cfg = self._cfg
        self._tick += 1

        # ── A1: ACQUIRE low-gain settling ─────────────────────────────────────
        # Ramp the PN gain from acquire_settle_min_frac*N up to full N over the first
        # acquire_settle_ticks; gentle corrections while the lock settles. 0 ticks -> gain 1.0.
        if cfg.acquire_settle_ticks > 0 and self._tick <= cfg.acquire_settle_ticks:
            acquire_gain = cfg.acquire_settle_min_frac + (1.0 - cfg.acquire_settle_min_frac) * (
                self._tick / cfg.acquire_settle_ticks)
        else:
            acquire_gain = 1.0

        # ── Vc scheduling ────────────────────────────────────────────────────
        Vc = Vc_override_mps if Vc_override_mps is not None else cfg.Vc_sched_mps
        Vc = max(Vc, 0.1)  # defensive: Vc must be positive

        # ── LOS-rate from IMM ────────────────────────────────────────────────
        # IMM gives filtered (az_rate_radps, el_rate_radps) in body frame.
        # Sign: az_rate > 0 → target drifting RIGHT; el_rate > 0 → target drifting UP.
        lambda_dot_az = imm.az_rate_radps
        lambda_dot_el = imm.el_rate_radps

        # Non-finite LOS rate (malformed IMM) -> fail safe to a labelled HALT, never let
        # NaN poison the blend/command and trip a generic, mis-labelled envelope halt (C6).
        if not (math.isfinite(lambda_dot_az) and math.isfinite(lambda_dot_el)):
            raise PolicyReject(
                reason="non-finite LOS rate from IMM -> fail-safe HALT",
                geometry=GeometryClass.HIGH_CROSSING,
                required_g=float("inf"),
                achievable_g=cfg.achievable_g(),
            )

        # ── Ten-tau wall / impact-freeze (W4) ────────────────────────────────
        # In the terminal window lambda_dot = Vt_perp/R blows up as R->0, demanding g the airframe
        # cannot pull; chasing it wastes authority and WORSENS miss. Inside the wall we FREEZE the
        # last established collision-course command and fly it straight in -- corrections must have
        # completed before this point. `terminal_hold` is decided upstream from a RANGE-FREE subtense
        # proxy (target filling the FOV => very close). Fail-safe: no established course -> compute.
        if terminal_hold and self._last_cmd is not None:
            return replace(self._last_cmd, terminal_hold=True)

        # ── R2: NIS-scheduled lambda-dot smoothing ───────────────────────────
        # Heavy EMA when innovations are quiet (reaches glint walk on the aimpoint); the weight
        # rises with the IMM NIS and snaps fully open on a sustained model-wrong alarm, so a real
        # maneuver is responsive, never lagged. OFF -> raw IMM rate (bit-identical).
        if cfg.nis_lambda_smoothing:
            nis = imm.nis if math.isfinite(imm.nis) else cfg.nis_chi2_open
            alpha = cfg.lambda_smooth_alpha_quiet + (1.0 - cfg.lambda_smooth_alpha_quiet) * min(
                max(nis, 0.0) / max(cfg.nis_chi2_open, 1e-9), 1.0)
            if imm.model_wrong_alarm:
                alpha = 1.0
            if self._lambda_dot_az_ema is None:
                self._lambda_dot_az_ema = lambda_dot_az
                self._lambda_dot_el_ema = lambda_dot_el
            else:
                self._lambda_dot_az_ema += alpha * (lambda_dot_az - self._lambda_dot_az_ema)
                self._lambda_dot_el_ema += alpha * (lambda_dot_el - self._lambda_dot_el_ema)
            lambda_dot_az = self._lambda_dot_az_ema
            lambda_dot_el = self._lambda_dot_el_ema

        # ── Geometry classification ──────────────────────────────────────────
        # LOS rate magnitude — proxy for crossing geometry
        lambda_dot_mag = math.sqrt(lambda_dot_az ** 2 + lambda_dot_el ** 2)
        crossing_threshold = cfg.effective_crossing_threshold(Vc)
        geometry = self._classify_geometry(lambda_dot_mag, looming, self._tick,
                                           crossing_threshold=crossing_threshold)

        # ── policy-HALT: high-crossing geometry ────────────────────────────────
        # High-crossing: large LOS rate + low closing confidence.
        # Physical reason: at crossing, dA/dt → 0, tau → inf, Vc underestimated
        # even from SpeedPolicy (Vc_proj = Vc * cos(crossing_angle) → 0).
        # Platform energy budget cannot close a high-g crossing rendezvous.
        # TWO-PHASE (mature-doctrine Axis II): the envelope HALT is a PRE-CONFIRM gate only --
        # do not CONFIRM into an infeasible crossing.  POST-CONFIRM the tracker is a doer, not a
        # doubter: it does NOT halt on geometry, it pushes through with the best clamped command
        # (below), and halt is reserved for HARD self-safe (CIVCAS keep-out / geo / genuine target
        # loss) handled by the activate-FSM, never here.  (Non-finite LOS above stays a fault-halt.)
        if geometry == GeometryClass.HIGH_CROSSING and not confirmed:
            required_g = lambda_dot_mag * Vc * cfg.N / 9.81
            achievable_g = cfg.achievable_g()
            # The 3:1 overmatch rule (a multirotor needs ~3x the target's lateral-g to
            # rendezvous) is the PHYSICAL reason this halt exists, not a tunable threshold:
            # a crosser drives required-g toward the regime our 0.84 g body cannot fly.
            raise PolicyReject(
                reason=(
                    f"HIGH_CROSSING geometry: lambda_dot_mag={lambda_dot_mag:.4f} rad/s "
                    f"> threshold={crossing_threshold:.4f} rad/s, "
                    f"tau_confidence={looming.tau_confidence:.3f} (low), "
                    f"required_g={required_g:.2f} > achievable_g={achievable_g:.2f}; "
                    f"3:1 overmatch -> reliably-reachable target maneuver "
                    f"ceiling ~{achievable_g / 3.0:.2f} g"
                ),
                geometry=geometry,
                required_g=required_g,
                achievable_g=achievable_g,
            )

        # ── Blend weight: tau_confidence drives blend ────────────────────────
        # blend_factor=0 → pure pursuit (Vc-free, uses bearing directly)
        # blend_factor=1 → full bearing-rate-null (requires Vc)
        # Sanitize a non-finite tau_confidence to 0 (pure pursuit) so it cannot produce a
        # NaN blend -> NaN command (C6).  The wired LoomingEstimator is finite-guarded; this
        # protects the public compute() API and any future adapter.
        tau_conf = looming.tau_confidence if math.isfinite(looming.tau_confidence) else 0.0
        blend_factor = _blend_weight(
            tau_conf,
            low_thresh=cfg.tau_confidence_pursuit_threshold,
            high_thresh=cfg.tau_confidence_full_brn_threshold,
        )

        # ── Pure-pursuit component ────────────────────────────────────────────
        # Pure pursuit: point toward the target.
        # Acceleration to null bearing = Vc * bearing (small angle approximation).
        # Physical: to close the angle, we accelerate toward where the target IS,
        # not where it's going.  This doesn't need Vc — we use Vc as a proxy gain
        # because a_cmd ~ v * angle for turning at speed v.
        pursuit_gain = cfg.pursuit_gain_mps2_per_rad if cfg.pursuit_gain_mps2_per_rad > 0.0 else Vc
        # W5 latency lead (Smith-predictor, purely ANGULAR -> no range dependence): aim at where the
        # bearing WILL be after the loop transport delay, az + az_rate*lead_time. 0 -> stale bearing.
        az_lead = imm.az_rad + imm.az_rate_radps * cfg.lead_time_s
        el_lead = imm.el_rad + imm.el_rate_radps * cfg.lead_time_s
        pursuit_az = pursuit_gain * az_lead
        pursuit_el = pursuit_gain * el_lead

        # ── Bearing-rate-null component (the PN law) ─────────────────────────
        # a_cmd = N * Vc * lambda_dot
        # Sign: lambda_dot_az > 0 (target moving right) → a_cmd_az > 0 (command right).
        # Physical interpretation: we command the vehicle to match the target's
        # angular motion, which creates the collision-triangle condition.
        brn_az = cfg.N * acquire_gain * Vc * lambda_dot_az
        brn_el = cfg.N * acquire_gain * Vc * lambda_dot_el

        # ── APN term: (N/2) * a_T (only when IMM confidently detects maneuver) ─
        # APN compensates for known target acceleration, halving the miss vs a jinking
        # target.  We gate it STRICTLY because a_T estimation from IMM is noisy.
        apn_az = 0.0
        apn_el = 0.0
        apn_active = False

        if (
            imm.maneuver_detected
            and imm.mode_probs[1] >= cfg.maneuver_prob_threshold
        ):
            # APN UNITS FIX — previous code computed Vc * innovation_az which is
            # dimensionally [m/s * rad] = NOT an acceleration.
            #
            # Correct APN: a_cmd_apn = (N/2) * a_T where a_T is target lateral
            # acceleration in m/s^2.  APN requires range to be known:
            #     a_T = range * d²λ/dt²
            # Since range is NOT observable from a passive monocular tracker, we
            # CANNOT compute a_T correctly here.  Options:
            #   (A) Remove APN entirely (honest: no range = no APN)
            #   (B) Use IMM rate-innovation / dt as a raw angular-accel estimate,
            #       then multiply by range_assumed.  But range_assumed = 0 here.
            #
            # Decision: REMOVE the dimensionally-wrong APN term.
            # The pure bearing-rate-null law (N*Vc*lambda_dot) is correct without APN.
            # APN can be re-enabled when range becomes observable (e.g., via looming
            # or RF triangulation): a_T = range * imm.az_rate_innovation / dt.
            #
            # We keep apn_active=True to log that the maneuver was detected, even
            # though the APN acceleration contribution is zero.
            apn_az = 0.0
            apn_el = 0.0
            apn_active = True

        # ── Blend: combine pursuit and bearing-rate-null ─────────────────────
        total_az = (1.0 - blend_factor) * pursuit_az + blend_factor * (brn_az + apn_az)
        total_el = (1.0 - blend_factor) * pursuit_el + blend_factor * (brn_el + apn_el)

        # ── Envelope check ───────────────────────────────────────────────────
        a_total = math.sqrt(total_az ** 2 + total_el ** 2)
        a_max = cfg.a_max_mps2()
        required_g = a_total / 9.81
        achievable_g = cfg.achievable_g()
        envelope_ok = a_total <= a_max * cfg.halt_g_margin

        # policy-HALT: demand exceeds achievable g.  PRE-CONFIRM only (Axis II): post-confirm we push
        # through with the hard-cap clamp below (best-effort complete) rather than halt on demand.
        if not envelope_ok and not confirmed:
            raise PolicyReject(
                reason=(
                    f"Lateral demand {a_total:.2f} m/s^2 ({required_g:.2f} g) "
                    f"exceeds achievable {a_max * cfg.halt_g_margin:.2f} m/s^2 "
                    f"({achievable_g * cfg.halt_g_margin:.2f} g at {math.degrees(cfg.theta_max_rad):.0f} deg tilt). "
                    f"Geometry: {geometry.value}.  This operation is out of envelope."
                ),
                geometry=geometry,
                required_g=required_g,
                achievable_g=achievable_g,
            )


        # ── Hard cap (safety floor) ───────────────────────────────────────────
        max_cmd = cfg.effective_max_a_cmd()
        total_az = _clamp(total_az, -max_cmd, max_cmd)
        total_el = _clamp(total_el, -max_cmd, max_cmd)

        # ── A3 honesty: continuous N_effective, t_go, 3:1 maneuver ceiling ────
        # N slides from pursuit (N'≈1, no lead) to full PN (N) with the blend weight,
        # so the field reads as "how much lead are we applying" rather than echoing cfg.N.
        n_effective = blend_factor * cfg.N * acquire_gain + (1.0 - blend_factor) * 1.0
        # t_go is honest ONLY when looming gives a confident, finite, positive tau;
        # otherwise it is unobservable (passive monocular).  Diagnostic only.
        if (looming.tau_confidence >= cfg.tau_confidence_full_brn_threshold
                and math.isfinite(looming.tau_s) and looming.tau_s > 0.0):
            t_go_s, t_go_source = float(looming.tau_s), "looming"
        else:
            t_go_s, t_go_source = float("inf"), "unobservable"
        # 3:1 overmatch rule: we reliably rendezvous a target maneuvering below ~a_max/3.
        target_ceiling_g = achievable_g / 3.0

        cmd = ControlCommand(
            a_cmd_az_mps2=total_az,
            a_cmd_el_mps2=total_el,
            blend_factor=blend_factor,
            geometry=geometry,
            apn_active=apn_active,
            Vc_sched_mps=Vc,
            N_effective=n_effective,
            required_g=a_total / 9.81,
            achievable_g=achievable_g,
            envelope_ok=envelope_ok,
            pursuit_az_mps2=pursuit_az,
            pursuit_el_mps2=pursuit_el,
            brn_az_mps2=brn_az,
            brn_el_mps2=brn_el,
            t_go_s=t_go_s,
            t_go_source=t_go_source,
            target_maneuver_ceiling_g=target_ceiling_g,
        )
        self._last_cmd = cmd                            # ten-tau wall: remember the established course
        return cmd

    def _classify_geometry(
        self,
        lambda_dot_mag: float,
        looming: LoomingEstimate,
        tick: int = 0,
        crossing_threshold: float | None = None,
    ) -> GeometryClass:
        """Classify operation geometry from LOS rate and looming cues.

        HIGH_CROSSING requires ALL of:
          (1) large LOS rate magnitude (target sweeping across FOV)
          (2) looming confidence is low (area not growing = not closing)
          (3) tick >= _CROSSING_WARMUP_TICKS (tracker initialized, not startup noise)

        The warmup guard prevents HIGH_CROSSING classification during the first
        0.5s when looming hasn't established the closure signal yet.
        A large LOS rate alone (pure pursuit, early acquisition) is not crossing.

        Parameters
        ----------
        lambda_dot_mag:
            |lambda_dot| in rad/s (from IMM).
        looming:
            Looming estimate (tau_confidence, closing_sign).
        tick:
            Current tick count.  HIGH_CROSSING suppressed before warmup.
        """
        cfg = self._cfg
        thr = cfg.crossing_rate_threshold_radps if crossing_threshold is None else crossing_threshold
        is_high_rate = lambda_dot_mag > thr

        # Warmup guard: do not fire HIGH_CROSSING before tracker is initialized.
        # Physically: the tracker needs several frames to distinguish "small blob
        # approaching" from "crossing target with constant area".
        past_warmup = tick >= self._CROSSING_WARMUP_TICKS

        # Closing determination: either tau_confidence is low (area not growing)
        # OR closing_sign indicates not-approaching.
        # closing_sign = 0 is acceptable after warmup (means area rate near zero →
        # consistent with crossing or very-slow-approach).
        # Use `not (>=)` so a non-finite tau_confidence reads as NOT-closing (fail-safe to
        # HIGH_CROSSING), where `< 0.3` would be False on NaN and silently mis-label (C6).
        is_not_closing = (not (looming.tau_confidence >= 0.3)) or looming.closing_sign <= 0

        if is_high_rate and is_not_closing and past_warmup:
            return GeometryClass.HIGH_CROSSING
        if is_high_rate:
            return GeometryClass.QUARTERING
        return GeometryClass.HEAD_ON


# ---------------------------------------------------------------------------
# Vc scheduling from SpeedPolicy
# ---------------------------------------------------------------------------

def schedule_Vc_mps(
    own_airspeed_mps: float,
    target_speed_assumed_mps: float = 5.0,
    geometry: GeometryClass = GeometryClass.HEAD_ON,
) -> float:
    """Schedule closing velocity from own airspeed and assumed target speed.

    For head-on and quartering geometry, Vc = own_speed + target_speed.
    For crossing, Vc_proj = Vc * cos(crossing_angle) — but we don't call this
    for crossing because that triggers POLICY_REJECT.

    This is the HONEST Vc estimate: we do not pretend to know target speed
    precisely.  The assumption (5 m/s default) is a conservative floor.
    Real operations are near-head-on where own-airspeed dominates.

    Parameters
    ----------
    own_airspeed_mps:
        Vehicle airspeed (m/s).
    target_speed_assumed_mps:
        Assumed target airspeed for closing-rate calculation (m/s).
        Use operator knowledge or default 5 m/s (slow DJI-class object).
    geometry:
        Classified geometry.  Used for a cosine projection correction.

    Returns
    -------
    float
        Scheduled Vc (m/s), always positive.
    """
    # Head-on or quartering: Vc ≈ own_speed + target_speed (relative approach)
    # Quartering: project by cos(45 deg) ≈ 0.707
    if geometry == GeometryClass.HEAD_ON:
        Vc = own_airspeed_mps + target_speed_assumed_mps
    else:  # QUARTERING
        Vc = (own_airspeed_mps + target_speed_assumed_mps) * math.cos(math.radians(22.5))
    return max(Vc, 1.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blend_weight(tau_conf: float, low_thresh: float, high_thresh: float) -> float:
    """Linearly ramp blend from 0 (pure pursuit) to 1 (full BRN) with tau_confidence."""
    if tau_conf <= low_thresh:
        return 0.0
    if tau_conf >= high_thresh:
        return 1.0
    return (tau_conf - low_thresh) / (high_thresh - low_thresh)


def _clamp(v: float, lo: float, hi: float) -> float:
    return min(max(v, lo), hi)

```


## `vision/control/pipeline.py`

```python
"""Tracker -> control pipeline (Block-3 piece #1): a thermal frame + gyro -> AICommand.

This is the real onboard perception+control chain, wired from the VERIFIED component
modules (S1 detect, S2 ego/los/imm/looming, S3 bearing-rate control + pilot). It is what
feeds the OnboardRuntime's ``control_command`` input -- replacing the test stub with the
actual pipeline, so the whole Block-3 system runs end to end: pixels in, RC out.

Per frame:
    detect_frame (S1)            -> hot blobs
    ThermalLockTracker.update    -> single-target lock / coast / reacquire
    gyro_derotation + LOSComputer-> ego-compensated bearing + LOS-rate (S2)
    IMMFilter.update             -> filtered lambda-dot
    LoomingEstimator.update      -> tau / closing confidence (weak cue)
    BearingRateController.compute  -> lateral accel command (or PolicyReject)
    LosControlPilot             -> bounded AICommand (roll/pitch/yaw/throttle)

EGO MODEL (sim-matched): like the verified Mode B pixel loop, only the ROLL rate is fed to
the LOS ego-compensation, because the tracker_sim renders a velocity-aligned boresight where
pitch/yaw already move the target pixel (passing them would double-compensate). For a real
body-fixed camera the full body-rate ego model is finalized at S0/B1 calibration; that is the
one piece of this chain that is mounting-dependent and not yet hardware-validated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from vision.tracker.blob import TargetObservation
from vision.tracker.detect import ThresholdState, detect_frame
from vision.tracker.egomotion import gyro_derotation
from vision.tracker.geometry import CameraIntrinsics, ft640_intrinsics, bearing_to_pixel
from vision.tracker.imm import IMMConfig, IMMEstimate, IMMFilter
from vision.tracker.looming import LoomingEstimate, LoomingEstimator
from vision.tracker.los import LOSComputer
from vision.tracker.mti import MotionGate
from vision.tracker.track import ThermalLockConfig, ThermalLockTracker
from vision.tracker.track_manager import MultiTrackManager
from vision.tracker.aimpoint import migrate_aimpoint
from vision.tracker.event_channel import EventChannel
from vision.tracker.correlation import CorrelationChannel, extract_chip, warp_chip

from vision.control.bearing_rate import BearingRateController, ControlConfig, PolicyReject
from vision.control.command_map import LosControlPilot, PilotConfig


@dataclass(frozen=True)
class PipelineOutput:
    command: object | None        # AICommand when locked & not halted, else None
    locked: bool                  # a fresh ego-compensated LOS was produced this frame
    tracking_state: str
    policy_reject: bool
    reason: str
    imm: IMMEstimate | None = None
    # A4: operation-permission gate output.  The IMM's sustained model-wrong alarm DROPS this
    # to False (default-deny on doubt) without touching the LOS/tracker/command spine (Inv 2):
    # it is the live "model-wrong halt" signal the confirm-gate / operator consumes.
    activate_permitted: bool = True
    # --- observability (populated by step(); never read by control/control) ---
    blobs: tuple = ()                                  # all detected ThermalBlobs this frame
    centroid_px: tuple[float, float] | None = None     # tracked target centroid (px)
    bbox: tuple[int, int, int, int] | None = None      # tracked target bbox (x,y,w,h)
    area_px: float | None = None
    snr: float | None = None
    threshold_counts: float = 0.0                       # adaptive detection threshold


def _default_looming(area_px: float) -> LoomingEstimate:
    # Used before the looming estimator has enough history: no closing confidence.
    return LoomingEstimate(tau_s=float("inf"), tau_confidence=0.0, closing_sign=0,
                           area_smoothed_px=area_px, d_area_dt_px_per_s=0.0)


class TrackerControlPipeline:
    def __init__(self, *, intrinsics: CameraIntrinsics | None = None,
                 acquisition_box: tuple[float, float, float, float] | None = None,
                 control_config: ControlConfig | None = None,
                 pilot_config: PilotConfig | None = None,
                 min_snr: float = 2.0, min_area_px: int = 2, max_blobs: int = 20,
                 acquisition_basket_fraction: float = 0.5, region_bands: int = 0,
                 motion_gate: bool = False, graduated_k: bool = False, use_mpcm: bool = False,
                 directional_median: bool = False, trajectory_continuity: bool = False,
                 use_imm_coast: bool = False, use_peak_relative_deletion: bool = False,
                 use_tau_terminal: bool = False, regime_enabled: bool = False,
                 aimpoint_migration: bool = False, aimpoint_forward_bias_px: float = 0.0,
                 event_channel: bool = False, require_consensus_for_lock: bool = False,
                 correlation: bool = False, correlation_psr_ref: float = 12.0,
                 prewarp: bool = False, jpda_enabled: bool = False,
                 roi_gating: bool = False, roi_margin_px: float = 24.0,
                 heavy_stage_decimation: int = 1,
                 discriminator=None,
                 use_terminal_hold: bool = False, terminal_hold_subtense_px: float = 240.0) -> None:
        # Detection gates -- live-tunable (the bench mutates these); defaults match detect_frame.
        self.min_snr = float(min_snr)
        self.min_area_px = int(min_area_px)
        self.max_blobs = int(max_blobs)
        self.region_bands = int(region_bands)   # >0 = look-down region-adaptive CFAR
        self.graduated_k = bool(graduated_k)    # region-classified k_horizon<k_sky<k_ground (B1)
        self.use_mpcm = bool(use_mpcm)          # MPCM local-contrast gate (B1)
        self.directional_median = bool(directional_median)  # directional max-median (B1)
        # Look-down MTI: gate detections by ego-compensated motion (drop static clutter).
        self._mti = MotionGate() if motion_gate else None
        # B3 trajectory-continuity backstop: only blobs belonging to a CONFIRMED (persistent +
        # CV-consistent) tracklet may seed a fresh lock, so a single-frame parallax flash that
        # slips past MTI can never acquire.  The manager observes every blob (so it still builds
        # confirmation); the gate only restricts what the single-target tracker is allowed to
        # acquire, and -- like MTI -- it never prunes the already-established lock.
        self._mtm = MultiTrackManager() if trajectory_continuity else None
        # R6 synthetic-event log-contrast channel: an AGC/background-invariant motion locator
        # (default-off). It runs every frame to keep its history and stores the latest event
        # centroid for R7's intensity^motion consensus; it does not (yet) feed the LOS spine.
        # R7 consensus needs an independent motion measurement, so it forces the event channel on.
        self._require_consensus = bool(require_consensus_for_lock)
        self._event = EventChannel() if (event_channel or self._require_consensus) else None
        self._last_event_centroid: tuple[float, float] | None = None
        # R8 MOSSE correlation channel: a structural-track confidence (PSR) that modulates the
        # lock-score (lifecycle) only -- never the live centroid/LOS (Inv 2). Default-off.
        self._corr = CorrelationChannel() if correlation else None
        self._corr_psr_ref = float(correlation_psr_ref)
        self._last_psr: float | None = None
        # R9 anticipatory pre-warp: scale the correlation chip by exp(-dt/tau) (range-free looming)
        # so a closing/grown target matches the template; confidence-gated, default-off.
        self._prewarp = bool(prewarp)
        self._last_looming: LoomingEstimate | None = None
        # WAVE-3: default to the FOXEER FT640 V2 wide lens (HFOV 48.7°, f_px ≈ 707 px,
        # ≈1.41 mrad/px) — the camera actually fielded and the one the DETECT-envelope
        # budget assumes.  The old default was the narrow Boson 640 24 mm (f_px ≈ 2130);
        # the hardware bench (observer.py / onboard_openloop.py) already passes FT640.
        self.intrinsics = intrinsics or ft640_intrinsics()
        self._threshold = ThresholdState()
        self._base_gate_px = 60.0
        # WAVE 2: ROI-gated perception (default-OFF -> roi=None -> bit-identical). When ON and an
        # established track exists, crop detect_frame to a box around the tracker's PREDICTED
        # centroid sized by the (covariance-widened) association gate + a margin, so the heavy
        # look-down stages only touch the on-target neighbourhood and fit the frame budget. In
        # ACQUIRE / reacquire-from-scratch (no established track) it falls back to the full frame.
        self._roi_gating = bool(roi_gating)
        self._roi_margin_px = float(roi_margin_px)
        # WAVE 2: temporal decimation of the heavy directional-median + MTI stages. 1 -> run every
        # frame (bit-identical). >1 -> run them only every Nth frame, reusing the last MTI mask
        # between, so the per-frame heavy budget amortizes over N frames.
        self._heavy_decimation = max(1, int(heavy_stage_decimation))
        self._last_mti_mask = None
        self._heavy_phase = 0
        # R1: consume the IMM hardening (default-off -> bit-identical). When on, the pipeline feeds
        # the IMM model-based coast state + lock-quality to the tracker after each IMM update.
        self._use_imm_coast = bool(use_imm_coast)
        self._use_peak_relative_deletion = bool(use_peak_relative_deletion)
        # R4: hysteretic regime state machine (default-OFF -> bit-identical to today).
        # R5 aimpoint migration needs the regime, so enabling it forces the regime machine on.
        self._aimpoint_migration = bool(aimpoint_migration)
        self._aimpoint_forward_bias_px = float(aimpoint_forward_bias_px)
        self._regime_enabled = bool(regime_enabled) or self._aimpoint_migration
        self._tracker = ThermalLockTracker(ThermalLockConfig(
            stable_frame_count=3, max_gate_px=self._base_gate_px,
            predictive_track_frames=18, reacquire_frames=90,
            use_imm_coast=self._use_imm_coast,
            use_peak_relative_deletion=self._use_peak_relative_deletion,
            regime_enabled=self._regime_enabled,
            require_consensus_for_lock=self._require_consensus,
            jpda_enabled=bool(jpda_enabled),
        ))
        # Handover basket: only targets near boresight can lock (A1).  A full-frame box
        # is the documented acquisition bug -- it lets the tracker lock the most-salient
        # clutter anywhere in a cluttered look-down scene.  Default to a centred basket;
        # an explicit acquisition_box (or designate()) overrides it with the operator aim.
        self._basket_fraction = float(acquisition_basket_fraction)
        if not (math.isfinite(self._basket_fraction) and 0.0 < self._basket_fraction <= 1.0):
            raise ValueError("acquisition_basket_fraction must be finite and in (0, 1]")
        box = acquisition_box if acquisition_box is not None else self._centered_basket(self._basket_fraction)
        self._tracker.seed(acquisition_box=box)
        self._los = LOSComputer(self.intrinsics)
        self._imm = IMMFilter(IMMConfig(
            sigma_meas_az=2e-3, sigma_meas_el=2e-3, sigma_meas_az_rate=0.02, sigma_meas_el_rate=0.02,
            q_cv_rate=0.01, q_maneuver_rate=0.8, ego_gate_radps=0.1,
        ))
        self._looming = LoomingEstimator()
        self._control = BearingRateController(control_config or ControlConfig())
        # R3: tau-driven terminal confirm (default-off). Only feed estimated_tau_s when on, so the
        # OFF path passes tau=None exactly as before (bit-identical; the legacy terminal switch
        # never fired in the pipeline because neither range nor tau was passed).
        self._use_tau_terminal = bool(use_tau_terminal)
        self._pilot = LosControlPilot(
            config=pilot_config or PilotConfig(use_tau_terminal=self._use_tau_terminal))
        self._seq = 0
        self._last_imm: IMMEstimate | None = None
        # AI-firewall discriminator: optional callable(frame_u16, centroid_px)->bool that can only
        # WITHDRAW activate-permission (default-deny). Kept optional so torch stays out of the
        # classical tracker path; the learned object-vs-not CNN (vision.tracker.classify) plugs in here.
        self._discriminator = discriminator
        # Ten-tau wall (W4): freeze the control course once the target subtense (largest bbox dim)
        # crosses this many px -- a range-free "very close" proxy. Default-off -> bit-identical.
        self._use_terminal_hold = bool(use_terminal_hold)
        self._terminal_hold_subtense_px = float(terminal_hold_subtense_px)

    def _centered_basket(self, fraction: float) -> tuple[float, float, float, float]:
        """A fraction-of-frame acquisition box centred on the boresight."""
        w = float(self.intrinsics.width)
        h = float(self.intrinsics.height)
        bw, bh = w * fraction, h * fraction
        return ((w - bw) / 2.0, (h - bh) / 2.0, bw, bh)

    def _detect_roi(self) -> tuple[int, int, int, int] | None:
        """WAVE 2: derive the detect_frame ROI from the tracker's predicted state, or None.

        Returns ``None`` (=> full frame) unless ROI-gating is on AND the tracker holds an
        ESTABLISHED track (LOCKED / PREDICTIVE_TRACK / REACQUIRE).  In ACQUIRE / reacquire-from-
        scratch there is no reliable predicted position, so we must search the whole frame.

        The box is centred on the tracker's PREDICTED centroid (``active_centroid()`` -- the same
        coast prediction the association gate is centred on) with half-width = the current gate
        radius (``gate_px`` already absorbs the REACQUIRE expansion and the A4 covariance-sized
        ``set_search_radius`` floor) plus a fixed margin.  Clamped to the frame; detect_frame
        clamps again, so an off-frame box is harmless.
        """
        if not self._roi_gating:
            return None
        center = self._tracker.active_centroid()
        if center is None:
            return None                                   # no established track -> full frame
        cx, cy = center
        if not (math.isfinite(cx) and math.isfinite(cy)):
            return None
        half = float(self._tracker.gate_px) + self._roi_margin_px
        w = float(self.intrinsics.width)
        h = float(self.intrinsics.height)
        x0 = int(math.floor(max(0.0, cx - half)))
        y0 = int(math.floor(max(0.0, cy - half)))
        x1 = int(math.ceil(min(w, cx + half)))
        y1 = int(math.ceil(min(h, cy + half)))
        if x1 <= x0 or y1 <= y0:
            return None
        return (x0, y0, x1 - x0, y1 - y0)

    def designate(self, center_px: tuple[float, float], basket_px: float | None = None) -> None:
        """Operator designation: re-seed acquisition on a basket centred at ``center_px``.

        Resets the tracker to re-acquire the designated target only (the operator-cued
        LOBL aim).  ``basket_px`` defaults to 40% of the smaller image dimension.
        """
        w = float(self.intrinsics.width)
        h = float(self.intrinsics.height)
        bp = float(basket_px) if basket_px is not None else min(w, h) * 0.4
        if not (math.isfinite(bp) and bp > 0.0):
            raise ValueError("basket_px must be finite and > 0")
        bp = min(bp, min(w, h))                       # never larger than the frame (C9)
        cx, cy = float(center_px[0]), float(center_px[1])
        if not (math.isfinite(cx) and math.isfinite(cy)):
            raise ValueError("designation center must be finite")
        # clamp so the basket stays fully on-screen (a real aim box, not a full-frame default)
        x0 = min(max(cx - bp / 2.0, 0.0), w - bp)
        y0 = min(max(cy - bp / 2.0, 0.0), h - bp)
        self._tracker.seed(acquisition_box=(x0, y0, bp, bp))

    def step(self, now: float, frame_u16, gyro_omega_xyz: tuple[float, float, float], dt: float,
             *, cam_temp_c: float = 25.0, ffc_state: str = "READY",
             confirmed: bool = False) -> PipelineOutput:
        frame_id = self._seq
        t_ns = int(now * 1e9)
        dt_eff = max(dt, 1e-4)

        # WAVE 2: ROI gate -- crop detection to the predicted-target neighbourhood once an
        # established track exists (None -> full frame, bit-identical). All blob outputs come back
        # in ABSOLUTE px, so every downstream LOS/IMM/tracker computation is unchanged.
        roi = self._detect_roi()
        # WAVE 2: temporal decimation -- run the heavy directional-median stage only on heavy
        # frames; the OFF (decimation==1) path is every frame, exactly as before.
        heavy_this_frame = (self._heavy_phase % self._heavy_decimation) == 0
        self._heavy_phase += 1                          # advance once per frame (any exit path)
        directional_median = self.directional_median and heavy_this_frame

        # S1 detection
        blobs, self._threshold = detect_frame(
            frame_u16, cam_temp_c=cam_temp_c, ffc_state=ffc_state,
            threshold_state=self._threshold, frame_id=frame_id, t_capture_ns=t_ns,
            min_area_px=self.min_area_px, min_snr=self.min_snr, max_blobs=self.max_blobs,
            region_bands=self.region_bands, graduated_k=self.graduated_k,
            use_mpcm=self.use_mpcm, directional_median=directional_median,
            roi=roi,
        )
        # R6: synthetic-event channel -- run every frame to maintain history; store the AGC-
        # invariant motion centroid for R7's consensus. FFC frames reset it (stale shutter pixels).
        if self._event is not None:
            if ffc_state != "READY":
                self._event.reset()
                self._last_event_centroid = None
            else:
                ev_ego = gyro_derotation(omega_xyz_radps=(0.0, 0.0, float(gyro_omega_xyz[2])),
                                         dt=dt_eff, intrinsics=self.intrinsics)
                self._last_event_centroid = self._event.update(frame_u16, ev_ego.shift_px)
        # Look-down MTI gate -- motion as a SOFT preference that NEVER prunes the established
        # track.  FFC frames are not ingested (stale -> reset history).  A blob is a "mover"
        # if any pixel of its BBOX is in the ego-compensated motion mask (not a single
        # centroid pixel, which a flat-topped target leaves still).  When movers exist we drop
        # static NEW candidates but ALWAYS retain the currently-tracked blob; when nothing
        # moves we keep all blobs so a HOVERING target is not erased.
        if self._mti is not None:
            if ffc_state != "READY":
                self._mti.reset()
                self._last_mti_mask = None
                mask = None
            elif heavy_this_frame:
                # Heavy frame: recompute the ego-compensated motion mask and cache it.
                mask = self._mti.update(frame_u16)
                self._last_mti_mask = mask
            else:
                # WAVE 2 decimation: reuse the last computed mask between heavy frames. The
                # cached mask is in absolute frame px (full-frame MTI), so it still indexes
                # the blob bboxes correctly.
                mask = self._last_mti_mask
            if mask is not None and blobs:
                mh, mw = mask.shape

                def _is_mover(b: object) -> bool:
                    bx, by, bw, bh = b.bbox  # type: ignore[attr-defined]
                    x0, x1 = min(max(bx, 0), mw), min(max(bx + bw, 0), mw)
                    y0, y1 = min(max(by, 0), mh), min(max(by + bh, 0), mh)
                    return x1 > x0 and y1 > y0 and bool(mask[y0:y1, x0:x1].any())

                movers = [b for b in blobs if _is_mover(b)]
                if movers:
                    tracked = self._tracker.active_centroid()
                    if tracked is None:
                        blobs = movers                       # fresh acquisition: prefer movers
                    else:
                        tcx, tcy = tracked
                        gate = self._tracker.gate_px
                        blobs = [b for b in blobs if _is_mover(b) or (
                            math.isfinite(b.centroid_px[0]) and math.isfinite(b.centroid_px[1])
                            and math.hypot(b.centroid_px[0] - tcx, b.centroid_px[1] - tcy) <= gate)]

        # B3 trajectory-continuity backstop -- the parallax/false-alarm gate.  The manager
        # observes EVERY post-MTI blob (so a real mover still accrues confirmation), but only
        # blobs near a CONFIRMED tracklet -- or the already-tracked target -- are allowed to
        # reach the single-target tracker.  A one-frame flash never reaches N-of-M, so it can
        # never seed a lock; acquisition of a genuine target is delayed only by the few frames
        # it takes to confirm.  FFC frames reset the manager (stale pixels).
        if self._mtm is not None:
            if ffc_state != "READY":
                self._mtm.reset()
            else:
                snaps = self._mtm.update(blobs, frame_id)
                confirmed = [s.centroid_px for s in snaps if s.confirmed]
                tracked = self._tracker.active_centroid()
                mgate = self._mtm.gate_px

                def _continuous(b: object) -> bool:
                    bx, by = b.centroid_px  # type: ignore[attr-defined]
                    if not (math.isfinite(bx) and math.isfinite(by)):
                        return False
                    if any(math.hypot(bx - cx, by - cy) <= mgate for cx, cy in confirmed):
                        return True
                    return tracked is not None and math.hypot(
                        bx - tracked[0], by - tracked[1]) <= self._tracker.gate_px

                blobs = [b for b in blobs if _continuous(b)]
        obs = TargetObservation(
            frame_id=frame_id, t_capture_ns=t_ns, cam_temp_c=cam_temp_c, ffc_state=ffc_state,
            blobs=blobs, threshold_baseline_counts=self._threshold.threshold_counts,
            detection_budget_ms=0.0,
        )
        # R7: feed the independent motion measurement so the tracker can require intensity^motion
        # consensus before LOCKED (no-op unless require_consensus_for_lock is set on the tracker).
        if self._require_consensus:
            self._tracker.set_motion_centroid(self._last_event_centroid)
        snap = self._tracker.update(obs)

        # R8: MOSSE structural confidence on the locked target. Seed the immutable LOBL reference on
        # first lock; thereafter feed the PSR-normalized confidence to the tracker lock-score for the
        # NEXT frame (like the IMM quality feed). The peak offset is for same-track re-detection only;
        # PSR is a lock-quality signal -- neither moves the live centroid/LOS (Inv 2).
        if self._corr is not None and ffc_state == "READY" and snap.associated_blob is not None:
            chip = extract_chip(frame_u16, snap.centroid_px[0], snap.centroid_px[1])
            if not self._corr.seeded:
                self._corr.seed(chip)
            else:
                # R9: pre-warp the chip to the predicted scale (exp(-dt/tau)) when looming is
                # confident, so a closing target matches the template; else use the chip as-is.
                if (self._prewarp and self._last_looming is not None
                        and self._last_looming.tau_confidence >= 0.5
                        and math.isfinite(self._last_looming.tau_s) and self._last_looming.tau_s > 0.0):
                    chip = warp_chip(chip, content_scale=math.exp(-dt_eff / self._last_looming.tau_s))
                _dx, _dy, psr = self._corr.measure(chip)
                self._last_psr = psr
                self._tracker.set_correlation_confidence(
                    min(psr / max(self._corr_psr_ref, 1e-6), 1.0))

        dbg = dict(blobs=tuple(blobs), threshold_counts=float(self._threshold.threshold_counts))

        # No detection this frame -> control coasts upstream; no fresh LOS.
        if snap.associated_blob is None:
            self._seq += 1
            return PipelineOutput(None, False, snap.tracking_state.name, False, "no_lock",
                                  self._last_imm, centroid_px=snap.centroid_px, **dbg)

        # S2 ego-compensated LOS (roll-only ego; see module docstring) + IMM filter
        ego = gyro_derotation(omega_xyz_radps=(0.0, 0.0, float(gyro_omega_xyz[2])),
                              dt=dt_eff, intrinsics=self.intrinsics)
        # R5: migrate the LOS-feeding aimpoint hotspot->silhouette in RESOLVED/FILL (DETERMINISTIC
        # geometry, never a quality signal -> Inv 2). OFF or POINT -> the unchanged hotspot centroid.
        los_centroid = snap.centroid_px
        if self._aimpoint_migration and snap.associated_blob is not None:
            los_centroid = migrate_aimpoint(
                frame_u16, snap.centroid_px, float(snap.associated_blob.peak_counts),
                self._tracker.velocity_px_per_frame, snap.regime,
                forward_bias_px=self._aimpoint_forward_bias_px)
        los_obs = self._los.update(centroid_px=los_centroid, ego=ego, dt=dt_eff,
                                   frame_id=frame_id, t_capture_ns=t_ns)
        imm_est = self._imm.update(
            los_obs, dt=dt_eff,
            pixel_extent_px=float(snap.associated_blob.area_extended_px or snap.associated_blob.area_px),
        )
        self._last_imm = imm_est

        # A4 covariance-sized search box: project the IMM's predicted bearing-innovation std to
        # pixels and hand it to the tracker as an EXPAND-ONLY gate floor for the next frame
        # (capped at 3x the fixed gate so a covariance blow-up can't open an unbounded window).
        f_px = float(self.intrinsics.f_px)
        gate_sigma = max(float(imm_est.gate_sigma_az_rad), float(imm_est.gate_sigma_el_rad))
        self._tracker.set_search_radius(min(3.0 * gate_sigma * f_px, 3.0 * self._base_gate_px))

        # A4 NIS consumer: a SUSTAINED true-NIS "model-wrong" alarm withdraws activate-permission
        # (default-deny) -- the real consumer of the alarm, feeding the confirm-gate, NOT the
        # centroid/LOS/tracker spine.  A single jink does not trip it (true NIS uses S).
        activate_permitted = not imm_est.model_wrong_alarm
        # AI-firewall: a learned discriminator (object-vs-not CNN) can only WITHDRAW activate-permission
        # (default-deny), never grant it against the kinematic gate, and never touch the
        # centroid/LOS/tracker (Inv 2). Runs only on a held lock; optional -> no torch in the OFF path.
        if self._discriminator is not None and activate_permitted and snap.centroid_px is not None:
            activate_permitted = bool(self._discriminator(frame_u16, snap.centroid_px))

        # R1: feed the IMM hardening into the tracker for the NEXT frame (used only when the
        # respective flag is on). set_imm_state is a KINEMATIC coast prediction (where the target
        # is); set_quality is an OUTPUT-only lifecycle signal -- neither moves the centroid (Inv 2).
        if self._use_imm_coast:
            ic = bearing_to_pixel(imm_est.az_rad, imm_est.el_rad, self.intrinsics)
            ic_next = bearing_to_pixel(imm_est.az_rad + imm_est.az_rate_radps * dt_eff,
                                       imm_est.el_rad + imm_est.el_rate_radps * dt_eff, self.intrinsics)
            self._tracker.set_imm_state(ic, (ic_next[0] - ic[0], ic_next[1] - ic[1]))
        if self._use_peak_relative_deletion:
            self._tracker.set_quality(imm_est.lock_quality, imm_est.model_ok)

        # Looming is driven by area_px (Phase-B review C3): area_extended_px is on a different
        # (180x180-window) scale than the LoomingConfig saturation thresholds, and its
        # look-down border-background artefact can both fabricate and suppress closing cues.
        # area_extended_px is kept as a separate diagnostic subtense cue, NOT a looming input,
        # until a window-scale-matched looming config + the local-background fix are validated.
        blob = snap.associated_blob
        looming_est = self._looming.update(float(blob.area_px), dt_eff)
        if looming_est is None:
            looming_est = _default_looming(float(blob.area_px))
        self._last_looming = looming_est               # R9: feed the next frame's pre-warp

        # S3 control law + pilot mapping
        self._seq += 1
        blob = snap.associated_blob
        track_dbg = dict(centroid_px=snap.centroid_px, bbox=blob.bbox,
                         area_px=float(blob.area_px), snr=float(blob.snr), **dbg)
        # Ten-tau wall trigger (range-free): the target's largest bbox dimension crossing the
        # threshold means it fills the FOV -> very close -> freeze the course (see bearing_rate).
        terminal_hold = (self._use_terminal_hold and blob.bbox is not None
                         and max(blob.bbox[2], blob.bbox[3]) >= self._terminal_hold_subtense_px)
        try:
            g_cmd = self._control.compute(imm_est, looming_est, confirmed=confirmed,
                                           terminal_hold=terminal_hold)
        except PolicyReject as halt:
            return PipelineOutput(None, True, snap.tracking_state.name, True, halt.reason,
                                  imm_est, activate_permitted=activate_permitted, **track_dbg)

        est_tau = (g_cmd.t_go_s if (self._use_tau_terminal and g_cmd.t_go_source == "looming"
                                    and math.isfinite(g_cmd.t_go_s)) else None)
        ai_cmd = self._pilot.command_from_control(
            g_cmd, az_rad=imm_est.az_rad, el_rad=imm_est.el_rad,
            sequence_id=frame_id, timestamp_ms=int(now * 1e3),
            estimated_tau_s=est_tau,
        )
        return PipelineOutput(ai_cmd, True, snap.tracking_state.name, False, "locked",
                              imm_est, activate_permitted=activate_permitted, **track_dbg)

```


## `vision/control/command_map.py`

```python
"""Map control acceleration commands to platform roll/pitch/yaw-rate/throttle.

PHYSICS (matching platform_sim.py conventions)
-------------------------------------------
Coordinate frame (body-frame → world-frame):
    x: right (East)
    y: forward (North)
    z: up

Platform actuation in world frame:
    roll_cmd  > 0 → right bank → lateral acceleration +x (a_x = g * tan(roll))
    pitch_cmd > 0 → nose forward → forward acceleration +y (a_y = g * tan(pitch))
    throttle  > 0.5 → climb; throttle = 0.5 → hover (a_z = 0); throttle < 0.5 → descend

Command mapping from control acceleration commands:
    a_cmd_az_mps2 > 0 → target right → command ROLL RIGHT (positive roll_cmd)
        roll_cmd = clamp(atan2(a_cmd_az, g) / theta_max, -1, +1)
    a_cmd_el_mps2 > 0 → target above → command THROTTLE UP
        throttle increases to climb toward the target.
    Forward speed maintained by pitch_cmd (forward_pitch_fraction).

NOTE: Elevation control (a_cmd_el) maps to throttle, NOT pitch.  Pitch is
used purely for forward speed.  This is consistent with platform dynamics where:
    - Lateral motion (x): controlled by roll
    - Vertical motion (z): controlled by throttle
    - Forward motion (y): controlled by pitch

Gravity feed-forward in throttle:
    At hover throttle 0.5, the platform holds altitude.  When tilted, the vertical
    thrust component decreases by cos(theta).  To maintain altitude during roll:
        throttle_needed = 0.5 / cos(roll_angle)

Terminal acro switch:
    At close range (<~15 m or <~0.4 s to impact) we amplify the roll command
    slightly to achieve faster angular response (simulating rate-mode agility).

LOS-rate hold (impact freeze):
    Near impact, freeze the last valid roll command.

SIGN / UNITS
-------------
    a_cmd_* in m/s^2.
    roll_cmd, pitch_cmd, yaw_rate_cmd in [-1, +1].
    throttle_cmd in [0, 1] with 0.5 = hover.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from vision.platform.betaflight_link.commands import AICommand, CommandLimits  # type: ignore[import]
from vision.platform.control.speed import SpeedMode, SpeedPolicy
from vision.control.bearing_rate import ControlCommand


_G: float = 9.81  # m/s^2


# ---------------------------------------------------------------------------
# Pilot configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PilotConfig:
    """Configuration for LosControlPilot.

    Attributes
    ----------
    theta_max_rad:
        Maximum tilt angle (radians).  Must match ControlConfig.theta_max_rad.
        Default: 40 deg = 0.698 rad.
    throttle_hover:
        Normalized throttle [0, 1] required to hold altitude (hover point).
        Default 0.5.
    forward_pitch_fraction:
        Pitch command [0, 1] to maintain forward speed (positive pitch = forward).
        Default 0.4 (moderate forward lean to maintain ~15 m/s closure speed).
    yaw_gain:
        Yaw rate command gain.  yaw_rate = yaw_gain * az_rad.
        Default 1.5 (maps ±0.1 rad bearing to ±0.15 yaw rate command).
    el_throttle_gain:
        Throttle gain for elevation control.  throttle_delta = el_throttle_gain * a_cmd_el / g.
        Default 0.2 (moderate vertical authority).
    acro_switch_range_m:
        Range threshold (m) below which the angle→acro switch activates.
        Default 15.0 m.
    acro_switch_tau_s:
        Time-to-impact threshold (s) below which acro switch activates.
        Default 0.4 s.
    los_rate_hold_range_m:
        Range below which the last valid LOS-rate command is frozen (impact freeze).
        Default 5.0 m.
    """
    theta_max_rad: float = math.radians(40.0)
    throttle_hover: float = 0.50
    forward_pitch_fraction: float = 0.40   # positive pitch = forward lean
    yaw_gain: float = 1.5
    el_throttle_gain: float = 0.20
    acro_switch_range_m: float = 15.0
    acro_switch_tau_s: float = 0.40
    los_rate_hold_range_m: float = 5.0
    # R3: drive the terminal/acro and LOS-hold switches off the passive, range-free time-to-contact
    # tau (looming) instead of range/fixed-timer.  Default-OFF -> bit-identical, and when ON it
    # REMOVES range from the terminal path entirely (strengthens Inv 1).
    use_tau_terminal: bool = False
    los_rate_hold_tau_s: float = 0.15      # tau below which LOS-rate hold freezes the command

    def __post_init__(self) -> None:
        if not 0.0 < self.theta_max_rad < math.pi / 2:
            raise ValueError("theta_max_rad must be in (0, pi/2)")
        if not 0.0 <= self.throttle_hover <= 1.0:
            raise ValueError("throttle_hover must be in [0, 1]")


# ---------------------------------------------------------------------------
# LOS Control Pilot
# ---------------------------------------------------------------------------

class LosControlPilot:
    """Map a ControlCommand to a bounded AICommand for the Betaflight link.

    Adapts GateVisualPilot (gate-center visual servo) to bearing-rate-null
    control.

    Command mapping (see module docstring for full physics):
        roll_cmd   ← a_cmd_az (lateral)
        pitch_cmd  ← forward_pitch_fraction (constant; elevation is throttle)
        throttle   ← hover + elevation control (a_cmd_el)
        yaw_rate   ← az_rad (bearing yaw hold)

    Thread safety
    -------------
    LosControlPilot has mutable state (last-valid LOS-rate freeze).
    Call from a single control thread.
    """

    def __init__(
        self,
        *,
        config: PilotConfig | None = None,
        speed_policy: SpeedPolicy | None = None,
    ) -> None:
        self._cfg = config or PilotConfig()
        self._speed_policy = speed_policy or SpeedPolicy.default()
        # LOS-rate hold state (impact freeze)
        self._frozen_roll: float = 0.0
        self._frozen_throttle: float = 0.5
        self._los_frozen: bool = False

    def command_from_control(
        self,
        control_cmd: ControlCommand,
        az_rad: float,
        el_rad: float,
        sequence_id: int,
        timestamp_ms: int,
        *,
        estimated_range_m: float | None = None,
        estimated_tau_s: float | None = None,
        speed_mode: SpeedMode = SpeedMode.ADAPTIVE_SPEED,
        target_confidence: float = 1.0,
        tracking_state: str = "LOCKED",
    ) -> AICommand:
        """Convert a control acceleration command to a bounded AICommand.

        Parameters
        ----------
        control_cmd:
            Lateral acceleration command from BearingRateController.
        az_rad:
            Current filtered azimuth bearing (rad).  Used for yaw rate command.
        el_rad:
            Current filtered elevation bearing (rad).  Used for throttle adjustment.
        sequence_id:
            Monotonically increasing sequence counter for the MSP frame.
        timestamp_ms:
            CLOCK_MONOTONIC timestamp in milliseconds.
        estimated_range_m:
            Estimated range to target (m).  Used for acro/LOS-rate-hold switches.
        estimated_tau_s:
            Estimated time-to-impact (s).  Used for acro switch.
        speed_mode, target_confidence, tracking_state:
            Passed to SpeedPolicy for resolved_speed output.

        Returns
        -------
        AICommand
            Bounded roll/pitch/yaw_rate/throttle commands.
        """
        cfg = self._cfg

        # ── Determine operating mode ──────────────────────────────────────────
        in_terminal_phase = _is_terminal_phase(
            estimated_range_m, estimated_tau_s,
            cfg.acro_switch_range_m, cfg.acro_switch_tau_s,
            use_tau=cfg.use_tau_terminal,
        )
        in_los_hold_phase = _is_los_hold_phase(
            estimated_range_m, cfg.los_rate_hold_range_m,
            tau_s=estimated_tau_s, tau_threshold_s=cfg.los_rate_hold_tau_s,
            use_tau=cfg.use_tau_terminal,
        )

        # ── Compute roll command from lateral (az) control ───────────────────
        # a_cmd_az > 0 → right → positive roll
        roll_natural = _accel_to_normalized_angle(
            control_cmd.a_cmd_az_mps2, cfg.theta_max_rad, _G
        )

        # ── Throttle: hover + elevation control + gravity feed-forward ────────
        # When the platform is tilted by (roll, pitch), the vertical thrust component
        # is: T_z = T * cos(roll) * cos(pitch).
        # To maintain altitude: T = T_hover / (cos(roll) * cos(pitch)).
        # throttle_cmd = throttle_hover / (cos(roll) * cos(pitch)).
        roll_angle   = roll_natural * cfg.theta_max_rad
        pitch_angle  = cfg.forward_pitch_fraction * cfg.theta_max_rad
        cos_combined = math.cos(roll_angle) * math.cos(pitch_angle)
        if cos_combined < 0.1:
            cos_combined = 0.1
        throttle_natural = cfg.throttle_hover / cos_combined

        # Add elevation control: a_cmd_el maps to throttle delta
        # a_cmd_el in m/s^2; divide by g to normalize to throttle units
        throttle_el_adj = cfg.el_throttle_gain * control_cmd.a_cmd_el_mps2 / _G
        throttle_natural = _clamp(throttle_natural + throttle_el_adj, 0.0, 1.0)

        # ── LOS-rate hold (impact freeze) ─────────────────────────────────────
        if in_los_hold_phase:
            self._los_frozen = True
        elif not self._los_frozen:
            self._frozen_roll = roll_natural
            self._frozen_throttle = throttle_natural

        if self._los_frozen:
            roll_cmd = self._frozen_roll
            throttle_cmd = self._frozen_throttle
        else:
            roll_cmd = roll_natural
            throttle_cmd = throttle_natural

        # ── Terminal acro phase ───────────────────────────────────────────────
        # Amplify slightly to simulate faster rate-mode angular response.
        if in_terminal_phase:
            roll_cmd = _clamp(roll_cmd * 1.3, -1.0, 1.0)

        # ── Pitch: constant forward lean (speed maintenance) ──────────────────
        # Positive pitch_cmd = nose forward = forward acceleration in platform_sim.
        pitch_cmd = cfg.forward_pitch_fraction

        # ── Yaw rate: point boresight toward target az ────────────────────────
        yaw_rate_cmd = _clamp(cfg.yaw_gain * az_rad, -1.0, 1.0)

        # ── Speed policy (A3: coupled to the lateral-g budget) ────────────────
        # Pass the control demand vs envelope so the policy holds a lateral-g reserve --
        # slowing closure when the bearing-rate-null demand approaches the achievable g.
        resolved_speed = self._speed_policy.resolve_speed_mps(
            speed_mode,
            target_confidence=target_confidence,
            tracking_state=tracking_state,
            required_g=control_cmd.required_g,
            achievable_g=control_cmd.achievable_g,
        )

        return AICommand.bounded(
            roll_cmd=roll_cmd,
            pitch_cmd=pitch_cmd,
            yaw_rate_cmd=yaw_rate_cmd,
            throttle_cmd=throttle_cmd,
            target_confidence=target_confidence,
            target_state=tracking_state,
            recovery_state="NOMINAL",
            speed_mode=speed_mode,
            resolved_speed_mps=resolved_speed,
            sequence_id=sequence_id,
            timestamp_ms=timestamp_ms,
        )

    def reset(self) -> None:
        """Reset the LOS-rate freeze state."""
        self._frozen_roll = 0.0
        self._frozen_throttle = 0.5
        self._los_frozen = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _accel_to_normalized_angle(a_mps2: float, theta_max_rad: float, g: float) -> float:
    """Convert lateral acceleration command to normalized tilt angle.

    theta_cmd = atan2(a_cmd, g)
    normalized = theta_cmd / theta_max  (clamped to [-1, +1])
    """
    theta = math.atan2(a_mps2, g)
    normalized = theta / theta_max_rad
    return _clamp(normalized, -1.0, 1.0)


def _is_terminal_phase(
    range_m: float | None,
    tau_s: float | None,
    range_threshold_m: float,
    tau_threshold_s: float,
    use_tau: bool = False,
) -> bool:
    """True if the operation is in the terminal (acro) phase.

    With ``use_tau`` (R3) the decision is tau-driven ONLY -- range is removed from the terminal
    path entirely (Inv 1).  Otherwise the legacy range-OR-tau behaviour is preserved exactly.
    """
    if use_tau:
        return tau_s is not None and 0.0 < tau_s < tau_threshold_s
    if range_m is not None and range_m < range_threshold_m:
        return True
    if tau_s is not None and 0.0 < tau_s < tau_threshold_s:
        return True
    return False


def _is_los_hold_phase(
    range_m: float | None,
    threshold_m: float,
    tau_s: float | None = None,
    tau_threshold_s: float = 0.0,
    use_tau: bool = False,
) -> bool:
    """True if in the LOS-rate-hold (impact-freeze) phase.

    With ``use_tau`` (R3) the trigger is a tau threshold (range-free); otherwise legacy range.
    """
    if use_tau:
        return tau_s is not None and 0.0 < tau_s < tau_threshold_s
    if range_m is not None and range_m < threshold_m:
        return True
    return False


def _clamp(v: float, lo: float, hi: float) -> float:
    return min(max(v, lo), hi)

```


## `vision/control/operation_regime.py`

```python
"""Operation-regime kinematics for the high-speed rendezvous (Block-3 tracker design driver).

BRIEFING (2026-07-03): the object closes at 200-300 km/h (55.6-83.3 m/s); our vehicle flies
100-150 m/s. The tracker must hold the track, predict the object trajectory, and hit on lead. These
speeds are 5-10x the values the closed-loop sim was tuned for (Vc ~15-23 m/s), so several things
change qualitatively. This module computes the load-bearing numbers so the design is sized to the
REAL regime and the consequences are pinned as tests, not prose.

CONVENTION
----------
``aspect_deg`` is the angle between the object's velocity vector and the line of sight FROM the
object TO the vehicle:
    0   deg -> object flying straight AT the vehicle (pure head-on / collision)
    90  deg -> object crossing broadside (all velocity tangential to the LOS)
    180 deg -> object fleeing (tail chase)

The object velocity splits into a component along the LOS (adds/subtracts closing speed) and a
component across it (drives the LOS rate the tracker must track and the vehicle must null).

WHAT BREAKS AT THESE SPEEDS (all quantified below)
--------------------------------------------------
1. Broadside crossing is geometrically UNACHIEVABLE: the PN lateral demand N*Vc*lambda_dot blows
   past the ~0.84 g airframe wall by more than an order of magnitude.
2. Terminal maneuver authority collapses: at 150 m/s and 0.84 g the turn radius is ~2.7 km, vastly
   larger than the 50-200 m thermal operation range -> the vehicle is nearly ballistic in the
   terminal, so the LEAD must be pre-established (ground cue + midcourse), and terminal PN only
   trims a small residual lambda_dot.
3. Track-holding gets hard: the target sweeps ~10-20 px/frame at 60 Hz on a crossing -> the ROI
   must be placed on the PREDICTED position, not the last one.
4. Latency dominates the miss: at Vc~230 m/s every millisecond of loop latency is ~0.23 m of blind
   closure and the crosser slips ~0.08 m laterally -> the FPGA's deterministic sub-frame latency is
   worth metres of miss distance vs the ~35 ms Pi loop.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

G = 9.80665  # m/s^2

# FT640 wide lens: f_px = (640/2)/tan(48.7 deg/2) ~= 707 px (see vision/tracker/geometry.py).
FT640_F_PX = 707.0


@dataclass(frozen=True)
class RendezvousGeometry:
    """One operation geometry.  All speeds m/s, range m, angle deg."""

    vehicle_speed_mps: float
    target_speed_mps: float
    range_m: float
    aspect_deg: float
    N: float = 3.0
    f_px: float = FT640_F_PX
    frame_rate_hz: float = 60.0
    body_g_limit: float = 0.84   # sustained lateral-accel wall of the airframe (a_lat = g*tan(40deg))


@dataclass(frozen=True)
class RegimeResult:
    closing_speed_mps: float      # Vc = range closure rate
    target_perp_mps: float        # object velocity component across the LOS
    los_rate_radps: float         # lambda_dot the tracker sees at acquisition (target contribution)
    pixel_rate_px_s: float        # lambda_dot mapped through the lens
    px_per_frame: float           # per-frame target motion at the frame rate
    required_lateral_g: float     # PN demand N*Vc*lambda_dot to null the LOS rate, in g
    feasible: bool                # required_lateral_g <= body_g_limit
    time_to_go_s: float           # R / Vc (closing operations only; inf if opening)
    turn_radius_m: float          # Vi^2 / (body_g_limit*g): how tight the vehicle can turn

    def blind_closure_m(self, latency_s: float) -> float:
        """Range the target closes during one loop-latency period (the 'blind' closure)."""
        return self.closing_speed_mps * latency_s

    def lateral_slip_m(self, latency_s: float) -> float:
        """How far a crossing target slips across the LOS during one loop-latency period.

        This is the direct miss contribution of loop latency against a crosser -- the argument for
        deterministic sub-frame latency (FPGA) over the ~35 ms Pi loop.
        """
        return self.target_perp_mps * latency_s

    def min_roi_halfwidth_px(self, margin_frames: float = 2.0, blob_radius_px: float = 4.0) -> float:
        """Half-width of a tracking ROI that will still contain the target next frame.

        Must cover the per-frame motion (times a margin for prediction error) plus the blob extent.
        With a PREDICTED ROI centre the required size shrinks; this is the reactive (last-position)
        bound, which is why prediction is needed at these speeds.
        """
        return self.px_per_frame * margin_frames + blob_radius_px


def analyze(geo: RendezvousGeometry) -> RegimeResult:
    """Compute the operation-regime kinematics for one geometry."""
    a = math.radians(geo.aspect_deg)
    vt = geo.target_speed_mps
    vi = geo.vehicle_speed_mps

    # object velocity split relative to the LOS.
    vt_radial = vt * math.cos(a)     # + = object approaching along the LOS
    vt_perp = abs(vt * math.sin(a))  # across the LOS

    # Closing speed: vehicle flies along the LOS toward the object, plus the object's radial part.
    closing = vi + vt_radial

    # LOS rate the tracker sees at acquisition (target's tangential motion at this range).
    los_rate = vt_perp / geo.range_m if geo.range_m > 0 else float("inf")
    pixel_rate = los_rate * geo.f_px
    px_per_frame = pixel_rate / geo.frame_rate_hz

    # PN lateral demand to null that LOS rate: a_cmd = N * Vc * lambda_dot.  Feasibility is against
    # the airframe's sustained-g wall.  (Use the magnitude of closing; on an opening geometry PN is
    # not the right frame, but the demand magnitude is still the correction the airframe would need.)
    required_g = geo.N * abs(closing) * los_rate / G

    time_to_go = geo.range_m / closing if closing > 0 else float("inf")
    turn_radius = vi * vi / (geo.body_g_limit * G)

    return RegimeResult(
        closing_speed_mps=closing,
        target_perp_mps=vt_perp,
        los_rate_radps=los_rate,
        pixel_rate_px_s=pixel_rate,
        px_per_frame=px_per_frame,
        required_lateral_g=required_g,
        feasible=required_g <= geo.body_g_limit,
        time_to_go_s=time_to_go,
        turn_radius_m=turn_radius,
    )


def max_feasible_aspect_deg(geo: RendezvousGeometry, *, resolution_deg: float = 0.05) -> float:
    """Largest off-head-on aspect that is still within the airframe g-wall at this range/speed.

    Scans aspect from 0 upward and returns the last angle whose PN demand stays under the wall.
    This is the 'lead cone' the vehicle must be positioned inside BEFORE terminal -- the tracker
    cannot correct a wider crossing angle in the last tens of metres.
    """
    last_ok = 0.0
    a = 0.0
    while a <= 90.0:
        g = RendezvousGeometry(
            vehicle_speed_mps=geo.vehicle_speed_mps, target_speed_mps=geo.target_speed_mps,
            range_m=geo.range_m, aspect_deg=a, N=geo.N, f_px=geo.f_px,
            frame_rate_hz=geo.frame_rate_hz, body_g_limit=geo.body_g_limit)
        if analyze(g).feasible:
            last_ok = a
        else:
            break
        a += resolution_deg
    return last_ok


# ── representative envelope (also the __main__ table) ─────────────────────────
def _representative_table() -> str:
    lines = ["Block-3 high-speed operation regime  (Vi=150, Vt=83 m/s unless noted, N=3, FT640)"]
    lines.append(f"  turn radius @150 m/s, 0.84 g = "
                 f"{analyze(RendezvousGeometry(150, 83, 100, 0)).turn_radius_m:.0f} m "
                 f"(>> 50-200 m operation range -> terminal is near-ballistic)")
    lines.append(f"  {'geometry':>18} {'R m':>5} {'Vc m/s':>7} {'lam_dot':>8} {'px/fr':>6} "
                 f"{'req_g':>7} {'t_go s':>7} {'feas':>5}")
    rows = [
        ("head-on", 0, 200), ("head-on", 0, 50),
        ("10deg lead", 10, 200), ("10deg lead", 10, 100),
        ("quartering 30", 30, 150), ("broadside", 90, 100), ("broadside", 90, 50),
        ("tail-chase 180", 180, 150),
    ]
    for name, asp, R in rows:
        r = analyze(RendezvousGeometry(150, 83, R, asp))
        tgo = f"{r.time_to_go_s:6.3f}" if math.isfinite(r.time_to_go_s) else "  inf "
        lines.append(f"  {name:>18} {R:>5} {r.closing_speed_mps:>7.1f} {r.los_rate_radps:>8.3f} "
                     f"{r.px_per_frame:>6.1f} {r.required_lateral_g:>7.2f} {tgo:>7} "
                     f"{str(r.feasible):>5}")
    for R in (100, 200, 500):
        mfa = max_feasible_aspect_deg(RendezvousGeometry(150, 83, R, 0))
        lines.append(f"  max feasible lead aspect @ R={R:>3} m : {mfa:.2f} deg")
    return "\n".join(lines)


if __name__ == "__main__":
    print(_representative_table())

```


## `vision/control/closed_loop.py`

```python
"""Closed-loop rendezvous simulation harness for Block-03 S3.

OVERVIEW
--------
Two simulation modes:

Mode A (analytic, fast):
    Bearing is computed analytically from the true 3-D relative geometry plus
    ego-rotation noise and measurement noise.  Fast enough for Monte-Carlo sweeps.
    The full LOS pipeline (detect → los → imm) is bypassed; IMM is run on the
    analytic bearing.

Mode B (pixel-in-the-loop, integration validation):
    A synthetic thermal frame is rendered using vision.tracker.thermal_sim + tracker_sim.
    The full S1+S2 pipeline (detect → los_computer → imm) is run on each frame.
    Slow (~0.5 s/frame); use for integration validation only, not Monte-Carlo.

DECOUPLED COMMAND-RATE MODEL
-----------------------------
Control ticks at control_rate_hz (default 250 Hz), independent of vision.
Vision runs at vision_rate_hz (default 60 Hz).
On frames where no new vision data is available (frame drops or low-rate vision),
control holds the last-valid LOS (with configurable decay) and continues
generating commands at the control rate.  The command stream is metronomic.

SMITH-PREDICTOR-STYLE LEAD
----------------------------
The bearing measurement is delayed by d_total = sensor_delay + loop_delay.
The Smith predictor compensates by advancing the bearing estimate forward by
d_total using the current LOS-rate estimate:

    az_lead = az_delayed + az_rate * d_total
    el_lead = el_delayed + el_rate * d_total

This effectively pre-corrects for the delay.  The improvement (miss WITH lead
vs WITHOUT lead) is quantified in Gate L.

MISS DISTANCE
-------------
Miss distance = minimum 3-D separation (closest approach) during the operation.
Computed by finding the minimum over the continuous relative trajectory using
linear interpolation between consecutive sim steps.  For each pair of consecutive
positions, the closest approach on the line segment is found analytically:

    p(t) = p0 + t*(p1-p0),  q(t) = q0 + t*(q1-q0),  t in [0,1]
    d(t)^2 = |p(t)-q(t)|^2, minimized at t* = -dot(d0, dd) / dot(dd, dd)
    where d0 = p0-q0, dd = (p1-p0)-(q1-q0)

This avoids the discrete-step artifact where miss = capture_radius - one_step_width.
HIT if miss_distance < capture_radius_m.

UNITS / SIGNS
-------------
All in SI: meters, m/s, m/s^2, radians, rad/s, seconds.
Signs match bearing_rate.py and platform_sim.py conventions.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np
import numpy.typing as npt

from vision.tracker.imm import IMMFilter, IMMConfig, IMMEstimate
from vision.tracker.looming import LoomingEstimator, LoomingEstimate
from vision.tracker.los import LOSComputer, LOSObservation
from vision.tracker.geometry import CameraIntrinsics, ft640_intrinsics
from vision.tracker.egomotion import EgoEstimate
from vision.control.pixel_loop import PixelLoopState, make_pixel_loop_state, run_pixel_vision_tick


def _passthrough_imm_estimate(
    az_rad: float,
    el_rad: float,
    az_rate_radps: float,
    el_rate_radps: float,
    frame_id: int,
    t_s: float,
) -> IMMEstimate:
    """Build a pass-through IMMEstimate without running the outer IMMFilter.

    Used in Mode B (pixel-in-the-loop) to bypass the outer IMM re-filter.
    The IMM has already been applied inside run_pixel_vision_tick (pixel_loop.py).
    Running the outer IMM a second time would double-smooth the detection noise
    and produce artificially tight CPA numbers — the double-IMM bug.

    In Mode B, the bearing/rate values here are already IMMFilter output from
    the inner pixel-loop IMMFilter.  We wrap them in an IMMEstimate directly
    so the control law (BearingRateController) sees them without further smoothing.
    """
    return IMMEstimate(
        az_rad=az_rad,
        el_rad=el_rad,
        az_rate_radps=az_rate_radps,
        el_rate_radps=el_rate_radps,
        mode_probs=(0.5, 0.5),
        maneuver_detected=False,
        frame_id=frame_id,
        innovation_az=0.0,
        innovation_el=0.0,
        ego_gate_active=False,
    )

from vision.control.bearing_rate import (
    BearingRateController,
    ControlConfig,
    ControlCommand,
    GeometryClass,
    PolicyReject,
    schedule_Vc_mps,
)
from vision.control.command_map import LosControlPilot, PilotConfig
from vision.control.platform_sim import (
    PlatformSim,
    PlatformState,
    TargetSim,
    TargetState,
    SimConfig,
    OperationGeometry,
    compute_bearing_from_states,
    compute_los_rates,
)


_G: float = 9.81

# WAVE-3 camera-model reconciliation.
# The closed-loop sim now uses the FOXEER FT640 V2 wide thermal lens — the camera
# actually fielded on the Block-3 vehicle and the one the Johnson DETECT-envelope
# budget is computed against.  Previously the looming/area approximation hard-coded the
# NARROW Boson 640 24 mm telephoto (f_px = 2130, 0.47 mrad/px), which did not match the
# wide pixel-loop optics nor the budget.  FT640: HFOV 48.7°, f_px ≈ 707 px, ≈1.41 mrad/px.
# This f_px scales the blob-radius/area used ONLY by the looming (τ) channel; it is ~3.0×
# smaller than the old 2130, so a target subtends ~3.0× fewer pixels at a given range.
_FT640_F_PX: float = float(ft640_intrinsics().f_px)   # ≈ 707.08 px (640 px / 2 / tan(48.7°/2))


# ---------------------------------------------------------------------------
# Closest-approach utility
# ---------------------------------------------------------------------------

def _segment_closest_approach(
    p0: npt.NDArray[np.float64],
    p1: npt.NDArray[np.float64],
    q0: npt.NDArray[np.float64],
    q1: npt.NDArray[np.float64],
) -> float:
    """Minimum 3-D separation between two moving objects over one time step.

    Models both objects as moving linearly from their previous to current
    positions.  Finds the parametric time t* in [0,1] that minimises
    |p(t) - q(t)|^2, then returns the minimum distance.

    This eliminates the discrete-step artifact (miss ~ capture_radius - step)
    and gives a true continuous miss that varies with geometry and seed.

    Parameters
    ----------
    p0, p1:
        Vehicle position at start and end of time step (m).
    q0, q1:
        Target position at start and end of time step (m).

    Returns
    -------
    float
        Minimum 3-D separation (m) achieved at any point on the segment.
    """
    d0 = p0 - q0                  # relative position at t=0
    dd = (p1 - p0) - (q1 - q0)   # relative velocity * dt

    # d(t) = d0 + t*dd, |d(t)|^2 = |d0|^2 + 2*t*dot(d0,dd) + t^2*|dd|^2
    # Minimise: d/dt = 2*dot(d0,dd) + 2*t*|dd|^2 = 0 -> t* = -dot(d0,dd)/|dd|^2
    dd_sq = float(np.dot(dd, dd))
    if dd_sq < 1e-18:
        # Relative velocity is zero; return fixed distance
        return float(np.linalg.norm(d0))

    t_star = -float(np.dot(d0, dd)) / dd_sq
    t_clamped = max(0.0, min(1.0, t_star))

    d_min = d0 + t_clamped * dd
    return float(np.linalg.norm(d_min))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClosedLoopConfig:
    """Closed-loop harness configuration.

    Attributes
    ----------
    sim:
        Platform/target dynamics configuration.
    control:
        Control law configuration.
    pilot:
        Command-map pilot configuration.
    imm:
        IMM filter configuration.
    mode:
        'analytic' (Mode A) or 'pixel_in_the_loop' (Mode B).
    los_hold_decay:
        Decay factor applied to the held LOS-rate per control tick when no new
        vision frame is available.  1.0 = no decay (hold forever).  0.95 = 5%
        decay per tick.  Default 0.97.
    smith_predictor:
        Override for Smith-predictor lead.  If None, uses sim.smith_predictor.
    print_progress_every_n_steps:
        Print a progress line every N sim steps.  0 = no printing.
    """
    sim: SimConfig = field(default_factory=SimConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    pilot: PilotConfig = field(default_factory=PilotConfig)
    imm: IMMConfig = field(default_factory=IMMConfig)
    mode: str = "analytic"
    los_hold_decay: float = 0.97
    smith_predictor: Optional[bool] = None
    print_progress_every_n_steps: int = 0


# ---------------------------------------------------------------------------
# Operation result
# ---------------------------------------------------------------------------

@dataclass
class OperationResult:
    """Result of one closed-loop operation simulation.

    Attributes
    ----------
    hit:
        True if miss_distance_m < capture_radius_m.
    miss_distance_m:
        Minimum 3-D separation between vehicle and target (m).
    time_to_closest_approach_s:
        Simulation time of closest approach (s).
    policy_reject:
        True if a POLICY_REJECT was raised (envelope exceeded or high-crossing).
    policy_reject_reason:
        POLICY_REJECT reason string, or None if no halt.
    operation_time_s:
        Total operation time until hit/halt/timeout (s).
    config:
        The ClosedLoopConfig used.
    vehicle_trajectory:
        List of (t, x, y, z) vehicle positions.  May be empty if verbose=False.
    target_trajectory:
        List of (t, x, y, z) target positions.  May be empty if verbose=False.
    control_cmds:
        List of ControlCommand outputs (sampled at control rate).
    final_range_m:
        Slant range at end of simulation.
    n_frame_drops:
        Number of vision frame drops during the operation.
    n_policy_reject_attempts:
        Number of POLICY_REJECT exceptions raised (can exceed 1 if re-attempted).
    smith_predictor_used:
        Whether Smith-predictor lead was active.
    """
    hit: bool = False
    miss_distance_m: float = float("inf")
    time_to_closest_approach_s: float = 0.0
    policy_reject: bool = False
    policy_reject_reason: Optional[str] = None
    operation_time_s: float = 0.0
    config: Optional[ClosedLoopConfig] = None
    vehicle_trajectory: list[tuple[float, float, float, float]] = field(default_factory=list)
    target_trajectory: list[tuple[float, float, float, float]] = field(default_factory=list)
    control_cmds: list[ControlCommand] = field(default_factory=list)
    final_range_m: float = float("inf")
    n_frame_drops: int = 0
    n_policy_reject_attempts: int = 0
    smith_predictor_used: bool = False
    # Mode B extras
    mode: str = "analytic"
    n_off_fov_frames: int = 0
    lock_states_seen: set = field(default_factory=set)


# ---------------------------------------------------------------------------
# Delay buffer
# ---------------------------------------------------------------------------

class _DelayBuffer:
    """FIFO buffer that delays observations by a fixed time.

    Stores (timestamp, data) tuples and returns data that is at least
    delay_s seconds old.
    """

    def __init__(self, delay_s: float, jitter_s: float = 0.0, rng: Any = None) -> None:
        self._delay_s = delay_s
        self._jitter_s = float(jitter_s)          # A5: per-frame latency jitter half-width (s)
        self._rng = rng                           # dedicated RNG so jitter never perturbs plant noise
        self._buf: deque[tuple[float, Any]] = deque()

    def _effective_delay(self) -> float:
        """Nominal delay, plus a per-frame uniform jitter when A5 latency jitter is active."""
        if self._jitter_s > 0.0 and self._rng is not None:
            return max(0.0, self._delay_s + float(self._rng.uniform(-self._jitter_s, self._jitter_s)))
        return self._delay_s

    def push(self, t: float, data: Any) -> None:
        self._buf.append((t, data))

    def pop_delayed(self, current_t: float) -> Optional[Any]:
        """Return the most recent data that is at least the (jittered) delay old."""
        result = None
        eff = self._effective_delay()
        while self._buf and current_t - self._buf[0][0] >= eff:
            _, data = self._buf.popleft()
            result = data
        return result

    def peek_delayed(self, current_t: float) -> Optional[Any]:
        """Same as pop_delayed but does not remove from buffer."""
        result = None
        for t_stored, data in self._buf:
            if current_t - t_stored >= self._delay_s:
                result = data
            else:
                break
        return result


# ---------------------------------------------------------------------------
# Closed-loop engine
# ---------------------------------------------------------------------------

class ClosedLoop:
    """Closed-loop rendezvous simulation engine.

    Runs the control/command-map/dynamics loop for one operation.

    Usage
    -----
    ::
        cfg = ClosedLoopConfig(sim=SimConfig(target_geometry=OperationGeometry.HEAD_ON))
        loop = ClosedLoop(cfg)
        result = loop.run(verbose=False)
        print(f"Miss: {result.miss_distance_m:.3f} m  Hit: {result.hit}")
    """

    def __init__(self, config: ClosedLoopConfig) -> None:
        self._cfg = config

    def run(self, verbose: bool = False) -> OperationResult:
        """Run one complete operation simulation.

        Parameters
        ----------
        verbose:
            If True, store full trajectories in the result.

        Returns
        -------
        OperationResult
        """
        cfg = self._cfg
        sim_cfg = cfg.sim
        use_smith = cfg.smith_predictor if cfg.smith_predictor is not None else sim_cfg.smith_predictor

        rng = np.random.default_rng(sim_cfg.seed)

        use_pixel_mode = (cfg.mode == "pixel")

        # ── Mode B: construct per-operation pixel-loop state ─────────────────
        pixel_state: Optional[PixelLoopState] = None
        if use_pixel_mode:
            pixel_state = make_pixel_loop_state(sim_cfg.seed, imm_cfg=cfg.imm,
                                                gyro_scale_error=sim_cfg.gyro_scale_error)

        # ── Initialize dynamics ────────────────────────────────────────────────
        platform = PlatformSim(sim_cfg)
        target = TargetSim(sim_cfg)

        # ── Initialize control ────────────────────────────────────────────────
        control = BearingRateController(cfg.control)
        pilot = LosControlPilot(config=cfg.pilot)
        imm = IMMFilter(cfg.imm)
        looming = LoomingEstimator()

        # ── Delay buffer (sensor + loop delay; A5 per-frame jitter) ──────────
        total_delay_s = sim_cfg.total_delay_s()
        # Dedicated RNG (seed-derived) so latency jitter never perturbs the plant/noise sequence:
        # with latency_jitter_s=0 this RNG is created but never drawn -> bit-identical baseline.
        delay_rng = np.random.default_rng((int(sim_cfg.seed) ^ 0x0DE1A4) & 0xFFFFFFFF)
        delay_buf: _DelayBuffer = _DelayBuffer(
            total_delay_s, jitter_s=sim_cfg.latency_jitter_s, rng=delay_rng)

        # Wave-1 honest-noise stream: SEPARATE RNG so the correlated lambda-dot bias and area noise
        # never perturb the plant/white-noise sequence.  With the honest terms at 0 it is created but
        # never drawn -> bit-identical to the pre-Wave-1 baseline.
        meas_rng = np.random.default_rng((int(sim_cfg.seed) ^ 0x10510B1A) & 0xFFFFFFFF)
        bias_az_rate: float = 0.0      # AR-1 lambda-dot bias state (persists across vision frames)
        bias_el_rate: float = 0.0

        # ── Timing setup ─────────────────────────────────────────────────────
        dt_sim = sim_cfg.dt_sim_s
        dt_control = 1.0 / sim_cfg.control_rate_hz
        dt_vision = 1.0 / sim_cfg.vision_rate_hz
        bias_rho = math.exp(-dt_vision / max(sim_cfg.los_rate_bias_tau_s, 1e-6))   # AR-1 retention/frame

        control_tick_counter = 0
        vision_tick_counter = 0
        next_control_t = 0.0
        next_vision_t = 0.0

        # ── State tracking ────────────────────────────────────────────────────
        t = 0.0
        min_range = float("inf")
        t_min_range = 0.0
        policy_reject = False
        policy_reject_reason: Optional[str] = None
        n_frame_drops = 0
        n_policy_reject_attempts = 0

        # Previous positions for segment-based closest-approach computation.
        # The continuous-minimum approach finds the exact closest approach on
        # each time-step segment [p0,p1] vs [q0,q1], not just at grid points.
        prev_int_pos: Optional[npt.NDArray[np.float64]] = None
        prev_tgt_pos: Optional[npt.NDArray[np.float64]] = None

        # Last-valid control bearing (for hold with decay)
        last_az: float = 0.0
        last_el: float = 0.0
        last_az_rate: float = 0.0
        last_el_rate: float = 0.0
        last_tau_conf: float = 0.0
        last_area_px: float = 4.0
        last_valid_control_cmd: Optional[ControlCommand] = None

        # Command to apply to the platform
        current_roll_cmd: float = 0.0
        current_pitch_cmd: float = cfg.pilot.forward_pitch_fraction
        current_yaw_cmd: float = 0.0
        current_throttle_cmd: float = cfg.pilot.throttle_hover

        # Trajectory storage
        vehicle_traj: list[tuple[float, float, float, float]] = []
        target_traj: list[tuple[float, float, float, float]] = []
        control_cmds_log: list[ControlCommand] = []
        frame_id: int = 0

        # ── Main simulation loop ──────────────────────────────────────────────
        # Track whether we have passed the closest-approach point.
        # Once range starts increasing after having been below a threshold,
        # we terminate (true closest approach has been captured).
        past_closest_approach: bool = False
        n_increasing_steps: int = 0    # consecutive steps where range is increasing
        _N_INC_TERM = 5               # terminate after this many increasing steps post-min
        prev_range_m: float = float("inf")

        while t <= sim_cfg.max_sim_time_s:
            q_state = platform.state
            tgt_state = target.state

            # ── Continuous closest-approach (segment minimum) ────────────────
            # For each pair of consecutive positions (p0→p1) and (q0→q1), find
            # the exact closest point on the line segment, using analytic linear
            # interpolation.  This removes the discrete-step artifact where
            # miss = capture_radius - one_step_closing_distance.
            #
            # When the relative trajectory is monotonically approaching (t* > 1),
            # the segment minimum is at the endpoint (same as grid sampling).
            # The TRUE benefit: when the relative trajectory turns around WITHIN
            # the segment (t* in [0,1]), we capture the exact minimum.  This
            # happens near actual closest approach (when range first starts to
            # increase), giving an accurate continuous miss distance.
            curr_int_pos = q_state.pos.copy()
            curr_tgt_pos = tgt_state.pos.copy()

            if prev_int_pos is not None and prev_tgt_pos is not None:
                seg_min = _segment_closest_approach(
                    prev_int_pos, curr_int_pos,
                    prev_tgt_pos, curr_tgt_pos,
                )
                if seg_min < min_range:
                    min_range = seg_min
                    t_min_range = t
            else:
                # First tick: just use point distance
                range_m0 = float(np.linalg.norm(curr_tgt_pos - curr_int_pos))
                if range_m0 < min_range:
                    min_range = range_m0
                    t_min_range = t

            prev_int_pos = curr_int_pos
            prev_tgt_pos = curr_tgt_pos

            # Current range (for control and early-termination logic)
            rel = tgt_state.pos - q_state.pos
            range_m = float(np.linalg.norm(rel))

            # Detect post-closest-approach: once range has been below a loose
            # threshold (3x capture_radius) and is now consistently increasing,
            # terminate — we have captured the true closest approach.
            if range_m < sim_cfg.capture_radius_m * 3.0:
                past_closest_approach = True

            if past_closest_approach:
                if range_m > prev_range_m:
                    n_increasing_steps += 1
                else:
                    n_increasing_steps = 0
                if n_increasing_steps >= _N_INC_TERM:
                    if verbose:
                        vehicle_traj.append((t, *q_state.pos.tolist()))
                        target_traj.append((t, *tgt_state.pos.tolist()))
                    break

            prev_range_m = range_m

            # ── Vision frame tick (at vision_rate_hz) ─────────────────────────
            if t >= next_vision_t:
                next_vision_t += dt_vision
                frame_id += 1

                if use_pixel_mode:
                    # ── MODE B: full tracker pipeline ──────────────────────────
                    # geometry -> render -> detect -> ego -> los -> imm
                    # IMPORTANT: the analytic bearing is used ONLY to position
                    # the rendered blob pixel.  The bearing/rate that enters
                    # the delay buffer and ultimately drives control is the
                    # output of the real detect->los->imm pipeline.
                    assert pixel_state is not None
                    los_obs_b, imm_est_b, detected = run_pixel_vision_tick(
                        q_state=q_state,
                        tgt_state=tgt_state,
                        pixel_state=pixel_state,
                        frame_id=frame_id,
                        t_sim=t,
                        dt_vision=dt_vision,
                        range_m=range_m,
                    )

                    if detected and los_obs_b is not None and imm_est_b is not None:
                        # Use IMM estimate from the real pipeline as the
                        # "measurement" to delay. This is what drives control.
                        if (sim_cfg.looming_from_detected_area
                                and pixel_state.last_detected_area_px is not None):
                            # HONEST: looming/tau from the REAL detected blob area (what the sensor
                            # actually saw this frame), not a clean read of the true range.
                            area_px_b = float(pixel_state.last_detected_area_px)
                        else:
                            # Legacy (bit-identical): area approximated from true range.
                            # WAVE-3: FT640 f_px (≈707), not the old Boson 2130.  The blob
                            # subtends ~3.0× fewer pixels at the same range under the wide lens.
                            f_px = _FT640_F_PX
                            target_size_m = 0.15
                            target_r_px = f_px * target_size_m / max(range_m, 1.0)
                            area_px_b = math.pi * target_r_px ** 2

                        # Push real pipeline outputs to delay buffer.
                        # az/el come from IMM (ego-compensated + filtered).
                        # az_rate/el_rate come from IMM.
                        # There is NO analytic bearing on this path.
                        delay_buf.push(t, (
                            imm_est_b.az_rad,
                            imm_est_b.el_rad,
                            imm_est_b.az_rate_radps,
                            imm_est_b.el_rate_radps,
                            area_px_b,
                            frame_id,
                        ))
                    # If not detected: no push; control holds last-valid on next tick

                else:
                    # ── MODE A: analytic bearing (original) ───────────────────
                    # Compute TRUE bearing from 3-D geometry
                    az_true, el_true, _ = compute_bearing_from_states(
                        q_state.pos, q_state.vel, tgt_state.pos
                    )
                    az_rate_true, el_rate_true = compute_los_rates(
                        q_state.pos, q_state.vel, tgt_state.pos, tgt_state.vel
                    )

                    # Analytic blob area (approximate): sigma=1.5 px, range-scaled
                    # area_px ≈ pi * r^2 where r = f * theta_target / range
                    # WAVE-3: FT640 f_px (≈707), not the old Boson 2130.  For a ~0.3 m object:
                    # area ≈ pi * (707 * 0.15 / max(range_m, 1))^2 px — ~9× smaller area than
                    # the old narrow-lens approximation at the same range (f scales area as f^2).
                    f_px = _FT640_F_PX
                    target_size_m = 0.15
                    target_r_px = f_px * target_size_m / max(range_m, 1.0)
                    area_px = math.pi * target_r_px ** 2
                    # Wave-1 honest tau: the looming area is a NOISY/quantized pixel measurement, not a
                    # clean read of true range.  Default frac=0 -> area unchanged (bit-identical).
                    if sim_cfg.area_noise_frac > 0.0:
                        area_px = max(1.0, area_px * (1.0 + float(meas_rng.normal(0.0, sim_cfg.area_noise_frac))))
                        area_px = float(round(area_px))   # integer-pixel area for a few-px blob

                    # Measurement noise (white, per-frame independent)
                    noise_az = float(rng.normal(0.0, sim_cfg.bearing_noise_sigma_rad))
                    noise_el = float(rng.normal(0.0, sim_cfg.bearing_noise_sigma_rad))
                    noise_az_rate = float(rng.normal(0.0, sim_cfg.bearing_noise_sigma_rad * 3.0))
                    noise_el_rate = float(rng.normal(0.0, sim_cfg.bearing_noise_sigma_rad * 3.0))

                    # Wave-1 honest lambda-dot error: a CORRELATED AR-1 bias that does NOT average out
                    # in the IMM (ego / cam<->IMU-skew / centroid-drift residual).  Default sigma=0 ->
                    # no draw, no effect; meas_rng is a separate stream so the white sequence is intact.
                    if sim_cfg.los_rate_bias_sigma_radps > 0.0:
                        k = math.sqrt(max(1.0 - bias_rho * bias_rho, 0.0)) * sim_cfg.los_rate_bias_sigma_radps
                        bias_az_rate = bias_rho * bias_az_rate + k * float(meas_rng.normal())
                        bias_el_rate = bias_rho * bias_el_rate + k * float(meas_rng.normal())

                    az_meas = az_true + noise_az
                    el_meas = el_true + noise_el
                    az_rate_meas = az_rate_true + noise_az_rate + bias_az_rate
                    el_rate_meas = el_rate_true + noise_el_rate + bias_el_rate

                    # Push to delay buffer
                    delay_buf.push(t, (az_meas, el_meas, az_rate_meas, el_rate_meas,
                                       area_px, frame_id))

            # ── Control tick (at control_rate_hz) ────────────────────────────
            if t >= next_control_t:
                next_control_t += dt_control
                control_tick_counter += 1

                # Pop delayed bearing
                delayed_obs = delay_buf.pop_delayed(t)

                if delayed_obs is not None:
                    (az_d, el_d, az_rate_d, el_rate_d, area_d, fid_d) = delayed_obs

                    # Smith-predictor lead: advance BEARING by total_delay using the
                    # delayed rate as the prediction slope.
                    #
                    # SMITH IMPLEMENTATION (corrected):
                    #
                    # Prior attempt: recompute az_rate_guided from finite differences
                    # of consecutive advanced bearings.  This was WRONG: it amplified
                    # rate noise by (1/dt_vision) ≈ 60x per noise unit, causing spurious
                    # large commands that halted the operation.
                    #
                    # Correct approach: advance ONLY the bearing.  The rate fed to the
                    # IMM is the delayed rate (az_rate_d), which is the best available
                    # estimate of the current rate.  Under constant-rate assumption (the
                    # basis of the Smith prediction), the rate doesn't change over the
                    # delay period, so delayed rate == current rate.
                    #
                    # The (bearing, rate) pair is intentionally from slightly different
                    # time instants: bearing is predicted-present, rate is delayed.  The
                    # IMM handles this via its process noise model.  The improvement from
                    # advancing the bearing is in the DIRECTION of the command, not the
                    # magnitude.  This is the honest Smith predictor.
                    if use_smith:
                        az_guided = az_d + az_rate_d * total_delay_s
                        el_guided = el_d + el_rate_d * total_delay_s
                        # Rate: use delayed rate directly (NOT finite-differenced).
                        # Finite differencing amplifies noise; delayed rate is better.
                        az_rate_guided = az_rate_d
                        el_rate_guided = el_rate_d
                    else:
                        az_guided = az_d
                        el_guided = el_d
                        az_rate_guided = az_rate_d
                        el_rate_guided = el_rate_d

                    area_guided = area_d

                    last_az = az_guided
                    last_el = el_guided
                    last_az_rate = az_rate_guided
                    last_el_rate = el_rate_guided
                    last_area_px = area_guided
                else:
                    # Frame drop: hold last-valid with decay
                    n_frame_drops += 1
                    last_az_rate *= cfg.los_hold_decay
                    last_el_rate *= cfg.los_hold_decay
                    az_guided = last_az
                    el_guided = last_el
                    az_rate_guided = last_az_rate
                    el_rate_guided = last_el_rate
                    area_guided = last_area_px

                if use_pixel_mode:
                    # MODE B: bypass the outer IMM.
                    #
                    # The bearing/rate values (az_guided, el_guided, ...) are
                    # already the output of the IMMFilter inside run_pixel_vision_tick
                    # (pixel_loop.py step 9).  Running the outer IMM a second time
                    # here would double-smooth detection noise, making Mode B CPA
                    # look artificially tight — the double-IMM bug.
                    #
                    # Fix: wrap the values in a pass-through IMMEstimate without
                    # calling imm.update().  The outer IMM is Mode A only.
                    imm_est = _passthrough_imm_estimate(
                        az_rad=az_guided,
                        el_rad=el_guided,
                        az_rate_radps=az_rate_guided,
                        el_rate_radps=el_rate_guided,
                        frame_id=frame_id,
                        t_s=t,
                    )
                else:
                    # MODE A: build synthetic LOSObservation and run the outer IMM
                    los_obs = LOSObservation(
                        az_rad=az_guided,
                        el_rad=el_guided,
                        az_rate_radps=az_rate_guided,
                        el_rate_radps=el_rate_guided,
                        ego_quality=1.0,
                        ego_source="gyro",
                        frame_id=frame_id,
                        t_capture_ns=int(t * 1e9),
                    )
                    imm_est = imm.update(los_obs, dt_control)

                # Looming update
                looming_est = looming.update(area_guided, dt_control)
                last_tau_conf = looming_est.tau_confidence

                # Schedule Vc from vehicle airspeed
                own_speed = float(np.linalg.norm(q_state.vel))
                Vc = schedule_Vc_mps(
                    own_speed,
                    target_speed_assumed_mps=sim_cfg.target_speed_mps,
                    geometry=GeometryClass.HEAD_ON,
                )

                # Control law
                try:
                    g_cmd = control.compute(imm_est, looming_est, Vc_override_mps=Vc)
                    last_valid_control_cmd = g_cmd

                    # Map to platform commands
                    ai_cmd = pilot.command_from_control(
                        g_cmd,
                        az_rad=imm_est.az_rad,
                        el_rad=imm_est.el_rad,
                        sequence_id=control_tick_counter,
                        timestamp_ms=int(t * 1e3),
                        estimated_range_m=range_m,
                    )
                    current_roll_cmd = ai_cmd.roll_cmd
                    current_pitch_cmd = ai_cmd.pitch_cmd
                    current_yaw_cmd = ai_cmd.yaw_rate_cmd
                    current_throttle_cmd = ai_cmd.throttle_cmd

                    if verbose:
                        control_cmds_log.append(g_cmd)

                except PolicyReject as halt:
                    n_policy_reject_attempts += 1
                    if not policy_reject:
                        policy_reject = True
                        policy_reject_reason = halt.reason
                    # HONEST HALT RESPONSE: zero lateral commands.
                    #
                    # Previous behaviour (hold last-valid command) created a
                    # SPURIOUS near-miss: the last command had already turned the
                    # vehicle toward the target, so coasting on that command
                    # produced a 1.27m 'miss' even for a genuinely unreachable
                    # crossing target.  This is false confidence.
                    #
                    # Correct behaviour: on halt, zero the lateral roll/yaw
                    # commands.  Maintain forward pitch and hover throttle so the
                    # vehicle continues forward without lateral correction.
                    # This produces an HONEST large miss for unreachable cases.
                    #
                    # Physical justification: in a real system, an POLICY_REJECT
                    # triggers a safe-ditch / hold mode that cancels rendezvous
                    # control, not a frozen bank-angle that may still rendezvous.
                    current_roll_cmd = 0.0
                    current_pitch_cmd = cfg.pilot.forward_pitch_fraction
                    current_yaw_cmd = 0.0
                    current_throttle_cmd = cfg.pilot.throttle_hover

            # ── Physics integration step ─────────────────────────────────────
            platform.step(
                roll_cmd=current_roll_cmd,
                pitch_cmd=current_pitch_cmd,
                yaw_rate_cmd=current_yaw_cmd,
                throttle_cmd=current_throttle_cmd,
                dt=dt_sim,
            )
            target.step(dt_sim)

            # Store trajectory at vision rate for efficiency
            if verbose and frame_id % 1 == 0:
                vehicle_traj.append((t, *platform.state.pos.tolist()))
                target_traj.append((t, *target.state.pos.tolist()))

            t += dt_sim

        final_range = float(np.linalg.norm(target.state.pos - platform.state.pos))

        return OperationResult(
            hit=(min_range < sim_cfg.capture_radius_m),
            miss_distance_m=min_range,
            time_to_closest_approach_s=t_min_range,
            policy_reject=policy_reject,
            policy_reject_reason=policy_reject_reason,
            operation_time_s=t,
            config=cfg,
            vehicle_trajectory=vehicle_traj,
            target_trajectory=target_traj,
            control_cmds=control_cmds_log,
            final_range_m=final_range,
            n_frame_drops=n_frame_drops,
            n_policy_reject_attempts=n_policy_reject_attempts,
            smith_predictor_used=use_smith,
            mode=cfg.mode,
            n_off_fov_frames=pixel_state.n_off_fov_frames if pixel_state is not None else 0,
            lock_states_seen=pixel_state.lock_states_seen if pixel_state is not None else set(),
        )


# ---------------------------------------------------------------------------
# Monte-Carlo runner
# ---------------------------------------------------------------------------

@dataclass
class MonteCarloResult:
    """Aggregated results from a Monte-Carlo miss-distance sweep.

    Attributes
    ----------
    n_runs:
        Total number of runs.
    n_hits:
        Number of HITs (miss_distance < capture_radius).
    n_halts:
        Number of POLICY_REJECTs.
    miss_distances_m:
        Array of miss distances for all runs (m).
    miss_median_m, miss_p90_m, miss_max_m:
        Percentile statistics of miss distances (m).
    hit_rate:
        n_hits / n_runs.
    N_value:
        Navigation ratio N used.
    geometry:
        Target operation geometry.
    sensor_delay_s:
        Sensor delay used.
    smith_predictor:
        Whether Smith-predictor was used.
    """
    n_runs: int = 0
    n_hits: int = 0
    n_halts: int = 0
    miss_distances_m: npt.NDArray[np.float64] = field(
        default_factory=lambda: np.array([], dtype=np.float64)
    )
    miss_median_m: float = float("nan")
    miss_p90_m: float = float("nan")
    miss_max_m: float = float("nan")
    hit_rate: float = 0.0
    N_value: float = 3.0
    geometry: str = "HEAD_ON"
    sensor_delay_s: float = 0.030
    smith_predictor: bool = True


def run_monte_carlo(
    base_cfg: ClosedLoopConfig,
    *,
    n_seeds: int = 50,
    N_values: Sequence[float] = (3.0, 4.0),
    geometries: Sequence[OperationGeometry] = (
        OperationGeometry.HEAD_ON,
        OperationGeometry.QUARTERING,
    ),
    sensor_delays_s: Sequence[float] = (0.0, 0.025, 0.045),
    smith_predictor_values: Sequence[bool] = (True, False),
    randomize: bool = False,
    randomize_frac: float = 0.2,
    latency_jitter_max_s: float = 0.010,    # A5: per-frame delay jitter swept in [0, this] when randomize
    target_step_jink_max_g: float = 0.28,   # A5: sustained step-jink swept in [0, this] when randomize
    verbose: bool = False,
) -> list[MonteCarloResult]:
    """Run a Monte-Carlo sweep over seeds, geometries, N values, delays.

    Each combination of (N, geometry, sensor_delay, smith) is swept over
    n_seeds random seeds.

    Parameters
    ----------
    base_cfg:
        Base configuration.  N, geometry, sensor_delay, smith_predictor will
        be overridden by the sweep values.
    n_seeds:
        Number of random seeds per combination.
    N_values:
        Navigation ratios to sweep.
    geometries:
        Operation geometries to sweep.
    sensor_delays_s:
        Sensor delays to sweep (seconds).
    smith_predictor_values:
        Whether to use Smith-predictor lead.
    verbose:
        Print progress.

    Returns
    -------
    list[MonteCarloResult]
        One result per (N, geometry, delay, smith) combination.
    """
    results = []

    for N in N_values:
        for geom in geometries:
            for delay_s in sensor_delays_s:
                for smith in smith_predictor_values:
                    misses = []
                    n_hits = 0
                    n_halts = 0

                    for seed in range(n_seeds):
                        # A5 honest Monte-Carlo: when randomize, draw the plant/target params
                        # per seed so robustness is not measured against a single fixed plant.
                        # (Per-frame latency jitter is a deeper sim change -- noted in the plan.)
                        b = base_cfg.sim
                        if randomize:
                            r = np.random.default_rng((0xA5A50000 ^ (seed * 2654435761)) & 0xFFFFFFFF)
                            j = r.uniform(-randomize_frac, randomize_frac, size=4)
                            attitude_tau = float(b.attitude_tau_s * (1.0 + j[0]))
                            drag = float(b.drag_coeff * (1.0 + j[1]))
                            mass = float(b.mass_kg * (1.0 + j[2]))
                            bearing_noise = float(b.bearing_noise_sigma_rad * (1.0 + j[3]))
                            target_jink = float(r.uniform(0.0, max(b.target_jink_g, 0.28)))
                            # A5: sweep the two stressors the gate NAMES but never exercised --
                            # per-frame latency jitter and the SUSTAINED step-jink (the sinusoidal
                            # target_jink_g averages to zero; the step is what actually tests miss).
                            latency_jitter = float(r.uniform(0.0, latency_jitter_max_s))
                            target_step_jink = float(r.uniform(0.0, target_step_jink_max_g))
                        else:
                            attitude_tau, drag, mass = b.attitude_tau_s, b.drag_coeff, b.mass_kg
                            bearing_noise, target_jink = b.bearing_noise_sigma_rad, b.target_jink_g
                            latency_jitter, target_step_jink = b.latency_jitter_s, b.target_step_jink_g
                        # Override sim config
                        sim_cfg = SimConfig(
                            seed=seed,
                            target_geometry=geom,
                            sensor_delay_s=delay_s,
                            smith_predictor=smith,
                            # carry rest from base:
                            dt_sim_s=b.dt_sim_s,
                            control_rate_hz=b.control_rate_hz,
                            vision_rate_hz=b.vision_rate_hz,
                            loop_delay_s=b.loop_delay_s,
                            theta_max_rad=b.theta_max_rad,
                            drag_coeff=drag,
                            attitude_tau_s=attitude_tau,
                            mass_kg=mass,
                            capture_radius_m=b.capture_radius_m,
                            target_speed_mps=b.target_speed_mps,
                            target_jink_g=target_jink,
                            target_jink_freq_hz=b.target_jink_freq_hz,
                            target_step_jink_g=target_step_jink,
                            latency_jitter_s=latency_jitter,
                            vehicle_speed_mps=b.vehicle_speed_mps,
                            initial_range_m=b.initial_range_m,
                            max_sim_time_s=b.max_sim_time_s,
                            bearing_noise_sigma_rad=bearing_noise,
                            # Wave-1 honest measurement model: carry from base so an honest-MC
                            # sweep actually injects the correlated lambda-dot bias + noisy looming
                            # area.  Default 0 on the base -> these stay 0 -> bit-identical baseline.
                            los_rate_bias_sigma_radps=b.los_rate_bias_sigma_radps,
                            los_rate_bias_tau_s=b.los_rate_bias_tau_s,
                            area_noise_frac=b.area_noise_frac,
                            gyro_scale_error=b.gyro_scale_error,
                            looming_from_detected_area=b.looming_from_detected_area,
                            # High-speed regime: carry the forward speed-hold so a 150 m/s sweep
                            # actually cruises at the setpoint (default OFF -> bit-identical).
                            speed_hold=b.speed_hold,
                            speed_hold_gain_hz=b.speed_hold_gain_hz,
                        )
                        control_cfg = ControlConfig(
                            N=N,
                            Vc_sched_mps=base_cfg.control.Vc_sched_mps,
                            theta_max_rad=base_cfg.control.theta_max_rad,
                            halt_g_margin=base_cfg.control.halt_g_margin,
                            crossing_rate_threshold_radps=base_cfg.control.crossing_rate_threshold_radps,
                            vc_scaled_crossing_threshold=base_cfg.control.vc_scaled_crossing_threshold,
                            tau_confidence_pursuit_threshold=base_cfg.control.tau_confidence_pursuit_threshold,
                            tau_confidence_full_brn_threshold=base_cfg.control.tau_confidence_full_brn_threshold,
                            pursuit_gain_mps2_per_rad=base_cfg.control.pursuit_gain_mps2_per_rad,
                            maneuver_prob_threshold=base_cfg.control.maneuver_prob_threshold,
                            apn_accel_cap_mps2=base_cfg.control.apn_accel_cap_mps2,
                            max_a_cmd_mps2=base_cfg.control.max_a_cmd_mps2,
                        )
                        cl_cfg = ClosedLoopConfig(
                            sim=sim_cfg,
                            control=control_cfg,
                            pilot=base_cfg.pilot,
                            imm=base_cfg.imm,
                            mode=base_cfg.mode,
                            los_hold_decay=base_cfg.los_hold_decay,
                            smith_predictor=smith,
                        )
                        loop = ClosedLoop(cl_cfg)
                        result = loop.run(verbose=False)

                        misses.append(result.miss_distance_m)
                        if result.hit:
                            n_hits += 1
                        if result.policy_reject:
                            n_halts += 1

                    miss_arr = np.array(misses, dtype=np.float64)
                    # Filter out inf for stats (POLICY_REJECTs may have inf miss)
                    finite_misses = miss_arr[np.isfinite(miss_arr)]
                    if len(finite_misses) > 0:
                        median_m = float(np.median(finite_misses))
                        p90_m = float(np.percentile(finite_misses, 90))
                        max_m = float(np.max(finite_misses))
                    else:
                        median_m = p90_m = max_m = float("nan")

                    mc_result = MonteCarloResult(
                        n_runs=n_seeds,
                        n_hits=n_hits,
                        n_halts=n_halts,
                        miss_distances_m=miss_arr,
                        miss_median_m=median_m,
                        miss_p90_m=p90_m,
                        miss_max_m=max_m,
                        hit_rate=n_hits / n_seeds,
                        N_value=N,
                        geometry=geom.value,
                        sensor_delay_s=delay_s,
                        smith_predictor=smith,
                    )
                    results.append(mc_result)

                    if verbose:
                        print(
                            f"  N={N} geom={geom.value:<14} delay={delay_s*1e3:.0f}ms "
                            f"smith={str(smith):<5} "
                            f"hits={n_hits}/{n_seeds} "
                            f"miss: med={median_m:.2f}m p90={p90_m:.2f}m max={max_m:.2f}m "
                            f"halts={n_halts}"
                        )

    return results

```


## `vision/control/pixel_loop.py`

```python
"""Mode B (pixel-in-the-loop) vision-tick bridge for the closed-loop sim.

OVERVIEW
--------
This module provides ``run_pixel_vision_tick`` — a drop-in replacement for the
Mode A analytic vision tick in ``closed_loop.py``.

When ``mode='pixel'`` the *entire* tracker pipeline is exercised each vision tick:

    1. geometry  -> project true body-frame bearing to a camera pixel
    2. thermal_sim -> render a synthetic thermal frame (hot blob + stars + noise)
    3. detect    -> S1 blob detection on the rendered frame
    4. egomotion -> gyro de-rotation driven by REAL platform body rates (NOT scripted)
    5. los       -> LOSComputer ego-compensated bearing + LOS-rate
    6. track     -> ThermalLockTracker lock/coast/reacquire FSM
    7. imm       -> IMMFilter filtered LOS-rate (fed to control as λ̇)
    8. delay     -> DelayBuffer injects the Boson >25 ms sensor delay

BODY / CAMERA FRAME AND EGO-COMPENSATION
------------------------------------------
The closed-loop platform_sim uses the VELOCITY DIRECTION as the camera boresight.
This means the camera is effectively gimballed to always point along the velocity
vector — the bearing (az, el) computed by ``compute_bearing_from_states`` already
reflects the full body attitude (roll, pitch, yaw) via the velocity direction.

Consequence for ego-compensation
    The bearing rendered to a pixel already accounts for the body attitude.
    Between frames, the change in the bearing pixel IS the true LOS motion
    (target own motion relative to the velocity-aligned boresight).
    Unlike a rigidly-body-fixed camera, the body rotation does NOT cause
    additional apparent pixel motion on top of the true LOS motion.

    HOWEVER: for the star rendering, we DO apply ego shift to stars because stars
    are WORLD-FIXED and their positions shift in the image due to both the
    velocity-direction change AND the body roll.  The ego shift applied to stars
    drives the LOSComputer to produce a non-zero ego estimate, which it uses to
    compensate apparent star motion.  For the TARGET, which is computed from
    geometry, its pixel position already reflects the true bearing — so the ego
    compensation applied by LOSComputer to the target centroid will slightly
    over-compensate.

    FIX (Mode B specific): We feed body rates to gyro_derotation as in S2 tests,
    but we ONLY apply the ego to star rendering (to make KLT honest) and NOT
    to the LOSComputer's bearing computation.  Instead, the LOSComputer input
    centroid is passed as-is (the detected centroid), and the ego estimate is
    passed so that the rate computation is ego-corrected.  This correctly
    computes the relative LOS rate (target own angular motion) while leaving the
    bearing accurate.

    In practice: for a velocity-aligned boresight, the pitch/yaw body rates
    cause the velocity direction to change, which is already captured in the
    changing target pixel position.  The ego shift is zero for a velocity-aligned
    camera.  We therefore pass omega=(0,0,roll_rate_only) to the gyro derotation,
    where roll_rate is the boresight-axis rotation rate (the only ego that is NOT
    captured by the velocity-direction change).

    Simplified implementation: pass ego with zero pitch/yaw rates (only roll
    from the boresight axis change) so that the LOSComputer's ego-compensation
    only corrects the in-plane roll, not pitch/yaw which are already in the pixel.

GEOMETRY -> PIXEL PROJECTION (sign-exact derivation)
------------------------------------------------------
Given the true 3-D geometry (platform position + ATTITUDE + target position):
1. Compute body-frame bearing (az_true, el_true) using compute_bearing_from_states.
   This function uses boresight = velocity direction, body_right = boresight × world_up,
   body_up = body_right × boresight.
2. Project to pixel using geometry.bearing_to_pixel:
       px = cx + f * tan(az_true)       (right is +x in image = positive az)
       py = cy - f * tan(el_true)       (up is -y in image = positive el is up → py < cy)
3. If (px, py) is outside [0, W) x [0, H), the target is OFF-FOV — do NOT render
   a target blob; the tracker will coast/reacquire.

IMPORTANT: When mode='pixel', the analytic true bearing az_true / el_true is used
ONLY to compute the target pixel for rendering.  The bearing that drives control
is ALWAYS the output of detect->los->imm, never az_true/el_true.

LATENCY
-------
The Boson >25 ms delay is injected via the same _DelayBuffer from closed_loop.py.
The bearing pushed into the delay buffer is the IMM estimate, not az_true.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np
import numpy.typing as npt

from vision.tracker.detect import detect_frame, ThresholdState
from vision.tracker.egomotion import gyro_derotation
from vision.tracker.los import LOSComputer, LOSObservation
from vision.tracker.track import ThermalLockTracker, ThermalLockConfig, TrackingState
from vision.tracker.blob import TargetObservation
from vision.tracker.imm import IMMFilter, IMMConfig, IMMEstimate
from vision.tracker.geometry import (
    CameraIntrinsics,
    bearing_to_pixel,
    focal_length_from_hfov,
    ft640_intrinsics,
)

from vision.control.platform_sim import PlatformState, TargetState, compute_bearing_from_states


def _wide_vision_intrinsics() -> CameraIntrinsics:
    """Return camera intrinsics for the fielded vision thermal tracker.

    WAVE-3: reconciled to the FOXEER FT640 V2 wide lens (HFOV 48.7°,
    f_px ≈ 707 px, ≈1.41 mrad/px) — the camera actually fielded on the Block-3
    vehicle and the one the DETECT-envelope budget assumes.  Previously this
    returned a hand-rolled "Boson 640 9 mm @ 50° HFOV" model (f_px ≈ 686); the
    geometry was already in the right wide ballpark, but ft640_intrinsics() is
    the single source of truth so the pixel-in-the-loop optics match the budget
    and the Mode-A looming f_px exactly.

    A 48.7° HFOV gives VFOV ≈ 39.8° at 640×512, so the target stays on-sensor
    for pitch / yaw excursions up to ~±20 deg — consistent with the 40 deg
    theta_max in the dynamics model.
    """
    return ft640_intrinsics()


# ---------------------------------------------------------------------------
# Thermal frame renderer (inline, no dependency on ThermalSimulator.generate)
# ---------------------------------------------------------------------------

def _render_one_frame(
    *,
    target_px: float,
    target_py: float,
    target_in_fov: bool,
    cum_ego_dx: float,
    cum_ego_dy: float,
    intrinsics: CameraIntrinsics,
    star_positions: list[tuple[float, float]],
    rng: np.random.Generator,
    sky_base_counts: int = 4096,
    sky_gradient_amplitude: float = 200.0,
    read_noise_sigma: float = 12.0,
    target_peak_above_bg: float = 1800.0,
    target_sigma_px: float = 1.5,
    star_peak_fraction: float = 0.55,
    cam_temp_c: float = 25.0,
    cam_temp_additive: float = 0.0,
) -> npt.NDArray[np.uint16]:
    """Render one synthetic thermal frame.

    Mirrors tracker_sim.TrackerSim._render_thermal_frame but is driven by the
    live geometry rather than a scripted trajectory.

    Stars are placed at (sx + cum_ego_dx, sy + cum_ego_dy) so that
    world-fixed stars shift in the image with the cumulative ego — this is
    what makes KLT honest (stars move with ego).

    If target_in_fov is False, the target blob is omitted (off-FOV lock-loss
    scenario).
    """
    H = intrinsics.height
    W = intrinsics.width

    # Cold sky + gradient + read noise
    yy = np.linspace(0.0, 1.0, H)[:, np.newaxis]
    sky_grad = sky_gradient_amplitude * (0.6 * yy)
    sky_grad = np.broadcast_to(sky_grad, (H, W)).copy()
    noise = rng.normal(0.0, read_noise_sigma, size=(H, W))
    frame_f = (np.full((H, W), float(sky_base_counts), dtype=np.float64)
               + sky_grad + noise + cam_temp_additive)

    yy_idx = np.arange(H, dtype=np.float64)[:, np.newaxis]
    xx_idx = np.arange(W, dtype=np.float64)[np.newaxis, :]

    # Target hot spot — only if in FOV
    if target_in_fov:
        dx = xx_idx - target_px
        dy = yy_idx - target_py
        r2 = dx * dx + dy * dy
        frame_f += target_peak_above_bg * np.exp(-r2 / (2.0 * target_sigma_px ** 2))

    # Stars: world-fixed features translated by cumulative ego shift
    star_peak = target_peak_above_bg * star_peak_fraction
    star_sigma = max(0.8, target_sigma_px * 0.8)
    for sx, sy in star_positions:
        star_img_x = sx + cum_ego_dx
        star_img_y = sy + cum_ego_dy
        dx_s = xx_idx - star_img_x
        dy_s = yy_idx - star_img_y
        r2_s = dx_s * dx_s + dy_s * dy_s
        frame_f += star_peak * np.exp(-r2_s / (2.0 * star_sigma ** 2))

    return np.clip(frame_f, 0.0, 16383.0).astype(np.uint16)


# ---------------------------------------------------------------------------
# Persistent per-operation pixel-loop state
# ---------------------------------------------------------------------------

@dataclass
class PixelLoopState:
    """Mutable state for one Mode B operation.

    Held by the caller (ClosedLoop.run) and updated each vision tick.
    Encapsulates all S1/S2 pipeline state so the per-operation harness is
    clean.

    Attributes
    ----------
    intrinsics:
        Camera intrinsics (FOXEER FT640 V2 wide lens by default — see
        _wide_vision_intrinsics; was a 50-deg "Boson 9 mm" model pre-Wave-3).
    star_positions:
        Fixed world star positions (set at construction, stable across frames).
    rng:
        Per-operation RNG for render noise (seeded deterministically).
    threshold_state:
        S1 adaptive threshold state (carried across frames).
    tracker:
        ThermalLockTracker FSM.
    los_computer:
        LOSComputer (S2 ego-compensated bearing + rate).
    imm:
        IMMFilter for LOS-rate smoothing.
    prev_attitude_rad:
        Previous frame's platform attitude_rad [roll, pitch, yaw] for finite-
        difference body-rate estimation.
    cum_ego_dx, cum_ego_dy:
        Cumulative translational ego shift (pixels) for star rendering.
    cum_roll_rad:
        Cumulative roll angle (radians) for star rendering.
    frame_count:
        Number of frames rendered (for FFC injection spacing).
    last_los_obs:
        Most recent LOSObservation from the real pipeline (for hold-on-drop).
    last_imm_est:
        Most recent IMMEstimate (for hold-on-drop).
    n_off_fov_frames:
        Counter for consecutive off-FOV frames (diagnostic).
    lock_states_seen:
        Set of TrackingState values observed (for Gate P assertion).
    """

    intrinsics: CameraIntrinsics = field(
        default_factory=_wide_vision_intrinsics
    )
    star_positions: list[tuple[float, float]] = field(default_factory=list)
    rng: np.random.Generator = field(
        default_factory=lambda: np.random.default_rng(0)
    )
    threshold_state: ThresholdState = field(default_factory=ThresholdState)
    tracker: ThermalLockTracker = field(
        default_factory=lambda: ThermalLockTracker(ThermalLockConfig(
            stable_frame_count=3,
            max_gate_px=60.0,           # slightly wider than default for sim
            predictive_track_frames=18,
            reacquire_frames=90,
        ))
    )
    los_computer: LOSComputer = field(init=False)
    imm: IMMFilter = field(init=False)
    prev_attitude_rad: Optional[npt.NDArray[np.float64]] = None
    cum_ego_dx: float = 0.0
    cum_ego_dy: float = 0.0
    cum_roll_rad: float = 0.0
    frame_count: int = 0
    last_los_obs: Optional[LOSObservation] = None
    last_imm_est: Optional[IMMEstimate] = None
    n_off_fov_frames: int = 0
    lock_states_seen: set = field(default_factory=set)
    # Mode-B cam<->IMU / gyro scale-factor residual on the roll de-rotation (0 -> bit-identical).
    gyro_scale_error: float = 0.0
    # Real detected blob area (px) from the last detected frame, for honest looming/tau.
    last_detected_area_px: Optional[float] = None

    def __post_init__(self) -> None:
        self.los_computer = LOSComputer(self.intrinsics)
        # IMMConfig with slightly looser noise to tolerate detection quantization
        imm_cfg = IMMConfig(
            sigma_meas_az=2e-3,
            sigma_meas_el=2e-3,
            sigma_meas_az_rate=0.02,
            sigma_meas_el_rate=0.02,
            q_cv_rate=0.01,
            q_maneuver_rate=0.8,
            ego_gate_radps=0.1,
        )
        self.imm = IMMFilter(imm_cfg)

    def seed_tracker(self, intrinsics: CameraIntrinsics) -> None:
        """Seed the lock tracker over the full sensor area.

        In the closed-loop sim the target starts near the image centre
        (boresight-aligned head-on geometry) but may move anywhere in the FOV.
        Using the full-image acquisition box avoids spurious CANDIDATE→NO_TARGET
        resets during the initial frames where the centroid may drift slightly.
        """
        self.tracker.seed(acquisition_box=(
            0.0, 0.0,
            float(intrinsics.width),
            float(intrinsics.height),
        ))


def make_pixel_loop_state(
    sim_seed: int,
    imm_cfg: Optional[IMMConfig] = None,
    gyro_scale_error: float = 0.0,
) -> PixelLoopState:
    """Construct a fresh PixelLoopState for one Mode B operation.

    Parameters
    ----------
    sim_seed:
        Operation random seed.  Stars are placed deterministically from this.
    imm_cfg:
        Optional IMMConfig override (uses Mode B defaults if None).
    """
    intr = _wide_vision_intrinsics()

    # Fixed star positions (world frame, stable across the operation)
    rng_stars = np.random.default_rng(sim_seed * 1000 + 7)
    margin = 30
    xs = rng_stars.uniform(margin, intr.width - margin, size=12).tolist()
    ys = rng_stars.uniform(margin, intr.height - margin, size=12).tolist()
    stars = list(zip(xs, ys))

    state = PixelLoopState(
        intrinsics=intr,
        star_positions=stars,
        rng=np.random.default_rng(sim_seed * 31337 + 13),
        gyro_scale_error=float(gyro_scale_error),
    )

    if imm_cfg is not None:
        state.imm = IMMFilter(imm_cfg)

    state.seed_tracker(intr)
    return state


# ---------------------------------------------------------------------------
# Public: one Mode B vision tick
# ---------------------------------------------------------------------------

def run_pixel_vision_tick(
    *,
    q_state: PlatformState,
    tgt_state: TargetState,
    pixel_state: PixelLoopState,
    frame_id: int,
    t_sim: float,
    dt_vision: float,
    range_m: float,
) -> tuple[Optional[LOSObservation], Optional[IMMEstimate], bool]:
    """Execute one Mode B vision tick.

    Geometry -> render -> detect -> ego -> los -> track -> imm.

    This function has NO path from which the analytic bearing (computed from
    q_state/tgt_state) reaches the returned LOSObservation or IMMEstimate.
    The analytic bearing is used ONLY to determine the target pixel for
    rendering.  After rendering, the pipeline is fully data-driven.

    Parameters
    ----------
    q_state:
        Current vehicle state (position, velocity, attitude_rad).
    tgt_state:
        Current target state.
    pixel_state:
        Mutable per-operation state (updated in place).
    frame_id:
        Monotonically increasing frame counter.
    t_sim:
        Current simulation time (seconds).
    dt_vision:
        Time elapsed since the previous vision tick (seconds).
    range_m:
        Current slant range (for blob area scaling, informational only).

    Returns
    -------
    (los_obs, imm_est, target_detected)
        los_obs:   LOSObservation from S2, or None if target not detected/locked.
        imm_est:   IMMEstimate from the filter, or None if no observation.
        target_detected: True if the target was detected and associated this frame.
    """
    intr = pixel_state.intrinsics
    ps = pixel_state

    # ------------------------------------------------------------------
    # STEP 1: Compute true body-frame bearing (ONLY for rendering pixel)
    # ------------------------------------------------------------------
    az_true, el_true, _ = compute_bearing_from_states(
        q_state.pos, q_state.vel, tgt_state.pos
    )

    # ------------------------------------------------------------------
    # STEP 2: Project to pixel and check FOV
    # ------------------------------------------------------------------
    px_true, py_true = bearing_to_pixel(az_true, el_true, intr)

    # FOV check: target must project onto sensor [0,W) x [0,H)
    target_in_fov = (
        0.0 <= px_true < intr.width
        and 0.0 <= py_true < intr.height
    )

    if not target_in_fov:
        ps.n_off_fov_frames += 1

    # ------------------------------------------------------------------
    # STEP 3: Estimate body angular rates from attitude finite-differences.
    #
    # PlatformSim attitude_rad = [roll, pitch, yaw].
    # Convention mapping to tracker egomotion.py:
    #   omega_x = pitch rate = d(attitude[1])/dt  (about body +X rightward)
    #   omega_y = yaw rate   = d(attitude[2])/dt  (about body +Y upward)
    #   omega_z = roll rate  = d(attitude[0])/dt  (about body +Z boresight)
    #
    # EGO COMPENSATION DESIGN FOR VELOCITY-ALIGNED BORESIGHT
    # --------------------------------------------------------
    # The platform_sim compute_bearing_from_states uses the VELOCITY direction as the
    # camera boresight.  This means pitch and yaw body rates already change the
    # boresight direction and are reflected in the target pixel position change
    # from frame to frame.  Passing pitch/yaw rates to gyro_derotation would
    # cause LOSComputer to DOUBLE-COMPENSATE (the pixel already moved due to
    # pitch/yaw; subtracting the ego would subtract it twice).
    #
    # For STAR rendering: stars are world-fixed.  Their image positions shift due
    # to BOTH velocity-direction change (pitch/yaw body motion → boresight rotates
    # → stars move in the image) AND body roll (in-plane rotation of the image).
    # We apply the full ego shift to stars to make them move realistically in the
    # rendered frame (so KLT tracks them correctly).
    #
    # For LOSComputer INPUT: we pass omega_x=0, omega_y=0 (pitch/yaw already in
    # pixel), and omega_z=roll_rate (roll is NOT captured by velocity direction;
    # it causes in-plane image rotation).  This means LOSComputer only
    # compensates for the roll component.
    #
    # For STAR RENDERING: use the full (omega_x, omega_y, omega_z) to shift stars
    # so that KLT on stars is honest.
    # ------------------------------------------------------------------
    att_now = q_state.attitude_rad.copy()  # [roll, pitch, yaw]

    if ps.prev_attitude_rad is not None and dt_vision > 0.0:
        att_prev = ps.prev_attitude_rad
        omega_x_full = (att_now[1] - att_prev[1]) / dt_vision   # pitch rate
        omega_y_full = (att_now[2] - att_prev[2]) / dt_vision   # yaw rate
        omega_z_full = (att_now[0] - att_prev[0]) / dt_vision   # roll rate
    else:
        omega_x_full = omega_y_full = omega_z_full = 0.0

    ps.prev_attitude_rad = att_now

    # Full ego for star rendering (apply to stars so they move with body rotation)
    ego_for_stars = gyro_derotation(
        omega_xyz_radps=(omega_x_full, omega_y_full, omega_z_full),
        dt=max(dt_vision, 1e-4),
        intrinsics=intr,
    )

    # Roll-only ego for LOSComputer (avoid double-compensating pitch/yaw)
    # Only omega_z (roll) causes in-plane image rotation not captured by the
    # velocity-aligned boresight.
    #
    # DESIGN NOTE — ego_for_los.shift_px is intentionally (0, 0):
    #   The shift_px field of an EgoEstimate encodes the TRANSLATIONAL shift of
    #   the image principal point due to pitching/yawing body motion.  Here we
    #   pass omega_x=0, omega_y=0, so gyro_derotation computes zero translational
    #   shift — only the roll_rad field is non-zero.
    #
    #   This is CORRECT for a velocity-aligned boresight: pitch and yaw body
    #   rates rotate the boresight and are already captured by the changing target
    #   pixel position (compute_bearing_from_states uses the velocity direction).
    #   Passing a non-zero shift_px for pitch/yaw would cause LOSComputer to
    #   SUBTRACT the ego shift from the centroid, double-compensating those axes.
    #
    #   CAVEAT — OFF-BORESIGHT CAMERA MOUNT:
    #   If the camera is mounted off-boresight (e.g., canted forward by 5 deg for
    #   a downward-looking configuration), this shortcut breaks down.  In that case
    #   the body pitch/yaw rates DO cause a translational shift of the camera image
    #   that is NOT captured by the velocity-direction change.  The full omega_xyz
    #   vector must be passed to gyro_derotation and ego_for_los, and
    #   compute_bearing_from_states must use the true camera boresight (not the
    #   velocity direction) as its reference frame.
    #   THIS MUST BE REASSESSED before any off-boresight mount is fielded.
    # Cam<->IMU / gyro scale-factor residual: the tracker's de-rotation uses an erroneous gyro
    # reading (omega_z_full * (1+err)), while the world (stars, above) rotated by the TRUE rate.
    # The mismatch leaves a residual in-plane rotation the LOSComputer cannot remove -> a correlated
    # LOS-rate error, the dominant strapdown defect.  err=0 -> bit-identical.
    omega_z_los = omega_z_full * (1.0 + ps.gyro_scale_error)
    ego_for_los = gyro_derotation(
        omega_xyz_radps=(0.0, 0.0, omega_z_los),
        dt=max(dt_vision, 1e-4),
        intrinsics=intr,
    )

    # Update cumulative ego for star placement in render (full rotation)
    ps.cum_ego_dx += ego_for_stars.shift_px[0]
    ps.cum_ego_dy += ego_for_stars.shift_px[1]
    ps.cum_roll_rad += ego_for_stars.roll_rad

    # ------------------------------------------------------------------
    # STEP 5: Render thermal frame
    #
    # cam_temp_additive: small sinusoidal to exercise adaptive threshold re-base
    # FFC freeze is NOT injected here (would need FFC-aware control coast path).
    # The REACQUIRE path is exercised by the off-FOV scenario instead.
    # ------------------------------------------------------------------
    cam_temp_additive = 30.0 * math.sin(2.0 * math.pi * t_sim / 5.0)
    frame_u16 = _render_one_frame(
        target_px=px_true,
        target_py=py_true,
        target_in_fov=target_in_fov,
        cum_ego_dx=ps.cum_ego_dx,
        cum_ego_dy=ps.cum_ego_dy,
        intrinsics=intr,
        star_positions=ps.star_positions,
        rng=ps.rng,
        cam_temp_additive=cam_temp_additive,
    )
    ps.frame_count += 1

    # ------------------------------------------------------------------
    # STEP 6: S1 detect
    # ------------------------------------------------------------------
    blobs, ps.threshold_state = detect_frame(
        frame_u16,
        cam_temp_c=25.0 + cam_temp_additive * 0.1,
        ffc_state="READY",
        threshold_state=ps.threshold_state,
        frame_id=frame_id,
        t_capture_ns=int(t_sim * 1e9),
    )

    obs = TargetObservation(
        frame_id=frame_id,
        t_capture_ns=int(t_sim * 1e9),
        cam_temp_c=25.0,
        ffc_state="READY",
        blobs=blobs,
        threshold_baseline_counts=ps.threshold_state.threshold_counts,
        detection_budget_ms=0.0,
    )

    # ------------------------------------------------------------------
    # STEP 7: Tracker update
    # ------------------------------------------------------------------
    snap = ps.tracker.update(obs)
    ps.lock_states_seen.add(snap.tracking_state)

    # When target is off-FOV and not detected, tracker will coast/reacquire.
    # In coast state, we hold the last valid LOS from the pipeline.
    if snap.associated_blob is None:
        # No detection — control will hold the last-valid LOS (coasting)
        return None, ps.last_imm_est, False

    # ------------------------------------------------------------------
    # STEP 8: S2 LOS computation (ego-compensated)
    # ------------------------------------------------------------------
    centroid_px: tuple[float, float] = snap.centroid_px
    # Stash the REAL detected blob area so the harness can drive looming/tau from what the sensor
    # actually saw (honest), instead of the true-range-derived area (a tautology).
    ps.last_detected_area_px = float(snap.associated_blob.area_px)

    los_obs = ps.los_computer.update(
        centroid_px=centroid_px,
        ego=ego_for_los,          # roll-only ego (pitch/yaw already in pixel)
        dt=max(dt_vision, 1e-4),
        frame_id=frame_id,
        t_capture_ns=int(t_sim * 1e9),
    )

    # ------------------------------------------------------------------
    # STEP 9: IMM filter update
    # ------------------------------------------------------------------
    imm_est = ps.imm.update(los_obs, dt=max(dt_vision, 1e-4))

    # Cache for hold-on-drop
    ps.last_los_obs = los_obs
    ps.last_imm_est = imm_est

    return los_obs, imm_est, True

```
