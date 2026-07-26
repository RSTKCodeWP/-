"""Service loop - assembles the pipeline and emits over two WS channels (Task 4.7).

This is the FIRST place the real pipeline runs end to end and emits the taskable
`ContactRecord`. Per the research gate (§10), it adds exactly THREE deltas over the proven
`cli/replay_dump` chain (which already wires FrameSource + SrtFileSource -> align -> Detector
-> Tracker -> Confirmation on CPU):

  1. Fuse on confirmed tracks (the real Projector + Fuser, not replay_dump's display proxy),
  2. the two-channel emit (binary JPEG frames + JSON detections/contacts), and
  3. a long-running loop.

Design for testability (§10): the core `run_messages()` is a GENERATOR of per-frame
`LoopOutput` (frame_id, jpeg, DetectionMessage, list[ContactRecord]), decoupled from the WS
transport - so it runs fully offline + deterministic with a `StubDetector` on CPU. The thin
`serve()` wrapper pushes those outputs onto the two localhost WS channels. CoreML is NEVER
imported at module top; the detector is injected (the ANE path stays a manual/hardware run).

The single highest seam risk is frame_id ALIGNMENT across the two channels: the JPEG, the
DetectionMessage, and every ContactRecord for a frame all carry the SAME frame_id (the join
key the UI uses). The `.srt` replay path is position-only, so `ray_to_ground` raises on every
frame and every contact is CUE-ONLY - the loop catches that and emits the contact (recall-
first), it does NOT crash and does NOT drop the detection from view.
"""

from __future__ import annotations

import io
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

import numpy as np
from PIL import Image

from hades.confirm.confirmation import Confirmation, Tier
from hades.ingest.file_frame_source import FileFrameSource
from hades.ingest.srt_file_source import SrtFileSource
from hades.ingest.sync import align
from hades.locate.camera_model import CameraModel
from hades.locate.error_model import SensorErrorModel
from hades.locate.fuse import FuseObservation, Fuser
from hades.locate.projector import GroundPoint, Projector
from hades.track.tracker import ByteTracker
from hades.ws.schema import ContactRecord, DetectionMessage

if TYPE_CHECKING:
    from hades.detect.detector import Detector
    from hades.ingest.telemetry_source import Pose

# How many recent per-track observations the fuser keeps (the fusion buffer ~ a few seconds).
_FUSE_WINDOW = 60


@dataclass
class LoopOutput:
    """One frame's emit: the binary JPEG + the JSON DetectionMessage + any ContactRecords.
    All three carry the SAME `frame_id` - the cross-channel join key (§10)."""

    frame_id: int
    timestamp: float
    jpeg: bytes
    detection_msg: DetectionMessage
    contacts: list[ContactRecord]


@dataclass
class _TrackBuf:
    """Per-track rolling fusion buffer + bookkeeping for the contact record."""

    obs: deque = field(default_factory=lambda: deque(maxlen=_FUSE_WINDOW))
    first_frame: int = -1  # -1 = never seen; stamped on first sighting (independent of obs)
    last_conf: float = 0.0


class ServiceLoop:
    """Assembles the pipeline over a recorded clip (+ telemetry) and produces per-frame emits.

    The detector is INJECTED (CPU-only `StubDetector` in tests, ONNX/CoreML in the real run) so
    the loop never imports a hardware backend. Camera + error model default to the v1 config.
    """

    def __init__(
        self,
        clip: str | Path,
        telemetry: str | Path | None,
        detector: Detector,
        *,
        camera: CameraModel | None = None,
        ground_elev: float = 0.0,
        error_model: SensorErrorModel | None = None,
    ) -> None:
        self.clip = clip
        self.telemetry = telemetry
        self.detector = detector
        self.camera = camera or CameraModel(fx=1400.0, fy=1400.0, cx=960.0, cy=540.0, mount="nadir")
        self.projector = Projector(camera=self.camera, ground_elev=ground_elev)
        self.fuser = Fuser(error_model=error_model or SensorErrorModel())
        self.tracker = ByteTracker(min_hits=1)
        self.confirmer = Confirmation()
        self._bufs: dict[int, _TrackBuf] = defaultdict(_TrackBuf)

    def run_messages(self, *, max_frames: int | None = None) -> Iterator[LoopOutput]:
        """Yield one `LoopOutput` per frame: the assembled-pipeline result, aligned by frame_id.

        Drop-to-latest / back-pressure is the WS transport's job (`serve`); this core runs the
        pipeline once per aligned frame and produces well-formed, frame_id-aligned messages.
        """
        frames = FileFrameSource(self.clip)
        poses = list(SrtFileSource(self.telemetry)) if self.telemetry is not None else []

        count = 0
        for aligned in align(frames, poses):
            if max_frames is not None and count >= max_frames:
                break
            frame_id = aligned.frame.seq
            ts = aligned.frame.timestamp
            detections = self.detector.detect(aligned.frame.frame)
            pose = aligned.pose

            # Detector path: detections are ALWAYS emitted on the JSON channel (recall-first).
            det_msg = DetectionMessage.from_detections(
                frame_id=frame_id, timestamp=ts, detections=detections
            )

            # Track -> per-track GroundPoint (real Projector, not the display proxy).
            tracks = self.tracker.update(detections)
            ground: dict[int, GroundPoint] = {}
            for t in tracks:
                gp = (
                    self.projector.project([_as_detection(t)], pose)[0]
                    if pose is not None
                    else _cue_only_ground_point(t)
                )
                ground[t.track_id] = gp
                buf = self._bufs[t.track_id]
                if buf.first_frame < 0:  # stamp age origin on FIRST sighting, even with no pose
                    buf.first_frame = frame_id
                buf.last_conf = t.conf
                # Buffer for fusion ONLY a gate-fusable observation. A REJECT frame (bad
                # geometry) whose ray still projects to a finite point must NOT enter the fused
                # estimate - the gate governs fusion-eligibility, never visibility (the
                # detection still surfaces via `ground`/the DetectionMessage above).
                if pose is not None and _should_buffer(gp):
                    buf.obs.append(_fuse_obs(t, pose, self.camera))

            tiers = self.confirmer.update(ground) if ground else {}

            contacts = self._contacts_for(frame_id, tracks, ground, tiers)
            yield LoopOutput(
                frame_id=frame_id,
                timestamp=ts,
                jpeg=_encode_jpeg(aligned.frame.frame),
                detection_msg=det_msg,
                contacts=contacts,
            )
            count += 1

    # --- contact-record assembly ----------------------------------------------------

    def _contacts_for(
        self,
        frame_id: int,
        tracks,
        ground: dict[int, GroundPoint],
        tiers: dict[int, Tier],
    ) -> list[ContactRecord]:
        out: list[ContactRecord] = []
        for t in tracks:
            tier = tiers.get(t.track_id, Tier.CONTACT)
            buf = self._bufs[t.track_id]
            age = max(1, frame_id - buf.first_frame + 1)
            gp = ground.get(t.track_id)

            # Fuse ONLY confirmed (STRONG) tracks that have fusable observations; otherwise the
            # contact is CUE-ONLY (visible, no fused coordinate) - the position-only .srt path.
            fused = None
            if tier is Tier.STRONG and buf.obs:
                fused = self.fuser.fuse(list(buf.obs))

            if fused is not None:
                out.append(
                    ContactRecord.from_fused(
                        frame_id=frame_id,
                        track_id=t.track_id,
                        coord=fused.coord,
                        r95_m=fused.r95_m,
                        actionability_class=fused.actionability_class,
                        semi_major_m=fused.semi_major_m,
                        semi_minor_m=fused.semi_minor_m,
                        orientation_deg=fused.orientation_deg,
                        convergence=fused.convergence,
                        heading_limited=fused.heading_limited,
                        aspect_spread_deg=fused.aspect_spread_deg,
                        moving_suspected=fused.moving_suspected,
                        mc_reject_fraction=0.0,
                        priority_tier=tier.name.lower(),
                        detection_conf=buf.last_conf,
                        localization_conf=_loc_conf(fused.r95_m),
                        age_frames=age,
                    )
                )
            else:
                out.append(_cue_only_record(frame_id, t, tier, age, buf.last_conf, gp))
        return out

    def promote(self, track_id: int) -> ContactRecord | None:
        """Operator-promote → on-demand Fuse (Task 5.10 / M6 — the human-as-confirmer path).

        Force Fuse+Quantify on a track's buffered observations REGARDLESS of its
        auto-confirmation tier: the operator says "localize THIS one now," exercising the whole
        rationale for the Projector/Fuse split. Returns the refined ContactRecord, or `None` if
        the track is unknown. A track with no fusable geometry (the position-only .srt path)
        yields an honest CUE_ONLY (the promote can't fabricate a fix that the data can't give).
        """
        buf = self._bufs.get(track_id)
        if buf is None:
            return None  # unknown track — nothing to promote

        last_frame = buf.first_frame if buf.first_frame >= 0 else 0
        age = max(1, last_frame - buf.first_frame + 1)

        fused = self.fuser.fuse(list(buf.obs)) if buf.obs else None
        if fused is None:
            # no fusable geometry → honest CUE_ONLY (no track object here; build directly)
            return _cue_only_for_id(track_id, age, buf.last_conf)

        return ContactRecord.from_fused(
            frame_id=last_frame,
            track_id=track_id,
            coord=fused.coord,
            r95_m=fused.r95_m,
            actionability_class=fused.actionability_class,
            semi_major_m=fused.semi_major_m,
            semi_minor_m=fused.semi_minor_m,
            orientation_deg=fused.orientation_deg,
            convergence=fused.convergence,
            heading_limited=fused.heading_limited,
            aspect_spread_deg=fused.aspect_spread_deg,
            moving_suspected=fused.moving_suspected,
            mc_reject_fraction=0.0,
            # operator-promoted → display as a candidate (operator-confirmed, not auto-STRONG)
            priority_tier="candidate",
            detection_conf=buf.last_conf,
            localization_conf=_loc_conf(fused.r95_m),
            age_frames=age,
        )


# --- small adapters / helpers -------------------------------------------------------


def _should_buffer(gp: GroundPoint) -> bool:
    """Whether a GroundPoint is eligible to enter the fusion buffer (DESIGN.md frame-gating).

    Exactly `gp.fusable`: the gate verdict is not REJECT AND a finite coordinate exists. A
    gate-REJECT frame is excluded from the FUSED estimate even when its ray projects to a
    finite point - otherwise bad-geometry frames contaminate the dispatch coordinate. The
    detection still surfaces (visibility is never gated); only fusion eligibility is."""
    return gp.fusable


def _as_detection(track):
    from hades.detect.detector import Detection

    return Detection(box_xyxy=track.box_xyxy, conf=track.conf, cls="person")


def _fuse_obs(track, pose: Pose, camera: CameraModel) -> FuseObservation:
    x_min, _y_min, x_max, y_max = track.box_xyxy
    bottom_center = ((x_min + x_max) / 2.0, y_max)  # feet-on-ground (§3.2)
    return FuseObservation(pose=pose, camera=camera, pixel=bottom_center)


def _cue_only_ground_point(track) -> GroundPoint:
    from hades.locate.frame_gate import GateVerdict

    return GroundPoint(
        detection=_as_detection(track), lat=None, lon=None, conf=track.conf,
        verdict=GateVerdict.PASS_UNVERIFIED, gate_reasons=("no_pose",),
    )


def _cue_only_record(
    frame_id: int, track, tier: Tier, age: int, conf: float, gp: GroundPoint | None
) -> ContactRecord:
    """A visible contact with no fused coordinate (position-only pose / un-projectable).

    Recall-first: the detection still surfaces. The coordinate falls back to the projected
    point if one exists (a gated-but-finite point), else None (NOT (0, 0), which would plot at
    Null Island and read as a discovered survivor) flagged CUE_ONLY with a huge radius - the
    operator sees a cue, never a false-precision pin."""
    has_coord = gp is not None and gp.lat is not None and gp.lon is not None
    lat = gp.lat if has_coord else None
    lon = gp.lon if has_coord else None
    return ContactRecord(
        frame_id=frame_id,
        track_id=track.track_id,
        lat=lat,
        lon=lon,
        r95_m=200.0,  # the CUE floor - an area cue, not a point
        actionability_class="CUE_ONLY",
        semi_major_m=200.0,
        semi_minor_m=200.0,
        orientation_deg=0.0,
        priority_tier=tier.name.lower(),
        convergence_state="CONVERGING",
        heading_limited=True,
        aspect_spread_deg=0.0,
        detection_conf=conf,
        localization_conf=0.0,
        mc_reject_fraction=1.0 if not has_coord else 0.0,
        moving_suspected=False,
        age_frames=age,
    )


def _cue_only_for_id(track_id: int, age: int, conf: float) -> ContactRecord:
    """A CUE_ONLY record built from a track_id alone (the operator-promote path, which has no
    live track object). Same honest no-fix shape as `_cue_only_record`: null coordinate, CUE
    floor radius, never a Null-Island pin."""
    return ContactRecord(
        frame_id=0,
        track_id=track_id,
        lat=None,
        lon=None,
        r95_m=200.0,
        actionability_class="CUE_ONLY",
        semi_major_m=200.0,
        semi_minor_m=200.0,
        orientation_deg=0.0,
        priority_tier="candidate",
        convergence_state="CONVERGING",
        heading_limited=True,
        aspect_spread_deg=0.0,
        detection_conf=conf,
        localization_conf=0.0,
        mc_reject_fraction=1.0,
        moving_suspected=False,
        age_frames=age,
    )


def _loc_conf(r95_m: float) -> float:
    """Localization confidence bound to the floor-inclusive R95 (research gate §2): a tight
    fused estimate is high-confidence, a big-radius one is low. Maps R95 in [1, 100] m -> [1, 0]."""
    return float(np.clip(1.0 - (r95_m - 1.0) / 99.0, 0.0, 1.0))


def _encode_jpeg(frame: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(frame, mode="RGB").save(buf, format="JPEG", quality=80)
    return buf.getvalue()


async def serve(
    loop: ServiceLoop,
    *,
    binary_port: int = 8765,
    json_port: int = 8766,
    fps: float = 30.0,
    max_frames: int | None = None,
) -> None:
    """Push the loop's per-frame outputs onto the two localhost WS channels.

    Binary channel (`binary_port`): JPEG frames. JSON channel (`json_port`): one
    `DetectionMessage` then any `ContactRecord`s per frame, frame_id-aligned to the JPEG.
    Drop-to-latest: a slow consumer never blocks the pipeline - the newest frame wins. Kept
    deliberately thin; the testable logic is in `run_messages`.
    """
    import asyncio

    import websockets  # local import: only the serving path needs the dependency

    # Each client gets a size-1 latest-wins queue drained by its OWN writer task. The pump
    # NEVER awaits a client's socket - it does a non-blocking put that OVERWRITES any stale
    # frame. So a slow / stalled consumer just keeps missing frames (drop-to-latest) while the
    # pump advances unimpeded - the honest implementation of the §10 120 ms-budget claim, and
    # the fix for the prior `await ws.send()` that could back-pressure the whole pipeline.
    binary_clients: set = set()
    json_clients: set = set()

    async def _register(ws, pool):
        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        pool.add(queue)
        writer = asyncio.create_task(_writer(ws, queue))
        try:
            await ws.wait_closed()
        finally:
            pool.discard(queue)
            writer.cancel()

    async def _register_json(ws):
        # The JSON channel is bidirectional: the pump WRITES detections/contacts to this client
        # (via its drop-to-latest queue + writer), and the client may SEND commands back. v1
        # command: operator-promote → on-demand Fuse (Task 5.10 / M6). The refined record is
        # sent straight to THIS client (not the broadcast queue) so the request/response pairs.
        import json as _json

        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        json_clients.add(queue)
        writer = asyncio.create_task(_writer(ws, queue))
        try:
            async for message in ws:  # inbound command loop; ends when the client disconnects
                if not isinstance(message, str):
                    continue
                try:
                    cmd = _json.loads(message)
                except Exception:
                    continue
                if cmd.get("type") == "promote":
                    tid = cmd.get("track_id")
                    if isinstance(tid, int):
                        rec = loop.promote(tid)
                        if rec is not None:
                            try:
                                await ws.send(rec.model_dump_json())  # direct reply to requester
                            except Exception:
                                break
        except Exception:
            pass  # client errored/closed; finally cleans up
        finally:
            json_clients.discard(queue)
            writer.cancel()

    async def _writer(ws, queue: asyncio.Queue):
        # The ONLY coroutine that awaits this client's socket. If the client stalls, this task
        # blocks here - never the pump - and the queue simply overwrites while it waits. Each
        # queue item is ONE frame's payloads (a list), so drop-to-latest drops a WHOLE frame
        # atomically: a frame's DetectionMessage + its ContactRecords are never split apart.
        try:
            while True:
                payloads = await queue.get()
                for payload in payloads:
                    await ws.send(payload)
        except Exception:
            return  # client gone / errored; its writer ends, _register cleans up the queue

    def _publish(pool, payloads):
        # Non-blocking latest-wins: drop the stale frame if the queue is full, then enqueue the
        # new frame's payload group. The pump never awaits a consumer.
        for queue in list(pool):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(payloads)
            except asyncio.QueueFull:
                pass  # raced with the writer draining; the next frame wins anyway

    async def _pump():
        period = 1.0 / fps
        for out in loop.run_messages(max_frames=max_frames):
            _publish(binary_clients, [out.jpeg])
            json_payloads = [out.detection_msg.model_dump_json()]
            json_payloads += [c.model_dump_json() for c in out.contacts]
            _publish(json_clients, json_payloads)
            await asyncio.sleep(period)  # pace the feed; never blocks on a consumer

    async with (
        websockets.serve(lambda ws: _register(ws, binary_clients), "127.0.0.1", binary_port),
        websockets.serve(_register_json, "127.0.0.1", json_port),
    ):
        await _pump()
