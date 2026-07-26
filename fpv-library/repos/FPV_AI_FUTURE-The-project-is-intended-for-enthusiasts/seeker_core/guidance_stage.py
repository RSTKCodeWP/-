"""seeker_core guidance stage — a bench PREVIEW proportional-navigation law.

HONEST scope: a stationary bench has NO closing velocity and NO range, so a real intercept law
(fpv.guidance.bearing_rate, which needs Vc + geometry) cannot run meaningfully. This produces a
PREVIEW command a = N·Vc_assumed·λ̇ from the LOS rate, purely to visualise steering demand on the
bench — it drives NOTHING (the mapper only actuates the airframe after a two-press commit, and the
bench has no motors). For flight/sim, swap in the full BearingRateGuidance.
"""
from __future__ import annotations

import math

from seeker_core.contracts import GuidanceCommand, Track

_G = 9.80665


class PreviewGuidance:
    """PN preview: a_cmd = N · Vc_assumed · λ̇. Preview only — Vc is assumed (no bench closing speed)."""

    def __init__(self, n_nav: float = 4.0, vc_assumed_mps: float = 100.0) -> None:
        self.n_nav = n_nav
        self.vc = vc_assumed_mps

    def command(self, track: Track) -> GuidanceCommand:
        gain = self.n_nav * self.vc
        a_az = gain * track.los_rate_az
        a_el = gain * track.los_rate_el
        required_g = math.hypot(a_az, a_el) / _G
        return GuidanceCommand(a_cmd_az=a_az, a_cmd_el=a_el, roe_abort=False,
                               engage_permit=track.locked,      # guidance-side permit; human authority is separate
                               required_g=required_g, provenance=track.provenance)
