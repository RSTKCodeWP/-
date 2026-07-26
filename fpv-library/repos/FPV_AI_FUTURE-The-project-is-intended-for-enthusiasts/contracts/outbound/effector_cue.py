"""Schema-compatible, dry-run-only Phase W effector cue wrapper."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast

from cuas.interop.codec.jcs import canonical_json

SCHEMA_EFFECTOR_CUE = "effector_cue.v1"

REQUIRED_CUE_FIELDS = (
    "schema_version",
    "cue_id",
    "cue_issued_at_utc",
    "cue_validity_window_s",
    "sense_node_id",
    "operator_authorization_id",
    "cross_witness_node_ids",
    "cross_witness_signatures_ed25519",
    "local_frame_id",
    "track_id",
    "target_birth_level",
    "fused_confidence",
    "multi_modal_redundancy",
    "iff_status",
    "civil_aviation_clearance",
    "current_state_3d",
    "current_kinematics",
    "target_signature",
    "trajectory_prediction",
    "search_box_at_terminal",
    "launch_recommendation",
    "threat_assessment",
    "update_channels",
    "sense_node_ed25519_signature",
    "nonce_b64",
    "canonical_encoding_hash_sha256",
)


def _deep_copy_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(payload, ensure_ascii=False)))


@dataclass(frozen=True)
class EffectorCue:
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        if self.payload.get("schema_version") != SCHEMA_EFFECTOR_CUE:
            raise ValueError("EffectorCue requires schema_version effector_cue.v1")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EffectorCue":
        return cls(payload=_deep_copy_dict(payload))

    def to_dict(self) -> dict[str, Any]:
        return _deep_copy_dict(self.payload)

    def to_canonical_json(self) -> str:
        return canonical_json(self.payload)


def validate_effector_cue_shape(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if payload.get("schema_version") != SCHEMA_EFFECTOR_CUE:
        failures.append("schema_version")
    for field in REQUIRED_CUE_FIELDS:
        if field not in payload:
            failures.append(f"missing:{field}")
    if not isinstance(payload.get("trajectory_prediction"), dict):
        failures.append("trajectory_prediction_not_object")
    if not isinstance(payload.get("search_box_at_terminal"), dict):
        failures.append("search_box_not_object")
    if not isinstance(payload.get("launch_recommendation"), dict):
        failures.append("launch_recommendation_not_object")
    return failures
