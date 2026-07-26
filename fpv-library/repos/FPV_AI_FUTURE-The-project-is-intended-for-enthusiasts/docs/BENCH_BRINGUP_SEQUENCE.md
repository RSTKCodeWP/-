# Bench bring-up sequence — seeker head on a stationary stand (2026-07-13)

The ordered path from the green software baseline to a working **seeker head on a bench** (no flight),
on OUR hardware: **Zynq ZYNQ MINI (XC7Z020)**, **FT640 (8-bit, via MS2107 grabber on the PC bench →
TVP5150/BT.656 into the Zynq PL later)**, **DIY 2-servo gimbal (pan + tilt) with a gyro+accel IMU on
the head**. Every stage has a GO/NO-GO gate; do not advance on a red gate. Props/motors are OUT of this
plan entirely — this is the sensor+gimbal head only.

## Hardware we're using
- Compute: Zynq ZYNQ MINI XC7Z020-CLG400 (bench: a PC/laptop or Pi is fine for stages 1–4).
- Thermal: Foxeer FT640, 8-bit CVBS → MS2107 USB grabber (PC bench). Flight ingest later = TVP5150→BT.656→PL.
- Gimbal: 2 servos (pan/tilt, precise + fast) + IMU (gyro+accel) mounted ON the head.
- Bench: a rigid stand, a warm point target (soldering iron / hot mug / a hand at distance), a cool background.

## What software is already built (the baseline — freeze it)
- Detector/tracker/guidance (fpv/, green) + FPGA detect front-end (fpga/, 47 co-sim green, bit-exact).
- Gimbal: `fpv/gimbal/` — GimbalController (gyro-stab + centroid track + accel leveling), plant, datalog,
  **BenchRunner** (`fpv/gimbal/bench_runner.py`, one hardware seam `BenchIO`).
- Real-thermal bridge: `fpv_ai/bench/real_ingest.py` (runs the real detector on a live grabber / clip).
- Honest 3D sim with a realistic servo-gimbal model (`fpv_ai/bench/sim3d_honest.py`).
- seeker_core: clean sensor-in → actuator-out core with GIMBAL_AZ/EL channels + a default-deny safety gate.

---

## The sequence

### Stage 0 — Freeze the software baseline  ✅ (done)
All suites green; commit/tag. **Gate:** `pytest -m "not slow"`, `pytest fpga -q`, `pytest fpv/gimbal` green.

### Stage 1 — FT640 real-target detection (PC bench)
FT640 → MS2107 → PC → `real_ingest`. Capture a **small warm target on a cool/uniform background** (not a
cluttered room), white-hot, and measure detection + lock.
- Run: `PYTHONPATH=fpv python3 -m fpv_ai.bench.real_ingest --source /dev/video0 --invert --annotate /tmp/ft640.mp4`
- **Gate:** the detector finds and HOLDS lock on the real small warm target (longest-lock ≫ a few frames,
  centroid σ small), on the real 8-bit FT640. Send me the clip/metrics; I confirm.

### Stage 2 — Gimbal characterization (3 captures)
Mount the IMU on the head. Implement **one** `BenchIO` for your IMU (SPI/I2C) + servos (PWM) + the FT640
centroid (from the Stage-1 detector). Then run the three captures (props/rig context = bench):
1. **static** (rig still, servos OFF) → gyro bias & noise, centroid jitter.
2. **servo step** (command a servo directly ~30°) → real servo max rate, lag, tracking error.
3. (hold — Stage 3 produces the closed-loop log).
- Run: `BenchRunner(io).capture_static(); BenchRunner(io).capture_servo_step()` → CSVs.
- **Gate:** three valid CSVs in the datalog format. Send them; **I run `characterize()` and calibrate
  `k_loop`/`k_track`/filters to YOUR servos+IMU, then re-measure CPA in the sim with your real numbers.**

### Stage 3 — Closed-loop gimbal stabilization (bench)
Run `GimbalController` (on the PC/Pi first — IMU in, servo PWM out, FT640 centroid in) via
`BenchRunner(io, GimbalController(cfg_calibrated)).run_closed_loop()`. Fix a warm target; **shake the
base by hand**.
- **Gate:** the target stays centred while you shake the base (residual pointing error small, target never
  leaves the FOV); then move the target slowly → the head tracks it. Log it (closed_loop.csv) for review.

### Stage 4 — Seeker-head integration (bench, no motors)
Wire it end to end: FT640 detect → centroid → GimbalController → 2 servos; head-gyro → guidance (PREVIEW
only, displayed, nothing actuated besides the gimbal). Move the warm target around.
- **Gate:** a moving warm target is detected, the gimbal holds it centred, and the guidance produces a
  plausible LOS-rate/command on screen. This is the full seeker head working on a bench.

### Stage 5 — Port to the Zynq (target compute)
Move off the PC: GimbalController Python→C on the PS; FT640 → TVP5150 → BT.656 → PL detect (the RTL we
built); IMU → PS/PL (single clock domain = the sync win). Golden-vector bit-exact vs the Python reference.
- **Gate:** Stage-3/4 behaviour reproduced on the Zynq; `OFF == bit-identical` to the reference.

### Stage 6 — Safety & authority (bench, props OFF)
seeker_core's two-press supervisor + independent HW-kill in the (future) motor path. No actuator authority
without a verified commit; ABORT latches kill.
- **Gate:** no airframe/motor authority is ever emitted without `Authority.committed`; kill is sticky.

---

## What YOU implement (the only new hardware code)
One class, `BenchIO` (see `fpv/gimbal/bench_runner.py`):
```
read_imu() -> (gyro3, accel3)     # your IMU driver (SPI/I2C)
read_centroid() -> (cx,cy)|None   # FT640 frame -> the detector -> target centroid
write_servo(pan_rad, tilt_rad)    # your 2 servos (PWM)
servo_feedback() -> (pan,tilt)    # angle feedback if available, else (nan,nan)
now_ns(); tick()                  # real-time clock / sleep dt
```
Everything else (captures, logging format, controller, characterization, sim validation) is done.

## Immediate next actions
- **You:** Stage 1 clean-target FT640 capture; then wire `BenchIO` and run Stage-2 captures.
- **Me (now, if you want):** wrap `GimbalController` into seeker_core as the gimbal stage (GIMBAL_AZ/EL),
  and/or stub a concrete `BenchIO` skeleton for your specific IMU/servo parts so you only fill the driver calls.
