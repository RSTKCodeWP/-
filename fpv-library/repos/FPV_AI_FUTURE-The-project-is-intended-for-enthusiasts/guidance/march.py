"""MARCH tracker — inertial bearing dead-reckoning so the gimbal keeps pointing where the target WILL be.

The measured gap (2026-07-20, `test_clutter_and_side_aspect...`): a side-aspect CROSSING target that drops
lock for even a moment crosses out of frame and is never reacquired, because a centroid-tracking gimbal that
has no centroid just HOLDS STILL. From-below overhead targets survive lock gaps (they barely move in
bearing); a crosser does not. MARCH replaces "hold still on a lost lock" with "dead-reckon the target's
inertial bearing and slew to where it should be" — and re-ID the reappearing blob against that prediction so
a confuser cannot steal the track.

This is the vector-space core of the angular MARCH proven in `fpv_ai/bench/march_sim.py` (which recovers a
target 99° off-frame). It runs the α-β filter directly on the unit bearing vector, so it is singularity-free
across the whole dome — overhead (el≈0, where az is undefined) through side-aspect — which the flight loop
spans. See `docs/MARCH_PROTOCOL.md` for the derivation.

    predict:  est_dir ← rotate(est_dir, est_ω·dt)          (dead-reckon the bearing forward)
    update:   residual = axis·angle from est_dir → measured;  est_dir ← rotate(est_dir, α·residual);
              est_ω ← est_ω + β·residual/dt                  (α-β, on the sphere)
    states:   TRACK → COAST(brief) → MARCH(slew to prediction) → LOST(give up)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np


class MarchState(str, Enum):
    TRACK = "TRACK"      # a fresh measurement this tick
    COAST = "COAST"      # brief measurement gap, still centred on the estimate
    MARCH = "MARCH"      # dead-reckoning: slew to the predicted bearing to reacquire
    LOST = "LOST"        # gap exceeded the budget; hold and stop chasing


@dataclass(frozen=True)
class MarchConfig:
    alpha: float = 0.5                       # α-β position gain (0..1)
    beta: float = 0.1                        # α-β velocity gain
    coast_s: float = 0.12                    # hold on the estimate this long before declaring MARCH
    march_budget_s: float = 2.0              # give up (LOST) after this long with no reacquire
    reid_tol_rad: float = math.radians(6.0)  # a reappearing blob must match the marched prediction within this
    max_omega_radps: float = math.radians(120.0)  # sanity cap on the estimated bearing rate


@dataclass(frozen=True)
class MarchStep:
    command_dir: np.ndarray                  # unit vector the gimbal should point at THIS tick
    predicted_dir: np.ndarray                # the dead-reckoned target bearing
    state: MarchState
    reacquired: bool                         # became TRACK from MARCH/LOST this tick
    uncertainty_deg: float                   # grows with the gap; 0 while tracking


def _unit(v):
    v = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else np.array([0.0, 0.0, 1.0])


def _rotate(v, axis, ang):
    """Rodrigues: rotate v about (unit) axis by ang."""
    if ang == 0.0:
        return v
    c, s = math.cos(ang), math.sin(ang)
    return v * c + np.cross(axis, v) * s + axis * float(axis @ v) * (1.0 - c)


def _axis_angle(a, b):
    """Rotation carrying unit a onto unit b: (axis, angle)."""
    d = max(-1.0, min(1.0, float(a @ b)))
    ang = math.acos(d)
    ax = np.cross(a, b)
    n = float(np.linalg.norm(ax))
    if n < 1e-9:                              # parallel or antiparallel -> no well-defined axis
        return np.array([0.0, 0.0, 1.0]), 0.0 if d > 0 else math.pi
    return ax / n, ang


class MarchTracker:
    """Dead-reckons a target's inertial bearing and, on a lock gap, commands the gimbal to the prediction.

    Frame-agnostic: feed it and read back UNIT DIRECTION VECTORS in one consistent inertial frame (the flight
    loop's world frame). ``update`` takes the measured target bearing when the seeker has a lock, or ``None``
    when it does not.
    """

    def __init__(self, config: MarchConfig | None = None) -> None:
        self.cfg = config or MarchConfig()
        self._dir: np.ndarray | None = None      # estimated bearing (unit)
        self._omega = np.zeros(3)                # estimated bearing angular velocity (rad/s, ⟂ to _dir)
        self._state = MarchState.LOST
        self._t_since_meas = 0.0

    @property
    def state(self) -> MarchState:
        return self._state

    @property
    def initialized(self) -> bool:
        return self._dir is not None

    def start(self, initial_dir) -> None:
        """LOBL enrolment: seed the estimate on the target the operator/seeker just locked."""
        self._dir = _unit(initial_dir)
        self._omega = np.zeros(3)
        self._state = MarchState.TRACK
        self._t_since_meas = 0.0

    def update(self, dt: float, measured_dir) -> MarchStep:
        cfg = self.cfg
        if self._dir is None:
            if measured_dir is None:
                d = np.array([0.0, 0.0, 1.0])
                return MarchStep(d, d, MarchState.LOST, False, 0.0)
            self.start(measured_dir)
            return MarchStep(self._dir.copy(), self._dir.copy(), MarchState.TRACK, False, 0.0)

        # --- PREDICT: dead-reckon the bearing forward every tick ---
        w = float(np.linalg.norm(self._omega))
        if w > 1e-9:
            self._dir = _unit(_rotate(self._dir, self._omega / w, w * dt))
        self._t_since_meas += dt

        reacquired = False
        measured = False
        if measured_dir is not None:
            m = _unit(measured_dir)
            # re-ID: while tracking/coasting accept any lock; once MARCHing, the reappearing bearing must
            # match the prediction (so a confuser elsewhere in frame cannot capture the track).
            gate_ok = self._state in (MarchState.TRACK, MarchState.COAST) or \
                _axis_angle(self._dir, m)[1] <= cfg.reid_tol_rad
            if gate_ok:
                axis, ang = _axis_angle(self._dir, m)
                if ang > 0.0:
                    self._dir = _unit(_rotate(self._dir, axis, cfg.alpha * ang))
                    self._omega = self._omega + axis * (cfg.beta * ang / max(dt, 1e-6))
                    ow = float(np.linalg.norm(self._omega))
                    if ow > cfg.max_omega_radps:          # sanity-cap the estimated rate
                        self._omega *= cfg.max_omega_radps / ow
                if self._state in (MarchState.MARCH, MarchState.LOST):
                    reacquired = True
                self._state = MarchState.TRACK
                self._t_since_meas = 0.0
                measured = True

        if not measured:
            if self._state == MarchState.TRACK:
                self._state = MarchState.COAST
            if self._state == MarchState.COAST and self._t_since_meas > cfg.coast_s:
                self._state = MarchState.MARCH
            if self._state == MarchState.MARCH and self._t_since_meas > cfg.march_budget_s:
                self._state = MarchState.LOST

        # command: TRACK/COAST/MARCH -> point at the prediction; LOST -> hold the last estimate (stop chasing)
        # uncertainty grows with the gap: a 2° floor + how far the estimate has dead-reckoned since the last fix
        unc = 0.0 if self._state == MarchState.TRACK else 2.0 + math.degrees(w) * self._t_since_meas
        return MarchStep(self._dir.copy(), self._dir.copy(), self._state, reacquired, unc)
