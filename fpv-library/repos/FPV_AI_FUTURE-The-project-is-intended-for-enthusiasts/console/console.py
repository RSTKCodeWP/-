"""Launch console + handoff verifier (Block-3 ground side).

HandoffVerifier is the INVERTED safety gate: default-deny, it only emits a verifier-passed
ArmingAuthorization when a signed handoff satisfies every condition (dual distinct trusted
signatures, unexpired, keypress in-window, and for KINETIC: non-synthetic-when-live + ROE pass).

LaunchConsole models the operator's side: the seeker-monitor lock (positive-ID), the ARM-key
(secondary authority) and FIRE button (primary commit), the ABORT mushroom, and the independent
HW-kill permit beacon. FIRE produces a verified authorization the onboard arming core consumes.
"""

from __future__ import annotations

from dataclasses import dataclass

from fpv_ai.betaflight_link.arming import ArmingAuthorization
from fpv_ai.betaflight_link.hwkill import HardwareKill
from fpv_ai.console.handoff import (
    EngagementOrder,
    SignedHandoff,
    TargetRef,
    canonical_order_bytes,
    sign_order,
    verify,
)
from fpv_ai.console.handoff import SCHEMA


def _denied_auth(order: EngagementOrder) -> ArmingAuthorization:
    """A default-deny authorization (verifier_passed=False) -- the arming core will not arm on it."""
    return ArmingAuthorization(
        verifier_passed=False, keypress_recorded=True,
        keypress_ts=order.keypress_ts, issued_at_s=order.issued_at_s, expires_at_s=order.expires_at_s,
        mission_goal=order.mission_goal, synthetic=order.synthetic,
    )


@dataclass(frozen=True)
class VerifierResult:
    accepted: bool
    authorization: ArmingAuthorization
    reason: str


class HandoffVerifier:
    def __init__(self, trusted_keys: set[bytes], *, allow_synthetic_bench: bool = False) -> None:
        self.trusted = set(trusted_keys)
        self.allow_synthetic_bench = allow_synthetic_bench

    def verify(self, signed: SignedHandoff, now: float) -> VerifierResult:
        order = signed.order
        body = canonical_order_bytes(order)

        def deny(reason: str) -> VerifierResult:
            return VerifierResult(False, _denied_auth(order), reason)

        if order.schema_version != SCHEMA:
            return deny("bad_schema")
        if not verify(signed.primary_pubkey, signed.primary_signature, body):
            return deny("primary_signature_invalid")
        if not verify(signed.secondary_pubkey, signed.secondary_signature, body):
            return deny("secondary_signature_invalid")
        if signed.primary_pubkey not in self.trusted:
            return deny("primary_key_untrusted")
        if signed.secondary_pubkey not in self.trusted:
            return deny("secondary_key_untrusted")
        if signed.primary_pubkey == signed.secondary_pubkey:
            return deny("not_dual_key")          # two DISTINCT authorities required
        if now >= order.expires_at_s:
            return deny("expired")
        if not (order.issued_at_s <= order.keypress_ts <= order.expires_at_s):
            return deny("keypress_out_of_window")
        if order.mission_goal == "KINETIC":
            if order.synthetic and not self.allow_synthetic_bench:
                return deny("synthetic_kinetic_blocked")
            if not order.roe_pass:
                return deny("roe_fail")

        auth = ArmingAuthorization(
            verifier_passed=True, keypress_recorded=True, keypress_ts=order.keypress_ts,
            issued_at_s=order.issued_at_s, expires_at_s=order.expires_at_s,
            mission_goal=order.mission_goal, synthetic=order.synthetic,
        )
        return VerifierResult(True, auth, "accepted")


@dataclass(frozen=True)
class ConsoleConfig:
    mission_goal: str = "RECON"        # RECON | CONTACT | KINETIC
    ttl_s: float = 90.0                # authorization lifetime
    synthetic: bool = True             # exhibition/demo default; live KINETIC must set False
    roe_pass: bool = True


class LaunchConsole:
    """The operator's ground console. Produces a verified ArmingAuthorization on FIRE."""

    def __init__(self, *, verifier: HandoffVerifier,
                 primary_key, primary_pub: bytes, secondary_key, secondary_pub: bytes,
                 hwkill: HardwareKill | None = None, config: ConsoleConfig | None = None) -> None:
        self.verifier = verifier
        self._pk, self._pk_pub = primary_key, primary_pub
        self._sk, self._sk_pub = secondary_key, secondary_pub
        self.hwkill = hwkill
        self.cfg = config or ConsoleConfig()
        self._lock: TargetRef | None = None
        self._arm_key_in = False
        self._aborted = False
        self._counter = 0

    # operator inputs --------------------------------------------------------------------
    def update_seeker(self, *, locked: bool, track_id: str = "trk-1",
                      classification: str = "hostile_uav", confidence: float = 1.0) -> None:
        """What the operator sees on the seeker monitor (the positive-ID source)."""
        self._lock = TargetRef(track_id, classification, confidence) if locked else None

    def insert_arm_key(self) -> None:
        self._arm_key_in = True            # the secondary authority's physical key-switch

    def remove_arm_key(self) -> None:
        self._arm_key_in = False

    def abort(self, reason: str = "operator_abort") -> None:
        """The ABORT mushroom: stop permitting power and drive the independent HW-kill."""
        self._aborted = True
        if self.hwkill is not None:
            self.hwkill.operator_kill(reason)

    def permit_beacon(self, now: float) -> None:
        """Emit the HW-kill permit beacon while the engagement is live (not aborted)."""
        if not self._aborted and self.hwkill is not None:
            self.hwkill.permit_beacon(now)

    def press_fire(self, now: float) -> tuple[ArmingAuthorization | None, str]:
        """The primary FIRE commit. Requires the ARM key (secondary) + a positive-ID lock.
        Builds, dual-signs and verifies the handoff; returns the verified authorization or None."""
        if self._aborted:
            return None, "aborted"
        if not self._arm_key_in:
            return None, "no_arm_key"
        if self._lock is None:
            return None, "no_positive_id"
        self._counter += 1
        order = EngagementOrder(
            handoff_id=f"hk-{self._counter}", schema_version=SCHEMA,
            issued_at_s=now, expires_at_s=now + self.cfg.ttl_s,
            mission_goal=self.cfg.mission_goal, target=self._lock,
            keypress_ts=now, roe_pass=self.cfg.roe_pass, synthetic=self.cfg.synthetic,
        )
        signed = sign_order(order, primary_key=self._pk, primary_pub=self._pk_pub,
                            secondary_key=self._sk, secondary_pub=self._sk_pub)
        result = self.verifier.verify(signed, now)
        return (result.authorization if result.accepted else None), result.reason
