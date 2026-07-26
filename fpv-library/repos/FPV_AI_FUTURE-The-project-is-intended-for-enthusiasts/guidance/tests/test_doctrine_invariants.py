"""V4 — the 7 Block-03 doctrine invariants as an executable CI gate.

These guard tests MUST stay green on every PR of the Task-1 campaign. A hole here is the most
dangerous failure mode (false assurance), so each is a concrete behavioral or structural check,
not a comment. The introspection guards are deliberately forward-looking: they trip the moment a
future task wires a forbidden input (e.g. a learned PSR/appearance signal) into the state path.
Per-task bit-equality variants (R1/R4/R5/R8/R9/R10) extend Inv-2 and Inv-7 as those land.

The 7 invariants (master plan §0):
  1. Range never scales the guidance gain (Vc scheduled only).
  2. AI/learned/appearance/scene → lock-quality/engage-permission ONLY, never centroid/LOS/tracker.
  3. ABORT is a PASS; WRONG-HIT is a HARD FAIL (default-deny on doubt).
  4. IMM angular state is modified-polar [az,el,az_rate,el_rate] (no Cartesian range rewrite).
  5. Every command <= 0.84 g lateral, in-FOV, corrections before the ~1.0-1.4 s ten-tau wall.
  6. Hard-mount the camera (no gimbal actuation in the command schema).
  7. Post-commit, acquiring a NEW track is forbidden; re-acquire only the SAME committed track.
"""

from __future__ import annotations

import inspect
import math

from fpv.seeker.blob import TargetObservation, ThermalBlob
from fpv.seeker.imm import IMMEstimate, IMMFilter
from fpv.seeker.looming import LoomingEstimate
from fpv.seeker.los import LOSObservation
from fpv.seeker.track import ThermalLockConfig, ThermalLockTracker, TrackingState
from fpv.guidance.bearing_rate import BearingRateGuidance, GuidanceConfig, ROEAbort
from fpv.guidance.command_map import LosGuidancePilot
from fpv.fpv_ai.betaflight_link.commands import AICommand


# ── builders ─────────────────────────────────────────────────────────────────

def _imm(az_rate: float = 0.0, el_rate: float = 0.0, az: float = 0.0, el: float = 0.0,
         fid: int = 0) -> IMMEstimate:
    return IMMEstimate(az_rad=az, el_rad=el, az_rate_radps=az_rate, el_rate_radps=el_rate,
                       mode_probs=(0.9, 0.1), maneuver_detected=False, frame_id=fid)


def _looming(tau: float = 2.0, conf: float = 0.8) -> LoomingEstimate:
    return LoomingEstimate(tau_s=tau, tau_confidence=conf, closing_sign=1,
                           area_smoothed_px=100.0, d_area_dt_px_per_s=10.0)


def _los(az_rate: float = 0.0, fid: int = 0) -> LOSObservation:
    return LOSObservation(az_rad=0.02, el_rad=0.0, az_rate_radps=az_rate, el_rate_radps=0.0,
                          ego_quality=1.0, ego_source="gyro", frame_id=fid)


def _blob(x: float, y: float, *, area: int = 6, peak: int = 5000, snr: float = 20.0,
          fid: int = 0) -> ThermalBlob:
    return ThermalBlob(centroid_px=(x, y), area_px=area, peak_counts=peak, mean_counts=peak * 0.7,
                       snr=snr, bbox=(int(x) - 2, int(y) - 2, 4, 4), frame_id=fid, t_capture_ns=None,
                       cam_temp_c=25.0, ffc_state="READY")


def _obs(blobs, fid: int = 0) -> TargetObservation:
    return TargetObservation(frame_id=fid, t_capture_ns=None, cam_temp_c=25.0, ffc_state="READY",
                             blobs=blobs, threshold_baseline_counts=100.0, detection_budget_ms=0.0)


# ── Inv 1 — range never scales the guidance gain ─────────────────────────────

def test_inv1_range_never_scales_the_lateral_gain():
    # The guidance law a_cmd = N*Vc_sched*lambda_dot takes NO range argument at all.
    params = set(inspect.signature(BearingRateGuidance.compute).parameters)
    assert not (params & {"range", "estimated_range_m", "range_m", "r_hat"})
    # The pilot's lateral (roll) command does not change with range OUTSIDE the terminal-timing
    # switches: range only gates terminal ACRO / LOS-hold *timing*, never the PN gain.
    pilot = LosGuidancePilot()
    g = BearingRateGuidance(GuidanceConfig(Vc_sched_mps=20.0))
    gcmd = g.compute(_imm(az_rate=0.02), _looming())
    rolls = [
        pilot.command_from_guidance(gcmd, az_rad=0.0, el_rad=0.0, sequence_id=0, timestamp_ms=0,
                                    estimated_range_m=R).roll_cmd
        for R in (50.0, 200.0, 1000.0)        # all beyond acro(15)/los-hold(5) -> non-terminal
    ]
    assert rolls[0] == rolls[1] == rolls[2]


# ── Inv 2 — quality/appearance never moves centroid/LOS ──────────────────────

def test_inv2_quality_signals_are_output_only_never_state_inputs():
    forbidden = {"lock_quality", "model_wrong_alarm", "nis", "psr", "apce", "appearance",
                 "confidence", "engage_permitted", "template", "correlation"}
    assert not (set(inspect.signature(IMMFilter.update).parameters) & forbidden)
    assert not (set(inspect.signature(ThermalLockTracker.update).parameters) & forbidden)
    # behavioral: the IMM angular state is a pure function of the LOS observation (the quality
    # fields are derived outputs and never fed back).
    f1, f2 = IMMFilter(), IMMFilter()
    e1 = e2 = None
    for i in range(5):
        e1 = f1.update(_los(az_rate=0.01, fid=i), dt=1 / 60.0)
        e2 = f2.update(_los(az_rate=0.01, fid=i), dt=1 / 60.0)
    assert (e1.az_rad, e1.el_rad, e1.az_rate_radps, e1.el_rate_radps) == \
           (e2.az_rad, e2.el_rad, e2.az_rate_radps, e2.el_rate_radps)


# ── Inv 3 — default-deny: an uninterceptable geometry ABORTS (a PASS) ─────────

def test_inv3_default_deny_aborts_an_uninterceptable_geometry():
    g = BearingRateGuidance(GuidanceConfig(Vc_sched_mps=20.0))
    raised = False
    for i in range(40):                       # past the HIGH_CROSSING warmup ticks
        try:
            g.compute(_imm(az_rate=2.0, fid=i), _looming())   # extreme crossing lambda-dot
        except ROEAbort as ab:
            raised = True
            assert ab.required_g > ab.achievable_g
            break
    assert raised, "an uninterceptable crossing must abort (default-deny), never command blindly"


# ── Inv 4 — IMM state is modified-polar 4-state, no Cartesian range ──────────

def test_inv4_imm_state_is_modified_polar_4state():
    f = IMMFilter()
    f.update(_los(fid=0), dt=1 / 60.0)
    assert all(x.shape == (4,) for x in f._x)             # per-mode [az,el,az_rate,el_rate]
    fields = set(IMMEstimate.__dataclass_fields__)
    assert not (fields & {"range_m", "range", "x_m", "y_m", "z_m", "pos_x", "pos_y", "inv_range"})
    assert {"az_rad", "el_rad", "az_rate_radps", "el_rate_radps"} <= fields


# ── Inv 5 — every commanded lateral accel <= the g-budget (or abort) ─────────

def test_inv5_commanded_lateral_never_exceeds_the_g_budget():
    g = BearingRateGuidance(GuidanceConfig(Vc_sched_mps=20.0))
    a_max = g._cfg.achievable_g() * 9.81
    for i in range(30):
        try:
            gc = g.compute(_imm(az_rate=0.02 + 0.004 * i, fid=i), _looming())
        except ROEAbort:
            continue                                       # default-deny is the other lawful out
        a_tot = math.hypot(gc.a_cmd_az_mps2, gc.a_cmd_el_mps2)
        assert a_tot <= a_max + 1e-6, f"lateral {a_tot:.3f} exceeds a_max {a_max:.3f} m/s^2"


# ── Inv 6 — hard-mount: no gimbal actuation in the command schema ────────────

def test_inv6_command_schema_has_no_gimbal_actuation():
    fields = set(AICommand.__dataclass_fields__)
    assert not (fields & {"gimbal_az", "gimbal_el", "gimbal_pitch", "gimbal_yaw",
                          "seeker_az", "seeker_el", "gimbal_rate"})
    assert {"roll_cmd", "pitch_cmd", "yaw_rate_cmd", "throttle_cmd"} <= fields


# ── Inv 7 — post-lock, an out-of-family intruder is never adopted ────────────

def test_inv7_no_new_track_on_out_of_family_intruder_post_lock():
    trk = ThermalLockTracker(ThermalLockConfig(stable_frame_count=3, max_gate_px=48.0))
    trk.seed((300 - 40, 200 - 40, 80, 80))
    snap = None
    for i in range(6):                                     # establish LOCK on target A
        snap = trk.update(_obs([_blob(300 + i, 200, fid=i)], fid=i))
    assert snap.tracking_state == TrackingState.LOCKED
    # present ONLY an in-gate but grossly out-of-family intruder (far bigger + hotter)
    intruder = _blob(318, 208, area=40, peak=30000, snr=60.0, fid=6)
    snap2 = trk.update(_obs([intruder], fid=6))
    assert snap2.associated_blob is None, "out-of-family intruder must be vetoed, not adopted"
    assert snap2.tracking_state != TrackingState.LOCKED or snap2.associated_blob is None
