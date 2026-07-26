"""Golden-vector generator for the PL detect front-end (M0 verification backbone).

WHAT THIS IS
------------
The FPGA port re-implements the S1 detect front-end (top-hat -> adaptive threshold ->
connected components -> intensity-weighted centroid) in the PL fabric.  To verify that RTL/HLS
against the trusted Python, we need a frozen, deterministic set of

    (input frame)  ->  (expected detect output)  +  (physical ground truth)

triples.  This module produces exactly that.  A Vitis HLS C testbench streams the ``.bin`` frames
through the synthesised detect IP and compares its output against ``expected`` in the manifest;
``ground_truth`` is the separate physical reference (where the target actually is) that both the
Python and the IP must track to within the S1 centroid budget.

The Python ``detect_frame`` is FLOAT.  The FPGA IP will be FIXED-POINT, so it will NOT be
bit-identical -- the contract is a TOLERANCE (centroid error vs ground truth), and the quantisation
budget is what the fixed-point design must fit under.  ``expected`` (the float detector's own
output) is the tighter self-consistency reference; ``ground_truth`` is the physical one.

SCENES
------
Two representative regimes, both deterministic (fixed seed):
  * ``s1_14bit_nominal``  -- the native S1 sim (14-bit, 640x512).  Grades the ALGORITHM.
  * ``ft640_cvbs_8bit``   -- an 8-bit, ~720x480 scene approximating the FT640LM CVBS reality
                             (analog CVBS -> decoder -> de-interlace -> 8-bit Y into detect).
                             The exact post-decoder grid (720x480 weave vs 720x240 bob) is pinned
                             by open-question #1 in the migration doc; update ``width/height`` and
                             the 8-bit levels here once the real decoder output is measured.

Run as a script to dump vectors for the HLS testbench::

    PYTHONPATH=fpv python3 -m fpga.ref_model.golden_vectors --out /tmp/golden --frames 120
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import numpy.typing as npt

from fpv.seeker.detect import ThresholdState, detect_frame
from fpv.seeker.thermal_sim import ThermalSceneConfig, ThermalSimulator


@dataclass(frozen=True)
class GoldenScene:
    """One deterministic scene + the detector settings used to grade it."""

    name: str
    cfg: ThermalSceneConfig
    n_frames: int = 120
    min_snr: float = 2.0
    min_area_px: int = 2
    # Centroid-tolerance contract (px): on READY, target-visible frames the detector's best-blob
    # centroid must track the ground-truth centroid to within this RMSE.  This is the number the
    # fixed-point PL IP must also meet.  s1 gate (a) is <0.10 px on the clean 14-bit sim.
    centroid_rmse_gate_px: float = 0.10
    note: str = ""


# --- 14-bit native S1 sim: the algorithm reference -------------------------------------------
_S1_14BIT = ThermalSceneConfig(
    width=640, height=512, seed=42,
    # defaults model a ~1800-count target on a 4096 sky at 14-bit -- a clean, high-SNR reference.
)

# --- 8-bit FT640LM/CVBS-representative scene (post-decoder, post-deinterlace input to detect) --
# NOTE: 8-bit AGC dynamic range (0..255), NOT radiometric.  Levels chosen so the scene SNR is
# realistic-but-detectable; grid ~720x480 reflects SD CVBS active area (see migration doc §1/§7).
_FT640_CVBS_8BIT = ThermalSceneConfig(
    width=720, height=480, seed=7,
    sky_base_counts=40, sky_gradient_amplitude=15.0, read_noise_sigma=2.0,
    target_peak_above_bg=110.0, target_sigma_px=1.6,
    n_stars=12, star_peak_fraction=0.55,
    ffc_freeze_interval=90, ffc_freeze_frames=30,
    cam_temp_drift_rate_cts_per_frame=0.05, cam_temp_gain_drift_rate=2e-5,
)

GOLDEN_SCENES: tuple[GoldenScene, ...] = (
    GoldenScene(
        name="s1_14bit_nominal", cfg=_S1_14BIT, n_frames=120,
        centroid_rmse_gate_px=0.10,
        note="Native S1 sim (14-bit, 640x512). Grades the detect ALGORITHM (S1 gate a).",
    ),
    GoldenScene(
        name="ft640_cvbs_8bit", cfg=_FT640_CVBS_8BIT, n_frames=120,
        # 8-bit AGC + SD grid is a coarser, noisier regime -> looser (still sub-pixel) budget.
        centroid_rmse_gate_px=0.35,
        note="FT640LM CVBS-representative (8-bit AGC, ~720x480). Update grid/levels once the "
             "real ADV7280/TVP5150 decoder output is measured (migration doc open-Q #1).",
    ),
)


@dataclass(frozen=True)
class FrameRecord:
    """Per-frame golden record: detector output (``expected``) + physical ``ground_truth``."""

    frame_id: int
    cam_temp_c: float
    ffc_state: str
    # detector output (the float reference the PL IP is compared against)
    n_blobs: int
    threshold_counts: float
    best_centroid_px: Optional[tuple[float, float]]
    best_area_px: Optional[int]
    best_snr: Optional[float]
    # physical ground truth
    gt_centroid_px: tuple[float, float]
    gt_area_px: float
    gt_visible: bool

    def to_manifest(self) -> dict:
        return {
            "frame_id": self.frame_id,
            "cam_temp_c": round(self.cam_temp_c, 4),
            "ffc_state": self.ffc_state,
            "expected": {
                "n_blobs": self.n_blobs,
                "threshold_counts": round(self.threshold_counts, 4),
                "best_centroid_px": (None if self.best_centroid_px is None
                                     else [round(self.best_centroid_px[0], 6),
                                           round(self.best_centroid_px[1], 6)]),
                "best_area_px": self.best_area_px,
                "best_snr": (None if self.best_snr is None else round(self.best_snr, 4)),
            },
            "ground_truth": {
                "target_centroid_px": [round(self.gt_centroid_px[0], 6),
                                       round(self.gt_centroid_px[1], 6)],
                "target_area_px": round(self.gt_area_px, 4),
                "is_target_visible": self.gt_visible,
            },
        }


def generate_scene(
    scene: GoldenScene,
) -> tuple[list[FrameRecord], list[npt.NDArray[np.uint16]]]:
    """Replay ``detect_frame`` across the scene.  Returns (records, raw uint16 frames).

    Deterministic: same scene -> byte-identical frames and identical records (fixed seed, no
    global RNG, no hash()-salted state).  That determinism is what makes this a regression gate.
    """
    sim = ThermalSimulator(scene.cfg)
    frames = sim.generate(scene.n_frames)

    ts = ThresholdState()
    records: list[FrameRecord] = []
    raw_frames: list[npt.NDArray[np.uint16]] = []

    for frame_u16, gt in frames:
        blobs, ts = detect_frame(
            frame_u16,
            cam_temp_c=gt.cam_temp_c,
            ffc_state=gt.ffc_state,
            threshold_state=ts,
            frame_id=gt.frame_id,
            min_snr=scene.min_snr,
            min_area_px=scene.min_area_px,
        )
        best = blobs[0] if blobs else None
        records.append(FrameRecord(
            frame_id=gt.frame_id,
            cam_temp_c=gt.cam_temp_c,
            ffc_state=gt.ffc_state,
            n_blobs=len(blobs),
            threshold_counts=float(ts.threshold_counts),
            best_centroid_px=(None if best is None else
                              (float(best.centroid_px[0]), float(best.centroid_px[1]))),
            best_area_px=(None if best is None else int(best.area_px)),
            best_snr=(None if best is None else float(best.snr)),
            gt_centroid_px=(float(gt.target_centroid_px[0]), float(gt.target_centroid_px[1])),
            gt_area_px=float(gt.target_area_px),
            gt_visible=bool(gt.is_target_visible),
        ))
        raw_frames.append(np.ascontiguousarray(frame_u16, dtype=np.uint16))

    return records, raw_frames


def write_vectors(scene: GoldenScene, out_dir: str | Path) -> Path:
    """Dump ``<out_dir>/<scene>/`` with raw ``frame_XXXX.bin`` (LE uint16) + ``manifest.json``.

    This is the on-disk contract the Vitis HLS / RTL testbench reads.
    """
    records, frames = generate_scene(scene)
    scene_dir = Path(out_dir) / scene.name
    scene_dir.mkdir(parents=True, exist_ok=True)

    frame_entries = []
    for rec, frame in zip(records, frames):
        fname = f"frame_{rec.frame_id:04d}.bin"
        # little-endian uint16, row-major (H, W) -- the byte order the RX/AXI-Stream will present.
        frame.astype("<u2").tofile(scene_dir / fname)
        entry = rec.to_manifest()
        entry["file"] = fname
        frame_entries.append(entry)

    manifest = {
        "scene": scene.name,
        "note": scene.note,
        "width": scene.cfg.width,
        "height": scene.cfg.height,
        "dtype": "uint16_le",
        "layout": "row_major_HxW",
        "n_frames": len(records),
        "detect": {"min_snr": scene.min_snr, "min_area_px": scene.min_area_px},
        "centroid_rmse_gate_px": scene.centroid_rmse_gate_px,
        "frames": frame_entries,
    }
    (scene_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return scene_dir


def _main() -> None:
    ap = argparse.ArgumentParser(description="Dump Block-03 detect golden vectors for HLS/RTL cosim")
    ap.add_argument("--out", default="/tmp/golden", help="output directory")
    ap.add_argument("--frames", type=int, default=None, help="override n_frames for every scene")
    ap.add_argument("--scene", default=None, help="only this scene name (default: all)")
    args = ap.parse_args()

    scenes = GOLDEN_SCENES
    if args.scene:
        scenes = tuple(s for s in scenes if s.name == args.scene)
        if not scenes:
            raise SystemExit(f"unknown scene {args.scene!r}; have "
                             f"{[s.name for s in GOLDEN_SCENES]}")
    for s in scenes:
        if args.frames is not None:
            s = GoldenScene(name=s.name, cfg=s.cfg, n_frames=args.frames, min_snr=s.min_snr,
                            min_area_px=s.min_area_px,
                            centroid_rmse_gate_px=s.centroid_rmse_gate_px, note=s.note)
        d = write_vectors(s, args.out)
        print(f"  wrote {s.n_frames:4d} frames -> {d}")


if __name__ == "__main__":
    _main()
