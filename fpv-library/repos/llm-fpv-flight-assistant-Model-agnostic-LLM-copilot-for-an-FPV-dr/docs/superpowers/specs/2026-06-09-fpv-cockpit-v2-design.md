# FPV Cockpit v2 — manual control, streaming chat, OSD redesign

- **Date:** 2026-06-09
- **Status:** approved (brainstorm) → spec review pending
- **Branch:** `feat/fpv-cockpit-v2`
- **Builds on:** M3 (FPV web dashboard, merged to `main`). Closes the M1 follow-up "wire `takeover`/`handback` to real OFFBOARD/manual".

## 1. Context & problem

M3 shipped a working dashboard (real gz camera over MJPEG, telemetry HUD, chat→propose→confirm→execute, ABORT), validated live in SITL. Operator feedback:

1. **No manual flight.** "Take control" should let the human actually fly. Today `takeover()`/`handback()` are stubs (both `action.hold()`); there is no setpoint channel anywhere in the stack.
2. **Take-control should be a toggle** (press = you fly, press again = back to the assistant), reflecting live control state.
3. **Chat feels bad:** noticeable delay, no echo of the operator's message, no "thinking" indicator, no streaming, no visible reasoning.
4. **The UI looks rough** — all ad-hoc inline styles, no design system.
5. **Add functionality.**

## 2. Goals / non-goals

**Goals**
- Real, safe **manual keyboard flight** via gate-validated OFFBOARD velocity setpoints.
- A **control toggle** (MANUAL ⇄ ASSISTANT) plus a separate always-on **ABORT**.
- **Streaming chat**: instant echo, thinking indicator, token streaming, visible reasoning, lower latency.
- A **full frontend rebuild** as an immersive FPV cockpit with a small design system.
- Extras: **quick-action buttons, OSD attitude+compass overlay, command/event log, connection/health chips**.

**Non-goals (YAGNI)**
- Gamepad/touch joysticks (keyboard only this round; setpoint API is designed so they can be added later without backend change).
- Map/mission planning, video recording, multi-vehicle.
- Voice, Turkish/T3 (tracked separately).
- A separate chat microservice (see §8 — kept unified deliberately).

## 3. Control model

Three concepts, two of them a binary toggle:

| State | Meaning | Drone mode | Setpoints accepted |
|---|---|---|---|
| **ASSISTANT** (default) | LLM proposes high-level verbs; you confirm | HOLD / AUTO after a verb | no |
| **MANUAL (you)** | You fly with the keyboard | OFFBOARD (browser-driven) | yes |

- **TAKE CONTROL ⇄ RELEASE** — one toggle. Take → enter OFFBOARD, `control_state=manual`, start streaming setpoints. Release → `handback()` (OFFBOARD off → HOLD), `control_state=assistant`.
- **ABORT** — separate emergency, always available: cancel any running command, exit manual, HOLD, `control_state=assistant`, narrate "ABORT — control returned."
- The dashboard hub is the **single source of truth** for `control_state` and pushes a `control_state` frame on every change and on connect. (The legacy LLM `takeover`/`handback` *verbs* are superseded by the explicit toggle and removed from the chat vocabulary to avoid a naming clash; the *bridge* methods are repurposed as the OFFBOARD enter/exit primitives.)

## 4. Manual flight — gate-validated OFFBOARD (safety-critical)

The browser never drives the vehicle directly; every setpoint passes the deterministic gate. The gate stays authoritative.

### 4.1 Bridge (`flight_safety/bridge.py`)
- `takeover()` → `offboard.set_velocity_body(0,0,0,0)`, then `offboard.start()`. Requires armed + airborne; if disarmed/on-ground, raise → dispatcher returns a friendly error ("take off first").
- `set_velocity_body(forward, right, down, yaw_rate_deg_s)` → `offboard.set_velocity_body(VelocityBodyYawspeed(...))`.
- `handback()` → `offboard.stop()` then `action.hold()`.
- Body frame is MAVSDK FRD: forward/right/down m/s, yaw-rate deg/s.

### 4.2 Dispatcher (`flight_safety/dispatcher.py`)
- Tracks `_offboard: bool` (true between `takeover` and `handback`/`abort`).
- `manual_setpoint(forward, right, down, yaw_rate)`:
  - Ignored unless `_offboard`.
  - **Clamp** horizontal/vertical speed to `Limits.max_speed_ms`, yaw-rate to `Limits.max_yaw_rate_dps` (new, default 90).
  - **Geofence brake:** project current position forward by a lookahead (`~1.0 s`) using current yaw; if the projected point is outside the fence polygon, zero `forward`/`right` (keep `down`/`yaw_rate`). Conservative: brake horizontally rather than fly out.
  - Store as the current setpoint; the stream loop (below) sends it.
- **OFFBOARD stream + watchdog:** while `_offboard`, a fixed-rate loop (~20 Hz) pushes the *current* setpoint to the bridge. If the latest `manual_setpoint` is older than `~500 ms`, the current setpoint decays to **zero** (hover) — a dropped browser tab can't fly away, and PX4's OFFBOARD min-rate is satisfied regardless of input rate.
- `abort()` and `handback()` clear `_offboard` and stop the loop.

### 4.3 Server (`flight_safety/server.py`) — new ws messages
- `{"type":"manual","forward":..,"right":..,"down":..,"yaw_rate":..}` → `dispatcher.manual_setpoint(...)`, **no reply** (high-rate, fire-and-forget). Bypasses the single-command "busy" lock (it is not a `command`).
- Toggle reuses the existing `command` path with verbs `takeover`/`handback` (low-rate, replies with status) — no new toggle message needed server-side.

### 4.4 Config (`flight_safety/config.py`)
- Add `Limits.max_yaw_rate_dps: float = 90.0`. `max_speed_ms` already exists and is now enforced for manual.

## 5. Telemetry & control-state

- Telemetry already carries `roll/pitch/yaw` (used by the OSD). No new fields required for OSD.
- `control_state` is **dashboard-owned** and pushed as `{"type":"control_state","who":"manual"|"assistant"}` on change and on connect (the frontend must not infer it from flight mode).

## 6. Streaming chat

### 6.1 Provider (`assistant/llm.py`)
- Add `stream(system, user) -> AsyncIterator[dict]` yielding deltas `{"reply": str?, "thinking": str?}` from the OpenAI-compatible streaming API. `thinking` comes from `delta.reasoning_content` when the model exposes it (e.g. reasoning models); otherwise only `reply` deltas flow. Keep `complete()` for non-streaming callers/tests.

### 6.2 Command generation (`assistant/command_gen.py`)
- **Schema gains `say`** — a short, human-facing sentence:
  - `{"action":"command","say":"Setting up a 20 m orbit here.","command":{…}}`
  - `{"action":"ask","say":"…","question":"…"}`
- `propose_stream(provider, nl, telemetry, on_delta)`:
  - streams deltas to `on_delta(kind, text)` (`kind ∈ {thinking, reply}`),
  - accumulates the reply, extracts JSON at the end, validates the command (retry once on invalid, non-streamed),
  - returns `CommandProposal{command, say}` / `QuestionProposal{say|question}` / `ErrorProposal`.
- `say` is model-agnostic and works even when the model has no separate reasoning channel.
- **Latency:** the agent uses the **last pushed telemetry** the dashboard already holds, instead of a fresh `get_telemetry()` round-trip.

### 6.3 Dashboard ws protocol (browser ⇄ dashboard)

Browser → dashboard:
- `{"type":"chat","text":…}`
- `{"type":"confirm"}` / `{"type":"cancel"}` / `{"type":"abort"}`
- `{"type":"take_control"}` / `{"type":"release_control"}`
- `{"type":"manual","forward":..,"right":..,"down":..,"yaw_rate":..}` (≤20 Hz)
- `{"type":"quick","verb":…,"args":{…}}` (quick-action; same propose/confirm rules)

Dashboard → browser:
- `{"type":"telemetry","data":{…}}` (existing push)
- `{"type":"video_status","ok":…,"url":…}` (existing)
- `{"type":"control_state","who":…}`
- chat stream: `{"type":"chat_start"}` → `{"type":"chat_delta","kind":"thinking"|"reply","text":…}`\* → `{"type":"chat_end"}`
- `{"type":"proposal","command":{…},"say":…}` / `{"type":"narration","text":…}`
- `{"type":"result","status":…,"verb":…,"reason":…}`
- `{"type":"event", …}` optional structured log entries (or the client derives the log from the above)

`SafetyClient` gains `send_manual(...)` (fire-and-forget), `takeover()`, `handback()` (wrap the `command` path). The demuxing reader is unchanged (manual has no reply).

## 7. Frontend — immersive FPV cockpit

Full rebuild of `frontend/src`. Vite + React + TS + react-three-fiber retained.

### 7.1 Design system
- `theme.ts` tokens (colors, spacing, radius, typography, z-layers) + a few primitives (`Panel`, `Chip`, `Button`, `IconButton`). Replaces scattered inline styles. Dark tactical palette, monospace for numerics.

### 7.2 Layout
- Full-bleed `VideoPane` (MJPEG `<img>`, Three.js fallback) as the base layer.
- Floating **TopBar**: health chips (safety link · video · GPS/EKF · battery), MANUAL/ASSISTANT **ControlToggle**, **AbortButton**.
- **OSD overlay** (`components/osd/`): `AttitudeIndicator` (roll/pitch artificial horizon), `CompassTape` (yaw), `LadderAlt` + `LadderSpeed`, center crosshair. Pure functions of telemetry; unit-testable math in `osd/math.ts`.
- **ChatDrawer** (bottom-right): bubbles, instant echo, streaming "thinking…"/reply, proposal card (Confirm/Cancel).
- **QuickActions** bar: Takeoff / RTL / Land / Loiter / Orbit (risky ones go through propose→confirm).
- **EventLog** (collapsible): timestamped commands/proposals/results/aborts/hand-offs.
- **ManualHUD** (visible in MANUAL): key map (W/A/S/D move, Q/E yaw, R/F up/down, Shift boost) + live velocity readout.

### 7.3 Manual input (`useManualControl.ts`)
- Tracks pressed keys; computes a body-frame setpoint each animation frame; sends `manual` frames at a fixed ~20 Hz only while `control_state==manual`; sends a final zero on release/blur. Speeds scaled to `max_speed_ms` (Shift = boost toward the cap). `window.blur`/visibility change → zero + stop.

### 7.4 Socket hook (`useDashboardSocket.ts`)
- Extended for the new protocol: assembles streaming chat into a message list (`user` | `assistant` with `thinking`+`reply`), tracks `control_state`, exposes `takeControl/release/sendManual/quick`, and an event list.

## 8. Services & ports (operator's question)

**Kept unified** in the dashboard backend. Rationale: chat streaming is async I/O (awaits between token chunks) so it does not block telemetry fan-out or the setpoint relay; the `Agent` + `SafetyClient` already live in the dashboard; one browser ws means lower latency and no duplicated telemetry. A separate chat port would add a second connection and shared-state plumbing for no gain at this scale. (Revisit only if the LLM call ever needs hard process isolation.)

Ports unchanged from the M3 live runs: flight-safety `:8765`, video bridge `:8092`, dashboard `:8090` (defaults 8080/8082 are taken on this box by an unrelated panel).

## 9. Testing (TDD)

**Python (pytest, unit):**
- Dispatcher: setpoint clamping (speed + yaw-rate), geofence brake (inside passes, outside zeroes horizontal), setpoints ignored when not OFFBOARD, watchdog decays stale setpoint to zero, `takeover` refused when disarmed.
- Server: `manual` routes to dispatcher with no reply; `takeover`/`handback` replies; `abort` clears offboard.
- Bridge: `takeover/handback/set_velocity_body` call the right MAVSDK offboard methods (fake drone).
- command_gen: `propose_stream` assembles deltas, parses `say`+command, retries once on invalid JSON; `ask` path.
- llm: `stream()` yields reply/thinking deltas from a fake client.

**Frontend (Vitest):**
- `osd/math` (roll/pitch→transform, yaw→compass window, ladder ticks).
- `useManualControl` keys→setpoint mapping, boost, blur→zero, only-when-manual gating.
- `useDashboardSocket` stream assembly (start/delta/end → message), control_state handling.
- ControlToggle behavior, ChatDrawer streaming render, QuickActions confirm flow.

**Live (integration, needs SITL):** extend the dashboard e2e — take control, stream a few setpoints, see the vehicle move, release; stream a chat turn and assert `chat_start/delta/end` + proposal; quick-action confirm. Run in the lighter `cam_test` world.

## 10. Risks / decisions
- **OFFBOARD on ground:** takeover requires airborne; UX is "take off (assistant or quick-action) → take control."
- **Geofence brake granularity:** v1 brakes horizontally on projected breach (simple, safe); per-component projection is a possible refinement, not in scope.
- **Reasoning visibility depends on the model:** `say` always works; live "thinking" tokens appear only when the configured model exposes `reasoning_content`. `AS_MODEL` may be switched to a reasoning model for the full effect.
- **Input authority:** keyboard focus required; `ManualHUD` makes the active state obvious; blur zeroes the stick.
