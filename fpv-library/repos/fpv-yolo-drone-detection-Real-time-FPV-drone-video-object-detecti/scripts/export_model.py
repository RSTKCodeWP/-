#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export YOLO model for deployment.")
    parser.add_argument("--model", type=str, default="yolo11n.pt", help="Input YOLO model path.")
    parser.add_argument(
        "--format",
        type=str,
        default="onnx",
        choices=["onnx", "engine", "openvino", "coreml", "tflite", "torchscript"],
        help="Export format. Use engine for TensorRT on NVIDIA GPUs/Jetson.",
    )
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--half", action="store_true", help="Export FP16 when supported.")
    parser.add_argument("--int8", action="store_true", help="Export INT8 when supported; needs calibration data for best results.")
    parser.add_argument("--device", type=str, default=None, help="Export device, e.g. 0, cpu, dla:0.")
    parser.add_argument("--dynamic", action="store_true", help="Enable dynamic input shape where supported.")
    parser.add_argument("--simplify", action="store_true", help="Simplify ONNX where supported.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise ImportError("Ultralytics is not installed. Run `pip install -r requirements.txt`.") from exc

    model = YOLO(args.model)
    print(f"[INFO] Exporting {args.model} to {args.format}...")
    exported_path = model.export(
        format=args.format,
        imgsz=args.imgsz,
        half=args.half,
        int8=args.int8,
        device=args.device,
        dynamic=args.dynamic,
        simplify=args.simplify,
    )
    print(f"[INFO] Export complete: {exported_path}")
    print(f"[INFO] File exists: {Path(str(exported_path)).exists()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
