"""TelemetrySource interface and the `Pose` value object.

`TelemetrySource` is an iterable of `Pose`s — the drone's position/attitude over
time, time-synced to frames by `seq` (the frame_id) downstream (Task 1.5). It
knows nothing about pixels or detection (DESIGN.md §1).

`Pose` is the cross-process pose contract the georeference geometry consumes. It
is deliberately honest about what a given source can supply:

- **Position** (`lat`, `lon`) is WGS84 degrees, **(lat, lon)** order (DESIGN.md §3.1),
  `None` when there is no GPS fix (`gps_valid` is then False — never silently 0,0).
- **Altitude** (`alt`, meters) carries an explicit `alt_datum` string tag
  (`HAE` | `MSL` | `REL_TAKEOFF` | `UNKNOWN`, DESIGN.md §3.1) set at the source
  boundary, so `ray_to_ground` can refuse to mix datums. `abs_alt` is kept as
  advisory metadata with an `abs_alt_valid` flag (the field is firmware-unreliable).
- **Attitude** (`roll`, `pitch`, `yaw`) is degrees or `None`. A source that cannot
  observe attitude (e.g. the DJI `.srt` replay path) leaves all three `None` — the
  geometry module (Task 3.4) refuses to build a rotation from a partial/None
  attitude rather than assuming level/north. `yaw` is true heading; GPS
  course-over-ground is NOT stuffed here (course ≠ heading — heading-limited).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class Pose:
    """One time-stamped drone pose. Attitude/GPS fields are `None` when unobserved."""

    t: float  # seconds from clip start (sync primitive)
    lat: float | None  # WGS84 degrees, None if no GPS fix
    lon: float | None  # WGS84 degrees, None if no GPS fix
    alt: float | None  # meters, in the frame named by alt_datum
    alt_datum: str  # "HAE" | "MSL" | "REL_TAKEOFF" | "UNKNOWN"
    roll: float | None = None  # degrees, None if unobserved
    pitch: float | None = None  # degrees, None if unobserved
    yaw: float | None = None  # degrees true heading, None if unobserved
    seq: int | None = None  # frame_id this pose aligns to (FrameCnt - 1)
    gps_valid: bool = True  # False when lat/lon absent or out of range
    abs_alt: float | None = None  # advisory absolute altitude (untrusted)
    abs_alt_valid: bool = True  # False when abs_alt is implausible


class TelemetrySource(ABC):
    """Yields `Pose`s. Impls: SrtFileSource (replay), CrsfSerialSource (live, stubbed)."""

    @abstractmethod
    def __iter__(self) -> Iterator[Pose]:
        raise NotImplementedError
