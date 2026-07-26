"""`hades-service` entry point - runs the assembled detection/georeference pipeline.

Wires the recorded clip + telemetry through `ServiceLoop` and serves the two localhost WS
channels (binary JPEG frames + JSON detections/contacts). The detector backend is chosen by
flag; `stub` is the CPU/offline default, `onnx`/`coreml` load a real exported model. CoreML is
imported only when that backend is selected (never at module top).
"""

from __future__ import annotations

import argparse
import asyncio
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hades-service", description=__doc__)
    parser.add_argument("--clip", required=True, help="recorded video clip (mp4/ts/h264)")
    parser.add_argument("--telemetry", default=None, help="optional .srt telemetry sidecar")
    parser.add_argument(
        "--detector", default="stub", choices=["stub", "onnx", "coreml"],
        help="detection backend (stub = CPU/offline default)",
    )
    parser.add_argument("--model", default=None, help="model path for onnx/coreml backends")
    parser.add_argument("--imgsz", type=int, default=960, help="detector input resolution")
    parser.add_argument("--binary-port", type=int, default=8765)
    parser.add_argument("--json-port", type=int, default=8766)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args(argv)

    from hades.cli.replay_dump import make_detector
    from hades.service.loop import ServiceLoop, serve

    detector = make_detector(args.detector, model_path=args.model, imgsz=args.imgsz)
    loop = ServiceLoop(clip=args.clip, telemetry=args.telemetry, detector=detector)
    print(
        f"hades-service: serving binary :{args.binary_port} json :{args.json_port} "
        f"(detector={args.detector})",
        file=sys.stderr,
    )
    try:
        asyncio.run(
            serve(
                loop,
                binary_port=args.binary_port,
                json_port=args.json_port,
                fps=args.fps,
                max_frames=args.max_frames,
            )
        )
    except KeyboardInterrupt:
        print("hades-service: stopped", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
