# Design Spec — M3 FPV Web Dashboard

**Date:** 2026-06-08 · **Status:** Approved design, pre-implementation · **Author:** (project owner) + Claude
**Parent spec:** `docs/superpowers/specs/2026-06-08-llm-fpv-flight-assistant-design.md` (§4.2, §4.3)
**Milestone:** M3 · **Branch:** `feat/fpv-dashboard`

## 1. Overview & goal

M3 delivers the **operator-facing web dashboard** that completes the first vertical slice: an operator
opens a browser, sees a **live FPV video feed** with a **telemetry HUD**, types a natural-language
command into a **chat box**, reviews the assistant's **preview**, confirms, and watches the drone
execute in PX4 SITL — with an always-visible **ABORT / TAKE CONTROL** button and a clear
**who's-in-control** indicator. This is the "first impressive demo" milestone from the parent roadmap.

M3 also lands two tracked M1 follow-ups that the dashboard depends on: the **real-time telemetry push
stream** and a **request `id`** for reply correlation.

## 2. Scope

### In scope
- Real **gz Harmonic camera** video, delivered to the browser as **MJPEG**, via an isolated bridge process.
- **Graceful fallback**: when the camera/video bridge is unavailable, the video pane renders a
  **live Three.js scene driven by telemetry** (so the demo never shows a dead pane).
- **HUD**: altitude, speed, battery, flight mode, who's-in-control, GPS/EKF health (+ attitude indicator).
- **Chat** with command **preview/confirm** and status **narration**.
- Always-visible **ABORT / TAKE CONTROL**.
- **Telemetry push stream** + **request `id`** added to the flight-safety service.

### Out of scope (later / unchanged)
VLM vision narration · telemetry/log-analysis role · Turkish + voice · graded autonomy · WebRTC (MJPEG
first; WebRTC remains a later option) · real hardware. The LLM/agent logic itself is unchanged — the
dashboard **reuses the existing `assistant.Agent`**, it does not re-implement command generation.

## 3. Architecture — three processes + a React frontend (Approach 2)

```
  Browser (React + three.js, Layout B)
    │  ws: telemetry / events / chat / preview / confirm / abort   ┌─ <img> MJPEG (read-only, direct)
    ▼                                                               │
  Dashboard backend  (src/dashboard, FastAPI)  ◀───────────────────┘  Video bridge (src/video_bridge)
    │  reuses assistant.Agent + SafetyClient (the LLM lives here)        gz-transport → JPEG → MJPEG
    │                                                                    standalone process, own port
    ▼  ws (commands + telemetry push)                                    ▲ gz camera topic
  Flight-safety service (src/flight_safety)  ─────────────────────────────┘
    │ MAVLink (UDP)                         PX4 SITL ◀─▶ gz Harmonic (camera-enabled airframe)
    ▼
  PX4 SITL
```

**Three independent processes** (chosen over an in-process video bridge for crash isolation — a
segfaulting gz subscriber must not take down the dashboard or the safety link):
1. **Flight-safety service** — existing trusted core, gains a telemetry push stream + reply `id`.
2. **Video bridge** — new, standalone; gz camera → MJPEG; restartable without touching anything else.
3. **Dashboard backend** — new FastAPI app = the parent spec's "Assistant + Dashboard Service".

The **browser talks to the dashboard backend** for all control/telemetry, and to the **video bridge only
for the MJPEG `<img>`** (read-only image; no CORS concern for `<img>` display). The safety service stays
walled off behind the backend — the browser never speaks to it directly.

## 4. Components

### 4.1 Flight-safety service changes (`src/flight_safety/server.py`)
- **Telemetry push stream:** a background task per websocket connection reads telemetry on an interval
  (~0.5 s, configurable) and sends `{"type":"telemetry","data":{...}}` frames. Independent of, and
  interleaved with, request/reply traffic. On a telemetry read error it pushes
  `{"type":"telemetry","error":"..."}` rather than dropping the connection.
- **Request `id` correlation:** the command envelope becomes `{"type":"command","id":<n>,"command":{...}}`
  and the reply echoes the same `id`. `abort`/`get_telemetry` likewise echo any provided `id`. Backward
  compatible: a missing `id` is simply not echoed. (Tracked M1 follow-up.)
- Existing semantics preserved: at-most-one in-flight command (`busy` rejection), abort preempts.

### 4.2 SafetyClient rework (`src/assistant/safety_client.py`)
The current client does a naive `send → recv`, which breaks the moment push frames interleave with
replies. Replace it with a **single receive loop that demultiplexes by frame**:
- A background reader task reads every frame: `telemetry`/event frames are dispatched to a **subscriber**
  (callback or async queue); command/abort replies are matched to their request by **`id`** via a
  pending-futures map.
- Public API: `subscribe_telemetry(cb)` (or an async iterator), `send_command(cmd) -> reply`,
  `abort() -> reply`, plus the existing `get_telemetry()` (now `id`-correlated). `connect()`/`close()`
  manage the reader task.
- The existing CLI (`src/assistant/__main__.py`) keeps working through the same `send_command`/`abort`.

### 4.3 Telemetry attitude fields (`src/flight_safety/models.py`, `bridge.py`)
Add **optional** `roll`, `pitch`, `yaw` (degrees, default `0.0`) to `Telemetry`, read from MAVSDK
`attitude_euler` in `read_telemetry`. Optional defaults keep every existing test and the validation gate
untouched. These drive a real **attitude indicator** in the HUD and let the Three.js fallback tilt the
horizon. *(Cuttable: if descoped, the HUD shows a level horizon and the fallback omits tilt.)*

### 4.4 Video bridge (`src/video_bridge/`, new process)
- Subscribes to the gz Harmonic **camera Image topic** via the gz-transport Python bindings
  (`gz.transport13` / `gz.msgs10`), converts each frame to **JPEG**, and serves an **MJPEG**
  `multipart/x-mixed-replace` stream over HTTP on its own port, plus a `/health` endpoint reporting the
  age of the last frame (so consumers can tell if video is actually flowing).
- Runs as `python -m video_bridge`. If gz/EGL rendering is unavailable, it stays up but reports
  `/health` unhealthy (no frames) — it never crashes the pipeline; the dashboard falls back.
- **Modules:** `bridge.py` (gz subscriber → latest-frame buffer), `mjpeg.py` (HTTP/MJPEG + health),
  `config.py` (topic name, port, JPEG quality), `__main__.py`.

### 4.5 Dashboard backend (`src/dashboard/`, new FastAPI app)
- Serves the built React app (static `frontend/dist/`).
- **Browser websocket** `/ws`:
  - **down:** `telemetry` (forwarded from the safety stream), `narration`/`event`, `proposal`
    (a pending command preview), command results (`executed`/`rejected`/`aborted`), `video_status`,
    `control_state` (manual/assistant).
  - **up:** `chat` (NL request), `confirm`/`cancel` (of the pending proposal), `abort`.
- **Orchestration** (reusing `assistant.Agent`): on `chat` → `Agent.propose`; a `CommandProposal` is
  held pending and sent to the UI as `proposal`; `QuestionProposal`/`ErrorProposal` go out as
  `narration`. On `confirm` → `Agent.execute(pending)` → relay result + narrate. On `abort` →
  `Agent.abort()` and flip `control_state`.
- **Telemetry fan-out:** subscribes to the SafetyClient telemetry stream and forwards frames to all
  connected browsers; derives simple **narration** from telemetry transitions (e.g. arrival, "orbit
  established, battery 78%").
- **Video status:** polls the video bridge `/health` and emits `video_status` so the frontend chooses
  MJPEG vs the Three.js fallback.
- **Config** (`src/dashboard/config.py`, `pydantic-settings`, `DASH_` prefix): `safety_url`,
  `video_bridge_url`, dashboard `host`/`port`; LLM settings reused from `AssistantSettings`.
- **Modules:** `app.py` (FastAPI + routes/static), `hub.py` (browser-ws orchestration + agent glue),
  `config.py`, `__main__.py`.

### 4.6 Frontend (`frontend/`, Vite + React + react-three-fiber — Layout B)
- **Top bar:** `control_state` indicator (MANUAL / ASSISTANT) and the always-visible
  **ABORT / TAKE CONTROL** button (red, full-width-prominent).
- **Left (~65%) video pane:** MJPEG `<img>` when `video_status.ok`, else a **react-three-fiber** scene
  driven by telemetry (ground grid + drone at the reported altitude/position, horizon tilt from
  attitude). A small overlay shows the active source.
- **Right column:** telemetry **cards** (ALT, SPD, BAT, MODE, GPS/EKF, attitude) on top; **chat** below
  — message history, input box, and an inline **preview + Confirm/Cancel** widget when a proposal is
  pending.
- **Dev/build:** Vite dev server proxies `/ws` to the backend in development; production build emitted to
  `frontend/dist/` and served by the dashboard backend.

## 5. Data flow — *"take over and orbit, 30 m radius, 25 m alt"*
1. Operator types it → browser ws `chat`.
2. Backend → `Agent.propose` → LLM → schema-validated command → backend sends `proposal` → UI shows
   **preview + Confirm**.
3. Operator confirms → ws `confirm` → backend `Agent.execute` → safety service validates
   (geofence/battery/health/mode) and executes **telemetry-gated** (or rejects with a reason).
4. Telemetry **push** streams back (safety → backend → browser); cards/HUD update live; backend narrates
   "orbit established, battery 78%".
5. **ABORT** at any moment → ws `abort` → `Agent.abort()` → safety hands back / holds; UI flips
   `control_state` to MANUAL.

## 6. Error handling (non-negotiables preserved)
- **Video bridge down/unhealthy** → `video_status.ok=false` → frontend shows the Three.js fallback. No
  dead pane.
- **Safety service disconnect** → backend marks telemetry **stale** and tells the browser; UI shows a
  degraded state; ABORT still attempts to send.
- **LLM invalid output** → existing retry-once in `command_gen`; an `ErrorProposal` surfaces as narration
  and is **never executed**.
- **Backend crash / ws drop** → browser shows "disconnected" and **auto-reconnects**.
- Each of the three processes is **independently restartable**; the LLM still cannot bypass the safety
  gate (it acts only through `Agent`→`SafetyClient`→validated API).

## 7. Testing strategy (TDD; Opus subagents; one commit per task)
- **Spike first (plan task 1):** confirm a camera-enabled airframe + **headless EGL rendering on the
  GTX 970** actually produces a gz camera topic — hit the riskiest unknown before building on it. Record
  the airframe name + topic in ROADMAP gotchas.
- **Unit (pytest):**
  - flight-safety: telemetry frames are pushed; replies echo `id`; abort still preempts.
  - SafetyClient: telemetry reaches the subscriber **while** an interleaved command reply still resolves
    by `id`.
  - video bridge: synthetic gz Image → valid JPEG; MJPEG multipart framing; `/health` reflects frame age.
  - dashboard backend: `chat → proposal → confirm → execute`, `abort`, telemetry fan-out — against a
    **fake SafetyClient + fake provider**.
- **Frontend (Vitest):** proposal/confirm rendering, telemetry-card formatting, MJPEG-vs-fallback
  selection logic.
- **Integration (marked `@pytest.mark.integration`, need SITL):** camera airframe → bridge emits real
  JPEG frames; end-to-end NL → dashboard → fly in SITL.

## 8. Repo additions / changes
- **Modify:** `src/flight_safety/server.py` (push + `id`), `src/flight_safety/models.py` &
  `bridge.py` (optional attitude), `src/assistant/safety_client.py` (demux client).
- **New:** `src/video_bridge/` (`bridge.py`, `mjpeg.py`, `config.py`, `__main__.py`);
  `src/dashboard/` (`app.py`, `hub.py`, `config.py`, `__main__.py`); `frontend/` (Vite React app).
- **Tests:** `tests/video_bridge/`, `tests/dashboard/`, additions to `tests/flight_safety/` &
  `tests/assistant/`; frontend Vitest tests under `frontend/`.
- **Docs:** update `ROADMAP.md` (run instructions, gotchas, tick M3), close the relevant items in
  `docs/M1-followups.md` (telemetry push + `id`).

## 9. Open decisions (non-blocking)
- gz-transport Python bindings vs a `gz topic` CLI fallback for the subscriber — resolved by the spike.
- Whether to also **proxy** MJPEG through the dashboard backend for single-origin (deferred; direct
  `<img>` to the bridge is fine for the demo).
- Telemetry push **interval** and whether to switch to event-driven push later (start fixed ~0.5 s).
