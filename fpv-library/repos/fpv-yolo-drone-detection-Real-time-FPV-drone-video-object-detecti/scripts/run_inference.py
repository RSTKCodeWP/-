#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from drone_yolo_fpv.config import load_yaml_config
from drone_yolo_fpv.drawing import draw_hud
from drone_yolo_fpv.io import ensure_parent, get_video_properties, make_video_writer, open_capture, write_json
from drone_yolo_fpv.metrics import FPSMeter
from drone_yolo_fpv.yolo_engine import YOLOInferenceEngine


def parse_classes(value: str | None) -> list[int] | None:
    if value is None or value.strip() == "":
        return None
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run real-time YOLO object detection on FPV/drone video using OpenCV."
    )
    parser.add_argument("--config", type=str, default=None, help="Optional YAML config file.")
    parser.add_argument("--source", type=str, default=None, help="Video path, webcam index, RTSP URL, or pipeline.")
    parser.add_argument("--model", type=str, default=None, help="YOLO model path, e.g., yolo11n.pt or yolo11n.engine.")
    parser.add_argument("--imgsz", type=int, default=None, help="Inference image size.")
    parser.add_argument("--conf", type=float, default=None, help="Confidence threshold.")
    parser.add_argument("--iou", type=float, default=None, help="IoU threshold.")
    parser.add_argument("--device", type=str, default=None, help="Device string, e.g., cpu, 0, cuda:0.")
    parser.add_argument("--half", action="store_true", help="Use FP16 half precision when supported.")
    parser.add_argument("--classes", type=str, default=None, help="Comma-separated class IDs, e.g., 0,2,3.")
    parser.add_argument("--show", action="store_true", help="Display live annotated window.")
    parser.add_argument("--output", type=str, default=None, help="Annotated output video path.")
    parser.add_argument("--save-csv", type=str, default=None, help="CSV path for detection records.")
    parser.add_argument("--save-json", type=str, default=None, help="JSON path for run summary.")
    parser.add_argument("--save-sample-every", type=int, default=0, help="Save annotated frame every N frames.")
    parser.add_argument("--sample-dir", type=str, default="outputs/detections", help="Directory for saved sample frames.")
    parser.add_argument("--max-frames", type=int, default=None, help="Stop after N frames. Useful for tests.")
    parser.add_argument("--no-hud", action="store_true", help="Disable FPS/HUD overlay.")
    return parser


def merge_args_with_config(args: argparse.Namespace) -> dict:
    cfg = {}
    if args.config:
        cfg.update(load_yaml_config(args.config))

    cli_values = {
        "source": args.source,
        "model": args.model,
        "imgsz": args.imgsz,
        "conf": args.conf,
        "iou": args.iou,
        "device": args.device,
        "classes": parse_classes(args.classes),
        "show": args.show if args.show else None,
        "output": args.output,
        "save_csv": args.save_csv,
        "save_json": args.save_json,
        "max_frames": args.max_frames,
    }
    for key, value in cli_values.items():
        if value is not None:
            cfg[key] = value
    if args.half:
        cfg["half"] = True

    cfg.setdefault("source", "0")
    cfg.setdefault("model", "yolo11n.pt")
    cfg.setdefault("imgsz", 640)
    cfg.setdefault("conf", 0.35)
    cfg.setdefault("iou", 0.45)
    cfg.setdefault("device", None)
    cfg.setdefault("half", False)
    cfg.setdefault("classes", None)
    cfg.setdefault("show", False)
    cfg.setdefault("output", None)
    cfg.setdefault("save_csv", None)
    cfg.setdefault("save_json", None)
    cfg.setdefault("max_frames", None)
    return cfg


def main() -> int:
    args = build_parser().parse_args()
    cfg = merge_args_with_config(args)

    cap = open_capture(str(cfg["source"]))
    props = get_video_properties(cap)
    width = int(props["width"] or 1280)
    height = int(props["height"] or 720)
    source_fps = float(props["fps"] or 30.0)

    writer = None
    if cfg["output"]:
        writer = make_video_writer(cfg["output"], source_fps, width, height)

    csv_file = None
    csv_writer = None
    if cfg["save_csv"]:
        ensure_parent(cfg["save_csv"])
        csv_file = Path(cfg["save_csv"]).open("w", newline="", encoding="utf-8")
        fieldnames = ["frame_index", "class_id", "class_name", "confidence", "x1", "y1", "x2", "y2"]
        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        csv_writer.writeheader()

    sample_dir = Path(args.sample_dir)
    sample_dir.mkdir(parents=True, exist_ok=True)

    engine = YOLOInferenceEngine(str(cfg["model"]))
    fps_meter = FPSMeter()
    total_records = 0
    per_class_counts: dict[str, int] = {}

    frame_index = 0
    print(f"[INFO] Source: {cfg['source']}")
    print(f"[INFO] Model:  {cfg['model']}")
    print(f"[INFO] Size:   {width}x{height} @ source FPS {source_fps:.2f}")
    print("[INFO] Press 'q' in the display window to stop.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_index += 1

            result, latency_ms = engine.predict_frame(
                frame,
                imgsz=int(cfg["imgsz"]),
                conf=float(cfg["conf"]),
                iou=float(cfg["iou"]),
                device=cfg["device"],
                half=bool(cfg["half"]),
                classes=cfg["classes"],
            )
            fps_meter.add_latency(latency_ms)

            records = engine.records_from_result(result, frame_index)
            total_records += len(records)
            for rec in records:
                per_class_counts[rec.class_name] = per_class_counts.get(rec.class_name, 0) + 1
                if csv_writer:
                    csv_writer.writerow(rec.as_dict())

            annotated = result.plot()
            if not args.no_hud:
                annotated = draw_hud(
                    annotated,
                    fps=fps_meter.average_fps,
                    frame_index=frame_index,
                    detections_count=len(records),
                    model_name=Path(str(cfg["model"])).name,
                )

            if writer:
                writer.write(annotated)

            if args.save_sample_every and frame_index % args.save_sample_every == 0:
                cv2.imwrite(str(sample_dir / f"sample_frame_{frame_index:06d}.jpg"), annotated)

            if cfg["show"]:
                cv2.imshow("FPV YOLO Detection", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if cfg["max_frames"] and frame_index >= int(cfg["max_frames"]):
                break
    finally:
        cap.release()
        if writer:
            writer.release()
        if csv_file:
            csv_file.close()
        cv2.destroyAllWindows()

    summary = {
        "model": str(cfg["model"]),
        "source": str(cfg["source"]),
        "imgsz": int(cfg["imgsz"]),
        "conf": float(cfg["conf"]),
        "iou": float(cfg["iou"]),
        "video_properties": props,
        "total_detection_records": total_records,
        "per_class_counts": dict(sorted(per_class_counts.items(), key=lambda kv: kv[0])),
        **fps_meter.summary(),
    }

    if cfg["save_json"]:
        write_json(cfg["save_json"], summary)

    print("\n[SUMMARY]")
    for key, value in summary.items():
        print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
