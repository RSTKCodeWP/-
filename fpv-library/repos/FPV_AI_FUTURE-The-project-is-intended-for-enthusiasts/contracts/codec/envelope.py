"""Dry-run Ed25519 envelope helpers for Phase W cue-readiness artifacts."""

from __future__ import annotations

import base64
from typing import Any

from cuas.interop.codec.jcs import canonical_json_bytes, sha256_hex
from cuas.trust import NodeIdentity, TrustRegistry, sign_payload

PRIMARY_SIGNATURE_FIELD = "sense_node_ed25519_signature"
PRIMARY_HASH_FIELD = "canonical_encoding_hash_sha256"
PRIMARY_KEY_ID_FIELD = "sense_node_key_id"
WITNESS_KEY_IDS_FIELD = "cross_witness_key_ids"


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _body_without_primary_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {PRIMARY_SIGNATURE_FIELD, PRIMARY_HASH_FIELD}
    }


def witness_body(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in _body_without_primary_envelope(payload).items()
        if key not in {"cross_witness_signatures_ed25519", WITNESS_KEY_IDS_FIELD, PRIMARY_KEY_ID_FIELD}
    }


def sign_envelope(payload: dict[str, Any], *, identity: NodeIdentity) -> dict[str, Any]:
    body = _body_without_primary_envelope(dict(payload))
    body[PRIMARY_KEY_ID_FIELD] = identity.key_id
    signed = sign_payload(identity, body)
    out = dict(body)
    out[PRIMARY_HASH_FIELD] = sha256_hex(body)
    out[PRIMARY_SIGNATURE_FIELD] = signed["signature"]
    return out


def sign_witness(payload: dict[str, Any], *, identity: NodeIdentity) -> str:
    return str(sign_payload(identity, witness_body(payload))["signature"])


def _verify_signature(public_key_b64: str, signature_b64: str, payload: dict[str, Any]) -> bool:
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519

        public = ed25519.Ed25519PublicKey.from_public_bytes(_b64d(public_key_b64))
        public.verify(_b64d(signature_b64), canonical_json_bytes(payload))
    except Exception:  # noqa: BLE001 - verifier returns False for all signature failures.
        return False
    return True


def verify_envelope(payload: dict[str, Any], *, registry: TrustRegistry) -> bool:
    body = _body_without_primary_envelope(dict(payload))
    signature = str(payload.get(PRIMARY_SIGNATURE_FIELD, ""))
    digest = str(payload.get(PRIMARY_HASH_FIELD, ""))
    key_id = str(body.get(PRIMARY_KEY_ID_FIELD, ""))
    node = registry.nodes.get(key_id)
    if not signature or not digest or node is None or not node.active():
        return False
    if sha256_hex(body) != digest:
        return False
    return _verify_signature(node.public_key, signature, body)


def verify_witness(
    payload: dict[str, Any],
    *,
    registry: TrustRegistry,
    node_id: str,
    signature_b64: str,
) -> bool:
    for node in registry.active_keys_for_node(node_id):
        if _verify_signature(node.public_key, signature_b64, witness_body(payload)):
            return True
    return False
