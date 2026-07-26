"""replay-dump — write annotated frames so ingestion is visually observable.

The Phase 1 green criterion: replay a recorded clip (+ optional `.srt` telemetry),
overlay each frame with its time-synced pose (alt / attitude / fix status), and
write the frames to disk. This is the first place the whole ingestion path runs
end to end: `FileFrameSource` + `SrtFileSource` -> `align()` -> overlay.

The overlay is deliberately honest (DESIGN.md): it shows the `pose_status`
(OK / INTERPOLATED / EXTRAPOLATED / STALE / MISSING), prints "no fix" rather than
a fabricated 0,0, and shows attitude as "--" when the source can't supply it
(the DJI `.srt` case) rather than implying a level/north default.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from hades.confirm.confirmation import Tier
from hades.ingest.file_frame_source import FileFrameSource
from hades.ingest.srt_file_source import SrtFileSource
from hades.ingest.sync import AlignedFrame, PoseStatus, align
from hades.ingest.telemetry_source import Pose

if TYPE_CHECKING:
    from hades.detect.detector import Detector

#: Detection box outline color (bright green) — distinct from the pose-overlay text.
BOX_COLOR = (0, 255, 120)

#: Per-tier box color so display priority is visually unambiguous on the feed (Task 3.8).
#: A faint glimpse (contact) is dim; a corroborated/persistent survivor (strong) is hot.
TIER_COLORS: dict[Tier, tuple[int, int, int]] = {
    Tier.CONTACT: (120, 120, 120),  # dim grey — the faint one-frame glimpse, still visible
    Tier.CANDIDATE: (255, 200, 0),  # amber — promoted by persistence/confidence
    Tier.STRONG: (255, 40, 40),  # hot red — corroborated / very-persistent, dispatch-grade
}


def run_replay_dump(
    clip: str | Path,
    telemetry: str | Path | None,
    out_dir: str | Path,
    *,
    stride: int = 1,
    max_frames: int | None = None,
    detector: Detector | None = None,
    track: bool = False,
) -> int:
    """Replay `clip` (+ optional telemetry), dump annotated frames to `out_dir`.

    A real clip is thousands of frames; `stride` (write every Nth frame) and
    `max_frames` (cap total written) keep this observability tool from dumping
    multi-GB of PNGs. When `detector` is given, each frame is run through it and the
    detected boxes are drawn — the Phase 2 observable green criterion. When `track` is
    also set, detections are run through the tracker → confirmation pipeline and each
    contact's TRACK ID + display-priority TIER is drawn instead (the Phase 3 observable
    green criterion), the box color encoding the tier. Returns the number of frames
    written.
    """
    if stride < 1:
        raise ValueError("stride must be >= 1")
    if track and detector is None:
        raise ValueError("--track requires a detector (nothing to track without detections)")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    frames = FileFrameSource(clip)
    poses = list(SrtFileSource(telemetry)) if telemetry is not None else []

    # The tracker and confirmation rule are stateful across frames; one instance per run.
    tracker = _make_tracker() if track else None
    confirmer = _make_confirmer() if track else None

    count = 0
    for aligned in align(frames, poses):
        if aligned.frame.seq % stride != 0:
            continue
        if max_frames is not None and count >= max_frames:
            break
        img = Image.fromarray(aligned.frame.frame, mode="RGB")
        # Pose overlay first (opaque top bar), then detection/track boxes on top — so a box
        # near the top edge isn't occluded by the telemetry strip (review, minor).
        _draw_overlay(img, aligned)
        if detector is not None:
            detections = detector.detect(aligned.frame.frame)
            if track:
                _track_and_draw(img, detections, tracker, confirmer)
            else:
                _draw_detections(img, detections)
        img.save(out / f"frame_{aligned.frame.seq:05d}.png")
        count += 1
    return count


def _make_tracker():
    from hades.track.tracker import ByteTracker

    # min_hits=1 so a glimpse becomes a (low-tier) contact immediately — recall-first.
    return ByteTracker(min_hits=1)


def _make_confirmer():
    from hades.confirm.confirmation import Confirmation

    return Confirmation()


def _track_and_draw(img: Image.Image, detections, tracker, confirmer) -> None:
    """Track this frame's detections, promote tiers, and draw each contact's id + tier.

    Confirmation needs a world ground point per track; the observable CLI feeds it the
    track's box-center in image space as a DISPLAY-ONLY proxy (the .srt fixture has no
    attitude, so true georeferencing is unavailable here — the real world-clustering runs
    in the assembled service, Phase 4). The proxy still lets persistence promote a stable
    track through the tiers so the overlay is meaningful.
    """
    from hades.confirm.confirmation import Tier
    from hades.detect.detector import Detection
    from hades.locate.frame_gate import GateVerdict
    from hades.locate.projector import GroundPoint

    tracks = tracker.update(detections)
    # Build a proxy GroundPoint per confirmed track from its box-center (image px → fake
    # lat/lon at a tiny scale just so distinct tracks stay distinct in the proxy world).
    ground: dict[int, GroundPoint] = {}
    for t in tracks:
        x_min, y_min, x_max, y_max = t.box_xyxy
        cx, cy = (x_min + x_max) / 2.0, (y_min + y_max) / 2.0
        det = Detection(box_xyxy=t.box_xyxy, conf=t.conf)
        ground[t.track_id] = GroundPoint(
            detection=det, lat=cy * 1e-5, lon=cx * 1e-5, conf=t.conf,
            verdict=GateVerdict.PASS_UNVERIFIED,
        )
    tiers = confirmer.update(ground) if ground else {}

    draw = ImageDraw.Draw(img)
    for t in tracks:
        tier = tiers.get(t.track_id, Tier.CONTACT)
        color = TIER_COLORS[tier]
        x_min, y_min, x_max, y_max = t.box_xyxy
        draw.rectangle((x_min, y_min, x_max, y_max), outline=color, width=2)
        label = f"#{t.track_id} {tier.name.lower()}"
        ly = max(0, int(y_min) - 10)
        draw.text((int(x_min) + 1, ly), label, fill=color)


def make_detector(backend: str = "stub", *, model_path: str | Path | None = None, imgsz: int = 640):
    """Construct a detector by backend name for the `--detect` CLI path.

    `stub` is the deterministic, model-free default (CI/observability without weights);
    `onnx` and `coreml` load a real exported model and so require `model_path`.
    """
    if backend == "stub":
        from hades.detect.detector import StubDetector

        return StubDetector()
    if backend == "onnx":
        if model_path is None:
            raise ValueError("backend 'onnx' requires --model <path to .onnx>")
        from hades.detect.onnx_detector import OnnxDetector

        return OnnxDetector(model_path, imgsz=imgsz)
    if backend == "coreml":
        if model_path is None:
            raise ValueError("backend 'coreml' requires --model <path to .mlpackage>")
        from hades.detect.coreml_detector import CoreMLDetector

        return CoreMLDetector(model_path, imgsz=imgsz)
    raise ValueError(f"unknown detector backend {backend!r} (choose stub|onnx|coreml)")


def _draw_detections(img: Image.Image, detections) -> None:
    """Draw each detection box + confidence onto the frame (boxes in original pixels)."""
    draw = ImageDraw.Draw(img)
    for d in detections:
        x_min, y_min, x_max, y_max = d.box_xyxy
        draw.rectangle((x_min, y_min, x_max, y_max), outline=BOX_COLOR, width=2)
        label = f"{d.cls} {d.conf:.2f}"
        # Put the label just above the box, clamped into frame so it stays visible.
        ly = max(0, int(y_min) - 10)
        draw.text((int(x_min) + 1, ly), label, fill=BOX_COLOR)


def _fmt(value: float | None, suffix: str = "") -> str:
    return f"{value:.3f}{suffix}" if value is not None else "--"


def _pose_lines(aligned: AlignedFrame) -> list[str]:
    pose: Pose | None = aligned.pose
    status = aligned.pose_status.value
    if pose is None or aligned.pose_status is PoseStatus.MISSING:
        return [f"seq {aligned.frame.seq}  t={aligned.frame.timestamp:.3f}s", "POSE: no telemetry"]
    fix = (
        f"{pose.lat:.6f}, {pose.lon:.6f}"
        if pose.gps_valid and pose.lat is not None and pose.lon is not None
        else "no fix"
    )
    return [
        f"seq {aligned.frame.seq}  t={aligned.frame.timestamp:.3f}s  [{status}]",
        f"fix: {fix}",
        f"alt: {_fmt(pose.alt, ' m')} ({pose.alt_datum})",
        f"att: r={_fmt(pose.roll)} p={_fmt(pose.pitch)} y={_fmt(pose.yaw)}",
    ]


def _draw_overlay(img: Image.Image, aligned: AlignedFrame) -> None:
    draw = ImageDraw.Draw(img)
    lines = _pose_lines(aligned)
    # A translucent backing box keeps text legible over any frame content.
    line_h = 11
    box_h = line_h * len(lines) + 4
    box = Image.new("RGB", (img.width, min(box_h, img.height)), (0, 0, 0))
    img.paste(Image.blend(img.crop((0, 0, img.width, box.height)), box, 0.55), (0, 0))
    for i, line in enumerate(lines):
        draw.text((3, 2 + i * line_h), line, fill=(0, 255, 120))
