"""Tests for the MSP byte transport (Block-3 S4). Hardware-free: uses MockFcChannel."""

from __future__ import annotations

import pytest

from fpv_ai.betaflight_link import msp_codec as mc
from fpv_ai.betaflight_link.serial_link import MockFcChannel, MspLink


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _channels(*, throttle: int = 1000, aux1: int = 1000, roll: int = 1500,
              pitch: int = 1500, yaw: int = 1500) -> list[int]:
    named = {"roll": roll, "pitch": pitch, "yaw": yaw, "throttle": throttle,
             "aux1": aux1, "aux2": 1000, "aux3": 1000, "aux4": 1000}
    return mc.channels_to_list(named)


def test_bench_link_is_not_hardware():
    link = MspLink.for_bench(MockFcChannel())
    assert link.is_hardware is False


def test_set_raw_rc_reaches_mock_fc_in_order():
    fc = MockFcChannel()
    link = MspLink.for_bench(fc)
    channels = _channels(throttle=1234, aux1=1700, roll=1600, pitch=1400, yaw=1500)
    link.send_set_raw_rc(channels)
    assert fc.last_rc == channels
    # spot-check positional meaning matches RC_CHANNEL_ORDER
    order = mc.RC_CHANNEL_ORDER
    assert fc.last_rc[order.index("throttle")] == 1234
    assert fc.last_rc[order.index("roll")] == 1600


def test_set_raw_rc_gets_ack_frame():
    fc = MockFcChannel()
    link = MspLink.for_bench(fc)
    link.send_set_raw_rc(_channels())
    frames = link.poll()
    assert len(frames) == 1
    assert frames[0].function == mc.MSP_SET_RAW_RC
    assert frames[0].direction == mc.DIR_FROM_FC
    assert frames[0].payload == b""


def test_imu_telemetry_round_trip():
    fc = MockFcChannel(gyro=(100, -200, 300), accel=(1, 2, 3), mag=(-4, -5, -6))
    link = MspLink.for_bench(fc)
    link.request(mc.MSP_RAW_IMU)
    frames = link.poll()
    assert len(frames) == 1
    imu = mc.decode_raw_imu(frames[0].payload)
    assert imu.gyro == (100, -200, 300)
    assert imu.acc == (1, 2, 3)
    assert imu.mag == (-4, -5, -6)


def test_attitude_telemetry_round_trip():
    fc = MockFcChannel(attitude_ddeg=(450, -100, 90))
    link = MspLink.for_bench(fc)
    link.request(mc.MSP_ATTITUDE)
    frames = link.poll()
    att = mc.decode_attitude(frames[0].payload)
    assert att.roll_rad == pytest.approx(45.0 * 0.017453292519943295, rel=1e-9)


def test_stats_and_watchdog_clock():
    clock = FakeClock()
    fc = MockFcChannel()
    link = MspLink.for_bench(fc, clock=clock)
    assert link.time_since_rx_s() is None  # nothing received yet

    clock.t = 1.0
    link.send_set_raw_rc(_channels())
    assert link.stats.frames_sent == 1
    assert link.stats.last_tx_s == 1.0

    clock.t = 1.2
    link.poll()  # receives the ack
    assert link.stats.frames_received == 1
    assert link.stats.last_rx_s == 1.2

    clock.t = 1.7
    assert link.time_since_rx_s() == pytest.approx(0.5)


def test_open_serial_refuses_without_authorization():
    # the UART gate fires BEFORE any pyserial import, so this is hardware-free
    with pytest.raises(PermissionError):
        MspLink.open_serial("/dev/ttyAMA0", hardware_authorized=False)


def test_mock_fc_arm_gate():
    fc = MockFcChannel()
    link = MspLink.for_bench(fc)
    # AUX1 high but throttle high -> Betaflight refuses to arm
    link.send_set_raw_rc(_channels(throttle=1500, aux1=1800))
    assert fc.armed is False
    # AUX1 high AND throttle low -> arms
    link.send_set_raw_rc(_channels(throttle=1000, aux1=1800))
    assert fc.armed is True
    # AUX1 low -> always disarms
    link.send_set_raw_rc(_channels(throttle=1000, aux1=1000))
    assert fc.armed is False


def test_repeated_commands_loop():
    fc = MockFcChannel()
    link = MspLink.for_bench(fc)
    for i in range(50):
        link.send_set_raw_rc(_channels(throttle=1000 + i))
        link.poll()
    assert fc.rc_frames_received == 50
    assert fc.last_rc[mc.RC_CHANNEL_ORDER.index("throttle")] == 1049
