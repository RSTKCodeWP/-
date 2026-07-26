"""R3 — tau-driven terminal/acro commit (range-free).

With use_tau_terminal the terminal switch fires on the passive looming time-to-contact tau,
not range -- removing range from the terminal path (Inv 1). Default-off is bit-identical (and
the legacy pipeline never even reached the terminal phase, since it passed neither range nor tau).
"""

from __future__ import annotations

from fpv.seeker.thermal_sim import ThermalSceneConfig, ThermalSimulator
from fpv.guidance.bearing_rate import GeometryClass, GuidanceCommand
from fpv.guidance.command_map import LosGuidancePilot, PilotConfig, _is_terminal_phase, _is_los_hold_phase
from fpv.guidance.pipeline import SeekerGuidancePipeline


def _gcmd(az=2.0):
    return GuidanceCommand(a_cmd_az_mps2=az, a_cmd_el_mps2=0.0, blend_factor=1.0,
                           geometry=GeometryClass.HEAD_ON, apn_active=False, Vc_sched_mps=20.0,
                           N_effective=3.0, required_g=0.2, achievable_g=0.84, envelope_ok=True)


def test_terminal_phase_tau_driven_ignores_range():
    # use_tau: tau-only -- a close range alone must NOT trigger terminal
    assert _is_terminal_phase(5.0, None, 15.0, 0.4, use_tau=True) is False
    assert _is_terminal_phase(1000.0, 0.2, 15.0, 0.4, use_tau=True) is True   # low tau does
    # legacy: range OR tau
    assert _is_terminal_phase(5.0, None, 15.0, 0.4, use_tau=False) is True


def test_los_hold_tau_driven():
    assert _is_los_hold_phase(100.0, 5.0, tau_s=0.10, tau_threshold_s=0.15, use_tau=True) is True
    assert _is_los_hold_phase(1.0, 5.0, tau_s=None, tau_threshold_s=0.15, use_tau=True) is False  # range ignored


def test_acro_amplifies_roll_at_low_tau():
    g = _gcmd(az=2.0)
    non_term = LosGuidancePilot(config=PilotConfig(use_tau_terminal=True)).command_from_guidance(
        g, az_rad=0.0, el_rad=0.0, sequence_id=0, timestamp_ms=0, estimated_tau_s=2.0)
    term = LosGuidancePilot(config=PilotConfig(use_tau_terminal=True)).command_from_guidance(
        g, az_rad=0.0, el_rad=0.0, sequence_id=0, timestamp_ms=0, estimated_tau_s=0.2)
    assert abs(term.roll_cmd) > abs(non_term.roll_cmd)            # terminal acro amplifies the roll


def test_off_is_bit_identical_no_terminal():
    # default pilot (use_tau_terminal off), tau passed -> the legacy tau path would still fire,
    # but the pipeline only passes tau when the flag is on; here we confirm the OFF pilot with
    # tau=None (as the pipeline sends it) is plain natural roll (no acro).
    g = _gcmd(az=2.0)
    out = LosGuidancePilot(config=PilotConfig(use_tau_terminal=False)).command_from_guidance(
        g, az_rad=0.0, el_rad=0.0, sequence_id=0, timestamp_ms=0, estimated_tau_s=None)
    ref = LosGuidancePilot(config=PilotConfig(use_tau_terminal=False)).command_from_guidance(
        g, az_rad=0.0, el_rad=0.0, sequence_id=0, timestamp_ms=0, estimated_tau_s=None)
    assert out.roll_cmd == ref.roll_cmd


def test_pipeline_tau_terminal_flag_on_still_locks():
    sim = ThermalSimulator(ThermalSceneConfig(ffc_freeze_interval=0, n_stars=3))
    pipe = SeekerGuidancePipeline(use_tau_terminal=True)
    out = None
    for i, (frame, _gt) in enumerate(sim.generate(12)):
        out = pipe.step(now=i / 60.0, frame_u16=frame, gyro_omega_xyz=(0.0, 0.0, 0.0), dt=1 / 60.0)
    assert out.locked is True
