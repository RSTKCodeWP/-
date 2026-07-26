"""Export YOLO weights to ONNX for the CPU detector backend (Task 2.4).

Mirror of `export_coreml.py` for the ONNX path. The produced `.onnx` is the
deterministic CPU backend's real-weights artifact — gitignored like the `.mlpackage`,
written to `models/yolo11s_<res>.onnx`. CI does NOT run this (it needs the torch stack
in the `bench` group); CI exercises the ONNX *decode seam* against a tiny synthetic
graph instead (tests/detect/test_onnx_detector.py). Run manually for the gated
real-weights test:

    uv run --group bench hades-export-onnx [--res 640 960 1280] [--out models]
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

DEFAULT_RESOLUTIONS: tuple[int, ...] = (640,)
DEFAULT_WEIGHTS = "yolo11s.pt"
DEFAULT_OUT_DIR = "models"


def artifact_path(out_dir: str | Path, resolution: int) -> Path:
    """Canonical `.onnx` path for a resolution — kept in lockstep with the loader."""
    return Path(out_dir) / f"yolo11s_{resolution}.onnx"


def export_one(
    resolution: int,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    weights: str = DEFAULT_WEIGHTS,
    assert_person: bool = False,
) -> Path:
    """Export `weights` to ONNX at `resolution` (square). `nms=False` to match the
    Core ML export so the SAME `decode_yolo` consumes both outputs (1, 84, 8400).

    `assert_person=True` (P2.5) requires single-class person@0; defaults False so the
    stock-COCO export path is unchanged.
    """
    if resolution <= 0 or resolution % 32 != 0:
        raise ValueError(f"resolution must be a positive multiple of 32, got {resolution}")

    from ultralytics import YOLO

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    model = YOLO(weights)
    if assert_person:
        from .class_assert import assert_single_person_class

        assert_single_person_class(dict(model.names))
    produced = Path(model.export(format="onnx", imgsz=resolution, half=False, nms=False))

    dest = artifact_path(out, resolution)
    dest.unlink(missing_ok=True)
    produced.replace(dest)
    return dest


def export_sweep(
    resolutions: Sequence[int] = DEFAULT_RESOLUTIONS,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    weights: str = DEFAULT_WEIGHTS,
    assert_person: bool = False,
) -> list[Path]:
    return [
        export_one(r, out_dir, weights=weights, assert_person=assert_person)
        for r in resolutions
    ]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hades-export-onnx",
        description="Export YOLO11s to ONNX (CPU detector backend, Task 2.4).",
    )
    parser.add_argument("--res", type=int, nargs="+", default=list(DEFAULT_RESOLUTIONS))
    parser.add_argument("--out", default=DEFAULT_OUT_DIR)
    parser.add_argument("--weights", default=DEFAULT_WEIGHTS)
    parser.add_argument(
        "--assert-person",
        action="store_true",
        help="require single-class person@0 (P2.5 fine-tuned export)",
    )
    args = parser.parse_args(argv)

    for p in export_sweep(
        args.res, args.out, weights=args.weights, assert_person=args.assert_person
    ):
        print(f"exported {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
