from fastapi.testclient import TestClient
from video_bridge.frames import FrameBuffer
from video_bridge.mjpeg import mjpeg_chunk, build_video_app


def test_mjpeg_chunk_has_multipart_headers():
    chunk = mjpeg_chunk(b"\xff\xd8data")
    assert b"--frame" in chunk
    assert b"Content-Type: image/jpeg" in chunk
    assert chunk.rstrip().endswith(b"data")


def test_health_reports_unhealthy_when_no_frames():
    app = build_video_app(FrameBuffer(), max_age_s=1.0)
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_health_reports_healthy_with_fresh_frame():
    clock = {"t": 0.0}
    buf = FrameBuffer(clock=lambda: clock["t"])
    buf.set(b"\xff\xd8frame")
    app = build_video_app(buf, max_age_s=1.0)
    r = TestClient(app).get("/health")
    assert r.json()["ok"] is True
    assert r.json()["age_s"] == 0.0
