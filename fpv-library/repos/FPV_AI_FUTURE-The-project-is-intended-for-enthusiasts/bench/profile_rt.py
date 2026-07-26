"""Real-time compute-budget profiler for the seeker pipeline (item #5 prep, HW-transition gate).

Times `SeekerGuidancePipeline.step()` (operational profile) on real
thermal clips and reports p50/p99/max latency + whether it fits the 60 Hz (16.6 ms) and 30 Hz
(33.3 ms) frame budgets. Full real-time proof needs the TARGET compute (RPi5 / Zynq PS); this gives
the budget + per-frame breakdown on the dev host so the transition is "re-run on the Pi", not guess.

    PYTHONPATH=.:fpv python3 -m fpv_ai.bench.profile_rt --clips /path/to/ir --with-classifier
"""
from __future__ import annotations

import argparse
import glob
import os
import statistics
import time

import cv2

from fpv.guidance.pipeline import SeekerGuidancePipeline
from fpv.seeker.geometry import ft640_intrinsics
from .real_ingest import to_counts
from .gate_gb import OPERATIONAL_PROFILE, SKY_PROXY


def _pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def profile(clips_dir: str, per_cat: int = 6, warmup: int = 20) -> None:
    clips = sorted(glob.glob(os.path.join(clips_dir, "IR_DRONE_*.mp4")))[:per_cat]
    step_ms: list[float] = []
    for clip in clips:
        pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics(), acquisition_box=SKY_PROXY,
                                      **OPERATIONAL_PROFILE)
        cap = cv2.VideoCapture(clip)
        n = 0
        while True:
            ok, f = cap.read()
            if not ok:
                break
            u16, _ = to_counts(f, False)
            if u16.shape != (512, 640):
                u16 = cv2.resize(u16, (640, 512), interpolation=cv2.INTER_AREA)
            t0 = time.perf_counter()
            pipe.step(now=n / 30.0, frame_u16=u16, gyro_omega_xyz=(0, 0, 0), dt=1 / 30.0)
            t1 = time.perf_counter()
            if n >= warmup:                          # skip cold-start frames
                step_ms.append((t1 - t0) * 1e3)
            n += 1
        cap.release()
    if not step_ms:
        print("no frames profiled"); return
    p50, p99, mx = _pct(step_ms, 0.50), _pct(step_ms, 0.99), max(step_ms)
    print(f"seeker pipeline latency  (DEV HOST, {len(step_ms)} frames, operational profile)")
    print(f"  per-frame step()  p50 {p50:5.1f} ms   p99 {p99:5.1f} ms   max {mx:5.1f} ms")
    print(f"  fits 60 Hz (16.6 ms): p99 {'YES' if p99 < 16.6 else 'NO'};  "
          f"30 Hz (33.3 ms): p99 {'YES' if p99 < 33.3 else 'NO'}")
    print("  NOTE: dev-host timing. RPi5 CPU is ~2-4x slower for numpy/scipy -> re-run on target "
          "hardware to certify; the ROI-gate + heavy-stage decimation flags exist to hit budget.")


def main():
    ap = argparse.ArgumentParser(description="Seeker pipeline real-time budget profiler")
    ap.add_argument("--clips", required=True)
    ap.add_argument("--per-cat", type=int, default=6)
    a = ap.parse_args()
    profile(a.clips, a.per_cat)


if __name__ == "__main__":
    main()
