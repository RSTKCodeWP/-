import io
from PIL import Image
from video_bridge.frames import encode_jpeg, FrameBuffer


def test_encode_jpeg_returns_valid_jpeg():
    # 2x2 RGB red square as raw bytes
    raw = bytes([255, 0, 0] * 4)
    jpeg = encode_jpeg(raw, width=2, height=2, channels=3, quality=80)
    assert jpeg[:2] == b"\xff\xd8"          # JPEG SOI marker
    img = Image.open(io.BytesIO(jpeg))
    assert img.size == (2, 2)


def test_frame_buffer_tracks_age():
    clock = {"t": 100.0}
    buf = FrameBuffer(clock=lambda: clock["t"])
    assert buf.latest() is None
    assert buf.is_fresh(max_age_s=1.0) is False
    buf.set(b"\xff\xd8jpeg")
    assert buf.latest() == b"\xff\xd8jpeg"
    assert buf.is_fresh(max_age_s=1.0) is True
    clock["t"] = 102.0
    assert buf.age_s() == 2.0
    assert buf.is_fresh(max_age_s=1.0) is False
