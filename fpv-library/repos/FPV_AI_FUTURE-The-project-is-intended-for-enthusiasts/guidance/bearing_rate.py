"""Bearing-rate-null guidance law for the Block-03 thermal FPV interceptor.

HONEST PHYSICS — READ THIS FIRST
---------------------------------
The core law is:
    a_cmd = N * Vc_sched * lambda_dot

This is a BEARING-RATE NULLER, not a range-free PN miracle.

Why we schedule Vc (not measure it from tau):
    A passive monocular seeker WITHOUT own-maneuver parallax fundamentally cannot
    observe closing velocity Vc.  The only passive estimate is optical looming:
        tau = A / (dA/dt),  Vc_approx = range / tau
    But tau degenerates in three critical regimes:
        (1) ACQUISITION (1-3 px blob): dA/dt is noise-dominated.
        (2) CROSSING: dA/dt → 0 while lambda_dot is large → tau → inf.
        (3) IMPACT: blob fills FOV, dA/dt underestimates, tau collapses.
    These are EXACTLY the regimes where the guidance law runs.  So we SCHEDULE
    Vc from SpeedPolicy.  This is honest.  The law direction (sign of lambda_dot)
    comes from S2 IMM; the MAGNITUDE is set by Vc_sched.

Why N = 3 (not 4):
    Standard PN theory sets N in 3-5 for zero-lag guidance.  With sensor delay
    T_d > 25 ms and loop delay, the miss-distance term from delay scales as:
        miss ~ N * Vc * T_d^2 * a_T / 2
    Higher N amplifies BOTH the noise in lambda_dot AND the delay-induced
    oscillation.  Simulations (Gate L) confirm N=3 is more robust than N=4
    for sensor delays above ~30 ms.  The trade is: N=4 catches faster maneuvers
    but diverges sooner under delay.

Pure-pursuit blend:
    Pure pursuit points the interceptor toward the target, using ONLY the bearing
    (az, el), not the bearing rate or Vc.  It is Vc-free.  When tau_confidence
    is low (acquisition, crossing, impact-saturation), we blend toward pure pursuit
    to avoid Vc-blind failures.  The blend weight is:

        blend_factor = tau_confidence  (0 = pure pursuit, 1 = full bearing-rate-null)

    But note: the design says "tau_confidence" as a proxy for "do we trust the
    geometry well enough to use bearing-rate-null".  It is also low during crossing.
    This is correct behavior: at crossing, pure pursuit diverges less than an
    underscaled bearing-rate-null.

APN term:
    Augmented PN adds (N/2) * a_T to compensate for known target acceleration.
    a_T is estimated from the IMM maneuver mode.  We gate it strictly:
        - Only when IMM.maneuver_detected is True (sustained over N_SUSTAIN frames)
        - Only when the maneuver probability exceeds maneuver_prob_threshold
        - Magnitude capped at apn_accel_cap_mps2 to prevent noise amplification.

Envelope gate (ROE safety):
    The quad's max achievable lateral acceleration:
        a_max = g * tan(theta_max_rad)
    At theta_max = 35 deg → a_max ≈ 6.87 m/s^2 ≈ 0.70 g
    At theta_max = 45 deg → a_max ≈ 9.81 m/s^2 ≈ 1.00 g

    The gate classifies geometry and raises ROE_ABORT if:
        (a) High-crossing target: |lambda_dot| > crossing_rate_threshold AND the
            cross-range closing cue (from tau_confidence) is near-zero.
        (b) Required lateral-g exceeds achievable: |a_cmd| > a_max * abort_g_margin.

SIGN CONVENTIONS
-----------------
    az_rate_radps:  positive = target moving RIGHT in body frame.  Source: IMM.
    el_rate_radps:  positive = target moving UP in body frame.  Source: IMM.
    a_cmd_az_mps2:  positive = command interceptor to accelerate RIGHT.
                    This NULLS a rightward-moving target bearing: if target moves right
                    (lambda_dot_az > 0), we command rightward acceleration to follow it.
                    The LOS rate is nulled when the interceptor matches target motion.
    a_cmd_el_mps2:  positive = command interceptor to accelerate UP.
    Vc_sched:       positive = interceptor is closing on target (scalar).
    N:              positive (default 3).

UNITS
------
    All angles and rates: radians, rad/s.
    All accelerations: m/s^2.
    Vc: m/s.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Optional

import numpy as np

from fpv.seeker.imm import IMMEstimate
from fpv.seeker.looming import LoomingEstimate


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class GeometryClass(str, Enum):
    """Engagement geometry classification."""
    HEAD_ON      = "HEAD_ON"       # |lambda_dot| < head_on_rate_threshold, closing
    QUARTERING   = "QUARTERING"    # Intermediate: oblique approach
    HIGH_CROSSING = "HIGH_CROSSING" # |lambda_dot| large, near-zero closing cue


class ROEAbort(Exception):
    """Raised when the engagement geometry falls outside the achievable envelope.

    This is NOT a software error — it is a safety gate.  The caller must catch
    this and revert to a non-kinetic hold or safe-ditch depending on mission phase.

    Attributes
    ----------
    reason:
        Human-readable explanation.
    geometry:
        Classified engagement geometry.
    required_g:
        The lateral acceleration (in g) the guidance law is demanding.
    achievable_g:
        The maximum lateral acceleration (in g) the quad can produce.
    """

    def __init__(
        self,
        reason: str,
        geometry: GeometryClass,
        required_g: float,
        achievable_g: float,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.geometry = geometry
        self.required_g = required_g
        self.achievable_g = achievable_g


@dataclass(frozen=True)
class GuidanceCommand:
    """Per-tick output of the guidance law.

    Attributes
    ----------
    a_cmd_az_mps2:
        Lateral acceleration command in the az (horizontal) plane (m/s^2).
        Positive = accelerate RIGHT to null a rightward-drifting target bearing.
    a_cmd_el_mps2:
        Lateral acceleration command in the el (vertical) plane (m/s^2).
        Positive = accelerate UP to null an upward-drifting target bearing.
    blend_factor:
        0.0 = pure pursuit only.  1.0 = full bearing-rate-null.
        Intermediate = weighted blend.
    geometry:
        Classified engagement geometry.
    apn_active:
        True if the APN (Augmented PN) term was added this tick.
    Vc_sched_mps:
        Scheduled closing velocity used this tick (m/s).
    N_effective:
        Effective navigation ratio used (may differ from cfg.N if blended).
    required_g:
        Lateral demand in units of g (= a_total / 9.81).
    achievable_g:
        Achievable lateral limit in units of g (= a_max / 9.81).
    envelope_ok:
        True if required_g <= achievable_g * abort_g_margin (no abort raised).
    pursuit_az_mps2, pursuit_el_mps2:
        Pure-pursuit component of the command (for diagnostics).
    brn_az_mps2, brn_el_mps2:
        Bearing-rate-null component of the command (for diagnostics).
    """

    a_cmd_az_mps2: float
    a_cmd_el_mps2: float
    blend_factor: float
    geometry: GeometryClass
    apn_active: bool
    Vc_sched_mps: float
    N_effective: float
    required_g: float
    achievable_g: float
    envelope_ok: bool
    pursuit_az_mps2: float = 0.0
    pursuit_el_mps2: float = 0.0
    brn_az_mps2: float = 0.0
    brn_el_mps2: float = 0.0
    # --- A3 honesty fields (diagnostic; never feed back into the PN gain) ---
    t_go_s: float = float("inf")          # time-to-go (s); inf when unobservable
    t_go_source: str = "unobservable"     # "looming" | "unobservable"
    target_maneuver_ceiling_g: float = 0.0  # 3:1 overmatch rule: reliably-killable target g
    terminal_hold: bool = False             # ten-tau wall: this command is a FROZEN impact course


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GuidanceConfig:
    """Configuration for the BearingRateGuidance law.

    Attributes
    ----------
    N:
        Navigation ratio.  Default 3.  Range 3-4.
        Keep at 3 for sensor delays > 25 ms (see module docstring).
    Vc_sched_mps:
        Scheduled closing velocity (m/s).  This is the PRIMARY Vc source.
        Derived from own airspeed (SpeedPolicy) + assumed target speed.
        Typical value: own_speed + target_speed_assumed.
        Example: interceptor at 15 m/s vs target at 5 m/s head-on → Vc ≈ 20 m/s.
    theta_max_rad:
        Maximum tilt angle (radians).  a_max = g * tan(theta_max_rad).
        Design: 35 deg (0.611 rad) → 0.70 g; 45 deg (0.785 rad) → 1.00 g.
    abort_g_margin:
        Fraction of achievable_g above which ROE_ABORT is raised.
        Default 0.90: abort if demand exceeds 90% of achievable lateral g.
    crossing_rate_threshold_radps:
        |lambda_dot| above which geometry is classified as HIGH_CROSSING.
        Default 0.15 rad/s (~8.6 deg/s).
    tau_confidence_pursuit_threshold:
        Below this tau_confidence, blend weight → pure pursuit.
        Default 0.3.
    tau_confidence_full_brn_threshold:
        Above this tau_confidence, blend weight → full bearing-rate-null.
        Default 0.7.
    pursuit_gain_mps2_per_rad:
        Gain for the pure-pursuit term (m/s^2 per radian of bearing error).
        Maps (az, el) bearing directly to lateral acceleration command.
        Physically: if target is at 0.1 rad (~5.7 deg) off-boresight and this
        gain is 10, the pursuit command is 1 m/s^2.
        Default: use Vc_sched as the gain (a = Vc * az/f ≈ Vc * az for small angles).
        Set to None to use Vc_sched dynamically.
    maneuver_prob_threshold:
        Minimum IMM maneuver probability for APN term to be active.
        Default 0.65.
    apn_accel_cap_mps2:
        Maximum |a_T| injected via APN term (m/s^2).  Prevents noise amplification.
        Default 3.0 m/s^2 (~0.3 g).
    max_a_cmd_mps2:
        Hard cap on the total lateral command magnitude (m/s^2).
        Safety floor below the ROE_ABORT threshold.
        Default: g * tan(theta_max_rad) * abort_g_margin (set at runtime if 0).
    """

    N: float = 3.0
    Vc_sched_mps: float = 20.0           # interceptor ~15 m/s + target ~5 m/s head-on
    lead_time_s: float = 0.0             # W5: angular Smith-predictor lead (s); 0 = off (bit-identical)
    theta_max_rad: float = math.radians(40.0)  # 40 deg → ~0.84 g
    abort_g_margin: float = 1.0    # abort at 100% of achievable: command clamp is the real guard; margin > 1 silently saturates
    # PERSISTENCE for the envelope ROE-abort, as a leaky accumulator (over-demand ticks add, in-envelope
    # ticks drain). A consecutive-run counter does NOT work here: the real spikes are intermittent, so it
    # would reset on every good frame and never fire.
    #
    # WHY IT EXISTS: the abort fires on a SINGLE over-demand tick, which kills engagements that are actually
    # succeeding -- one noisy LOS-rate frame spikes the demand and the engagement ends. Worse, the abort is
    # disabled post-commit BY DESIGN, so it also DEADLOCKS the commit: the abort prevents the commit that
    # would have disabled the abort. In `launch_and_forget` that ended engagements at ~1.2 s with the target
    # still ~100 m out; setting this to 25 takes formal COMMITTED from 1/5 seeds to 4/5.
    #
    # WHY IT IS NEVERTHELESS OFF BY DEFAULT (measured 2026-07-19): persistence is NOT uniformly good. In the
    # head-on closed loop (`test_true_pn_measured_vc`) it makes the miss ~2x WORSE on 6 of 6 seeds
    # (0.66->1.34, 0.84->2.67, 1.60->2.76, 0.49->1.60, 0.49->1.28, 0.72->1.32 m against a 0.75 m capture
    # radius). That is systematic, not seed noise.
    #
    # MECHANISM (measured, not assumed): the closed loop's abort response ZEROES the lateral command. Riding
    # through the over-demand instead applies the CLAMPED command, which pins the airframe at saturated bank
    # 8x longer (100 vs 12 ticks at >0.9 roll). On a STRAPDOWN seeker that is self-harming: full bank tilts
    # the camera, corrupting the very lambda-dot the guidance depends on -- the same maneuver<->seeker
    # coupling that made a gimbal win by 9x in the honest 3D sim. Thrust is also diverted off the closing axis.
    #
    # NOTE what this is NOT. The first explanation written here was a terminal blow-up of our perp-LOS law.
    # The data refutes it: with persistence the terminal is CALMER, not wilder (max |lambda-dot| 0.044 vs
    # 0.127 rad/s, max |a_cmd| 3.6 vs 5.0 m/s^2). The damage is done by sustained SATURATION, and it is not
    # specific to the terminal.
    #
    # So the abort's zeroing is doing real work as an over-demand SATURATION-AVOIDANCE policy, not merely as
    # an abort -- and that policy is worth having explicitly rather than as a side effect of aborting. The
    # honest fix is a principled over-demand response ("if the demand is unreachable, do not fly a saturated
    # version of it"), which is separable from the commit deadlock this flag exists to solve.
    envelope_abort_persist_ticks: int = 0
    crossing_rate_threshold_radps: float = 0.15   # ~8.6 deg/s LOS rate → crossing
    # --- Vc-scaled crossing threshold (default-OFF -> bit-identical) ---
    # The fixed 0.15 rad/s was tuned for the OLD slow regime (Vc~20): at Vc=20 the airframe g-wall
    # a_lat = N*Vc*lambda_dot = a_max is reached at lambda_dot ~ a_max/(N*Vc) ~ 0.137 rad/s ~ 0.15.
    # At the high-speed regime (Vc~150-230) that same g-wall is hit at lambda_dot ~ 0.012-0.018 rad/s,
    # so a FIXED 0.15 threshold under-fires HIGH_CROSSING by ~8-12x and can leak a silent miss on a
    # non-closing crosser.  When ON, the crossing threshold IS the g-wall LOS rate lambda_dot_wall =
    # a_max/(N*Vc) -- the first-principles boundary where required_g == achievable_g -- so the
    # classifier tracks feasibility across the whole speed range (more permissive at low Vc where
    # crossings ARE achievable, more sensitive at high Vc where they are not).
    vc_scaled_crossing_threshold: bool = False
    tau_confidence_pursuit_threshold: float = 0.30
    tau_confidence_full_brn_threshold: float = 0.70
    pursuit_gain_mps2_per_rad: float = 0.0        # 0 = use Vc_sched dynamically
    maneuver_prob_threshold: float = 0.65
    apn_accel_cap_mps2: float = 3.0
    max_a_cmd_mps2: float = 0.0                   # 0 = derive from theta_max + margin
    # --- R2: NIS-scheduled lambda-dot smoothing (default-OFF -> bit-identical) ---
    # Smooth lambda-dot HARD when innovations are quiet (glint defence), and OPEN the loop as the
    # NIS rises / on a sustained model-wrong alarm (so a real jink is NOT lagged). The innovation
    # is the only honest glint-vs-maneuver discriminator. Purely an angular-rate filter -- no
    # range, state stays modified-polar (Inv 1/4).
    nis_lambda_smoothing: bool = False
    lambda_smooth_alpha_quiet: float = 0.3        # EMA weight when quiet (low = heavy smoothing)
    nis_chi2_open: float = 9.21                   # NIS at which the loop fully opens (alpha->1)
    # --- A1: ACQUIRE low-gain settling before full PN (default-OFF -> bit-identical) ---
    # Ramp the PN gain from a benign fraction to full N over the first ticks of the engagement,
    # so the first commands after lock-on are gentle while the LOS estimate is still settling
    # (the falcon's feed-forward lock-on phase before terminal PN). 0 ticks = off.
    acquire_settle_ticks: int = 0
    acquire_settle_min_frac: float = 0.3          # starting gain fraction of N at tick 1

    def a_max_mps2(self) -> float:
        """Maximum achievable lateral acceleration (m/s^2)."""
        return 9.81 * math.tan(self.theta_max_rad)

    def effective_crossing_threshold(self, Vc_mps: float) -> float:
        """The LOS-rate threshold used to classify HIGH_CROSSING at this closing speed.

        OFF (default): the fixed ``crossing_rate_threshold_radps`` -> bit-identical to before.
        ON: the g-wall LOS rate ``lambda_dot_wall = a_max/(N*Vc)`` -- the rate at which the PN
        demand ``N*Vc*lambda_dot`` equals the achievable lateral accel ``a_max``.  This is the
        physical feasibility boundary, so it scales correctly with Vc.
        """
        if not self.vc_scaled_crossing_threshold:
            return self.crossing_rate_threshold_radps
        return self.a_max_mps2() / (self.N * max(Vc_mps, 0.1))

    def achievable_g(self) -> float:
        """Maximum achievable lateral acceleration in units of g."""
        return math.tan(self.theta_max_rad)

    def effective_max_a_cmd(self) -> float:
        """Effective hard cap on |a_cmd| (m/s^2).

        HONEST PHYSICS: the clamp must agree with the abort boundary.
        abort_g_margin=1.0 means we abort at a_max.  The clamp is set to
        a_max so that guidance and plant agree on the physical limit.
        With abort_g_margin=1.0 and the clamp at a_max, there is no silent
        20% saturation margin — what the abort sees is what the actuator sees.
        """
        if self.max_a_cmd_mps2 > 0.0:
            return self.max_a_cmd_mps2
        # Cap at true achievable a_max (NOT a_max * margin):
        return self.a_max_mps2()


# ---------------------------------------------------------------------------
# Guidance law
# ---------------------------------------------------------------------------

class BearingRateGuidance:
    """Body-frame bearing-rate-null guidance law with pursuit blend.

    See module docstring for the honest physics description.

    State
    -----
    The law maintains a tick counter to implement a warmup guard before
    HIGH_CROSSING abort can fire.  The seeker needs several frames to
    establish geometry (distinguish "small blob approaching" from "crossing
    target").  During warmup, HIGH_CROSSING classification is suppressed.

    Usage
    -----
    ::
        cfg = GuidanceConfig(N=3, Vc_sched_mps=20.0, theta_max_rad=math.radians(40))
        guidance = BearingRateGuidance(cfg)

        # Each tick (at guidance rate, decoupled from vision):
        try:
            cmd = guidance.compute(imm_estimate, looming_estimate)
        except ROEAbort as abort:
            handle_abort(abort)

    Thread safety
    -------------
    BearingRateGuidance is NOT stateless — it tracks tick count for warmup.
    Use from a single guidance thread only.
    """

    # Minimum ticks before HIGH_CROSSING abort can fire.
    # At 250 Hz, 250 ticks = 1 second of engagement data.
    # This prevents startup-noise and looming-uninitialized aborts.
    # The physical justification: the seeker needs ~0.5s (typical: 30 vision frames)
    # to establish both bearing rate trend and looming signal.
    _CROSSING_WARMUP_TICKS: int = 125   # 0.5 s at 250 Hz

    def __init__(self, config: GuidanceConfig | None = None) -> None:
        self._cfg = config or GuidanceConfig()
        self._tick: int = 0   # monotonic tick counter for warmup guard
        # R2 NIS-scheduled lambda-dot EMA state (None until first tick).
        self._lambda_dot_az_ema: float | None = None
        self._lambda_dot_el_ema: float | None = None
        self._last_cmd: GuidanceCommand | None = None   # ten-tau wall: last established course
        # Leaky accumulator for the envelope abort: over-demand ticks add, in-envelope ticks drain.
        self._over_envelope: float = 0.0

    @property
    def config(self) -> GuidanceConfig:
        return self._cfg

    def compute(
        self,
        imm: IMMEstimate,
        looming: LoomingEstimate,
        *,
        Vc_override_mps: float | None = None,
        committed: bool = False,
        terminal_hold: bool = False,
    ) -> GuidanceCommand:
        """Compute one guidance tick.

        Parameters
        ----------
        imm:
            Filtered LOS state from S2 IMMFilter (body-frame az/el/rates).
        looming:
            Looming estimate from S2 LoomingEstimator (tau, tau_confidence).
        Vc_override_mps:
            If supplied, override the configured Vc_sched.  Used for testing or
            SpeedPolicy integration where the outer loop provides a current speed.

        Returns
        -------
        GuidanceCommand
            Lateral acceleration commands in az and el.

        Raises
        ------
        ROEAbort
            If the engagement geometry exceeds the achievable lateral-g envelope
            or is classified as HIGH_CROSSING.
        """
        cfg = self._cfg
        self._tick += 1

        # ── A1: ACQUIRE low-gain settling ─────────────────────────────────────
        # Ramp the PN gain from acquire_settle_min_frac*N up to full N over the first
        # acquire_settle_ticks; gentle corrections while the lock settles. 0 ticks -> gain 1.0.
        if cfg.acquire_settle_ticks > 0 and self._tick <= cfg.acquire_settle_ticks:
            acquire_gain = cfg.acquire_settle_min_frac + (1.0 - cfg.acquire_settle_min_frac) * (
                self._tick / cfg.acquire_settle_ticks)
        else:
            acquire_gain = 1.0

        # ── Vc scheduling ────────────────────────────────────────────────────
        Vc = Vc_override_mps if Vc_override_mps is not None else cfg.Vc_sched_mps
        Vc = max(Vc, 0.1)  # defensive: Vc must be positive

        # ── LOS-rate from IMM ────────────────────────────────────────────────
        # IMM gives filtered (az_rate_radps, el_rate_radps) in body frame.
        # Sign: az_rate > 0 → target drifting RIGHT; el_rate > 0 → target drifting UP.
        lambda_dot_az = imm.az_rate_radps
        lambda_dot_el = imm.el_rate_radps

        # Non-finite LOS rate (malformed IMM) -> fail safe to a labelled ABORT, never let
        # NaN poison the blend/command and trip a generic, mis-labelled envelope abort (C6).
        if not (math.isfinite(lambda_dot_az) and math.isfinite(lambda_dot_el)):
            raise ROEAbort(
                reason="non-finite LOS rate from IMM -> fail-safe ABORT",
                geometry=GeometryClass.HIGH_CROSSING,
                required_g=float("inf"),
                achievable_g=cfg.achievable_g(),
            )

        # ── Ten-tau wall / impact-freeze (W4) ────────────────────────────────
        # In the terminal window lambda_dot = Vt_perp/R blows up as R->0, demanding g the airframe
        # cannot pull; chasing it wastes authority and WORSENS miss. Inside the wall we FREEZE the
        # last established collision-course command and fly it straight in -- corrections must have
        # completed before this point. `terminal_hold` is decided upstream from a RANGE-FREE subtense
        # proxy (target filling the FOV => very close). Fail-safe: no established course -> compute.
        if terminal_hold and self._last_cmd is not None:
            return replace(self._last_cmd, terminal_hold=True)

        # ── R2: NIS-scheduled lambda-dot smoothing ───────────────────────────
        # Heavy EMA when innovations are quiet (kills glint walk on the aimpoint); the weight
        # rises with the IMM NIS and snaps fully open on a sustained model-wrong alarm, so a real
        # maneuver is responsive, never lagged. OFF -> raw IMM rate (bit-identical).
        if cfg.nis_lambda_smoothing:
            nis = imm.nis if math.isfinite(imm.nis) else cfg.nis_chi2_open
            alpha = cfg.lambda_smooth_alpha_quiet + (1.0 - cfg.lambda_smooth_alpha_quiet) * min(
                max(nis, 0.0) / max(cfg.nis_chi2_open, 1e-9), 1.0)
            if imm.model_wrong_alarm:
                alpha = 1.0
            if self._lambda_dot_az_ema is None:
                self._lambda_dot_az_ema = lambda_dot_az
                self._lambda_dot_el_ema = lambda_dot_el
            else:
                self._lambda_dot_az_ema += alpha * (lambda_dot_az - self._lambda_dot_az_ema)
                self._lambda_dot_el_ema += alpha * (lambda_dot_el - self._lambda_dot_el_ema)
            lambda_dot_az = self._lambda_dot_az_ema
            lambda_dot_el = self._lambda_dot_el_ema

        # ── Geometry classification ──────────────────────────────────────────
        # LOS rate magnitude — proxy for crossing geometry
        lambda_dot_mag = math.sqrt(lambda_dot_az ** 2 + lambda_dot_el ** 2)
        crossing_threshold = cfg.effective_crossing_threshold(Vc)
        geometry = self._classify_geometry(lambda_dot_mag, looming, self._tick,
                                           crossing_threshold=crossing_threshold)

        # ── ROE-ABORT: high-crossing geometry ────────────────────────────────
        # High-crossing: large LOS rate + low closing confidence.
        # Physical reason: at crossing, dA/dt → 0, tau → inf, Vc underestimated
        # even from SpeedPolicy (Vc_proj = Vc * cos(crossing_angle) → 0).
        # Quad energy budget cannot close a high-g crossing intercept.
        # TWO-PHASE (mature-doctrine Axis II): the envelope ABORT is a PRE-COMMIT gate only --
        # do not COMMIT into an infeasible crossing.  POST-COMMIT the seeker is a doer, not a
        # doubter: it does NOT abort on geometry, it pushes through with the best clamped command
        # (below), and abort is reserved for HARD self-safe (CIVCAS keep-out / geo / genuine target
        # loss) handled by the engage-FSM, never here.  (Non-finite LOS above stays a fault-abort.)
        if geometry == GeometryClass.HIGH_CROSSING and not committed:
            required_g = lambda_dot_mag * Vc * cfg.N / 9.81
            achievable_g = cfg.achievable_g()
            # The 3:1 overmatch rule (a multirotor needs ~3x the target's lateral-g to
            # intercept) is the PHYSICAL reason this abort exists, not a tunable threshold:
            # a crosser drives required-g toward the regime our 0.84 g body cannot fly.
            raise ROEAbort(
                reason=(
                    f"HIGH_CROSSING geometry: lambda_dot_mag={lambda_dot_mag:.4f} rad/s "
                    f"> threshold={crossing_threshold:.4f} rad/s, "
                    f"tau_confidence={looming.tau_confidence:.3f} (low), "
                    f"required_g={required_g:.2f} > achievable_g={achievable_g:.2f}; "
                    f"3:1 overmatch -> reliably-killable target maneuver "
                    f"ceiling ~{achievable_g / 3.0:.2f} g"
                ),
                geometry=geometry,
                required_g=required_g,
                achievable_g=achievable_g,
            )

        # ── Blend weight: tau_confidence drives blend ────────────────────────
        # blend_factor=0 → pure pursuit (Vc-free, uses bearing directly)
        # blend_factor=1 → full bearing-rate-null (requires Vc)
        # Sanitize a non-finite tau_confidence to 0 (pure pursuit) so it cannot produce a
        # NaN blend -> NaN command (C6).  The wired LoomingEstimator is finite-guarded; this
        # protects the public compute() API and any future adapter.
        tau_conf = looming.tau_confidence if math.isfinite(looming.tau_confidence) else 0.0
        blend_factor = _blend_weight(
            tau_conf,
            low_thresh=cfg.tau_confidence_pursuit_threshold,
            high_thresh=cfg.tau_confidence_full_brn_threshold,
        )

        # ── Pure-pursuit component ────────────────────────────────────────────
        # Pure pursuit: point toward the target.
        # Acceleration to null bearing = Vc * bearing (small angle approximation).
        # Physical: to close the angle, we accelerate toward where the target IS,
        # not where it's going.  This doesn't need Vc — we use Vc as a proxy gain
        # because a_cmd ~ v * angle for turning at speed v.
        pursuit_gain = cfg.pursuit_gain_mps2_per_rad if cfg.pursuit_gain_mps2_per_rad > 0.0 else Vc
        # W5 latency lead (Smith-predictor, purely ANGULAR -> no range dependence): aim at where the
        # bearing WILL be after the loop transport delay, az + az_rate*lead_time. 0 -> stale bearing.
        az_lead = imm.az_rad + imm.az_rate_radps * cfg.lead_time_s
        el_lead = imm.el_rad + imm.el_rate_radps * cfg.lead_time_s
        pursuit_az = pursuit_gain * az_lead
        pursuit_el = pursuit_gain * el_lead

        # ── Bearing-rate-null component (the PN law) ─────────────────────────
        # a_cmd = N * Vc * lambda_dot
        # Sign: lambda_dot_az > 0 (target moving right) → a_cmd_az > 0 (command right).
        # Physical interpretation: we command the interceptor to match the target's
        # angular motion, which creates the collision-triangle condition.
        brn_az = cfg.N * acquire_gain * Vc * lambda_dot_az
        brn_el = cfg.N * acquire_gain * Vc * lambda_dot_el

        # ── APN term: (N/2) * a_T (only when IMM confidently detects maneuver) ─
        # APN compensates for known target acceleration, halving the miss vs a jinking
        # target.  We gate it STRICTLY because a_T estimation from IMM is noisy.
        apn_az = 0.0
        apn_el = 0.0
        apn_active = False

        if (
            imm.maneuver_detected
            and imm.mode_probs[1] >= cfg.maneuver_prob_threshold
        ):
            # APN UNITS FIX — previous code computed Vc * innovation_az which is
            # dimensionally [m/s * rad] = NOT an acceleration.
            #
            # Correct APN: a_cmd_apn = (N/2) * a_T where a_T is target lateral
            # acceleration in m/s^2.  APN requires range to be known:
            #     a_T = range * d²λ/dt²
            # Since range is NOT observable from a passive monocular seeker, we
            # CANNOT compute a_T correctly here.  Options:
            #   (A) Remove APN entirely (honest: no range = no APN)
            #   (B) Use IMM rate-innovation / dt as a raw angular-accel estimate,
            #       then multiply by range_assumed.  But range_assumed = 0 here.
            #
            # Decision: REMOVE the dimensionally-wrong APN term.
            # The pure bearing-rate-null law (N*Vc*lambda_dot) is correct without APN.
            # APN can be re-enabled when range becomes observable (e.g., via looming
            # or RF triangulation): a_T = range * imm.az_rate_innovation / dt.
            #
            # We keep apn_active=True to log that the maneuver was detected, even
            # though the APN acceleration contribution is zero.
            apn_az = 0.0
            apn_el = 0.0
            apn_active = True

        # ── Blend: combine pursuit and bearing-rate-null ─────────────────────
        total_az = (1.0 - blend_factor) * pursuit_az + blend_factor * (brn_az + apn_az)
        total_el = (1.0 - blend_factor) * pursuit_el + blend_factor * (brn_el + apn_el)

        # ── Envelope check ───────────────────────────────────────────────────
        a_total = math.sqrt(total_az ** 2 + total_el ** 2)
        a_max = cfg.a_max_mps2()
        required_g = a_total / 9.81
        achievable_g = cfg.achievable_g()
        envelope_ok = a_total <= a_max * cfg.abort_g_margin

        # Leaky accumulator: a transient spike drains away, a persistent over-demand builds up.
        self._over_envelope = (self._over_envelope + 1.0 if not envelope_ok
                               else max(0.0, self._over_envelope - 1.0))

        # ROE-ABORT: demand PERSISTENTLY exceeds achievable g.  PRE-COMMIT only (Axis II): post-commit we
        # push through with the hard-cap clamp below (best-effort complete) rather than abort on demand.
        if not envelope_ok and not committed and self._over_envelope > cfg.envelope_abort_persist_ticks:
            raise ROEAbort(
                reason=(
                    f"Lateral demand {a_total:.2f} m/s^2 ({required_g:.2f} g) "
                    f"exceeds achievable {a_max * cfg.abort_g_margin:.2f} m/s^2 "
                    f"({achievable_g * cfg.abort_g_margin:.2f} g at {math.degrees(cfg.theta_max_rad):.0f} deg tilt). "
                    f"Geometry: {geometry.value}.  This engagement is out of envelope."
                ),
                geometry=geometry,
                required_g=required_g,
                achievable_g=achievable_g,
            )


        # ── Hard cap (safety floor) ───────────────────────────────────────────
        max_cmd = cfg.effective_max_a_cmd()
        total_az = _clamp(total_az, -max_cmd, max_cmd)
        total_el = _clamp(total_el, -max_cmd, max_cmd)

        # ── A3 honesty: continuous N_effective, t_go, 3:1 maneuver ceiling ────
        # N slides from pursuit (N'≈1, no lead) to full PN (N) with the blend weight,
        # so the field reads as "how much lead are we applying" rather than echoing cfg.N.
        n_effective = blend_factor * cfg.N * acquire_gain + (1.0 - blend_factor) * 1.0
        # t_go is honest ONLY when looming gives a confident, finite, positive tau;
        # otherwise it is unobservable (passive monocular).  Diagnostic only.
        if (looming.tau_confidence >= cfg.tau_confidence_full_brn_threshold
                and math.isfinite(looming.tau_s) and looming.tau_s > 0.0):
            t_go_s, t_go_source = float(looming.tau_s), "looming"
        else:
            t_go_s, t_go_source = float("inf"), "unobservable"
        # 3:1 overmatch rule: we reliably intercept a target maneuvering below ~a_max/3.
        target_ceiling_g = achievable_g / 3.0

        cmd = GuidanceCommand(
            a_cmd_az_mps2=total_az,
            a_cmd_el_mps2=total_el,
            blend_factor=blend_factor,
            geometry=geometry,
            apn_active=apn_active,
            Vc_sched_mps=Vc,
            N_effective=n_effective,
            required_g=a_total / 9.81,
            achievable_g=achievable_g,
            envelope_ok=envelope_ok,
            pursuit_az_mps2=pursuit_az,
            pursuit_el_mps2=pursuit_el,
            brn_az_mps2=brn_az,
            brn_el_mps2=brn_el,
            t_go_s=t_go_s,
            t_go_source=t_go_source,
            target_maneuver_ceiling_g=target_ceiling_g,
        )
        self._last_cmd = cmd                            # ten-tau wall: remember the established course
        return cmd

    def _classify_geometry(
        self,
        lambda_dot_mag: float,
        looming: LoomingEstimate,
        tick: int = 0,
        crossing_threshold: float | None = None,
    ) -> GeometryClass:
        """Classify engagement geometry from LOS rate and looming cues.

        HIGH_CROSSING requires ALL of:
          (1) large LOS rate magnitude (target sweeping across FOV)
          (2) looming confidence is low (area not growing = not closing)
          (3) tick >= _CROSSING_WARMUP_TICKS (seeker initialized, not startup noise)

        The warmup guard prevents HIGH_CROSSING classification during the first
        0.5s when looming hasn't established the closure signal yet.
        A large LOS rate alone (pure pursuit, early acquisition) is not crossing.

        Parameters
        ----------
        lambda_dot_mag:
            |lambda_dot| in rad/s (from IMM).
        looming:
            Looming estimate (tau_confidence, closing_sign).
        tick:
            Current tick count.  HIGH_CROSSING suppressed before warmup.
        """
        cfg = self._cfg
        thr = cfg.crossing_rate_threshold_radps if crossing_threshold is None else crossing_threshold
        is_high_rate = lambda_dot_mag > thr

        # Warmup guard: do not fire HIGH_CROSSING before seeker is initialized.
        # Physically: the seeker needs several frames to distinguish "small blob
        # approaching" from "crossing target with constant area".
        past_warmup = tick >= self._CROSSING_WARMUP_TICKS

        # Closing determination: either tau_confidence is low (area not growing)
        # OR closing_sign indicates not-approaching.
        # closing_sign = 0 is acceptable after warmup (means area rate near zero →
        # consistent with crossing or very-slow-approach).
        # Use `not (>=)` so a non-finite tau_confidence reads as NOT-closing (fail-safe to
        # HIGH_CROSSING), where `< 0.3` would be False on NaN and silently mis-label (C6).
        is_not_closing = (not (looming.tau_confidence >= 0.3)) or looming.closing_sign <= 0

        if is_high_rate and is_not_closing and past_warmup:
            return GeometryClass.HIGH_CROSSING
        if is_high_rate:
            return GeometryClass.QUARTERING
        return GeometryClass.HEAD_ON


# ---------------------------------------------------------------------------
# Vc scheduling from SpeedPolicy
# ---------------------------------------------------------------------------

def schedule_Vc_mps(
    own_airspeed_mps: float,
    target_speed_assumed_mps: float = 5.0,
    geometry: GeometryClass = GeometryClass.HEAD_ON,
) -> float:
    """Schedule closing velocity from own airspeed and assumed target speed.

    For head-on and quartering geometry, Vc = own_speed + target_speed.
    For crossing, Vc_proj = Vc * cos(crossing_angle) — but we don't call this
    for crossing because that triggers ROE_ABORT.

    This is the HONEST Vc estimate: we do not pretend to know target speed
    precisely.  The assumption (5 m/s default) is a conservative floor.
    Real engagements are near-head-on where own-airspeed dominates.

    Parameters
    ----------
    own_airspeed_mps:
        Interceptor airspeed (m/s).
    target_speed_assumed_mps:
        Assumed target airspeed for closing-rate calculation (m/s).
        Use operator knowledge or default 5 m/s (slow DJI-class drone).
    geometry:
        Classified geometry.  Used for a cosine projection correction.

    Returns
    -------
    float
        Scheduled Vc (m/s), always positive.
    """
    # Head-on or quartering: Vc ≈ own_speed + target_speed (relative approach)
    # Quartering: project by cos(45 deg) ≈ 0.707
    if geometry == GeometryClass.HEAD_ON:
        Vc = own_airspeed_mps + target_speed_assumed_mps
    else:  # QUARTERING
        Vc = (own_airspeed_mps + target_speed_assumed_mps) * math.cos(math.radians(22.5))
    return max(Vc, 1.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blend_weight(tau_conf: float, low_thresh: float, high_thresh: float) -> float:
    """Linearly ramp blend from 0 (pure pursuit) to 1 (full BRN) with tau_confidence."""
    if tau_conf <= low_thresh:
        return 0.0
    if tau_conf >= high_thresh:
        return 1.0
    return (tau_conf - low_thresh) / (high_thresh - low_thresh)


def _clamp(v: float, lo: float, hi: float) -> float:
    return min(max(v, lo), hi)
