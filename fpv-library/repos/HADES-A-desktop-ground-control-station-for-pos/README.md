<div align="center">

<img src="hades-logo.png" alt="HADES" width="200" />

### Hurricane Autonomous Detection and Emergency System

**A ground station for post-hurricane drone search-and-rescue.**

An FPV drone flies the search area and streams video to a laptop on the ground. HADES is the
ground station that receives that feed: it runs real-time human detection on the frames, turns
each detection into a real-world survivor coordinate with an honest uncertainty radius, and
presents the contacts on a live map in a coordinator interface. The whole loop runs on one
fanless MacBook Air with the network off.

<br/>

![on-device](https://img.shields.io/badge/runs-100%25_on--device-2FB67C?style=for-the-badge)
![platform](https://img.shields.io/badge/Apple_Silicon-Core_ML_+_ANE-3B7BC8?style=for-the-badge&logo=apple&logoColor=white)
![latency](https://img.shields.io/badge/glass--to--glass-22.4_ms_p95-E6A23C?style=for-the-badge)

</div>

---

## How it connects

HADES is the ground half of a two-part system: an aircraft in the air and a laptop on the
ground. The signal chain, drone to survivor pin, is:

```
   DRONE (in the air)                          GROUND STATION (one laptop)
 ┌─────────────────────┐                     ┌──────────────────────────────────────────┐
 │  DJI O4 camera  ─────┼── digital video ───┼─► HDMI/UVC capture ─► Python service      │
 │  (fixed mount)       │     (analog-free)   │       │                 detect → track    │
 │                      │                     │       │                 → project → fuse  │
 │  F405 FC + M10 GPS ──┼── CRSF telemetry ──┼─► ELRS USB serial ──────┘        │        │
 │  ELRS radio          │   (pose: lat/lon/   │                                  ▼        │
 └─────────────────────┘    alt/attitude)     │    two localhost WebSockets ─► Electron   │
                                              │    (frames + detections)      coordinator │
                                              │                                UI (map)   │
                                              └──────────────────────────────────────────┘
```

Two links come off the aircraft, on **separate radios**: the **DJI O4** flies the camera view
down as a digital video feed (captured into the laptop over HDMI-to-USB UVC), and the **ELRS**
radio carries low-rate **CRSF telemetry** (the aircraft's GPS position, altitude, and attitude)
in over USB serial. On the laptop, a **Python detection service** runs the vision-and-math
pipeline and a **coordinator UI** (an Electron app) draws the results. The service and the UI
talk over two localhost WebSocket channels, aligned frame-by-frame. Nothing leaves the machine.

## The pipeline

Video displays at full frame rate while detection, tracking, and localization run decoupled, so
a survivor pin never costs you a dropped frame. One contact flows through seven stages, each with
a single responsibility and no reach across the boundary:

<div align="center">

<img src="docs/documentation/figures/fig-arch.png" alt="HADES pipeline architecture" width="960" />

</div>

- **FrameSource** yields `(frame, timestamp, seq)` with drop-to-latest, and tolerates dropped
  frames, mid-stream resolution changes, and link loss. Implementations are swappable: recorded
  file, live UVC capture, or synthetic.
- **Detector** is a stateless `frame → Detection[]` (box, `person`, confidence). YOLO11s
  fine-tuned on HERIDAL + SARD for tiny aerial people, exported to Core ML (FP16) and served on
  the Apple Neural Engine. It knows nothing about time or the world.
- **Tracker** gives detections persistent IDs and bridges the 10 fps detector to 30 fps video: a
  from-scratch NumPy **ByteTrack** with a Kalman filter, two-stage association, and no ID
  resurrection.
- **Projector** turns each detection's box bottom-center into a ray and intersects it with the
  ground (a cheap per-detection point, no Monte Carlo).
- **Confirmation** promotes a track's display priority by a decay score, hysteresis, and
  world-space clustering. It sets **display priority, never visibility**, so a real detection is
  never hidden.
- **Fuse + Quantify** (the localizer) fuses a confirmed contact across frames and runs a Monte
  Carlo to produce an honest uncertainty ellipse and an actionability class (PINPOINT, SWEEP,
  AREA, or CUE-ONLY). It never emits a false-precision pin.
- **Coordinator UI** shows one contact in three projections (map, video, list) over a global
  selection model, with MGRS and WGS84 readouts, a status spine that degrades visibly under load,
  and an append-only mission log. Runs fully offline.

**The IPC.** Two localhost WebSocket channels carry the data. A **binary channel** streams
JPEG-encoded frames, and a **JSON channel** (bidirectional) carries per-frame detections and
contact records, plus operator commands back to the service (for example, promote a track to a
full localization on demand). The JPEG, the detection message, and every contact for a frame all
carry the **same `frame_id`**, so every overlay lands on the frame it belongs to. Electron
supervises the Python service as a child process and shuts it down when the app closes.

## Live demo

The project site (linked at the top of this repo) includes a static, click-to-run demo that
replays a canned mission through the real coordinator UI in a plain browser. No install, no
backend.

<div align="center">

<img src="docs/assets/p6/demo-site.png" alt="HADES coordinator UI" width="900" />

</div>

The demo is labeled **DEMO MODE**: the scene and drone pose are scripted, but every map pin,
uncertainty ellipse, and confidence value is live output of the HADES localizer run against
known ground truth. The banner reports the localizer's median error against that known truth
(1.1 m on this scripted scene). It is not a live feed.

---

## How the math works

Turning a person-shaped patch of pixels into a coordinate on a map is the heart of the system.
It happens in two steps: a geometric projection that gives a single best-guess coordinate, and a
Monte Carlo that turns the sensors' error into an honest uncertainty radius.

### From pixel to coordinate: monocular ray-to-ground

There is one camera and no depth sensor, so a single detection is not a point in space; it is a
**ray**. HADES casts that ray from the camera, through the aircraft's known pose, and intersects
it with the ground. The model is flat-earth v1 in a local **ENU** (East-North-Up) tangent plane
centered under the drone, on WGS84.

Given a pixel `(u, v)` at the person's feet (the box bottom-center), the camera intrinsics
`K = [[fx,0,cx],[0,fy,cy],[0,0,1]]`, the aircraft attitude `(roll, pitch, yaw)`, the fixed
camera boresight, the drone altitude, and the ground elevation:

```
ray_cam = K⁻¹ · [u, v, 1]ᵀ                 # direction in the camera's optical frame
d       = R_world_body · R_body_cam · ray_cam   # rotate that ray into ENU world coordinates
require d_up < 0                            # the ray must point at the ground, or reject
H       = drone_alt − ground_elev           # height above ground (AGL)
t       = −H / d_up                         # scale the ray down to the ground plane
east    = t · d_east ,  north = t · d_north
lat     = drone_lat + north / 111320
lon     = drone_lon + east  / (111320 · cos(lat))
```

`R_world_body` is the aircraft's attitude (an aerospace ZYX Euler rotation), and `R_body_cam` is
the fixed mount of the gimbal-less O4 camera; the effective camera pitch is the mount angle plus
the airframe's pitch. The projection **refuses to invent a pin**: if there is no GPS fix, any
attitude value is missing, the vertical datums do not match (a coastal geoid offset of 25 to 35 m
would otherwise poison the height), or the ray points at or above the horizon, it raises rather
than returning a confident, wrong coordinate.

### From one coordinate to an honest radius: the Monte Carlo

The projection above is exact given perfect inputs, but the inputs are not perfect. A single
degree of heading error moves the ground point by about **1.75 m per 100 m of range**, and an FPV
quad has no magnetometer, so heading (from GPS course and a drifting gyro) is the dominant error
source. HADES quantifies this by sampling.

For each confirmed contact it draws **N = 1000** realizations. Each draw perturbs every input by
its calibrated sensor error (GPS horizontal and vertical, roll/pitch/yaw jitter, pixel jitter,
ground-elevation, time-sync) and re-projects through the same `ray_to_ground`. The key subtlety:
the **heading bias is drawn once per contact and shared across all its frames**, not redrawn per
frame. A per-frame bias would average out across a multi-frame fusion and fake a precision the
geometry cannot deliver; because the bias is common-mode, it does **not** average away, so the
reported radius asymptotes to a floor that grows with range instead of shrinking to zero.

Multi-frame contacts are fused first with an information-weighted (inverse-covariance) mean of
the per-frame ground points, then the Monte Carlo is run over that fusion. The outputs are a 2×2
ENU covariance, a 95% confidence ellipse (semi-axes scaled by `√χ²₂,₀.₉₅ ≈ 2.45`), and, as the
headline number, **R95: the empirical 95th-percentile radius** of the sample cloud about the
estimate. A NEES diagnostic (target ≈ 2) checks that the reported spread matches the actual
error, and a residual test flags a target that is moving rather than stationary.

Each contact then lands in one of four **actionability classes** by its R95, so an operator reads
intent, not just a number:

| Class | R95 | Meaning |
| --- | --- | --- |
| **PINPOINT** | ≤ 5 m | walk straight to it |
| **SWEEP** | ≤ 25 m | a short line search |
| **AREA** | ≤ 100 m | search the neighborhood |
| **CUE-ONLY** | > 100 m | a direction, not a location |

A single straight pass with little aspect diversity is capped at SWEEP no matter how tight the
math looks, because only viewing a survivor from different angles actually breaks the
heading limit. The problem is heading-limited, not algorithm-limited, and the system is built to
say so out loud.

---

## How well it works

Every number below traces to a real artifact produced in an earlier build phase. Detection
metrics are on a leakage-guarded HERIDAL held-out scene split (a custom by-scene re-split, not
the official HERIDAL test split, so numbers are not directly comparable to published benchmarks).
Localization numbers are from a
calibrated synthetic simulator (tagged `sim`) whose noise models are tuned to the sensor-error
literature; they prove the method is correct and the uncertainty is honest, and they will move
when the real labeled-with-pose flight set lands. The latency p95 is a dev-machine floor under
software GL, not the binding field number.

### Detection

YOLO11s fine-tuned on HERIDAL + SARD, single `person` class, evaluated by center-distance
matching (50 px) on 376 held-out HERIDAL frames. The fine-tune is the win: stock COCO YOLO11s
barely fires on tiny aerial people. FP16 quantization did not cost accuracy.

<div align="center">

<img src="docs/documentation/figures/showcase/showcase-before-after.png" alt="Stock vs fine-tuned detector on a real HERIDAL frame" width="640" />

<sub>Stock YOLO11s (left) vs the HADES SAR fine-tune (right) on the same real HERIDAL aerial
frame. Boxes are live model output.</sub>

</div>

<table>
<tr>
<td><img src="docs/documentation/figures/fig-detection-conf-sweep.png" alt="Detection operating points" width="430" /></td>
<td><img src="docs/documentation/figures/fig-quant-delta.png" alt="FP16 vs float32" width="430" /></td>
</tr>
</table>

| Operating point (conf) | Recall | Precision |
| --- | --- | --- |
| 0.25 (default) | 0.51 | 0.62 |
| 0.10 | 0.63 | 0.46 |
| 0.05 (recall-first) | 0.69 | 0.37 |

Recall is operating-point-driven. At a fielded, recall-first threshold the shipped FP16 Core ML
model reaches **~0.69 recall** on single frames (higher again after multi-frame confirmation),
while the strict 0.25 default point gives **recall 0.551, precision 0.676** (793 true positives,
380 false positives, 645 misses). Both are honest: 0.551 is the conservative anchor, ~0.69 is the
realistic fielded number. This sits below the 0.80 recall floor that was pre-registered against a
looser IoU-mAP scale; the acceptance test here is a stricter center-distance match on native
4000 px frames, and it is reported faithfully rather than reframed. Selection optimism is
disclosed too: the 960 input resolution was chosen on the same held-out set, so these move when
the curated disaster footage lands.

### Localization

Monocular ray-to-ground fusion with a Monte Carlo uncertainty ellipse. Error grows cleanly with
slant range and camera pitch: near-nadir is PINPOINT-grade, oblique standoff is AREA-grade. The
system is heading-limited (no magnetometer); that is the dominant error source, and the
uncertainty ellipse reflects it rather than reporting false precision.

<table>
<tr>
<td><img src="docs/documentation/figures/fig-loc-error-by-geometry.png" alt="Localization error by geometry" width="430" /></td>
<td><img src="docs/documentation/figures/fig-coverage-calibration.png" alt="Uncertainty calibration" width="430" /></td>
</tr>
</table>

| Geometry (range x pitch from nadir) | median (sim) | p90 (sim) | coverage |
| --- | --- | --- | --- |
| 30 to 80 m, near-nadir (0 to 15 deg) | 1.2 m | 2.2 m | 0.97 |
| 80 to 150 m, near-nadir | 7.6 m | 15.6 m | 0.80 |
| 150 to 300 m, oblique (65+ deg) | 11.8 m | 17.4 m | 1.00 |

The right-hand chart is the credibility check. The reported 95% ellipse is validated against
model error: a matched control covers about 95% (the arithmetic is right), and an out-of-schema
time-sync offset, which the Monte Carlo cannot model, collapses coverage to 25%. That collapse
is the evidence the metric measures the world, not its own math. A moving target stays
AREA-class with a large radius (R95 about 84 m) and never reports PINPOINT.

### Real-time

The latency budget is in-app glass-to-glass (frame on socket to painted with overlay and pin)
at 120 ms. Video runs at 30 fps; detection runs decoupled at 10 fps or better. All three
candidate resolutions clear the detection gate on a fanless MacBook Air M4 (32 GB), and the ANE
serves the model (a 5.6x speedup over CPU at 640 px confirms it is not falling back).

<table>
<tr>
<td><img src="docs/documentation/figures/fig-fps-by-resolution.png" alt="Detector FPS by resolution" width="430" /></td>
<td><img src="docs/documentation/figures/fig-latency-budget.png" alt="In-app latency budget" width="430" /></td>
</tr>
</table>

| Resolution | Detector throughput (ANE) | Clears 10 fps gate |
| --- | --- | --- |
| 640 px | 293 fps | yes |
| **960 px (shipped)** | **63 fps** | yes |
| 1280 px | 57 fps | yes |

In-app latency on the dev machine: p50 1.9 ms, **p95 22.4 ms**, max 33.6 ms over 90 frames,
clearing the 120 ms budget by more than 5x. This is a floor measured under software GL with
small canned frames; the on-device field run on real-resolution frames is pending.

> Three hero visuals (a 3D localization-error surface, a geographic survivor map, and a 3D
> calibration field) are rendered with Wolfram. The scripts and run instructions live in
> [`docs/documentation/wolfram/`](docs/documentation/wolfram/README.md).

---

## Built with

Versions are read from the lockfiles, not guessed (`service/uv.lock`,
`artifacts/armA_heridal_sard/requirements.lock.txt`, `ui/pnpm-lock.yaml`).

**Detection service (Python 3.12)**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Ultralytics](https://img.shields.io/badge/Ultralytics_YOLO11-8.4.76-111F68?style=for-the-badge)
![PyTorch](https://img.shields.io/badge/PyTorch-2.11.0_(cu128)-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![Core ML](https://img.shields.io/badge/Core_ML_Tools-8.x-000000?style=for-the-badge&logo=apple&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-1.26.4-013243?style=for-the-badge&logo=numpy&logoColor=white)
![ONNX Runtime](https://img.shields.io/badge/ONNX_Runtime-1.27.0-005CED?style=for-the-badge&logo=onnx&logoColor=white)
![PyAV](https://img.shields.io/badge/PyAV-17.1.0-0D7377?style=for-the-badge)
![OpenCV](https://img.shields.io/badge/OpenCV-4.11.0-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-2.13.4-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![websockets](https://img.shields.io/badge/websockets-16.0-4B8BBE?style=for-the-badge)

**Coordinator UI (TypeScript)**

![Electron](https://img.shields.io/badge/Electron-33.4.11-47848F?style=for-the-badge&logo=electron&logoColor=white)
![React](https://img.shields.io/badge/React-18.3.1-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.9.3-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-6.4.3-646CFF?style=for-the-badge&logo=vite&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind_CSS-3.4.19-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)
![MapLibre](https://img.shields.io/badge/MapLibre_GL-5.24.0-396CB2?style=for-the-badge&logo=maplibre&logoColor=white)
![Zustand](https://img.shields.io/badge/Zustand-5.0.14-2D3748?style=for-the-badge)
![Playwright](https://img.shields.io/badge/Playwright-1.61.0-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)
![Vitest](https://img.shields.io/badge/Vitest-4.1.9-6E9F18?style=for-the-badge&logo=vitest&logoColor=white)

---

## The aircraft

The ground station is only half the system; the other half flies. The drone is built, not
bought: a 3D-printed airframe carrying an off-the-shelf FPV and telemetry stack.

| Part | Role |
| --- | --- |
| **3D-printed airframe** | A monocoque printed in-house that carries the whole stack. |
| **Speedy Bee F405 flight controller** | Keeps the aircraft level and streams attitude and GPS telemetry, which the localizer turns into coordinates. |
| **DJI O4 Air Unit Lite + camera** | The digital video link. Fixed mount, no gimbal; flies the survivor's-eye view down to the laptop. |
| **ELRS Nano RX** | The control link, plus a second telemetry path (CRSF) over USB serial. |
| **HGLRC M10 GPS** | Position and altitude for every frame's pose. |
| **2306 motors, 5-inch tri-blades** | Four of each. Sized for post-storm wind, not for racing. |
| **6S battery** | Sets the flight time; every choice upstream is weighed against the air time it costs. |

**How pose reaches the math.** Telemetry is time-synced to video by timestamp, so every frame is
paired with the aircraft pose interpolated at that instant. Two `TelemetrySource` adapters feed
it: `SrtFileSource` replays the O4's `.srt` sidecar against recorded video (the validation path),
and `CrsfSerialSource` reads live CRSF off the ELRS radio's USB serial port (stubbed in v1, built
with the hardware in hand). Pose that lacks attitude is left honestly incomplete, and the
geometry refuses rather than assuming the aircraft is level and pointing north.

---

## Run it locally

Targets an Apple Silicon MacBook (M4 or M5), macOS. No CUDA: inference is Core ML.

```bash
# Python detection service
cd service && uv run hades-service --clip <clip.mp4> --telemetry <clip.srt>

# Coordinator UI (Electron app, supervises the service)
cd ui && pnpm install && pnpm start
```

Tests: `uv run pytest` (service) and `pnpm test` (UI, Playwright over a mock WS). Metrics:
`uv run hades-eval` (detection) and `uv run hades-locsim` (localization). Documentation figures:
`uv run --group docs hades-make-figures`.

Hard constraints the build holds to: the detect, localize, and display loop runs with the
network off (no cloud inference, no runtime model or tile fetch, no telemetry phone-home); it
stays functional on a fanless MacBook Air M4 by degrading processed-detection FPS, never the
video. Allowed exceptions are pre-downloaded offline map tiles and an optional, user-triggered
post-mission export.

## Documentation

- `docs/DESIGN.md`, `docs/DESIGN-SYSTEM.md`: system design and the UI aesthetic spec.
- `docs/documentation/`: the metrics behind every chart above (`data/`), the chart renderers
  (`figures/`), the Wolfram hero-visual scripts (`wolfram/`), and the content gate that maps
  each figure to its source artifact (`OUTLINE.md`).
- `docs/plans/`: the phase-by-phase build plan and the per-phase result writeups.
