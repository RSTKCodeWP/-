"""Instantaneous miss geometry — the honest commit cue.

Replaces the range threshold that the commit gate used to rely on. That threshold was silently disabled for
months by a wrong assumed target span (subtense range is ``f·assumed_span/extent_px``, so a 2x wrong span is
a 2x wrong range and nothing in the system noticed). The cues here are built so the weakest one needs no
range at all.

Three cues, degrading gracefully into each other:

===========================  ===============================  ==================================
cue                          needs                            availability
===========================  ===============================  ==================================
``collision_course``         the seeker's LOS rate only        **range-free, always**
``phi_h`` (miss phase)       LOS rate + any ``t_go``           inherits the range estimate's error
``miss_vector`` (exact)      full relative state ``r``, ``v``  only when an estimator supplies it
===========================  ===============================  ==================================

The physics, in one line: a **constant bearing means a collision course**. If the line of sight to the target
holds still while the range closes, you are on an intercept — that is the whole basis of proportional
navigation, and it needs no range, no target size, and no filter. It is the only commit evidence a purely
passive seeker can produce without borrowing an assumption from somewhere else.

The miss phase relates the two (Sozinov & Gorevich's ``φ_h``; Palumbo's eq. 45 ``r_CPA`` is the same quantity
reached independently)::

    φ_h = atan(λ̇ · t_go)        exact for t_go = R / Vc; verified to 0.01° in tests

``φ_h → 0`` means the relative velocity points straight down the line of sight — a collision course.
``sin(φ_h)`` is the miss as a fraction of current range, so it is a *normalised* miss that stays meaningful
without knowing metric range.

References: Palumbo, Blaukamp & Lloyd, JHU APL Tech. Digest 29(1) 2010, eqs. 41/44/45;
Sozinov & Gorevich, Vestnik Almaz-Antey 2/2022 (miss phase φ_h). See docs/GUIDANCE_UPGRADE_PLAN.md §3.2.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MissGeometry:
    """Instantaneous miss geometry. Fields are ``None`` when the inputs cannot support them honestly."""

    t_go_s: float | None          # time to closest approach
    phi_h_rad: float | None       # miss phase: angle between the closing velocity and the LOS
    miss_ratio: float | None      # sin(phi_h) -- miss as a FRACTION of current range (range-free)
    miss_m: float | None          # metric miss at CPA; only when a metric relative state was supplied
    lambda_dot_radps: float       # the LOS rate we measured (always present)
    source: str                   # "relative-state" | "los-rate+tgo" | "los-rate-only"

    @property
    def on_collision_course(self) -> bool:
        """A constant bearing IS a collision course. Range-free, and the strongest thing a passive seeker
        can assert on its own."""
        return abs(self.lambda_dot_radps) <= COLLISION_LAMBDA_DOT_RADPS


# A collision course means the LOS holds still. This threshold is what "still" means for us: it is set from
# the seeker's own angular noise floor (~0.3 deg/frame at 50 Hz would be ~0.1 rad/s of apparent rate), so
# demanding much tighter would just be gating on noise. Deliberately NOT scaled by range -- the whole point
# of this cue is that it does not need range.
COLLISION_LAMBDA_DOT_RADPS: float = 0.05


def from_relative_state(r_xyz, v_xyz) -> MissGeometry:
    """Exact miss geometry from a full metric relative state (Palumbo eqs. 44/45).

    ``r`` is target-minus-interceptor position, ``v`` the relative velocity, in one consistent frame. Use
    this only when an estimator actually supplies a metric state -- its quality is inherited wholesale.
    """
    r = np.asarray(r_xyz, dtype=float)
    v = np.asarray(v_xyz, dtype=float)
    vv = float(v @ v)
    rr = float(np.linalg.norm(r))
    if vv <= 1e-12 or rr <= 1e-9:
        return MissGeometry(None, None, None, None, 0.0, "relative-state")

    t_go = -float(r @ v) / vv                                    # eq. 44: time to CPA (not the biased R/Ṙ)
    miss_vec = np.cross(np.cross(v, r), v) / vv                  # eq. 45: the instantaneous miss vector
    miss = float(np.linalg.norm(miss_vec))
    lam_dot = float(np.linalg.norm(np.cross(r, v))) / (rr * rr)  # LOS rate implied by this state

    cos_phi = float(-(r @ v)) / (rr * math.sqrt(vv))
    phi = math.acos(max(-1.0, min(1.0, cos_phi)))
    return MissGeometry(t_go_s=t_go, phi_h_rad=phi, miss_ratio=math.sin(phi), miss_m=miss,
                        lambda_dot_radps=lam_dot, source="relative-state")


def from_los_rate(lambda_dot_radps: float, t_go_s: float | None = None) -> MissGeometry:
    """The practical path: miss geometry from the MEASURED LOS rate, plus a ``t_go`` if we have one.

    With ``t_go`` this gives the miss phase ``φ_h = atan(λ̇·t_go)`` -- exact, and it needs no metric range,
    only the LOS rate the seeker already produces. Without ``t_go`` the collision-course cue still works,
    because a constant bearing is a collision course regardless of how far away the target is.
    """
    lam = float(lambda_dot_radps)
    if t_go_s is None or not math.isfinite(t_go_s) or t_go_s <= 0.0:
        return MissGeometry(None, None, None, None, lam, "los-rate-only")

    phi = math.atan(abs(lam) * t_go_s)
    return MissGeometry(t_go_s=float(t_go_s), phi_h_rad=phi, miss_ratio=math.sin(phi), miss_m=None,
                        lambda_dot_radps=lam, source="los-rate+tgo")


def t_go_from_range_rate(range_m: float, closing_mps: float) -> float | None:
    """``t_go = R / Vc`` (Palumbo eq. 41) -- the form for which ``φ_h = atan(λ̇·t_go)`` is exact.

    Returns ``None`` when not closing, so an opening geometry can never manufacture a terminal cue.
    """
    if closing_mps is None or closing_mps <= 0.0 or range_m is None or range_m <= 0.0:
        return None
    return float(range_m) / float(closing_mps)
