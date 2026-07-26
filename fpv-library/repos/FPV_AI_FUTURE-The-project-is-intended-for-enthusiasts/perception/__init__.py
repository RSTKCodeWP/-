"""Perception adapters for FPV AI detector outputs."""

from __future__ import annotations

from fpv_ai.perception.detector_output import (
    ADAPTER_REPORT_SCHEMA,
    CANONICAL_SEQUENCE_SCHEMA,
    DetectorAdapterReport,
    adapt_detector_payload,
    build_synthetic_detector_payload,
    write_adapted_detector_output,
)
from fpv_ai.perception.yolo_offline import (
    YOLO_OFFLINE_REPORT_SCHEMA,
    build_synthetic_yolo_payload,
    run_yolo_offline_predict,
    write_yolo_offline_outputs,
    yolo_results_to_detector_payload,
)

__all__ = [
    "ADAPTER_REPORT_SCHEMA",
    "CANONICAL_SEQUENCE_SCHEMA",
    "DetectorAdapterReport",
    "adapt_detector_payload",
    "build_synthetic_detector_payload",
    "build_synthetic_yolo_payload",
    "run_yolo_offline_predict",
    "write_adapted_detector_output",
    "write_yolo_offline_outputs",
    "yolo_results_to_detector_payload",
    "YOLO_OFFLINE_REPORT_SCHEMA",
]
