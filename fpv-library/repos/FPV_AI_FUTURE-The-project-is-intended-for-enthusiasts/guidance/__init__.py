"""S3 Terminal guidance package — bearing-rate nuller + closed-loop intercept sim.

HONEST PHYSICS SUMMARY
----------------------
The law is:  a_cmd = N * Vc_sched * lambda_dot

This is a BEARING-RATE NULLER, not a range-free PN miracle.  A passive monocular
seeker cannot observe closing velocity Vc.  Vc is SCHEDULED from SpeedPolicy
own-airspeed + assumed target speed.  lambda_dot (from S2 IMM) gives the
DIRECTION only.  Looming-tau is a weak confidence-gated cross-check, never trusted
for Vc scaling.

A quad is NOT a missile.  Lateral acceleration a = g * tan(theta), theta clamped
to ±35-45 deg → max ~0.7-1.0 g.  This BOUNDS the interceptable envelope.  High-
crossing and high-g jinking targets are NOT interceptable — the envelope gate
fires ROE_ABORT for those.

Sign / frame / units conventions:
    All angles: radians.
    All angular rates: rad/s.
    All linear accelerations: m/s^2.
    Body-frame bearing: az positive RIGHT, el positive UP.  Matches seeker/geometry.py.
    a_cmd_az: positive = accelerate RIGHT (increases az_rate).
    a_cmd_el: positive = accelerate UP (increases el_rate).
    Vc_sched: positive = interceptor closing on target (scalar, m/s).
    N (navigation ratio): dimensionless, default 3, range 3-4.
        N pushes DOWN toward 3 at higher sensor delay because delay-induced
        oscillation amplitude scales as N * delay, not linearly with N.
"""
from fpv.guidance.bearing_rate import (
    BearingRateGuidance,
    GuidanceConfig,
    GuidanceCommand,
    GeometryClass,
    ROEAbort,
)
from fpv.guidance.command_map import LosGuidancePilot, PilotConfig as GuidancePilotConfig
from fpv.guidance.quad_sim import QuadSim, QuadState, TargetSim, TargetState, SimConfig
from fpv.guidance.closed_loop import ClosedLoop, ClosedLoopConfig, EngagementResult, run_monte_carlo

__all__ = [
    "BearingRateGuidance",
    "GuidanceConfig",
    "GuidanceCommand",
    "GeometryClass",
    "ROEAbort",
    "LosGuidancePilot",
    "GuidancePilotConfig",
    "QuadSim",
    "QuadState",
    "TargetSim",
    "TargetState",
    "SimConfig",
    "ClosedLoop",
    "ClosedLoopConfig",
    "EngagementResult",
    "run_monte_carlo",
]
