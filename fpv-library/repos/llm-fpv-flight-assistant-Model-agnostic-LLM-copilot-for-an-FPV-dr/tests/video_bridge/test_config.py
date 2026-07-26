from video_bridge.config import VideoBridgeSettings


def test_defaults():
    s = VideoBridgeSettings()
    assert s.port == 8082
    assert s.jpeg_quality == 80
    assert "image" in s.topic.lower() or s.topic == ""
