"""Frame-gating — decide which frames feed the fused localization estimate (Task 3.3).

DESIGN.md lines 151-152: hard-gate bad-geometry / high-angular-rate / |accel|≠1g frames
OUT of the fused estimate, while STILL surfacing those detections as CUE-ONLY contacts.
The gate produces a per-frame *verdict*; it NEVER suppresses a detection from visibility
(Confirmation owns display priority, not the gate) — it only marks whether the frame's
ground points are clean enough to average into a fused coordinate.

**The verdict is three-valued on purpose.** "I have no evidence of badness" (the .srt
replay path has no IMU and no attitude) is a different epistemic state from "I verified
the geometry is good." A boolean would force a lie: either fuse unverifiable frames as if
good, or black out the entire replay-validation path so Phase 4 has nothing to fuse. So
absent signals yield PASS_UNVERIFIED (still fusable, but downstream inflates its radius),
and only an evaluated-and-bad signal yields REJECT.

This module knows nothing about `Pose` — the Projector (Task 3.5) computes a `GateInput`
from `Pose` + the fixed O4 mount angle and hands it here. That keeps the cross-process
telemetry contract clean and the gate trivially unit-testable from hand-built inputs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

# --- thresholds -------------------------------------------------------------
# Only the oblique-pitch cutoff is principled: ground-error sensitivity to heading and
# altitude grows ~1/cos² of the nadir angle, and the bottom-center prone bias (DESIGN
# §3.1) blows up at high obliquity, so past ~65° from nadir a frame is geometry-toxic to
# fusion. The two IMU thresholds are placeholders to tune against real FC logs (the .srt
# replay path never exercises them — they are live-CRSF-path signals). The vibration
# criterion is deliberately NOT implemented in v1: it is always absent, has no defined
# metric, and no data to tune against — a field that is always `na` and never principled
# is dead weight. `GateInput.vibration_metric` is reserved (always None in v1) so the
# struct stays stable when the live path adds it.
OBLIQUE_PITCH_CUTOFF_DEG = 65.0  # principled: degrees from nadir (0 = straight down)
MAX_ANGULAR_RATE_DPS = 40.0  # placeholder: |gyro| above this smears the frame
ACCEL_BAND_G = 0.3  # placeholder: reject if |accel| is outside 1g ± this


class GateVerdict(str, Enum):
    """Three-valued gate outcome (str-Enum so it serializes cleanly downstream)."""

    PASS = "PASS"  # every existing signal was evaluated and passed
    PASS_UNVERIFIED = "PASS_UNVERIFIED"  # nothing bad, but ≥1 signal absent
    REJECT = "REJECT"  # ≥1 signal evaluated AND over threshold


@dataclass(frozen=True)
class GateInput:
    """Per-frame signals the gate evaluates. Every field Optional: None means the source
    could not supply it (NOT zero, NOT good). Built by the Projector from Pose + mount."""

    camera_pitch_deg: float | None  # degrees FROM NADIR (0 = straight down)
    angular_rate_dps: float | None  # |gyro| magnitude, deg/s (FC IMU; None on .srt)
    accel_magnitude_g: float | None  # |accel| in g (FC IMU; None on .srt)
    vibration_metric: float | None = None  # reserved; always None in v1 (criterion unimpl.)


@dataclass(frozen=True)
class GateResult:
    """The gate's verdict + human-readable reasons (for the CUE-ONLY label / radius)."""

    verdict: GateVerdict
    reasons: tuple[str, ...]  # rejection causes, or absent-signal names; () for clean PASS

    @property
    def fusable(self) -> bool:
        """Whether the frame's ground points may enter the fused estimate.

        PASS and PASS_UNVERIFIED are both fusable (the latter with an inflated radius set
        downstream); only REJECT is excluded. Centralised here so every caller agrees.
        """
        return self.verdict is not GateVerdict.REJECT


def evaluate(gi: GateInput) -> GateResult:
    """Evaluate one frame. See the module docstring for the three-valued policy.

    Per-criterion outcome is pass / reject / na (na only when the input is None). Any
    reject ⇒ REJECT (evaluated-and-bad always wins, so a live mid-maneuver frame is
    rejected even when other signals are absent). Otherwise, any na ⇒ PASS_UNVERIFIED;
    all-present-and-pass ⇒ PASS.
    """
    reject_reasons: list[str] = []
    absent: list[str] = []

    # A NaN/inf signal must NOT pass silently: every comparison with NaN is False, so
    # `nan > cutoff` is False and a naive check would call a NaN-geometry frame a clean
    # PASS (bad geometry into fusion). Treat a non-finite signal as ABSENT (untrustworthy,
    # can't confirm good) → PASS_UNVERIFIED, never PASS.
    pitch = _finite_or_none(gi.camera_pitch_deg)
    rate = _finite_or_none(gi.angular_rate_dps)
    accel = _finite_or_none(gi.accel_magnitude_g)

    # Oblique geometry (the one principled criterion).
    if pitch is None:
        absent.append("pitch_absent")
    elif pitch > OBLIQUE_PITCH_CUTOFF_DEG:
        reject_reasons.append(
            f"oblique: pitch={pitch:.0f}°>{OBLIQUE_PITCH_CUTOFF_DEG:.0f}° from nadir"
        )

    # High angular rate → motion blur / rolling-shutter smear.
    if rate is None:
        absent.append("angular_rate_absent")
    elif rate > MAX_ANGULAR_RATE_DPS:
        reject_reasons.append(
            f"high angular rate: {rate:.0f}°/s>{MAX_ANGULAR_RATE_DPS:.0f}°/s"
        )

    # |accel| ≠ 1g → aggressive maneuver violating the quasi-static pose assumption.
    if accel is None:
        absent.append("accel_absent")
    elif abs(accel - 1.0) > ACCEL_BAND_G:
        reject_reasons.append(
            f"accel off 1g: {accel:.2f}g (band ±{ACCEL_BAND_G:.2f}g)"
        )

    if reject_reasons:
        return GateResult(GateVerdict.REJECT, tuple(reject_reasons))
    if absent:
        return GateResult(GateVerdict.PASS_UNVERIFIED, tuple(absent))
    return GateResult(GateVerdict.PASS, ())


def _finite_or_none(v: float | None) -> float | None:
    """A non-finite (NaN/inf) signal is untrustworthy → treat it as absent, not as data."""
    if v is None or not math.isfinite(v):
        return None
    return v
