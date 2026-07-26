"""Pi5 hardware-layer tests — the calibration/mapping (the part that must be right) is unit-tested."""
from __future__ import annotations

from seeker_core.contracts import (
    ActuatorChannel, ActuatorCommand, ActuatorFrame, Authority, Provenance,
)
from seeker_core.pi5_io import Pi5Config, Pi5Imu, Pi5Servos, imu_raw_to_si, rad_to_pulse_us


def test_imu_calibration_remaps_scales_signs():
    cfg = Pi5Config(gyro_scale_rps=0.001, accel_scale_mps2=0.01,
                    gyro_axis_map=(1, 0, 2), gyro_sign=(1.0, -1.0, 1.0))
    gyro, accel = imu_raw_to_si((10, 20, 30, 40, 50, 60), cfg)
    assert abs(gyro[0] - 0.020) < 1e-9        # body x = raw[1]*scale
    assert abs(gyro[1] + 0.010) < 1e-9        # body y = -raw[0]*scale
    assert abs(gyro[2] - 0.030) < 1e-9
    assert abs(accel[0] - 0.40) < 1e-9


def test_servo_pulse_mapping_and_clamp():
    cfg = Pi5Config(servo_us_center=1500.0, servo_us_per_rad=1000.0, servo_us_min=1000.0, servo_us_max=2000.0)
    assert rad_to_pulse_us(0.0, 1.0, cfg) == 1500.0
    assert rad_to_pulse_us(0.2, 1.0, cfg) == 1700.0
    assert rad_to_pulse_us(0.2, -1.0, cfg) == 1300.0
    assert rad_to_pulse_us(5.0, 1.0, cfg) == 2000.0        # clamped to the mechanical range


def test_pi5_servos_writes_only_the_two_gimbal_servos():
    cfg = Pi5Config()
    calls: list[tuple[int, float]] = []
    servos = Pi5Servos(cfg, lambda ch, us: calls.append((ch, us)))
    frame = ActuatorFrame(commands=(
        ActuatorCommand(ActuatorChannel.GIMBAL_AZ, 0.1, 0),
        ActuatorCommand(ActuatorChannel.GIMBAL_EL, -0.1, 0),
        ActuatorCommand(ActuatorChannel.AIRFRAME_THROTTLE, 0.6, 0),   # MUST be ignored on the bench
        ActuatorCommand(ActuatorChannel.AIRFRAME_YAW, 0.5, 0)),
        authority=Authority(True, True, False, "committed"), provenance=Provenance("t", 0))
    servos.write(frame)
    chans = sorted(c[0] for c in calls)
    assert chans == sorted((cfg.pan_channel, cfg.tilt_channel)) and len(calls) == 2   # no motor ever driven


def test_pi5_imu_produces_real_flagged_sample():
    imu = Pi5Imu(Pi5Config(), lambda: (0, 0, 100, 0, 0, 2048))
    s = imu.read(123)
    assert s.provenance.synthetic is False and s.provenance.t_capture_ns == 123 and len(s.gyro_rps) == 3


def test_pca9685_tick_computation():
    from seeker_core.pi5_io import pca9685_ticks
    assert pca9685_ticks(1500, 50) == 307        # 1500us @ 50Hz -> 1500*4096*50/1e6
    assert pca9685_ticks(1000, 50) == 205
    assert pca9685_ticks(2000, 50) == 410
    assert pca9685_ticks(1e9, 50) <= 0x0FFF       # 12-bit clamp


def test_esp32_servo_wire_format_and_writer():
    from seeker_core.pi5_io import esp32_servo_cmd, make_esp32_serial_servo_writer
    assert esp32_servo_cmd(0, 1500.4) == b"S 0 1500\n"
    assert esp32_servo_cmd(1, 1723.9) == b"S 1 1724\n"

    class _FakeSerial:
        def __init__(self): self.sent: list[bytes] = []
        def write(self, b): self.sent.append(b)

    fake = _FakeSerial()
    write_us = make_esp32_serial_servo_writer(serial_obj=fake)
    write_us(0, 1400.0)
    write_us(1, 1600.0)
    assert fake.sent == [b"S 0 1400\n", b"S 1 1600\n"]
