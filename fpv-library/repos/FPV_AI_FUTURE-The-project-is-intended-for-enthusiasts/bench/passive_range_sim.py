"""PASSIVE RANGING by own-maneuver + EKF — make range observable from a bearings-only (monocular) seeker.

The fundamental gap (docs/GUIDANCE_LAW_SCIENCE.md): a passive monocular seeker measures only the BEARING
(az, el) to the target, never range. Bearings-only is UNOBSERVABLE in range from a straight run (a near-slow
and a far-fast target trace the same bearing history). We currently fabricate/schedule Vc and range because
of this.

The fix, with NO new hardware: the interceptor's OWN maneuver creates parallax that makes the target's range
AND relative velocity observable via an Extended Kalman Filter. The interceptor's acceleration is KNOWN (we
command it), so it enters the relative dynamics as a known input; a NON-zero maneuver breaks the range
scale-ambiguity. (Daugherty 2019; AIAA G003003; Ning 2024.)

EKF (relative state, inertial): x = [r; v] = (target − interceptor) position & velocity.
    predict:  r += v·dt ;  v += (−a_int)·dt        (a_int known; target accel → process noise Q)
    measure:  z = bearing(r) = [az, el]             (2 angles, NO range)  → EKF update

This module proves: STRAIGHT interceptor → range estimate does not converge (unobservable); MANEUVERING
interceptor → the EKF pulls range/Vc to truth. Then measured Vc feeds a TRUE-Vc PN and measured range/t_go
gives a real terminal cue → a formal COMMITTED, replacing the fabricated range.

Run:  PYTHONPATH=.:fpv python3 -m fpv_ai.bench.passive_range_sim
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

_G = 9.81

# The honest trust gate. The bearings-only EKF is DEMONSTRABLY overconfident: on a straight run its own σr
# collapses to ~12% while the range estimate is ~66% wrong (false convergence -- a known bearings-only TMA
# pathology). So we must NOT gate the commit on the filter's covariance. We gate instead on the parallax we
# have actually EARNED with our own maneuver, which we know exactly from our own INS: no maneuver -> no range,
# whatever the filter claims.
PARALLAX_MIN_DEG = 8.0


@dataclass
class PassiveCfg:
    int_pos: tuple = (0.0, 0.0, 0.0)
    int_vel: tuple = (6.0, 9.0, 32.0)
    tgt_pos: tuple = (45.0, 60.0, 150.0)  # acquire far -> track & maneuver through the approach
    tgt_vel: tuple = (2.0, -3.0, -6.0)
    maneuver_g: float = 0.6               # lateral accel amplitude within the 0.84 g wall (parallax source)
    maneuver_mode: str = "weave"          # "weave" = bounded on-course S (realistic); "turn" = sustained bank
    bearing_noise_deg: float = 0.3        # seeker angular noise
    range_init_factor: float = 1.5        # start the filter's range guess WRONG (no range info at t0)
    commit_gate_m: float = 40.0           # the range at which we want a usable range/Vc for the commit cue
    dt: float = 1.0 / 50.0
    tmax: float = 7.0
    seed: int = 1


@dataclass
class PassiveResult:
    maneuvered: bool
    range_err_gate_pct: float             # |r̂ − r| / r when range first crosses the commit gate, %
    vc_err_gate_pct: float                # closing-speed estimate error at the commit gate, %
    range_err_final_pct: float            # |r̂ − r| / r at the end, %
    sigma_r_gate_pct: float               # the FILTER'S OWN 1-σ range uncertainty at the gate, % of range
    baseline_m: float                     # max cross-LOS interceptor displacement (parallax baseline)
    parallax_deg: float                   # parallax angle EARNED by our own maneuver (baseline / range)
    trust_range: bool                     # honest gate: earned parallax exceeds PARALLAX_MIN_DEG
    converged: bool                       # range error at the commit gate < 25% (coarse-but-usable)
    log: list                             # per-tick (t, r_true, r_est, vc_true, vc_est)


def _bearing(r):
    az = math.atan2(r[1], r[0])
    el = math.atan2(r[2], math.hypot(r[0], r[1]))
    return np.array([az, el])


def _H(r):
    x, y, z = r
    rr2 = x * x + y * y + z * z
    rho2 = x * x + y * y
    rho = math.sqrt(rho2) + 1e-9
    Hp = np.zeros((2, 3))
    Hp[0, 0] = -y / (rho2 + 1e-9); Hp[0, 1] = x / (rho2 + 1e-9)          # d az / d r
    Hp[1, 0] = -z * x / (rr2 * rho + 1e-9); Hp[1, 1] = -z * y / (rr2 * rho + 1e-9); Hp[1, 2] = rho / (rr2 + 1e-9)
    return np.hstack([Hp, np.zeros((2, 3))])                             # velocity block = 0


def run_passive(cfg: PassiveCfg | None = None, *, maneuver: bool = True) -> PassiveResult:
    cfg = cfg or PassiveCfg()
    rng = np.random.default_rng(cfg.seed)
    ip = np.array(cfg.int_pos, float); iv = np.array(cfg.int_vel, float)
    ip0 = ip.copy(); iv0 = iv.copy()
    tp = np.array(cfg.tgt_pos, float); tv = np.array(cfg.tgt_vel, float)
    lat = np.cross(iv, [0, 0, 1.0]); lat /= (np.linalg.norm(lat) + 1e-9)    # cross-velocity turn axis

    # EKF init: bearing is known at t0; RANGE is guessed wrong (no range info in one bearing). Velocity gets a
    # realistic INS prior: we know our own velocity iv, so seed v_rel ≈ -iv (target ~slow) -- the filter then
    # only has to refine range + the target's motion, which the maneuver makes observable.
    r0 = tp - ip
    b0 = _bearing(r0)
    rng_guess = float(np.linalg.norm(r0)) * cfg.range_init_factor
    x = np.zeros(6)
    x[0:3] = rng_guess * np.array([math.cos(b0[1]) * math.cos(b0[0]),
                                   math.cos(b0[1]) * math.sin(b0[0]), math.sin(b0[1])])
    x[3:6] = -iv                                                            # INS prior on relative velocity
    P = np.diag([90.0, 90.0, 90.0, 12.0, 12.0, 12.0]) ** 2
    bnr = math.radians(cfg.bearing_noise_deg)
    R = np.diag([bnr, bnr]) ** 2
    q = 1.0
    Q = np.diag([0.3, 0.3, 0.3, q, q, q]) ** 2 * cfg.dt
    log = []; baseline = 0.0; gate = None

    for step in range(int(cfg.tmax / cfg.dt)):
        t = step * cfg.dt
        # interceptor commanded acceleration = the KNOWN control input that creates parallax.
        #   "weave" -> bounded on-course S (one sine over the window: swings off course and back, stays on the
        #              intercept on average) -- realistic but modest baseline.
        #   "turn"  -> sustained one-sided bank: maximal parallax, but it curves away from the intercept
        #              (the observability-vs-control tension) -- the accuracy ceiling, not an on-course maneuver.
        if not maneuver:
            a_int = np.zeros(3)
        elif cfg.maneuver_mode == "turn":
            a_int = cfg.maneuver_g * _G * lat
        else:  # a(t)=A·cos(ωt): velocity AND displacement return to zero at t=tmax -> a true on-course S
            a_int = cfg.maneuver_g * _G * math.cos(2 * math.pi * t / cfg.tmax) * lat

        # --- EKF predict (with the known control input) ---
        F = np.eye(6); F[0:3, 3:6] = np.eye(3) * cfg.dt
        x = F @ x
        x[3:6] += -a_int * cfg.dt
        P = F @ P @ F.T + Q

        # --- truth propagate ---
        iv = iv + a_int * cfg.dt; ip = ip + iv * cfg.dt
        tp = tp + tv * cfg.dt
        r_true = tp - ip; v_true = tv - iv

        # cross-LOS displacement of the interceptor from its no-maneuver straight path = the parallax baseline
        straight = ip0 + iv0 * ((step + 1) * cfg.dt)
        los0 = r0 / (np.linalg.norm(r0) + 1e-9)
        d = ip - straight
        baseline = max(baseline, float(np.linalg.norm(d - np.dot(d, los0) * los0)))

        # --- EKF update from the noisy bearing ---
        z = _bearing(r_true) + rng.normal(0, bnr, 2)
        H = _H(x[0:3])
        innov = z - _bearing(x[0:3])
        innov[0] = (innov[0] + math.pi) % (2 * math.pi) - math.pi           # wrap az
        S = H @ P @ H.T + R
        K = P @ H.T @ np.linalg.inv(S)
        x = x + K @ innov
        P = (np.eye(6) - K @ H) @ P

        # metrics: range + closing speed (Vc) from the estimate vs truth
        r_est = float(np.linalg.norm(x[0:3])); rt = float(np.linalg.norm(r_true))
        los = r_true / (rt + 1e-9)
        vc_true = float(np.dot(-v_true, los))
        vc_est = float(np.dot(-x[3:6], x[0:3] / (r_est + 1e-9)))
        log.append((round((step + 1) * cfg.dt, 3), round(rt, 1), round(r_est, 1), round(vc_true, 1), round(vc_est, 1)))

        if gate is None and rt <= cfg.commit_gate_m:                        # first crossing of the commit gate
            # the filter's OWN 1-σ uncertainty along the LOS -- this is what the system can gate the commit on,
            # since it is available in flight (unlike the true error).
            e = x[0:3] / (r_est + 1e-9)
            sig_r = math.sqrt(max(float(e @ P[0:3, 0:3] @ e), 0.0))
            # parallax angle earned so far: our own cross-LOS displacement subtended at the target
            par = math.degrees(math.atan2(baseline, max(rt, 1e-6)))
            gate = (abs(r_est - rt) / max(rt, 1e-6), abs(vc_est - vc_true) / max(abs(vc_true), 1e-6),
                    sig_r / max(r_est, 1e-6), par)

    if gate is None:                                                        # never reached the gate (flew off)
        gate = (abs(log[-1][2] - log[-1][1]) / max(log[-1][1], 1e-6), 9.99, 9.99, 0.0)
    rt = log[-1][1]; re = log[-1][2]
    return PassiveResult(maneuvered=maneuver,
                         range_err_gate_pct=gate[0] * 100,
                         vc_err_gate_pct=gate[1] * 100,
                         range_err_final_pct=abs(re - rt) / max(rt, 1e-6) * 100,
                         sigma_r_gate_pct=gate[2] * 100,
                         baseline_m=baseline,
                         parallax_deg=gate[3],
                         trust_range=gate[3] >= PARALLAX_MIN_DEG,
                         converged=gate[0] < 0.25, log=log)


def main() -> None:  # pragma: no cover
    print("bearings-only passive ranging: does the interceptor's OWN maneuver make range observable?")
    print("(error reported when range first crosses the %.0f m commit gate, mean over 6 seeds)\n" % PassiveCfg().commit_gate_m)
    import statistics as st
    cases = [("STRAIGHT run        ", False, "weave", 0.6),
             ("WEAVE on-course 0.6g", True, "weave", 0.6),
             ("WEAVE on-course max ", True, "weave", 0.84),
             ("TURN  (off-course)  ", True, "turn", 0.6)]
    for tag, man, mode, g in cases:
        runs = [run_passive(PassiveCfg(seed=s, maneuver_mode=mode, maneuver_g=g), maneuver=man) for s in range(6)]
        print("%s -> range err %5.1f%%  Vc err %5.1f%%  filter σr %5.1f%%  parallax %4.1f°  TRUST=%s" % (
            tag, st.mean(r.range_err_gate_pct for r in runs), st.mean(r.vc_err_gate_pct for r in runs),
            st.mean(r.sigma_r_gate_pct for r in runs), st.mean(r.parallax_deg for r in runs),
            all(r.trust_range for r in runs)))
    print("\nSTRAIGHT: CV/CV geometry -> range UNOBSERVABLE; the estimate stays stuck near its wrong guess.")
    print("MANEUVER: our own lateral motion creates parallax -> range/Vc become observable. Honest accuracy:")
    print("          on-course weave ~28-36%, off-course turn ~17% (observability-vs-control: more parallax")
    print("          costs intercept geometry). COARSE, not precise.")
    print("\n!! The filter's own σr is a LIAR: on the straight run it claims ~12% while being ~66% wrong")
    print("   (false convergence). So the commit is gated on the parallax we actually EARNED with our own")
    print("   maneuver (known exactly from INS), NOT on the filter's covariance. No maneuver -> no range.")


if __name__ == "__main__":
    main()
