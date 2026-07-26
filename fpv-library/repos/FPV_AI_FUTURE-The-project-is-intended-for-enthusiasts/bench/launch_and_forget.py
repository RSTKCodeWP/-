"""LAUNCH-AND-FORGET closed loop -- the WHOLE system as one proof (навёлся→зафиксировал→подтвердил→
запустил→ЗАБЫЛ).

Every other harness proves a PIECE:
  * sim3d_honest closes the PHYSICS loop but drives the guidance pipeline + PN DIRECTLY -- it skips the
    mission FSM, the two-press crypto authority, and the arming gate.
  * sil_runtime runs the FULL stack (mission -> arming -> MSP) but the physics loop is OPEN -- the frames
    do not come from the interceptor's own motion, so nothing actually CLOSES.

This module closes BOTH at once. It runs the real ``ProductionRuntime`` -- perception -> mission FSM
(acquire→study→ready→commit→engage→terminal) -> REAL Ed25519 dual-signature authority -> arming -- inside
an honest quad closing loop with an UP-LOOKING thermal camera (intercept from below). The operator's TWO
PRESSES are injected the moment the mission reaches READY; after that NOTHING external drives the aircraft
-- it flies itself on its own perception until contact.  That is "launch and forget", proven end to end.

HONEST SCOPE
------------
  * Quad dynamics are the honest tilt-bounded model: a_lateral = g*tan(theta), theta<=theta_max=40deg ->
    0.84 g ceiling (identical bound to quad_sim.py). Throttle closes the vertical gap. NOT a missile.
  * The camera looks straight UP at a warm target on a cold sky (excellent contrast); guidance uses the
    up-camera PN mapping (a_cmd_az->roll, a_cmd_el->pitch, throttle->climb).
  * The authorization is a REAL dual-signed Ed25519 commit (not synthetic) -> it exercises the real arming
    gate; a synthetic auth could never arm (arming.py invariant).
  * Still a SIM: it proves the SYSTEM logic closes on honest physics + real perception on rendered thermal.
    It is NOT flight and NOT HIL (no real seeker/FC hardware in this loop).

Run:  PYTHONPATH=.:fpv python3 -m fpv_ai.bench.launch_and_forget
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from fpv.guidance.bearing_rate import GuidanceConfig
from fpv.guidance.command_map import PilotConfig
from fpv.guidance.march import MarchTracker
from fpv.seeker.geometry import ft640_intrinsics
from fpv_ai.bench.sim3d import F_PX, H, W, WINGSPAN_M
from fpv_ai.betaflight_link.arming import ArmingConfig, ArmState
from fpv_ai.betaflight_link.authorization import sign_commit
from fpv_ai.betaflight_link.mission_fsm import MissionPhase
from fpv_ai.betaflight_link.serial_link import MockFcChannel, MspLink
from fpv_ai.production_runtime import ProductionConfig, ProductionRuntime

_G = 9.81
_THETA_MAX = math.radians(40.0)          # 0.84 g lateral ceiling -- the honest quad wall
_YY, _XX = np.mgrid[0:H, 0:W]
_YY = _YY.astype(np.float64); _XX = _XX.astype(np.float64)
_T0, _CPK, _NETD = 240.0, 40.0, 14.0


@dataclass
class LaFConfig:
    # geometry (metres), interceptor climbs from below toward a target above
    int_pos: tuple = (0.0, 0.0, 0.0)
    int_climb_mps: float = 34.0           # initial climb rate
    tgt_pos: tuple = (3.0, 1.5, 105.0)    # target ~overhead (operator cued the nose) + small offset
    tgt_vel: tuple = (-0.6, 0.3, -6.0)    # weak drift + descent (closes the vertical gap)
    tgt_weave_g: float = 0.0              # optional horizontal weave (g)
    climb_accel_max: float = 16.0         # throttle authority about hover (m/s^2)
    cap_m: float = 1.5                    # contact radius == body-to-body bar
    dt: float = 1.0 / 100.0
    tmax: float = 6.0
    sub: int = 2                          # vision every ``sub`` physics steps (~50 Hz)
    seed: int = 11
    vibration_px: float = 0.4             # soft-mounted head -> clean lambda-dot (few spurious ROE)
    climb_throttle: float = 0.62
    occl_start_s: float = 0.0             # target hidden (cloud) window during the close -- 0,0 = off
    occl_end_s: float = 0.0
    vc_sched_mps: float = 40.0            # real vertical closing (climb + target descent) for the PN magnitude
    crossing_thresh_radps: float = 0.6    # relax looming-based HIGH_CROSSING for the from-below geometry
    abort_g_margin: float = 2.5           # SATURATE a transient over-demand at max-g; abort only if >2.1 g gross
    passive_range: bool = False           # size-free parallax range feeding the commit gate (needs own INS)
    # STRAPDOWN camera: the boresight tilts with the airframe. False = world-stabilised head, i.e. an ideal
    # gimbal -- what this harness silently modelled before 2026-07-19, and why its numbers were optimistic.
    camera_tilts_with_body: bool = True
    # Remove the TRANSLATIONAL ego-shift too, not just image roll. Needs a real body rate (this harness now
    # derives one from the camera-frame rotation). Without it a strapdown head reads its own tilt as target
    # motion -- ~12 px per degree against a ~14 px target.
    full_ego_compensation: bool = False
    # Camera mount. "strapdown" = boresight rigidly on the body (the doctrine build).
    # "gimbal" = the REAL 2-axis stabilised head: it slews toward the target the SEEKER reports, with the
    #            servo rate limit and lag from fpv.gimbal.plant, and HOLDS inertial attitude when unlocked.
    #            This is a closed perception loop -- the gimbal never sees truth.
    # Setting camera_tilts_with_body=False instead gives an IDEAL gimbal (perfect, instant) -- a ceiling,
    # not a build.
    mount: str = "strapdown"
    gimbal_rate_max_dps: float = 500.0     # fpv.gimbal.plant.GimbalPlant default
    gimbal_tau_s: float = 0.01
    # First-order ATTITUDE LAG (s). A quad cannot change bank instantly, so it cannot change where a
    # strapdown boresight points instantly either. With 0 the camera teleports between commanded attitudes
    # and reports impossible body rates (we measured 558 deg/s), which is neither a strapdown camera nor a
    # real plant. Matches quad_sim.attitude_tau_s.
    attitude_tau_s: float = 0.10
    terminal_hold: bool = False           # W4 ten-tau wall: freeze the established course inside the terminal
    terminal_hold_px: float = 240.0       # range-free trigger: target span in the frame (px)
    # Leaky-accumulator persistence before the g-envelope ROE abort. 0 = the shipped default (abort on the
    # first over-demand tick). Setting it to 25 stops a transient spike from ending the engagement and takes
    # formal COMMITTED from 1/5 seeds to 4/5 -- but it is NOT the default, because the same change turns a
    # head-on closed-loop hit into a miss (our ⊥LOS law blows up terminally). See GuidanceConfig.
    envelope_persist_ticks: int = 0
    # --- harder scene: confuser clutter + degraded FT640 data (0 / 1.0 == the clean default, bit-identical) ---
    n_decoys: int = 0                     # number of hot confuser objects fixed in the sky (inertial dirs)
    decoy_intensity: float = 0.8          # each decoy's brightness as a fraction of the target peak (>=1 = as bright)
    netd_scale: float = 1.0               # sensor-noise multiplier -- bad AGC / noisy rail on the FT640
    clutter_std: float = 2.0              # background texture std (warm hazy sky vs the clean cold-sky ideal)
    discrimination: bool = False          # opt-in clutter discrimination; UNTUNED for this synthetic scene
    cue_gimbal_at_target: bool = False    # operator/ground cue: pre-slew the gimbal onto the target bearing
                                          # at launch (needed for a SIDE-aspect target off the vertical FOV)
    march: bool = False                   # MARCH: dead-reckon the target bearing during a lock gap and keep
                                          # the gimbal slewing to the prediction (vs holding at the last fix)


@dataclass
class LaFResult:
    hit: bool
    cpa_m: float
    phases: list = field(default_factory=list)     # (t, MissionPhase) transitions
    armed_ai_active: bool = False
    committed: bool = False
    n_ticks: int = 0
    lock_frames: int = 0
    decoy_lock_frames: int = 0            # frames the tracker sat on a CONFUSER instead of the true target


def _target_signature(T, px, py, rng_m, vib):
    """Add the winged-UAV thermal signature (warm body + two hot engine spots) at (px,py)."""
    atmo = math.exp(-rng_m / 1500.0)
    span = min(F_PX * WINGSPAN_M / max(rng_m, 0.5), 900.0)
    cx, cy = px + vib[0], py + vib[1]
    fl = max(span * 0.55, 1.6); fw = max(span * 0.10, 1.0)
    T += 20.0 * atmo * np.exp(-(((_YY - cy) ** 2) / (2 * fl ** 2) + ((_XX - cx) ** 2) / (2 * fw ** 2)))
    ho = span * 0.30; hw = max(span * 0.07, 1.0)
    for s in (-1.0, 1.0):                                   # engine/motor hot spots
        hy = cy + s * ho
        T += 70.0 * atmo * np.exp(-((_XX - cx) ** 2 + (_YY - hy) ** 2) / (2 * hw ** 2))
    return T


def _render_up(px, py, rng_m, in_fov, vib, rng):
    """Up-looking frame: a COLD uniform sky (great contrast) + a warm range-attenuated target."""
    T = 246.0 + rng.normal(0.0, 2.0, (H, W))                # cold sky, low clutter looking straight up
    if in_fov:
        T = _target_signature(T, px, py, rng_m, vib)
    counts = 4096.0 + (T - _T0) * _CPK + rng.normal(0.0, _NETD, (H, W))
    return np.clip(counts, 0.0, 65535.0).astype(np.uint16)


def _render_scene(px, py, rng_m, in_fov, vib, rng, *, decoys=(), netd_scale=1.0, clutter_std=2.0):
    """A HARDER frame: the target + confuser decoys + degraded FT640 data.

    ``decoys`` is a list of (dx_px, dy_px, intensity) already projected through the CURRENT camera basis by
    the caller -- so as the gimbal slews, clutter sweeps across the frame the way real background does. Each
    decoy is a hot blob (other aircraft exhaust, sun glint, a ground/roof hotspot) whose ``intensity`` is a
    fraction of the target's peak; >= 1.0 means it is AS BRIGHT as the target -- a genuine confuser.
    ``netd_scale`` inflates the sensor noise (bad FT640 AGC / a noisy rail); ``clutter_std`` is the
    background texture (a warm hazy sky is not the clean cold sky of the from-below ideal).
    """
    T = 246.0 + rng.normal(0.0, clutter_std, (H, W))
    for dx, dy, inten in decoys:
        if 0 <= dx < W and 0 <= dy < H:
            hw = 2.5
            T += 70.0 * float(inten) * np.exp(-((_XX - dx) ** 2 + (_YY - dy) ** 2) / (2 * hw ** 2))
    if in_fov:
        T = _target_signature(T, px, py, rng_m, vib)
    counts = 4096.0 + (T - _T0) * _CPK + rng.normal(0.0, _NETD * netd_scale, (H, W))
    return np.clip(counts, 0.0, 65535.0).astype(np.uint16)


def _keys():
    from nacl.signing import SigningKey
    ka, kb = SigningKey.generate(), SigningKey.generate()
    return (bytes(ka), bytes(ka.verify_key)), (bytes(kb), bytes(kb.verify_key))


def _camera_basis(accel: np.ndarray) -> tuple:
    """Camera axes for a STRAPDOWN head, given the acceleration the airframe is currently producing.

    A quad's thrust is rigidly along body +z, and so is the camera boresight -- so the boresight IS the
    thrust direction. Thrust/m = a_total - g_vec = (ax, ay, az + g), which we already compute, so no extra
    attitude state is needed and the camera can never disagree with the plant.

    This is the physics `launch_and_forget` was missing: it projected through `fwd = rel[2]`, pinning the
    boresight to world-up so it never tilted with the airframe -- silently modelling a PERFECTLY STABILISED
    (gimballed) camera. That hides the dominant strapdown defect, because the FT640's half-VFOV is 19.9 deg
    while the bank limit is 40 deg: a centred target -- which is what a collision course produces -- leaves
    the frame at about 20 deg of bank. See docs/CHECKPOINT.md section 5.0.

    Returns (right, up, fwd) unit vectors. At hover (accel=0) this is exactly the old world-aligned basis,
    so the model degrades continuously into the previous behaviour.
    """
    thrust = np.array([accel[0], accel[1], accel[2] + _G], dtype=float)
    n = float(np.linalg.norm(thrust))
    fwd = np.array([0.0, 0.0, 1.0]) if n < 1e-9 else thrust / n
    # Minimal rotation carrying world-up onto the boresight (no yaw component -- yaw only spins the image).
    axis = np.cross([0.0, 0.0, 1.0], fwd)
    s = float(np.linalg.norm(axis))
    if s < 1e-9:
        return np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), fwd
    axis /= s
    ang = math.atan2(s, float(fwd[2]))
    c, sn = math.cos(ang), math.sin(ang)

    def rot(v):
        v = np.asarray(v, dtype=float)
        return v * c + np.cross(axis, v) * sn + axis * float(axis @ v) * (1.0 - c)

    return rot([1.0, 0.0, 0.0]), rot([0.0, 1.0, 0.0]), fwd


def _slew_boresight(cur: np.ndarray, desired: np.ndarray, rate_max_dps: float, tau_s: float,
                    dt: float) -> np.ndarray:
    """Slew a gimbal boresight toward `desired` with the REAL servo dynamics.

    Same first-order-lag-plus-slew-rate-limit law as ``fpv.gimbal.plant._servo``, applied to the boresight
    direction in this harness's frame rather than to the module's pan/tilt pair (the module assumes the
    camera looks along +x; this harness looks along +z, and re-deriving that mapping here would risk a
    silent frame bug for no gain). The DYNAMICS -- the part that decides whether a gimbal can actually keep
    up -- are the module's.

    Travel limits are not modelled: the owner's QD115TB has +-180 deg, against a +-40 deg bank envelope, so
    travel is not the binding constraint. Slew RATE and lag are, which is exactly what this models.
    """
    cur = cur / (np.linalg.norm(cur) + 1e-12)
    desired = desired / (np.linalg.norm(desired) + 1e-12)
    axis = np.cross(cur, desired)
    s_ax = float(np.linalg.norm(axis))
    ang = math.atan2(s_ax, float(cur @ desired))
    if s_ax < 1e-12 or ang < 1e-12:
        return cur
    axis /= s_ax
    step = ang * (min(1.0, dt / (tau_s + dt)) if tau_s > 0 else 1.0)   # first-order lag
    step = max(-math.radians(rate_max_dps) * dt,                        # slew-rate cap
               min(math.radians(rate_max_dps) * dt, step))
    c, sn = math.cos(step), math.sin(step)
    return cur * c + np.cross(axis, cur) * sn + axis * float(axis @ cur) * (1.0 - c)


def _accel_from_command(cmd, cfg: LaFConfig) -> np.ndarray:
    """Honest quad map: roll/pitch -> horizontal a=g*tan(theta); throttle -> climb about hover."""
    if cmd is None:
        return np.array([0.0, 0.0, 0.0])
    ax = _G * math.tan(_clamp(cmd.roll_cmd, -1.0, 1.0) * _THETA_MAX)      # world +x (body right)
    ay = _G * math.tan(_clamp(cmd.pitch_cmd, -1.0, 1.0) * _THETA_MAX)     # world +y (body forward)
    az = (_clamp(cmd.throttle_cmd, 0.0, 1.0) - 0.5) * 2.0 * cfg.climb_accel_max   # climb/descend
    return np.array([ax, ay, az])


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def run_launch_and_forget(cfg: LaFConfig | None = None, *, verbose: bool = False,
                          debug: bool = False, traj: list | None = None,
                          frames: list | None = None) -> LaFResult:
    cfg = cfg or LaFConfig()
    rng = np.random.default_rng(cfg.seed)
    (a, ap), (b, bp) = _keys()

    arming = ArmingConfig(armed_idle_dwell_s=0.05, stabilize_dwell_s=0.05, ramp_s=0.1)
    rt = ProductionRuntime(
        link=MspLink.for_bench(MockFcChannel()), operator_public_keys=[ap, bp],
        intrinsics=ft640_intrinsics(), classifier=lambda frame, centroid: True,   # trusted-vote placeholder
        # target_span_m MUST match what the scene actually renders (WINGSPAN_M). Subtense range is
        # f*assumed_span/extent_px, so an assumed span that is 2x the truth reports 2x the range -- silently,
        # with no symptom anywhere in the system. That mismatch (assume 4 m, render 2 m) is exactly why the
        # commit gate never saw range<=50 m. In flight the true span is genuinely unknown, so this error is
        # unavoidable there; that is the case for the size-free passive range (fpv.guidance.passive_range).
        config=ProductionConfig(arming_config=arming, require_measured_range=False,
                                passive_range=cfg.passive_range, target_span_m=WINGSPAN_M),
        pipeline_kwargs=dict(
            pilot_config=PilotConfig(up_looking_camera=True, climb_throttle=cfg.climb_throttle),
            # Clutter discrimination -- OFF on the clean from-below scene (no confusers), ON when the scene
            # has decoys/bad data. These are the anti-clutter tools: appearance correlation rejects blobs
            # that don't LOOK like the enrolled target, trajectory continuity rejects blobs inconsistent with
            # its motion, JPDA associates among multiple blobs, consensus needs cues to agree.
            # Clutter discrimination is OPT-IN and OFF by default. Measured 2026-07-20: on this SYNTHETIC
            # clutter render every discrimination feature (correlation, trajectory continuity, JPDA,
            # consensus) either mis-triggers or is too strict and the target never locks (0/300, stuck in
            # ACQUIRE). The features are calibrated for REAL thermal, not Gaussian-blob decoys -- so clutter
            # robustness is an honestly OPEN question that this sim cannot answer; it needs real thermal
            # (real_ingest / HIL, GAP 2 in REMAINING_WORK.md). Left wired so it can be tuned there.
            correlation=cfg.discrimination, trajectory_continuity=cfg.discrimination,
            # ROE gate tuned for INTERCEPT-FROM-BELOW: the closing cue is vertical (weak passive looming
            # early), so schedule the real closing Vc and relax the looming-based HIGH_CROSSING
            # misclassification. The g-envelope guard (abort_g_margin=1.0, required_g<=0.84g) STAYS on.
            use_terminal_hold=cfg.terminal_hold, terminal_hold_subtense_px=cfg.terminal_hold_px,
            # A tracking gimbal makes full ego-compensation ARCHITECTURALLY REQUIRED, not optional.
            # The head deliberately rotates to hold the target centred, so image motion is
            # (true LOS motion - head motion) -- i.e. the thing guidance needs is precisely what the
            # tracking cancels. Feeding the head's own inertial rate back in is what reconstructs the
            # inertial LOS rate. Measured: gimbal without it 0/5 (CPA 2.52), with it 10/10 (CPA 1.23).
            full_ego_compensation=cfg.full_ego_compensation or cfg.mount == "gimbal",
            guidance_config=GuidanceConfig(Vc_sched_mps=cfg.vc_sched_mps,
                                           crossing_rate_threshold_radps=cfg.crossing_thresh_radps,
                                           abort_g_margin=cfg.abort_g_margin,
                                           envelope_abort_persist_ticks=cfg.envelope_persist_ticks)))

    # the operator's dual-signed commit (the TWO PRESSES), submitted once the mission reaches READY
    now0 = 1000.0
    auth = rt.submit_authorization(sign_commit(
        dict(keypress_recorded=True, keypress_ts=now0, issued_at_s=now0, expires_at_s=now0 + 60,
             mission_goal="KINETIC", synthetic=False, nonce="laf1"), [a, b]))

    ip = np.array(cfg.int_pos, float); iv = np.array([0.0, 0.0, cfg.int_climb_mps])
    tp = np.array(cfg.tgt_pos, float); tv = np.array(cfg.tgt_vel, float)
    res = LaFResult(hit=False, cpa_m=1e9)
    designated = False
    cmd_accel = np.zeros(3)          # what guidance ASKED for
    applied_accel = np.zeros(3)      # what the airframe has actually DELIVERED (first-order lag)
    prev_basis = (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0]))
    gim_bore = np.array([0.0, 0.0, 1.0])   # gimbal boresight (world); starts pointing up like the body
    if cfg.cue_gimbal_at_target and cfg.mount == "gimbal":
        # Ground/operator cue: the target is confirmed and its bearing handed to the interceptor, so the
        # gimbal is already pointed at it at launch (a SIDE-aspect target sits outside the up-camera's
        # vertical FOV, so without the cue it is never in frame and never locks).
        gim_bore = (tp - ip) / (np.linalg.norm(tp - ip) + 1e-9)
    last_centroid = None                   # what the SEEKER last reported -- the gimbal's only cue
    last_locked = False                    # was the last frame a real lock (vs a coasted/stale centroid)?
    march_tracker = None
    if cfg.march and cfg.mount == "gimbal":
        march_tracker = MarchTracker()
        if cfg.cue_gimbal_at_target:
            march_tracker.start(gim_bore)  # seed the estimate on the ground-cued bearing
    last_phase = None

    # Confuser decoys as FIXED inertial directions near the initial target bearing (the hard case: clutter in
    # the same part of sky as the target). Generated once, projected through the camera each frame so they
    # sweep realistically as the gimbal slews.
    decoy_dirs = []
    if cfg.n_decoys > 0:
        los0 = (tp - ip) / (np.linalg.norm(tp - ip) + 1e-9)
        for _ in range(cfg.n_decoys):
            d = los0 + rng.normal(0.0, 0.18, 3)            # ~10 deg scatter around the target bearing
            decoy_dirs.append((d / (np.linalg.norm(d) + 1e-9),
                               cfg.decoy_intensity * float(rng.uniform(0.6, 1.3))))
    lock_on_decoy = 0

    for step in range(int(cfg.tmax / cfg.dt)):
        rel = tp - ip
        rng_m = float(np.linalg.norm(rel))
        res.cpa_m = min(res.cpa_m, rng_m)
        if traj is not None:
            traj.append((round(step * cfg.dt, 4), ip.copy(), tp.copy()))
        if rng_m < cfg.cap_m:
            res.hit = True
            break

        if step % cfg.sub == 0:
            # STRAPDOWN: the boresight tilts with the airframe (see _camera_basis). With
            # camera_tilts_with_body=False the head is world-stabilised, i.e. an ideal gimbal -- which is
            # what this harness silently assumed before 2026-07-19.
            if cfg.mount == "gimbal":
                # REAL stabilised head: slew toward the target the SEEKER reported, rate-limited and lagged.
                # No lock -> hold inertial attitude (that is what a stabilised head does; it does NOT follow
                # the body). The gimbal never sees truth, so this stays a closed perception loop.
                bright, bup, bfwd = _camera_basis(applied_accel)
                # world direction of the last reported centroid = the seeker's bearing measurement
                meas_dir = None
                if last_centroid is not None:
                    az = math.atan2(last_centroid[0] - W / 2.0, F_PX)
                    el = math.atan2(-(last_centroid[1] - H / 2.0), F_PX)
                    prev_r, prev_u, prev_f = prev_basis
                    v = prev_f + math.tan(az) * prev_r + math.tan(el) * prev_u
                    meas_dir = v / (np.linalg.norm(v) + 1e-12)
                if march_tracker is not None:
                    # MARCH: feed the measurement only when the last frame was a REAL lock; on a gap it
                    # dead-reckons and keeps the gimbal moving along the target's bearing (the crossing fix).
                    mstep = march_tracker.update(cfg.sub * cfg.dt, meas_dir if last_locked else None)
                    gim_bore = _slew_boresight(gim_bore, mstep.command_dir, cfg.gimbal_rate_max_dps,
                                               cfg.gimbal_tau_s, cfg.sub * cfg.dt)
                elif meas_dir is not None:
                    gim_bore = _slew_boresight(gim_bore, meas_dir, cfg.gimbal_rate_max_dps,
                                               cfg.gimbal_tau_s, cfg.sub * cfg.dt)
                cright, cup, cfwd = _camera_basis(np.array([0.0, 0.0, 0.0]))
                cfwd = gim_bore
                ref = bup if abs(float(gim_bore @ bup)) < 0.9 else bright
                cright = np.cross(ref, cfwd); cright /= (np.linalg.norm(cright) + 1e-12)
                cup = np.cross(cfwd, cright)
            elif cfg.camera_tilts_with_body:
                cright, cup, cfwd = _camera_basis(applied_accel)
            else:
                cright, cup, cfwd = (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]),
                                     np.array([0.0, 0.0, 1.0]))
            # Body rate the seeker's gyro would report: the rotation carrying the previous camera frame
            # onto this one, expressed in the CURRENT camera axes (x,y = boresight pitch/yaw -> image
            # translation; z = roll about the boresight -> image rotation).
            dt_vis = cfg.sub * cfg.dt
            w_world = np.cross(prev_basis[2], cfwd) / max(dt_vis, 1e-9)
            gyro = (float(w_world @ cright), float(w_world @ cup), float(w_world @ cfwd))
            prev_basis = (cright, cup, cfwd)

            fwd = float(rel @ cfwd)                        # range along the boresight
            in_fov = False; px = py = -1e3
            if fwd > 1.0:
                px = W / 2.0 + F_PX * float(rel @ cright) / fwd
                py = H / 2.0 - F_PX * float(rel @ cup) / fwd
                in_fov = 0 <= px < W and 0 <= py < H
            vib = rng.normal(0.0, cfg.vibration_px, 2)
            occluded = cfg.occl_start_s < cfg.occl_end_s and cfg.occl_start_s <= step * cfg.dt <= cfg.occl_end_s
            if decoy_dirs or cfg.netd_scale != 1.0:
                # project each inertial decoy direction through the CURRENT camera frame
                decoy_px = []
                for d, inten in decoy_dirs:
                    df = float(d @ cfwd)
                    if df > 0.2:
                        dpx = W / 2.0 + F_PX * float(d @ cright) / df
                        dpy = H / 2.0 - F_PX * float(d @ cup) / df
                        decoy_px.append((dpx, dpy, inten))
                frame = _render_scene(px, py, rng_m, in_fov and not occluded, vib, rng,
                                      decoys=decoy_px, netd_scale=cfg.netd_scale, clutter_std=cfg.clutter_std)
            else:
                frame = _render_up(px, py, rng_m, in_fov and not occluded, vib, rng)

            # designate on the very first vision tick (operator points the nose / cues the target)
            if not designated:
                rt.designate((W / 2.0, H / 2.0) if not in_fov else (px, py))
                designated = True

            # DOCTRINE: the operator submits the dual-signed commit only once the mission is READY.
            send = auth if rt.mission_phase in (MissionPhase.READY, MissionPhase.ENGAGING) else None
            # own_accel/own_velocity = what the INS gives us in flight. The passive-range EKF needs them as
            # the KNOWN input; the parallax gate is computed from own_accel alone (filter-independent).
            out, rtstep = rt.step(now0 + step * cfg.dt, frame, gyro, cfg.sub * cfg.dt,
                                  authorization=send,
                                  own_accel_xyz=tuple(applied_accel), own_velocity_xyz=tuple(iv))
            last_centroid = out.centroid_px if out.centroid_px is not None else last_centroid
            last_locked = "LOCK" in out.tracking_state and out.centroid_px is not None
            res.n_ticks += 1
            if "LOCK" in out.tracking_state:
                res.lock_frames += 1
            # decoy discrimination: is the tracked centroid on the TRUE target, or did clutter steal it?
            if decoy_dirs and out.centroid_px is not None and in_fov and "LOCK" in out.tracking_state:
                to_tgt = math.hypot(out.centroid_px[0] - px, out.centroid_px[1] - py)
                near_decoy = any(math.hypot(out.centroid_px[0] - dx, out.centroid_px[1] - dy) < 12.0
                                 for dx, dy, _ in decoy_px)
                if to_tgt > 20.0 and near_decoy:
                    lock_on_decoy += 1
            if rt.mission_phase != last_phase:
                res.phases.append((round(step * cfg.dt, 3), rt.mission_phase))
                last_phase = rt.mission_phase
            if frames is not None:
                frames.append(dict(t=round(step * cfg.dt, 3), frame=frame.copy(),
                                   centroid=out.centroid_px, locked=("LOCK" in out.tracking_state),
                                   phase=rt.mission_phase.name, ip=ip.copy(), tp=tp.copy(),
                                   speed=float(np.linalg.norm(iv)), rng=float(rng_m),
                                   px=float(px), py=float(py), in_fov=bool(in_fov)))
            if rtstep.arm_state == ArmState.AI_ACTIVE:
                res.armed_ai_active = True
            res.committed = res.committed or rt.committed
            # HONEST gate: the aircraft flies its guidance ONLY while the mission is ENGAGING (post-trigger,
            # through terminal). Before the two-press it is pre-launch; after an abort it coasts (default-DENY).
            fly = rt.mission_phase is MissionPhase.ENGAGING and out.command is not None
            cmd_accel = _accel_from_command(out.command, cfg) if fly else np.zeros(3)
            if cfg.mount == "gimbal" and fly:
                # GIMBAL-ANGLE RESOLUTION. Guidance measures az/el in the HEAD frame, but the command is
                # flown by the AIRFRAME. With a strapdown head those frames coincide, so nothing is needed.
                # With a gimbal the head is deliberately decoupled -- so the command must be resolved through
                # the known head orientation before it means anything to the airframe. This is why every real
                # gimballed seeker carries angle resolvers; without it the aircraft banks in the head's frame
                # and the loop is simply wired to the wrong axes.
                _w = cmd_accel[0] * cright + cmd_accel[1] * cup
                cmd_accel = np.array([_w[0], _w[1], cmd_accel[2]])
            if debug and (step % (cfg.sub * 2) == 0 or out.roe_abort):
                if out.roe_abort:
                    print("   >> ROE reason: %s" % out.reason)
                print("t=%.2f %-9s lock=%d roe=%d perm=%d rng=%s tgo=%s px=%.0f py=%.0f cmd=%s" % (
                    step * cfg.dt, rt.mission_phase.name, out.locked, out.roe_abort, out.engage_permitted,
                    ("%.0f" % out.range_m) if out.range_m else "--",
                    ("%.2f" % out.t_go_s) if out.t_go_s else "--", px, py,
                    "r%.2f p%.2f t%.2f" % (out.command.roll_cmd, out.command.pitch_cmd, out.command.throttle_cmd)
                    if out.command else "none"))

        # honest quad dynamics: the airframe LAGS the command (attitude cannot step)
        if cfg.attitude_tau_s > 0.0:
            applied_accel = applied_accel + (cmd_accel - applied_accel) * min(1.0, cfg.dt / cfg.attitude_tau_s)
        else:
            applied_accel = cmd_accel
        iv = iv + applied_accel * cfg.dt
        ip = ip + iv * cfg.dt
        if cfg.tgt_weave_g > 0.0:
            tv[0] += cfg.tgt_weave_g * _G * math.sin(step * cfg.dt * 1.3) * cfg.dt
        tp = tp + tv * cfg.dt

    res.decoy_lock_frames = lock_on_decoy
    if verbose:
        print("phases:", " -> ".join("%s@%.2fs" % (p.name, t) for t, p in res.phases))
        print("armed_AI_ACTIVE=%s committed=%s lock=%d/%d  CPA=%.2fm  HIT=%s" % (
            res.armed_ai_active, res.committed, res.lock_frames, res.n_ticks, res.cpa_m, res.hit))
    return res


def main() -> None:  # pragma: no cover
    r = run_launch_and_forget(verbose=True)
    print("=" * 70)
    print("LAUNCH-AND-FORGET:", "HIT %.2fm" % r.cpa_m if r.hit else "MISS %.2fm" % r.cpa_m)


if __name__ == "__main__":
    main()
