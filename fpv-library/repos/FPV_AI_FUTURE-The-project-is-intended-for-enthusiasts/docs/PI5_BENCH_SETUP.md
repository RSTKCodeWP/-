# Raspberry Pi 5 bench setup — seeker head on a stand (2026-07-13)

Concrete steps to run the assembled seeker head (`seeker_core.head.bench_seeker_head`) on a Pi 5 with
the FT640 (via MS2107 grabber), the DIY 2-servo gimbal, and the head IMU. Bench only — **no motors, no
flight**; only the 2 gimbal servos are ever driven. Pairs with `BENCH_BRINGUP_SEQUENCE.md` (Stages 1–4).

## 1. Hardware (identified from the owner's photos)
- Compute: **Raspberry Pi 5** (flashed, RPi OS 64-bit).
- Thermal: **FT640 → MS2107 USB grabber → a Pi USB port** (`/dev/video0`; already connected).
- IMU: **MPU-9250 (HW-290)** — preferred; **MPU-6050 (GY-521)** is a fine fallback (identical driver,
  I²C 0x68). (GY-85/ADXL345+ITG3205 = weaker, last resort.) Mount RIGIDLY on the gimbal head by the camera.
- Servos: **2 servos on a PCA9685** (16-ch I²C hardware PWM driver, addr 0x40) — the recommended path.
  (An ESP32 serial-PWM slave is supported as an alternative — see firmware/esp32_gimbal_servo/.)

## 1b. Wiring
- **IMU + PCA9685 both on the Pi I²C:** VCC→3.3V, GND→GND, **SCL→GPIO3, SDA→GPIO2**. IMU at 0x68,
  PCA9685 at 0x40 — no conflict, so the PCA9548A mux is NOT needed.
- **Servos → PCA9685:** PAN → channel 0, TILT → channel 1.
- **⚠️ Power:** servos on their **own 5–6 V BEC** wired to the PCA9685 **V+ terminal** (NOT the Pi rail);
  PCA9685 logic VCC from the Pi 3.3V; **common ground**. A servo stall must not brown out the Pi.
- **⚠️ Mechanical end-stops** on both gimbal axes (a sign error can't then strip the gimbal).

## 2. Pi OS + dependencies
```bash
sudo raspi-config           # enable I2C
sudo apt install -y python3-opencv python3-numpy python3-scipy i2c-tools
pip3 install smbus2
i2cdetect -y 1              # confirm the IMU (0x68) and the PCA9685 (0x40) both appear
# (Alternative servo path: ESP32 -> pip3 install pyserial + flash firmware/esp32_gimbal_servo/.)
```

## 3. Get the code + run in sim first (no hardware)
```bash
cd <repo>/03-fpv
PYTHONPATH=fpv python3 -m seeker_core.bench_app --sim            # validate the head loop
PYTHONPATH=fpv python3 -m pytest seeker_core -q                  # 19 green
```

## 4. Wire the Pi5 adapters (the only new code you write)
Fill `Pi5Config` (calibration) and the two chip hooks, then run the same head loop on hardware:
```python
from seeker_core.pi5_io import (Pi5Config, Pi5Camera, Pi5Imu, Pi5Servos,
                                make_i2c_imu_reader, make_pca9685_servo_writer)
from seeker_core.bench_app import run
from seeker_core.contracts import OperatorButton, OperatorCommand

cfg = Pi5Config(camera_device="/dev/video0", invert=False)          # set `invert` from the camera calibration
imu   = Pi5Imu(cfg, make_i2c_imu_reader(addr=0x68))                 # MPU-9250/6050: wakes + sets ±2000dps/±16g
servo = Pi5Servos(cfg, make_pca9685_servo_writer(addr=0x40))        # PCA9685 on the Pi I2C
cam   = Pi5Camera(cfg)
op    = lambda: OperatorCommand(OperatorButton.NONE, None, 0)       # wire GPIO buttons here (two-press)
run(cam, imu, servo, op, realtime=True, ticks=100000)
```

## 5. Calibration order (do these before trusting the loop) — ties to the bench sequence
1. **IMU (Stage 2 static):** run `BenchRunner(io).capture_static()` (servos off, head still) → send me the
   CSV; `characterize()` gives bias/noise. Set `gyro_scale_rps`/`accel_scale_mps2` from the datasheet.
   Determine `gyro_axis_map`/`gyro_sign` empirically: rotate the head in yaw → only `gz` should move (+ for
   CCW); pitch up → `gy`. Fix the map/signs until it does.
2. **Servos (Stage 2 step):** `BenchRunner(io).capture_servo_step()` → real max slew/lag. Command known
   angles and measure the actual head angle → tune `servo_us_per_rad`, `servo_us_center`, `*_min/max`,
   `pan_sign`/`tilt_sign` (a wrong sign = positive feedback → runs to the stop).
3. **Camera (Stage 1):** point FT640 at a **small warm target on a cool background**, run
   `real_ingest --source /dev/video0`; confirm the detector locks. Set `invert` (True for black-hot).
4. **Controller gains:** with the above, I re-tune `k_loop`/`k_track` (and add a rate-command LPF if the
   servo buzzes) from your logs, and re-check CPA in the sim with your real numbers.

## 6. Bench test flow
- **Stage 3 (stabilization):** `BenchRunner(io, GimbalController(cfg_tuned)).run_closed_loop()` — fix a warm
  target, **shake the base by hand** → the target must stay centred (target never leaves the FOV). Log it.
- **Stage 4 (full head):** `bench_app.run(cam, imu, servo, op, realtime=True)` — a moving warm target is
  detected, the gimbal holds it, telemetry shows a plausible LOS-rate/command; airframe stays neutral
  (no motors). Wire the two GPIO buttons → `op` returns COMMIT with a signed token to exercise authority.

## 7. Safety on the bench
- Only the 2 gimbal servos are wired. `Pi5Servos` writes **only** `GIMBAL_AZ/EL` and ignores every
  airframe/motor channel by construction.
- The head never emits airframe authority without a verified two-press (`Authority.committed`); ABORT latches.
- Servos on their own BEC + common ground; a mechanical end-stop so a sign error can't strip the gimbal.

## Next (send me)
- Stage-1 clean-target FT640 clip, and the Stage-2 static + servo-step CSVs → I calibrate `Pi5Config`
  + the controller to YOUR hardware and re-measure CPA in the honest sim with your real numbers.
