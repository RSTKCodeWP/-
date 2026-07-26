"""Engagement-regime kinematics for the high-speed intercept (Block-3 seeker design driver).

BRIEFING (2026-07-03): the threat closes at 200-300 km/h (55.6-83.3 m/s); our interceptor flies
100-150 m/s. The seeker must hold the track, predict the threat trajectory, and hit on lead. These
speeds are 5-10x the values the closed-loop sim was tuned for (Vc ~15-23 m/s), so several things
change qualitatively. This module computes the load-bearing numbers so the design is sized to the
REAL regime and the consequences are pinned as tests, not prose.

CONVENTION
----------
``aspect_deg`` is the angle between the threat's velocity vector and the line of sight FROM the
threat TO the interceptor:
    0   deg -> threat flying straight AT the interceptor (pure head-on / collision)
    90  deg -> threat crossing broadside (all velocity tangential to the LOS)
    180 deg -> threat fleeing (tail chase)

The threat velocity splits into a component along the LOS (adds/subtracts closing speed) and a
component across it (drives the LOS rate the seeker must track and the interceptor must null).

WHAT BREAKS AT THESE SPEEDS (all quantified below)
--------------------------------------------------
1. Broadside crossing is geometrically UNACHIEVABLE: the PN lateral demand N*Vc*lambda_dot blows
   past the ~0.84 g airframe wall by more than an order of magnitude.
2. Terminal maneuver authority collapses: at 150 m/s and 0.84 g the turn radius is ~2.7 km, vastly
   larger than the 50-200 m thermal engagement range -> the interceptor is nearly ballistic in the
   terminal, so the LEAD must be pre-established (ground cue + midcourse), and terminal PN only
   trims a small residual lambda_dot.
3. Track-holding gets hard: the target sweeps ~10-20 px/frame at 60 Hz on a crossing -> the ROI
   must be placed on the PREDICTED position, not the last one.
4. Latency dominates the miss: at Vc~230 m/s every millisecond of loop latency is ~0.23 m of blind
   closure and the crosser slips ~0.08 m laterally -> the FPGA's deterministic sub-frame latency is
   worth metres of miss distance vs the ~35 ms Pi loop.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

G = 9.80665  # m/s^2

# FT640 wide lens: f_px = (640/2)/tan(48.7 deg/2) ~= 707 px (see fpv/seeker/geometry.py).
FT640_F_PX = 707.0


@dataclass(frozen=True)
class InterceptGeometry:
    """One engagement geometry.  All speeds m/s, range m, angle deg."""

    interceptor_speed_mps: float
    target_speed_mps: float
    range_m: float
    aspect_deg: float
    N: float = 3.0
    f_px: float = FT640_F_PX
    frame_rate_hz: float = 60.0
    body_g_limit: float = 0.84   # sustained lateral-accel wall of the airframe (a_lat = g*tan(40deg))


@dataclass(frozen=True)
class RegimeResult:
    closing_speed_mps: float      # Vc = range closure rate
    target_perp_mps: float        # threat velocity component across the LOS
    los_rate_radps: float         # lambda_dot the seeker sees at acquisition (target contribution)
    pixel_rate_px_s: float        # lambda_dot mapped through the lens
    px_per_frame: float           # per-frame target motion at the frame rate
    required_lateral_g: float     # PN demand N*Vc*lambda_dot to null the LOS rate, in g
    feasible: bool                # required_lateral_g <= body_g_limit
    time_to_go_s: float           # R / Vc (closing engagements only; inf if opening)
    turn_radius_m: float          # Vi^2 / (body_g_limit*g): how tight the interceptor can turn

    def blind_closure_m(self, latency_s: float) -> float:
        """Range the target closes during one loop-latency period (the 'blind' closure)."""
        return self.closing_speed_mps * latency_s

    def lateral_slip_m(self, latency_s: float) -> float:
        """How far a crossing target slips across the LOS during one loop-latency period.

        This is the direct miss contribution of loop latency against a crosser -- the argument for
        deterministic sub-frame latency (FPGA) over the ~35 ms Pi loop.
        """
        return self.target_perp_mps * latency_s

    def min_roi_halfwidth_px(self, margin_frames: float = 2.0, blob_radius_px: float = 4.0) -> float:
        """Half-width of a tracking ROI that will still contain the target next frame.

        Must cover the per-frame motion (times a margin for prediction error) plus the blob extent.
        With a PREDICTED ROI centre the required size shrinks; this is the reactive (last-position)
        bound, which is why prediction is needed at these speeds.
        """
        return self.px_per_frame * margin_frames + blob_radius_px


def analyze(geo: InterceptGeometry) -> RegimeResult:
    """Compute the engagement-regime kinematics for one geometry."""
    a = math.radians(geo.aspect_deg)
    vt = geo.target_speed_mps
    vi = geo.interceptor_speed_mps

    # Threat velocity split relative to the LOS.
    vt_radial = vt * math.cos(a)     # + = threat approaching along the LOS
    vt_perp = abs(vt * math.sin(a))  # across the LOS

    # Closing speed: interceptor flies along the LOS toward the threat, plus the threat's radial part.
    closing = vi + vt_radial

    # LOS rate the seeker sees at acquisition (target's tangential motion at this range).
    los_rate = vt_perp / geo.range_m if geo.range_m > 0 else float("inf")
    pixel_rate = los_rate * geo.f_px
    px_per_frame = pixel_rate / geo.frame_rate_hz

    # PN lateral demand to null that LOS rate: a_cmd = N * Vc * lambda_dot.  Feasibility is against
    # the airframe's sustained-g wall.  (Use the magnitude of closing; on an opening geometry PN is
    # not the right frame, but the demand magnitude is still the correction the airframe would need.)
    required_g = geo.N * abs(closing) * los_rate / G

    time_to_go = geo.range_m / closing if closing > 0 else float("inf")
    turn_radius = vi * vi / (geo.body_g_limit * G)

    return RegimeResult(
        closing_speed_mps=closing,
        target_perp_mps=vt_perp,
        los_rate_radps=los_rate,
        pixel_rate_px_s=pixel_rate,
        px_per_frame=px_per_frame,
        required_lateral_g=required_g,
        feasible=required_g <= geo.body_g_limit,
        time_to_go_s=time_to_go,
        turn_radius_m=turn_radius,
    )


def max_feasible_aspect_deg(geo: InterceptGeometry, *, resolution_deg: float = 0.05) -> float:
    """Largest off-head-on aspect that is still within the airframe g-wall at this range/speed.

    Scans aspect from 0 upward and returns the last angle whose PN demand stays under the wall.
    This is the 'lead cone' the interceptor must be positioned inside BEFORE terminal -- the seeker
    cannot correct a wider crossing angle in the last tens of metres.
    """
    last_ok = 0.0
    a = 0.0
    while a <= 90.0:
        g = InterceptGeometry(
            interceptor_speed_mps=geo.interceptor_speed_mps, target_speed_mps=geo.target_speed_mps,
            range_m=geo.range_m, aspect_deg=a, N=geo.N, f_px=geo.f_px,
            frame_rate_hz=geo.frame_rate_hz, body_g_limit=geo.body_g_limit)
        if analyze(g).feasible:
            last_ok = a
        else:
            break
        a += resolution_deg
    return last_ok


# ── representative envelope (also the __main__ table) ─────────────────────────
def _representative_table() -> str:
    lines = ["Block-3 high-speed engagement regime  (Vi=150, Vt=83 m/s unless noted, N=3, FT640)"]
    lines.append(f"  turn radius @150 m/s, 0.84 g = "
                 f"{analyze(InterceptGeometry(150, 83, 100, 0)).turn_radius_m:.0f} m "
                 f"(>> 50-200 m engagement range -> terminal is near-ballistic)")
    lines.append(f"  {'geometry':>18} {'R m':>5} {'Vc m/s':>7} {'lam_dot':>8} {'px/fr':>6} "
                 f"{'req_g':>7} {'t_go s':>7} {'feas':>5}")
    rows = [
        ("head-on", 0, 200), ("head-on", 0, 50),
        ("10deg lead", 10, 200), ("10deg lead", 10, 100),
        ("quartering 30", 30, 150), ("broadside", 90, 100), ("broadside", 90, 50),
        ("tail-chase 180", 180, 150),
    ]
    for name, asp, R in rows:
        r = analyze(InterceptGeometry(150, 83, R, asp))
        tgo = f"{r.time_to_go_s:6.3f}" if math.isfinite(r.time_to_go_s) else "  inf "
        lines.append(f"  {name:>18} {R:>5} {r.closing_speed_mps:>7.1f} {r.los_rate_radps:>8.3f} "
                     f"{r.px_per_frame:>6.1f} {r.required_lateral_g:>7.2f} {tgo:>7} "
                     f"{str(r.feasible):>5}")
    for R in (100, 200, 500):
        mfa = max_feasible_aspect_deg(InterceptGeometry(150, 83, R, 0))
        lines.append(f"  max feasible lead aspect @ R={R:>3} m : {mfa:.2f} deg")
    return "\n".join(lines)


if __name__ == "__main__":
    print(_representative_table())
