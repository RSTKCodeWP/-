"""Operator-promote → on-demand Fuse (impl-plan Task 5.10 / M6 — the human-as-confirmer path).

The Projector/Fuse split exists precisely so the operator can force a localization on a track
the auto-confirmation rule did NOT promote to STRONG. `ServiceLoop.promote(track_id)` runs
Fuse+Quantify on that track's buffered observations regardless of tier and returns the refined
ContactRecord (or an honest CUE_ONLY when the track has no fusable geometry, e.g. the
position-only .srt path). CPU-only with the StubDetector; no CoreML import.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from hades.detect.detector import StubDetector
from hades.ingest.telemetry_source import Pose
from hades.locate.camera_model import CameraModel
from hades.locate.fuse import FuseObservation

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
CLIP = FIXTURES / "clip_2s.mp4"
SRT = FIXTURES / "clip_2s.srt"


def _loop():
    from hades.service.loop import ServiceLoop

    return ServiceLoop(
        clip=CLIP,
        telemetry=SRT,
        detector=StubDetector(box_xyxy=(400.0, 300.0, 460.0, 420.0), conf=0.8),
    )


def _full_pose(yaw: float) -> Pose:
    """A full-attitude pose (the live/CRSF path) — fusable, unlike the position-only .srt."""
    return Pose(
        lat=30.0,
        lon=-88.0,
        alt=30.0,
        roll=0.0,
        pitch=-30.0,  # looking forward-down
        yaw=yaw,
        t=0.0,
        alt_datum="REL_TAKEOFF",
    )


def test_promote_unknown_track_returns_none():
    loop = _loop()
    assert loop.promote(99999) is None


def test_promote_a_position_only_track_returns_honest_cue_only():
    # Run a few frames so a track exists; the .srt is position-only → no fusable obs → the
    # operator's promote can't fabricate a fix, it returns CUE_ONLY (honest, not a crash).
    loop = _loop()
    track_ids = set()
    for out in loop.run_messages(max_frames=8):
        for c in out.contacts:
            track_ids.add(c.track_id)
    assert track_ids, "the stub detector should have produced at least one track"

    tid = next(iter(track_ids))
    rec = loop.promote(tid)
    assert rec is not None
    assert rec.track_id == tid
    assert rec.actionability_class == "CUE_ONLY"  # no geometry to fuse → honest cue
    assert rec.lat is None and rec.lon is None


def test_promote_forces_a_real_fuse_on_a_NON_strong_track_with_fusable_obs():
    # The M6 rationale: a track the auto-rule left as a mere candidate (NOT STRONG) gets a
    # REAL fused coordinate when the operator promotes it. Seed the track buffer with full-
    # attitude observations (the live path), leave its tier unset (defaults to CONTACT), and
    # promote → a fused record with a real coordinate, even though it was never auto-confirmed.
    loop = _loop()
    cam = CameraModel(fx=1400.0, fy=1400.0, cx=960.0, cy=540.0, mount="nadir")
    tid = 7
    buf = loop._bufs[tid]
    buf.first_frame = 0
    buf.last_conf = 0.9
    # several frames of fusable geometry from slightly different yaws (aspect diversity)
    for k, yaw in enumerate((10.0, 12.0, 14.0, 16.0, 18.0)):
        buf.obs.append(FuseObservation(pose=_full_pose(yaw), camera=cam, pixel=(960.0, 700.0)))

    rec = loop.promote(tid)
    assert rec is not None
    assert rec.track_id == tid
    # a real on-demand fix: a coordinate exists and it is NOT the CUE-only floor
    assert rec.lat is not None and rec.lon is not None
    assert rec.actionability_class in {"PINPOINT", "SWEEP", "AREA"}
    assert rec.r95_m < 200.0  # tighter than the CUE floor — fusion actually ran
    assert np.isfinite(rec.lat) and np.isfinite(rec.lon)
