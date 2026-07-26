"""MARCH protocol -- inertial target-trajectory estimation + slew-to-cue reacquisition BEYOND the FOV.

The problem it solves: a strapdown/gimbaled seeker has a NARROW instantaneous field of view (FT640 ~48°,
half-FOV ~24°). When the target briefly disappears (occluded by a cloud, or jinks out of frame) it moves
to a bearing OUTSIDE the current FOV. Expanding a pixel gate cannot find it -- it is off-frame. You must
physically POINT the sensor to where the target SHOULD be. That is MARCH.

SCIENTIFIC BASIS (see docs/MARCH_PROTOCOL.md for the full derivation)
--------------------------------------------------------------------
1. INERTIAL LOS. The target pixel gives a bearing in the CAMERA frame. Fusing the gimbal angles (encoders)
   and the body gyro (FC IMU) rotates that bearing into the WORLD (inertial) frame -> the target's true
   line-of-sight direction u(t), decoupled from our own rotation. (Here: gimbal truth + measurement noise.)
2. TRAJECTORY ESTIMATE. An alpha-beta filter on the inertial bearing (az, el) estimates position AND
   angular velocity (ȧz, ėl). This is "where is it going", not just "where is it".
3. DEAD-RECKON PREDICT. While unseen, propagate û(t) = last + rate·Δt. Constant-velocity dead reckoning;
   a maneuver DURING the gap degrades it (honest limit).
4. UNCERTAINTY CONE. The predicted bearing's 1σ radius GROWS with time-unseen: σ(Δt) = σ0 + q·Δt. The
   gimbal search sweep widens with the cone.
5. SLEW-TO-CUE. Command the gimbal boresight to the predicted bearing (rate + limit bounded), sweeping the
   uncertainty cone. Reachable within the gimbal's mechanical envelope.
6. RE-ID (LOBL). When a blob re-enters the swept FOV, verify it matches the frozen study reference
   (aspect / signature / silhouette) before re-locking -> we grab the SAME target, not clutter.

This module is the ANGULAR-domain core (the domain MARCH lives in): the target's bearing on the sky dome,
the gimbal pointing, the FOV circle. It closes the loop honestly (rate-limited gimbal, growing uncertainty,
constant-velocity dead reckoning) and logs every tick for visualization.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import numpy as np

_HALF_FOV = math.radians(24.0)          # FT640 ~48° full -> 24° half
_D2R = math.pi / 180.0
_R2D = 180.0 / math.pi


def _dir(az, el):
    """Unit direction on the sky dome: el = off-vertical angle (0=overhead), az = azimuth."""
    se, ce = math.sin(el), math.cos(el)
    return np.array([se * math.cos(az), se * math.sin(az), ce])


def _azel(u):
    u = u / (np.linalg.norm(u) + 1e-9)
    return math.atan2(u[1], u[0]), math.acos(max(-1.0, min(1.0, u[2])))


def _ang(u, v):
    return math.acos(max(-1.0, min(1.0, float(np.dot(u, v)) / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-9))))


def _slew(g, cmd, rate_rad, dt):
    """Rotate gimbal direction g toward cmd, rate-limited (rad/s). Singularity-free (Rodrigues)."""
    ang = _ang(g, cmd)
    if ang < 1e-6:
        return g.copy()
    applied = min(ang, rate_rad * dt)
    axis = np.cross(g, cmd); axis /= (np.linalg.norm(axis) + 1e-9)
    gg = (g * math.cos(applied) + np.cross(axis, g) * math.sin(applied)
          + axis * float(np.dot(axis, g)) * (1.0 - math.cos(applied)))
    return gg / (np.linalg.norm(gg) + 1e-9)


@dataclass
class MarchConfig:
    az0_deg: float = -46.0
    el0_deg: float = 30.0
    waz_dps: float = 72.0                # target azimuth rate (fast crosser)
    wel_dps: float = 7.0
    occl_start_s: float = 1.4            # target hidden (cloud) window -> forces off-FOV loss
    occl_end_s: float = 2.25
    gimbal_rate_dps: float = 130.0       # servo gimbal slew limit
    gimbal_el_max_deg: float = 72.0      # mechanical: can look this far off vertical
    meas_noise_deg: float = 0.4          # inertial-bearing measurement noise (post gyro-fusion)
    alpha: float = 0.55                  # alpha-beta position gain
    beta: float = 0.10                   # alpha-beta velocity gain
    sigma0_deg: float = 1.5              # uncertainty at loss
    q_dps: float = 9.0                   # uncertainty growth rate (deg per s unseen)
    coast_s: float = 0.12                # brief hold before declaring MARCH
    march_budget_s: float = 2.0          # give up MARCH after this
    reid_tol_deg: float = 8.0            # re-lock only if reappears within this of the predicted bearing
    dt: float = 1.0 / 100.0
    tmax: float = 4.0
    seed: int = 3


@dataclass
class MarchResult:
    reacquired: bool = False
    t_reacquire_s: float | None = None
    max_offframe_deg: float = 0.0        # how far off-FOV the target got (proves gate-expansion can't work)
    log: list = field(default_factory=list)


def _target_dir(t, cfg):
    az = (cfg.az0_deg + cfg.waz_dps * t) * _D2R
    el = (cfg.el0_deg + cfg.wel_dps * t) * _D2R
    el = max(0.05, min(cfg.gimbal_el_max_deg * _D2R * 1.2, el))
    return _dir(az, el)


def run_march(cfg: MarchConfig | None = None, *, march: bool = True) -> MarchResult:
    cfg = cfg or MarchConfig()
    rng = np.random.default_rng(cfg.seed)
    res = MarchResult()

    g = _target_dir(0.0, cfg)                  # gimbal starts on the target (LOBL enrolled)
    est_az, est_el = _azel(g); est_vaz = est_vel = 0.0
    state = "TRACK"; t_since_meas = 0.0
    el_max = cfg.gimbal_el_max_deg * _D2R
    tol = cfg.reid_tol_deg * _D2R

    for step in range(int(cfg.tmax / cfg.dt)):
        t = step * cfg.dt
        tu = _target_dir(t, cfg)                # true target direction
        occluded = cfg.occl_start_s <= t <= cfg.occl_end_s
        off = _ang(g, tu)                        # angular gap gimbal->target
        in_fov = off < _HALF_FOV
        visible = in_fov and not occluded

        # --- PREDICT (every tick): dead-reckon the inertial-bearing estimate forward ---
        est_az += est_vaz * cfg.dt
        est_el += est_vel * cfg.dt
        t_since_meas += cfg.dt

        measured = False
        if visible:
            maz = _azel(tu)[0] + rng.normal(0, cfg.meas_noise_deg * _D2R)
            mel = _azel(tu)[1] + rng.normal(0, cfg.meas_noise_deg * _D2R)
            # re-ID (LOBL proxy): reappearing bearing must match the marched prediction; always OK while tracking
            reid_ok = state in ("TRACK", "COAST") or _ang(_dir(maz, mel), _dir(est_az, est_el)) < tol
            if reid_ok:                          # --- UPDATE (alpha-beta) ---
                raz, rel = maz - est_az, mel - est_el
                est_az += cfg.alpha * raz; est_vaz += cfg.beta * raz / cfg.dt
                est_el += cfg.alpha * rel; est_vel += cfg.beta * rel / cfg.dt
                if state in ("MARCH", "LOST"):
                    res.reacquired = True
                    res.t_reacquire_s = res.t_reacquire_s or t
                state = "TRACK"; t_since_meas = 0.0; measured = True

        if not measured:                        # --- no usable measurement: COAST -> MARCH ---
            if state == "TRACK":
                state = "COAST"
            if state == "COAST" and t_since_meas > cfg.coast_s:
                state = "MARCH"
            res.max_offframe_deg = max(res.max_offframe_deg, off * _R2D)
            if state == "MARCH" and t_since_meas > cfg.march_budget_s:
                state = "LOST"

        # command: TRACK/COAST -> centre the estimate; MARCH(on) -> slew to the predicted bearing; else hold
        if state in ("TRACK", "COAST") or (state == "MARCH" and march):
            cmd = _dir(est_az, est_el)
        else:
            cmd = g                              # baseline / LOST: hold
        g = _slew(g, cmd, cfg.gimbal_rate_dps * _D2R, cfg.dt)
        gaz, gel = _azel(g)
        if gel > el_max:
            g = _dir(gaz, el_max); gaz, gel = _azel(g)

        taz, tel = _azel(tu)
        unc = (cfg.sigma0_deg + cfg.q_dps * t_since_meas) if state in ("MARCH", "COAST", "LOST") else 0.0
        res.log.append(dict(t=round(t, 3), taz=round(taz * _R2D, 2), tel=round(tel * _R2D, 2),
                            gaz=round(gaz * _R2D, 2), gel=round(gel * _R2D, 2),
                            paz=round(est_az * _R2D, 2), pel=round(est_el * _R2D, 2),
                            state=state, in_fov=bool(in_fov), occl=bool(occluded),
                            off=round(off * _R2D, 2), unc=round(unc, 2)))
    return res


def main() -> None:  # pragma: no cover
    for m in (False, True):
        r = run_march(march=m)
        tag = "MARCH ON " if m else "MARCH OFF"
        print("%s -> reacquired=%-5s t=%s  max_offframe=%.1f°  (FOV half=24°)" % (
            tag, r.reacquired, ("%.2fs" % r.t_reacquire_s) if r.t_reacquire_s else "--", r.max_offframe_deg))


if __name__ == "__main__":
    main()
