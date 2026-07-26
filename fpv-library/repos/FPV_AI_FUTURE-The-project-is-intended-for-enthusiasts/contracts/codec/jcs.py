"""Small RFC-8785-like canonical JSON helper.

The repository keeps this dependency-light for smoke tests. It provides stable
UTF-8, sorted-key, no-whitespace JSON suitable for local digests. Production
cross-implementation JCS conformance remains a future hardening item.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_json_bytes(payload: Any) -> bytes:
    return canonical_json(payload).encode("utf-8")


def sha256_hex(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
