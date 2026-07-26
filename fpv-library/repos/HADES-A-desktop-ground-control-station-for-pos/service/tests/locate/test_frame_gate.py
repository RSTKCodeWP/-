"""Tests for frame-gating (Task 3.3).

Frame-gating produces a per-frame VERDICT (DESIGN.md lines 151-152): hard-gate bad
geometry / high angular-rate / |accel|≠1g frames OUT of the fused localization estimate,
while STILL surfacing those detections as CUE-ONLY contacts. It never suppresses a
detection from being visible — it only excludes the frame's ground points from fusion.

The verdict is three-valued, not boolean, because "I have no evidence of badness"
(absent IMU on the .srt replay path) is a different epistemic state from "I verified the
geometry is good." Collapsing them would force a lie: either fuse unverifiable frames as
if good, or black out the entire replay-validation path. So:

  PASS             — every signal that EXISTS was evaluated and passed.
  PASS_UNVERIFIED  — nothing rejected, but ≥1 signal was absent (can't confirm good).
  REJECT           — ≥1 signal was evaluated AND violated its threshold.

A criterion that can't be evaluated (None input) NEVER rejects; only an evaluated-and-bad
criterion rejects. PASS_UNVERIFIED is still fusable (downstream inflates its radius).
"""

from __future__ import annotations

from hades.locate.frame_gate import (
    OBLIQUE_PITCH_CUTOFF_DEG,
    GateInput,
    GateResult,
    GateVerdict,
    evaluate,
)


def _good() -> GateInput:
    """A clean, fully-observed near-nadir frame in steady flight."""
    return GateInput(
        camera_pitch_deg=10.0,  # 10° from nadir — near-nadir, good geometry
        angular_rate_dps=5.0,  # gentle
        accel_magnitude_g=1.0,  # steady (1g)
        vibration_metric=None,  # v1 never ships the vibration criterion
    )


# --- good geometry passes ---------------------------------------------------


def test_good_frame_passes():
    res = evaluate(_good())
    assert res.verdict is GateVerdict.PASS
    assert res.fusable is True
    assert res.reasons == ()


# --- each bad criterion rejects (evaluated-and-bad) -------------------------


def test_oblique_frame_rejected():
    g = GateInput(
        camera_pitch_deg=72.0,  # 72° from nadir — past the 65° oblique cutoff
        angular_rate_dps=5.0,
        accel_magnitude_g=1.0,
        vibration_metric=None,
    )
    res = evaluate(g)
    assert res.verdict is GateVerdict.REJECT
    assert res.fusable is False
    assert any("oblique" in r or "pitch" in r for r in res.reasons)


def test_high_angular_rate_rejected():
    g = GateInput(
        camera_pitch_deg=10.0,
        angular_rate_dps=80.0,  # past the 40°/s cutoff — motion blur
        accel_magnitude_g=1.0,
        vibration_metric=None,
    )
    res = evaluate(g)
    assert res.verdict is GateVerdict.REJECT
    assert any("rate" in r for r in res.reasons)


def test_accel_off_1g_rejected():
    g = GateInput(
        camera_pitch_deg=10.0,
        angular_rate_dps=5.0,
        accel_magnitude_g=1.6,  # |accel| far from 1g — aggressive maneuver
        vibration_metric=None,
    )
    res = evaluate(g)
    assert res.verdict is GateVerdict.REJECT
    assert any("accel" in r for r in res.reasons)


def test_evaluated_bad_wins_over_absent_signals():
    # A frame caught mid-maneuver on the live path is REJECTED even though other signals
    # are absent — evaluated-and-bad always beats absent (the live-maneuver guard).
    g = GateInput(
        camera_pitch_deg=None,  # absent
        angular_rate_dps=90.0,  # evaluated AND bad
        accel_magnitude_g=None,  # absent
        vibration_metric=None,
    )
    res = evaluate(g)
    assert res.verdict is GateVerdict.REJECT


# --- absent signals → PASS_UNVERIFIED, never REJECT -------------------------


def test_srt_replay_frame_all_absent_is_pass_unverified():
    # The DJI .srt replay path: attitude is None, no IMU at all. Nothing can be evaluated,
    # so the gate cannot reject — but it also cannot confirm good. PASS_UNVERIFIED keeps
    # the replay-validation path fusable (downstream inflates the radius) without lying.
    g = GateInput(
        camera_pitch_deg=None,
        angular_rate_dps=None,
        accel_magnitude_g=None,
        vibration_metric=None,
    )
    res = evaluate(g)
    assert res.verdict is GateVerdict.PASS_UNVERIFIED
    assert res.fusable is True  # still fusable — not blacked out
    assert any("absent" in r for r in res.reasons)


def test_partial_absent_but_present_pass_is_unverified():
    # Pitch present and good, but IMU absent → not a clean PASS (can't verify dynamics),
    # not a REJECT (nothing was bad). PASS_UNVERIFIED.
    g = GateInput(
        camera_pitch_deg=10.0,  # good geometry, evaluable
        angular_rate_dps=None,  # absent
        accel_magnitude_g=None,  # absent
        vibration_metric=None,
    )
    res = evaluate(g)
    assert res.verdict is GateVerdict.PASS_UNVERIFIED
    assert res.fusable is True


# --- threshold boundary + contract -----------------------------------------


def test_oblique_cutoff_is_exposed_and_principled():
    # The oblique pitch cutoff is the one principled threshold (geometry: ground-error
    # sensitivity grows ~1/cos² of nadir angle). Exposed so callers/docs can cite it.
    assert OBLIQUE_PITCH_CUTOFF_DEG == 65.0


def test_nan_gate_input_does_not_silently_pass():
    # Codex P1 (frame_gate:91): a NaN signal must not PASS by accident (every NaN
    # comparison is False, so `nan > cutoff` is False → looks fine). A NaN is an absent /
    # untrustworthy signal, so it must downgrade to PASS_UNVERIFIED (or REJECT), never a
    # clean PASS that lets bad geometry into fusion.
    g = GateInput(
        camera_pitch_deg=float("nan"),
        angular_rate_dps=5.0,
        accel_magnitude_g=1.0,
        vibration_metric=None,
    )
    res = evaluate(g)
    assert res.verdict is not GateVerdict.PASS  # not a clean pass on a NaN geometry signal


def test_gate_result_fusable_property():
    assert GateResult(GateVerdict.PASS, ()).fusable is True
    assert GateResult(GateVerdict.PASS_UNVERIFIED, ("imu_absent",)).fusable is True
    assert GateResult(GateVerdict.REJECT, ("oblique",)).fusable is False
