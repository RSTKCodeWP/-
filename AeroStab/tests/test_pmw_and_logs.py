"""Tests for PMW3901 synthetic sensor and log analyzer."""

import time
from pathlib import Path

from aerostab.config import PmwConfig, load_config
from aerostab.log_analyzer import analyze_csv, write_report
from aerostab.sensors.pmw3901 import SyntheticPmw3901, create_pmw_sensor


def test_synthetic_pmw_velocity():
    s = SyntheticPmw3901(vx_m_s=0.2, vy_m_s=0.0, altitude_m=2.0)
    s.start()
    # Integrate discrete counts over a longer window (SPI sensors are quantized)
    t0 = time.monotonic()
    sx = sy = 0.0
    while time.monotonic() - t0 < 0.5:
        time.sleep(0.02)
        m = s.read_motion()
        vx, vy = s.velocity_m_s(m, 2.0)
        sx += vx * m.dt_s
        sy += vy * m.dt_s
    assert m.quality > 0.5
    # Expected displacement ≈ 0.2 m/s * 0.5 s = 0.1 m
    assert abs(sx - 0.1) < 0.05
    assert abs(sy) < 0.03


def test_create_pmw_disabled():
    cfg = PmwConfig(enabled=False)
    assert create_pmw_sensor(cfg) is None


def test_create_pmw_synthetic():
    cfg = PmwConfig(enabled=True, backend="synthetic")
    s = create_pmw_sensor(cfg, simulate=True)
    assert s is not None
    m = s.read_motion()
    assert m.dt_s > 0
    s.stop()


def test_log_analyzer(tmp_path):
    csv_path = tmp_path / "flight.csv"
    csv_path.write_text(
        "t,x,y,vx,vy,alt,quality,points,armed,nav_valid\n"
        "100.0,0,0,0,0,2,0.9,40,1,1\n"
        "101.0,1,0,1,0,2,0.8,35,1,1\n"
        "102.0,2,0,1,0,2,0.85,38,1,1\n"
    )
    report = analyze_csv(csv_path)
    assert report.samples == 3
    assert report.distance_m == 2.0
    assert report.duration_s == 2.0
    assert report.nav_valid_pct == 100.0
    out = write_report(report, tmp_path / "out.aerostab.json")
    assert out.exists()


def test_config_has_pmw():
    cfg = load_config()
    assert hasattr(cfg, "pmw3901")
    assert cfg.pmw3901.blend_weight > 0
