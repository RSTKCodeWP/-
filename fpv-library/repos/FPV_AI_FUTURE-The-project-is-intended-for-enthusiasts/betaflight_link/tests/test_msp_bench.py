"""Tests for the MSP telemetry bench read helpers (hardware-free via MockFcChannel)."""

from __future__ import annotations

from fpv_ai.betaflight_link.msp_bench import check_connectivity, read_attitude, read_imu
from fpv_ai.betaflight_link.serial_link import MockFcChannel, MspLink


def test_check_connectivity():
    link = MspLink.for_bench(MockFcChannel())
    assert check_connectivity(link) == (0, 1, 46)


def test_read_imu_gyro_and_accel():
    fc = MockFcChannel(gyro=(11, -22, 33), accel=(1, 2, 3))
    link = MspLink.for_bench(fc)
    imu = read_imu(link)
    assert imu is not None
    assert imu.gyro == (11, -22, 33) and imu.acc == (1, 2, 3)


def test_read_attitude():
    fc = MockFcChannel(attitude_ddeg=(300, -150, 45))   # roll 30.0, pitch -15.0 deg, yaw 45
    link = MspLink.for_bench(fc)
    att = read_attitude(link)
    assert att is not None
    assert round(att.roll_rad * 57.29577951308232, 1) == 30.0
    assert round(att.pitch_rad * 57.29577951308232, 1) == -15.0


def test_silent_link_returns_none():
    fc = MockFcChannel()
    fc.link_up = False                                   # FC/link dead
    link = MspLink.for_bench(fc)
    assert check_connectivity(link) is None
    assert read_imu(link) is None
    assert read_attitude(link) is None
