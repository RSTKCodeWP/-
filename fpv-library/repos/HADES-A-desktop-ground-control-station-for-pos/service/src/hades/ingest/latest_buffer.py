"""LatestFrameBuffer — drop-to-latest, single-slot frame handoff.

The display path must show the freshest frame and never accumulate a backlog
under backpressure (CLAUDE.md: "drop-to-latest, tolerate frame drops"). This
buffer holds exactly one frame — the newest. `put` overwrites; `get` consumes and
drains. A consumer that falls behind simply skips the frames it missed instead of
processing a growing queue (which would add latency without value).

Thread-safe: a producer thread `put`s while a consumer thread `get`s.
"""

from __future__ import annotations

import threading

from hades.ingest.frame_source import Frame


class LatestFrameBuffer:
    """Single-slot, newest-wins frame buffer for drop-to-latest delivery."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._latest: Frame | None = None

    def put(self, frame: Frame) -> None:
        """Store `frame` as the latest, dropping any unconsumed older frame."""
        with self._cond:
            self._latest = frame
            self._cond.notify()

    def get(self, timeout: float | None = None) -> Frame | None:
        """Return and clear the latest frame.

        Blocks until a frame is available or `timeout` (seconds) elapses. Returns
        `None` on timeout. Never re-delivers a frame it already returned (no stale
        re-delivery), so a slow consumer always advances to fresh data.
        """
        with self._cond:
            if self._latest is None:
                self._cond.wait(timeout)
            frame, self._latest = self._latest, None
            return frame

    def depth(self) -> int:
        """Number of buffered frames — always 0 or 1 (never a backlog)."""
        with self._lock:
            return 0 if self._latest is None else 1
