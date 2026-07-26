# seeker_core — a clean-room, hardware-agnostic seeker (ГСН) core

**One job:** turn a sensor stream into actuator commands, behind strict typed contracts, with honesty
rules that forbid fabrication. Sensor in → aim-point/guidance → **command bus out** (airframe ESCs/
servos, gimbal, any peripheral).

This is a *clean architecture* layer, not a reimplementation of the physics. The proven detect / track
/ guidance in `../fpv/` plug in as `Detector` / `Tracker` / `Guidance` implementations — we give the
verified algorithms clear boundaries and a real actuator output; we do **not** reinvent them.

## Boundaries (what is core vs adapter)

```
[input adapters]              CORE (portable, golden reference)            [output adapters]
 Camera ─Frame─►  Detect ─► Track/LOS ─► Guidance ─► ActuatorMapper ─ActuatorFrame─► Airframe sink
 IMU ────Imu──►       ▲          ▲           ▲             ▲                          └► Gimbal sink
 Operator ─Cmd─►      └──────── SafetySupervisor (two-press auth · arming · HW-kill · ROE) ─► aux sinks
```

- **Core** = `detect → track → guidance → safety → actuator-mapping` (`core.py`). Pure, testable,
  deterministic, portable to C/RTL. This Python is the GOLDEN reference; an FPGA impl must be bit-exact.
- **Adapters** (`adapters.py`) = everything device-specific: `CameraSource`, `ImuSource`,
  `ActuatorSink`. The "most preferable" hardware is a *choice of adapter*, not baked into the core:
  - camera: native-digital Y16 (MIPI/LVDS) preferred; FT640 CVBS-8bit is one adapter.
  - mount: 2-axis gimbal *or* strapdown — a config + a `GIMBAL_AZ/EL` output channel.
  - compute: FPGA/Zynq for minimal latency (this reference defines the contract it meets bit-exact).

## Honesty rules (the core never fabricates)
1. No line-of-sight without a detection.
2. No range/t_go without an observable — `Optional`, `None` when unobservable (never a made-up number).
3. No lock without enrollment (LOBL).
4. **No engage authority without a signed two-press operator commit.**
5. Degrade to coast/abort — never invent state.
6. Every output carries provenance + capture timestamp + a `synthetic` flag.

## Latency / power / range — honest scope
- **Latency** is minimised by the *FPGA implementation* (single clock domain: frame timestamp + IMU
  external clock; streaming line-rate detect; ROI after lock). This reference defines the contract.
- **Power / range** are sensor + optics + geometry bound, not core-bound. The core extracts the most
  from the sensor (CFAR, subtense ranging); it does not exceed physics and never pretends to.

## Layout
- `contracts.py`    — the typed, versioned, validated data contracts (the boundaries).
- `adapters.py`     — input/output adapter Protocols + honest reference stubs (sim camera, record/print sinks).
- `core.py`         — the `SeekerCore` pipeline + stage Protocols + default-deny honest stubs + actuator mapping.
- `gimbal_stage.py` — `GimbalControllerStage`: the proven `fpv.gimbal.GimbalController` (gyro-stabilized
  2-servo head, IMU on the head) plugged in as the core's gimbal stage → `GIMBAL_AZ/EL` servo setpoints
  + the clean inertial LOS rate (head gyro). `gimbaled_core(...)` wires it; `default_core()` is strapdown.
- `detector_stage.py` — `RealDetector`: the proven `fpv.seeker.detect` (top-hat / adaptive threshold /
  CCL / weighted centroid, bit-exact to the FPGA front-end) plugged in as the `Detector` → real FT640
  detections feed the gimbal + tracker. This is the physics port for Bench Stages 1→4.
- `tests/`          — contract validation + safety boundary + a gimbaled head that tracks a blob.

Run: `cd 03-fpv && python3 -m pytest seeker_core -q`
