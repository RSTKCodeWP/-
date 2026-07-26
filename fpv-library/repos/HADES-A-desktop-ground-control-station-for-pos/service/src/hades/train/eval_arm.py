"""Evaluate one trained arm's checkpoint on the held-out test set (Task 2.5.3/2.5.6).

The ablation's recall number must be the SAME metric for both arms — the project's
center-distance harness (`hades.eval`), NOT Ultralytics' IoU-based `model.val()` mAP (a
different matcher whose "winner" can disagree). This script:

1. Wraps a YOLO `.pt`/`.mlpackage`/`.onnx` in the `Detector` interface (`_UltralyticsDetector`).
2. Loads the merged test split (YOLO labels → `GroundTruth` in ORIGINAL-frame pixels).
3. Runs `evaluate()` at an explicit `conf_threshold` + `max_distance`, printing overall P/R
   and per-size/subclass recall — with the operating point recorded so the number is honest.

Run on the cluster after each arm, and on the Mac against the FP16 export for the shipped
acceptance number. `max_distance` is ORIGINAL-frame pixels (resolution-invariant — the
detector un-letterboxes before a box leaves it), held fixed across arms and resolutions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hades.detect.detector import Detection, Detector
from hades.eval.detection_metrics import GroundTruth
from hades.eval.report import LabeledFrame, evaluate, format_report


class _UltralyticsDetector(Detector):
    """Adapt a YOLO model to the `Detector` interface, in ORIGINAL-frame pixels.

    Ultralytics already un-letterboxes its `boxes.xyxy` back to the input image's pixel
    coordinates, so the boxes are directly comparable to the GT (which is also original
    pixels). Single-class person model → every detection is `person`.
    """

    def __init__(self, weights: str, *, conf: float, imgsz: int):
        from ultralytics import YOLO

        self._model = YOLO(weights)
        self._conf = conf
        self._imgsz = imgsz

    def detect(self, frame):
        # conf=0.001 here so evaluate() can apply the real threshold itself (one pass,
        # many operating points). verbose off to keep logs clean.
        res = self._model.predict(
            frame, conf=0.001, imgsz=self._imgsz, verbose=False
        )[0]
        dets: list[Detection] = []
        for b in res.boxes:
            x1, y1, x2, y2 = (float(v) for v in b.xyxy[0].tolist())
            if x2 <= x1 or y2 <= y1:
                continue
            dets.append(Detection(box_xyxy=(x1, y1, x2, y2), conf=float(b.conf[0]), cls="person"))
        return dets


def load_test_frames(test_dir: Path) -> list[LabeledFrame]:
    """Load a YOLO `images/`+`labels/` split into `LabeledFrame`s (GT in original pixels)."""
    import numpy as np
    from PIL import Image

    frames: list[LabeledFrame] = []
    for img_path in sorted((test_dir / "images").glob("*")):
        label_path = test_dir / "labels" / f"{img_path.stem}.txt"
        img = np.asarray(Image.open(img_path).convert("RGB"), dtype=np.uint8)
        h, w = img.shape[:2]
        gts: list[GroundTruth] = []
        if label_path.exists():
            for line in label_path.read_text().splitlines():
                parts = line.split()
                if len(parts) != 5:
                    continue
                _, cx, cy, bw, bh = (float(p) for p in parts)
                x1 = (cx - bw / 2) * w
                y1 = (cy - bh / 2) * h
                x2 = (cx + bw / 2) * w
                y2 = (cy + bh / 2) * h
                if x2 > x1 and y2 > y1:
                    gts.append(GroundTruth(box_xyxy=(x1, y1, x2, y2)))
        frames.append(LabeledFrame(image=img, ground_truths=gts))
    return frames


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hades-eval-arm")
    parser.add_argument("--weights", required=True, help="best.pt / .mlpackage / .onnx")
    parser.add_argument("--test-dir", required=True, help="merged test split dir")
    parser.add_argument("--conf", type=float, default=0.25, help="operating threshold")
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--max-distance", type=float, default=10.0, help="orig-frame px")
    parser.add_argument(
        "--backend",
        choices=["ultralytics", "coreml"],
        default="ultralytics",
        help="coreml = the SHIPPED CoreMLDetector path (FP16 + decode_yolo NMS); the honest "
        "acceptance number. ultralytics = .pt/.mlpackage via YOLO (training-proxy).",
    )
    args = parser.parse_args(argv)

    frames = load_test_frames(Path(args.test_dir))
    if not frames:
        print(f"ERROR: no frames under {args.test_dir}", file=sys.stderr)
        return 1
    if args.backend == "coreml":
        # The actual shipped path: FP16 .mlpackage through the real CoreMLDetector + decode_yolo.
        from hades.detect.coreml_detector import CoreMLDetector

        det = CoreMLDetector(args.weights, imgsz=args.imgsz, conf_threshold=0.01)
    else:
        det = _UltralyticsDetector(args.weights, conf=args.conf, imgsz=args.imgsz)
    report = evaluate(det, frames, max_distance=args.max_distance, conf_threshold=args.conf)

    print(f"=== arm eval: {args.weights} ===")
    print(f"operating point: conf={args.conf} | matcher=center-distance@{args.max_distance}px "
          f"(orig-frame) | imgsz={args.imgsz} | n_frames={len(frames)}")
    print(format_report(report))
    o = report.overall
    print(f"RECALL={o.recall} PRECISION={o.precision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
