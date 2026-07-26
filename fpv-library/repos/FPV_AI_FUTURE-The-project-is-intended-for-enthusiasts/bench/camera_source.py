"""Live camera frame source — run the real seeker on a LIVE thermal feed (FT640 via a UVC grabber).

The recorded-clip bench (`video_source.py`) proves the pipeline; this streams the seeker on the LIVE
feed. Frames come through ffmpeg's `avfoundation` input (macOS), which addresses the MS2107 CVBS→USB
grabber by its device NAME ("USB Video") — robust vs OpenCV's flaky AVFoundation index ordering.
ffmpeg scales to the pipeline grid and pipes raw BGR24 frames on stdout; we read one frame's worth of
bytes per `read()`. ffmpeg's own log goes to a FILE (default /tmp/bench_live_ffmpeg.log) so a
wrong-device / format / permission failure is inspectable after the fact.

IMPORTANT: must be launched from a process that HAS camera (TCC) permission — i.e. the operator's own
terminal. A sandboxed/agent process is denied camera access by macOS and will get no frames.
"""
from __future__ import annotations

import shutil
import subprocess

import numpy as np


class CameraFrameSource:
    """A ``FrameSource`` (``read()``/``close()``) that streams a live UVC device via ffmpeg."""

    def __init__(self, device: str = "USB Video", *, width: int = 640, height: int = 512,
                 fps: float = 30.0, backend: str = "avfoundation",
                 log_path: str = "/tmp/bench_live_ffmpeg.log") -> None:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found on PATH — needed for the live camera source")
        self.width = int(width)
        self.height = int(height)
        self.fps = float(fps)
        self.frame_count = 0
        self.log_path = log_path
        self._nbytes = self.width * self.height * 3
        cmd = [
            "ffmpeg", "-loglevel", "info", "-nostdin", "-nostats",
            "-f", backend, "-framerate", str(int(fps)),
            "-i", f"{device}:none",                       # ":none" = video only, skip the grabber's audio
            "-vf", f"scale={self.width}:{self.height}",
            "-pix_fmt", "bgr24", "-f", "rawvideo", "-",
        ]
        # ffmpeg log -> a file we (or the agent) can read on the same host; NOT the terminal, so its
        # stderr can never back-pressure/stall the pipe.
        self._log = open(self.log_path, "wb")
        self._log.write(("[bench-live] $ " + " ".join(cmd) + "\n").encode())
        self._log.flush()
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=self._log, bufsize=self._nbytes)

    def read(self) -> "np.ndarray | None":
        out = self._proc.stdout
        if out is None:
            return None
        buf = bytearray()
        while len(buf) < self._nbytes:                    # exact-read: pipes can return partial chunks
            chunk = out.read(self._nbytes - len(buf))
            if not chunk:                                 # EOF -> ffmpeg exited (device/format/permission)
                return None
            buf += chunk
        self.frame_count += 1
        return np.frombuffer(bytes(buf), np.uint8).reshape(self.height, self.width, 3).copy()

    def alive(self) -> bool:
        return self._proc.poll() is None

    def close(self) -> None:
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        try:
            self._log.close()
        except Exception:
            pass
