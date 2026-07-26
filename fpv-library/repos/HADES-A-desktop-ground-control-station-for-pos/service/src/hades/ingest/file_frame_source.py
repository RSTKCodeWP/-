"""FileFrameSource — decode a recorded video file into `Frame`s via PyAV.

The replay path for v1: recorded drone footage in, `Frame(frame, timestamp, seq)`
out. Software decode by default; VideoToolbox HW decode is requested only when the
clip is large enough to satisfy its minimum-dimension constraints (it rejects tiny
inputs), with software fallback. Dimensions are read per frame (no caching) so a
mid-stream resolution change flows through (Task 1.3). A frame that raises a libav
decode error is skipped, not propagated (tolerate corrupt frames / link loss).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import av
import numpy as np

from hades.ingest.frame_source import Frame, FrameSource

# VideoToolbox rejects small frames; only attempt HW decode at/above this size.
# Below it (fixtures, thumbnails) software decode is used directly.
_HW_MIN_DIM = 240


class FileFrameSource(FrameSource):
    """Yields `Frame`s decoded from a recorded video file.

    Args:
        path: video file to decode.
        hwaccel: if True, attempt VideoToolbox HW decode for large clips
            (with software fallback). Default True; harmless on small fixtures
            because the size gate keeps them on the software path.
    """

    def __init__(self, path: str | Path, hwaccel: bool = True):
        self.path = Path(path)
        self.hwaccel = hwaccel

    def _open(self) -> av.container.InputContainer:
        try:
            container = self._open_container()
        except av.FFmpegError as exc:
            raise ValueError(f"not a decodable video file: {self.path} ({exc})") from exc
        if not container.streams.video:
            container.close()
            raise ValueError(f"no video stream in {self.path}")
        return container

    def _open_container(self) -> av.container.InputContainer:
        if self.hwaccel:
            try:
                from av.codec.hwaccel import HWAccel, hwdevices_available

                if "videotoolbox" in hwdevices_available():
                    # Peek at the first stream's coded size to decide; VideoToolbox
                    # errors on tiny inputs, so gate on dimensions before using it.
                    with av.open(str(self.path)) as probe:
                        if not probe.streams.video:
                            raise av.FFmpegError(0, "no video stream")
                        vs = probe.streams.video[0]
                        big_enough = min(vs.width or 0, vs.height or 0) >= _HW_MIN_DIM
                    if big_enough:
                        hw = HWAccel(device_type="videotoolbox", allow_software_fallback=True)
                        return av.open(str(self.path), hwaccel=hw)
            except (ImportError, av.FFmpegError):
                pass  # fall through to software decode
        return av.open(str(self.path))

    def __iter__(self) -> Iterator[Frame]:
        seq = 0
        t0: float | None = None  # first frame's PTS — the video clock is zero-based to it
        with self._open() as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            rate = stream.guessed_rate or stream.average_rate or stream.base_rate
            packets = container.demux(stream)
            while True:
                try:
                    packet = next(packets)
                except StopIteration:
                    break
                except av.FFmpegError:
                    continue  # skip a corrupt packet, keep going
                try:
                    decoded = list(packet.decode())
                except av.FFmpegError:
                    continue  # skip a frame that fails to decode
                for av_frame in decoded:
                    # HW-decoded surfaces may not be rgb24; reformat defensively.
                    arr = av_frame.to_ndarray(format="rgb24")
                    ts = av_frame.time
                    if ts is None:
                        # No PTS — reconstruct from the frame rate (rare; remuxed/VFR).
                        ts = float(seq) / float(rate or 30)
                    # Zero-base to the first frame so this clock shares the .srt origin
                    # (the .srt timecode always starts at 0); a nonzero container
                    # start_time / edit-list offset must not shift telemetry alignment.
                    if t0 is None:
                        t0 = ts
                    yield Frame(
                        frame=np.ascontiguousarray(arr),
                        timestamp=float(ts - t0),
                        seq=seq,
                    )
                    seq += 1
