from drone_yolo_fpv.metrics import FPSMeter


def test_fps_meter_summary_has_expected_keys():
    meter = FPSMeter()
    meter.add_latency(10.0)
    meter.add_latency(20.0)
    meter.add_latency(30.0)
    summary = meter.summary()

    assert summary["frames_measured"] == 3
    assert summary["mean_latency_ms"] == 20.0
    assert "average_fps" in summary
    assert "p50_latency_ms" in summary
    assert "p95_latency_ms" in summary
