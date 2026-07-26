"""Map guidance acceleration commands to quad roll/pitch/yaw-rate/throttle.

PHYSICS (matching quad_sim.py conventions)
-------------------------------------------
Coordinate frame (body-frame → world-frame):
    x: right (East)
    y: forward (North)
    z: up

Quad actuation in world frame:
    roll_cmd  > 0 → right bank → lateral acceleration +x (a_x = g * tan(roll))
    pitch_cmd > 0 → nose forward → forward acceleration +y (a_y = g * tan(pitch))
    throttle  > 0.5 → climb; throttle = 0.5 → hover (a_z = 0); throttle < 0.5 → descend

Command mapping from guidance acceleration commands:
    a_cmd_az_mps2 > 0 → target right → command ROLL RIGHT (positive roll_cmd)
        roll_cmd = clamp(atan2(a_cmd_az, g) / theta_max, -1, +1)
    a_cmd_el_mps2 > 0 → target above → command THROTTLE UP
        throttle increases to climb toward the target.
    Forward speed maintained by pitch_cmd (forward_pitch_fraction).

NOTE: Elevation guidance (a_cmd_el) maps to throttle, NOT pitch.  Pitch is
used purely for forward speed.  This is consistent with quad dynamics where:
    - Lateral motion (x): controlled by roll
    - Vertical motion (z): controlled by throttle
    - Forward motion (y): controlled by pitch

Gravity feed-forward in throttle:
    At hover throttle 0.5, the quad holds altitude.  When tilted, the vertical
    thrust component decreases by cos(theta).  To maintain altitude during roll:
        throttle_needed = 0.5 / cos(roll_angle)

Terminal acro switch:
    At close range (<~15 m or <~0.4 s to impact) we amplify the roll command
    slightly to achieve faster angular response (simulating rate-mode agility).

LOS-rate hold (impact freeze):
    Near impact, freeze the last valid roll command.

SIGN / UNITS
-------------
    a_cmd_* in m/s^2.
    roll_cmd, pitch_cmd, yaw_rate_cmd in [-1, +1].
    throttle_cmd in [0, 1] with 0.5 = hover.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from fpv.fpv_ai.betaflight_link.commands import AICommand, CommandLimits  # type: ignore[import]
from fpv.fpv_ai.control.speed import SpeedMode, SpeedPolicy
from fpv.guidance.bearing_rate import GuidanceCommand


_G: float = 9.81  # m/s^2


# ---------------------------------------------------------------------------
# Pilot configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PilotConfig:
    """Configuration for LosGuidancePilot.

    Attributes
    ----------
    theta_max_rad:
        Maximum tilt angle (radians).  Must match GuidanceConfig.theta_max_rad.
        Default: 40 deg = 0.698 rad.
    throttle_hover:
        Normalized throttle [0, 1] required to hold altitude (hover point).
        Default 0.5.
    forward_pitch_fraction:
        Pitch command [0, 1] to maintain forward speed (positive pitch = forward).
        Default 0.4 (moderate forward lean to maintain ~15 m/s closure speed).
    yaw_gain:
        Yaw rate command gain.  yaw_rate = yaw_gain * az_rad.
        Default 1.5 (maps ±0.1 rad bearing to ±0.15 yaw rate command).
    el_throttle_gain:
        Throttle gain for elevation guidance.  throttle_delta = el_throttle_gain * a_cmd_el / g.
        Default 0.2 (moderate vertical authority).
    acro_switch_range_m:
        Range threshold (m) below which the angle→acro switch activates.
        Default 15.0 m.
    acro_switch_tau_s:
        Time-to-impact threshold (s) below which acro switch activates.
        Default 0.4 s.
    los_rate_hold_range_m:
        Range below which the last valid LOS-rate command is frozen (impact freeze).
        Default 5.0 m.
    """
    theta_max_rad: float = math.radians(40.0)
    throttle_hover: float = 0.50
    forward_pitch_fraction: float = 0.40   # positive pitch = forward lean
    yaw_gain: float = 1.5
    el_throttle_gain: float = 0.20
    acro_switch_range_m: float = 15.0
    acro_switch_tau_s: float = 0.40
    los_rate_hold_range_m: float = 5.0
    # R3: drive the terminal/acro and LOS-hold switches off the passive, range-free time-to-contact
    # tau (looming) instead of range/fixed-timer.  Default-OFF -> bit-identical, and when ON it
    # REMOVES range from the terminal path entirely (strengthens Inv 1).
    use_tau_terminal: bool = False
    los_rate_hold_tau_s: float = 0.15      # tau below which LOS-rate hold freezes the command
    # UP-LOOKING CAMERA (boresight = world-up; intercept from BELOW with PN + climb).  Default-OFF ->
    # the forward-camera mapping above is bit-identical.  When ON, the image plane is HORIZONTAL, so
    # BOTH LOS-rate axes are horizontal translation: a_cmd_az -> ROLL, a_cmd_el -> PITCH (not throttle,
    # not a constant forward march).  Throttle instead CLIMBS to close the vertical gap (invisible in
    # the pixel).  Yaw is left at ~0 (for a strapdown up-camera, yawing only spins the pixel frame --
    # it does not close; the owner's "yaw is only доворот" note).
    up_looking_camera: bool = False
    climb_throttle: float = 0.62           # throttle that CLOSES the vertical gap from below (> hover)
    yaw_gain_up: float = 0.0               # up-camera доворот gain (0 = no yaw authority; keep frame fixed)

    def __post_init__(self) -> None:
        if not 0.0 < self.theta_max_rad < math.pi / 2:
            raise ValueError("theta_max_rad must be in (0, pi/2)")
        if not 0.0 <= self.throttle_hover <= 1.0:
            raise ValueError("throttle_hover must be in [0, 1]")


# ---------------------------------------------------------------------------
# LOS Guidance Pilot
# ---------------------------------------------------------------------------

class LosGuidancePilot:
    """Map a GuidanceCommand to a bounded AICommand for the Betaflight link.

    Adapts GateVisualPilot (gate-center visual servo) to bearing-rate-null
    guidance.

    Command mapping (see module docstring for full physics):
        roll_cmd   ← a_cmd_az (lateral)
        pitch_cmd  ← forward_pitch_fraction (constant; elevation is throttle)
        throttle   ← hover + elevation guidance (a_cmd_el)
        yaw_rate   ← az_rad (bearing yaw hold)

    Thread safety
    -------------
    LosGuidancePilot has mutable state (last-valid LOS-rate freeze).
    Call from a single guidance thread.
    """

    def __init__(
        self,
        *,
        config: PilotConfig | None = None,
        speed_policy: SpeedPolicy | None = None,
    ) -> None:
        self._cfg = config or PilotConfig()
        self._speed_policy = speed_policy or SpeedPolicy.default()
        # LOS-rate hold state (impact freeze)
        self._frozen_roll: float = 0.0
        self._frozen_pitch: float = 0.0        # up-camera: pitch is a guidance axis too, so it freezes
        self._frozen_throttle: float = 0.5
        self._los_frozen: bool = False

    def command_from_guidance(
        self,
        guidance_cmd: GuidanceCommand,
        az_rad: float,
        el_rad: float,
        sequence_id: int,
        timestamp_ms: int,
        *,
        estimated_range_m: float | None = None,
        estimated_tau_s: float | None = None,
        speed_mode: SpeedMode = SpeedMode.ADAPTIVE_SPEED,
        target_confidence: float = 1.0,
        tracking_state: str = "LOCKED",
    ) -> AICommand:
        """Convert a guidance acceleration command to a bounded AICommand.

        Parameters
        ----------
        guidance_cmd:
            Lateral acceleration command from BearingRateGuidance.
        az_rad:
            Current filtered azimuth bearing (rad).  Used for yaw rate command.
        el_rad:
            Current filtered elevation bearing (rad).  Used for throttle adjustment.
        sequence_id:
            Monotonically increasing sequence counter for the MSP frame.
        timestamp_ms:
            CLOCK_MONOTONIC timestamp in milliseconds.
        estimated_range_m:
            Estimated range to target (m).  Used for acro/LOS-rate-hold switches.
        estimated_tau_s:
            Estimated time-to-impact (s).  Used for acro switch.
        speed_mode, target_confidence, tracking_state:
            Passed to SpeedPolicy for resolved_speed output.

        Returns
        -------
        AICommand
            Bounded roll/pitch/yaw_rate/throttle commands.
        """
        cfg = self._cfg

        # ── Determine operating mode ──────────────────────────────────────────
        in_terminal_phase = _is_terminal_phase(
            estimated_range_m, estimated_tau_s,
            cfg.acro_switch_range_m, cfg.acro_switch_tau_s,
            use_tau=cfg.use_tau_terminal,
        )
        in_los_hold_phase = _is_los_hold_phase(
            estimated_range_m, cfg.los_rate_hold_range_m,
            tau_s=estimated_tau_s, tau_threshold_s=cfg.los_rate_hold_tau_s,
            use_tau=cfg.use_tau_terminal,
        )

        # ── UP-LOOKING CAMERA: intercept from BELOW (PN in the horizontal plane + climb) ──────
        if cfg.up_looking_camera:
            # Boresight = world-up, so the two LOS-rate axes are BOTH horizontal translations:
            #   a_cmd_az -> ROLL (body-right), a_cmd_el -> PITCH (body-forward).  Throttle CLIMBS to
            #   close the vertical gap; yaw stays ~0 (yawing a strapdown up-camera only spins the pixel).
            roll_n = _accel_to_normalized_angle(guidance_cmd.a_cmd_az_mps2, cfg.theta_max_rad, _G)
            pitch_n = _accel_to_normalized_angle(guidance_cmd.a_cmd_el_mps2, cfg.theta_max_rad, _G)
            cos_comb = math.cos(roll_n * cfg.theta_max_rad) * math.cos(pitch_n * cfg.theta_max_rad)
            climb_n = _clamp(cfg.climb_throttle / max(cos_comb, 0.1), 0.0, 1.0)   # climb + tilt comp
            if in_los_hold_phase:
                self._los_frozen = True
            elif not self._los_frozen:
                self._frozen_roll, self._frozen_pitch, self._frozen_throttle = roll_n, pitch_n, climb_n
            if self._los_frozen:
                roll_u, pitch_u, thr_u = self._frozen_roll, self._frozen_pitch, self._frozen_throttle
            else:
                roll_u, pitch_u, thr_u = roll_n, pitch_n, climb_n
            if in_terminal_phase:                                    # amplify BOTH translation axes
                roll_u = _clamp(roll_u * 1.3, -1.0, 1.0)
                pitch_u = _clamp(pitch_u * 1.3, -1.0, 1.0)
            resolved = self._speed_policy.resolve_speed_mps(
                speed_mode, target_confidence=target_confidence, tracking_state=tracking_state,
                required_g=guidance_cmd.required_g, achievable_g=guidance_cmd.achievable_g)
            return AICommand.bounded(
                roll_cmd=roll_u, pitch_cmd=pitch_u,
                yaw_rate_cmd=_clamp(cfg.yaw_gain_up * az_rad, -1.0, 1.0), throttle_cmd=thr_u,
                target_confidence=target_confidence, target_state=tracking_state,
                recovery_state="NOMINAL", speed_mode=speed_mode, resolved_speed_mps=resolved,
                sequence_id=sequence_id, timestamp_ms=timestamp_ms)

        # ── Compute roll command from lateral (az) guidance ───────────────────
        # a_cmd_az > 0 → right → positive roll
        roll_natural = _accel_to_normalized_angle(
            guidance_cmd.a_cmd_az_mps2, cfg.theta_max_rad, _G
        )

        # ── Throttle: hover + elevation guidance + gravity feed-forward ────────
        # When the quad is tilted by (roll, pitch), the vertical thrust component
        # is: T_z = T * cos(roll) * cos(pitch).
        # To maintain altitude: T = T_hover / (cos(roll) * cos(pitch)).
        # throttle_cmd = throttle_hover / (cos(roll) * cos(pitch)).
        roll_angle   = roll_natural * cfg.theta_max_rad
        pitch_angle  = cfg.forward_pitch_fraction * cfg.theta_max_rad
        cos_combined = math.cos(roll_angle) * math.cos(pitch_angle)
        if cos_combined < 0.1:
            cos_combined = 0.1
        throttle_natural = cfg.throttle_hover / cos_combined

        # Add elevation guidance: a_cmd_el maps to throttle delta
        # a_cmd_el in m/s^2; divide by g to normalize to throttle units
        throttle_el_adj = cfg.el_throttle_gain * guidance_cmd.a_cmd_el_mps2 / _G
        throttle_natural = _clamp(throttle_natural + throttle_el_adj, 0.0, 1.0)

        # ── LOS-rate hold (impact freeze) ─────────────────────────────────────
        if in_los_hold_phase:
            self._los_frozen = True
        elif not self._los_frozen:
            self._frozen_roll = roll_natural
            self._frozen_throttle = throttle_natural

        if self._los_frozen:
            roll_cmd = self._frozen_roll
            throttle_cmd = self._frozen_throttle
        else:
            roll_cmd = roll_natural
            throttle_cmd = throttle_natural

        # ── Terminal acro phase ───────────────────────────────────────────────
        # Amplify slightly to simulate faster rate-mode angular response.
        if in_terminal_phase:
            roll_cmd = _clamp(roll_cmd * 1.3, -1.0, 1.0)

        # ── Pitch: constant forward lean (speed maintenance) ──────────────────
        # Positive pitch_cmd = nose forward = forward acceleration in quad_sim.
        pitch_cmd = cfg.forward_pitch_fraction

        # ── Yaw rate: point boresight toward target az ────────────────────────
        yaw_rate_cmd = _clamp(cfg.yaw_gain * az_rad, -1.0, 1.0)

        # ── Speed policy (A3: coupled to the lateral-g budget) ────────────────
        # Pass the guidance demand vs envelope so the policy holds a lateral-g reserve --
        # slowing closure when the bearing-rate-null demand approaches the achievable g.
        resolved_speed = self._speed_policy.resolve_speed_mps(
            speed_mode,
            target_confidence=target_confidence,
            tracking_state=tracking_state,
            required_g=guidance_cmd.required_g,
            achievable_g=guidance_cmd.achievable_g,
        )

        return AICommand.bounded(
            roll_cmd=roll_cmd,
            pitch_cmd=pitch_cmd,
            yaw_rate_cmd=yaw_rate_cmd,
            throttle_cmd=throttle_cmd,
            target_confidence=target_confidence,
            target_state=tracking_state,
            recovery_state="NOMINAL",
            speed_mode=speed_mode,
            resolved_speed_mps=resolved_speed,
            sequence_id=sequence_id,
            timestamp_ms=timestamp_ms,
        )

    def reset(self) -> None:
        """Reset the LOS-rate freeze state."""
        self._frozen_roll = 0.0
        self._frozen_throttle = 0.5
        self._los_frozen = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _accel_to_normalized_angle(a_mps2: float, theta_max_rad: float, g: float) -> float:
    """Convert lateral acceleration command to normalized tilt angle.

    theta_cmd = atan2(a_cmd, g)
    normalized = theta_cmd / theta_max  (clamped to [-1, +1])
    """
    theta = math.atan2(a_mps2, g)
    normalized = theta / theta_max_rad
    return _clamp(normalized, -1.0, 1.0)


def _is_terminal_phase(
    range_m: float | None,
    tau_s: float | None,
    range_threshold_m: float,
    tau_threshold_s: float,
    use_tau: bool = False,
) -> bool:
    """True if the engagement is in the terminal (acro) phase.

    With ``use_tau`` (R3) the decision is tau-driven ONLY -- range is removed from the terminal
    path entirely (Inv 1).  Otherwise the legacy range-OR-tau behaviour is preserved exactly.
    """
    if use_tau:
        return tau_s is not None and 0.0 < tau_s < tau_threshold_s
    if range_m is not None and range_m < range_threshold_m:
        return True
    if tau_s is not None and 0.0 < tau_s < tau_threshold_s:
        return True
    return False


def _is_los_hold_phase(
    range_m: float | None,
    threshold_m: float,
    tau_s: float | None = None,
    tau_threshold_s: float = 0.0,
    use_tau: bool = False,
) -> bool:
    """True if in the LOS-rate-hold (impact-freeze) phase.

    With ``use_tau`` (R3) the trigger is a tau threshold (range-free); otherwise legacy range.
    """
    if use_tau:
        return tau_s is not None and 0.0 < tau_s < tau_threshold_s
    if range_m is not None and range_m < threshold_m:
        return True
    return False


def _clamp(v: float, lo: float, hi: float) -> float:
    return min(max(v, lo), hi)
