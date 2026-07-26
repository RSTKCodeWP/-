# Design Spec — LLM FPV Drone Flight Assistant

**Date:** 2026-06-08 · **Status:** Approved design, pre-implementation · **Author:** (project owner) + Claude

## 1. Overview & goals

A **model-agnostic LLM copilot for an FPV drone**, built on **PX4 + MAVLink**, developed **SITL-first** in **Gazebo (gz) Harmonic**. The human pilot flies FPV manually and **delegates discrete tasks to the assistant by natural language** (shared / hand-off control); the assistant also provides situational awareness, telemetry narration, and safety advice. Over time the assistant covers four roles — (1) NL command & control, (2) mission planning/replanning, (3) telemetry & log analysis, (4) safety/operator copilot — but this spec covers the **first vertical slice: flying NL command & control with hand-off**.

**Strategic context:** the project is aligned with Baykar / TEKNOFEST. Turkish-language and voice are planned later phases (see §11), and a model-agnostic design keeps the door open to the Turkish **T3 AI** model as one more backend.

**Guiding principle (from prior-art research):** the LLM is an advisor/translator that **never sits in the hard real-time control loop**. It proposes; a deterministic safety layer disposes; the human stays in command.

## 2. Scope

### First slice (this spec)
> *Type an English command in the dashboard → the assistant proposes a structured command → the operator confirms → the drone executes it in PX4 SITL, with the validation gate enforcing limits, the manual⇄assistant hand-off working, the telemetry HUD live, and the FPV video showing.*

### Out of scope (later phases, each its own spec)
VLM "see-and-describe" vision · telemetry/log-analysis role · RAG safety copilot · **Turkish language + voice I/O** · graded autonomy levels · HITL / real hardware.

## 3. Architecture (Approach B — two services)

```
 ┌──────────────────────────────────────────────────────────────────┐
 │  ASSISTANT + DASHBOARD SERVICE  (Python; LLM lives here)          │
 │  • Model-agnostic LLM layer (OpenRouter → Gemini → Ollama/T3 AI)  │
 │  • Agent loop: NL → STRUCTURED command (JSON schema) → preview    │
 │  • Web dashboard: FPV video + HUD overlay + chat + ABORT button   │
 └───────────────┬───────────────────────────▲──────────────────────┘
   validated cmd │ (JSON / websocket)         │ telemetry + events
                 ▼                            │
 ┌──────────────────────────────────────────────────────────────────┐
 │  FLIGHT-SAFETY SERVICE  (Python; NO LLM — the trusted core)       │
 │  • Owns the single MAVSDK link to PX4                             │
 │  • Validation gate: geofence · alt/speed · battery · EKF/GPS ·    │
 │    mode/armed preconditions · schema · rate-limit  → reject+reason│
 │  • Active flight management: telemetry-GATED execution            │
 │  • Hand-off: manual ⇄ OFFBOARD; instant return-to-human on abort  │
 └───────────────┬──────────────────────────────────────────────────┘
                 │ MAVLink (UDP)
                 ▼
 ┌───────────────────────────┐   gz camera  ┌─────────────────────────┐
 │  PX4 SITL ◀──▶ gz Harmonic │   topic ───▶ │ Video bridge (gz-transp │
 │  (x500 camera model)       │              │ → frames → WebRTC/MJPEG)│
 └───────────────────────────┘              └─────────────────────────┘
        ▲ (optional) QGroundControl = human map view
```

**Why two services:** the LLM **cannot bypass** the safety layer — it can only act through the validated command API. Each unit is independently testable: the safety service is hammered with no LLM; the LLM/UI swap without touching flight code.

## 4. Components

### 4.1 Flight-Safety Service (deterministic, no LLM)
- Owns the single **MAVSDK-Python** connection to PX4 SITL.
- **Telemetry monitor:** continuously reads position, attitude, velocity, battery, GPS/EKF health, flight mode, armed state; publishes a telemetry + events stream over websocket.
- **Validated command API** — a small verb set (§5). Each call runs:
  - **Validation gate (deterministic):** geofence polygon, altitude ceiling/floor, speed cap, battery threshold, GPS/EKF health, armed/mode preconditions, JSON-schema check, rate limit. On violation → **reject with a human-readable reason**.
  - **Active flight management (telemetry-gated):** a command does not report "done" until telemetry confirms it (e.g. `orbit` is established, `goto` is within arrival radius). No fire-and-forget.
  - **Hand-off:** switches PX4 between manual (human) and **OFFBOARD** (assistant) only on explicit request; **instantly relinquishes to the human** on stick input, `ABORT`/`TAKE CONTROL`, or any anomaly.
- Exposes a local **websocket + JSON** API. Contains **no LLM**; fully unit-testable.

### 4.2 Assistant + Dashboard Service (LLM lives here)
- **Model-agnostic LLM layer:** an `LLMProvider` interface. First adapter = **OpenRouter** (OpenAI-compatible, via the `openai` SDK with OpenRouter base URL); next = **Gemini API**; later = Ollama / T3 AI. Model chosen by a config string.
- **Command representation:** the LLM emits **constrained structured output** (a strict JSON schema of the safety verbs), validated with `pydantic` **before** anything is sent — *not* reliant on native tool-calling, so it works across any model (the TypeFly/MiniSpec lesson). Schema-invalid output is rejected and regenerated, never sent.
- **Agent loop:** operator NL + current telemetry/context → propose a structured command → **preview** to operator → on confirm, call the safety API → narrate status from telemetry events. Read-only Q&A ("what's my battery?") bypasses the command path.
- **Web dashboard (FastAPI + websockets; lightweight frontend):** FPV `<video>` + canvas **HUD overlay** (alt, speed, battery, mode, who's in control), chat box, command **preview/confirm** widget, and an always-visible **ABORT / TAKE CONTROL** button.

### 4.3 Video pipeline
gz Harmonic **camera sensor topic** (e.g. `x500_mono_cam` / gimbal-camera model) → a **gz-transport** subscriber → frames → browser via **WebRTC** (low latency) or **MJPEG** (simple first). No ROS required. For the first slice the feed is **passive** (shown, not yet analyzed); VLM narration is a later phase using a **cloud VLM** (the GTX 970 can't host a good local VLM alongside gz).

## 5. Command schema (first-slice verb set)
A strict JSON schema; each verb has typed, range-checked params. Verbs: `arm_takeoff(alt)`, `goto(lat,lon,alt)`, `orbit(center?,radius,alt)`, `loiter()`/`hold()`, `return_to_launch()`, `land()`, `takeover()` (enter OFFBOARD), `handback()` (return to manual). "Assist takeover" verbs require the validation gate + telemetry-gating; `arm_takeoff` is included mainly for self-contained SITL demos (the human normally takes off in the real concept).

## 6. Control model & hand-off
Human flies FPV manually (PX4 manual/position mode). On an explicit, **confirmed** delegated command, the safety service switches to **OFFBOARD** and executes telemetry-gated. Control returns to the human **immediately and authoritatively** on stick movement, `TAKE CONTROL`/`ABORT`, command completion, or any anomaly. PX4's own failsafes (geofence, RTL, battery, kill switch) remain the ultimate backstop below everything.

## 7. Data flow — "take over and orbit, 30 m radius, 25 m alt"
1. Operator types/says it. 2. LLM → `{verb:"orbit", radius:30, alt:25}` (or asks a clarifying question if ambiguous). 3. Parser validates schema → dashboard shows **preview + Confirm**. 4. Operator confirms. 5. Safety service validates (geofence/battery/health/mode); if OK switches to OFFBOARD and executes telemetry-gated, else **rejects with reason**. 6. Telemetry events stream back; assistant narrates ("orbit established, battery 78%"). 7. Any moment: human stick input / `TAKE CONTROL` → manual control restored instantly.

## 8. Safety & error handling (non-negotiables)
- LLM **never** in the real-time loop; acts **only** through the validated API (enforced by the two-service split).
- **Every command requires explicit operator confirmation** in v1.
- Validation gate **rejects deterministically with reasons**; **telemetry-gated** execution (no fire-and-forget).
- **Human override is instant and authoritative.** PX4 failsafes remain the ultimate backstop.
- Link loss / agent crash → safety service commands PX4 **hold/RTL**; dashboard shows degraded state. Schema-invalid LLM output is rejected/regenerated, never sent.

## 9. Tech stack
Python 3.11+ (both services, one repo) · **MAVSDK-Python** (flight bridge) + `pymavlink`/`pyulog` (raw/logs, later) · **PX4 SITL + gz Harmonic** (`x500` camera model) · **websocket + JSON** inter-service link · LLM via **OpenRouter** (OpenAI SDK) then Gemini, structured output validated by **pydantic** · **FastAPI + websockets** backend, Vite + vanilla/React frontend with canvas HUD · **GStreamer/WebRTC** (or MJPEG) video · `.env` + `pydantic-settings` config · **pytest** (mock safety service for agent tests; SITL-in-the-loop integration tests).

## 10. Environment & simulation
- **Host:** Linux Mint 22.2 "Zara" (Ubuntu 24.04 "noble" base), kernel 6.17, 8 cores, 15 GiB RAM, **NVIDIA GTX 970 4 GiB**, driver **535**, currently a **headless tty**.
- **Sim:** PX4 SITL + **gz Harmonic**, **headless GPU rendering (EGL)**, FPV feed viewed in the **browser dashboard**; QGroundControl optional for the map view.
- **Setup nuances to handle:** point the **OSRF apt repo at `noble`** (Mint's `zara` codename is not in OSRF repos); **work around PX4 `ubuntu.sh`** not recognizing Mint; verify gz OGRE2 headless rendering on the GTX 970.
- **Prerequisites the owner provides:** an **OpenRouter API key** (and optionally a Gemini key) in a local **`.env`** (never pasted in chat). Everything else (PX4 build, gz, GStreamer, Python venv) is scripted during setup.

## 11. Milestone roadmap
- **M0 — Environment:** PX4 SITL + gz Harmonic + MAVSDK "hello world" (arm/takeoff/land from a script).
- **M1 — Flight-Safety service:** telemetry + validation gate + verbs + telemetry-gated execution + hand-off + abort, fully tested (no LLM).
- **M2 — Assistant core:** model-agnostic provider + structured command generation + preview/confirm + narration (vs mock, then real safety service).
- **M3 — Dashboard:** FPV video + HUD + chat + abort wired to both services → **first impressive demo (first slice complete).**
- **M4 — Eval harness:** scenario suite + metrics (valid-command rate, mission success, unsafe-command rejection) + rejection tests.
- **Later phases (separate spec/plan cycles):** VLM vision narration · telemetry/log-analysis role · RAG safety copilot · **Turkish + voice** · graded autonomy · HITL.

## 12. Open decisions (deferred, not blocking the first slice)
- Turkish-language strategy and whether to build on / benchmark against **T3 AI**.
- Voice I/O (STT/TTS) stack.
- WebRTC vs MJPEG for the first video implementation (start MJPEG if WebRTC wiring is slow).
- Graded autonomy levels (beyond always-confirm) — revisit after M3.
