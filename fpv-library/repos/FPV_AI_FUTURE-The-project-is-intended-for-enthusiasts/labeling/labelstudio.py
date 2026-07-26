"""Render Label Studio config XML for FPV racing gate annotation."""

from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fpv_ai.control.speed import SpeedMode
from fpv_ai.datasets.config import FpvRacingGateConfig

LABELING_REPORT_SCHEMA = "fpv_labeling_config_report.v1"
LABELING_XML_SCHEMA = "fpv_gate_labeling_config.v1"

GATE_LABEL_COLORS = {
    "racing_gate": "#00C853",
    "partial_gate": "#FFAB00",
    "false_ring_hard_negative": "#D50000",
}
PER_REGION_ATTRIBUTES = {
    "visibility": ("full", "partial", "occluded"),
    "blur_level": ("none", "mild", "heavy"),
    "passable": ("true", "false", "unknown"),
    "gate_angle": ("frontal", "mild_tilt", "steep_tilt", "unknown"),
}
GLOBAL_ATTRIBUTES = {
    "source_type": ("real_camera", "simulator", "augmentation"),
    "lighting_condition": ("day", "indoor", "dusk", "low_light", "unknown"),
    "frame_quality": ("usable", "review", "reject"),
}


def render_labelstudio_xml(config: FpvRacingGateConfig) -> str:
    root = ET.Element("View")
    ET.SubElement(root, "Header", value="FPV AI Gate-Lock: sports racing gate annotation", size="4")
    ET.SubElement(root, "Text", name="schema_version", value=LABELING_XML_SCHEMA)
    ET.SubElement(root, "Image", name="image", value="$image", zoom="true", zoomControl="true", rotateControl="true")
    _gate_labels(root, config)
    _gate_center_keypoint(root)
    _choices(root, PER_REGION_ATTRIBUTES, per_region=True)
    _choices(root, GLOBAL_ATTRIBUTES, per_region=False)
    _notes(root)
    return ET.tostring(root, encoding="unicode")


def build_labeling_config_report(
    config: FpvRacingGateConfig,
    *,
    xml_path: Path | None = None,
    write_performed: bool = False,
) -> dict[str, Any]:
    labels = [config.dataset.names[key] for key in sorted(config.dataset.names)]
    return {
        "schema": LABELING_REPORT_SCHEMA,
        "status": "PASS",
        "generated_at": _utc_now(),
        "domain": config.domain,
        "config_schema": config.schema,
        "xml_path": "" if xml_path is None else str(xml_path),
        "write_performed": write_performed,
        "label_count": len(labels),
        "labels": labels,
        "keypoints": ["gate_center"],
        "per_region_attributes": list(PER_REGION_ATTRIBUTES),
        "global_attributes": list(GLOBAL_ATTRIBUTES),
        "augmentation_scales": list(config.augmentation.scale_ladder),
        "operator_adjustable_race_speed": config.speed_policy.profile(
            SpeedMode.RACE_SPEED
        ).adjustable_by_operator,
        "dataset_write_performed": False,
        "training_launched": False,
        "hardware_test_authorized": False,
        "safety_boundary": {
            "sports_gate_only": True,
            "does_not_modify_real_dataset": True,
            "does_not_launch_training": True,
            "does_not_authorize_hardware_test": True,
        },
    }


def _gate_labels(root: ET.Element, config: FpvRacingGateConfig) -> None:
    rect = ET.SubElement(root, "RectangleLabels", name="gate_bbox", toName="image", smartOnly="false")
    for _class_id, label in sorted(config.dataset.names.items()):
        ET.SubElement(
            rect,
            "Label",
            value=label,
            background=GATE_LABEL_COLORS.get(label, "#607D8B"),
        )


def _gate_center_keypoint(root: ET.Element) -> None:
    keypoints = ET.SubElement(root, "KeyPointLabels", name="gate_center", toName="image", strokeWidth="2")
    ET.SubElement(keypoints, "Label", value="gate_center", background="#2962FF")


def _choices(root: ET.Element, groups: dict[str, tuple[str, ...]], *, per_region: bool) -> None:
    for name, values in groups.items():
        attrs = {
            "name": f"attr_{name}",
            "toName": "image",
            "choice": "single",
            "showInLine": "true",
        }
        if per_region:
            attrs["perRegion"] = "true"
        choices = ET.SubElement(root, "Choices")
        for attr_key, attr_value in attrs.items():
            choices.set(attr_key, attr_value)
        for value in values:
            ET.SubElement(choices, "Choice", value=value)


def _notes(root: ET.Element) -> None:
    ET.SubElement(
        root,
        "TextArea",
        name="attr_reacquire_notes",
        toName="image",
        rows="2",
        placeholder=html.escape("Briefly note occlusion, blur, false ring, or reacquire moment."),
        maxSubmissions="1",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
