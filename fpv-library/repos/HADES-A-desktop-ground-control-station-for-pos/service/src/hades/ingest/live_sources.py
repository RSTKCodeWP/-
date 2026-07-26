"""Live source stubs — the hardware path, built in v1.x (Task 1.6).

These exist now so the interface seam is real: the live capture/telemetry path
plugs in behind the SAME `FrameSource` / `TelemetrySource` interfaces the replay
impls use, with no change to consumers. They raise `NotImplementedError` until the
hardware path is built (live UVC capture and CRSF serial both require a connected
drone, per CLAUDE.md — v1 is recorded/synthetic only).

- `UvcFrameSource`: live USB UVC capture (O4 -> goggles -> HDMI -> capture card).
- `CrsfSerialSource`: live CRSF telemetry off the ELRS radio's USB-C serial port.
"""

from __future__ import annotations

from collections.abc import Iterator

from hades.ingest.frame_source import Frame, FrameSource
from hades.ingest.telemetry_source import Pose, TelemetrySource

_LIVE_MSG = "live path built with hardware (v1.x)"


class UvcFrameSource(FrameSource):
    """Live USB UVC video capture. Stubbed in v1."""

    def __init__(self, device: int = 0):
        self.device = device

    def __iter__(self) -> Iterator[Frame]:
        raise NotImplementedError(_LIVE_MSG)


class CrsfSerialSource(TelemetrySource):
    """Live CRSF telemetry over the ELRS radio's USB-C serial port. Stubbed in v1."""

    def __init__(self, port: str, baud: int = 420_000):
        self.port = port
        self.baud = baud

    def __iter__(self) -> Iterator[Pose]:
        raise NotImplementedError(_LIVE_MSG)
