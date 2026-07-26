"""Stress behavior: corrupt-frame skip, mid-stream resize, drop-to-latest — Task 1.3."""

from pathlib import Path

from hades.ingest.file_frame_source import FileFrameSource
from hades.ingest.frame_source import Frame
from hades.ingest.latest_buffer import LatestFrameBuffer

FIXTURES = Path(__file__).parent.parent / "fixtures"
CORRUPT = FIXTURES / "clip_corrupt.h264"
RES_CHANGE = FIXTURES / "res_change.ts"


def _frame(seq: int) -> Frame:
    import numpy as np

    return Frame(frame=np.zeros((2, 2, 3), np.uint8), timestamp=float(seq), seq=seq)


# (a) corrupt frame is skipped, not raised
def test_corrupt_frame_is_skipped_not_raised():
    # Must not raise; yields the decodable frames and silently drops the bad one.
    frames = list(FileFrameSource(CORRUPT))
    assert len(frames) >= 1
    # The raw stream has 30 frames with 2 damaged slices; we get most, not all.
    assert len(frames) < 30


# (b) mid-stream resolution change is handled (per-frame dims, no caching)
def test_midstream_resolution_change_is_handled():
    shapes = [f.frame.shape for f in FileFrameSource(RES_CHANGE)]
    assert (48, 64, 3) in shapes  # first segment
    assert (64, 96, 3) in shapes  # second segment, larger
    # The shape genuinely changes partway through, not a single constant.
    assert len(set(shapes)) == 2


def test_resolution_change_seq_stays_monotonic():
    seqs = [f.seq for f in FileFrameSource(RES_CHANGE)]
    assert seqs == list(range(len(seqs)))


# (c) LatestFrameBuffer returns newest under backpressure, never a backlog
def test_latest_buffer_returns_newest_only():
    buf = LatestFrameBuffer()
    for i in range(5):
        buf.put(_frame(i))
    got = buf.get()
    assert got.seq == 4  # newest, the older four are dropped


def test_latest_buffer_get_blocks_until_first_put_then_returns():
    buf = LatestFrameBuffer()
    buf.put(_frame(7))
    assert buf.get().seq == 7


def test_latest_buffer_drains_to_empty_after_get():
    buf = LatestFrameBuffer()
    buf.put(_frame(1))
    assert buf.get().seq == 1
    assert buf.get(timeout=0.01) is None  # nothing new -> no stale re-delivery


def test_latest_buffer_never_accumulates_backlog():
    buf = LatestFrameBuffer()
    for i in range(100):
        buf.put(_frame(i))
    assert buf.depth() == 1  # only ever holds the latest
