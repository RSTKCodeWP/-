"""`hades` umbrella CLI — subcommand dispatch.

`hades replay-dump <clip> [--telemetry <srt>] [--out <dir>]` is the first
subcommand (Phase 1, the observable-ingestion green criterion). More subcommands
are added as later phases land.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from hades.cli.replay_dump import make_detector, run_replay_dump


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hades", description="HADES service CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    rd = sub.add_parser("replay-dump", help="dump annotated frames from a recorded feed")
    rd.add_argument("clip", help="path to the recorded video clip")
    rd.add_argument("--telemetry", default=None, help="optional .srt telemetry sidecar")
    rd.add_argument("--out", default="replay_frames", help="output directory for frames")
    rd.add_argument("--stride", type=int, default=1, help="write every Nth frame (default 1)")
    rd.add_argument("--max-frames", type=int, default=None, help="cap frames written")
    rd.add_argument("--detect", action="store_true", help="run the detector and draw boxes")
    rd.add_argument(
        "--backend",
        choices=("stub", "onnx", "coreml"),
        default="stub",
        help="detector backend for --detect (default stub; onnx/coreml need --model)",
    )
    rd.add_argument("--model", default=None, help="path to the model for onnx/coreml backend")
    rd.add_argument(
        "--track",
        action="store_true",
        help="track detections and draw track id + priority tier (implies --detect)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse exits SystemExit on --help/--version (code 0) and on bad args
        # (code 2). Preserve the code as-is; `code or 2` would turn a 0 into a 2,
        # making successful help output look like an error to scripts.
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return exc.code
        return 2  # a string code means an argparse error message

    if args.command == "replay-dump":
        # --track needs detections to track, so it implies --detect.
        need_detector = args.detect or args.track
        detector = make_detector(args.backend, model_path=args.model) if need_detector else None
        n = run_replay_dump(
            args.clip,
            args.telemetry,
            args.out,
            stride=args.stride,
            max_frames=args.max_frames,
            detector=detector,
            track=args.track,
        )
        print(f"wrote {n} frames to {args.out}")
        return 0
    return 2  # unreachable: subparsers are required


if __name__ == "__main__":
    raise SystemExit(main())
