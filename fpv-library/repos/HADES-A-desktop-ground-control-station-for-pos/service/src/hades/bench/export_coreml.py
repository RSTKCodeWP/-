"""Export stock YOLO11s to CoreML `.mlpackage` at a sweep of input resolutions.

Phase 1.5 Task 1.5.1. Produces the artifacts the latency benchmark loads. Exports
are **stock** `yolo11s` (COCO weights) — this phase measures *latency only*; the
fine-tuned model and the final resolution pick (latency × recall) come in P2.5
(per implementation-plan review note F5).

Export settings are fixed by CLAUDE.md / DESIGN.md:
  - FP16 (half precision)
  - ComputeUnits.all (let CoreML place ops on ANE/GPU/CPU)
  - one `person`-relevant COCO model; single class filtering happens at inference

Artifacts are written to a gitignored `models/` directory (DESIGN.md §4) named by
resolution, e.g. `models/yolo11s_coreml_640.mlpackage`. The weights download
(`yolo11s.pt`, ~19 MB) is a one-time dev-tooling fetch — it is NOT the runtime
on-device loop the offline constraint governs.

Run:  uv run --group bench hades-export-coreml [--res 640 960 1280] [--out models]
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

# The three candidate resolutions from CLAUDE.md ("a latency spike at {640,960,1280}").
DEFAULT_RESOLUTIONS: tuple[int, ...] = (640, 960, 1280)
DEFAULT_WEIGHTS = "yolo11s.pt"
DEFAULT_OUT_DIR = "models"


def artifact_path(out_dir: str | Path, resolution: int) -> Path:
    """Canonical `.mlpackage` path for a given resolution. The benchmark loads the
    same function, so export and benchmark never disagree on the filename."""
    return Path(out_dir) / f"yolo11s_coreml_{resolution}.mlpackage"


def export_one(
    resolution: int,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    weights: str = DEFAULT_WEIGHTS,
    assert_person: bool = False,
) -> Path:
    """Export `weights` to a CoreML `.mlpackage` at `resolution` (square input).

    Returns the path to the produced `.mlpackage`. Ultralytics writes the export
    next to the weights by default; we move it to the canonical `artifact_path` so
    the benchmark can find it by resolution alone.

    `assert_person=True` (P2.5 fine-tuned export) requires the model to be single-class with
    `person` at index 0 — the `decode_yolo` PERSON_CLASS_INDEX=0 contract. It defaults False
    so the P1.5 stock-COCO (80-class) latency export still works unchanged.
    """
    if resolution <= 0 or resolution % 32 != 0:
        # YOLO requires the input side to be a multiple of the max stride (32).
        raise ValueError(f"resolution must be a positive multiple of 32, got {resolution}")

    # Lazy import: keeps this module importable (and unit-testable) without the
    # heavy `bench` deps installed.
    from ultralytics import YOLO

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    model = YOLO(weights)
    if assert_person:
        from .class_assert import assert_single_person_class

        assert_single_person_class(dict(model.names))
    # half=True -> FP16; ultralytics maps CoreML export to ComputeUnits.all by default.
    produced = model.export(format="coreml", imgsz=resolution, half=True, nms=False)
    produced_path = Path(produced)

    dest = artifact_path(out, resolution)
    if dest.exists():
        _rmtree(dest)
    produced_path.replace(dest)
    return dest


def export_sweep(
    resolutions: Sequence[int] = DEFAULT_RESOLUTIONS,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    weights: str = DEFAULT_WEIGHTS,
    assert_person: bool = False,
) -> list[Path]:
    """Export each resolution in turn. Returns the produced artifact paths."""
    return [
        export_one(r, out_dir, weights=weights, assert_person=assert_person)
        for r in resolutions
    ]


def _rmtree(path: Path) -> None:
    """`.mlpackage` is a directory; remove it before re-exporting."""
    import shutil

    shutil.rmtree(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hades-export-coreml",
        description="Export stock YOLO11s to CoreML at a resolution sweep (Phase 1.5 spike).",
    )
    parser.add_argument(
        "--res",
        type=int,
        nargs="+",
        default=list(DEFAULT_RESOLUTIONS),
        help="input resolutions to export (default: 640 960 1280)",
    )
    parser.add_argument(
        "--out", default=DEFAULT_OUT_DIR, help="output dir for .mlpackage artifacts"
    )
    parser.add_argument(
        "--weights", default=DEFAULT_WEIGHTS, help="source weights (default: yolo11s.pt)"
    )
    parser.add_argument(
        "--assert-person",
        action="store_true",
        help="require the model to be single-class person@0 (P2.5 fine-tuned export)",
    )
    args = parser.parse_args(argv)

    paths = export_sweep(
        args.res, args.out, weights=args.weights, assert_person=args.assert_person
    )
    for p in paths:
        print(f"exported {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
