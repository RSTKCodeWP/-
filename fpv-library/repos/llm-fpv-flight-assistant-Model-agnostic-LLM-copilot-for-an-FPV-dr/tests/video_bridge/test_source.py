from video_bridge.frames import FrameBuffer
from video_bridge.source import on_image


class FakeImage:
    # duck-types the gz.msgs Image fields on_image() reads
    width = 2
    height = 2
    step = 6  # 2px * 3 channels
    data = bytes([0, 255, 0] * 4)  # 2x2 green


def test_on_image_writes_jpeg_to_buffer():
    buf = FrameBuffer()
    on_image(FakeImage(), buf, quality=70)
    jpeg = buf.latest()
    assert jpeg is not None and jpeg[:2] == b"\xff\xd8"
