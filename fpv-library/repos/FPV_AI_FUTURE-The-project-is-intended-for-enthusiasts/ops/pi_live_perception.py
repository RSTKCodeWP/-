"""Run OUR seeker pipeline on LIVE FT640 frames -- pulled from the running seeker.service MJPEG stream, so it
needs no exclusive camera access and no sudo. This is the first time the new flight-code perception sees REAL
thermal data (the sim-vs-real check, GAP 2). Read-only: no servos, no FC, no motors.

    PYTHONPATH=.:fpv python3 ops/pi_live_perception.py [--seconds 8] [--designate cx,cy]
"""
from __future__ import annotations

import argparse
import sys
import time

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", default="http://127.0.0.1:8090/s.mjpg")
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--designate", default="", help="cx,cy to cue the tracker (default: frame centre)")
    args = ap.parse_args()

    import cv2
    from fpv.guidance.pipeline import SeekerGuidancePipeline
    from fpv.seeker.geometry import ft640_intrinsics

    cap = cv2.VideoCapture(args.stream)
    if not cap.isOpened():
        print("FAIL: cannot open the stream %s (is seeker.service up on :8090?)" % args.stream)
        sys.exit(1)

    pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics(), full_ego_compensation=True)
    designated = False
    n = 0
    locks = 0
    snrs = []
    mins = []
    maxs = []
    states = {}
    t0 = time.monotonic()
    last_shape = None
    while time.monotonic() - t0 < args.seconds:
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        if frame.ndim == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        last_shape = frame.shape
        # 8-bit AGC gray -> uint16 pseudo-counts (documented lossy; matches pi5_io.frame_8bit_to_contract)
        u16 = (frame.astype(np.uint16) << 6) + 4096
        mins.append(int(frame.min())); maxs.append(int(frame.max()))
        if not designated:
            h, w = frame.shape
            if args.designate:
                cx, cy = (float(x) for x in args.designate.split(","))
            else:
                cx, cy = w / 2.0, h / 2.0
            pipe.designate((cx, cy))
            designated = True
        out = pipe.step(time.monotonic(), u16, (0.0, 0.0, 0.0), 1.0 / 25.0)
        n += 1
        states[out.tracking_state] = states.get(out.tracking_state, 0) + 1
        if "LOCK" in out.tracking_state:
            locks += 1
        if out.snr is not None:
            snrs.append(out.snr)
    cap.release()

    print("=== LIVE FT640 perception (our pipeline on the service's stream) ===")
    if n == 0:
        print("FAIL: no frames decoded from the stream"); sys.exit(1)
    fps = n / (time.monotonic() - t0)
    print("frames: %d  (%.1f fps)  size %s" % (n, fps, last_shape))
    print("pixel 8-bit min/max: %d..%d (median max %d)  -> %s" % (
        int(np.median(mins)), int(np.median(maxs)), int(np.median(maxs)),
        "flat, no strong warm object" if np.median(maxs) - np.median(mins) < 40 else "there IS contrast in view"))
    print("tracker states: " + ", ".join("%s=%d" % (k, v) for k, v in sorted(states.items())))
    print("LOCK frames: %d/%d (%.0f%%)" % (locks, n, 100.0 * locks / n))
    if snrs:
        print("target SNR when detected: median %.1f  max %.1f" % (float(np.median(snrs)), float(np.max(snrs))))
    print("\nHONEST READ: this proves the pipeline RUNS on real FT640 data. Whether it LOCKS depends on a warm")
    print("object being in the cued box -- point the camera at a warm target (a hand, a soldering iron, a")
    print("person) and re-run, or pass --designate cx,cy to cue where the target actually is.")


if __name__ == "__main__":
    main()
