"""RTL path recorder tests."""

from aerostab.rtl_path import RtlPathRecorder


def test_rtl_records_while_armed():
    r = RtlPathRecorder(enabled=True, min_dist_m=0.1)
    r.on_arm(True)
    for i in range(10):
        r.sample(float(i) * 0.5, 0.0, 2.0, nav_valid=True)
    assert r.point_count >= 5
    assert r.path_length_m() > 1.0
    r.on_arm(False)
    assert not r.recording


def test_rtl_skips_when_nav_invalid():
    r = RtlPathRecorder(enabled=True, min_dist_m=0.1)
    r.on_arm(True)
    r.sample(1.0, 1.0, 2.0, nav_valid=False)
    assert r.point_count == 0
