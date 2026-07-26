"""Launcher: run the REAL seeker bench on a recorded thermal VIDEO FILE.

The same Python seeker we validate in sim, driven by a real thermal clip instead of a synthetic
scene. Serves the annotated video + live telemetry + operator LAUNCH/SAFE at http://127.0.0.1:8093.

    PYTHONPATH=fpv python run_bench_video.py path/to/clip.mp4
    BENCH_VIDEO=demo/thermal_input.mp4 BENCH_BLACKHOT=1 python run_bench_video.py

Env:
    BENCH_VIDEO    path to the clip (default: demo/thermal_input.mp4)
    BENCH_BLACKHOT set to 1 for black-hot palette (hot = dark)
    BENCH_PORT     server port (default 8093)
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "fpv"))

from fpv_ai.bench.observer import ObserverConfig       # noqa: E402
from fpv_ai.bench.video_source import VideoFileFrameSource  # noqa: E402
from fpv_ai.bench.server import run                     # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BENCH_VIDEO", "demo/thermal_input.mp4")
black_hot = os.environ.get("BENCH_BLACKHOT", "0") == "1"
port = int(os.environ.get("BENCH_PORT", "8093"))

if not os.path.isabs(path):
    path = os.path.join(_HERE, path)

# border_crop=0: a clean recorded clip has no CVBS edge. mask_on=False: a static-clutter mask assumes
# a fixed camera; a moving thermal clip is better served by the SNR/area gates + operator reticle.
cfg = ObserverConfig(hfov_deg=48.7, border_crop=0, mask_on=False, invert=black_hot)
video_dir = os.path.dirname(path)          # every clip in this folder is selectable from the UI
print(f"[bench-video] {path}  black_hot={black_hot}  ->  http://127.0.0.1:{port}")
run(cfg, host="127.0.0.1", port=port, source=VideoFileFrameSource(path, loop=True),
    video_dir=video_dir, current_video=os.path.basename(path))
