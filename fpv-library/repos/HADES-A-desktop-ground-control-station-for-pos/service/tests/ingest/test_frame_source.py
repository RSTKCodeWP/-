"""Tests for the FrameSource interface and SyntheticFrameSource (Task 1.1)."""

import numpy as np
import pytest

from hades.ingest.frame_source import FrameSource, SyntheticFrameSource


def test_synthetic_source_yields_timestamped_frames():
    src = SyntheticFrameSource(n=3, w=64, h=48)
    frames = list(src)
    assert len(frames) == 3
    assert frames[0].seq == 0
    assert frames[0].frame.shape == (48, 64, 3)
    assert frames[1].timestamp > frames[0].timestamp


def test_synthetic_source_seq_is_monotonic_from_zero():
    frames = list(SyntheticFrameSource(n=5, w=32, h=32))
    assert [f.seq for f in frames] == [0, 1, 2, 3, 4]


def test_synthetic_frames_are_uint8_rgb():
    frame = next(iter(SyntheticFrameSource(n=1, w=16, h=8))).frame
    assert frame.dtype == np.uint8
    assert frame.shape == (8, 16, 3)


def test_synthetic_source_is_a_framesource():
    assert issubclass(SyntheticFrameSource, FrameSource)


def test_framesource_is_abstract():
    with pytest.raises(TypeError):
        FrameSource()  # ABC with abstract __iter__ — cannot instantiate


def test_frame_is_hashable_despite_ndarray_field():
    # frozen dataclass holding an ndarray must not blow up on hash/eq (identity).
    frame = next(iter(SyntheticFrameSource(n=1, w=8, h=8)))
    assert hash(frame) is not None
    assert frame == frame  # identity eq, no ambiguous-truth ValueError
    assert len({frame, frame}) == 1
    other = next(iter(SyntheticFrameSource(n=1, w=8, h=8)))
    assert frame != other  # distinct instances
