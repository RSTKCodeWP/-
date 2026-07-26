"""6-DOF-lite interceptor and target dynamics for the Block-03 closed-loop sim.

HONEST PHYSICS
--------------
The interceptor is NOT a missile.  Its lateral acceleration is bounded by the
tilt angle:
    a_lateral = g * tan(theta_cmd)    theta_cmd clamped to ±theta_max

At theta_max = 40 deg:  a_lateral_max ≈ 8.22 m/s^2  (0.84 g)
At theta_max = 45 deg:  a_lateral_max ≈ 9.81 m/s^2  (1.00 g)

This fundamentally bounds the interceptable target envelope.  A high-crossing
target at >1 g lateral demand is NOT interceptable.  The sim shows this honestly.

LATENCY MODEL
-------------
The sim injects sensor delay (d_sensor_s, default >25 ms per design §4) and
loop delay.  The bearing fed to guidance is DELAYED.  The Smith-predictor lead
compensates for this by using a model of the delay to project the state forward.

Without Smith predictor:
    bearing_to_guidance(t) = bearing_measured(t - d_total)
With Smith predictor:
    bearing_to_guidance(t) = bearing_measured(t - d_total) + lambda_dot * d_total
    (i.e., the seeker predicted state is forwarded by the delay time)

COORDINATE SYSTEM
-----------------
    x: East (or inertial right)
    y: North (or inertial forward)
    z: Up (positive = altitude gain)

Interceptor launches from origin (0, 0, 0) moving in +y direction initially.
Target approaches from a range down the +y axis.

ENGAGEMENT GEOMETRIES
---------------------
    HEAD_ON: target moves in -y direction (toward interceptor), lambda_dot ≈ 0
    QUARTERING: target moves at ~45 deg off the intercept axis
    HIGH_CROSSING: target moves nearly perpendicular to the LOS

SIGN / UNITS CONVENTIONS
-------------------------
    Positions: meters (m)
    Velocities: m/s
    Accelerations: m/s^2
    Angles: radians
    Time: seconds

    Body-frame bearing: same as seeker/geometry.py
        az_rad > 0 = target right of interceptor boresight
        el_rad > 0 = target above interceptor boresight
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

import numpy as np
import numpy.typing as npt


_G: float = 9.81  # m/s^2


# ---------------------------------------------------------------------------
# Engagement geometry enum
# ---------------------------------------------------------------------------

class EngagementGeometry(str, Enum):
    """Target engagement geometry for the sim."""
    HEAD_ON       = "HEAD_ON"
    QUARTERING    = "QUARTERING"
    HIGH_CROSSING = "HIGH_CROSSING"


# ---------------------------------------------------------------------------
# State dataclasses
# ---------------------------------------------------------------------------

@dataclass
class QuadState:
    """Full interceptor state.

    Attributes
    ----------
    pos: np.ndarray shape (3,)
        Position [x, y, z] in meters.
    vel: np.ndarray shape (3,)
        Velocity [vx, vy, vz] in m/s.
    attitude_rad: np.ndarray shape (3,)
        Roll, pitch, yaw in radians.  Used for gravity feed-forward.
    az_rad: float
        Current boresight azimuth bearing to target (rad).
    el_rad: float
        Current boresight elevation bearing to target (rad).
    t_s: float
        Simulation time (seconds).
    """
    pos: npt.NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )
    vel: npt.NDArray[np.float64] = field(
        default_factory=lambda: np.array([0.0, 15.0, 0.0], dtype=np.float64)
    )
    attitude_rad: npt.NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )
    az_rad: float = 0.0
    el_rad: float = 0.0
    t_s: float = 0.0


@dataclass
class TargetState:
    """Full target state.

    Attributes
    ----------
    pos: np.ndarray shape (3,)
        Position [x, y, z] in meters.
    vel: np.ndarray shape (3,)
        Velocity [vx, vy, vz] in m/s.
    t_s: float
        Simulation time (seconds).
    """
    pos: npt.NDArray[np.float64] = field(
        default_factory=lambda: np.array([0.0, 300.0, 0.0], dtype=np.float64)
    )
    vel: npt.NDArray[np.float64] = field(
        default_factory=lambda: np.array([0.0, -5.0, 0.0], dtype=np.float64)
    )
    t_s: float = 0.0


# ---------------------------------------------------------------------------
# Sim configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SimConfig:
    """Configuration for the closed-loop 6-DOF-lite simulator.

    Attributes
    ----------
    dt_sim_s:
        Integration time step (seconds).  Default 0.001 (1 kHz).
    guidance_rate_hz:
        Guidance tick rate (Hz).  Default 250 Hz.  Decoupled from vision.
    vision_rate_hz:
        Vision pipeline output rate (Hz).  Default 60 Hz.
    sensor_delay_s:
        Boson sensor + USB pipeline delay (seconds).  Default 0.030 (30 ms).
        Design §4 states: >25 ms sensor.  This is the total sensor+pipeline delay.
    loop_delay_s:
        Additional processing loop delay (seconds).  Default 0.010 (10 ms).
    theta_max_rad:
        Maximum tilt angle (radians).  Bounds a_lateral_max.
    drag_coeff:
        Simple linear drag coefficient (1/s).  v_drag = -drag_coeff * vel * dt.
        Default 0.05 (approximates mild drag at ~15 m/s).
    attitude_tau_s:
        Attitude response time constant (seconds).  Actual attitude approaches
        commanded attitude with first-order lag: tau * d(att)/dt = att_cmd - att.
        Default 0.10 s (10 Hz bandwidth, realistic for ANGLE mode on BF).
    mass_kg:
        Interceptor mass (kg).  Used for thrust → acceleration scaling.
        With payload 140-180 g this is the total system mass.
        Default 0.55 kg.
    capture_radius_m:
        Miss distance below which the intercept is counted as a HIT.
        Default 0.75 m (collision intercept for a small drone target).
    target_geometry:
        Engagement geometry enum.
    target_speed_mps:
        Target speed (m/s).  Default 5.0.
    target_jink_g:
        Target lateral jink acceleration in g (SINUSOIDAL, averages to zero).
        0 = no jink.  Default 0.0.
    target_jink_freq_hz:
        Frequency of the sinusoidal jink (Hz).  Default 0.5.
    target_step_jink_g:
        SUSTAINED step-jink: constant lateral acceleration in +x (g units).
        Applied from t=0.  Unlike sinusoidal jink (which averages to zero),
        this demands continuous lateral g from the interceptor.  If >=0.84g,
        the interceptor cannot match it and the engagement fails.  Default 0.
    target_lateral_offset_m:
        Initial lateral (x-axis) offset of the target (m).  0 = collinear.
        With non-zero offset, the guidance must do real lateral work and seed
        noise creates measurable spread in miss distance.  Default 0.
    interceptor_speed_mps:
        Interceptor initial speed (m/s).  Default 15.0.
    initial_range_m:
        Initial range between interceptor and target (m).  Default 200.0.
    max_sim_time_s:
        Maximum simulation time (seconds).  Default 30.0.
    smith_predictor:
        If True, apply a Smith-predictor-style lead to compensate sensor delay.
        Default True.
    seed:
        Random seed for noise injection.  Default 42.
    bearing_noise_sigma_rad:
        1-sigma bearing measurement noise added to the analytic bearing.
        Default 0.0003 rad (~0.6 mrad, ~1.2 px at f=2130 px).
    """
    dt_sim_s: float = 0.001
    guidance_rate_hz: float = 250.0
    vision_rate_hz: float = 60.0
    sensor_delay_s: float = 0.030        # >25 ms sensor (design §4)
    loop_delay_s: float = 0.010          # ~10 ms compute + link
    theta_max_rad: float = math.radians(40.0)
    drag_coeff: float = 0.05
    attitude_tau_s: float = 0.10
    mass_kg: float = 0.55
    capture_radius_m: float = 0.75       # collision intercept
    target_geometry: EngagementGeometry = EngagementGeometry.HEAD_ON
    target_speed_mps: float = 5.0
    target_jink_g: float = 0.0
    target_jink_freq_hz: float = 0.5
    target_step_jink_g: float = 0.0     # sustained step-jink: constant lateral g in +x
    latency_jitter_s: float = 0.0       # A5: per-frame +/- uniform jitter on the sensor+loop delay
    target_lateral_offset_m: float = 0.0  # initial target x-offset from boresight (m)
    interceptor_speed_mps: float = 15.0
    # --- Forward speed-hold (default-OFF -> bit-identical) ---
    # Legacy plant: forward accel = g*tan(pitch) - drag_coeff*v.  The pilot flies a CONSTANT
    # forward_pitch_fraction=0.4 (16 deg -> 2.81 m/s^2), which balances the slow-regime drag
    # (0.05, "mild drag at ~15 m/s") only at ~56 m/s -- so interceptor_speed_mps is merely the
    # INITIAL condition and the plant drifts away from it (the audit's speed-runaway).  That makes a
    # high-speed (150 m/s) Mode-B miss meaningless.  ON: the forward-axis acceleration becomes a
    # first-order speed controller  a_y = speed_hold_gain_hz * (interceptor_speed_mps - v_forward),
    # holding cruise speed regardless of the (slow-regime) drag model -- a fixed-wing/rocket-like
    # interceptor that cruises at constant airspeed while roll does the lateral intercept work.
    speed_hold: bool = False
    speed_hold_gain_hz: float = 2.0          # 1/tau of the forward speed controller (s^-1)
    initial_range_m: float = 200.0
    max_sim_time_s: float = 30.0
    smith_predictor: bool = True
    seed: int = 42
    bearing_noise_sigma_rad: float = 3e-4
    # --- Wave-1 honest measurement model (all default 0 -> bit-identical to the optimistic baseline) ---
    # A CORRELATED (AR-1) bias on the lambda-dot measurement: the ego-compensation / cam<->IMU-skew /
    # centroid-drift residual that does NOT average out in the IMM (unlike the white bearing noise).
    # The audit found the white-only Mode-A loop near-tautological; this is the dominant real-world
    # lambda-dot error and the one the guidance cannot filter away.
    los_rate_bias_sigma_radps: float = 0.0   # std-dev of the stationary AR-1 lambda-dot bias (rad/s)
    los_rate_bias_tau_s: float = 0.30        # AR-1 correlation time of that bias (s)
    # Multiplicative noise + integer-pixel quantization on the blob AREA fed to looming/tau, so the
    # tau-confidence is not a clean closing signal read straight off the true range.
    area_noise_frac: float = 0.0             # 1-sigma fractional area noise (0 -> area unchanged)
    # --- Mode-B (pixel-in-the-loop) honesty knobs (default off -> bit-identical) ---
    # Gyro scale-factor error on the seeker's ROLL de-rotation rate: the world rotates by the TRUE
    # rate (stars render truly), but the seeker's ego-compensation uses an erroneous gyro, leaving a
    # residual LOS error.  This is the in-the-pixel-loop proxy for the dominant cam<->IMU sync / gyro
    # scale-factor strapdown error (the science's top unmeasured term).  0.0 -> bit-identical.
    gyro_scale_error: float = 0.0            # fractional error on omega_z used for ego de-rotation
    # Drive looming/tau from the REAL detected blob area (what the sensor sees) instead of the
    # true-range-derived area -- removes the last Mode-B tautology (tau read off ground-truth range).
    looming_from_detected_area: bool = False
    # --- TRUE PN: measured closing velocity (Mode B only; default OFF -> scheduled Vc, bit-identical) ---
    # When ON, the interceptor renders a RANGE-DEPENDENT (closing) target, measures its silhouette major
    # axis each frame, and runs the subtense range filter (fpv.seeker.subtense_range) to OBSERVE range +
    # closing velocity Vc.  The guidance PN gain then uses the MEASURED Vc / t_go instead of the scheduled
    # scalar -- the payoff of the passive range channel, demonstrated in the loop.  A weak/opening/uncertain
    # estimate declines and the law falls back to the scheduled Vc (graceful degradation).
    measured_vc: bool = False
    target_span_m: float = 4.0        # physical target span (m) for range-dependent render + subtense

    def total_delay_s(self) -> float:
        """Total delay from sensor + loop."""
        return self.sensor_delay_s + self.loop_delay_s


# ---------------------------------------------------------------------------
# Interceptor dynamics
# ---------------------------------------------------------------------------

class QuadSim:
    """6-DOF-lite interceptor dynamics.

    Models position, velocity, attitude with:
    - Lateral acceleration bounded by g * tan(theta_max)
    - Attitude response with first-order lag
    - Simple linear drag model
    - Gravity feed-forward in vertical channel

    NOTE: This is NOT a full Betaflight sim.  We model the physics at the
    level of forces and integrate positions directly.  The PID loop and motor
    mixing are abstracted to an "attitude follows command with time constant tau".
    """

    def __init__(self, config: SimConfig, *, pos0: npt.NDArray[np.float64] | None = None) -> None:
        self._cfg = config
        p0 = pos0 if pos0 is not None else np.zeros(3, dtype=np.float64)
        v0 = np.array([0.0, config.interceptor_speed_mps, 0.0], dtype=np.float64)
        self._state = QuadState(
            pos=p0.copy(),
            vel=v0.copy(),
            attitude_rad=np.zeros(3, dtype=np.float64),
            t_s=0.0,
        )
        # Commanded attitude (first-order lag target)
        self._att_cmd: npt.NDArray[np.float64] = np.zeros(3, dtype=np.float64)

    @property
    def state(self) -> QuadState:
        return self._state

    def step(
        self,
        roll_cmd: float,
        pitch_cmd: float,
        yaw_rate_cmd: float,
        throttle_cmd: float,
        dt: float,
    ) -> QuadState:
        """Integrate one time step.

        Parameters
        ----------
        roll_cmd, pitch_cmd:
            Normalized [-1, +1] angle commands.  Converted to radians via theta_max.
        yaw_rate_cmd:
            Normalized [-1, +1] yaw rate command.  Mapped to ±pi/2 rad/s.
        throttle_cmd:
            Normalized [0, 1] throttle.  0.5 = hover.
        dt:
            Integration time step (seconds).

        Returns
        -------
        QuadState
            Updated state.
        """
        cfg = self._cfg

        # ── Commanded attitude ────────────────────────────────────────────────
        # SIGN CONVENTIONS (body frame, NED-like inertial):
        #   roll_cmd  > 0 → right bank → lateral acceleration in +x (RIGHT)
        #   pitch_cmd > 0 → nose FORWARD (DOWN in NED) → forward acceleration in +y
        #                   This is the RACING QUAD convention: positive pitch = dive forward.
        #   In world coordinates (x=East, y=North, z=Up):
        #     roll → ax = g * sin(roll) ≈ g * tan(roll) for small angles
        #     pitch → ay = g * sin(pitch) ≈ g * tan(pitch) for small angles (forward)
        #     pitch also slightly reduces vertical thrust component (cos effect)
        theta_max = cfg.theta_max_rad
        roll_target  = roll_cmd  * theta_max   # right: +x acceleration
        pitch_target = pitch_cmd * theta_max   # forward: +y acceleration (nose forward)
        yaw_rate = yaw_rate_cmd * (math.pi / 2.0)   # max ±90 deg/s

        # ── First-order attitude lag ──────────────────────────────────────────
        # d(att)/dt = (att_cmd - att) / tau
        tau = cfg.attitude_tau_s
        s = self._state
        roll_actual  = s.attitude_rad[0]
        pitch_actual = s.attitude_rad[1]
        yaw_actual   = s.attitude_rad[2]

        roll_actual  += (roll_target  - roll_actual)  / tau * dt
        pitch_actual += (pitch_target - pitch_actual) / tau * dt
        yaw_actual   += yaw_rate * dt

        self._state.attitude_rad[0] = roll_actual
        self._state.attitude_rad[1] = pitch_actual
        self._state.attitude_rad[2] = yaw_actual

        # ── Lateral acceleration from tilt ────────────────────────────────────
        # Roll  → ax (rightward in world x): a_x = g * tan(roll)
        # Pitch → ay (forward  in world y): a_y_tilt = g * tan(pitch)
        # Combined tilt angle (for vertical thrust loss): cos(sqrt(roll^2 + pitch^2))
        a_lateral_x = _G * math.tan(_clamp(roll_actual, -theta_max, theta_max))
        a_tilt_fwd  = _G * math.tan(_clamp(pitch_actual, -theta_max, theta_max))

        # ── Throttle: vertical thrust component ───────────────────────────────
        # At throttle_cmd = 0.5 (hover point): vertical thrust exactly cancels gravity.
        # throttle_cmd = 0.5 → a_z_from_thrust = +g (hover, level)
        # throttle_cmd = 1.0 → a_z_from_thrust = +2g (climbing hard)
        # throttle_cmd = 0.0 → a_z_from_thrust =  0  (free fall)
        # Formula: a_z_thrust = 2 * throttle_cmd * g  (so 0.5 → g, which cancels -g)
        a_z_thrust = 2.0 * throttle_cmd * _G   # [0, 2g] from throttle

        # Combined tilt reduces vertical thrust (small-angle cos effect):
        # With roll + pitch, cos(theta_total) < 1 → less vertical lift.
        # For small angles this is second-order; include for physical correctness.
        theta_total = math.sqrt(roll_actual ** 2 + pitch_actual ** 2)
        cos_tilt = math.cos(_clamp(theta_total, 0.0, theta_max))

        # Total accelerations in world frame (x=right, y=forward, z=up):
        a_x = a_lateral_x                              # roll:  right
        if cfg.speed_hold:
            # Hold forward (cruise) speed at the setpoint instead of the pitch-vs-drag balance.
            a_y = cfg.speed_hold_gain_hz * (cfg.interceptor_speed_mps - s.vel[1])
        else:
            a_y = a_tilt_fwd - cfg.drag_coeff * s.vel[1]  # pitch: forward + drag (legacy)
        a_z = a_z_thrust * cos_tilt - _G               # throttle*cos - gravity

        # ── Euler integration ─────────────────────────────────────────────────
        accel = np.array([a_x, a_y, a_z], dtype=np.float64)
        new_vel = s.vel + accel * dt
        new_pos = s.pos + s.vel * dt + 0.5 * accel * dt * dt

        self._state.vel = new_vel
        self._state.pos = new_pos
        self._state.t_s += dt

        return self._state


# ---------------------------------------------------------------------------
# Target dynamics
# ---------------------------------------------------------------------------

class TargetSim:
    """Target dynamics with selectable engagement geometry and optional jink.

    Geometries (from SimConfig.target_geometry):
        HEAD_ON:       target moves directly toward interceptor
        QUARTERING:    target moves at ~45 deg off the intercept axis
        HIGH_CROSSING: target moves ~90 deg (nearly perpendicular)

    Jink: sinusoidal lateral acceleration of selectable amplitude and frequency.
    """

    def __init__(self, config: SimConfig) -> None:
        cfg = config
        self._cfg = cfg

        # Initial position: along +y axis at initial_range_m, with optional
        # lateral (x) offset so that guidance must do real lateral work.
        x0 = float(cfg.target_lateral_offset_m)
        y0 = float(cfg.initial_range_m)
        z0 = 0.0

        # Target velocity direction from geometry
        spd = cfg.target_speed_mps
        vx0, vy0, vz0 = _target_velocity_from_geometry(cfg.target_geometry, spd)

        self._state = TargetState(
            pos=np.array([x0, y0, z0], dtype=np.float64),
            vel=np.array([vx0, vy0, vz0], dtype=np.float64),
            t_s=0.0,
        )
        self._rng = np.random.default_rng(cfg.seed + 100)

    @property
    def state(self) -> TargetState:
        return self._state

    def step(self, dt: float) -> TargetState:
        """Integrate target one time step."""
        cfg = self._cfg
        s = self._state

        # ── Sinusoidal jink (averages to zero over a full cycle) ──────────────
        jink_accel_mps2 = 0.0
        if cfg.target_jink_g > 0.0:
            jink_accel_mps2 = cfg.target_jink_g * _G * math.sin(
                2.0 * math.pi * cfg.target_jink_freq_hz * s.t_s
            )

        # Jink direction: perpendicular to current velocity in the xz plane
        vel_mag = float(np.linalg.norm(s.vel))
        if vel_mag > 0.1:
            # Perpendicular in xz: rotate vel 90 deg in x direction
            jink_dir = np.array([-s.vel[2] / vel_mag, 0.0, s.vel[0] / vel_mag], dtype=np.float64)
        else:
            jink_dir = np.array([1.0, 0.0, 0.0], dtype=np.float64)

        jink_vec = jink_dir * jink_accel_mps2

        # ── SUSTAINED step-jink (constant lateral g in +x, held throughout) ──
        # Unlike sinusoidal jink (which averages to zero), a step-jink demands
        # continuous lateral acceleration from the interceptor.  If step_jink_g
        # exceeds achievable 0.84g, the engagement is geometrically impossible.
        step_jink_vec = np.zeros(3, dtype=np.float64)
        if cfg.target_step_jink_g != 0.0:
            step_jink_vec[0] = cfg.target_step_jink_g * _G   # constant +x acceleration

        # Total acceleration: sinusoidal jink + sustained step-jink
        accel = jink_vec + step_jink_vec
        new_vel = s.vel + accel * dt
        new_pos = s.pos + s.vel * dt + 0.5 * accel * dt * dt

        self._state.vel = new_vel
        self._state.pos = new_pos
        self._state.t_s += dt

        return self._state


# ---------------------------------------------------------------------------
# Relative geometry
# ---------------------------------------------------------------------------

def compute_bearing_from_states(
    interceptor_pos: npt.NDArray[np.float64],
    interceptor_vel: npt.NDArray[np.float64],
    target_pos: npt.NDArray[np.float64],
) -> tuple[float, float, float]:
    """Compute body-frame bearing and range from interceptor to target.

    Assumes the interceptor boresight points in the direction of its velocity.

    Parameters
    ----------
    interceptor_pos, interceptor_vel:
        Interceptor position (m) and velocity (m/s).
    target_pos:
        Target position (m).

    Returns
    -------
    (az_rad, el_rad, range_m)
        Body-frame bearing and slant range.
    """
    rel = target_pos - interceptor_pos
    range_m = float(np.linalg.norm(rel))
    if range_m < 1e-6:
        return 0.0, 0.0, range_m

    # Interceptor boresight direction = velocity direction
    vel_mag = float(np.linalg.norm(interceptor_vel))
    if vel_mag < 0.1:
        # Fallback: use +y as boresight
        boresight = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    else:
        boresight = interceptor_vel / vel_mag

    # ASSERTION: boresight must not be near-vertical (|boresight_z| < 0.95).
    # A near-vertical boresight (interceptor pointing mostly straight up or down)
    # degrades the cross(boresight, world_up) basis vector to near-zero, causing
    # the Euler-angle fallback (body_right = +X) to silently activate.  In the
    # FPV intercept scenario the interceptor always has significant horizontal
    # velocity, so a near-vertical boresight indicates a dynamics fault.
    # If this assertion fires in a terminal-dive scenario, the bearing frame must
    # be redefined (e.g., using the previous non-vertical boresight as the last
    # good reference) before the simulation is used for that geometry.
    boresight_z = boresight[2]
    assert abs(boresight_z) < 0.95, (
        f"compute_bearing_from_states: near-vertical Euler fallback triggered "
        f"(|boresight_z|={abs(boresight_z):.3f} >= 0.95).  The velocity-aligned "
        f"boresight is nearly vertical; the bearing frame degenerates.  "
        f"interceptor_vel={interceptor_vel.tolist()}"
    )

    # Build a body frame: +Z = boresight, +X = right, +Y = up
    # Simplified: use world +Z as "up", then right = boresight cross up, etc.
    world_up = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    body_right = np.cross(boresight, world_up)
    right_mag = float(np.linalg.norm(body_right))
    if right_mag < 1e-6:
        # Boresight is nearly vertical — use +X as "right"
        body_right = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    else:
        body_right = body_right / right_mag
    body_up = np.cross(body_right, boresight)

    # Project relative vector onto body axes
    az_px = float(np.dot(rel, body_right))    # right component
    el_px = float(np.dot(rel, body_up))       # up component
    # Boresight range (range along boresight)
    boresight_range = float(np.dot(rel, boresight))

    # Small-angle: az_rad ≈ az_px / boresight_range
    # Full: az = atan2(az_px, boresight_range)
    if boresight_range > 0.0:
        az_rad = math.atan2(az_px, boresight_range)
        el_rad = math.atan2(el_px, boresight_range)
    else:
        # Target behind — rear hemisphere
        az_rad = math.atan2(az_px, max(abs(boresight_range), 0.1))
        el_rad = math.atan2(el_px, max(abs(boresight_range), 0.1))

    return az_rad, el_rad, range_m


def compute_los_rates(
    interceptor_pos: npt.NDArray[np.float64],
    interceptor_vel: npt.NDArray[np.float64],
    target_pos: npt.NDArray[np.float64],
    target_vel: npt.NDArray[np.float64],
) -> tuple[float, float]:
    """Compute true body-frame LOS rates from 3-D kinematics.

    Returns
    -------
    (az_rate_radps, el_rate_radps)
        True LOS angular rates in body frame.
    """
    rel_pos = target_pos - interceptor_pos
    rel_vel = target_vel - interceptor_vel
    range_m = float(np.linalg.norm(rel_pos))
    if range_m < 1e-3:
        return 0.0, 0.0

    # Interceptor boresight = velocity direction
    vel_mag = float(np.linalg.norm(interceptor_vel))
    if vel_mag < 0.1:
        boresight = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    else:
        boresight = interceptor_vel / vel_mag

    world_up = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    body_right = np.cross(boresight, world_up)
    right_mag = float(np.linalg.norm(body_right))
    if right_mag < 1e-6:
        body_right = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    else:
        body_right = body_right / right_mag
    body_up = np.cross(body_right, boresight)

    # LOS rate: d(az)/dt = (rel_vel_right - Vc * az) / range
    # For small angles: lambda_dot_az ≈ (v_perp_right) / range
    # Full: derivative of atan2(y, x) = (x*dy - y*dx) / (x^2 + y^2)
    rel_right = float(np.dot(rel_pos, body_right))
    rel_up    = float(np.dot(rel_pos, body_up))
    rel_boresight = float(np.dot(rel_pos, boresight))

    vrel_right = float(np.dot(rel_vel, body_right))
    vrel_up    = float(np.dot(rel_vel, body_up))
    vrel_boresight = float(np.dot(rel_vel, boresight))

    denom_az = rel_boresight ** 2 + rel_right ** 2
    denom_el = rel_boresight ** 2 + rel_up ** 2

    if denom_az > 1e-6:
        az_rate = (rel_boresight * vrel_right - rel_right * vrel_boresight) / denom_az
    else:
        az_rate = 0.0

    if denom_el > 1e-6:
        el_rate = (rel_boresight * vrel_up - rel_up * vrel_boresight) / denom_el
    else:
        el_rate = 0.0

    return az_rate, el_rate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _target_velocity_from_geometry(
    geometry: EngagementGeometry,
    speed_mps: float,
) -> tuple[float, float, float]:
    """Compute initial target velocity vector from geometry and speed."""
    if geometry == EngagementGeometry.HEAD_ON:
        # Target moves directly toward interceptor origin: -y direction
        return 0.0, -speed_mps, 0.0
    elif geometry == EngagementGeometry.QUARTERING:
        # Target moves at 45 deg to intercept axis
        # Component: cos(45) in -y, sin(45) in +x
        c = speed_mps * math.cos(math.radians(45.0))
        s = speed_mps * math.sin(math.radians(45.0))
        return s, -c, 0.0
    elif geometry == EngagementGeometry.HIGH_CROSSING:
        # Target moves nearly perpendicular to intercept axis (+x direction)
        return speed_mps, 0.0, 0.0
    else:
        raise ValueError(f"Unknown geometry: {geometry}")


def _clamp(v: float, lo: float, hi: float) -> float:
    return min(max(v, lo), hi)
