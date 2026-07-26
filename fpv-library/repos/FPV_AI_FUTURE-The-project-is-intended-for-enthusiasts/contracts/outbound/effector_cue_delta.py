"""Dry-run cue delta contract for Phase W."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cuas.interop.codec.jcs import canonical_json

SCHEMA_EFFECTOR_CUE_DELTA = "effector_cue_delta.v1"


@dataclass(frozen=True)
class EffectorCueDelta:
    delta_id: str
    refers_to_cue_id: str
    issued_at_utc: str
    sequence_number: int
    operator_abort: bool = False
    operator_recall: bool = False
    handoff_to_terminal_now: bool = False
    refined_state_3d: dict[str, Any] | None = None
    refined_kinematics: dict[str, Any] | None = None
    refined_trajectory: dict[str, Any] | None = None
    refined_search_box: dict[str, Any] | None = None
    new_threat_assessment: dict[str, Any] | None = None
    sense_node_ed25519_signature: str = ""
    nonce_b64: str = ""
    canonical_encoding_hash_sha256: str = ""
    dry_run_only: bool = True
    schema_version: str = SCHEMA_EFFECTOR_CUE_DELTA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "delta_id": self.delta_id,
            "refers_to_cue_id": self.refers_to_cue_id,
            "issued_at_utc": self.issued_at_utc,
            "sequence_number": self.sequence_number,
            "refined_state_3d": self.refined_state_3d,
            "refined_kinematics": self.refined_kinematics,
            "refined_trajectory": self.refined_trajectory,
            "refined_search_box": self.refined_search_box,
            "operator_abort": self.operator_abort,
            "operator_recall": self.operator_recall,
            "handoff_to_terminal_now": self.handoff_to_terminal_now,
            "new_threat_assessment": self.new_threat_assessment,
            "sense_node_ed25519_signature": self.sense_node_ed25519_signature,
            "nonce_b64": self.nonce_b64,
            "canonical_encoding_hash_sha256": self.canonical_encoding_hash_sha256,
            "dry_run_only": self.dry_run_only,
            "safety_boundary": {
                "dry_run_only": True,
                "no_effector_publication": True,
                "no_launch_or_intercept_command": True,
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EffectorCueDelta":
        return cls(
            delta_id=str(payload.get("delta_id", "")),
            refers_to_cue_id=str(payload.get("refers_to_cue_id", "")),
            issued_at_utc=str(payload.get("issued_at_utc", "")),
            sequence_number=int(payload.get("sequence_number", 0) or 0),
            operator_abort=bool(payload.get("operator_abort", False)),
            operator_recall=bool(payload.get("operator_recall", False)),
            handoff_to_terminal_now=bool(payload.get("handoff_to_terminal_now", False)),
            refined_state_3d=payload.get("refined_state_3d"),
            refined_kinematics=payload.get("refined_kinematics"),
            refined_trajectory=payload.get("refined_trajectory"),
            refined_search_box=payload.get("refined_search_box"),
            new_threat_assessment=payload.get("new_threat_assessment"),
            sense_node_ed25519_signature=str(payload.get("sense_node_ed25519_signature", "")),
            nonce_b64=str(payload.get("nonce_b64", "")),
            canonical_encoding_hash_sha256=str(payload.get("canonical_encoding_hash_sha256", "")),
            dry_run_only=bool(payload.get("dry_run_only", True)),
        )

    def to_canonical_json(self) -> str:
        return canonical_json(self.to_dict())
