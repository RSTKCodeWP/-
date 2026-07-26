<div align="center">

# LLM FPV Flight Assistant

**A model-agnostic LLM copilot for an FPV drone — natural-language command & control with a deterministic safety layer that keeps the AI out of the hard real-time loop.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![PX4 + Gazebo](https://img.shields.io/badge/PX4-SITL%20%2B%20gz%20Harmonic-026FB6)](https://px4.io/)
[![Tests](https://img.shields.io/badge/tests-170%20py%20%2B%2025%20web%20%2B%20SITL%20e2e-3ddc97)](#testing)

![FPV cockpit dashboard](docs/img/cockpit.png)

</div>

---

## What this is

The human flies an FPV drone manually and **delegates tasks to an assistant in natural language** ("orbit that area at 20 m", "return to launch"). The assistant proposes a structured command; a **deterministic flight-safety layer validates and executes it**; the human can take the sticks back at any time. The defining rule:

> **The LLM never sits in the hard real-time control loop.** It proposes — a validation gate decides — the human stays in command.

Everything is developed **SITL-first** on **PX4 + Gazebo (gz Harmonic)**, so you can run the whole thing on a laptop with no hardware. It's model-agnostic via OpenRouter (any OpenAI-compatible endpoint).

> ⚠️ **Simulation project.** This is a research/education codebase validated in SITL. Do not fly it on a real airframe without your own safety review, geofencing, and regulatory compliance.

---

## Highlights

- 🛡️ **Authoritative safety gate** — a deterministic, LLM-free service validates every command against a typed schema, geofence, altitude/speed limits, and live telemetry health before any actuation.
- 🗣️ **Streaming natural-language control** — type a request; the assistant streams its reply token-by-token (with a "thinking" trace when the model exposes reasoning), proposes a validated command, and waits for your **Confirm**.
- 🎮 **Gate-validated manual flight** — take the sticks with the keyboard (WASD / Q-E / R-F). Every velocity setpoint is clamped to safe limits, geofence-braked, and protected by a **500 ms hover watchdog** — the browser never drives the vehicle directly.
- 📹 **Real onboard camera** — the live Gazebo camera is streamed as MJPEG from a crash-isolated bridge process, with an automatic Three.js telemetry fallback if the feed drops.
- 🧭 **Immersive FPV/OSD cockpit** — full-bleed video with attitude horizon, compass tape, altitude/speed ladders, health chips, quick-action buttons, and a live event log.
- 🔌 **Model-agnostic** — OpenRouter / any OpenAI-compatible API; swap models with one env var.
- 📊 **Eval harness** — a deterministic benchmark scores any model's NL→command quality against the schema + safety gate (no SITL needed): happy-path accuracy, ask-when-ambiguous, **unsafe→gate-rejects**, and never-invent-coordinates → a Markdown/JSON scorecard for cross-model regression tracking.

---

## Screenshots

| Natural-language → validated command | Manual keyboard control |
|:---:|:---:|
| ![Chat proposal](docs/img/chat.png) | ![Manual control](docs/img/manual.png) |
| Streamed assistant reply + the exact JSON command the gate will run, behind a **Confirm/Cancel** gate. | **MANUAL (YOU)** mode: live keyboard HUD; setpoints stream through the safety gate at 20 Hz. |

<div align="center">

**Live onboard camera (Gazebo, headless EGL):**

<img src="docs/img/camera-feed.jpg" width="520" alt="Live gz camera frame">

</div>

---

## Architecture

Three independent processes behind a hard trust boundary. The **LLM lives only on the assistant side** and can never reach the vehicle except through the validated safety API.

```mermaid
flowchart LR
  subgraph BROWSER["🖥️  Browser — FPV Cockpit (Vite + React)"]
    UI["OSD overlay · streaming chat · manual keyboard · quick actions · ABORT"]
  end

  subgraph DASH["Dashboard backend  :8090  (FastAPI)"]
    HUB["DashboardHub + Agent<br/>(owns control-state)"]
    SC["SafetyClient (demuxing ws)"]
  end

  subgraph VID["Video bridge  :8092  (standalone, crash-isolated)"]
    MJ["gz camera → JPEG → MJPEG + /health"]
  end

  subgraph SAFE["⛨  Flight-safety service  :8765  — NO LLM"]
    GATE["Validation gate<br/>(schema · geofence · limits · health)"]
    BR["MAVSDK bridge<br/>(telemetry-gated executors + OFFBOARD)"]
  end

  LLM[("LLM<br/>OpenRouter")]
  PX4[("PX4 SITL<br/>+ Gazebo")]

  UI -- "ws: chat / manual / quick / confirm / abort" --> HUB
  HUB -- "telemetry push + streamed chat + control_state" --> UI
  UI -- "MJPEG video tag" --> MJ
  HUB <-->|"NL to structured command"| LLM
  HUB --> SC
  SC <-->|"ws: validated commands + 20 Hz setpoints + telemetry"| GATE
  GATE --> BR
  BR <-->|"MAVLink / OFFBOARD"| PX4
  MJ <-->|"gz-transport"| PX4

  classDef safe fill:#0d2018,stroke:#3ddc97,color:#e6edf3;
  classDef llm fill:#241a2e,stroke:#b07cf0,color:#e6edf3;
  class GATE,BR safe;
  class LLM,HUB,SC llm;
```

### The safety invariant — every manual setpoint passes the gate

The browser sends *desired velocity*, not motor commands. The gate clamps, geofence-brakes, and watchdogs it before anything reaches MAVSDK.

```mermaid
flowchart TD
  K["⌨️ keyboard WASD/QE/RF"] --> SP["body-frame velocity setpoint"]
  SP -->|"ws 'manual' @ 20 Hz"| SRV["flight-safety server"]
  SRV --> MS["dispatcher.manual_setpoint()"]
  MS --> C1{"in OFFBOARD?"}
  C1 -- no --> X["⛔ dropped"]
  C1 -- yes --> CL["clamp to max_speed_ms<br/>+ max_yaw_rate_dps"]
  CL --> GF{"1 s look-ahead<br/>inside geofence?"}
  GF -- no --> BRK["zero horizontal<br/>(geofence brake)"]
  GF -- yes --> ST["store setpoint + timestamp"]
  BRK --> ST
  ST --> WD{"setpoint &lt; 500 ms old?"}
  WD -- no --> HOV["command zero → hover<br/>(watchdog: dropped link can't fly away)"]
  WD -- yes --> SEND["set_velocity_body() → MAVSDK → PX4"]
  HOV --> SEND

  classDef danger fill:#2a1416,stroke:#ff4d4f,color:#fff;
  class X,BRK,HOV danger;
```

### Natural-language command flow

```mermaid
sequenceDiagram
  actor Op as Operator
  participant UI as Cockpit
  participant Hub as Dashboard / Agent
  participant LLM
  participant Gate as Safety gate
  participant PX4

  Op->>UI: "orbit here at 20 m, radius 25"
  UI->>Hub: chat
  Hub->>LLM: NL + live telemetry (streaming)
  LLM-->>UI: prose reply, streamed token-by-token
  LLM-->>Hub: {"verb":"orbit","radius":25,"alt":20,...}
  Hub->>Hub: validate against typed schema
  Hub-->>UI: proposal card (Confirm / Cancel)
  Op->>UI: Confirm
  UI->>Hub: confirm
  Hub->>Gate: command
  Gate->>Gate: geofence · limits · battery · GPS/EKF health
  Gate->>PX4: execute (telemetry-gated)
  Gate-->>UI: result → "Executed orbit."
  Note over Op,PX4: ABORT preempts any in-flight command at any moment.
```

---

## Tech stack

| Layer | Tech |
|---|---|
| **Flight-safety service** | Python 3.11 · FastAPI · websockets · MAVSDK-Python · pydantic |
| **Assistant** | OpenRouter (OpenAI-compatible) · constrained JSON output (not tool-calling) · streaming |
| **Video bridge** | gz-transport Python bindings · Pillow · MJPEG over FastAPI |
| **Frontend** | Vite · React 18 · TypeScript · react-three-fiber · Vitest |
| **Simulator** | PX4 SITL · Gazebo (gz Harmonic) · headless EGL rendering |

---

## Repository layout

```
src/flight_safety/   the trusted core — NO LLM: config, command schema, geofence,
                     validation gate, MAVSDK bridge (OFFBOARD), dispatcher, ws server
src/assistant/       the LLM side: provider, streaming command generation,
                     demuxing safety-client, agent, CLI
src/video_bridge/    standalone gz-camera → MJPEG process (+ /health)
src/dashboard/       dashboard backend: hub orchestration, broadcaster, ws app
src/eval_harness/    eval harness: NL→command quality benchmark (cases, runner,
                     deterministic scorer, scorecard report, CLI) vs schema + gate
frontend/            Vite + React + react-three-fiber FPV/OSD cockpit
evals/               curated NL→command test cases (results/ gitignored)
tests/               pytest (unit + SITL/API-gated integration) · Vitest
docs/                design specs, implementation plans, eval baselines, ROADMAP
```

The full project tracker, conventions, and hard-won gotchas live in **[`ROADMAP.md`](ROADMAP.md)**.

---

## Getting started

### Prerequisites
- PX4-Autopilot built for SITL with Gazebo (gz Harmonic) — see the PX4 docs.
- Python 3.11 (project venv) and Node.js for the frontend.
- An OpenRouter API key (or any OpenAI-compatible endpoint).

### Install
```bash
python -m venv .venv && . .venv/bin/activate
pip install -e .
npm --prefix frontend install
cp .env.example .env        # then add your AS_OPENROUTER_API_KEY
```
Secrets live in `.env` (gitignored). `FS_GEOFENCE` must contain the SITL home (~47.398, 8.546) or commands are rejected as out-of-bounds.

### Run (each in its own terminal)
```bash
# 1) Simulator — camera airframe + landmark test world
PX4_GZ_WORLD=cam_test HEADLESS=1 make -C /path/to/PX4-Autopilot px4_sitl gz_x500_mono_cam

# 2) Flight-safety service (no LLM) — ws on 127.0.0.1:8765
python -m flight_safety

# 3) Video bridge → MJPEG on :8092
#    NOTE: gz Python bindings live in the SYSTEM interpreter, not the venv.
PYTHONPATH=src VB_TOPIC="/world/cam_test/model/x500_mono_cam_0/link/camera_link/sensor/camera/image" \
  VB_PORT=8092 /usr/bin/python3 -m video_bridge

# 4) Dashboard backend → http://<host>:8090
npm --prefix frontend run build
DASH_PORT=8090 python -m dashboard
```
Open **http://&lt;host&gt;:8090**, then: type a command → **Confirm**, or click **TAKE CONTROL** and fly with **WASD / Q-E / R-F** (Shift = boost). **ABORT** is always live.

> Default ports `8080/8082` are assumed free; this repo's examples use `8090/8092` because they were taken on the dev box. See `ROADMAP.md` for the full set of operational gotchas.

---

## Testing

```bash
pytest -q                       # Python unit suite (170 passing)
npm --prefix frontend test      # frontend unit suite (Vitest, 25 passing)
pytest -m integration -v        # live integration (SITL e2e + 1 eval live smoke)
python -m eval_harness --models "$AS_MODEL"   # benchmark a model → scorecard (docs/evals/)
```

The validation gate, geofence brake, manual-setpoint clamping, OFFBOARD watchdog, and streaming chat parser are all unit-tested. The end-to-end flow (NL → propose → confirm → execute, plus take-control → manual setpoints → release) is verified live in SITL. The **eval harness** scores NL→command quality deterministically against the schema + gate (offline, CI-safe) and benchmarks real models on demand; a dated baseline lives in [`docs/evals/`](docs/evals/).

---

## Project status

- [x] **M1 — Flight-safety service** — validation gate, MAVSDK bridge, hand-off, abort. *Merged · validated live.*
- [x] **M2 — Assistant core** — model-agnostic LLM, constrained command generation, agent loop, CLI. *Merged · validated live.*
- [x] **M3 — FPV web dashboard** — real gz camera over MJPEG, telemetry HUD, chat with confirm, ABORT. *Merged · validated live.*
- [x] **Cockpit v2** — gate-validated manual flight, streaming chat, immersive OSD redesign. *Merged · validated live.*
- [x] **M4 — Eval harness** — deterministic NL→command quality benchmark (schema + gate oracle), offline CI tier + live cross-model scorecard. *Merged · validated live (92% / gate-agreement 100% on `deepseek-v4-flash`).*
- [ ] **Next** — voice I/O; Turkish-language support; VLM "see-and-describe" narration; on-screen joysticks / gamepad.

---

## Acknowledgements

Built on the excellent open-source work of [PX4](https://px4.io/), [Gazebo](https://gazebosim.org/), and [MAVSDK](https://mavsdk.mavlink.io/). Model access via [OpenRouter](https://openrouter.ai/).

## License

[MIT](LICENSE) © 2026 Ali Kendir
