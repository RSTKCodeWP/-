"""Y16 data COLLECTION — the lossless raw-thermal capture + provenance + coverage path.

The bench's MP4 recorder is the WRONG format for keeping real thermal: it 8-bit-encodes the stream and
DESTROYS the radiometric Y16.  This module is the right path: it records RAW uint16 frames LOSSLESSLY into a
labelled clip with full provenance, and tracks coverage -- so when the real Y16 sensor is on the gun, the
operator just presses record and the clips are captured with no transcoding loss.  This is real-data
recording infrastructure (used by ``real_ingest`` / the bench), NOT a classifier: the learned drone-vs-not
model and its dataset were removed (2026-07-11); the machine never classifies target TYPE.

An HONEST flag ``is_radiometric_y16`` gates what COUNTS: only real radiometric Y16 advances field-readiness;
an 8-bit AGC transcode (the current CVBS camera) is recorded but does NOT count toward the clip budget.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

import numpy as np

# Minimum radiometric-Y16 drone sorties for a meaningful real-data coverage sample. (Was shared with the
# removed classifier evaluator; kept here as the recorder's own field-readiness coverage threshold.)
_MIN_POS_CLIPS_FOR_CI = 8


@dataclass
class ClipManifest:
    """Provenance for one recorded clip -- everything a split / audit / coverage check needs."""

    class_label: str                       # DRONE | BIRD | HELICOPTER | AIRPLANE | BALLOON | CLUTTER ...
    sortie_id: str                         # distinct capture session (splits are per-sortie, no leakage)
    sensor: str = "unknown"                # e.g. "FT640_CVBS_8bit" | "Y16_radiometric_<model>"
    is_radiometric_y16: bool = False       # HONEST: True ONLY for real radiometric Y16 (not an 8-bit transcode)
    range_hint_m: Optional[float] = None   # coarse range bucket for diversity coverage
    aspect_deg: Optional[float] = None     # head-on(0)..broadside(90) for aspect coverage
    conditions: str = ""                   # e.g. "night/sky", "day/ground"
    notes: str = ""
    n_frames: int = 0
    width: int = 0
    height: int = 0


class Y16ClipRecorder:
    """Record RAW uint16 frames losslessly into ``<dir>/IR_<CLASS>_<sortie>.npz`` + a JSON manifest sidecar.

    Usage:
        rec = Y16ClipRecorder("dataset", "DRONE", "sortie_2026_07_07_a", sensor="Y16_radiometric_x",
                              is_radiometric_y16=True, range_hint_m=180, aspect_deg=10, conditions="day/sky")
        for f in frames_u16: rec.add(f)
        path = rec.close()
    """

    def __init__(self, out_dir: str, class_label: str, sortie_id: str, **meta) -> None:
        self._dir = out_dir
        self._frames: list[np.ndarray] = []
        self._man = ClipManifest(class_label=str(class_label).upper(), sortie_id=str(sortie_id), **meta)

    def add(self, frame_u16: np.ndarray) -> None:
        f = np.asarray(frame_u16)
        if f.dtype != np.uint16:
            raise ValueError(f"Y16 recorder needs uint16 frames (lossless), got {f.dtype}")
        if self._frames and f.shape != self._frames[0].shape:
            raise ValueError(f"frame shape {f.shape} != clip shape {self._frames[0].shape}")
        self._frames.append(f.copy())

    def close(self) -> str:
        if not self._frames:
            raise ValueError("no frames recorded")
        os.makedirs(self._dir, exist_ok=True)
        stack = np.stack(self._frames).astype(np.uint16)     # (N, H, W)
        self._man.n_frames = int(stack.shape[0])
        self._man.height = int(stack.shape[1])
        self._man.width = int(stack.shape[2])
        base = f"IR_{self._man.class_label}_{self._man.sortie_id}"
        npz = os.path.join(self._dir, base + ".npz")
        np.savez_compressed(npz, frames=stack)               # lossless uint16
        with open(os.path.join(self._dir, base + ".json"), "w", encoding="utf-8") as fh:
            json.dump(asdict(self._man), fh, indent=2, ensure_ascii=False)
        return npz


def load_y16_clip(npz_path: str) -> tuple[np.ndarray, ClipManifest]:
    """Load a recorded clip back: (frames_u16 [N,H,W], manifest).  Frames are bit-identical to capture."""
    frames = np.load(npz_path)["frames"]
    man_path = npz_path[:-4] + ".json" if npz_path.endswith(".npz") else npz_path + ".json"
    man = ClipManifest(class_label="UNKNOWN", sortie_id="?")
    if os.path.isfile(man_path):
        with open(man_path, encoding="utf-8") as fh:
            man = ClipManifest(**json.load(fh))
    return frames, man


def _iter_manifests(dataset_dir: str):
    if not os.path.isdir(dataset_dir):
        return
    for name in sorted(os.listdir(dataset_dir)):
        if name.endswith(".json"):
            try:
                with open(os.path.join(dataset_dir, name), encoding="utf-8") as fh:
                    yield ClipManifest(**json.load(fh))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue


@dataclass
class CoverageReport:
    clips_per_class: dict
    n_radiometric_y16_drone: int          # drone clips that COUNT (real Y16, not transcodes)
    n_sorties_drone: int                  # distinct drone sorties (splits are per-sortie)
    range_buckets: set = field(default_factory=set)
    aspect_buckets: set = field(default_factory=set)
    conditions: set = field(default_factory=set)
    gaps: list = field(default_factory=list)
    data_field_ready: bool = False
    summary: str = ""


def coverage_report(dataset_dir: str) -> CoverageReport:
    """Track collected raw-thermal data against the field-readiness coverage spec.

    Only RADIOMETRIC Y16 clips from DISTINCT sorties count toward the clip budget; diversity of
    range/aspect/conditions and confuser coverage are checked and any gaps are named.
    """
    per: dict = {}
    y16_drone_sorties, ranges, aspects, conds = set(), set(), set(), set()
    confusers = set()
    for m in _iter_manifests(dataset_dir):
        per[m.class_label] = per.get(m.class_label, 0) + 1
        if m.class_label == "DRONE" and m.is_radiometric_y16:
            y16_drone_sorties.add(m.sortie_id)
            if m.range_hint_m is not None:
                ranges.add(int(m.range_hint_m // 50) * 50)         # 50 m buckets
            if m.aspect_deg is not None:
                aspects.add(int(m.aspect_deg // 30) * 30)          # 30 deg buckets
            if m.conditions:
                conds.add(m.conditions)
        elif m.class_label != "DRONE" and m.is_radiometric_y16:
            confusers.add(m.class_label)

    n_y16_drone = len(y16_drone_sorties)
    gaps = []
    if n_y16_drone < _MIN_POS_CLIPS_FOR_CI:
        gaps.append(f"need {_MIN_POS_CLIPS_FOR_CI - n_y16_drone} more radiometric-Y16 drone sortie(s) "
                    f"(have {n_y16_drone}/{_MIN_POS_CLIPS_FOR_CI})")
    if len(ranges) < 2:
        gaps.append("need drone clips across >=2 range buckets (acquisition..terminal)")
    if len(aspects) < 2:
        gaps.append("need drone clips across >=2 aspect buckets (head-on..broadside)")
    for need in ("BIRD", "AIRPLANE", "HELICOPTER"):
        if need not in confusers:
            gaps.append(f"need radiometric-Y16 confuser clips: {need}")
    ready = not gaps
    summary = ("DATA FIELD-READY: coverage meets the spec." if ready
               else f"DATA NOT ready ({len(gaps)} gap(s)): " + "; ".join(gaps))
    return CoverageReport(per, n_y16_drone, n_y16_drone, ranges, aspects, conds, gaps, ready, summary)
