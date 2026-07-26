"""Live thermal-detection bench for the Pi5 (Block-3 hardware phase, camera B1 step).

Run this ON THE RASPBERRY PI with the FT640 connected through a CVBS->USB grabber. It opens
the V4L2 device, runs the real S1 detector + S2/S3 pipeline on live frames, and prints the
lock state / centroid / LOS-rate / measured FPS. This is how you validate that the real
thermal feed actually detects and tracks a hot target before any flight.

    python -m fpv_ai.sensor.thermal_bench --device /dev/video0 --invert
    # find the grabber device first:  v4l2-ctl --list-devices
    # if the thermal image is letterboxed in the grabbed frame, pass --roi X Y W H

Needs opencv-python on the Pi (pip install opencv-python). Hardware-only -- not unit tested.
"""

from __future__ import annotations

import argparse
import time

from fpv.guidance.pipeline import SeekerGuidancePipeline

from fpv_ai.sensor.thermal_capture import (
    CaptureConfig,
    ThermalCapture,
    V4L2Source,
    ft640_intrinsics,
)


def main() -> None:  # pragma: no cover - hardware bench
    ap = argparse.ArgumentParser(description="Live FT640 thermal detection bench (Pi5)")
    ap.add_argument("--device", default="/dev/video0", help="V4L2 device (CVBS->USB grabber)")
    ap.add_argument("--width", type=int, default=720, help="MS2109/EasyCap max is 720x480")
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--fourcc", default="MJPG", help="MJPG gets 720x480 on MS2109; YUYV caps at 480x320")
    ap.add_argument("--roi", type=int, nargs=4, metavar=("X", "Y", "W", "H"), default=None,
                    help="active thermal area in the grabbed frame (for letterboxed CVBS)")
    ap.add_argument("--invert", action="store_true", help="black-hot palette (target is dark)")
    ap.add_argument("--deinterlace", action="store_true", help="CVBS even-field de-interlace")
    ap.add_argument("--hfov", type=float, default=48.7, help="lens HFOV in degrees (FT640 V2 ~48.7)")
    ap.add_argument("--report-every", type=int, default=30)
    args = ap.parse_args()

    source = V4L2Source(args.device, width=args.width, height=args.height, fourcc=args.fourcc)
    cap = ThermalCapture(source, CaptureConfig(
        roi=tuple(args.roi) if args.roi else None,
        deinterlace=args.deinterlace, invert=args.invert,
    ))
    pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics(hfov_deg=args.hfov))

    print(f"[bench] capturing from {args.device}; Ctrl-C to stop")
    n = 0
    t0 = time.monotonic()
    last = t0
    try:
        while True:
            now = time.monotonic()
            frame = cap.frame_u16()
            if frame is None:
                print("[bench] no frame (device closed?)")
                break
            dt = now - last
            last = now
            out = pipe.step(now, frame, (0.0, 0.0, 0.0), max(dt, 1e-4))
            n += 1
            if n % args.report_every == 0:
                fps = args.report_every / (now - t0) if n == args.report_every else None
                az = el = None
                if out.imm is not None:
                    az, el = out.imm.az_rate_radps, out.imm.el_rate_radps
                print(f"[{n:5d}] state={out.tracking_state:14s} locked={out.locked} "
                      f"cmd={'yes' if out.command else 'no '} "
                      f"lam_az={az if az is None else round(az,4)} lam_el={el if el is None else round(el,4)} "
                      f"fps={round(1.0/dt,1) if dt>0 else '?'}")
    except KeyboardInterrupt:
        print("\n[bench] stopped")
    finally:
        cap.close()


if __name__ == "__main__":
    main()
