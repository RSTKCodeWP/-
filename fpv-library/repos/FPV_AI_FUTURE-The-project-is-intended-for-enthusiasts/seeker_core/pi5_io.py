"""Raspberry Pi 5 hardware layer for the seeker-head bench — camera / IMU / servos as seeker_core adapters.

The VALUABLE, TESTABLE parts live here: axis/scale/sign calibration for the head IMU, rad→servo-pulse
mapping, and the FT640-frame→contract conversion (with the 8-bit→pseudo-counts map). The ~10 lines of
chip-specific bus I/O are small HOOKS you pass in (`raw_imu_read`, `servo_write_us`) with reference
factories for common parts. Everything imports safely off-Pi (cv2/smbus imported lazily), and there are
sim fallbacks so the bench app runs on this machine before hardware.

Wiring assumptions (edit Pi5Config): IMU on I2C, 2 servos via PCA9685 (I2C) or GPIO PWM, FT640 via a USB
grabber at /dev/videoN. NEVER wire motors to this bench — only the 2 gimbal servos.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from seeker_core.contracts import ActuatorChannel, ActuatorFrame, Frame, ImuSample, Provenance

RawImuRead = Callable[[], "tuple[float, float, float, float, float, float]"]   # (gx,gy,gz,ax,ay,az) raw LSB
ServoWriteUs = Callable[[int, float], None]                                     # (channel, pulse_us)


# ── calibration / config ──────────────────────────────────────────────────────────────────────────
@dataclass
class Pi5Config:
    # IMU: raw LSB -> SI, axis remap (raw -> body x/y/z), sign. camera looks +x; gy=pitch, gz=yaw.
    gyro_scale_rps: float = math.radians(1.0) / 16.4    # e.g. ICM ±2000dps: 16.4 LSB/(deg/s)
    accel_scale_mps2: float = 9.80665 / 2048.0          # e.g. ±16g: 2048 LSB/g
    gyro_axis_map: tuple[int, int, int] = (0, 1, 2)
    gyro_sign: tuple[float, float, float] = (1.0, 1.0, 1.0)
    accel_axis_map: tuple[int, int, int] = (0, 1, 2)
    accel_sign: tuple[float, float, float] = (1.0, 1.0, 1.0)
    # servo: rad -> pulse width (us), clamped to the mechanical range
    servo_us_center: float = 1500.0
    servo_us_per_rad: float = 500.0 / math.radians(45.0)   # 45° -> 500us (typical); calibrate per servo
    servo_us_min: float = 900.0
    servo_us_max: float = 2100.0
    pan_channel: int = 0
    tilt_channel: int = 1
    pan_sign: float = 1.0
    tilt_sign: float = 1.0
    # Mechanical travel limits (rad), measured by hand-moving the head to each stop (ops/pi_gimbal_calib.py).
    # The servo command is clamped to these so it NEVER drives past the mechanical stops. None = no limit
    # (falls back to the servo_us_min/max pulse clamp only).
    pan_limit_rad: "tuple[float, float] | None" = None      # (min=left, max=right)
    tilt_limit_rad: "tuple[float, float] | None" = None     # (min=down, max=up)
    # camera
    camera_device: str = "/dev/video0"
    invert: bool = False              # black-hot source -> True
    img_w: int = 640
    img_h: int = 512
    loop_hz: float = 200.0            # control-loop rate


def imu_raw_to_si(raw6, cfg: Pi5Config) -> "tuple[tuple, tuple]":
    """Raw IMU counts -> (gyro rad/s, accel m/s^2) in the camera body frame (remapped + scaled + signed)."""
    g_raw, a_raw = raw6[0:3], raw6[3:6]
    gyro = tuple(cfg.gyro_sign[i] * g_raw[cfg.gyro_axis_map[i]] * cfg.gyro_scale_rps for i in range(3))
    accel = tuple(cfg.accel_sign[i] * a_raw[cfg.accel_axis_map[i]] * cfg.accel_scale_mps2 for i in range(3))
    return gyro, accel


def rad_to_pulse_us(angle_rad: float, sign: float, cfg: Pi5Config) -> float:
    us = cfg.servo_us_center + sign * angle_rad * cfg.servo_us_per_rad
    return max(cfg.servo_us_min, min(cfg.servo_us_max, us))


def load_calibration(path: str, base: "Pi5Config | None" = None) -> "Pi5Config":
    """Build a Pi5Config from a gimbal_calib.json written by ops/pi_gimbal_calib.py. Unknown/missing keys
    keep the base default, so a partial calibration still loads."""
    import dataclasses
    import json
    cfg = base or Pi5Config()
    with open(path) as f:
        d = json.load(f)
    fields = {f.name for f in dataclasses.fields(Pi5Config)}
    updates = {}
    for k, v in d.items():
        if k not in fields:
            continue
        if k in ("gyro_axis_map", "accel_axis_map"):
            v = tuple(int(x) for x in v)
        elif k in ("gyro_sign", "accel_sign"):
            v = tuple(float(x) for x in v)
        elif k in ("pan_limit_rad", "tilt_limit_rad") and v is not None:
            v = (float(v[0]), float(v[1]))
        updates[k] = v
    return dataclasses.replace(cfg, **updates)


def _clamp_limit(angle_rad: float, limit) -> float:
    if limit is None:
        return angle_rad
    lo, hi = limit
    return max(lo, min(hi, angle_rad))


def pan_pulse_us(angle_rad: float, cfg: Pi5Config) -> float:
    """Pan command -> servo pulse, first clamped to the measured mechanical travel limit so the servo can
    NEVER be driven past its stop (ops/pi_gimbal_calib.py records pan_limit_rad)."""
    return rad_to_pulse_us(_clamp_limit(angle_rad, cfg.pan_limit_rad), cfg.pan_sign, cfg)


def tilt_pulse_us(angle_rad: float, cfg: Pi5Config) -> float:
    """Tilt command -> servo pulse, clamped to the measured mechanical travel limit (tilt_limit_rad)."""
    return rad_to_pulse_us(_clamp_limit(angle_rad, cfg.tilt_limit_rad), cfg.tilt_sign, cfg)


def frame_8bit_to_contract(gray_u8: np.ndarray, cfg: Pi5Config) -> Frame:
    """8-bit thermal (grabber) -> uint16 pseudo-counts Frame the detector expects (documented lossy)."""
    import cv2
    g = 255.0 - gray_u8 if cfg.invert else gray_u8.astype(np.float64)
    if g.shape != (cfg.img_h, cfg.img_w):
        g = cv2.resize(g, (cfg.img_w, cfg.img_h), interpolation=cv2.INTER_AREA)
    u16 = (4096.0 + g * 42.0).clip(0, 65535).astype(np.uint16)
    return Frame(u16, radiometric=False, provenance=Provenance("ft640", time.monotonic_ns(), synthetic=False))


# ── adapters (seeker_core Protocols) ────────────────────────────────────────────────────────────────
class Pi5Imu:
    """ImuSource: raw hook -> calibrated ImuSample."""
    def __init__(self, cfg: Pi5Config, raw_imu_read: RawImuRead) -> None:
        self.cfg, self.raw = cfg, raw_imu_read

    def read(self, t_ns: int) -> Optional[ImuSample]:
        gyro, accel = imu_raw_to_si(self.raw(), self.cfg)
        return ImuSample(gyro_rps=gyro, accel_mps2=accel, provenance=Provenance("imu", t_ns, synthetic=False))


class Pi5Servos:
    """ActuatorSink: writes ONLY the gimbal channels (GIMBAL_AZ/EL) to the 2 servos. Airframe channels
    are ignored — the bench has no motors, and motors must never be driven from the stand."""
    def __init__(self, cfg: Pi5Config, servo_write_us: ServoWriteUs) -> None:
        self.cfg, self.write_us = cfg, servo_write_us

    def write(self, frame: ActuatorFrame) -> None:
        az = frame.by_channel(ActuatorChannel.GIMBAL_AZ)
        el = frame.by_channel(ActuatorChannel.GIMBAL_EL)
        if az is not None:
            self.write_us(self.cfg.pan_channel, rad_to_pulse_us(az.value, self.cfg.pan_sign, self.cfg))
        if el is not None:
            self.write_us(self.cfg.tilt_channel, rad_to_pulse_us(el.value, self.cfg.tilt_sign, self.cfg))


class Pi5Camera:
    """CameraSource: FT640 via a V4L2 grabber (OpenCV) -> Frame. Uses the datalog/real_ingest 8-bit map."""
    def __init__(self, cfg: Pi5Config) -> None:
        import cv2
        self.cfg = cfg
        self._cap = cv2.VideoCapture(cfg.camera_device, getattr(cv2, "CAP_V4L2", 0))

    def read(self) -> Optional[Frame]:
        import cv2
        ok, bgr = self._cap.read()
        if not ok:
            return None
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
        return frame_8bit_to_contract(gray, self.cfg)

    def close(self) -> None:
        try:
            self._cap.release()
        except Exception:
            pass


# ── reference raw-hook factories (chip-specific; guarded imports) ─────────────────────────────────
def make_i2c_imu_reader(bus_num: int = 1, addr: int = 0x68, gyro_reg: int = 0x43,
                        accel_reg: int = 0x3B, gyro_fs: int = 0x18, accel_fs: int = 0x18) -> RawImuRead:
    """MPU-6050 / MPU-9250 (HW-290/GY-521) raw reader over I2C: wakes the device, sets full-scale
    (gyro_fs 0x18 = ±2000 dps, accel_fs 0x18 = ±16 g — match Pi5Config scales), returns 6×int16.
    Same register map for both MPU parts (accel 0x3B, gyro 0x43, addr 0x68)."""
    from smbus2 import SMBus  # type: ignore
    sm = SMBus(bus_num)
    for _ in range(15):                       # I2C glitches near servos (Errno 110/121) — retry the init
        try:
            sm.write_byte_data(addr, 0x6B, 0x00)      # PWR_MGMT_1: wake from sleep
            sm.write_byte_data(addr, 0x1B, gyro_fs)   # GYRO_CONFIG
            sm.write_byte_data(addr, 0x1C, accel_fs)  # ACCEL_CONFIG
            break
        except OSError:
            time.sleep(0.05)

    def _rd16(reg: int) -> float:
        hi = sm.read_byte_data(addr, reg)
        lo = sm.read_byte_data(addr, reg + 1)
        v = (hi << 8) | lo
        return float(v - 65536 if v & 0x8000 else v)

    def read():
        return (_rd16(gyro_reg), _rd16(gyro_reg + 2), _rd16(gyro_reg + 4),
                _rd16(accel_reg), _rd16(accel_reg + 2), _rd16(accel_reg + 4))
    return read


def pca9685_ticks(pulse_us: float, freq_hz: float = 50.0) -> int:
    """Servo pulse (us) -> PCA9685 12-bit OFF-count at the given PWM frequency."""
    return int(round(pulse_us * 4096.0 * freq_hz / 1_000_000.0)) & 0x0FFF


def make_pca9685_servo_writer(bus_num: int = 1, addr: int = 0x40, freq_hz: float = 50.0) -> ServoWriteUs:
    """PCA9685 (I2C, addr 0x40) servo PWM writer over raw smbus2 — no extra library. Shares the Pi I2C
    bus with the IMU (0x68, no conflict). Servo power goes to the board's V+ terminal from a separate
    5-6 V BEC (NOT the Pi rail); logic VCC from the Pi 3.3V; common ground. THE recommended path."""
    from smbus2 import SMBus  # type: ignore
    sm = SMBus(bus_num)
    prescale = int(round(25_000_000.0 / (4096.0 * freq_hz)) - 1)
    sm.write_byte_data(addr, 0x00, 0x10)        # MODE1: sleep (PRESCALE is writable only in sleep)
    sm.write_byte_data(addr, 0xFE, prescale)    # PRESCALE
    sm.write_byte_data(addr, 0x00, 0x00)        # MODE1: wake
    sm.write_byte_data(addr, 0x00, 0xA1)        # MODE1: restart + auto-increment

    def write_us(channel: int, pulse_us: float) -> None:
        ticks = pca9685_ticks(pulse_us, freq_hz)
        base = 0x06 + 4 * channel               # LEDn_ON_L
        sm.write_byte_data(addr, base + 0, 0x00)              # ON_L
        sm.write_byte_data(addr, base + 1, 0x00)              # ON_H
        sm.write_byte_data(addr, base + 2, ticks & 0xFF)     # OFF_L
        sm.write_byte_data(addr, base + 3, (ticks >> 8) & 0x0F)  # OFF_H
    return write_us


def esp32_servo_cmd(channel: int, pulse_us: float) -> bytes:
    """Wire format to the ESP32 servo slave: 'S <channel> <pulse_us>\\n'."""
    return f"S {int(channel)} {int(round(pulse_us))}\n".encode()


def make_esp32_serial_servo_writer(port: str = "/dev/ttyUSB0", baud: int = 115200,
                                   serial_obj=None) -> ServoWriteUs:
    """Servo writer that sends pulse commands to the ESP32 PWM slave over USB-serial (firmware in
    firmware/esp32_gimbal_servo/). The ESP32's hardware LEDC gives jitter-free servo PWM; the Pi keeps
    the control loop. `serial_obj` lets tests inject a fake port."""
    ser = serial_obj
    if ser is None:
        import serial  # type: ignore  (pyserial)
        ser = serial.Serial(port, baud, timeout=0.1)

    def write_us(channel: int, pulse_us: float) -> None:
        ser.write(esp32_servo_cmd(channel, pulse_us))
    return write_us
