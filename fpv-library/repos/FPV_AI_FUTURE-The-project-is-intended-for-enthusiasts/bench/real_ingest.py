"""Run the REAL seeker on REAL thermal imagery and report honest metrics — the measurement bridge.

This is what the project actually needs (not another synthetic sim): point it at the QD115TB thermal
stream (RTSP) or a real thermal clip, and it runs the SAME detect->track pipeline the whole system is
built on, then reports whether it detects, holds lock, and how stable the centroid is. That is the
reality check no self-made synthetic target can give.

    QD115TB (Y16/stream):  python3 -m fpv_ai.bench.real_ingest --source "rtsp://192.168.1.100:554/stream0"
    FT640 via MS2107 grab: python3 -m fpv_ai.bench.real_ingest --source /dev/video0 --invert   # or --source 0
    real clip file:        python3 -m fpv_ai.bench.real_ingest --source thermal_drone.mp4 --annotate /tmp/real.mp4
    raw .npy frame dir:    python3 -m fpv_ai.bench.real_ingest --source /path/to/frames_dir

HONEST CAVEAT: 8-bit colormapped display video (MJPEG/RTSP preview, downloaded clips) is lossy and
NOT radiometric — here luma is mapped to pseudo-counts so the detector can run, but the DEFINITIVE
test needs the raw Y16 the QD115TB can emit. Metrics on 8-bit sources are indicative, not final;
this is stated in the report so nobody mistakes an 8-bit pass for a validated seeker.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import statistics
import time

import cv2
import numpy as np

from fpv.guidance.pipeline import SeekerGuidancePipeline
from fpv.seeker.geometry import ft640_intrinsics


def to_counts(frame, invert: bool, auto_polarity: bool = False) -> tuple[np.ndarray, bool]:
    """Map an arbitrary decoded frame to a uint16 'counts' image the detector expects.

    Returns (frame_u16, is_raw16).  Raw single-channel 16-bit (true Y16) is used as-is; 8-bit or
    colour display frames get luma mapped into a plausible counts range (hot = high). `invert` for
    black-hot sources; `auto_polarity` decides white-hot/black-hot from the frame itself (below).
    The mapping for 8-bit is documented as lossy/non-radiometric in the report.
    """
    if frame.ndim == 2 and frame.dtype == np.uint16:
        return frame, True                                # true radiometric Y16 — best case
    if frame.ndim == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    gray = gray.astype(np.float64)
    if gray.max() > 255:                                  # 16-bit-ish single channel not typed u16
        gray = gray / gray.max() * 255.0
    flip = invert
    if auto_polarity and not invert:
        # Per-frame polarity check that matches what the detector actually keys on: a COMPACT
        # extreme. A global skew/percentile test is fooled by a hot, structured background (a
        # compact target is a fraction of a percent of pixels, the same order as background
        # structure). So compare the peak WHITE-top-hat response (bright compact features) against
        # the peak BLACK-hat response (dark compact features): top-hat removes the background and
        # any gradient, leaving only compact structure, so whichever polarity produces the stronger
        # compact peak is the target polarity. If the DARK compact peak clearly dominates, the
        # source is black-hot -> flip so the detector sees hot=high. The 1.5x margin biases an
        # ambiguous scene (no clear compact target either way) to white-hot, the safe default for a
        # hot-target seeker. Computed on a downsample (polarity is global) to stay Pi-cheap. This
        # removes the operator footgun where a wrong manual --invert silently breaks the lock.
        small = cv2.resize(gray, (160, 128), interpolation=cv2.INTER_AREA).astype(np.uint8)
        se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        white_peak = float(cv2.morphologyEx(small, cv2.MORPH_TOPHAT, se).max())
        black_peak = float(cv2.morphologyEx(small, cv2.MORPH_BLACKHAT, se).max())
        flip = black_peak > white_peak * 1.5
    if flip:
        gray = 255.0 - gray
    u16 = (4096.0 + gray * 42.0).clip(0, 65535).astype(np.uint16)   # luma -> pseudo-counts (hot=high)
    return u16, False


def _open_capture(source: str) -> "cv2.VideoCapture":
    """Open a cv2.VideoCapture for a live V4L2 grabber, an RTSP URL, or a video file.

    A *live* source is a UVC/V4L2 device: the MS2107 CVBS->USB grabber carrying the FT640 shows up as
    ``/dev/video0`` on the Zynq PS Linux. cv2 needs the integer index (or the V4L2 backend) for those;
    a bare device path handed to the default backend is treated as a filename and silently fails. So:
      * ``"0"``, ``"1"`` ...        -> live camera/grabber by index (default backend; works on Mac too)
      * ``"/dev/videoN"``          -> V4L2 device node (explicit V4L2 backend, index fallback)
      * everything else            -> RTSP URL / video file (unchanged)
    """
    if source.isdigit():
        return cv2.VideoCapture(int(source))
    if source.startswith("/dev/video"):
        cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
        if not cap.isOpened():                        # some OpenCV builds only take the index form
            cap.release()
            tail = source[len("/dev/video"):]
            if tail.isdigit():
                cap = cv2.VideoCapture(int(tail), cv2.CAP_V4L2)
        return cap
    return cv2.VideoCapture(source)


def _frames(source: str):
    """Yield decoded frames from a live V4L2 grabber, an RTSP URL, a video file, or a dir of .npy/.png."""
    if os.path.isdir(source):
        files = sorted(glob.glob(os.path.join(source, "*.npy")) + glob.glob(os.path.join(source, "*.png")))
        for f in files:
            yield np.load(f) if f.endswith(".npy") else cv2.imread(f, cv2.IMREAD_UNCHANGED)
        return
    cap = _open_capture(source)
    if not cap.isOpened():
        raise RuntimeError(f"could not open source: {source!r} (live /dev/videoN or index, RTSP URL, video file, frame dir)")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        yield frame
    cap.release()


def run(source: str, *, max_frames: int = 900, invert: bool = False, annotate: str | None = None,
        fps: float = 30.0, auto_polarity: bool = False, pipe_kwargs: dict | None = None) -> dict:
    # Default to the BARE pipeline: the 2026-07-21 real-data config sweep showed region-CFAR +
    # sky-basket did NOT help these clips (and hurt several: DRONE_001 jitter 0.07 -> 83 px) while
    # ~doubling the per-frame cost, so the headless measurement no longer silently enables them.
    pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics(), **(pipe_kwargs or {}))
    writer = None
    states, blob_counts, snrs, locked_centroids, is_raw = [], [], [], [], None
    dt = 1.0 / max(fps, 1.0)
    n = 0
    for frame in _frames(source):
        if frame is None:
            continue
        u16, raw = to_counts(frame, invert, auto_polarity=auto_polarity)
        is_raw = raw if is_raw is None else is_raw
        if u16.shape != (512, 640):
            u16 = cv2.resize(u16, (640, 512), interpolation=cv2.INTER_AREA)
        out = pipe.step(now=n * dt, frame_u16=u16, gyro_omega_xyz=(0, 0, 0), dt=dt)
        states.append(out.tracking_state)
        blob_counts.append(len(out.blobs))
        if out.snr is not None:
            snrs.append(float(out.snr))
        if "LOCK" in out.tracking_state and out.centroid_px is not None:
            locked_centroids.append((n, out.centroid_px))
        if annotate:
            d8 = np.clip((u16.astype(np.float64) - 4050.0) / 26.0, 0, 255).astype("uint8")
            disp = cv2.applyColorMap(d8, cv2.COLORMAP_INFERNO)
            col = (110, 240, 120) if "LOCK" in out.tracking_state else (90, 200, 250)
            if out.bbox:
                x, y, w, h = out.bbox
                cv2.rectangle(disp, (x, y), (x + w, y + h), col, 2)
            if out.centroid_px and out.centroid_px[0] == out.centroid_px[0]:
                cv2.drawMarker(disp, (int(out.centroid_px[0]), int(out.centroid_px[1])), col, cv2.MARKER_CROSS, 22, 2)
            cv2.putText(disp, f"{out.tracking_state}  blobs {len(out.blobs)}", (8, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1, cv2.LINE_AA)
            if writer is None:
                writer = cv2.VideoWriter(annotate, cv2.VideoWriter_fourcc(*"mp4v"), fps, (640, 512))
            writer.write(disp)
        n += 1
        if n >= max_frames:
            break
    if writer:
        writer.release()

    # ---- honest metrics ----
    det_rate = (sum(1 for c in blob_counts if c > 0) / n) if n else 0.0
    # longest contiguous LOCKED run + centroid stability within it
    best_len = best_start = cur = cur_start = 0
    for i, s in enumerate(states):
        if "LOCK" in s:
            if cur == 0:
                cur_start = i
            cur += 1
            if cur > best_len:
                best_len, best_start = cur, cur_start
        else:
            cur = 0
    lock_win = [c for (idx, c) in locked_centroids if best_start <= idx < best_start + best_len]
    cx_std = statistics.pstdev([c[0] for c in lock_win]) if len(lock_win) > 1 else float("nan")
    cy_std = statistics.pstdev([c[1] for c in lock_win]) if len(lock_win) > 1 else float("nan")
    # Per-frame centroid JUMP within the lock — the honest jitter metric. Sigma over the whole lock
    # conflates a target legitimately traversing the frame (a crossing aircraft moves tens of px, all
    # tracked correctly) with real tracking error. A hop is a sudden large single-frame displacement.
    # We report median/p95/max jump, the count of >15 px jumps (candidate association hops), and the
    # net traversal — so a large sigma that is really smooth travel is visible as such, not a defect.
    jumps = [math.hypot(lock_win[i][0] - lock_win[i - 1][0], lock_win[i][1] - lock_win[i - 1][1])
             for i in range(1, len(lock_win))]
    if jumps:
        js = sorted(jumps)
        jump_med = statistics.median(jumps)
        jump_p95 = js[min(len(js) - 1, int(0.95 * len(js)))]
        jump_max = max(jumps)
        hops = sum(1 for j in jumps if j > 15.0)
        travel = math.hypot(lock_win[-1][0] - lock_win[0][0], lock_win[-1][1] - lock_win[0][1])
    else:
        jump_med = jump_p95 = jump_max = travel = float("nan")
        hops = 0
    return dict(frames=n, raw_y16=bool(is_raw), det_rate=det_rate,
                longest_lock_frames=best_len, longest_lock_s=best_len / fps,
                centroid_std_px=(cx_std, cy_std),
                jump_px=(jump_med, jump_p95, jump_max), hops_gt15=hops, net_travel_px=travel,
                mean_blobs=(statistics.mean(blob_counts) if blob_counts else 0.0),
                max_blobs=(max(blob_counts) if blob_counts else 0),
                mean_snr=(statistics.mean(snrs) if snrs else float("nan")),
                annotate=annotate if writer is not None else None)


def _overlay(u16, out, name: str, n: int, cfg_label: str, basket_y: float | None):
    d8 = np.clip((u16.astype(np.float64) - 4050.0) / 26.0, 0, 255).astype("uint8")
    disp = cv2.applyColorMap(d8, cv2.COLORMAP_INFERNO)
    if basket_y is not None:                              # acquisition basket edge (sky region)
        cv2.line(disp, (0, int(basket_y)), (639, int(basket_y)), (120, 120, 120), 1)
    for b in out.blobs:                                  # every detected blob (perceptron candidates)
        x, y = int(b.centroid_px[0]), int(b.centroid_px[1])
        cv2.drawMarker(disp, (x, y), (255, 90, 255), cv2.MARKER_TILTED_CROSS, 7, 1)
    locked = "LOCK" in out.tracking_state
    col = (110, 240, 120) if locked else (90, 200, 250)
    if out.bbox:
        x, y, w, h = out.bbox
        cv2.rectangle(disp, (x, y), (x + w, y + h), col, 2)
    if out.centroid_px and out.centroid_px[0] == out.centroid_px[0]:
        cv2.drawMarker(disp, (int(out.centroid_px[0]), int(out.centroid_px[1])), col, cv2.MARKER_CROSS, 24, 2)
    snr = f"{out.snr:.0f}" if out.snr else "-"
    for i, ln in enumerate([f"{name}  f{n}", f"state {out.tracking_state}",
                            f"blobs {len(out.blobs)}  SNR {snr}", cfg_label]):
        cv2.putText(disp, ln, (8, 20 + 17 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (235, 235, 235), 1, cv2.LINE_AA)
    cv2.putText(disp, "space=pause  n=next  r=restart  q=quit", (8, 505),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)
    return disp


def live(source: str, *, invert: bool = False, fps: float = 30.0,
         region_cfar: bool = True, sky_basket: bool = True) -> None:
    """Native window: play a real thermal clip and watch the perceptron (detect+track) run live.

    Controls: space = pause, n = next clip (if source is a dir), r = restart clip, q = quit.
    Defaults to the config validated on real data (region-CFAR + sky acquisition basket), which
    puts the lock on the drone instead of ground clutter.
    """
    clips = (sorted(glob.glob(os.path.join(source, "*.mp4"))) if os.path.isdir(source) else [source])
    if not clips:
        raise RuntimeError(f"no clips at {source!r}")
    kw: dict = {}
    if region_cfar:
        kw.update(region_bands=4, graduated_k=True)
    basket_y = None
    if sky_basket:
        kw["acquisition_box"] = (0.0, 0.0, 640.0, 270.0); basket_y = 270.0
    label = f"cfg: {'region-CFAR ' if region_cfar else ''}{'sky-basket' if sky_basket else 'full-frame'}"
    win = "perceptron - real thermal"
    idx = 0
    while 0 <= idx < len(clips):
        clip = clips[idx]; name = os.path.basename(clip)
        pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics(), **kw)
        cap = _open_capture(clip); n = 0; paused = False; disp = None
        while True:
            if not paused:
                ok, frame = cap.read()
                if not ok:
                    break
                u16, _ = to_counts(frame, invert)
                if u16.shape != (512, 640):
                    u16 = cv2.resize(u16, (640, 512), interpolation=cv2.INTER_AREA)
                out = pipe.step(now=n / fps, frame_u16=u16, gyro_omega_xyz=(0, 0, 0), dt=1 / fps)
                disp = _overlay(u16, out, name, n, label, basket_y)
                n += 1
            if disp is not None:
                cv2.imshow(win, disp)
            k = cv2.waitKey(max(1, int(1000 / fps))) & 0xFF
            if k == ord("q"):
                cap.release(); cv2.destroyAllWindows(); return
            if k == ord(" "):
                paused = not paused
            elif k == ord("n"):
                break
            elif k == ord("r"):
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0); n = 0
                pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics(), **kw)
        cap.release(); idx += 1
    cv2.destroyAllWindows()


def record(source: str, out_dir: str, *, max_frames: int = 1800) -> int:
    """Capture RAW frames + capture timestamps from a live source to disk (the 'press record' bridge).

    Saves each decoded frame losslessly as ``fNNNNNN.npy`` (native dtype -- Y16 stays uint16) plus a
    ``manifest.json`` with per-frame ``t_capture_ns`` (monotonic). The result replays through the same
    pipeline via ``--source <out_dir>`` (a dir of .npy). This is what makes the real-sensor
    transition "press record", not new code: point --source at the QD115TB RTSP and record, then
    replay/measure/re-train offline against the SAME `detect_frame`/pipeline.
    """
    os.makedirs(out_dir, exist_ok=True)
    manifest = {"source": source, "recorded_utc": time.time(), "frames": []}
    n = 0
    for frame in _frames(source):
        if frame is None:
            continue
        t_ns = time.monotonic_ns()                    # true capture time on a live source
        fn = f"f{n:06d}.npy"
        np.save(os.path.join(out_dir, fn), frame)     # RAW frame, native dtype (Y16 -> uint16)
        manifest["frames"].append({"frame": n, "t_capture_ns": t_ns, "file": fn,
                                   "shape": list(frame.shape), "dtype": str(frame.dtype)})
        n += 1
        if n >= max_frames:
            break
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    print(f"recorded {n} raw frames + manifest -> {out_dir}  (replay: --source {out_dir})")
    return n


def _report(source: str, r: dict) -> None:
    print(f"REAL-DATA seeker measurement  ({source})")
    print(f"  source type          : {'RAW Y16 (radiometric)' if r['raw_y16'] else '8-bit display (lossy, NON-radiometric — indicative only)'}")
    print(f"  frames processed     : {r['frames']}")
    print(f"  detection rate       : {r['det_rate']*100:5.1f} %   (frames with >=1 blob)")
    print(f"  longest held LOCK    : {r['longest_lock_frames']} frames ({r['longest_lock_s']:.2f} s)")
    cxs, cys = r['centroid_std_px']
    print(f"  centroid spread      : sigma_x {cxs:.2f} px, sigma_y {cys:.2f} px  (INCLUDES target traversal — not error)")
    jm, jp, jx = r.get('jump_px', (float('nan'),) * 3)
    print(f"  tracking jitter      : per-frame jump med {jm:.2f} / p95 {jp:.2f} / max {jx:.2f} px  "
          f"({r.get('hops_gt15', 0)} hops >15 px; net travel {r.get('net_travel_px', float('nan')):.1f} px)")
    print(f"  blob count mean/max  : {r['mean_blobs']:.2f} / {r['max_blobs']}   (>1 sustained = clutter/false-alarm risk)")
    print(f"  mean blob SNR        : {r['mean_snr']:.1f}")
    if r['annotate']:
        print(f"  annotated review     : {r['annotate']}")
    if not r['raw_y16']:
        print("  NOTE: 8-bit colormapped source — this is INDICATIVE. The definitive test is raw Y16 from the QD115TB.")


def main():
    ap = argparse.ArgumentParser(description="Run the real seeker on real thermal imagery (QD115TB/file)")
    ap.add_argument("--source", required=True,
                    help="live grabber (/dev/video0 or index 0), RTSP URL, video file, or dir of .npy/.png frames")
    ap.add_argument("--max-frames", type=int, default=900)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--invert", action="store_true", help="black-hot source (invert luma)")
    ap.add_argument("--auto-polarity", action="store_true",
                    help="auto-detect white-hot/black-hot per frame (defaults hot=high; ignores a wrong --invert)")
    ap.add_argument("--region-cfar", action="store_true",
                    help="enable look-down region-adaptive CFAR (headless). Off by default: the real-data "
                         "sweep showed it did not help these clips and ~doubled per-frame cost")
    ap.add_argument("--annotate", default=None, help="write an annotated MP4 here for eyeball review")
    ap.add_argument("--live", action="store_true", help="open a native window and watch the perceptron run live")
    ap.add_argument("--no-cfar", action="store_true", help="disable region-adaptive CFAR in --live")
    ap.add_argument("--no-basket", action="store_true", help="disable the sky acquisition basket in --live")
    ap.add_argument("--record", default=None, help="capture RAW frames + timestamps to this dir (press-record bridge)")
    a = ap.parse_args()
    if a.record:
        record(a.source, a.record, max_frames=a.max_frames)
    elif a.live:
        live(a.source, invert=a.invert, fps=a.fps,
             region_cfar=not a.no_cfar, sky_basket=not a.no_basket)
    else:
        pipe_kwargs = dict(region_bands=4, graduated_k=True) if a.region_cfar else None
        _report(a.source, run(a.source, max_frames=a.max_frames, invert=a.invert,
                              annotate=a.annotate, fps=a.fps,
                              auto_polarity=a.auto_polarity, pipe_kwargs=pipe_kwargs))


if __name__ == "__main__":
    main()
