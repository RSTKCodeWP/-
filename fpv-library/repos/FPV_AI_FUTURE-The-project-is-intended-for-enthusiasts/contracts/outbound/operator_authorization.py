"""Operator authorization contract for dry-run cue readiness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEMA_OPERATOR_AUTHORIZATION = "operator_authorization.v1"


@dataclass(frozen=True)
class OperatorAuthorization:
    authorization_id: str
    related_cue_id: str
    status: str
    reason: str
    operator_review_required: bool = True
    timestamp_utc: str = ""
    expires_at_utc: str = ""
    authorization_method: str = "missing"
    primary_operator_id: str = ""
    primary_operator_session_id: str = ""
    primary_operator_signature_ed25519: str = ""
    secondary_authority_id: str = ""
    secondary_authority_session_id: str = ""
    secondary_authority_signature_ed25519: str = ""
    biometric_factor_hash: str = ""
    physical_keypress_recorded: bool = False
    physical_keypress_timestamp_utc: str = ""
    roe_engine_pass: bool = False
    roe_ruleset_id: str = ""
    civcas_estimate: dict[str, Any] | None = None
    proportionality_assessment: str = ""
    mock_mode: bool = True
    dry_run_only: bool = True
    operator_review_audit_only: bool = True
    schema_version: str = SCHEMA_OPERATOR_AUTHORIZATION

    def to_dict(self) -> dict[str, Any]:
        civcas = self.civcas_estimate or {
            "schema_version": "civcas_assessment.v1",
            "risk_acceptable": False,
            "estimated_civilian_risk_class": "not_evaluated",
            "operator_review_only": True,
        }
        return {
            "schema_version": self.schema_version,
            "authorization_id": self.authorization_id,
            "related_cue_id": self.related_cue_id,
            "status": self.status,
            "reason": self.reason,
            "operator_review_required": self.operator_review_required,
            "timestamp_utc": self.timestamp_utc,
            "expires_at_utc": self.expires_at_utc,
            "authorization_method": self.authorization_method,
            "primary_operator_id": self.primary_operator_id,
            "primary_operator_session_id": self.primary_operator_session_id,
            "primary_operator_signature_ed25519": self.primary_operator_signature_ed25519,
            "secondary_authority_id": self.secondary_authority_id,
            "secondary_authority_session_id": self.secondary_authority_session_id,
            "secondary_authority_signature_ed25519": self.secondary_authority_signature_ed25519,
            "biometric_factor_hash": self.biometric_factor_hash,
            "physical_keypress_recorded": self.physical_keypress_recorded,
            "physical_keypress_timestamp_utc": self.physical_keypress_timestamp_utc,
            "roe_engine_pass": self.roe_engine_pass,
            "roe_ruleset_id": self.roe_ruleset_id,
            "civcas_estimate": civcas,
            "proportionality_assessment": self.proportionality_assessment,
            "mock_mode": self.mock_mode,
            "dry_run_only": self.dry_run_only,
            "operator_review_audit_only": self.operator_review_audit_only,
            "publication_authority_granted": False,
            "cue_emission_authorized_by_this_repository": False,
            "safety_boundary": {
                "sense_only": True,
                "dry_run_only": self.dry_run_only,
                "operator_review_audit_only": self.operator_review_audit_only,
                "no_action_cue": True,
                "no_effector_publication": True,
                "no_launch_or_intercept_command": True,
                "no_jamming_spoofing_or_target_engagement": True,
            },
        }


def missing_operator_authorization(cue_id: str) -> OperatorAuthorization:
    return OperatorAuthorization(
        authorization_id="missing_operator_authorization",
        related_cue_id=cue_id,
        status="MISSING",
        reason="dry_run_scaffold_does_not_issue_operator_authorization",
    )
