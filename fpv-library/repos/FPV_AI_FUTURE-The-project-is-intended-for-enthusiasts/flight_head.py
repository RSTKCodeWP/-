"""GimbalFlightHead — the flight brain for the chosen configuration: FT640 on our 2-axis gimbal, up-camera.

This composes the three proven pieces into the exact arrangement the 2026-07-19 measurement showed is the one
that closes (`launch_and_forget mount="gimbal"`: 10/10, CPA 1.23 m):

    thermal frame ─▶ SeekerGuidancePipeline ─▶ centroid + guidance command
         ▲                (up-camera, FULL ego)          │
         │                                               ▼
    the gimbal keeps the target centred  ◀── GimbalController(head IMU, centroid) ─▶ servo setpoints

Two things this arrangement gets right, both of which were *learned by measurement* and are easy to get
wrong:

1. **Full ego-compensation is architecturally REQUIRED, not optional, on a tracking gimbal.** The head
   rotates to hold the target centred, so raw image motion is (true LOS motion − head motion) — the tracking
   cancels exactly the signal guidance needs. Feeding the head's own inertial rate (its IMU gyro) back into
   the pipeline reconstructs the inertial LOS rate. Without it the *same* gimbal scores 0/5; with it, 10/10.
   So this class builds the pipeline with ``full_ego_compensation=True`` and there is no way to turn it off.

2. **The gimbal steers on the centroid the SEEKER reports, never on truth.** It is a closed perception loop:
   the head points where the detector says the target is, the new frame comes from that pointing, and so on.

Hardware I/O is injected, not imported, so the whole brain is testable without a Pi:
``step(frame_u16, head_gyro_xyz, head_accel_xyz, dt)`` in → guidance command + servo setpoints out. The
caller wires the FT640 grabber, the head IMU, and the 2 gimbal servos (see ``seeker_core.pi5_io``) and streams
the guidance command to the FC over MSP (see ``fpv_ai.msp_override_flight``).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from fpv.gimbal.controller import GimbalConfig, GimbalController
from fpv.guidance.command_map import PilotConfig
from fpv.guidance.march import MarchState, MarchTracker
from fpv.guidance.pipeline import PipelineOutput, SeekerGuidancePipeline


@dataclass(frozen=True)
class FlightHeadStep:
    command: object | None            # AICommand for the FC (up-camera roll/pitch/yaw/throttle), or None
    pan_setpoint_rad: float           # gimbal servo setpoints (relative to the airframe)
    tilt_setpoint_rad: float
    tracking: bool                    # the gimbal has a target to hold
    locked: bool                      # the seeker holds a lock this frame
    centroid_px: tuple[float, float] | None
    los_rate_yaw: float               # inertial LOS rate from the head IMU (clean while centred)
    los_rate_pitch: float
    march_state: str                  # MARCH state: TRACK / COAST / MARCH / LOST (observability)
    pipeline: PipelineOutput          # full pipeline output, for telemetry/observability


class GimbalFlightHead:
    """FT640-on-gimbal, up-camera flight brain. Deterministic; hardware injected by the caller."""

    def __init__(self, *, intrinsics=None, climb_throttle: float = 0.62,
                 pipeline_kwargs: dict | None = None, gimbal_config: GimbalConfig | None = None,
                 guidance_config=None, march: bool = False) -> None:
        kw = dict(pipeline_kwargs or {})
        # The two non-negotiables for this configuration. full_ego_compensation is forced ON (see the class
        # docstring, point 1); passing it in kwargs would only let a caller wrongly turn it off.
        kw.pop("full_ego_compensation", None)
        kw.pop("pilot_config", None)
        self._pipe = SeekerGuidancePipeline(
            intrinsics=intrinsics, guidance_config=guidance_config,
            pilot_config=PilotConfig(up_looking_camera=True, climb_throttle=climb_throttle),
            full_ego_compensation=True, **kw)
        self._gimbal = GimbalController(gimbal_config)
        gc = self._gimbal.cfg
        self._cx, self._cy, self._f = gc.img_w / 2.0, gc.img_h / 2.0, gc.f_px
        # MARCH: dead-reckon the target bearing so a lock gap does not lose a CROSSING target. Off by default
        # -- the from-below design case survives gaps without it, and MARCH is the crossing-case lever.
        self._march = MarchTracker() if march else None
        self._R_ci = np.eye(3)            # camera->inertial orientation, integrated from the head gyro

    def designate(self, center_px: tuple[float, float]) -> None:
        """Operator designation — seed the acquisition basket (IDLE → ACQUIRE)."""
        self._pipe.designate(center_px)

    def step(self, now: float, frame_u16, head_gyro_xyz: tuple[float, float, float],
             head_accel_xyz: tuple[float, float, float], dt: float, *,
             committed: bool = False) -> FlightHeadStep:
        # 1. Perceive. The head IMU gyro drives the full ego-compensation that reconstructs the inertial LOS
        #    rate the tracking gimbal would otherwise hide.
        out = self._pipe.step(now, frame_u16, head_gyro_xyz, dt, committed=committed)

        # 2. Point. The gimbal slews to hold the seeker's reported centroid. Without MARCH, a lock gap yields
        #    centroid=None and the gimbal just holds inertial attitude -- which loses a CROSSING target that
        #    keeps moving. With MARCH, a gap is filled by a dead-reckoned predicted centroid.
        centroid = out.centroid_px
        march_state = MarchState.LOST
        if self._march is not None:
            centroid, march_state = self._march_centroid(out, head_gyro_xyz, dt)

        g = self._gimbal.step(head_gyro_xyz, head_accel_xyz, centroid, dt)

        return FlightHeadStep(
            command=out.command, pan_setpoint_rad=g.pan_setpoint_rad, tilt_setpoint_rad=g.tilt_setpoint_rad,
            tracking=g.tracking, locked=bool(out.locked), centroid_px=out.centroid_px,
            los_rate_yaw=g.los_rate_yaw, los_rate_pitch=g.los_rate_pitch,
            march_state=march_state.value, pipeline=out)

    def _cam_dir(self, px, py):
        """Camera-frame unit vector of a pixel (boresight = +z)."""
        v = np.array([(px - self._cx) / self._f, -(py - self._cy) / self._f, 1.0])
        return v / (np.linalg.norm(v) + 1e-12)

    def _pixel_of(self, cam_dir):
        """Project a camera-frame direction back to a pixel; None if behind the boresight."""
        if cam_dir[2] <= 1e-6:
            return None
        return (self._cx + self._f * cam_dir[0] / cam_dir[2],
                self._cy - self._f * cam_dir[1] / cam_dir[2])

    def _march_centroid(self, out: PipelineOutput, head_gyro_xyz, dt):
        """MARCH in an inertial frame maintained from the head gyro: measure the target bearing when LOCKED,
        dead-reckon it through a gap, and hand the gimbal a PREDICTED centroid so it keeps slewing along the
        target's path instead of freezing. Returns (centroid_for_gimbal, march_state)."""
        # integrate the camera->inertial orientation with the head's inertial rate (strapdown propagation)
        w = np.asarray(head_gyro_xyz, dtype=float)
        wn = float(np.linalg.norm(w))
        if wn > 1e-9:
            k = w / wn; th = wn * dt
            K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
            self._R_ci = self._R_ci @ (np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * (K @ K))

        # Feed MARCH the measurement ONLY on a real LOCK -- not the pipeline's stale REACQUIRE/search centroid,
        # which it always emits and which may sit on nothing. Otherwise MARCH gets None and dead-reckons.
        locked = ("LOCK" in out.tracking_state) and out.centroid_px is not None
        meas_inertial = self._R_ci @ self._cam_dir(*out.centroid_px) if out.centroid_px is not None else None
        mstep = self._march.update(dt, meas_inertial if locked else None)

        if not self._march.initialized:
            return out.centroid_px, mstep.state             # before the first lock, defer to the pipeline
        # Once enrolled, the gimbal follows MARCH's bearing: on a LOCK it has converged to the real centroid
        # (smoothed); in a gap it is the dead-reckoned prediction that keeps the gimbal on a crossing target.
        pred_px = self._pixel_of(self._R_ci.T @ mstep.command_dir)
        return (pred_px if pred_px is not None else out.centroid_px), mstep.state

    @property
    def pipeline(self) -> SeekerGuidancePipeline:
        return self._pipe

    @property
    def gimbal(self) -> GimbalController:
        return self._gimbal
