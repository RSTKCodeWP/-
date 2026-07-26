"""Tests for track/contact overlay in replay-dump (Task 3.8 — the Phase 3 green criterion).

The observable end state: `replay-dump --track` runs detector → tracker → (projector →
confirmation) and draws each contact's TRACK ID + display-priority TIER, with the box
color encoding the tier (contact → candidate → strong) so priority is visually distinct.
Determinism on CI is via a moving-box stub detector (no model, no ANE); the fixture has no
real people, so the test asserts the tracking/tier OVERLAY PATH works, not accuracy.
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from hades.cli.main import main
from hades.cli.replay_dump import TIER_COLORS, run_replay_dump
from hades.confirm.confirmation import Tier
from hades.detect.detector import Detection, Detector

FIXTURES = Path(__file__).parent.parent / "fixtures"
CLIP = FIXTURES / "clip_2s.mp4"
SRT = FIXTURES / "clip_2s.srt"


class _MovingStub(Detector):
    """A detector that returns one box drifting linearly — gives the tracker a stable ID."""

    def __init__(self) -> None:
        self._k = 0

    def detect(self, frame):
        x = 20.0 + self._k * 1.0
        self._k += 1
        h, w = frame.shape[:2]
        x = min(x, w - 30.0)
        return [Detection(box_xyxy=(x, 20.0, x + 20.0, 60.0), conf=0.9)]


def test_track_draws_id_and_tier_on_each_frame(tmp_path):
    n = run_replay_dump(CLIP, SRT, tmp_path, detector=_MovingStub(), track=True)
    assert n == 20
    # Frames are dumped with a track overlay; later frames (persistent track) reach a
    # higher tier than the first glimpse, so a brighter tier color appears.
    last = np.asarray(Image.open(tmp_path / "frame_00019.png").convert("RGB"))
    strong = TIER_COLORS[Tier.STRONG]
    # The strong-tier color should appear once the track has persisted to the last frame.
    matches = np.all(np.abs(last.astype(int) - np.array(strong)) <= 30, axis=-1)
    assert matches.any()


def test_track_overlay_differs_from_detect_only(tmp_path):
    detect = tmp_path / "detect"
    track = tmp_path / "track"
    run_replay_dump(CLIP, SRT, detect, detector=_MovingStub())
    run_replay_dump(CLIP, SRT, track, detector=_MovingStub(), track=True)
    a = np.asarray(Image.open(detect / "frame_00019.png").convert("RGB"))
    b = np.asarray(Image.open(track / "frame_00019.png").convert("RGB"))
    assert not np.array_equal(a, b)  # the id/tier label adds pixels


def test_track_requires_a_detector(tmp_path):
    # Tracking with no detector is meaningless — fail clearly rather than dump untracked.
    with pytest.raises(ValueError):
        run_replay_dump(CLIP, SRT, tmp_path, detector=None, track=True)


def test_tier_colors_cover_all_tiers():
    # Every tier must have a distinct color so priority is unambiguous on the feed.
    assert set(TIER_COLORS) == set(Tier)
    assert len(set(TIER_COLORS.values())) == len(Tier)  # all distinct


def test_cli_track_flag_dispatches(tmp_path):
    rc = main(
        [
            "replay-dump", str(CLIP),
            "--telemetry", str(SRT),
            "--out", str(tmp_path),
            "--detect",
            "--track",
        ]
    )
    assert rc == 0
    assert len(list(tmp_path.glob("*.png"))) == 20
