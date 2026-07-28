#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from drone_yolo_fpv.io import open_capture


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture still frames from a video source for README samples.")
    parser.add_argument("--source", type=str, required=True)
    parser.add_argument("--output-dir", type=str, default="outputs/detections/raw_frames")
    parser.add_argument("--every", type=int, default=60, help="Save every Nth frame.")
    parser.add_argument("--max-saves", type=int, default=10)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = open_capture(args.source)
    frame_index = 0
    saved = 0

    try:
        while saved < args.max_saves:
            ok, frame = cap.read()
            if not ok:
                break
            frame_index += 1
            if frame_index % args.every == 0:
                path = out_dir / f"frame_{frame_index:06d}.jpg"
                cv2.imwrite(str(path), frame)
                print(f"[INFO] Saved {path}")
                saved += 1
    finally:
        cap.release()

    print(f"[INFO] Saved {saved} frames to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
