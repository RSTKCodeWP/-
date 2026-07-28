#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a short demo clip from an annotated video.")
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, default="outputs/videos/demo_15s.mp4")
    parser.add_argument("--start-sec", type=float, default=0.0)
    parser.add_argument("--duration-sec", type=float, default=15.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open input video: {args.input}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
    start_frame = int(args.start_sec * fps)
    frames_to_write = int(args.duration_sec * fps)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        args.output,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not create output video: {args.output}")

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    written = 0
    try:
        while written < frames_to_write:
            ok, frame = cap.read()
            if not ok:
                break
            writer.write(frame)
            written += 1
    finally:
        cap.release()
        writer.release()

    print(f"[INFO] Wrote {written} frames to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
