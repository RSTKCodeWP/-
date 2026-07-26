"""``engagement_handoff.v1`` — the formal operator -> interceptor commit hand-off (audit gap, now closed).

The audit found the operator->fpv boundary was covered only by the outbound (sense-only) contracts; the
KINETIC hand-off had NO schema on disk, so "kinetic is blocked" rested on prose.  This is that schema: the
versioned, auditable record that carries the operator's commit to the seeker for a specific engagement and
that the kinetic branch is gated on.

WHAT IT BINDS
-------------
  * ``authorization_id`` / ``authorization_hash`` — the exact confirmed operator authorization (the dual
    Ed25519 ``operator_commit`` verified by ``fpv_ai.betaflight_link.authorization.verify_operator_commit``).
  * ``mission_task`` — RECON / CONTACT / KILL.  Only KILL can ever permit kinetics.
  * ``target_reference_hash`` — binds the immutable ``TargetReference`` frozen at commit
    (``fpv_ai.betaflight_link.mission_fsm``), so the seeker provably prosecutes the target the operator
    confirmed on the monitor (Axis III — target fidelity).
  * ``kill_box`` — the geo keep-out the intercept must stay inside (CIVCAS hard invariant).
  * validity window + explicit ``abort_conditions``.

THE GATE (allow-on-authorization; verifier.py is NOT inverted)
--------------------------------------------------------------
``kinetic_permitted`` returns True ONLY for a KILL hand-off that references a VALID, UNEXPIRED authorization,
carries a bound target reference and a kill-box, and asserts the target is a CONFIRMED non-responsive threat.
Everything else -> default-DENY.  This is the allow-on-authorization gate; the ground sense-only anti-weapon
verifier (``fpv/safety/verifier.py``) stays as-is (see its REFRAME_NOTES / authorization.py rationale).
"""

from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA_ENGAGEMENT_HANDOFF = "engagement_handoff.v1"


class MissionTask(str, enum.Enum):
    RECON = "recon"       # observe/collect only -- never kinetic
    CONTACT = "contact"   # close/identify/IFF -- never kinetic
    KILL = "kill"         # kinetic intercept -- the ONLY task that can permit kinetics


DEFAULT_ABORT_CONDITIONS = (
    "geo_keepout_breach",       # intercept would leave the kill-box (CIVCAS)
    "alt_keepout_breach",
    "ttl_exceeded",
    "guidance_roe_abort",
    "target_lost",
    "link_loss_pre_commit",     # link loss aborts ONLY before the terminal fire-and-forget commit
)


@dataclass(frozen=True)
class EngagementHandoff:
    handoff_id: str
    authorization_id: str
    authorization_hash: str                 # canonical hash of the exact confirmed authorization
    mission_task: str                       # MissionTask value
    target_reference_hash: str              # binds the immutable TargetReference (Axis III)
    target_track_id: str = ""
    kill_box: dict[str, Any] | None = None  # geo/alt keep-out for the intercept (CIVCAS)
    issued_at_utc: str = ""
    expires_at_utc: str = ""
    target_confirmed_nonresponsive: bool = False
    abort_conditions: tuple = DEFAULT_ABORT_CONDITIONS
    schema_version: str = SCHEMA_ENGAGEMENT_HANDOFF

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["abort_conditions"] = list(self.abort_conditions)
        d["kill_box"] = self.kill_box or {}
        return d


def _expired(expires_at_utc: str, now_utc: str) -> bool:
    """True if the hand-off is expired (or has no/parse-failing window -> treated as expired = fail-safe)."""
    try:
        exp = datetime.fromisoformat(expires_at_utc.replace("Z", "+00:00"))
        now = datetime.fromisoformat(now_utc.replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now >= exp
    except (ValueError, AttributeError):
        return True


def kinetic_permitted(handoff: EngagementHandoff, *, now_utc: str,
                      authorization_valid: bool) -> tuple[bool, str]:
    """The allow-on-authorization kinetic gate.  True ONLY for a fully-authorised, bound, unexpired KILL.

    ``authorization_valid`` is the result of verifying the referenced dual-Ed25519 operator commit upstream
    (``verify_operator_commit``); this function does not re-verify signatures, it enforces the hand-off
    invariants around them.  Any failure -> default-DENY.
    """
    if handoff.mission_task != MissionTask.KILL.value:
        return False, f"task '{handoff.mission_task}' is sense-only -> no kinetic (default-deny)"
    if not authorization_valid:
        return False, "referenced operator authorization is not valid (default-deny)"
    if not handoff.authorization_hash:
        return False, "no authorization binding hash (default-deny)"
    if not handoff.target_reference_hash:
        return False, "no target reference bound (Axis III target fidelity) -> default-deny"
    if not handoff.target_confirmed_nonresponsive:
        return False, "target not confirmed as a non-responsive threat -> default-deny"
    if not handoff.kill_box:
        return False, "no kill-box (CIVCAS geo keep-out) defined -> default-deny"
    if _expired(handoff.expires_at_utc, now_utc):
        return False, "engagement hand-off expired -> default-deny"
    return True, "kinetic permitted: valid KILL hand-off, confirmed threat, bound reference, inside kill-box"


def build_kill_handoff(*, handoff_id: str, authorization_id: str, authorization_hash: str,
                       target_reference_hash: str, kill_box: dict[str, Any], issued_at_utc: str,
                       expires_at_utc: str, target_track_id: str = "",
                       target_confirmed_nonresponsive: bool = True) -> EngagementHandoff:
    """Construct a KILL hand-off from a confirmed authorization + the immutable target reference hash.

    ``target_reference_hash`` is ``TargetReference.reference_hash`` from the mission supervisor's commit --
    so the flying seeker is bound to the exact target the operator confirmed.
    """
    return EngagementHandoff(
        handoff_id=handoff_id, authorization_id=authorization_id, authorization_hash=authorization_hash,
        mission_task=MissionTask.KILL.value, target_reference_hash=target_reference_hash,
        target_track_id=target_track_id, kill_box=dict(kill_box), issued_at_utc=issued_at_utc,
        expires_at_utc=expires_at_utc, target_confirmed_nonresponsive=target_confirmed_nonresponsive)
