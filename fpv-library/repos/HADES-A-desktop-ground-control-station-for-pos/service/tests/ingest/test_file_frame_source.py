"""Tests for FileFrameSource (PyAV, recorded video) — Task 1.2."""

from pathlib import Path

import numpy as np
import pytest

from hades.ingest.file_frame_source import FileFrameSource
from hades.ingest.frame_source import Frame, FrameSource

FIXTURES = Path(__file__).parent.parent / "fixtures"
CLIP = FIXTURES / "clip_2s.mp4"
OFFSET_CLIP = FIXTURES / "clip_offset.mp4"  # first-frame PTS is far from zero


def test_file_source_is_a_framesource():
    assert issubclass(FileFrameSource, FrameSource)


def test_yields_frames_from_fixture():
    frames = list(FileFrameSource(CLIP))
    assert len(frames) == 20  # fixture is 20 frames
    assert all(isinstance(f, Frame) for f in frames)


def test_frames_are_uint8_rgb_with_fixture_shape():
    frame = next(iter(FileFrameSource(CLIP)))
    assert frame.frame.dtype == np.uint8
    assert frame.frame.shape == (48, 64, 3)  # H, W, C for the 64x48 fixture


def test_timestamps_are_monotonic_nondecreasing():
    ts = [f.timestamp for f in FileFrameSource(CLIP)]
    assert ts[0] == 0.0
    assert all(b >= a for a, b in zip(ts, ts[1:]))
    assert ts[-1] > ts[0]


def test_seq_is_monotonic_from_zero():
    seqs = [f.seq for f in FileFrameSource(CLIP)]
    assert seqs == list(range(20))


def test_reiterable_opens_fresh_each_time():
    src = FileFrameSource(CLIP)
    first = list(src)
    second = list(src)
    assert len(first) == len(second) == 20


def test_not_a_video_file_raises_clean_error(tmp_path):
    bogus = tmp_path / "notvideo.txt"
    bogus.write_text("this is not a video")
    with pytest.raises(ValueError):
        list(FileFrameSource(bogus))


def test_srt_path_pointed_at_as_video_raises_clean_error():
    # Operator fat-fingers the .srt as the clip -> clean ValueError, not IndexError.
    with pytest.raises(ValueError):
        list(FileFrameSource(FIXTURES / "clip_2s.srt"))


def test_timestamps_are_zero_based_despite_container_start_offset():
    # The offset fixture has a first-frame PTS ~100s in. Timestamps must be
    # zero-based to the first frame so they share an origin with the .srt clock
    # (which always starts at 0) — otherwise every frame mis-aligns to telemetry.
    ts = [f.timestamp for f in FileFrameSource(OFFSET_CLIP)]
    assert ts[0] == pytest.approx(0.0, abs=1e-6)
    assert all(b >= a for a, b in zip(ts, ts[1:]))
