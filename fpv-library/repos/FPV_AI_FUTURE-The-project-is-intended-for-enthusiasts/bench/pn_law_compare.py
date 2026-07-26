"""PN-LAW comparison: command ⊥ LOS (our TPN/IPN-family law) vs command ⊥ VELOCITY (PPN).

Motivated by Sozinov & Gorevich (Almaz-Antey 2022) + the open literature (docs/GUIDANCE_LAW_SCIENCE.md):
methods that form the command ORTHOGONAL TO THE LOS (TPN/IPN) suffer a sharp TERMINAL acceleration blow-up
against a maneuvering target, while methods orthogonal to the MISSILE VELOCITY (PPN) stay bounded. Our
`bearing_rate.py` law `a = N·Vc·λ̇` is ⊥ LOS -> the blow-up class -> the likely mechanism behind the terminal
ROE aborts / transient over-demand we saw in launch_and_forget.

This closes the loop on our OWN geometry (intercept from below, a weaving overhead target, the honest 0.84 g
quad wall) and measures, per law: the PEAK and TERMINAL demanded-g (pre-clamp -- the real envelope demand)
and the CPA. It needs no pipeline change -- both laws are computed vectorially from the same truth geometry,
so we compare the LAW FORM, not the sensor.

    TPN/IPN family (ours):   a_cmd = N · Vc · (ω_los × ê_los)          (⊥ LOS, scaled by closing speed)
    PPN:                     a_cmd = N · (ω_los × V_interceptor)       (⊥ velocity, scaled by own speed)

Run:  PYTHONPATH=.:fpv python3 -m fpv_ai.bench.pn_law_compare
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

_G = 9.81
_THETA_MAX = math.radians(40.0)          # 0.84 g quad wall


@dataclass
class PnConfig:
    int_pos: tuple = (0.0, 0.0, 0.0)
    int_vel: tuple = (0.0, 0.0, 34.0)     # climbing from below
    tgt_pos: tuple = (6.0, 3.0, 105.0)    # overhead + small offset
    tgt_vel: tuple = (-1.0, 0.5, -6.0)    # descending
    weave_g: float = 0.6                  # target lateral weave amplitude (g) -- the maneuver
    weave_hz: float = 0.5
    N: float = 4.0
    cap_m: float = 1.5
    climb_accel: float = 4.0              # sustain climb
    dt: float = 1.0 / 200.0
    tmax: float = 6.0


@dataclass
class PnResult:
    law: str
    hit: bool
    cpa_m: float
    term_demand_g: float                  # max demanded g in the terminal window r∈[3,20] m (pre-singularity)
    v_char: float                         # characteristic control velocity Vхар.упр = ∫|a_applied| dt (m/s)
    frac_over_envelope: float             # fraction of terminal-window ticks whose demand exceeded 0.84 g


def _guide(law, rel, iv, tv, N):
    r = float(np.linalg.norm(rel)); los = rel / (r + 1e-9)
    vrel = tv - iv
    vc = max(float(np.dot(-vrel, los)), 1.0)          # closing speed
    omega = np.cross(rel, vrel) / max(r * r, 1e-6)    # LOS angular-velocity vector
    if law == "TPN":                                   # ⊥ LOS, scaled by closing speed (our family)
        return N * vc * np.cross(omega, los)
    # PPN: ⊥ velocity, scaled by own speed
    return N * np.cross(omega, iv)


def run(cfg: PnConfig, law: str) -> PnResult:
    ip = np.array(cfg.int_pos, float); iv = np.array(cfg.int_vel, float)
    tp = np.array(cfg.tgt_pos, float); tv0 = np.array(cfg.tgt_vel, float)
    res = PnResult(law=law, hit=False, cpa_m=1e9, term_demand_g=0.0, v_char=0.0, frac_over_envelope=0.0)
    rel0 = tp - ip; wax = np.cross(rel0, [0, 0, 1.0]); wax /= (np.linalg.norm(wax) + 1e-9)
    term_dg = []; over = term_ticks = 0; vchar = 0.0
    a_max = _G * math.tan(_THETA_MAX)                  # 0.84 g
    for step in range(int(cfg.tmax / cfg.dt)):
        t = step * cfg.dt
        rel = tp - ip; r = float(np.linalg.norm(rel))
        res.cpa_m = min(res.cpa_m, r)
        if r < cfg.cap_m:
            res.hit = True; break
        tv = tv0 + cfg.weave_g * _G * math.sin(2 * math.pi * cfg.weave_hz * t) * wax
        a_cmd = _guide(law, rel, iv, tv, cfg.N)
        dg = float(np.linalg.norm(a_cmd)) / _G         # demanded g (pre-clamp)
        if 3.0 <= r <= 20.0:                           # terminal window, BEFORE the r->0 singularity
            term_dg.append(dg); term_ticks += 1
            if dg > a_max / _G:
                over += 1
        amag = float(np.linalg.norm(a_cmd))            # clamp to the quad envelope + integrate control energy
        if amag > a_max:
            a_cmd *= a_max / amag
        vchar += float(np.linalg.norm(a_cmd)) * cfg.dt
        a_cmd = a_cmd + cfg.climb_accel * np.array([0, 0, 1.0])
        iv = iv + a_cmd * cfg.dt; ip = ip + iv * cfg.dt
        tp = tp + tv * cfg.dt
    res.term_demand_g = max(term_dg) if term_dg else 0.0
    res.v_char = vchar
    res.frac_over_envelope = over / max(term_ticks, 1)
    return res


def main() -> None:  # pragma: no cover
    print("intercept-from-below, weaving overhead target, 0.84 g quad wall")
    print("(term-demand = max demanded g in r∈[3,20]m before impact; Vхар = control energy; %%over = ticks past 0.84g)\n")
    for w in (0.0, 0.4, 0.8, 1.2):
        print("weave %.1f g:" % w)
        for law in ("TPN", "PPN"):
            r = run(PnConfig(weave_g=w), law)
            print("   %-4s hit=%-5s CPA=%5.2fm  term-demand=%5.1f g  Vхар=%5.1f m/s  over=%3.0f%%" % (
                r.law, r.hit, r.cpa_m, r.term_demand_g, r.v_char, 100 * r.frac_over_envelope))


if __name__ == "__main__":
    main()
