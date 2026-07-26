"""G2U event validation, signing, and the no-weaponization gate.

This module is the architectural enforcement of the safety invariant:
**ground never tells UAV to engage**. Even if a future bug somewhere produces
an event with a forbidden action keyword, the verifier rejects it before it
hits the wire and before the UAV consumes it.

Signing uses Ed25519 (PyNaCl). When PyNaCl is not available we degrade to a
keyed-HMAC-SHA256 fallback so tests don't pull in a heavyweight dep — but
production deployments MUST use Ed25519. The fallback is clearly marked in
the envelope's `key_id` (`hmac:...`).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
import uuid
from importlib import resources
from pathlib import Path
from typing import Any, Iterable, Optional

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except ImportError:  # pragma: no cover
    _HAS_JSONSCHEMA = False


# ---------------------------------------------------------------------------
# Forbidden values — architectural enforcement
# ---------------------------------------------------------------------------

FORBIDDEN_FIELD_VALUES: tuple[str, ...] = (
    "engage", "intercept", "jam", "disable", "attack", "kinetic",
    "harm", "weapon", "fire", "destroy", "neutralize", "collide",
    "collision", "ram", "strike", "detonate", "munition",
)

# Substring (not word-boundary) match — paranoid: `engage_target`,
# `please_engage`, `kinetic_energy` all rejected. False positives in edge
# cases are acceptable cost for closing the obvious bypass.
_FORBIDDEN_RX = re.compile(
    "|".join(re.escape(w) for w in FORBIDDEN_FIELD_VALUES),
    re.IGNORECASE,
)

_SCHEMA_PACKAGE = "fpv.safety"
_SCHEMA_ROOT = "schemas"
_SCHEMAS_BY_ID: dict[str, dict[str, Any]] = {}


class G2UVerifyError(ValueError):
    """Raised when an event fails schema, safety, or signature checks."""


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------

def load_schema(schema_id: str) -> dict[str, Any]:
    """Load a schema by `$id` (e.g. 'g2u.track.v1')."""
    if schema_id in _SCHEMAS_BY_ID:
        return _SCHEMAS_BY_ID[schema_id]
    name = schema_id.replace("g2u.", "").replace(".", ".") + ".json"
    schema_resource = resources.files(_SCHEMA_PACKAGE).joinpath(_SCHEMA_ROOT).joinpath(name)
    if not schema_resource.is_file():
        raise G2UVerifyError(f"unknown schema: {schema_id}")
    schema = json.loads(schema_resource.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise G2UVerifyError(f"schema is not a JSON object: {schema_id}")
    _SCHEMAS_BY_ID[schema_id] = schema
    return schema


# ---------------------------------------------------------------------------
# Anti-weaponization gate
# ---------------------------------------------------------------------------

def _scan_forbidden(value: Any) -> Optional[str]:
    """Recursively walk the payload, return the first forbidden token found."""
    if isinstance(value, str):
        m = _FORBIDDEN_RX.search(value)
        return m.group(0).lower() if m else None
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str):
                m = _FORBIDDEN_RX.search(k)
                if m:
                    return m.group(0).lower()
            found = _scan_forbidden(v)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _scan_forbidden(item)
            if found:
                return found
    return None


# ---------------------------------------------------------------------------
# Per-schema invariants beyond JSON Schema
# ---------------------------------------------------------------------------

def _check_track_invariants(payload: dict[str, Any]) -> None:
    cov = payload.get("wgs84", {}).get("covariance_6x6")
    if not cov or len(cov) != 36 or all(abs(float(c)) < 1e-12 for c in cov):
        raise G2UVerifyError("track wgs84 covariance must be non-zero 36-element vector")


def _check_cue_invariants(payload: dict[str, Any]) -> None:
    if "expires_ts" not in payload:
        raise G2UVerifyError("cue must have expires_ts")
    if float(payload["expires_ts"]) <= float(payload.get("ts_utc", 0)):
        raise G2UVerifyError("cue expires_ts must be after ts_utc")


def _check_observation_cue_invariants(payload: dict[str, Any]) -> None:
    if "expires_ts" not in payload:
        raise G2UVerifyError("observation cue must have expires_ts")
    if float(payload["expires_ts"]) <= float(payload.get("ts_utc", 0)):
        raise G2UVerifyError("observation cue expires_ts must be after ts_utc")
    task = payload.get("task", {})
    if not isinstance(task, dict):
        raise G2UVerifyError("observation cue task must be an object")
    if task.get("mode") != "sense_only":
        raise G2UVerifyError("observation cue task.mode must be sense_only")
    allowed = task.get("allowed_actions", [])
    if not isinstance(allowed, list) or not allowed:
        raise G2UVerifyError("observation cue requires allowed_actions")
    allowed_set = {str(item) for item in allowed}
    safe_actions = {"observe", "record", "report", "return_home", "hold_position"}
    unsafe = sorted(allowed_set - safe_actions)
    if unsafe:
        raise G2UVerifyError("observation cue has unsupported allowed_actions: " + ", ".join(unsafe))


_INVARIANTS = {
    "g2u.track.v1": _check_track_invariants,
    "g2u.cue.v1": _check_cue_invariants,
    "g2u.observation_cue.v1": _check_observation_cue_invariants,
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def verify_event(payload: dict[str, Any]) -> None:
    """Raise G2UVerifyError if payload is invalid, unsafe, or unknown.

    Performs:
      1. Schema lookup by `schema` field.
      2. JSON Schema validation (if jsonschema is available).
      3. Forbidden-keyword scan (anti-weaponization).
      4. Per-schema invariants (covariance non-zero, expires_ts > ts_utc, ...).
      5. ts_source presence.
    """
    if not isinstance(payload, dict):
        raise G2UVerifyError("payload is not a dict")
    schema_id = payload.get("schema")
    if not schema_id:
        raise G2UVerifyError("missing schema field")
    schema = load_schema(schema_id)

    if _HAS_JSONSCHEMA:
        try:
            jsonschema.validate(instance=payload, schema=schema)
        except jsonschema.ValidationError as exc:
            raise G2UVerifyError(f"schema validation failed: {exc.message}") from exc

    if "ts_source" not in payload:
        raise G2UVerifyError("ts_source is required on every event")

    bad = _scan_forbidden(payload)
    if bad:
        raise G2UVerifyError(
            f"forbidden token '{bad}' present — G2U does not transmit weaponizing intent"
        )

    invariant = _INVARIANTS.get(schema_id)
    if invariant:
        invariant(payload)


# ---------------------------------------------------------------------------
# Canonical JSON for signing
# ---------------------------------------------------------------------------

def canonical_payload(payload: dict[str, Any]) -> bytes:
    """Sorted-keys, no-whitespace JSON for stable hashing/signing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------

def _hmac_sign(payload_bytes: bytes, key: bytes) -> str:
    """Fallback signing when Ed25519 is not installed. Uses HMAC-SHA256.

    Production deployments should install PyNaCl; this exists only so tests
    and dev environments work without an extra C extension.
    """
    return hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()


def _hmac_verify(payload_bytes: bytes, signature: str, key: bytes) -> bool:
    expected = _hmac_sign(payload_bytes, key)
    return hmac.compare_digest(expected, signature)


def sign_envelope(
    payload: dict[str, Any],
    *,
    node_id: str,
    key_id: str,
    secret_key: bytes,
) -> dict[str, Any]:
    """Produce a g2u.signed.v1 envelope around payload."""
    verify_event(payload)
    body = canonical_payload(payload)
    if key_id.startswith("hmac:"):
        sig = _hmac_sign(body, secret_key)
    else:
        # Try Ed25519 via PyNaCl first, then cryptography. Both use raw
        # 32-byte Ed25519 seeds and produce 64-byte signatures.
        try:
            from nacl.signing import SigningKey  # type: ignore
            sk = SigningKey(secret_key)
            sig_bytes = sk.sign(body).signature
            import base64
            sig = base64.urlsafe_b64encode(sig_bytes).decode("ascii").rstrip("=")
        except ImportError:
            try:
                from cryptography.hazmat.primitives.asymmetric import ed25519
                import base64
                sk = ed25519.Ed25519PrivateKey.from_private_bytes(secret_key)
                sig = base64.urlsafe_b64encode(sk.sign(body)).decode("ascii").rstrip("=")
            except ImportError as exc:
                raise G2UVerifyError(
                    "Ed25519 signing requires PyNaCl or cryptography; "
                    "use 'hmac:' key_id for dev only"
                ) from exc
    return {
        "schema": "g2u.signed.v1",
        "node_id": node_id,
        "key_id": key_id,
        "payload": payload,
        "signature": sig,
    }


def verify_envelope(envelope: dict[str, Any], *, public_key: bytes) -> dict[str, Any]:
    """Validate signed envelope; return inner payload on success."""
    if envelope.get("schema") != "g2u.signed.v1":
        raise G2UVerifyError("not a signed envelope")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise G2UVerifyError("envelope payload missing")
    body = canonical_payload(payload)
    sig = envelope.get("signature", "")
    key_id = envelope.get("key_id", "")
    if key_id.startswith("hmac:"):
        if not _hmac_verify(body, sig, public_key):
            raise G2UVerifyError("HMAC signature mismatch")
    else:
        try:
            from nacl.signing import VerifyKey
            import base64
            pad = "=" * (-len(sig) % 4)
            sig_bytes = base64.urlsafe_b64decode(sig + pad)
            VerifyKey(public_key).verify(body, sig_bytes)
        except ImportError:
            try:
                from cryptography.hazmat.primitives.asymmetric import ed25519
                import base64
                pad = "=" * (-len(sig) % 4)
                sig_bytes = base64.urlsafe_b64decode(sig + pad)
                ed25519.Ed25519PublicKey.from_public_bytes(public_key).verify(sig_bytes, body)
            except ImportError as exc:
                raise G2UVerifyError("Ed25519 verification requires PyNaCl or cryptography") from exc
            except Exception as exc:  # noqa: BLE001
                raise G2UVerifyError(f"Ed25519 verify failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 (PyNaCl raises BadSignatureError)
            raise G2UVerifyError(f"Ed25519 verify failed: {exc}") from exc
    verify_event(payload)
    return payload


# ---------------------------------------------------------------------------
# Publish helper (writes to JSONL journal — transport-agnostic)
# ---------------------------------------------------------------------------

def publish_event(
    payload: dict[str, Any],
    *,
    journal_dir: Path,
    node_id: str,
    key_id: str,
    secret_key: bytes,
    now: Optional[float] = None,
) -> dict[str, Any]:
    """Sign + journal a G2U event. Returns the signed envelope.

    JSONL journal layout: <journal_dir>/<YYYY-MM-DD>.jsonl
    """
    payload = dict(payload)
    payload.setdefault("event_id", uuid.uuid4().hex[:16])
    payload.setdefault("ts_utc", now if now is not None else time.time())
    payload.setdefault("ts_source", "monotonic")
    payload.setdefault("node_id", node_id)
    envelope = sign_envelope(payload, node_id=node_id, key_id=key_id, secret_key=secret_key)
    journal_dir.mkdir(parents=True, exist_ok=True)
    day = time.strftime("%Y-%m-%d", time.gmtime(payload["ts_utc"]))
    journal_path = journal_dir / f"{day}.jsonl"
    with journal_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n")
    return envelope


def replay_events(journal_dir: Path, since_ts: float = 0.0) -> Iterable[dict[str, Any]]:
    """Yield envelopes from JSONL journal in time order."""
    if not journal_dir.exists():
        return
    for path in sorted(journal_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    env = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = env.get("payload", {})
                if float(payload.get("ts_utc", 0)) >= since_ts:
                    yield env
