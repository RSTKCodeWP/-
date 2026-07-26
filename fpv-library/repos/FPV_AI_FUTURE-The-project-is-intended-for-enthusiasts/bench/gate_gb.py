"""Gate G-B — detect-and-hold on REAL thermal clips (the "must be true #1" gate).

The audit's item #1 ("detects and holds a REAL target, not clutter") is measured here on real
thermal imagery, with the OPERATIONAL SEEKER PROFILE validated on real data this session:

    region-adaptive CFAR + ROI track-gate + anti-pull-off (peak-relative deletion + IMM coast).

Result on the DroneDetectionThesis IR drone clips: lock held ~0.91 of frames with only ~0.05 of
locked frames on ground clutter (vs baseline that locked clutter and missed the drone entirely).

HONEST SCOPE:
- The acquisition basket here (`acquisition_box`) stands in for the OPERATOR's LOBL designation.
  In the field the operator/midcourse cue provides it; on these GT-less surveillance clips we use a
  sky proxy (the drone flies in the upper FOV). This is an eval stand-in, stated so it isn't
  mistaken for autonomous acquisition.
- Source is 8-bit display video (indicative). The definitive gate is raw Y16 from the real sensor.
- Distractor clips (bird/plane/heli) are locked too (no classifier) — that is Gate G-D (item #2),
  reported here as the false-lock rate so the discrimination gap is quantified alongside.

    PYTHONPATH=.:fpv python3 -m fpv_ai.bench.gate_gb --clips /path/to/ir --per-cat 20
"""
from __future__ import annotations

import argparse
import glob
import os
import statistics

import cv2

from fpv.guidance.pipeline import SeekerGuidancePipeline
from fpv.seeker.geometry import CameraIntrinsics, ft640_intrinsics
from .real_ingest import to_counts

# The seeker configuration validated on real thermal data (2026-07-04). Acquisition basket is
# supplied per-engagement by the operator's LOBL designation; everything else is fixed here.
OPERATIONAL_PROFILE = dict(
    region_bands=4, graduated_k=True,        # region-adaptive CFAR: sky vs horizon vs ground
    roi_gating=True,                          # track-gate: once locked, detect only near the target
    use_peak_relative_deletion=True,          # anti-pull-off: don't let a hotter blob steal the lock
    use_imm_coast=True,                       # kinematic coast prediction feeds the gate
)
SKY_PROXY = (0.0, 0.0, 640.0, 270.0)          # stand-in for the operator's LOBL designation
GROUND_Y = 270.0                              # locked centroid below this = ground clutter


def build_pipeline(intrinsics: CameraIntrinsics | None = None,
                   acquisition_box=SKY_PROXY) -> SeekerGuidancePipeline:
    return SeekerGuidancePipeline(intrinsics=intrinsics or ft640_intrinsics(),
                                  acquisition_box=acquisition_box, **OPERATIONAL_PROFILE)


def eval_clip(path: str, acquisition_box=SKY_PROXY) -> dict:
    pipe = build_pipeline(acquisition_box=acquisition_box)
    cap = cv2.VideoCapture(path)
    n = locked = 0
    clutter = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        u16, _ = to_counts(f, False)
        if u16.shape != (512, 640):
            u16 = cv2.resize(u16, (640, 512), interpolation=cv2.INTER_AREA)
        out = pipe.step(now=n / 30.0, frame_u16=u16, gyro_omega_xyz=(0, 0, 0), dt=1 / 30.0)
        if "LOCK" in out.tracking_state and out.centroid_px:
            locked += 1
            if out.centroid_px[1] > GROUND_Y:
                clutter += 1
        n += 1
    cap.release()
    return dict(frames=n, hold=locked / max(n, 1),
                clutter_frac=clutter / locked if locked else 0.0)


def run(clips_dir: str, per_cat: int = 20) -> None:
    cats = ("DRONE", "BIRD", "HELICOPTER", "AIRPLANE")
    print("Gate G-B — detect-and-hold on REAL thermal clips (operational seeker profile)")
    print(f"profile: {', '.join(k for k, v in OPERATIONAL_PROFILE.items() if v)}")
    print(f"{'category':11} {'clips':>5} {'hold':>6} {'clutter_frac':>13}   note")
    for cat in cats:
        files = sorted(glob.glob(os.path.join(clips_dir, f"IR_{cat}_*.mp4")))[:per_cat]
        if not files:
            continue
        rs = [eval_clip(p) for p in files]
        hold = statistics.mean(r["hold"] for r in rs)
        clut = statistics.mean(r["clutter_frac"] for r in rs)
        note = ("TARGET: want high hold, low clutter" if cat == "DRONE"
                else "DISTRACTOR: hold>0 = false-lock (no classifier => Gate G-D)")
        print(f"{cat:11} {len(rs):5} {hold:6.2f} {clut:13.2f}   {note}")
    print("\nItem #1 (detect+hold real target, not clutter): DRONE hold high & clutter low = PASS-on-proxy.")
    print("Caveats: 8-bit source (not Y16); acquisition basket = LOBL stand-in; distractor false-lock = Gate G-D.")


def main():
    ap = argparse.ArgumentParser(description="Gate G-B: detect-and-hold on real thermal clips")
    ap.add_argument("--clips", required=True, help="directory of IR_{DRONE,BIRD,...}_*.mp4 clips")
    ap.add_argument("--per-cat", type=int, default=20)
    a = ap.parse_args()
    run(a.clips, a.per_cat)


if __name__ == "__main__":
    main()
