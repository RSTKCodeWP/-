"""seeker_core contracts — the typed boundaries between every stage and adapter.

Every value that crosses a boundary is a frozen, validated, timestamped dataclass carrying provenance
and a `synthetic` flag. These contracts ARE the honesty guarantees: a stage physically cannot pass on
a fabricated line-of-sight or an invented range, because the type forces `Optional`/`None` where the
quantity is unobservable. Versioned so an FPGA/C implementation can be checked bit-for-bit against it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

SCHEMA_VERSION = "seeker_core.v1"


# ── provenance (attached to everything crossing a boundary) ───────────────────────────────────────
@dataclass(frozen=True)
class Provenance:
    source: str                      # who produced this ("ft640", "sim", "imu0", "operator", ...)
    t_capture_ns: int                # hardware/monotonic capture time (ns) — the sync anchor
    synthetic: bool = True           # True unless it came from real, attested hardware
    note: str = ""


# ── inputs ────────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Frame:
    """One thermal frame. `radiometric` distinguishes true Y16 from 8-bit AGC (a fidelity fact, not a flag to fake)."""
    pixels: np.ndarray               # (H, W) uint16 counts
    radiometric: bool                # True = radiometric Y16; False = 8-bit AGC mapped to counts
    provenance: Provenance

    def __post_init__(self) -> None:
        if self.pixels.ndim != 2:
            raise ValueError("Frame.pixels must be 2-D (H,W)")
        if self.pixels.dtype != np.uint16:
            raise ValueError("Frame.pixels must be uint16 counts")

    @property
    def height(self) -> int: return int(self.pixels.shape[0])

    @property
    def width(self) -> int: return int(self.pixels.shape[1])


@dataclass(frozen=True)
class ImuSample:
    gyro_rps: tuple[float, float, float]     # body rates (rad/s) — de-rotation input
    accel_mps2: tuple[float, float, float]
    provenance: Provenance                   # t_capture_ns MUST share the frame's clock domain


class OperatorButton(str, Enum):
    NONE = "none"
    ENROLL = "enroll"          # LOBL: memorise the designated target (silhouette/thermal signature)
    COMMIT = "commit"          # the second, deliberate press → engage authorisation
    RESELECT = "reselect"      # reject current lock, re-designate
    ABORT = "abort"            # mushroom → safe


@dataclass(frozen=True)
class OperatorCommand:
    """The human in the loop. Authority is proven by a signed token, never by a bare bool."""
    button: OperatorButton
    auth_token: Optional[bytes]      # signed dual-operator commit; None until a valid two-press exists
    t_ns: int


# ── internal contracts ────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Blob:
    centroid_px: tuple[float, float]     # (x, y)
    area_px: int
    snr: float
    bbox: tuple[int, int, int, int]      # (x, y, w, h)


@dataclass(frozen=True)
class Detections:
    blobs: tuple[Blob, ...]
    provenance: Provenance


@dataclass(frozen=True)
class Track:
    """De-rotated line of sight to the tracked target. Range/t_go are Optional — None when unobservable."""
    locked: bool
    az_rad: float
    el_rad: float
    los_rate_az: float                   # ego-compensated LOS rate (rad/s)
    los_rate_el: float
    range_m: Optional[float]             # None unless a real observable (subtense/ToF) provides it
    t_go_s: Optional[float]
    quality: float                       # 0..1 lock confidence
    provenance: Provenance

    def __post_init__(self) -> None:
        if not (0.0 <= self.quality <= 1.0):
            raise ValueError("Track.quality must be in [0,1]")
        if self.range_m is not None and self.range_m < 0:
            raise ValueError("range_m must be >= 0 or None")


@dataclass(frozen=True)
class GimbalState:
    """Output of the gimbal stage: 2 servo setpoints + the clean inertial LOS rate (head gyro)."""
    pan_setpoint_rad: float        # pan (yaw) servo setpoint, relative to the base
    tilt_setpoint_rad: float       # tilt (pitch) servo setpoint
    los_rate_yaw: float            # inertial LOS rate from the head gyro (clean; feeds guidance)
    los_rate_pitch: float
    tracking: bool                 # a target centroid was available this tick
    provenance: Provenance


@dataclass(frozen=True)
class GuidanceCommand:
    """Commanded lateral acceleration (seeker-head frame) + ROE. NOT an actuator command yet."""
    a_cmd_az: float                      # rad/s^2 (or m/s^2 lateral, per config) — steering demand
    a_cmd_el: float
    roe_abort: bool                      # guidance raised a rules-of-engagement abort this tick
    engage_permit: bool                  # guidance-side permit (NOT the human authority)
    required_g: float
    provenance: Provenance


@dataclass(frozen=True)
class Authority:
    """The safety verdict. `committed` is true ONLY on a verified two-press; default-deny everywhere else."""
    armed: bool
    committed: bool
    kill: bool
    reason: str


# ── output: the actuator command bus ───────────────────────────────────────────────────────────────
class ActuatorChannel(str, Enum):
    AIRFRAME_PITCH = "airframe_pitch"
    AIRFRAME_YAW = "airframe_yaw"
    AIRFRAME_ROLL = "airframe_roll"
    AIRFRAME_THROTTLE = "airframe_throttle"
    GIMBAL_AZ = "gimbal_az"
    GIMBAL_EL = "gimbal_el"
    AUX = "aux"


@dataclass(frozen=True)
class ActuatorCommand:
    channel: ActuatorChannel
    value: float                         # normalised [-1,1] for surfaces, [0,1] for throttle, rad for gimbal
    t_ns: int


@dataclass(frozen=True)
class ActuatorFrame:
    """Everything the core emits per tick to the outside world, gated by Authority."""
    commands: tuple[ActuatorCommand, ...]
    authority: Authority
    provenance: Provenance

    def by_channel(self, ch: ActuatorChannel) -> Optional[ActuatorCommand]:
        for c in self.commands:
            if c.channel == ch:
                return c
        return None


@dataclass(frozen=True)
class SeekerOutput:
    """The full per-tick core output (telemetry + the actuator frame)."""
    track: Track
    guidance: GuidanceCommand
    authority: Authority
    actuators: ActuatorFrame
    gimbal: Optional[GimbalState] = None
    schema_version: str = SCHEMA_VERSION
