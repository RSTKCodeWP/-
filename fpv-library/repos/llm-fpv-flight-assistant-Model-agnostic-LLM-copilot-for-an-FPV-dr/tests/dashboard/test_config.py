from dashboard.config import DashboardSettings


def test_defaults():
    s = DashboardSettings()
    assert s.port == 8080
    assert s.safety_url.endswith("/ws")
    assert s.video_stream_url.endswith(".mjpg")
    assert s.video_health_url.endswith("/health")
