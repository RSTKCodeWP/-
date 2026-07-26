"""PASSIVE RANGE from bearings + our own maneuver — a size-free range/Vc source for the commit gate.

Our thermal seeker is monocular: it measures BEARING only. Two independent ways to recover range:

  * SUBTENSE (``fpv.seeker.subtense_range``): range from the target's angular extent. Direct and low-latency,
    but it must ASSUME the target's physical span — for an unknown winged UAV that assumption IS a fabrication,
    and a wrong span biases range proportionally.
  * THIS module: range from PARALLAX. Bearings-only range is unobservable while we fly straight, but our own
    lateral maneuver moves the observer, and that motion is known exactly from our own INS. The resulting
    parallax makes range and closing speed observable through an EKF. **Size-free** — it assumes nothing about
    the target's dimensions, so it is an independent cross-check on subtense.

Measured on our own from-below geometry (`fpv_ai/bench/passive_range_sim.py`, 6 seeds, at a 40 m gate):
straight run 66% range error (unobservable) -> on-course weave at full 0.84 g authority 28%. Real, but COARSE.

**Why the trust gate is not the filter's covariance.** On a straight run this EKF's own σr collapses to ~12%
while its estimate is ~66% wrong — textbook bearings-only FALSE CONVERGENCE. An estimate that sounds confident
while being fabricated is strictly worse than one that admits it is fabricated. So the estimate is released
ONLY when we have EARNED enough parallax, computed by double-integrating our own accelerometer — a physical
precondition observable independently of the filter. **No maneuver -> no range, whatever the filter claims.**
(Same principle as the two-press human authority: authority comes from outside the estimator.)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PassiveRangeConfig:
    init_range_m: float = 120.0          # prior range when we have no information at all
    init_range_sigma_m: float = 90.0     # ...held very loosely
    init_vel_sigma_mps: float = 12.0
    bearing_sigma_rad: float = math.radians(0.3)
    accel_process_sigma: float = 1.0     # unmodelled target acceleration (CV target assumption)
    pos_process_sigma: float = 0.3
    parallax_min_deg: float = 8.0        # the trust gate: parallax we must EARN before releasing a range
    # The parallax requirement is evaluated against a FIXED range scale -- the range at which the decision is
    # actually being made (the commit gate) -- and never against the filter's own range estimate. Dividing the
    # baseline by the estimate would make the "filter-independent" gate secretly filter-dependent, and in the
    # dangerous direction: a filter that under-estimates range would inflate the apparent parallax and open
    # the gate it has not earned. A fixed scale cannot be talked into opening.
    gate_reference_range_m: float = 50.0
    min_closing_mps: float = 3.0         # below this we are not closing -> no t_go


@dataclass(frozen=True)
class PassiveRangeEstimate:
    """A passively-derived range/closing, released only when the parallax gate is satisfied."""

    range_m: float | None                # None unless trusted
    closing_mps: float | None            # None unless trusted
    t_go_s: float | None                 # None unless trusted AND genuinely closing
    parallax_deg: float                  # parallax earned so far from our own maneuver
    trusted: bool
    source: str                          # "passive-parallax" | "unearned-parallax" | "inactive"
    raw_range_m: float                   # the filter's number even when untrusted (observability only)


# FRAME CONTRACT. The seeker reports bearings measured FROM THE BORESIGHT (`fpv.seeker.geometry`):
#     az = atan2(dx, f)      el = atan2(-dy, f)
# so the LOS direction is proportional to (tan az, tan el, 1) with **+z along the boresight**. The state and
# the caller's ``own_accel_xyz`` MUST use that same axis convention. For our up-looking camera the boresight
# is world-up, so world (x, y, up) satisfies it directly. Do NOT feed spherical (az-from-x-axis) angles here.


def _bearing_unit(az: float, el: float) -> np.ndarray:
    v = np.array([math.tan(az), math.tan(el), 1.0])
    return v / np.linalg.norm(v)


def _bearing_of(r: np.ndarray) -> np.ndarray:
    return np.array([math.atan2(r[0], r[2]), math.atan2(r[1], r[2])])


def _jacobian(r: np.ndarray) -> np.ndarray:
    x, y, z = float(r[0]), float(r[1]), float(r[2])
    dxz = x * x + z * z + 1e-9
    dyz = y * y + z * z + 1e-9
    H = np.zeros((2, 6))
    H[0, 0] = z / dxz              # d az / dx
    H[0, 2] = -x / dxz             # d az / dz
    H[1, 1] = z / dyz              # d el / dy
    H[1, 2] = -y / dyz             # d el / dz
    return H


class PassiveRangeEstimator:
    """Bearings-only EKF on the RELATIVE state, driven by our own known acceleration.

    State ``x = [r; v]`` — target position and velocity relative to us, in the local inertial frame.
        predict:  r += v·dt ;  v += (−a_own)·dt      (a_own known from INS; target accel -> process noise)
        update:   z = (az, el)                        (bearing only, no range)

    A non-zero ``a_own`` is what makes the range observable; with ``a_own = 0`` the relative motion is
    constant-velocity and range stays unobservable no matter how many bearings we integrate.
    """

    def __init__(self, config: PassiveRangeConfig | None = None) -> None:
        self.cfg = config or PassiveRangeConfig()
        self._x: np.ndarray | None = None
        self._P: np.ndarray | None = None
        self._los0: np.ndarray | None = None
        self._dev = np.zeros(3)          # our deviation from the no-maneuver straight path
        self._dvel = np.zeros(3)         # ...and its rate. Both are pure INS double-integration.

    @property
    def initialized(self) -> bool:
        return self._x is not None

    def _parallax_deg(self) -> float:
        """Cross-LOS baseline earned by our own maneuver, subtended at the FIXED decision scale.

        Depends only on our own accelerometer (double-integrated) and a constant — nothing the filter
        produces can raise it.
        """
        if self._los0 is None:
            return 0.0
        perp = self._dev - float(self._dev @ self._los0) * self._los0
        return math.degrees(math.atan2(float(np.linalg.norm(perp)),
                                       max(self.cfg.gate_reference_range_m, 1e-6)))

    def reset(self) -> None:
        self._x = self._P = self._los0 = None
        self._dev = np.zeros(3)
        self._dvel = np.zeros(3)

    def update(self, dt: float, az_rad: float, el_rad: float,
               own_accel_xyz: tuple[float, float, float],
               own_velocity_xyz: tuple[float, float, float] | None = None) -> PassiveRangeEstimate:
        cfg = self.cfg
        a_own = np.asarray(own_accel_xyz, dtype=float)

        if self._x is None:                                  # first bearing fixes direction, never range
            los = _bearing_unit(az_rad, el_rad)
            self._los0 = los
            self._x = np.zeros(6)
            self._x[0:3] = cfg.init_range_m * los
            # INS prior on relative velocity: we know our own, and a slow target is the neutral assumption.
            if own_velocity_xyz is not None:
                self._x[3:6] = -np.asarray(own_velocity_xyz, dtype=float)
            self._P = np.diag([cfg.init_range_sigma_m] * 3 + [cfg.init_vel_sigma_mps] * 3) ** 2
            return self._emit()

        # --- our own deviation from a straight path (INS only -- independent of the filter) -------------
        self._dev = self._dev + self._dvel * dt
        self._dvel = self._dvel + a_own * dt

        # --- EKF predict, with our own acceleration as the known control input ---------------------------
        F = np.eye(6)
        F[0:3, 3:6] = np.eye(3) * dt
        self._x = F @ self._x
        self._x[3:6] -= a_own * dt
        q = np.diag([cfg.pos_process_sigma] * 3 + [cfg.accel_process_sigma] * 3) ** 2 * dt
        self._P = F @ self._P @ F.T + q

        # --- EKF update from the bearing ----------------------------------------------------------------
        innov = np.array([az_rad, el_rad]) - _bearing_of(self._x[0:3])
        innov[0] = (innov[0] + math.pi) % (2 * math.pi) - math.pi
        innov[1] = (innov[1] + math.pi) % (2 * math.pi) - math.pi
        H = _jacobian(self._x[0:3])
        R = np.diag([cfg.bearing_sigma_rad, cfg.bearing_sigma_rad]) ** 2
        S = H @ self._P @ H.T + R
        try:
            K = self._P @ H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:                        # singular -> skip the update, keep predicting
            return self._emit()
        self._x = self._x + K @ innov
        self._P = (np.eye(6) - K @ H) @ self._P
        return self._emit()

    def _emit(self) -> PassiveRangeEstimate:
        r_vec = self._x[0:3]
        rng = float(np.linalg.norm(r_vec))
        parallax = self._parallax_deg()
        los = r_vec / (rng + 1e-9)
        closing = float(-(self._x[3:6] @ los))

        if parallax < self.cfg.parallax_min_deg:
            # The filter has a number and may even sound confident about it. We have not earned it.
            return PassiveRangeEstimate(None, None, None, parallax, False, "unearned-parallax", rng)

        t_go = rng / closing if closing >= self.cfg.min_closing_mps else None
        return PassiveRangeEstimate(rng, closing, t_go, parallax, True, "passive-parallax", rng)
