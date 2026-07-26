r"""SrtFileSource — parse a DJI O4 `.srt` telemetry sidecar into `Pose`s.

The high-rate validation replay path. Each SubRip block is one video frame
(`FrameCnt`), carrying lat/lon/rel_alt/abs_alt but **no attitude** (DESIGN.md §3.5).
Parser policy (hardened against real DJI variation):

- Tolerant `[key: value]` token extraction (`\s*` around the colon), so field-order
  and modern/legacy spacing variation is absorbed; the combined
  `[rel_alt: X abs_alt: Y]` two-keys-one-bracket form is handled.
- `alt` is sourced from the trustworthy `rel_alt`, tagged `REL_TAKEOFF`. `abs_alt`
  is parsed as advisory metadata and flagged `abs_alt_valid=False` when implausible
  (the field glitches on O-series firmware).
- A block with no GPS fix yields a ``Pose`` flagged ``gps_valid=False`` (lat/lon ``None``) —
  never dropped (would shift frame alignment) and never plotted as 0,0.
- ``seq = FrameCnt - 1`` makes the 1-based -> 0-based conversion explicit (aligns to
  ``Frame.seq``).
- An empty/zero-telemetry sidecar raises — running the validation path blind is unsafe.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from hades.ingest.telemetry_source import Pose, TelemetrySource

# A signed decimal, optionally in scientific notation.
_NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"
# Plausible absolute-altitude envelope (meters); outside -> abs_alt flagged invalid.
# The floor is just-below-sea-level: a negative abs_alt is the documented DJI FPV
# firmware glitch signature (nonzero-ground / 1/10-scaling bugs), not a real altitude
# over coastal SAR terrain. The fixture plants -32.309 to exercise this path.
_ABS_ALT_MIN, _ABS_ALT_MAX = -5.0, 10_000.0


def _find(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


def _to_float(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    # NaN/inf must never reach the georeference math.
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


class SrtFileSource(TelemetrySource):
    """Replays a DJI O4 `.srt` sidecar as `Pose` samples."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def __iter__(self) -> Iterator[Pose]:
        text = self.path.read_text(encoding="utf-8-sig", errors="replace")
        # Split into blocks on blank-line boundaries (tolerate \r and irregular gaps).
        blocks = [b for b in re.split(r"\r?\n\s*\r?\n", text) if b.strip()]
        if not blocks:
            raise ValueError(f"empty telemetry sidecar: {self.path}")
        poses = [p for p in (self._parse_block(b) for b in blocks) if p is not None]
        if not poses:
            # Non-empty file but no parseable telemetry block (corrupt/truncated):
            # raise rather than silently look like missing telemetry, so the
            # validation path never runs blind on a bad sidecar.
            raise ValueError(f"no parseable telemetry in sidecar: {self.path}")
        yield from poses

    def _parse_block(self, block: str) -> Pose | None:
        # Timecode start (HH:MM:SS,mmm) -> seconds; the sync primitive.
        tc = re.search(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->", block)
        if tc is None:
            return None  # not a telemetry block (e.g. a truncated tail)
        h, m, s, ms = (int(g) for g in tc.groups())
        t = h * 3600 + m * 60 + s + ms / 1000.0

        frame_cnt = _find(r"FrameCnt:\s*(\d+)", block)
        seq = int(frame_cnt) - 1 if frame_cnt is not None else None

        # GPS — accept the legacy "longtitude" misspelling; preserve sign.
        lat = _to_float(_find(rf"\[\s*latitude\s*:\s*({_NUM})", block))
        lon = _to_float(_find(rf"\[\s*longt?itude\s*:\s*({_NUM})", block))
        gps_valid = self._gps_ok(lat, lon)
        if not gps_valid:
            lat = lon = None

        # Altitude — rel_alt is trustworthy (REL_TAKEOFF); abs_alt is advisory.
        rel_alt = _to_float(_find(rf"\[\s*rel_alt\s*:\s*({_NUM})", block))
        # Require a bracket/whitespace boundary before abs_alt so a vendor token
        # like [gb_abs_alt: ...] can't be grabbed instead of the real value.
        abs_alt = _to_float(_find(rf"[\[\s]abs_alt\s*:\s*({_NUM})", block))
        if rel_alt is None:  # legacy single-value [altitude: Z] fallback
            rel_alt = _to_float(_find(rf"\[\s*altitude\s*:\s*({_NUM})", block))
        abs_alt_valid = abs_alt is not None and _ABS_ALT_MIN <= abs_alt <= _ABS_ALT_MAX

        return Pose(
            t=t,
            lat=lat,
            lon=lon,
            alt=rel_alt,
            alt_datum="REL_TAKEOFF",
            seq=seq,
            gps_valid=gps_valid,
            abs_alt=abs_alt,
            abs_alt_valid=abs_alt_valid,
        )

    @staticmethod
    def _gps_ok(lat: float | None, lon: float | None) -> bool:
        if lat is None or lon is None:
            return False
        if lat == 0.0 and lon == 0.0:
            return False  # 0,0 is the no-fix sentinel, not a coordinate
        # TODO(2026-07-01, DESIGN.md §3.5): tighten the near-null-island guard
        # against real DJI cold-start samples (tiny non-zero noise near 0,0).
        return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0
