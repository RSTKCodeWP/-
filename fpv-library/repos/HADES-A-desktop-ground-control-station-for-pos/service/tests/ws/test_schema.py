"""Tests for the WS detection message schema (Task 2.6).

`DetectionMessage` is the JSON-channel contract the service emits and the UI consumes,
aligned to a video frame by `frame_id` (== the FrameSource `seq`). Per DESIGN.md §2/§3.2:
boxes are `box_xyxy` in original-frame pixels; confidences in [0, 1]. The schema must
round-trip, validate a golden fixture, and REJECT malformed input (a bad message must
fail loudly at the process boundary, not flow downstream as a wrong coordinate).
"""

import json

import pytest
from pydantic import ValidationError

from hades.detect.detector import Detection
from hades.ws.schema import BoxMessage, DetectionMessage


def test_detection_message_round_trips():
    msg = DetectionMessage(
        frame_id=42,
        timestamp=1.5,
        boxes=[
            BoxMessage(box_xyxy=(10.0, 20.0, 30.0, 50.0), conf=0.9, cls="person"),
            BoxMessage(box_xyxy=(100.0, 100.0, 140.0, 180.0), conf=0.7, cls="person"),
        ],
    )
    wire = msg.model_dump_json()
    back = DetectionMessage.model_validate_json(wire)
    assert back == msg
    assert back.frame_id == 42
    assert back.boxes[0].box_xyxy == (10.0, 20.0, 30.0, 50.0)


def test_detection_message_from_detections_helper():
    dets = [
        Detection(box_xyxy=(10.0, 20.0, 30.0, 50.0), conf=0.9),
        Detection(box_xyxy=(1.0, 2.0, 3.0, 4.0), conf=0.4),
    ]
    msg = DetectionMessage.from_detections(frame_id=7, timestamp=0.25, detections=dets)
    assert msg.frame_id == 7
    assert len(msg.boxes) == 2
    assert msg.boxes[0].box_xyxy == (10.0, 20.0, 30.0, 50.0)
    assert msg.boxes[1].conf == pytest.approx(0.4)


def test_empty_boxes_is_valid():
    # An empty frame (no detections) is a normal, valid message — not an error.
    msg = DetectionMessage(frame_id=0, timestamp=0.0, boxes=[])
    back = DetectionMessage.model_validate_json(msg.model_dump_json())
    assert back.boxes == []


def test_schema_validates_golden_fixture():
    golden = {
        "type": "detection",
        "frame_id": 3,
        "timestamp": 0.1,
        "boxes": [{"box_xyxy": [5.0, 6.0, 15.0, 26.0], "conf": 0.8, "cls": "person"}],
    }
    msg = DetectionMessage.model_validate(golden)
    assert msg.frame_id == 3
    assert msg.boxes[0].conf == pytest.approx(0.8)
    # The discriminator `type` is preserved so the UI can route the message.
    assert msg.type == "detection"


def test_rejects_negative_frame_id():
    with pytest.raises(ValidationError):
        DetectionMessage(frame_id=-1, timestamp=0.0, boxes=[])


def test_rejects_conf_out_of_range():
    with pytest.raises(ValidationError):
        BoxMessage(box_xyxy=(0.0, 0.0, 1.0, 1.0), conf=1.5, cls="person")


def test_rejects_inverted_box():
    with pytest.raises(ValidationError):
        BoxMessage(box_xyxy=(30.0, 20.0, 10.0, 50.0), conf=0.5, cls="person")  # x_max<x_min


def test_rejects_zero_area_box():
    # Codex P2: a degenerate zero-area box must not survive onto the wire.
    with pytest.raises(ValidationError):
        BoxMessage(box_xyxy=(10.0, 20.0, 10.0, 50.0), conf=0.5, cls="person")  # zero width


def test_rejects_wrong_box_arity():
    with pytest.raises(ValidationError):
        BoxMessage(box_xyxy=(1.0, 2.0, 3.0), conf=0.5, cls="person")  # only 3 values


def test_rejects_missing_required_field():
    with pytest.raises(ValidationError):
        DetectionMessage.model_validate({"frame_id": 1, "boxes": []})  # no timestamp


def test_json_schema_is_exportable_and_has_frame_id():
    schema = DetectionMessage.model_json_schema()
    assert "frame_id" in schema["properties"]
    # Exportable to a JSON-Schema doc the UI side can consume.
    assert json.dumps(schema)
