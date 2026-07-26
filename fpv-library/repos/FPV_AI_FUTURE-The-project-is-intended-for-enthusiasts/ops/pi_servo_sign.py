"""Verify the gimbal servo SIGN safely -- the #1 pre-flight defect (a wrong sign drives the target OUT of
frame instead of centring it). OPEN-LOOP probe: step each servo a small known amount and measure which way a
live warm target moves in the FT640 image. No feedback loop, so it cannot run the gimbal into its stops.

Uses the seeker.service stream for frames (no exclusive camera / no sudo) and the PCA9685 for the 2 gimbal
servos only. Head must be free to move and a stable warm object in view (run pi_live_perception first).

    PYTHONPATH=.:fpv python3 ops/pi_servo_sign.py [--step-deg 8]
"""
from __future__ import annotations

import argparse
import math
import sys
import time

import numpy as np


def _target_px(cap, pipe, tries=25):
    """Grab frames until the tracker reports a centroid; return (px,py) or None."""
    import cv2
    for _ in range(tries):
        ok, f = cap.read()
        if not ok or f is None:
            continue
        if f.ndim == 3:
            f = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        u16 = (f.astype(np.uint16) << 6) + 4096
        out = pipe.step(time.monotonic(), u16, (0.0, 0.0, 0.0), 0.04)
        if out.centroid_px is not None and "LOCK" in out.tracking_state:
            return out.centroid_px, f.shape
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", default="http://127.0.0.1:8090/s.mjpg")
    ap.add_argument("--step-deg", type=float, default=8.0)
    ap.add_argument("--pan-channel", type=int, default=0)
    ap.add_argument("--tilt-channel", type=int, default=1)
    ap.add_argument("--designate", default="240,192", help="cx,cy of the warm target in the stream frame")
    args = ap.parse_args()

    import cv2
    from fpv.guidance.pipeline import SeekerGuidancePipeline
    from fpv.seeker.geometry import ft640_intrinsics
    from seeker_core.pi5_io import Pi5Config, make_pca9685_servo_writer, rad_to_pulse_us

    cfg = Pi5Config()
    write = make_pca9685_servo_writer(addr=0x40)

    def center():
        write(args.pan_channel, rad_to_pulse_us(0.0, +1.0, cfg))
        write(args.tilt_channel, rad_to_pulse_us(0.0, +1.0, cfg))

    cap = cv2.VideoCapture(args.stream)
    if not cap.isOpened():
        print("FAIL: no stream (%s)" % args.stream); sys.exit(1)
    pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics(), full_ego_compensation=True)
    _cx, _cy = (float(v) for v in args.designate.split(","))
    pipe.designate((_cx, _cy))

    center(); time.sleep(0.8)
    p0, shape = _target_px(cap, pipe)
    if p0 is None:
        print("FAIL: no locked target in view -- point the camera at a warm object and re-run"); sys.exit(1)
    print("start: target at px=(%.0f,%.0f) in %s" % (p0[0], p0[1], shape))

    def probe(ch, name, ang_deg):
        write(ch, rad_to_pulse_us(math.radians(ang_deg), +1.0, cfg)); time.sleep(1.0)
        p, _ = _target_px(cap, pipe)
        write(ch, rad_to_pulse_us(0.0, +1.0, cfg)); time.sleep(0.8)      # return to centre
        return p

    step = args.step_deg
    pan_p = probe(args.pan_channel, "PAN", step)
    tilt_p = probe(args.tilt_channel, "TILT", step)

    print("\n=== servo sign ===")
    ok = True
    if pan_p is None:
        print("PAN : lost the target during the step (inconclusive)"); ok = False
    else:
        dx = pan_p[0] - p0[0]
        # PAN + should turn the camera one way; a fixed target then shifts the OPPOSITE way in the image.
        # Convention check: the controller expects target-right(ex>0) -> pan+ to CENTRE it, i.e. pan+ moves the
        # image target LEFT (dx<0). dx>0 means the sign is INVERTED.
        verdict = "CORRECT (target moved left)" if dx < -3 else ("INVERTED -> set Pi5Config sign/invert" if dx > 3 else "too small / target not moving")
        print("PAN +%.0f deg -> target dx = %+.0f px  => %s" % (step, dx, verdict))
        ok = ok and dx < -3

    if tilt_p is None:
        print("TILT: lost the target during the step (inconclusive)"); ok = False
    else:
        dy = tilt_p[1] - p0[1]
        verdict = "CORRECT (target moved up)" if dy < -3 else ("INVERTED -> set Pi5Config sign/invert" if dy > 3 else "too small / target not moving")
        print("TILT +%.0f deg -> target dy = %+.0f px  => %s" % (step, dy, verdict))
        ok = ok and dy < -3

    center()
    cap.release()
    print("\n%s" % ("BOTH AXES CORRECT -- the gimbal will centre a target, not push it out." if ok
                    else "FIX THE FLAGGED AXIS before any closed-loop tracking (a wrong sign loses the target)."))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
