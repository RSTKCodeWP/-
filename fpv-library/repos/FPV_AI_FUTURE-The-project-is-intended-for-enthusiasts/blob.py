"""Shared data contracts for the thermal seeker perception layer (S1).

``ThermalBlob`` is the elementary detector output for one connected component.
``TargetObservation`` bundles the per-frame list of blobs together with frame
metadata so that the downstream track FSM and guidance law can consume a single
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

SCHEMA: str = "fpv_thermal_blob_sequence.v1"

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
    guidance law) consume this type directly.

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
