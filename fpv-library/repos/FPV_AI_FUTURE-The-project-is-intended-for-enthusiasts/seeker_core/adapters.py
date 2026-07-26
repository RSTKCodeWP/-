"""seeker_core adapters — the hardware boundary. The core talks to the world ONLY through these.

Inputs: `CameraSource`, `ImuSource`. Output: `ActuatorSink`. The "most preferable" camera / mount /
computer is a CHOICE OF ADAPTER, not something baked into the core. Reference stubs here are honest:
the sim camera is clearly synthetic; the sinks record/print without pretending to be flight hardware.
Real adapters (FT640-CVBS, ICM-42688-P over SPI, DShot/servo, gimbal driver, FC-MSP link) implement
the same Protocols and live behind the same boundary.
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

import numpy as np

from seeker_core.contracts import (
    ActuatorFrame,
    Frame,
    ImuSample,
    Provenance,
)


# ── input adapters ──────────────────────────────────────────────────────────────────────────────
@runtime_checkable
class CameraSource(Protocol):
    def read(self) -> Optional[Frame]: ...
    def close(self) -> None: ...


@runtime_checkable
class ImuSource(Protocol):
    def read(self, t_ns: int) -> Optional[ImuSample]: ...


# ── output adapter ──────────────────────────────────────────────────────────────────────────────
@runtime_checkable
class ActuatorSink(Protocol):
    def write(self, frame: ActuatorFrame) -> None: ...


# ── honest reference implementations (clearly synthetic / non-flight) ─────────────────────────────
class SimCameraSource:
    """A synthetic moving hot-target-on-cold-sky camera. `synthetic=True` on every frame it emits."""

    def __init__(self, width: int = 640, height: int = 512, fps: float = 60.0, seed: int = 0) -> None:
        self.w, self.h, self.fps = width, height, fps
        self._rng = np.random.default_rng(seed)
        self._n = 0

    def read(self) -> Optional[Frame]:
        yy, xx = np.mgrid[0:self.h, 0:self.w]
        base = 4096.0 + self._rng.normal(0.0, 12.0, (self.h, self.w))
        cx = self.w * 0.5 + 60.0 * np.sin(self._n / 20.0)     # a target that crosses
        cy = self.h * 0.4
        base += 1500.0 * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * 2.0 ** 2))
        px = np.clip(base, 0, 65535).astype(np.uint16)
        self._n += 1
        return Frame(px, radiometric=False,
                     provenance=Provenance("sim", t_capture_ns=int(self._n * 1e9 / self.fps),
                                           synthetic=True, note="SimCameraSource"))

    def close(self) -> None:
        pass


class RecordActuatorSink:
    """Records every emitted ActuatorFrame in memory (for tests / replay). Drives no hardware."""

    def __init__(self) -> None:
        self.frames: list[ActuatorFrame] = []

    def write(self, frame: ActuatorFrame) -> None:
        self.frames.append(frame)


class PrintActuatorSink:
    """Human-readable actuator stream — a safe default that touches no motors."""

    def write(self, frame: ActuatorFrame) -> None:
        cmds = ", ".join(f"{c.channel.value}={c.value:+.3f}" for c in frame.commands)
        print(f"[actuators armed={frame.authority.armed} committed={frame.authority.committed} "
              f"kill={frame.authority.kill}] {cmds}")
