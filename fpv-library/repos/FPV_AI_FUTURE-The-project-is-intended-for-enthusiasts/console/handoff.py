"""engagement_handoff.v1 -- the signed engagement order (Block-3 legal spine, ground side).

The launch console assembles an EngagementOrder from the operator's positive-ID + the two
deliberate physical acts (ARM key = secondary authority, FIRE button = primary commit), and
both authorities sign the SAME canonical order body with Ed25519. The onboard verifier checks
the dual signatures + window before the order can authorize arming. This is the producing side
of the contract documented in contracts/engagement_handoff.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

SCHEMA = "engagement_handoff.v1"


# ── Ed25519 helpers ──────────────────────────────────────────────────────────────
def generate_keypair() -> tuple[Ed25519PrivateKey, bytes]:
    """Return (private_key, 32-byte raw public key)."""
    sk = Ed25519PrivateKey.generate()
    pub = sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return sk, pub


def sign(private_key: Ed25519PrivateKey, data: bytes) -> bytes:
    return private_key.sign(data)


def verify(public_raw: bytes, signature: bytes, data: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(public_raw).verify(signature, data)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


# ── the order ────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class TargetRef:
    track_id: str
    classification: str    # e.g. "hostile_uav"
    confidence: float


@dataclass(frozen=True)
class EngagementOrder:
    """The signed body. mission_goal: RECON | CONTACT | KINETIC."""
    handoff_id: str
    schema_version: str
    issued_at_s: float
    expires_at_s: float
    mission_goal: str
    target: TargetRef
    keypress_ts: float     # the physical FIRE press time
    roe_pass: bool
    synthetic: bool


@dataclass(frozen=True)
class SignedHandoff:
    order: EngagementOrder
    primary_pubkey: bytes      # FIRE operator (primary commit)
    primary_signature: bytes
    secondary_pubkey: bytes    # ARM authority (secondary)
    secondary_signature: bytes


def canonical_order_bytes(order: EngagementOrder) -> bytes:
    """Deterministic byte serialization of the order body that both signers and the verifier
    sign/verify. Any field change invalidates the signatures."""
    body = {
        "handoff_id": order.handoff_id,
        "schema_version": order.schema_version,
        "issued_at_s": order.issued_at_s,
        "expires_at_s": order.expires_at_s,
        "mission_goal": order.mission_goal,
        "target": {
            "track_id": order.target.track_id,
            "classification": order.target.classification,
            "confidence": order.target.confidence,
        },
        "keypress_ts": order.keypress_ts,
        "roe_pass": order.roe_pass,
        "synthetic": order.synthetic,
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_order(order: EngagementOrder, *,
               primary_key: Ed25519PrivateKey, primary_pub: bytes,
               secondary_key: Ed25519PrivateKey, secondary_pub: bytes) -> SignedHandoff:
    body = canonical_order_bytes(order)
    return SignedHandoff(
        order=order,
        primary_pubkey=primary_pub, primary_signature=primary_key.sign(body),
        secondary_pubkey=secondary_pub, secondary_signature=secondary_key.sign(body),
    )
