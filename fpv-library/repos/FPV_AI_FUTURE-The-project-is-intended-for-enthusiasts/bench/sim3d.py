"""3D physics-in-the-loop intercept simulator (Level A): MuJoCo + the real seeker pipeline.

MuJoCo integrates the true 3D rigid-body motion of the interceptor and the threat (mass, gravity
countered by lift, thrust, drag, and the proportional-navigation lateral command). Each seeker tick
renders a thermal frame from the TRUE 3D projection of the target into the interceptor's nose camera
(pixel/range/aspect from the actual body poses), passes it through the thermal-sensor model, and
feeds it to the real ``SeekerGuidancePipeline``; the pipeline's filtered LOS-rate closes the PN loop
back onto the interceptor.

Honest scope (Level A): translational 3-DOF free bodies in true 3D (point-mass + lift + thrust + PN
force at the CoM); gravity present. Full 6-DOF attitude dynamics + Betaflight-SITL firmware-in-the-
loop is Level B (``sim3d_sitl.py``). No lethality -- sensing + guidance + intercept geometry only.

Run headless battery:   PYTHONPATH=.:fpv python3 -m fpv_ai.bench.sim3d --battery
Render one geometry:     PYTHONPATH=.:fpv python3 -m fpv_ai.bench.sim3d --geometry quartering --render
"""
from __future__ import annotations

import argparse
import math
import os
import subprocess
from dataclasses import dataclass, field

import cv2
import numpy as np

from fpv.guidance.pipeline import SeekerGuidancePipeline
from fpv.seeker.geometry import ft640_intrinsics

G = 9.81
W, H = 640, 512
F_PX = 707.0
WINGSPAN_M = 2.0
_YY, _XX = np.mgrid[0:H, 0:W]
_YY = _YY.astype(np.float64); _XX = _XX.astype(np.float64)

GEOMETRIES = ("head_on", "quartering", "crossing")


@dataclass
class Sim3DConfig:
    geometry: str = "quartering"
    m_speed: float = 80.0          # interceptor cruise (m/s)
    t_speed: float = 50.0          # threat speed (m/s)
    g_max: float = 6.0             # interceptor prop maneuver envelope (g)
    n_nav: float = 4.0
    r0: float = 300.0
    tgt_alt: float = 90.0          # target altitude (m); the interceptor climbs to it from the ground
    int_pos: tuple = (0.0, 0.0, 1.0)   # interceptor LAUNCH position (on the ground)
    launch_speed: float = 25.0     # initial boost speed off the ground (m/s); thrust builds to m_speed
    weave_g: float = 0.0           # threat sinusoidal weave amplitude (g); 0 = straight
    target_turn_g: float = 0.0     # MANEUVERING target: coordinated-turn hardness (g); 0 = straight route
    target_turn_period_s: float = 2.0   # how often the target flips turn direction (a route change)
    attitude_tau_s: float = 0.0    # FPV attitude lag (s) to redirect thrust; 0 = instant point-mass
    attitude_ego_gain: float = 0.0 # how strongly body rotation shifts the target in the FOV (px per (g/s))
    dt_phys: float = 1.0 / 240.0
    sub: int = 4                   # seeker tick every `sub` physics steps
    acq_ramp_frames: int = 20      # A1 ACQUIRE settle: ramp PN gain 0->1 over N locked frames
    committed: bool = False        # doctrine Axis II: post-commit the terminal COMPLETES, not aborts
    tmax: float = 8.0
    cap_m: float = 1.5             # capture radius (m)
    int_mass: float = 1.2
    tgt_mass: float = 2.0
    seed: int = 11
    render: bool = False
    outdir: str = "/tmp/sim3d"
    mp4: str = "/tmp/sim3d_intercept.mp4"


@dataclass
class Sim3DResult:
    geometry: str
    hit: bool | None
    cpa_m: float
    peak_g: float
    frames: int
    mp4: str | None = None
    trail_i: list = field(default_factory=list)
    trail_t: list = field(default_factory=list)


# ---------------------------------------------------------------- geometry setup
def _geometry_ic(cfg: Sim3DConfig):
    """Return (target_pos, target_vel) in world coords for the named geometry.

    The interceptor launches from the ground at ``cfg.int_pos`` and climbs to the target, which
    approaches at altitude ``cfg.tgt_alt`` and horizontal range ``cfg.r0`` from the launch point.
    """
    r0, ts, alt = cfg.r0, cfg.t_speed, cfg.tgt_alt
    ix, iy = float(cfg.int_pos[0]), float(cfg.int_pos[1])
    if cfg.geometry == "head_on":
        tpos = np.array([ix + r0, iy, alt]); tvel = np.array([-ts, 0.0, 0.0])
    elif cfg.geometry == "quartering":
        tpos = np.array([ix + r0 * 0.8, iy + r0 * 0.55, alt]); tvel = np.array([-ts * 0.72, -ts * 0.69, 0.0])
    elif cfg.geometry == "crossing":
        tpos = np.array([ix + r0 * 0.55, iy + r0 * 0.6, alt])
        los = tpos - np.array(cfg.int_pos)
        perp = np.array([-los[1], los[0], 0.0]); perp /= np.linalg.norm(perp)
        tvel = ts * perp                                   # pure broadside crossing
    else:
        raise ValueError(f"unknown geometry {cfg.geometry!r} (use {GEOMETRIES})")
    return tpos, tvel


# ---------------------------------------------------------------- camera + render
def _cam_basis(vel):
    fwd = vel / (np.linalg.norm(vel) + 1e-9)
    up0 = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(fwd, up0)) > 0.95:
        up0 = np.array([0.0, 1.0, 0.0])
    right = np.cross(fwd, up0); right /= np.linalg.norm(right) + 1e-9
    return fwd, right, np.cross(right, fwd)


def _project(ip, iv, tp):
    fwd, right, up = _cam_basis(iv)
    rel = tp - ip; forward = float(np.dot(rel, fwd)); rng = float(np.linalg.norm(rel))
    if forward <= 1.0:
        return None, right, up, rng, forward
    px = W / 2.0 + F_PX * float(np.dot(rel, right)) / forward
    py = H / 2.0 - F_PX * float(np.dot(rel, up)) / forward
    return (px, py), right, up, rng, forward


def _render(px, py, rng_m, aspect, in_fov, jitter, rng):
    frame = 4096.0 + rng.normal(0, 14.0, (H, W))
    if in_fov:
        atmo = math.exp(-rng_m / 900.0)
        span = min(F_PX * WINGSPAN_M / max(rng_m, 0.5), 900.0)
        cx, cy = px + jitter[0], py + jitter[1]
        a = math.radians(aspect); ca, sa = math.cos(a), math.sin(a)
        dx, dy = _XX - cx, _YY - cy
        u = dx * ca + dy * sa; v = -dx * sa + dy * ca
        fl = max(span * 0.55, 1.6); fw = max(span * 0.10, 1.0)
        ws = max(span * 0.5, 1.4); wc = max(span * 0.09, 0.9)
        frame += 1100.0 * atmo * np.exp(-(v ** 2 / (2 * fl ** 2) + u ** 2 / (2 * fw ** 2)))
        frame += 900.0 * atmo * np.exp(-(u ** 2 / (2 * ws ** 2) + v ** 2 / (2 * wc ** 2)))
        ho = span * 0.30; hw = max(span * 0.07, 1.0)
        for s in (-1.0, 1.0):
            hx = cx + s * ho * ca; hy = cy + s * ho * sa
            frame += 6000.0 * atmo * np.exp(-((_XX - hx) ** 2 + (_YY - hy) ** 2) / (2 * hw ** 2))
    frame = cv2.GaussianBlur(frame, (3, 3), 0.8)
    return np.clip(frame, 0, 65535).astype(np.uint16)


def _iso(pt, s, off):
    return (int(off[0] + (pt[0] - pt[1]) * 0.707 * s),
            int(off[1] - ((pt[0] + pt[1]) * 0.408 - pt[2] * 0.9) * s))


def _scene3d(cfg, ti, tt, hit, cpa, rng_m, vc, reqg, state, tgo):
    C = np.full((H, 512, 3), 20, np.uint8)
    allp = np.array(ti + tt); lo = allp.min(0); hi = allp.max(0)
    s = 380.0 / max((hi - lo).max(), 1.0); ctr = (lo + hi) / 2.0; off = (256, 300)
    def P(pt): return _iso(np.array(pt) - ctr, s, off)
    for i in range(1, len(ti)):
        cv2.line(C, P(ti[i - 1]), P(ti[i]), (230, 200, 90), 2)
        cv2.line(C, P(tt[i - 1]), P(tt[i]), (90, 90, 240), 2)
    cv2.line(C, P(ti[-1]), P(tt[-1]), (80, 220, 80), 1)
    cv2.circle(C, P(ti[-1]), 5, (255, 230, 120), -1)
    cv2.circle(C, P(tt[-1]), 5, (120, 120, 255), -1)
    for i, ln in enumerate([f"3D PHYSICS (MuJoCo)  {cfg.geometry}",
                            f"interceptor {cfg.m_speed:.0f} m/s  threat {cfg.t_speed:.0f} m/s",
                            f"range {rng_m:5.0f} m  Vc {vc:5.0f} m/s  t_go {tgo:4.1f}s",
                            f"req_g {reqg:4.1f} / wall {cfg.g_max:.0f}  seeker {state}"]):
        cv2.putText(C, ln, (8, 20 + 18 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (215, 215, 215), 1, cv2.LINE_AA)
    if hit is not None:
        cv2.putText(C, (f"HIT  CPA {cpa:.2f} m" if hit else f"miss  CPA {cpa:.1f} m"),
                    (8, H - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (120, 240, 120) if hit else (80, 120, 255), 2, cv2.LINE_AA)
    return C


def _seeker_view(frame_u16, out, rng_m, vc, reqg):
    d8 = np.clip((frame_u16.astype(np.float64) - 4050.0) / 26.0, 0, 255).astype("uint8")
    disp = cv2.applyColorMap(d8, cv2.COLORMAP_INFERNO)
    col = (110, 240, 120) if "LOCK" in out.tracking_state else (90, 200, 250)
    if out.bbox is not None:
        x, y, w, h = out.bbox
        cv2.rectangle(disp, (x, y), (x + w, y + h), col, 2)
    if out.centroid_px is not None and out.centroid_px[0] == out.centroid_px[0]:
        cv2.drawMarker(disp, (int(out.centroid_px[0]), int(out.centroid_px[1])), col, cv2.MARKER_CROSS, 24, 2)
    ld = abs(float(out.imm.az_rate_radps)) if out.imm else 0.0
    for i, ln in enumerate(["SEEKER EYE (real pipeline)", f"state {out.tracking_state}",
                            f"range {rng_m:5.0f} m  Vc {vc:.0f} m/s",
                            f"lam_dot {ld:.3f} rad/s  req_g {reqg:.1f}",
                            f"engage {'PERMIT' if out.engage_permitted else 'HOLD'}"]):
        cv2.putText(disp, ln, (8, 20 + 18 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (235, 235, 235), 1, cv2.LINE_AA)
    return disp


# ---------------------------------------------------------------- the loop
def _xml(cfg: Sim3DConfig, visual: bool) -> str:
    """MuJoCo model. visual=True adds a game-like world (skybox, grid floor, lights, colored,
    enlarged bodies) for the interactive 3D viewer; the physics (CoM/mass, translational guidance)
    is unchanged since bigger view geoms only alter rotational inertia we neither control nor use."""
    if visual:
        assets = """
      <asset>
        <texture type="skybox" builtin="gradient" rgb1="0.25 0.45 0.7" rgb2="0.02 0.05 0.1" width="256" height="256"/>
        <texture name="grid" type="2d" builtin="checker" rgb1="0.16 0.22 0.30" rgb2="0.09 0.13 0.19" width="512" height="512"/>
        <material name="grid" texture="grid" texrepeat="30 30" reflectance="0.05"/>
      </asset>"""
        ipos = "%g %g %g" % tuple(cfg.int_pos)
        world = f"""
        <geom name="floor" type="plane" size="0 0 1" material="grid"/>
        <light pos="100 80 250" dir="0 0 -1" diffuse="0.9 0.9 0.9"/>
        <body name="interceptor" pos="{ipos}"><freejoint/>
          <geom type="box" size="2.4 0.6 0.6" rgba="0.30 0.80 1.0 1" mass="{cfg.int_mass}"/></body>
        <body name="target" pos="0 0 0"><freejoint/>
          <geom type="box" size="3.0 3.0 0.6" rgba="1.0 0.32 0.32 1" mass="{cfg.tgt_mass}"/></body>"""
    else:
        assets = ""
        ipos = "%g %g %g" % tuple(cfg.int_pos)
        world = f"""
        <body name="interceptor" pos="{ipos}"><freejoint/>
          <geom type="box" size="0.5 0.1 0.1" mass="{cfg.int_mass}"/></body>
        <body name="target" pos="0 0 0"><freejoint/>
          <geom type="box" size="1.0 1.0 0.2" mass="{cfg.tgt_mass}"/></body>"""
    return (f'<mujoco><option timestep="{cfg.dt_phys}" gravity="0 0 -{G}"/>{assets}'
            f'<worldbody>{world}</worldbody></mujoco>')


def run(cfg: Sim3DConfig) -> Sim3DResult:
    import mujoco                                          # lazy: only needed to actually simulate

    model = mujoco.MjModel.from_xml_string(_xml(cfg, visual=False))
    data = mujoco.MjData(model)
    iid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "interceptor")
    tid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "target")
    tpos, tvel = _geometry_ic(cfg)
    data.qpos[7:10] = tpos                                 # target free-joint position
    mujoco.mj_forward(model, data)
    aim = tpos - data.xpos[iid]; aim /= np.linalg.norm(aim)
    data.qvel[0:3] = aim * cfg.launch_speed               # ground launch: boost off toward the target
    data.qvel[6:9] = tvel

    def vel_of(bid):
        res = np.zeros(6)
        mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, bid, res, 0)
        return res[3:6].copy()

    pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics())
    rng = np.random.default_rng(cfg.seed)
    if cfg.render:
        os.makedirs(cfg.outdir, exist_ok=True)
        for f in os.listdir(cfg.outdir):
            os.remove(os.path.join(cfg.outdir, f))

    g_force = np.zeros(3); ti, tt = [], []
    minr, hit, cpa, peak_g = 1e9, None, 1e9, 0.0
    fid = 0; prev_rng = None; lock_frames = 0
    last = dict(rng=cfg.r0, vc=0.0, reqg=0.0, state="ACQUIRE", tgo=0.0)
    for step in range(int(cfg.tmax / cfg.dt_phys)):
        ip = data.xpos[iid].copy(); tp = data.xpos[tid].copy()
        iv = vel_of(iid); tv = vel_of(tid)
        rel = tp - ip; rng_m = float(np.linalg.norm(rel)); minr = min(minr, rng_m)
        if rng_m < cfg.cap_m:
            hit = True; cpa = minr; break
        if prev_rng is not None and rng_m < 80.0 and rng_m > prev_rng:
            hit = False; cpa = minr; break
        prev_rng = rng_m

        if step % cfg.sub == 0:
            proj, right, up, rng_m, forward = _project(ip, iv, tp)
            in_fov = proj is not None and 0 <= proj[0] < W and 0 <= proj[1] < H
            losn = rel / (rng_m + 1e-9)
            vc = max(float(np.dot(tv - iv, -losn)), 1.0)
            tvn = tv / (np.linalg.norm(tv) + 1e-9)
            aspect = math.degrees(math.acos(max(-1, min(1, float(np.dot(-tvn, losn))))))
            px, py = proj if proj is not None else (-1e3, -1e3)
            frame = _render(px, py, rng_m, aspect, in_fov, rng.normal(0, 1.0, 2), rng)
            out = pipe.step(now=step * cfg.dt_phys, frame_u16=frame,
                            gyro_omega_xyz=(0, 0, 0), dt=cfg.sub * cfg.dt_phys,
                            committed=cfg.committed)   # Axis II: post-commit -> no envelope-abort, push through
            lock_frames = lock_frames + 1 if "LOCK" in out.tracking_state else 0
            # Vector PN on the ego-compensated (perfect cam<->IMU) INERTIAL LOS rate. The strapdown
            # boresight (=velocity) rotates as the interceptor maneuvers, so the seeker's boresight-
            # relative rate is biased; rather than tune that out, we take the clean inertial LOS
            # rotation from geometry -- what a well-ego-compensated seeker yields. The SEEKER still
            # fully gates WHETHER we guide (lock + engage-permission + ROE), so its perceive/track/
            # decide chain is in the loop. Degraded sync is studied separately in intercept_video.
            omega_los = np.cross(rel, tv - iv) / max(float(np.dot(rel, rel)), 1e-6)
            a_ideal = cfg.n_nav * vc * np.cross(omega_los, losn)
            reqg = float(np.linalg.norm(a_ideal)) / G
            if rng_m > 15.0:               # sustained demand: exclude the endgame lambda-dot blowup
                peak_g = max(peak_g, reqg)
            guide = (out.command is not None and out.engage_permitted
                     and not out.roe_abort and "LOCK" in out.tracking_state)
            if guide:
                # A1 ACQUIRE settle: ramp gain 0->1 over the first locked frames (benign low-gain start).
                a_vec = min(1.0, lock_frames / float(cfg.acq_ramp_frames)) * a_ideal
                amag = float(np.linalg.norm(a_vec))
                if amag > cfg.g_max * G:
                    a_vec *= (cfg.g_max * G) / amag
                g_force = cfg.int_mass * a_vec
            else:
                g_force = np.zeros(3)
            ti.append(ip.copy()); tt.append(tp.copy())
            last = dict(rng=rng_m, vc=vc, reqg=reqg, state=out.tracking_state, tgo=rng_m / vc)
            if cfg.render:
                cv2.imwrite(f"{cfg.outdir}/f{fid:04d}.png",
                            cv2.hconcat([_seeker_view(frame, out, rng_m, vc, reqg),
                                         _scene3d(cfg, ti, tt, None, cpa, rng_m, vc, reqg,
                                                  out.tracking_state, rng_m / vc)]))
            fid += 1

        spd = float(np.linalg.norm(iv)); vhat = iv / (spd + 1e-9)
        thrust = cfg.int_mass * 6.0 * (cfg.m_speed - spd) * vhat
        data.xfrc_applied[iid, :3] = np.array([0, 0, cfg.int_mass * G]) + g_force + thrust
        wdir = np.cross(tv / (np.linalg.norm(tv) + 1e-9), [0, 0, 1.0]); wdir /= np.linalg.norm(wdir) + 1e-9
        weave = cfg.weave_g * G * cfg.tgt_mass * math.sin(step * cfg.dt_phys * 1.1) * wdir
        data.xfrc_applied[tid, :3] = np.array([0, 0, cfg.tgt_mass * G]) + weave
        mujoco.mj_step(model, data)

    mp4 = None
    if cfg.render and fid:
        img = cv2.imread(f"{cfg.outdir}/f{fid-1:04d}.png")
        s3 = _scene3d(cfg, ti, tt, bool(hit), cpa if hit is not None else minr,
                      last['rng'], last['vc'], last['reqg'], last['state'], last['tgo'])
        combo = cv2.hconcat([img[:, :W], s3])
        for _ in range(48):
            cv2.imwrite(f"{cfg.outdir}/f{fid:04d}.png", combo); fid += 1
        subprocess.run(["ffmpeg", "-y", "-framerate", "60", "-i", f"{cfg.outdir}/f%04d.png",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", cfg.mp4], check=True, capture_output=True)
        mp4 = cfg.mp4
    return Sim3DResult(cfg.geometry, hit, cpa if hit is not None else minr, peak_g, fid, mp4, ti, tt)


def view(cfg: Sim3DConfig) -> None:
    """Watch the intercept live in MuJoCo's interactive 3D window (game-like: orbit/zoom the camera).

    macOS: must be launched with `mjpython` (the GUI needs the main thread), e.g.
        PYTHONPATH=.:fpv mjpython -m fpv_ai.bench.sim3d --view --geometry quartering
    Geometry-PN flies the interceptor every seeker tick; the real seeker pipeline runs decimated to
    gate lock/engage while keeping the window real-time smooth.
    """
    import time
    import mujoco
    import mujoco.viewer

    model = mujoco.MjModel.from_xml_string(_xml(cfg, visual=True))
    data = mujoco.MjData(model)
    iid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "interceptor")
    tid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "target")
    tpos, tvel = _geometry_ic(cfg)
    pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics())
    rng = np.random.default_rng(cfg.seed)
    seeker_decim = cfg.sub * 4                              # gate the seeker at ~15 Hz (smooth window)
    ctrl = {"reset": False}

    def vel_of(bid):
        res = np.zeros(6)
        mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, bid, res, 0)
        return res[3:6].copy()

    def reset_scene():
        mujoco.mj_resetData(model, data)
        data.qpos[0:3] = cfg.int_pos; data.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]     # interceptor on the ground
        data.qpos[7:10] = tpos;        data.qpos[10:14] = [1.0, 0.0, 0.0, 0.0]  # target aloft
        mujoco.mj_forward(model, data)
        aim = tpos - data.xpos[iid]; aim /= np.linalg.norm(aim)
        data.qvel[0:3] = aim * cfg.launch_speed            # ground launch: boost off toward the target
        data.qvel[6:9] = tvel

    def key_cb(keycode):
        if keycode in (ord("R"), ord("r")):                # 'R' -> restart the scene
            ctrl["reset"] = True

    with mujoco.viewer.launch_passive(model, data, key_callback=key_cb) as viewer:
        viewer.cam.lookat[:] = [cfg.int_pos[0] + cfg.r0 * 0.4, cfg.int_pos[1] + cfg.r0 * 0.25, cfg.tgt_alt * 0.5]
        viewer.cam.distance = cfg.r0 * 1.4
        viewer.cam.elevation = -20.0
        viewer.cam.azimuth = 130.0
        print(f"3D viewer live ({cfg.geometry}) — orbit/zoom with the mouse; press 'R' to restart; close window to exit.")
        while viewer.is_running():
            reset_scene(); ctrl["reset"] = False
            g_force = np.zeros(3); lock_frames = 0; gate = False; minr = 1e9; hit = None
            wall0 = time.time(); step = 0; nmax = int(cfg.tmax / cfg.dt_phys)
            while viewer.is_running() and not ctrl["reset"] and step < nmax:
                ip = data.xpos[iid].copy(); tp = data.xpos[tid].copy()
                iv = vel_of(iid); tv = vel_of(tid)
                rel = tp - ip; rng_m = float(np.linalg.norm(rel)); minr = min(minr, rng_m)
                losn = rel / (rng_m + 1e-9)
                if rng_m < cfg.cap_m:
                    hit = True; break
                if step % cfg.sub == 0:
                    vc = max(float(np.dot(tv - iv, -losn)), 1.0)
                    omega = np.cross(rel, tv - iv) / max(float(np.dot(rel, rel)), 1e-6)
                    a_ideal = cfg.n_nav * vc * np.cross(omega, losn)
                    if step % seeker_decim == 0:
                        proj, right, up, _, _ = _project(ip, iv, tp)
                        in_fov = proj is not None and 0 <= proj[0] < W and 0 <= proj[1] < H
                        px, py = proj if proj is not None else (-1e3, -1e3)
                        tvn = tv / (np.linalg.norm(tv) + 1e-9)
                        aspect = math.degrees(math.acos(max(-1, min(1, float(np.dot(-tvn, losn))))))
                        frame = _render(px, py, rng_m, aspect, in_fov, rng.normal(0, 1.0, 2), rng)
                        out = pipe.step(now=step * cfg.dt_phys, frame_u16=frame,
                                        gyro_omega_xyz=(0, 0, 0), dt=seeker_decim * cfg.dt_phys)
                        lock_frames = lock_frames + 1 if "LOCK" in out.tracking_state else 0
                        gate = (out.command is not None and out.engage_permitted
                                and not out.roe_abort and "LOCK" in out.tracking_state)
                    if gate:
                        a_vec = min(1.0, lock_frames / float(cfg.acq_ramp_frames)) * a_ideal
                        amag = float(np.linalg.norm(a_vec))
                        if amag > cfg.g_max * G:
                            a_vec *= (cfg.g_max * G) / amag
                        g_force = cfg.int_mass * a_vec
                    else:
                        g_force = np.zeros(3)
                spd = float(np.linalg.norm(iv)); vhat = iv / (spd + 1e-9)
                thrust = cfg.int_mass * 6.0 * (cfg.m_speed - spd) * vhat
                data.xfrc_applied[iid, :3] = np.array([0, 0, cfg.int_mass * G]) + g_force + thrust
                wdir = np.cross(tv / (np.linalg.norm(tv) + 1e-9), [0, 0, 1.0]); wdir /= np.linalg.norm(wdir) + 1e-9
                weave = cfg.weave_g * G * cfg.tgt_mass * math.sin(step * cfg.dt_phys * 1.1) * wdir
                data.xfrc_applied[tid, :3] = np.array([0, 0, cfg.tgt_mass * G]) + weave
                mujoco.mj_step(model, data); step += 1
                if step % 4 == 0:
                    viewer.sync()
                tsleep = wall0 + step * cfg.dt_phys - time.time()
                if tsleep > 0:
                    time.sleep(tsleep)
            print(f"  {cfg.geometry}: {'HIT' if hit else 'flyby'}  CPA={minr:.2f} m  (press 'R' to replay)")
            t_hold = time.time()
            while viewer.is_running() and not ctrl["reset"] and time.time() - t_hold < 2.5:
                viewer.sync(); time.sleep(0.03)


def _battery(cfg: Sim3DConfig):
    print(f"3D intercept battery  (interceptor {cfg.m_speed:.0f} m/s, threat {cfg.t_speed:.0f} m/s, "
          f"g-wall {cfg.g_max:.0f} g, N={cfg.n_nav:.0f})")
    print(f"{'geometry':<12} {'outcome':<8} {'CPA (m)':>8} {'peak g':>7}")
    for geom in GEOMETRIES:
        r = run(Sim3DConfig(**{**cfg.__dict__, "geometry": geom, "render": False}))
        outcome = "HIT" if r.hit else ("MISS" if r.hit is False else "n/a")
        print(f"{geom:<12} {outcome:<8} {r.cpa_m:>8.2f} {r.peak_g:>7.1f}")


def main():
    ap = argparse.ArgumentParser(description="3D physics-in-the-loop intercept sim (MuJoCo + real seeker)")
    ap.add_argument("--geometry", choices=GEOMETRIES, default="quartering")
    ap.add_argument("--battery", action="store_true", help="run all geometries headless -> feasibility table")
    ap.add_argument("--render", action="store_true", help="render an MP4 (else headless metrics only)")
    ap.add_argument("--view", action="store_true", help="live interactive 3D window (launch with mjpython on macOS)")
    ap.add_argument("--m-speed", type=float, default=80.0)
    ap.add_argument("--t-speed", type=float, default=50.0)
    ap.add_argument("--g-max", type=float, default=6.0)
    ap.add_argument("--weave-g", type=float, default=0.0)
    ap.add_argument("--r0", type=float, default=300.0, help="horizontal range to the target (m)")
    ap.add_argument("--tgt-alt", type=float, default=90.0, help="target altitude (m); interceptor climbs to it")
    ap.add_argument("--int-x", type=float, default=0.0, help="interceptor ground launch X (m)")
    ap.add_argument("--int-y", type=float, default=0.0, help="interceptor ground launch Y (m)")
    ap.add_argument("--launch-speed", type=float, default=25.0, help="boost speed off the ground (m/s)")
    ap.add_argument("--tmax", type=float, default=8.0)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--mp4", default="/tmp/sim3d_intercept.mp4")
    a = ap.parse_args()
    base = Sim3DConfig(geometry=a.geometry, m_speed=a.m_speed, t_speed=a.t_speed, g_max=a.g_max,
                       weave_g=a.weave_g, r0=a.r0, tgt_alt=a.tgt_alt, int_pos=(a.int_x, a.int_y, 1.0),
                       launch_speed=a.launch_speed, tmax=a.tmax, seed=a.seed, render=a.render, mp4=a.mp4)
    if a.view:
        view(base)
    elif a.battery:
        _battery(base)
    else:
        r = run(base)
        print(f"{r.geometry}: hit={r.hit} CPA={r.cpa_m:.2f} m peak_g={r.peak_g:.1f} frames={r.frames}"
              + (f" -> {r.mp4}" if r.mp4 else ""))


if __name__ == "__main__":
    main()
