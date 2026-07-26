"""Entry point: PYTHONPATH=fpv python -m fpv_ai.bench --device /dev/video0

Starts the seeker observation bench and serves the dashboard on :8080.
"""

from __future__ import annotations

import argparse

from fpv_ai.bench.observer import ObserverConfig
from fpv_ai.bench.server import run


def main() -> None:
    ap = argparse.ArgumentParser(description="Block-3 seeker test/observation bench")
    ap.add_argument("--device", default="/dev/video0", help="V4L2 device (CVBS->USB grabber)")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--hfov", type=float, default=48.7)
    ap.add_argument("--border-crop", type=int, default=24)
    ap.add_argument("--fourcc", default="MJPG", help="MJPG (720x480, compressed -> block artefacts) "
                    "or YUYV (uncompressed, caps at 480x320 on MS2109 -- cleaner for thermal)")
    ap.add_argument("--width", type=int, default=720)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--deinterlace", action="store_true", help="CVBS even-field de-interlace")
    ap.add_argument("--no-mask", action="store_true", help="start with the clutter mask off")
    ap.add_argument("--invert", action="store_true", help="black-hot palette")
    ap.add_argument("--sim", action="store_true",
                    help="replay a synthetic moving-target scene instead of the camera")
    ap.add_argument("--sim-mode", default="sweep", choices=["sweep", "approach"],
                    help="sweep = fixed-size lateral target; approach = growing/looming target")
    args = ap.parse_args()

    source = None
    if args.sim:
        from fpv_ai.bench.sim_source import SimFrameSource
        source = SimFrameSource(mode=args.sim_mode)
        # synthetic scene is clean + 14-bit: no clutter mask, no CVBS border crop
        cfg = ObserverConfig(hfov_deg=args.hfov, border_crop=0, mask_on=False, invert=args.invert)
    else:
        cfg = ObserverConfig(device=args.device, hfov_deg=args.hfov, border_crop=args.border_crop,
                             mask_on=not args.no_mask, invert=args.invert,
                             fourcc=args.fourcc, width=args.width, height=args.height,
                             deinterlace=args.deinterlace)
    run(cfg, host=args.host, port=args.port, source=source)


if __name__ == "__main__":
    main()
