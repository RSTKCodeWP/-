

# **UAS Top-Level Diagram**

<img width="1251" height="810" alt="UAS Top Level" src="https://github.com/user-attachments/assets/6fdc9972-4499-48d8-96c8-2671672261f2" />

 The companion ground station (HTML/JS GCS with a live mission planning) and the FPGA/SDR telemetry link this firmware is designed to pair with live in separate repos — see [Related work](#related-work).

## Why this exists
This project was built to mirror the firmware architecture used in production UAS and avionics systems — the kind of concept-to-flight ownership that companies like Anduril, Shield AI, and Joby Aviation hire embedded engineers to do. It deliberately avoids reaching for off-the-shelf flight stacks (PX4, ArduPilot, Betaflight) in favor of writing the scheduler, sensor fusion, and control architecture from first principles, because that is where the actual engineering judgment lives.
<img width="1514" height="963" alt="Drone diagram" src="https://github.com/user-attachments/assets/a252c92d-16fa-4429-a04a-f04903e216d0" />

# Bare-metal STM32H7 Flight Controller
A from-scratch flight controller firmware stack for the STM32H743 — a cooperative SysTick scheduler with hardware-backed fault detection, 9-DOF sensor fusion, and a graceful-degradation flight mode state machine.
<img width="1567" height="970" alt="Flight Controller" src="https://github.com/user-attachments/assets/add1e0f3-78e3-4968-a752-b1b474c120cf" />
> **Project status: core firmware infrastructure in progress , drivers in progress.** See [Implementation status](#implementation-status) below for exactly what runs today versus what's stubbed.
---
## Build

### Prerequisites

# Ubuntu / Debian
### Build & flash
```
sudo apt install gcc-arm-none-eabi cmake openocd
mkdir build && cd build
cmake --build build
make -j$(nproc)
make flash    # requires ST-Link V3 + OpenOCD
```
---
## Hardware target

| Component | Part |
|---|---|
| MCU | STM32H743ZIT6 (480 MHz Cortex-M7) |
| IMU | ICM-42670-P |
| Magnetometer | MMC5603NJ |
| Barometer | BMP388 |
| GPS | u-blox NEO-M9N |
| ESCs | commercial board |
| FPGA | Lattice MACHXO3LF |
| 25MP Cam | Sony IMX219 |
| SDR RF transceiver | Adalm Pluto |
| OS | Jetson nano |
| LoRa RF | Adafruit RFM95W |

---
## Sensor Fusion
Sensor fusion runs as two cooperating filters: a 9-DOF Madgwick quaternion filter (gyro + accelerometer + magnetometer) + complementary filter (linear z-axis acceleration + barometer) + Kalman filter ( GPS).

<img width="1223" height="873" alt="Sensor Fusion" src="https://github.com/user-attachments/assets/5cc8959a-407c-4550-a99e-e9fae534709c" />

---
## Cascading PID Controller
*(diagram goes here)*

---
## Related work

- **Ground control station** — HTML/JS GCS with live MAVLink telemetry, mission planning with real tile-map waypoints response panel. *(link to repo)*
🚧 Not yet written
- **SDR telemetry link** — GNU Radio flowgraph for the ADALM-PLUTO ground station: bridging to MAVLink over a local TCP socket. *(link to repo)*
🚧 Not yet written
- **FPGA Video Feed link** - Custom Lattice MACHXO3LF FPGA board integrated with Sony IMX219 camera and RF Communication downlink *(link to repo)*
🚧 Not yet written
- **Custom V4L2 Camera Driver with YOLOv8 TensorRT Object detection** - using a Logitech C270 webcam to interface with a jetson nano over V4L2 camera driver running YOLOv8 + TensorRT object detection algorithm.

    https://github.com/Ryannscotty/Custom-V4L2-Camera-Driver-with-YOLOv8-TensorRT-Object-detection

     🚧 in progress

---
##  Scheduler Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│  STM32H743 — bare-metal                                           │
│                                                                   │
│  SysTick ISR (1 kHz)  ──sets pending flags──▶  superloop          │
│         │                                          │              │
│         │                                  watchdog_task_start()  │
│         │                                          ▼              │
│         │                                    tasklist.fn() runs   │
│         │                                          │              │
│         ▼                                   watchdog_task_end()   │
│  IWDG (hardware) ◀── kicked once per loop pass, never inside a    │
│  TIM7 deadman timer ── fires independently if a task hangs        │
│                                                                   │
│  ┌───────────────┐   ┌────────────────┐   ┌────────────────────┐ │|
│  │ 1 kHz tier     │   │ 10 Hz tier     │   │ Flight mode FSM     ││
│  │ IMU → AHRS     │──▶│ GPS/baro/batt  │──▶│ STABILIZE→ALT_HOLD  ││
│  │ → rate PID     │   │ → position PID │   │ →LOITER→RTL→FAILSAFE││
│  └───────────────┘   └────────────────┘   └────────────────────┘ │|
└─────────────────────────────────────────────────────────────────┘
```
## Implementation status

| Module | Status | Notes |
|---|---|---|
| `scheduler.c`| 🚧 In Progress | Cooperative SysTick dispatcher, per-task execution profiling via DWT cycle counter, configurable task table |
| `watchdog.c` | 🚧 In Progress | Two-layer fault detection: IWDG hardware reset + TIM7 deadman timer that identifies *which* task hung, surviving the reset via RTC backup register |
| `ahrs.c` | 🚧 Not yet written  | 9-DOF Madgwick filter — gyro + accel + magnetometer, online gyro bias estimation, hard-iron mag calibration routine |
| `mag.c` | 🚧 Not yet written  | magnetometer SPI driver |
| `flight_mode.c`| 🚧 Not yet written  | Flight mode FSM — STABILIZE, ALT_HOLD, LOITER, AUTO, RTL, LAND, FAILSAFE, with automatic graceful degradation when a mode's required sensors become unavailable |
| `task_sensorfusion.c` | 🚧 Not yet written | Scheduler glue connecting IMU/mag drivers to the AHRS update task |
| `main.c` | ✅ Complete | Boot sequence, clock config, peripheral init, watchdog diagnostic readback |
| `imu.c` | 🚧 Not yet written | SPI DMA driver + IIR filter |
| `pid.c` | 🚧 Not yet written | Cascaded rate/attitude/position PID, motor mix matrix |
| `baro.c` | 🚧 Not yet written | BMP388 driver + altitude IIR filter |
| `gps.c` | 🚧 Not yet written | u-blox M10 UBX parser, NED conversion |
| `battery.c` | 🚧 Not yet written | ADC voltage/current monitoring, mAh integration |
| `mavlink.c` | 🚧 Not yet written | MAVLink 2.0 telemetry TX/RX, command parsing |
| `dshot.c` | 🚧 Not yet written | DShot600 ESC output via TIM1 DMA |
| `mission.c` | 🚧 Not yet written | Waypoint sequencing for AUTO mode |
| `failsafe.c` | 🚧 Not yet written | Pre-arm checks, link-loss detection, arm/disarm gating |
| task_stubs.c`| 🚧 In Progress | provides a harmless no-op for every task callback not yet implemented, so the scheduler core can be flashed and verified on real hardware today, independent of the rest of the stack. |

---

**FlightController PCB**

#🚧 in progress

<img width="1157" height="803" alt="MCU" src="https://github.com/user-attachments/assets/beb0ad78-16e2-4d22-91d5-616a4f1ae915" />

<img width="1154" height="805" alt="Sensors1" src="https://github.com/user-attachments/assets/c9fa9051-f383-41ac-8185-bacfccb0430e" />

#🚧 in progress

see [View Flight Controller Hardware details](Flight%20Controller%20Hardware/)

---
## Safety

This is firmware for a system that can spin propellers at lethal speed. Before connecting motors:
- Remove all propellers for every bench test until rate and attitude loops are verified stable.
- Confirm `scheduler_get_stats().missed_deadlines == 0` after a 60-second bench run.
- Verify the watchdog actually resets the MCU within the configured timeout by deliberately hanging a test task.
- Confirm failsafe triggers correctly with the radio link physically disconnected before any flight test.

## Design decisions worth knowing about

**Why a bare-metal scheduler instead of FreeRTOS.** A cooperative SysTick dispatcher gives full control over execution order and eliminates an entire class of priority-inversion and context-switch-jitter bugs that make PID tuning miserable to debug. Every task runs to completion, in a fixed table order, with execution time measured via the DWT cycle counter — you can put an oscilloscope on a single GPIO and see exactly what the CPU is doing at any microsecond. An RTOS earns its complexity when you have many independent, asynchronous workloads; a flight controller's control loops are not that — they are a small number of strictly periodic tasks with hard deadlines, which is exactly what a cooperative scheduler is built for.

**Why the watchdog has two layers, not one.** Every statistic the scheduler tracks (`max_exec_us`, `overruns`) is written *after* a task returns — a task stuck forever in a blocking call or an infinite loop never reaches that code, and the failure is invisible. The IWDG (hardware, LSI-clocked, independent of the CPU core) guarantees recovery no matter what. A second timer, TIM7, runs in one-pulse mode armed fresh before every task call; if it fires, it means that *specific* task exceeded its time budget, and the index is written to an RTC backup register that survives the reset. The result: the next boot can report "task `gps_parse` hung" instead of just resetting with zero diagnostic information.

**Why the flight mode FSM degrades instead of refusing.** If LOITER is requested but GPS lock drops mid-flight, the FSM doesn't get stuck or fault — it walks down a degradation ladder (`LOITER → ALT_HOLD → STABILIZE → FAILSAFE`) until it finds the most capable mode the *currently healthy* sensors can actually support, and sends a status message explaining why. This check runs every tick against the *active* mode, not just at the moment of a mode-change request, because sensors fail mid-flight, not just at the moment a button is pressed.

**Why the rate PID will read raw gyro, not the AHRS output.** (Implemented in the not-yet-written `pid.c`, documented here because it shapes the rest of the design.) The inner control loop needs the lowest possible latency; routing it through a filter — even a fast one — adds phase lag that directly degrades stability margin. Only the D-term gets a light PT1 low-pass, because differentiating raw gyro noise produces spikes a filter has no business being absent for.

---
