"""Camera signal probe for the Pi bench -- diagnoses "is CVBS reaching the grabber?".

A black (all-zero) frame means the grabber is alive but no analog video is locked onto
its composite input. On the FT640/CVBS bench that is almost always one of:
  * the FT640 is not powered (it needs ~5V; the USB grabber does NOT power the camera),
  * the camera's VIDEO wire is not on the grabber's YELLOW composite-in (vs audio RCA),
  * no common GND between the camera and the grabber,
  * the camera just powered up and hasn't started its sensor yet (give it a few seconds).

Run on the Pi:  PYTHONPATH=fpv python -m fpv_ai.sensor.cam_probe
"""

from __future__ import annotations

import argparse
import time

import numpy as np


def probe_device(device: str, *, fourcc: str, width: int, height: int,
                 frames: int, settle: float) -> dict:
    from fpv_ai.sensor.thermal_capture import V4L2Source

    try:
        src = V4L2Source(device, width=width, height=height, fourcc=fourcc)
    except Exception as exc:  # pragma: no cover - hardware path
        return {"device": device, "fourcc": fourcc, "opened": False, "error": str(exc)}

    t0 = time.monotonic()
    while time.monotonic() - t0 < settle:        # discard the grabber's warm-up frames
        src.read()

    gmax = 0.0
    nonzero_frames = 0
    n = 0
    shape = None
    acc = None
    for _ in range(frames):
        r = src.read()
        if r is None:
            continue
        n += 1
        shape = r.shape
        g = r.astype(np.float64).mean(axis=2) if r.ndim == 3 else r.astype(np.float64)
        m = float(g.max())
        if m > 0:
            nonzero_frames += 1
        gmax = max(gmax, m)
        acc = g if acc is None else np.maximum(acc, g)
    src.close()

    res = {"device": device, "fourcc": fourcc, "opened": True, "frames_read": n,
           "shape": shape, "nonzero_frames": nonzero_frames, "max_over_time": gmax}
    if acc is not None and gmax > 0:
        h, w = acc.shape
        gh, gw = h // 8, w // 8
        if gh and gw:
            res["grid"] = acc[: gh * 8, : gw * 8].reshape(8, gh, 8, gw).max(axis=(1, 3))
    return res


def main() -> None:  # pragma: no cover - hardware bench
    ap = argparse.ArgumentParser(description="Probe a CVBS->USB grabber for a live signal")
    ap.add_argument("--device", default="/dev/video0")
    ap.add_argument("--also", default="/dev/video1", help="second node tried if the first is black")
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--settle", type=float, default=1.5, help="seconds of frames to discard at start")
    args = ap.parse_args()

    combos = [(args.device, "MJPG", 720, 480), (args.device, "YUYV", 480, 320)]
    if args.also:
        combos.append((args.also, "MJPG", 720, 480))

    verdict = "NO SIGNAL"
    for dev, fcc, w, h in combos:
        r = probe_device(dev, fourcc=fcc, width=w, height=h, frames=args.frames, settle=args.settle)
        if not r["opened"]:
            print(f"[{dev} {fcc}] could not open: {r.get('error')}")
            continue
        print(f"[{dev} {fcc} {w}x{h}] frames={r['frames_read']} shape={r['shape']} "
              f"nonzero_frames={r['nonzero_frames']} max_over_time={r['max_over_time']:.0f}")
        if r["max_over_time"] > 0:
            verdict = "SIGNAL PRESENT"
            if "grid" in r:
                print("  8x8 max-intensity grid (shows WHERE the signal is, center is the boresight):")
                for row in r["grid"]:
                    print("   " + " ".join("%3d" % int(v) for v in row))
            break

    print("VERDICT:", verdict)
    if verdict == "NO SIGNAL":
        print("  -> grabber is alive but no analog video is locked onto it.")
        print("  -> CHECK: (1) FT640 has its own ~5V power (the grabber does NOT power it),")
        print("            (2) camera VIDEO wire -> grabber YELLOW composite RCA (not audio),")
        print("            (3) common GND between camera and grabber,")
        print("            (4) give the camera ~5s after power to start its sensor.")


if __name__ == "__main__":
    main()
