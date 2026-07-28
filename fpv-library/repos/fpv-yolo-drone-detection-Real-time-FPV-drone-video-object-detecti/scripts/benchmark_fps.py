#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from drone_yolo_fpv.io import open_capture, write_json
from drone_yolo_fpv.metrics import FPSMeter
from drone_yolo_fpv.yolo_engine import YOLOInferenceEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark YOLO FPS and latency on a video source.")
    parser.add_argument("--source", type=str, required=True)
    parser.add_argument("--model", type=str, default="yolo11n.pt")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--half", action="store_true")
    parser.add_argument("--warmup", type=int, default=20, help="Warmup frames ignored from metrics.")
    parser.add_argument("--frames", type=int, default=300, help="Measured frames after warmup.")
    parser.add_argument("--output", type=str, default="outputs/benchmarks/benchmark.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cap = open_capture(args.source)
    engine = YOLOInferenceEngine(args.model)

    measured = FPSMeter()
    seen = 0
    target_total = args.warmup + args.frames

    print(f"[INFO] Warming up for {args.warmup} frames, then measuring {args.frames} frames.")

    try:
        while seen < target_total:
            ok, frame = cap.read()
            if not ok:
                cap.set(1, 0)
                ok, frame = cap.read()
                if not ok:
                    break

            seen += 1
            _, latency_ms = engine.predict_frame(
                frame,
                imgsz=args.imgsz,
                conf=args.conf,
                iou=args.iou,
                device=args.device,
                half=args.half,
            )
            if seen > args.warmup:
                measured.add_latency(latency_ms)
    finally:
        cap.release()

    summary = {
        "model": args.model,
        "source": args.source,
        "imgsz": args.imgsz,
        "conf": args.conf,
        "iou": args.iou,
        "device": args.device,
        "half": args.half,
        "warmup_frames": args.warmup,
        **measured.summary(),
    }
    write_json(args.output, summary)

    print("\n[BENCHMARK]")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"\n[INFO] Saved benchmark: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
