"""FrameSource interface and a synthetic implementation.

A `FrameSource` is an iterable of `Frame`s — one responsibility: yield
`(frame, timestamp, seq)`. It knows nothing about detection or telemetry
(DESIGN.md §1). `seq` is the monotonic per-frame id used downstream to align
telemetry (the `frame_id` in CLAUDE.md).

Image convention (DESIGN.md §3.2): frames are HxWx3 uint8 in RGB, origin
top-left, +x right / +y down.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np


# eq=False -> identity eq/hash; a value-eq on the ndarray field would raise the
# ambiguous-truth ValueError and break hashing (frames are never value-compared).
@dataclass(frozen=True, eq=False)
class Frame:
    """One decoded frame.

    Attributes:
        frame: HxWx3 uint8 RGB image (DESIGN.md §3.2 axis convention).
        timestamp: presentation time in seconds (monotonic within a source).
        seq: monotonic frame id from 0; the key telemetry is aligned on.
    """

    frame: np.ndarray
    timestamp: float
    seq: int


class FrameSource(ABC):
    """Yields `Frame`s. Drop-to-latest and drop/resize tolerance live in impls."""

    @abstractmethod
    def __iter__(self) -> Iterator[Frame]:
        raise NotImplementedError


class SyntheticFrameSource(FrameSource):
    """Generates `n` deterministic gradient frames with monotonic timestamps.

    Used for offline tests and as the trivial FrameSource. Frames are a simple
    horizontal/vertical gradient that shifts per frame so consecutive frames
    differ (useful when a downstream consumer needs visibly distinct frames).
    """

    def __init__(self, n: int = 3, w: int = 64, h: int = 48, fps: float = 30.0):
        if n < 0:
            raise ValueError("n must be >= 0")
        if w <= 0 or h <= 0:
            raise ValueError("w and h must be positive")
        if fps <= 0:
            raise ValueError("fps must be positive")
        self.n = n
        self.w = w
        self.h = h
        self.fps = fps

    def __iter__(self) -> Iterator[Frame]:
        dt = 1.0 / self.fps
        col = np.linspace(0, 255, self.w, dtype=np.int32)[None, :]
        row = np.linspace(0, 255, self.h, dtype=np.int32)[:, None]
        for seq in range(self.n):
            arr = np.empty((self.h, self.w, 3), dtype=np.uint8)
            arr[:, :, 0] = ((col + seq * 8) % 256).astype(np.uint8)
            arr[:, :, 1] = (row % 256).astype(np.uint8)
            arr[:, :, 2] = np.uint8((seq * 12) % 256)
            yield Frame(frame=arr, timestamp=seq * dt, seq=seq)
