"""HONEST closed-loop test (cuts the Holzweg): radiometric thermal + guidance on the seeker's OWN
lambda-dot, on real MuJoCo physics. Built to EXPOSE weaknesses, not confirm the system.

Two deliberate honesty upgrades over sim3d.py:
  1. RADIOMETRIC thermal render -- the frame comes from physical apparent temperatures: a cold-sky
     gradient warming to a WARM CLUTTERED GROUND BAND at the horizon, and a winged-UAV target whose
     apparent dT is physical (body/wing/engine over ambient) and ATMOSPHERICALLY attenuated with
     range. Not gaussians hand-tuned to be detectable -> far/low targets can drop into clutter.
  2. GUIDANCE ON THE SEEKER'S OWN lambda-dot (IMM az_rate/el_rate), NOT the geometry truth, with
     airframe vibration and NO full ego-compensation (roll-only). This closes the loop on the real,
     ego-corrupted signal -> it EXPOSES W1 (ego/lambda-dot corruption) and W3 (loop on real signal).

Run:  PYTHONPATH=.:fpv python3 -m fpv_ai.bench.sim3d_honest
"""
from __future__ import annotations

import math
import os
import subprocess

import cv2
import numpy as np

from fpv.guidance.pipeline import SeekerGuidancePipeline
from fpv.seeker.geometry import ft640_intrinsics
from .sim3d import (G, W, H, F_PX, WINGSPAN_M, Sim3DConfig, _cam_basis, _geometry_ic, _project,
                    _seeker_view, _scene3d)

_OUTDIR = "/tmp/honest3d"

_YY, _XX = np.mgrid[0:H, 0:W]
_YY = _YY.astype(np.float64); _XX = _XX.astype(np.float64)
_NETD_COUNTS = 14.0                     # ~50 mK NETD referred to the 40 counts/K scale below
_COUNTS_PER_K = 40.0
_T0 = 240.0


def _render_radiometric(px, py, rng_m, aspect, in_fov, vib, rng, *,
                        occ_scale: float = 1.0, occ_cold=None, extra_hot=None):
    """Frame from physical apparent temperatures (K): cold-sky gradient + warm cluttered ground band
    + a range-attenuated winged-UAV dT. Returns uint16 counts (Y16-equivalent).

    Optional scene stressors (default OFF -> the clean render):
      * ``occ_scale`` (<1)     DIMS the target dT (a cloud thinning its apparent contrast),
      * ``occ_cold``=(cx,cy,sig,amp)   adds a COLD occluder patch sitting on the target,
      * ``extra_hot``=[(cx,cy,sig,amp),...]  adds bright off-axis distractors (a sun glint / hot ground
        source the tracker can false-lock onto when the real target drops out)."""
    # Background: cold sky at top (~258 K) warming toward a warm, cluttered ground band at the bottom.
    T = 258.0 + (_YY / H) * 44.0
    ground = _YY > (H * 0.72)
    T = T + ground * np.clip(rng.normal(7.0, 5.0, (H, W)), 0.0, None)      # warm ground clutter texture
    if in_fov:
        atmo = math.exp(-rng_m / 1200.0) * occ_scale                       # big target -> longer range
        span = min(F_PX * WINGSPAN_M / max(rng_m, 0.5), 900.0)
        cx, cy = px + vib[0], py + vib[1]
        a = math.radians(aspect); ca, sa = math.cos(a), math.sin(a)
        dx, dy = _XX - cx, _YY - cy
        u = dx * ca + dy * sa; v = -dx * sa + dy * ca
        fl = max(span * 0.55, 1.6); fw = max(span * 0.10, 1.0)
        ws = max(span * 0.5, 1.4); wc = max(span * 0.09, 0.9)
        T += 18.0 * atmo * np.exp(-(v ** 2 / (2 * fl ** 2) + u ** 2 / (2 * fw ** 2)))   # body dT +18K
        T += 12.0 * atmo * np.exp(-(u ** 2 / (2 * ws ** 2) + v ** 2 / (2 * wc ** 2)))   # wings +12K
        ho = span * 0.30; hw = max(span * 0.07, 1.0)
        for s in (-1.0, 1.0):                                              # engine/motor hot spots +65K
            hx = cx + s * ho * ca; hy = cy + s * ho * sa
            T += 65.0 * atmo * np.exp(-((_XX - hx) ** 2 + (_YY - hy) ** 2) / (2 * hw ** 2))
    if occ_cold is not None:                                              # cold cloud body sitting on the target
        ocx, ocy, osig, oamp = occ_cold
        T += oamp * np.exp(-((_XX - ocx) ** 2 + (_YY - ocy) ** 2) / (2 * osig ** 2))
    if extra_hot is not None:                                            # bright off-axis distractors (sun / hot src)
        for (hx, hy, hsig, hamp) in extra_hot:
            T += hamp * np.exp(-((_XX - hx) ** 2 + (_YY - hy) ** 2) / (2 * hsig ** 2))
    counts = 4096.0 + (T - _T0) * _COUNTS_PER_K + rng.normal(0, _NETD_COUNTS, (H, W))
    counts = cv2.GaussianBlur(counts, (3, 3), 0.8)
    return np.clip(counts, 0, 65535).astype(np.uint16)


def run_honest(cfg: Sim3DConfig, *, guidance_source: str = "seeker", vibration_px: float = 1.3,
               sync_error_ms: float | None = None, pipeline_kwargs: dict | None = None,
               gimbal: bool = False, gimbal_rate_max_dps: float | None = None,
               gimbal_tau_s: float = 0.0, gimbal_los: str = "truth", scene=None,
               los_rate_tau_s: float = 0.06, sun_dir=None, sun_amp: float = 120.0,
               sun_sig: float = 4.5, trace=None) -> dict:
    """One closing engagement. guidance_source='geometry' (Holzweg truth) or 'seeker' (real lambda-dot).
    When guidance_source='seeker' and sync_error_ms is set, MODEL a cam<->IMU ego-comp that recovers
    the inertial LOS rate with a timestamp-skew residual (0 ms = perfect HW timestamp, e.g. Zynq PL).

    gimbal=True: a stabilized head. gimbal_rate_max_dps=None -> IDEAL gimbal (clean truth LOS rate, a
    best-case ceiling). Set gimbal_rate_max_dps (+ optional gimbal_tau_s) -> a REALISTIC servo gimbal:
    the head slews toward the LOS with a deg/s rate limit and a first-order lag, the guidance rides the
    gimbal's actual inertial slew (which lags/saturates on a fast-crossing terminal), and lock is lost
    if the pointing error exceeds the FT640 half-VFOV (~19.3 deg). This is the model that tells you the
    servo bandwidth a real DIY gimbal needs to actually hit.

    gimbal_los='seeker': CLOSE THE PERCEPTION LOOP. The head no longer slews toward the TRUTH LOS -- it
    slews toward the direction the SEEKER reports, recovered from ``out.centroid_px`` (the tracked pixel)
    by the exact inverse of ``_project``. PN then rides the head's OWN pointing (``g_point``), not truth.
    So a perception failure now MOVES THE MISS: if the tracker false-locks onto a distractor its centroid
    jumps, the head chases it, and PN drives the airframe off the true target -> a real miss. This joins
    the perception fix and the gimbal hit into ONE end-to-end proof. (Honest scope: the render stays
    strapdown -- it does NOT re-center as the head moves -- so this models the pixel->pointing COUPLING,
    not a full image-in-the-loop gimbal; and ``vc`` still uses truth range-rate, which scales the command
    MAGNITUDE but not its DIRECTION -- direction, which decides hit/miss, comes entirely from the pixel.)
    ``scene(step, px, py, rng_m) -> dict(occ_scale=, occ_cold=, extra_hot=)`` injects render stressors
    (occlusion + off-axis distractor) so the false-lock is physically produced, not asserted."""
    import mujoco
    from .sim3d import _xml
    model = mujoco.MjModel.from_xml_string(_xml(cfg, visual=False))
    data = mujoco.MjData(model)
    iid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "interceptor")
    tid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "target")
    tpos, tvel = _geometry_ic(cfg)
    data.qpos[0:3] = cfg.int_pos; data.qpos[3:7] = [1, 0, 0, 0]
    data.qpos[7:10] = tpos; data.qpos[10:14] = [1, 0, 0, 0]
    mujoco.mj_forward(model, data)
    aim = tpos - data.xpos[iid]; aim /= np.linalg.norm(aim)
    data.qvel[0:3] = aim * cfg.launch_speed
    data.qvel[6:9] = tvel

    def vel_of(bid):
        res = np.zeros(6)
        mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, bid, res, 0)
        return res[3:6].copy()

    pk = dict(region_bands=4, graduated_k=True, roi_gating=True,
              use_peak_relative_deletion=True, use_imm_coast=True)
    if pipeline_kwargs:
        pk.update(pipeline_kwargs)                  # W6 lock-hardening (sky basket, traj-continuity, ...)
    pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics(), **pk)
    rng = np.random.default_rng(cfg.seed)
    g_force = np.zeros(3); minr = 1e9; hit = None; prev_rng = None
    lock_frames = detect_frames = n_ticks = 0
    applied_lat = np.zeros(3); prev_lat = np.zeros(3); ego_px_extra = 0.0    # FPV attitude state
    g_point = None; _HALF_VFOV = math.radians(19.3); gimbal_lost = 0        # servo-gimbal pointing state
    omega_filt = np.zeros(3)                                                # seeker LOS-rate guidance filter
    ti, tt = [], []; fid = 0
    if cfg.render:
        os.makedirs(_OUTDIR, exist_ok=True)
        for f in os.listdir(_OUTDIR):
            os.remove(os.path.join(_OUTDIR, f))
    for step in range(int(cfg.tmax / cfg.dt_phys)):
        ip = data.xpos[iid].copy(); tp = data.xpos[tid].copy()
        iv = vel_of(iid); tv = vel_of(tid)
        rel = tp - ip; rng_m = float(np.linalg.norm(rel)); minr = min(minr, rng_m)
        losn = rel / (rng_m + 1e-9)
        if rng_m < cfg.cap_m:
            hit = True; break
        if prev_rng is not None and rng_m < 80.0 and rng_m > prev_rng:
            hit = False; break
        prev_rng = rng_m
        if step % cfg.sub == 0:
            proj, right, up, _, _ = _project(ip, iv, tp)
            vc = max(float(np.dot(tv - iv, -losn)), 1.0)
            tvn = tv / (np.linalg.norm(tv) + 1e-9)
            aspect = math.degrees(math.acos(max(-1, min(1, float(np.dot(-tvn, losn))))))
            vib = rng.normal(0, vibration_px + ego_px_extra, 2)            # vibration + body-rotation ego
            eh = []
            if gimbal and gimbal_los == "seeker":
                # RENDER THROUGH THE GIMBAL: a stabilized head keeps the target near boresight, so the tracker
                # sees the HEAD's view -- NOT the strapdown airframe view (where the target migrates into the
                # ground-clutter band and is lost). g_point is the head boresight (LOBL-enrolled on the target).
                if g_point is None:
                    g_point = losn.copy()
                gfwd, gright, gup = _cam_basis(g_point)
                fT = float(np.dot(rel, gfwd))
                if fT > 1.0:
                    px = W / 2.0 + F_PX * float(np.dot(rel, gright)) / fT
                    py = H / 2.0 - F_PX * float(np.dot(rel, gup)) / fT
                else:
                    px, py = -1e3, -1e3
                right, up = gright, gup                                    # pixel->LOS uses the gimbal basis
                if sun_dir is not None:                                    # bright distractor at a FIXED world dir
                    fS = float(np.dot(sun_dir, gfwd))
                    if fS > 0.05:
                        sx = W / 2.0 + F_PX * float(np.dot(sun_dir, gright)) / fS
                        sy = H / 2.0 - F_PX * float(np.dot(sun_dir, gup)) / fS
                        if 0 <= sx < W and 0 <= sy < H:
                            eh.append((sx, sy, sun_sig, sun_amp))
            else:
                px, py = proj if proj is not None else (-1e3, -1e3)
            in_fov = bool(0 <= px < W and 0 <= py < H)
            sc = scene(step, px, py, rng_m) if scene is not None else {}
            eh += list(sc.get("extra_hot") or [])
            frame = _render_radiometric(px, py, rng_m, aspect, in_fov, vib, rng,
                                        occ_scale=sc.get("occ_scale", 1.0), occ_cold=sc.get("occ_cold"),
                                        extra_hot=eh or None)
            out = pipe.step(now=step * cfg.dt_phys, frame_u16=frame, gyro_omega_xyz=(0, 0, 0),
                            dt=cfg.sub * cfg.dt_phys, committed=cfg.committed)
            n_ticks += 1
            if out.blobs:
                detect_frames += 1
            omega_true = np.cross(rel, tv - iv) / max(float(np.dot(rel, rel)), 1e-6)   # inertial LOS rate
            omega_meas = omega_true
            if gimbal:                                                      # stabilized head
                dt_g = cfg.sub * cfg.dt_phys
                if g_point is None:
                    g_point = losn.copy()
                if gimbal_los == "seeker":                                 # CLOSED LOOP: aim at the ГСН centroid
                    c = out.centroid_px
                    if c is not None:                                     # pixel -> LOS in the GIMBAL basis (the
                        fwd_cam = g_point                                 # boresight the frame was rendered through)
                        aim_los = (fwd_cam + ((float(c[0]) - W / 2.0) / F_PX) * right
                                   + (-(float(c[1]) - H / 2.0) / F_PX) * up)
                        aim_los /= np.linalg.norm(aim_los) + 1e-9
                        have_meas = True
                    else:                                                 # no centroid -> HOLD (coast the head)
                        aim_los = g_point; have_meas = False
                else:                                                     # legacy: gimbal rides TRUTH LOS
                    aim_los = losn; have_meas = proj is not None
                if gimbal_rate_max_dps is None:                            # IDEAL gimbal (snaps onto aim)
                    omega_meas = (omega_true if gimbal_los == "truth"     # truth-mode best-case ceiling (unchanged)
                                  else np.cross(g_point, aim_los) / dt_g)  # seeker-mode implied slew from the pixel
                    g_point = aim_los.copy()
                    guided = have_meas
                else:                                                      # REALISTIC servo gimbal
                    ang = math.acos(float(np.clip(np.dot(g_point, aim_los), -1.0, 1.0)))   # pointing error
                    applied = min(ang, math.radians(gimbal_rate_max_dps) * dt_g)        # servo slew budget
                    if gimbal_tau_s > 0:
                        applied = min(applied, ang * dt_g / (gimbal_tau_s + dt_g))      # first-order lag
                    if ang > 1e-9:
                        axis = np.cross(g_point, aim_los); axis /= (np.linalg.norm(axis) + 1e-9)
                        g_point = (g_point * math.cos(applied) + np.cross(axis, g_point) * math.sin(applied)
                                   + axis * float(np.dot(axis, g_point)) * (1.0 - math.cos(applied)))
                        g_point /= (np.linalg.norm(g_point) + 1e-9)
                        omega_meas = axis * (applied / dt_g)               # gimbal inertial slew = measured LOS rate
                    else:
                        omega_meas = np.zeros(3)
                    if gimbal_los == "seeker":                            # measurement present AND inside FOV
                        guided = have_meas and ang < _HALF_VFOV
                    else:                                                 # legacy truth-mode (unchanged)
                        guided = ang < _HALF_VFOV                          # target inside the gimbaled FOV
                    if not guided:
                        gimbal_lost += 1
                if gimbal_los == "seeker" and los_rate_tau_s > 0.0:       # guidance LOS-rate filter (real seekers
                    a_f = dt_g / (los_rate_tau_s + dt_g)                   # low-pass lambda-dot before PN): smooths
                    omega_filt = (1.0 - a_f) * omega_filt + a_f * omega_meas   # PIXEL JITTER, not a false-lock BIAS
                    omega_meas = omega_filt
                use_geo = True
                if trace is not None:                                     # diagnostics (pixel/pointing/rate)
                    cerr = (math.hypot(out.centroid_px[0] - px, out.centroid_px[1] - py)
                            if out.centroid_px is not None and proj is not None else -1.0)
                    trace.append((rng_m, out.tracking_state,
                                  math.degrees(math.acos(float(np.clip(np.dot(g_point, losn), -1, 1)))),
                                  cerr, float(np.linalg.norm(omega_meas)), bool(guided), px, py))
            else:
                guided = (out.command is not None and out.engage_permitted and not out.roe_abort
                          and "LOCK" in out.tracking_state)
                use_geo = guidance_source == "geometry"
            if "LOCK" in out.tracking_state:
                lock_frames += 1
            if guided:
                if gimbal:                                                  # gimbal rides its own inertial slew
                    los_pn = g_point if gimbal_los == "seeker" else losn    # seeker: PN on the head's OWN LOS
                    a_vec = cfg.n_nav * vc * np.cross(omega_meas, los_pn)
                elif use_geo:                                               # geometry-truth lambda-dot ceiling
                    a_vec = cfg.n_nav * vc * np.cross(omega_true, losn)
                elif sync_error_ms is None:                                 # HONEST: raw seeker lambda-dot (W1 exposed)
                    a_vec = cfg.n_nav * vc * (out.imm.az_rate_radps * right + out.imm.el_rate_radps * up)
                else:                                                       # MODELED cam<->IMU ego-comp
                    # A synced gyro removes the boresight rotation to reveal the INERTIAL LOS rate;
                    # a timestamp skew leaves a residual lambda-dot error that grows with the skew.
                    a_ideal = cfg.n_nav * vc * np.cross(omega_true, losn)
                    a_vec = a_ideal + cfg.n_nav * vc * rng.normal(0, sync_error_ms * 0.02, 3)
                amag = float(np.linalg.norm(a_vec))
                if amag > cfg.g_max * G:
                    a_vec *= (cfg.g_max * G) / amag
                g_desired = cfg.int_mass * a_vec
            else:
                g_desired = np.zeros(3)
            # FPV ATTITUDE LAG: the airframe must ROTATE to redirect thrust, so the lateral force LAGS
            # the command, and the rotation rate corrupts the strapdown seeker (ego shift NEXT frame).
            if cfg.attitude_tau_s > 0:
                dt_t = cfg.sub * cfg.dt_phys
                applied_lat = applied_lat + min(1.0, dt_t / cfg.attitude_tau_s) * (g_desired - applied_lat)
                tilt_rate = float(np.linalg.norm(applied_lat - prev_lat)) / max(cfg.int_mass * G, 1e-6) / dt_t
                ego_px_extra = cfg.attitude_ego_gain * tilt_rate
                prev_lat = applied_lat.copy()
                g_force = applied_lat
            else:
                g_force = g_desired
            if cfg.render:
                ti.append(ip.copy()); tt.append(tp.copy())
                reqg = float(np.linalg.norm(g_force)) / (cfg.int_mass * G)
                combo = cv2.hconcat([_seeker_view(frame, out, rng_m, vc, reqg),
                                     _scene3d(cfg, ti, tt, None, minr, rng_m, vc, reqg,
                                              out.tracking_state, rng_m / max(vc, 1e-6))])
                cv2.imwrite(f"{_OUTDIR}/f{fid:04d}.png", combo); fid += 1
        spd = float(np.linalg.norm(iv)); vhat = iv / (spd + 1e-9)
        thrust = cfg.int_mass * 6.0 * (cfg.m_speed - spd) * vhat
        data.xfrc_applied[iid, :3] = np.array([0, 0, cfg.int_mass * G]) + g_force + thrust
        tvn = tv / (np.linalg.norm(tv) + 1e-9)
        turn_axis = np.cross(tvn, [0, 0, 1.0]); turn_axis /= np.linalg.norm(turn_axis) + 1e-9
        if cfg.target_turn_g > 0:                          # MANEUVERING target: turn flips each period (route change)
            sign = 1.0 if int((step * cfg.dt_phys) / cfg.target_turn_period_s) % 2 == 0 else -1.0
            tforce = cfg.target_turn_g * G * cfg.tgt_mass * sign * turn_axis
        else:
            tforce = cfg.weave_g * G * cfg.tgt_mass * math.sin(step * cfg.dt_phys * 1.1) * turn_axis
        data.xfrc_applied[tid, :3] = np.array([0, 0, cfg.tgt_mass * G]) + tforce
        mujoco.mj_step(model, data)
    mp4 = None
    if cfg.render and fid:
        img = cv2.imread(f"{_OUTDIR}/f{fid-1:04d}.png")
        s3 = _scene3d(cfg, ti, tt, bool(hit), minr, minr, 0.0, 0.0, "END", 0.0)
        combo = cv2.hconcat([img[:, :W], s3])
        for _ in range(40):                            # hold the final frame ~0.7 s
            cv2.imwrite(f"{_OUTDIR}/f{fid:04d}.png", combo); fid += 1
        subprocess.run(["ffmpeg", "-y", "-framerate", "60", "-i", f"{_OUTDIR}/f%04d.png",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", cfg.mp4], check=True, capture_output=True)
        mp4 = cfg.mp4
    return dict(hit=hit, cpa=minr, det_rate=detect_frames / max(n_ticks, 1),
                lock_rate=lock_frames / max(n_ticks, 1),
                gimbal_lost_rate=gimbal_lost / max(n_ticks, 1), mp4=mp4)


def main():
    print("HONEST closed loop (radiometric thermal + real ego) -- geometry-truth vs seeker's own lambda-dot")
    print(f"{'geometry':<12} {'guidance':<10} {'outcome':<7} {'CPA(m)':>7} {'det%':>6} {'lock%':>6}")
    for geom in ("head_on", "quartering", "crossing"):
        for src in ("geometry", "seeker"):
            r = run_honest(Sim3DConfig(geometry=geom, g_max=6, committed=True), guidance_source=src)
            oc = "HIT" if r["hit"] else ("MISS" if r["hit"] is False else "n/a")
            print(f"{geom:<12} {src:<10} {oc:<7} {r['cpa']:>7.2f} {100*r['det_rate']:>5.0f}% {100*r['lock_rate']:>5.0f}%")
    print("\nseeker vs geometry gap = the honest cost of W1 (ego-corrupted lambda-dot) + W3 (real-signal loop).")

    print("\n=== What cam<->IMU sync buys (head_on, seeker guidance, modeled ego-comp) ===")
    print(f"{'sync error':<12} {'meaning':<26} {'outcome':<7} {'CPA(m)':>7}")
    base = dict(geometry="head_on", g_max=6, committed=True)
    geo = run_honest(Sim3DConfig(**base), guidance_source="geometry")
    print(f"{'(geometry)':<12} {'truth lambda-dot ceiling':<26} {'-':<7} {geo['cpa']:>7.2f}")
    for ms, tag in [(0.0, "perfect HW ts (Zynq PL)"), (1.0, "good HW sync"),
                    (5.0, "Pi / USB skew"), (10.0, "poor sync")]:
        r = run_honest(Sim3DConfig(**base), guidance_source="seeker", sync_error_ms=ms)
        oc = "HIT" if r["hit"] else ("MISS" if r["hit"] is False else "n/a")
        print(f"{str(ms) + ' ms':<12} {tag:<26} {oc:<7} {r['cpa']:>7.2f}")
    raw = run_honest(Sim3DConfig(**base), guidance_source="seeker")
    oc = "HIT" if raw["hit"] else ("MISS" if raw["hit"] is False else "n/a")
    print(f"{'(none)':<12} {'raw seeker lambda-dot':<26} {oc:<7} {raw['cpa']:>7.2f}")
    print("\n=> CPA rides the sync error: HW timestamp (0-1 ms, Zynq) approaches the truth ceiling;")
    print("   Pi/USB skew (5-10 ms) degrades toward the uncompensated miss. That IS the value of the fix.")


if __name__ == "__main__":
    main()
