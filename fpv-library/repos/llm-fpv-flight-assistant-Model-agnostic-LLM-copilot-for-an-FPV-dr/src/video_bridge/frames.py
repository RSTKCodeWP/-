import io
import time

from PIL import Image


def encode_jpeg(raw: bytes, width: int, height: int, channels: int, quality: int = 80) -> bytes:
    """Encode raw RGB/RGBA pixel bytes to JPEG."""
    mode = "RGBA" if channels == 4 else "RGB"
    img = Image.frombytes(mode, (width, height), raw)
    if mode == "RGBA":
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality)
    return out.getvalue()


class FrameBuffer:
    """Holds the latest JPEG frame and how old it is (thread-safe enough for one writer)."""

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._jpeg: bytes | None = None
        self._ts: float | None = None

    def set(self, jpeg: bytes) -> None:
        self._jpeg = jpeg
        self._ts = self._clock()

    def latest(self) -> bytes | None:
        return self._jpeg

    def age_s(self) -> float | None:
        return None if self._ts is None else self._clock() - self._ts

    def is_fresh(self, max_age_s: float) -> bool:
        age = self.age_s()
        return age is not None and age <= max_age_s
