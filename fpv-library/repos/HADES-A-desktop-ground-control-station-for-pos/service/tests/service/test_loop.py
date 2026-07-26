"""Tests for the assembled service loop (Task 4.7; research gate §10).

The loop is the FIRST place the real pipeline runs end to end and emits the taskable
ContactRecord over WS: FrameSource + TelemetrySource -> align -> Detector -> Tracker ->
Projector -> Confirmation -> (Fuse on confirmed) -> two-channel messages. Per §10 it adds
exactly three deltas over the proven `replay_dump` chain: Fuse, the two-channel emit, and a
long-running loop.

The seams these tests guard (§10, ranked by risk):
1. frame_id ALIGNMENT across the two channels - the binary JPEG and the JSON detection/contact
   for a frame must carry the SAME frame_id (the join key the UI uses).
2. POSE-NONE / gate-reject - the .srt replay path is position-only (roll/pitch/yaw = None), so
   ray_to_ground RAISES on every frame. The loop MUST emit CUE-ONLY contacts, NOT crash and
   NOT drop the detection from view.
3. CPU-only with StubDetector (no CoreML import at module top).

The loop's core (`run_messages`) is a generator of per-frame outputs, decoupled from the WS
transport so it is fully testable offline + deterministic.
"""

from __future__ import annotations

from pathlib import Path

from hades.detect.detector import StubDetector
from hades.ws.schema import ContactRecord, DetectionMessage

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
CLIP = FIXTURES / "clip_2s.mp4"
SRT = FIXTURES / "clip_2s.srt"


def _loop():
    from hades.service.loop import ServiceLoop

    # A stub detector whose box sits well inside the frame so the tracker/confirmation run.
    return ServiceLoop(
        clip=CLIP,
        telemetry=SRT,
        detector=StubDetector(box_xyxy=(400.0, 300.0, 460.0, 420.0), conf=0.8),
    )


def test_does_not_import_coreml_at_module_top():
    # §10 mandate: loop.py must not import CoreML at module top (it must stay CPU-importable).
    import ast
    import inspect

    import hades.service.loop as lp

    tree = ast.parse(inspect.getsource(lp))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    assert not any("coreml" in m.lower() for m in imported)


def test_loop_runs_on_cpu_with_stub_detector_and_emits_messages():
    outputs = list(_loop().run_messages(max_frames=10))
    assert len(outputs) > 0
    for out in outputs:
        # Each frame produces a JPEG (binary channel) + a DetectionMessage (JSON channel).
        assert isinstance(out.jpeg, (bytes, bytearray)) and len(out.jpeg) > 0
        assert isinstance(out.detection_msg, DetectionMessage)
        assert all(isinstance(c, ContactRecord) for c in out.contacts)


def test_frame_id_alignment_across_both_channels():
    # The single highest seam risk (§10): the JPEG, the DetectionMessage, and every
    # ContactRecord for a frame must carry the SAME frame_id (the UI's join key).
    for out in _loop().run_messages(max_frames=10):
        assert out.detection_msg.frame_id == out.frame_id
        for c in out.contacts:
            assert c.frame_id == out.frame_id


def test_frame_ids_are_monotonic_and_match_source_seq():
    outs = list(_loop().run_messages(max_frames=10))
    ids = [o.frame_id for o in outs]
    assert ids == sorted(ids)  # monotonic, never desynced
    assert len(set(ids)) == len(ids)  # unique per frame


def test_position_only_srt_yields_cue_only_contacts_not_a_crash():
    # The .srt path is position-only -> ray_to_ground raises on every frame -> the contacts
    # must be CUE_ONLY (no fused coordinate), emitted, NOT a crash, NOT dropped from view.
    saw_contact = False
    for out in _loop().run_messages(max_frames=10):
        for c in out.contacts:
            saw_contact = True
            assert c.actionability_class == "CUE_ONLY"
    # The stub detector fires every frame, so at least one track should be promoted to a
    # contact record over a 10-frame window.
    assert saw_contact


def test_detection_message_carries_the_stub_box_every_frame():
    # Recall-first: the detection is ALWAYS on the JSON channel even when un-projectable.
    for out in _loop().run_messages(max_frames=5):
        assert len(out.detection_msg.boxes) >= 1


def test_age_frames_increments_on_no_telemetry_path():
    # On the link-loss path (telemetry=None) the pose is MISSING, so no FuseObservation is ever
    # buffered. age_frames must still count from a track's FIRST sighting, not re-stamp to the
    # current frame every frame (which pins age at 1 forever - a wrong emitted field).
    from hades.service.loop import ServiceLoop

    loop = ServiceLoop(
        clip=CLIP, telemetry=None,
        detector=StubDetector(box_xyxy=(400.0, 300.0, 460.0, 420.0), conf=0.8),
    )
    max_age = 0
    for out in loop.run_messages(max_frames=8):
        for c in out.contacts:
            max_age = max(max_age, c.age_frames)
    assert max_age > 1  # a persistent track ages past 1 even with no telemetry


def test_gate_rejected_frame_is_never_buffered_for_fusion():
    # Frame-gating invariant (DESIGN.md): a REJECT verdict means the frame is excluded from the
    # FUSED estimate, even if its ray still projects to a finite point. The loop must consult
    # gp.fusable before buffering an observation - otherwise a bad-geometry (oblique / high-
    # rate) frame can move a STRONG track's dispatch coordinate, the exact bug gating prevents.
    from hades.detect.detector import Detection
    from hades.locate.frame_gate import GateVerdict
    from hades.locate.projector import GroundPoint
    from hades.service.loop import _should_buffer

    det = Detection(box_xyxy=(10.0, 10.0, 50.0, 90.0), conf=0.8)
    # A REJECT point that DOES carry a finite coordinate (the dangerous case: projectable but
    # gate-excluded). _should_buffer must say NO despite the finite lat/lon.
    rejected = GroundPoint(
        detection=det, lat=40.0, lon=-74.0, conf=0.8, verdict=GateVerdict.REJECT,
    )
    assert _should_buffer(rejected) is False
    # A PASS_UNVERIFIED point with a finite coordinate (the .srt-with-attitude / live case) IS
    # buffered - the gate only excludes REJECT.
    passing = GroundPoint(
        detection=det, lat=40.0, lon=-74.0, conf=0.8, verdict=GateVerdict.PASS_UNVERIFIED,
    )
    assert _should_buffer(passing) is True
    # A passing verdict but NO coordinate (un-projectable) is not fusable either.
    no_coord = GroundPoint(
        detection=det, lat=None, lon=None, conf=0.8, verdict=GateVerdict.PASS,
    )
    assert _should_buffer(no_coord) is False


def test_cue_only_never_emits_a_zero_zero_null_island_pin():
    # A CUE-ONLY contact (no fused coordinate) must NOT carry a hard (0, 0): that plots at
    # Null Island and a coordinator reads it as a discovered survivor. The coordinate must be
    # None - the wire contract forces the UI to special-case "no fix", never trust a fake pin.
    for out in _loop().run_messages(max_frames=10):
        for c in out.contacts:
            if c.actionability_class == "CUE_ONLY":
                assert not (c.lat == 0.0 and c.lon == 0.0)
                assert c.lat is None and c.lon is None  # honest "no coordinate"
