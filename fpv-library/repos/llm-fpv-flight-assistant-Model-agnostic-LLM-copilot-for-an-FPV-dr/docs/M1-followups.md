# M1 Flight-Safety Service — tracked follow-ups

M1 is complete and validated (39 unit tests + 3 live SITL integration tests; end-to-end
websocket→gate→bridge→PX4 verified). The final holistic review's Critical/Important items
(C1 abort preemption, C2 fail-safe error handling, I3 test isolation, I4 dispatcher tests)
are **fixed**. The items below are deliberately deferred — none block M1, but the M2 (LLM
assistant) and M3 (dashboard) authors should know about them.

## Behavioral stubs (document so M2 isn't surprised)
- ✅ **DONE (Cockpit v2).** ~~`takeover()` is a stub.~~ `takeover()` now enters real **OFFBOARD** (`offboard.set_velocity_body(0,0,0,0)` + `offboard.start()`); `bridge.set_velocity_body(...)` streams body-frame velocity setpoints. Used for **human manual keyboard flight** through the gate (clamp + geofence brake + 500 ms hover watchdog), driven by the dashboard MANUAL⇄ASSISTANT toggle.
- ✅ **DONE (Cockpit v2).** ~~`handback()` returns to HOLD.~~ `handback()` now `offboard.stop()` → `action.hold()` (leaves OFFBOARD cleanly); `abort` still delegates to it (safe HOLD). A true RC/position-manual mode remains a possible future refinement, but HOLD-on-handback is the intended safe state.

## Deferred enforcement (spec §4.1 items not yet wired)
- **Rate limit** (`Settings.command_min_interval_s`) is defined but **not enforced**. Add a timestamp gate in the dispatcher when the assistant can fire commands back-to-back (M2).
- **Speed cap** (`Limits.max_speed_ms`) is defined but unused — latent until a verb carries a speed/velocity parameter.

## API contract gaps for M2/M3
- ✅ **DONE (M3).** ~~No request/response correlation id.~~ The server now echoes an `id` on command/abort/get_telemetry replies (`server.py`), and `SafetyClient` (`src/assistant/safety_client.py`) demultiplexes a single ws by matching replies to requests by `id`, with a FIFO fallback for legacy/no-id servers.
- ✅ **DONE (M3).** ~~No telemetry/event push stream.~~ The flight-safety server now pushes periodic `{"type":"telemetry","data":...}` frames (id-less, sleep-first so request/reply stays deterministic); `SafetyClient.subscribe_telemetry` delivers them, and the dashboard fans them out to the browser HUD.

## Minor / cosmetic
- `ekf_ok` is mapped from `is_local_position_ok` (a proxy, not a dedicated EKF-health flag); fine for SITL, revisit for GPS-denied.
- `goto()` reads position a second time for the AMSL conversion; `do_orbit` ground speed is hardcoded to 3.0 m/s (unrelated to `max_speed_ms`).

## Housekeeping
- Three root-owned junk files (`sudo`, `apt-get`, `update`) sit untracked in the repo root (from an early shell paste mishap). Remove with `sudo rm -f sudo apt-get update` from the project root.
