# Gimbal bring-up runbook (Pi5) — physical target tracking

The seeker head physically pans/tilts to keep the warm target centred (gyro-stabilised). Small servos, no
motors/props — **safe**. Order matters: **calibrate signs BEFORE closed-loop**, or a wrong sign runs the servo
into the stop. Software is ready (`seeker_core.gimbal_bench_io`, `seeker_core.calibrate_gimbal`); it deploys the
moment the Pi is reachable.

## 1. Wire it (I²C — same bus as before)
- **IMU MPU-9250/6050** on the HEAD (rigid, by the camera): VCC→**3.3 V**, GND→GND, SDA→**pin 3 (GPIO2)**,
  SCL→**pin 5 (GPIO3)**, AD0→GND → address **0x68**.
- **PCA9685**: VCC(logic)→**3.3 V**, GND→GND, SDA→pin 3, SCL→pin 5 → address **0x40**;
  **V+ ← own 5–6 V BEC** (NOT the Pi rail); **common ground**.
- **Servos**: PAN → PCA9685 **CH0**, TILT → **CH1**. **Mechanical end-stops on both axes.**
- ⚠️ 3.3 V logic only on SDA/SCL (Pi GPIO is not 5 V tolerant).

## 2. I²C is already enabled (`dtparam=i2c_arm=on`, `/dev/i2c-1`, `i2c-tools` installed)
Verify after wiring:
```
i2cdetect -y 1        # MUST show 40 (PCA9685) and 68 (IMU). Both present -> bus wired right.
```

## 3. Calibrate (Stage S0) — gimbal free to move, end-stops present
```
sudo systemctl stop seeker            # free the resources
cd /home/admin/seeker/system
PYTHONPATH=$PWD:$PWD/fpv python3 -m seeker_core.calibrate_gimbal
```
It runs two captures (I run this for you once the Pi is back):
- **STATIC (15 s):** head still → gyro **bias + noise**.
- **SERVO STEP (+30°):** each axis steps → real servo **slew/lag**. **Watch which way pan and tilt move.**

Then tell me: on the +30° step, **PAN → left or right? TILT → up or down?** and rotate the head by hand in
yaw / pitch. From that I fix `Pi5Config`: `gyro_axis_map`, `gyro_sign`, `pan_sign`, `tilt_sign`,
`servo_us_per_rad`. CSVs: `runs/cal_static.csv`, `runs/cal_servo_step.csv`.

## 4. Closed-loop tracking (after signs are fixed)
With the calibrated `Pi5Config`, the head runs the gyro-stabilised track loop (`GimbalController` +
`Pi5GimbalBenchIO` + the FT640 centroid): **shake the base by hand → the head holds the warm target centred.**
I finalise `run_gimbal.sh` from your real slew/sign numbers so it can't strip the gimbal, then you run it.

## 5. What this proves
The **decisive lever** from the honest sim: a gimbaled seeker holds a maneuvering target where strapdown misses.
This is the visible "отслеживание" — the head physically following the target — and the first hardware step
toward closing the body-to-body envelope. Ties to SYSTEM_SPEC.md §5–6.
