"""Operator-commit crypto verification + the engage-permission runtime gate (Block-3 S4 safety)."""
from nacl.signing import SigningKey

from fpv_ai.betaflight_link.arming import (ArmingConfig, ArmingOutput, ArmingStateMachine, ArmState)
from fpv_ai.betaflight_link.authorization import sign_commit, verify_operator_commit
from fpv_ai.betaflight_link.failsafe import FailsafeController
from fpv_ai.betaflight_link.hwkill import HardwareKill
from fpv_ai.betaflight_link.onboard_runtime import OnboardRuntime


def _keypair():
    sk = SigningKey.generate()
    return bytes(sk), bytes(sk.verify_key)


def _payload(now, nonce="n1"):
    return dict(keypress_recorded=True, keypress_ts=now, issued_at_s=now, expires_at_s=now + 60,
                mission_goal="KINETIC", synthetic=False, nonce=nonce, target_track_ref="trk-7")


# ── crypto verifier (B) ───────────────────────────────────────────────────────
def test_valid_dual_signature_passes():
    (a, ap), (b, bp) = _keypair(), _keypair()
    v = verify_operator_commit(sign_commit(_payload(1000.0), [a, b]), [ap, bp], min_signatures=2)
    assert v.authorization.verifier_passed and v.valid_signers == 2
    assert v.authorization.mission_goal == "KINETIC" and v.authorization.synthetic is False


def test_single_signature_denied():
    (a, ap), (b, bp) = _keypair(), _keypair()
    v = verify_operator_commit(sign_commit(_payload(1000.0), [a]), [ap, bp], min_signatures=2)
    assert not v.authorization.verifier_passed and "insufficient" in v.reason


def test_tampered_payload_denied():
    (a, ap), (b, bp) = _keypair(), _keypair()
    env = sign_commit(_payload(1000.0), [a, b])
    env["payload"]["mission_goal"] = "RECON"                 # tamper AFTER signing
    assert not verify_operator_commit(env, [ap, bp]).authorization.verifier_passed


def test_unauthorized_key_denied():
    (a, _ap), (b, _bp) = _keypair(), _keypair()
    (_c, cp) = _keypair()                                    # a key NOT in the authorized set
    env = sign_commit(_payload(1000.0), [a, b])
    assert not verify_operator_commit(env, [cp], min_signatures=2).authorization.verifier_passed


def test_replay_nonce_denied():
    (a, ap), (b, bp) = _keypair(), _keypair()
    env = sign_commit(_payload(1000.0), [a, b])
    seen = set()
    assert verify_operator_commit(env, [ap, bp], seen_nonces=seen).authorization.verifier_passed
    assert not verify_operator_commit(env, [ap, bp], seen_nonces=seen).authorization.verifier_passed


def test_verified_commit_arms_but_denied_does_not():
    (a, ap), (b, bp) = _keypair(), _keypair()
    now = 1000.0
    good = verify_operator_commit(sign_commit(_payload(now), [a, b]), [ap, bp]).authorization
    m = ArmingStateMachine(ArmingConfig(ramp_s=0.01))
    m.authorize(good); m.tick(now); m.tick(now)             # SAFE->PREARM->ARMED_IDLE
    assert m.is_armed                                        # real dual-signed commit arms

    bad = verify_operator_commit(sign_commit(_payload(now), [a]), [ap, bp]).authorization
    m2 = ArmingStateMachine(ArmingConfig(ramp_s=0.01))
    m2.authorize(bad); m2.tick(now); m2.tick(now)
    assert not m2.is_armed                                   # single-signature commit is default-denied


# ── engage-permission runtime gate (A) ────────────────────────────────────────
class _SpyArm:
    def __init__(self):
        self.cmds = []

    @property
    def is_armed(self):
        return False

    def authorize(self, auth):
        pass

    def abort(self, reason):
        pass

    def tick(self, now, cmd=None):
        self.cmds.append(cmd)
        rc = {"roll": 1500, "pitch": 1500, "yaw": 1500, "throttle": 1000,
              "aux1": 1000, "aux2": 1000, "aux3": 1000, "aux4": 1000}
        return ArmingOutput(ArmState.SAFE, rc, armed=False, reason="spy")


class _FakeLink:
    def poll(self):
        return []

    def send_set_raw_rc(self, ch):
        self.sent = ch


class _Cmd:
    roll_cmd = 0.5
    pitch_cmd = 0.0
    yaw_rate_cmd = 0.0
    throttle_cmd = 0.5


def test_engage_permitted_gate_suppresses_command():
    rt = OnboardRuntime(link=_FakeLink(), arming=_SpyArm(),
                        failsafe=FailsafeController(), hwkill=HardwareKill())
    rt.step(1.0, guidance_command=_Cmd(), engage_permitted=False)   # firewall: withhold
    rt.step(2.0, guidance_command=_Cmd(), engage_permitted=True)    # permitted: apply
    assert rt.arming.cmds[0] is None                                # command suppressed (hold)
    assert rt.arming.cmds[1] is not None                            # command applied
