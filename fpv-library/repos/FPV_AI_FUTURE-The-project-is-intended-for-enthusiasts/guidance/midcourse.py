"""Midcourse lead establishment for the near-ballistic high-speed terminal (with a large reserve).

WHY THIS EXISTS (the doctrine's own physics)
--------------------------------------------
At Vi ~ 150 m/s the airframe turn radius is Vi^2/(g*tan(theta_max)) ~ 2.7 km, VASTLY larger than the
50-200 m thermal engagement range (see ``engagement_regime.py``).  So the interceptor is nearly
BALLISTIC in the terminal -- it cannot turn appreciably in the last tenths of a second.  Therefore the
collision course (the LEAD) must be ESTABLISHED IN MIDCOURSE, where range and time still buy turning
authority; the terminal then only trims a tiny residual LOS rate.

"WITH A LARGE RESERVE, AS IF BALLISTIC" (the owner's directive)
--------------------------------------------------------------
The g-wall LOS rate is ``lambda_dot_wall = a_max/(N*Vc)`` -- the rate at which the PN demand equals the
airframe limit.  Midcourse drives the LOS rate WELL BELOW the wall, by a margin factor (default 3, the
doctrine's 3:1 overmatch), so that when the terminal goes ballistic (course effectively frozen) the tiny
residual it inherits is comfortably inside the terminal's remaining authority.  So:

    MIDCOURSE          : full-authority PN nulls lambda_dot toward lambda_dot_wall / margin (aggressive; the
                         phase where the airframe CAN turn) -- establishes the lead with reserve.
    BALLISTIC_TERMINAL : once close AND the lead is established with the reserve, apply only a TINY trim
                         (the course is essentially set) -- treat the terminal as ballistic.
    TERMINAL_BEST_EFFORT: close but the lead was NOT established to the reserve -> HONESTLY flagged; push
                         through with full authority (default-COMPLETE), but the ballistic assumption does
                         not hold and this is a targeting-geometry shortfall, surfaced not hidden.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass

from fpv.guidance.engagement_regime import G


class MidcoursePhase(str, enum.Enum):
    MIDCOURSE = "MIDCOURSE"                    # establishing the lead with full authority
    BALLISTIC_TERMINAL = "BALLISTIC_TERMINAL"  # lead established with reserve -> tiny terminal trim
    TERMINAL_BEST_EFFORT = "TERMINAL_BEST_EFFORT"  # close but lead short of reserve -> honest push-through


@dataclass(frozen=True)
class MidcourseConfig:
    N_mid: float = 4.0                    # aggressive midcourse nav ratio (>= terminal N)
    theta_max_rad: float = math.radians(40.0)
    lead_margin_factor: float = 3.0       # the RESERVE: establish lambda_dot <= wall / this (3:1 overmatch)
    handover_t_go_s: float = 1.5          # t_go below this -> terminal regime
    handover_range_m: float = 60.0        # OR range below this -> terminal regime
    terminal_trim_frac: float = 0.15      # BALLISTIC terminal applies at most this fraction of a_max

    def a_max_mps2(self) -> float:
        return G * math.tan(self.theta_max_rad)


@dataclass(frozen=True)
class MidcourseCommand:
    a_cmd_az_mps2: float
    a_cmd_el_mps2: float
    phase: MidcoursePhase
    lambda_dot_mag_radps: float
    lambda_dot_wall_radps: float          # a_max/(N*Vc): the g-wall LOS rate at this closing speed
    lead_margin: float                    # wall / |lambda_dot|: how much reserve the ballistic terminal has
    lead_established: bool                # lead_margin >= lead_margin_factor (the reserve is met)


def _clamp(v: float, lim: float) -> float:
    return max(-lim, min(lim, v))


class MidcourseGuidance:
    """Establish the collision-course lead in midcourse with a reserve, then hand a ballistic terminal.

    Consumes the same body-frame LOS the terminal PN uses (IMM az/el rates) plus the MEASURED closing
    velocity and time-to-go from the subtense range channel.  Output is a lateral acceleration command
    like ``bearing_rate``; the two compose -- midcourse sets the lead, ``bearing_rate`` (+ terminal_hold)
    flies the near-ballistic terminal.
    """

    def __init__(self, config: MidcourseConfig | None = None) -> None:
        self._cfg = config or MidcourseConfig()

    def compute(self, *, az_rate_radps: float, el_rate_radps: float, vc_mps: float,
                t_go_s: float, range_m: float) -> MidcourseCommand:
        cfg = self._cfg
        a_max = cfg.a_max_mps2()
        vc = max(float(vc_mps), 0.1)

        lam_az, lam_el = float(az_rate_radps), float(el_rate_radps)
        lam_mag = math.hypot(lam_az, lam_el)

        # The g-wall LOS rate and the achieved reserve.
        wall = a_max / (cfg.N_mid * vc)
        lead_margin = wall / lam_mag if lam_mag > 1e-9 else float("inf")
        established = lead_margin >= cfg.lead_margin_factor

        # Full-authority lead-nulling PN (the midcourse command).
        cmd_az = cfg.N_mid * vc * lam_az
        cmd_el = cfg.N_mid * vc * lam_el

        terminal = (math.isfinite(t_go_s) and t_go_s <= cfg.handover_t_go_s) or (range_m <= cfg.handover_range_m)

        if not terminal:
            phase = MidcoursePhase.MIDCOURSE
            lim = a_max                                   # midcourse can use the full airframe to set the lead
        elif established:
            phase = MidcoursePhase.BALLISTIC_TERMINAL
            lim = cfg.terminal_trim_frac * a_max          # course is set -> only a tiny ballistic trim
        else:
            phase = MidcoursePhase.TERMINAL_BEST_EFFORT
            lim = a_max                                   # honest: lead short of reserve -> push through, best effort

        return MidcourseCommand(
            a_cmd_az_mps2=_clamp(cmd_az, lim),
            a_cmd_el_mps2=_clamp(cmd_el, lim),
            phase=phase,
            lambda_dot_mag_radps=lam_mag,
            lambda_dot_wall_radps=wall,
            lead_margin=lead_margin,
            lead_established=established,
        )
