"""Launcher: run the seeker bench on the LIVE FT640 feed (UVC grabber via ffmpeg/avfoundation).

Run this from a terminal that HAS macOS camera permission — the recorded-clip bench can't open the
camera (a sandboxed process is denied by macOS TCC). Serves the LIVE annotated seeker + telemetry +
operator LAUNCH/SAFE at http://127.0.0.1:8093.

    PYTHONPATH=fpv python run_bench_live.py
    BENCH_CAM_DEVICE="USB Video" BENCH_BLACKHOT=0 BENCH_PORT=8093 python run_bench_live.py

Env:
    BENCH_CAM_DEVICE  ffmpeg avfoundation device name/index of the grabber (default "USB Video").
                      List devices: ffmpeg -f avfoundation -list_devices true -i ""
    BENCH_CAM_FPS     capture framerate (default 30)
    BENCH_BLACKHOT    1 = black-hot palette (hot = dark); default 0 (white-hot, matches FT640 here)
    BENCH_PORT        server port (default 8093)
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "fpv"))

from fpv_ai.bench.observer import ObserverConfig          # noqa: E402
from fpv_ai.bench.camera_source import CameraFrameSource   # noqa: E402
from fpv_ai.bench.server import run                         # noqa: E402

device = os.environ.get("BENCH_CAM_DEVICE", "USB Video")
fps = float(os.environ.get("BENCH_CAM_FPS", "30"))
black_hot = os.environ.get("BENCH_BLACKHOT", "0") == "1"
port = int(os.environ.get("BENCH_PORT", "8093"))

cfg = ObserverConfig(hfov_deg=48.7, border_crop=0, mask_on=False, invert=black_hot)
print(f"[bench-live] camera='{device}' fps={fps:.0f} black_hot={black_hot}  ->  http://127.0.0.1:{port}")
print("[bench-live] must run from a camera-permitted terminal; if the wrong camera opens, set BENCH_CAM_DEVICE.")
run(cfg, host="127.0.0.1", port=port, source=CameraFrameSource(device, fps=fps))
