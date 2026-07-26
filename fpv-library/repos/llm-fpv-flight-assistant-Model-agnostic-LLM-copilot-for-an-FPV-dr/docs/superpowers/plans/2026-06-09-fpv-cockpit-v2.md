# FPV Cockpit v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe manual keyboard flight (gate-validated OFFBOARD), a MANUAL⇄ASSISTANT toggle, streaming chat with visible thinking, and a rebuilt immersive FPV/OSD frontend with quick actions, event log, and health chips.

**Architecture:** The browser never drives the vehicle directly — manual velocity setpoints stream browser → dashboard → safety gate (clamp + geofence brake + hover watchdog) → MAVSDK OFFBOARD, so the deterministic gate stays authoritative. Chat streams over the existing dashboard websocket (kept unified, no separate port). The frontend is rebuilt on a small design system as a full-bleed video cockpit with telemetry-driven OSD overlays.

**Tech Stack:** Python 3.11 (FastAPI, uvicorn, websockets, MAVSDK, pydantic), OpenAI-compatible streaming (OpenRouter), Vite + React + TS + react-three-fiber, Vitest.

**Conventions:** Run Python under `.venv` (`. .venv/bin/activate`); the video bridge runs under system `/usr/bin/python3` (gz bindings). Ports: flight-safety `:8765`, video `:8092`, dashboard `:8090`. Commit after every green step. Body-frame velocity = MAVSDK FRD: `forward`/`right`/`down` m/s, `yaw_rate` deg/s.

---

## File structure

**Safety service (`src/flight_safety/`)**
- `config.py` — add `Limits.max_yaw_rate_dps`.
- `geofence.py` — add `project_latlon()` (pure forward-projection helper).
- `bridge.py` — real `takeover/handback`, new `set_velocity_body`.
- `dispatcher.py` — OFFBOARD state, `manual_setpoint`, `_effective_setpoint`, stream loop + watchdog; route `takeover/handback` verbs through dispatcher methods.
- `server.py` — new `manual` ws message.

**Assistant (`src/assistant/`)**
- `llm.py` — add `stream()`.
- `command_gen.py` — prose-then-JSON system prompt, `say`, `propose_stream()`, drop `takeover/handback` from vocab.
- `safety_client.py` — `last_telemetry` cache, `send_manual`, `takeover`, `handback`.
- `agent.py` — `propose_stream()` using cached telemetry.

**Dashboard (`src/dashboard/`)**
- `hub.py` — emit-based streaming, control-state ownership, take/release/quick.
- `app.py` — route new ws messages, stream via broadcaster, control_state on connect.

**Frontend (`frontend/src/`)**
- `theme.ts`, `components/ui/` (`Panel.tsx`, `Chip.tsx`, `Button.tsx`)
- `types.ts`, `useDashboardSocket.ts`, `useManualControl.ts`
- `osd/math.ts`, `components/osd/` (`AttitudeIndicator.tsx`, `CompassTape.tsx`, `Ladder.tsx`, `Crosshair.tsx`)
- `components/` (`TopBar.tsx`, `ControlToggle.tsx`, `HealthChips.tsx`, `AbortButton.tsx`, `ChatDrawer.tsx`, `QuickActions.tsx`, `ManualHUD.tsx`, `EventLog.tsx`, `VideoPane.tsx`, `FallbackScene.tsx`)
- `App.tsx`

---

# PHASE A — Safety service: manual OFFBOARD

### Task 1: Limits + geofence projection helper

**Files:**
- Modify: `src/flight_safety/config.py`
- Modify: `src/flight_safety/geofence.py`
- Test: `tests/flight_safety/test_geofence.py` (append)

- [ ] **Step 1: Write failing tests**

```python
# tests/flight_safety/test_geofence.py  (append)
from flight_safety.geofence import project_latlon

def test_project_latlon_north():
    # heading 0 (north), 10 m/s forward, 1 s -> ~10 m north (~9e-5 deg lat)
    lat, lon = project_latlon(47.0, 8.0, yaw_deg=0.0, forward=10.0, right=0.0, dt=1.0)
    assert lon == 8.0
    assert abs((lat - 47.0) - (10.0 / 111320.0)) < 1e-7

def test_project_latlon_east_via_right():
    # heading 0, strafe right 10 m/s -> moves east
    lat, lon = project_latlon(47.0, 8.0, yaw_deg=0.0, forward=0.0, right=10.0, dt=1.0)
    assert abs(lat - 47.0) < 1e-9
    assert lon > 8.0
```

- [ ] **Step 2: Run, expect fail** — `pytest tests/flight_safety/test_geofence.py -k project -v` → ImportError.

- [ ] **Step 3: Implement**

```python
# src/flight_safety/config.py — add field to Limits
    max_speed_ms: float = 12.0
    max_yaw_rate_dps: float = 90.0   # manual-control yaw-rate cap (deg/s)
    min_battery_pct: float = 0.20  # reject new commands below 20%
```

```python
# src/flight_safety/geofence.py — append
import math

def project_latlon(lat: float, lon: float, yaw_deg: float,
                   forward: float, right: float, dt: float) -> tuple[float, float]:
    """Project a lat/lon forward by a body-frame horizontal velocity over dt seconds.

    yaw_deg is heading (0 = North, clockwise). Body forward points along heading,
    body right is 90deg clockwise from forward. Flat-earth small-step approximation.
    """
    yaw = math.radians(yaw_deg)
    v_north = forward * math.cos(yaw) - right * math.sin(yaw)
    v_east = forward * math.sin(yaw) + right * math.cos(yaw)
    dlat = (v_north * dt) / 111320.0
    dlon = (v_east * dt) / (111320.0 * math.cos(math.radians(lat)) or 1e-9)
    return lat + dlat, lon + dlon
```

- [ ] **Step 4: Run, expect pass** — `pytest tests/flight_safety/test_geofence.py -k project -v`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(safety): max_yaw_rate_dps limit + project_latlon helper"`

---

### Task 2: Bridge OFFBOARD methods

**Files:**
- Modify: `src/flight_safety/bridge.py` (replace `takeover`/`handback`, add `set_velocity_body`)
- Test: `tests/flight_safety/test_bridge_offboard.py` (create)

- [ ] **Step 1: Write failing tests** (fake drone records offboard calls)

```python
# tests/flight_safety/test_bridge_offboard.py
import pytest
from flight_safety.bridge import FlightBridge

class _Offboard:
    def __init__(self): self.started=False; self.stopped=False; self.vel=None
    async def set_velocity_body(self, v): self.vel=v
    async def start(self): self.started=True
    async def stop(self): self.stopped=True

class _Action:
    def __init__(self): self.held=False
    async def hold(self): self.held=True

class _Drone:
    def __init__(self): self.offboard=_Offboard(); self.action=_Action()

@pytest.fixture
def bridge():
    b = FlightBridge("udpin://0.0.0.0:14540")
    b._drone = _Drone()
    return b

async def test_takeover_starts_offboard(bridge):
    await bridge.takeover()
    assert bridge._drone.offboard.started is True
    assert bridge._drone.offboard.vel is not None  # zero setpoint sent first

async def test_set_velocity_body_forwards(bridge):
    await bridge.set_velocity_body(1.0, 2.0, -0.5, 30.0)
    v = bridge._drone.offboard.vel
    assert (v.forward_m_s, v.right_m_s, v.down_m_s, v.yawspeed_deg_s) == (1.0, 2.0, -0.5, 30.0)

async def test_handback_stops_offboard_and_holds(bridge):
    await bridge.handback()
    assert bridge._drone.offboard.stopped is True
    assert bridge._drone.action.held is True
```

- [ ] **Step 2: Run, expect fail** — `pytest tests/flight_safety/test_bridge_offboard.py -v`.

- [ ] **Step 3: Implement** (replace the stub `takeover`/`handback`, add import + method)

```python
# src/flight_safety/bridge.py
# at top with other mavsdk imports:
from mavsdk.offboard import VelocityBodyYawspeed

# replace the existing takeover()/handback() with:
    async def takeover(self) -> None:
        """Enter OFFBOARD so velocity setpoints drive the vehicle (assistant or human-via-GCS)."""
        await self._drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
        await self._drone.offboard.start()

    async def set_velocity_body(self, forward: float, right: float,
                                down: float, yaw_rate: float) -> None:
        await self._drone.offboard.set_velocity_body(
            VelocityBodyYawspeed(forward, right, down, yaw_rate))

    async def handback(self) -> None:
        """Leave OFFBOARD and park in HOLD (safe autonomous state)."""
        try:
            await self._drone.offboard.stop()
        except Exception:
            pass  # not in offboard -> ignore
        await self._drone.action.hold()
```

- [ ] **Step 4: Run, expect pass** — `pytest tests/flight_safety/test_bridge_offboard.py -v`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(safety): real OFFBOARD takeover/handback + set_velocity_body"`

---

### Task 3: Dispatcher manual setpoint (clamp + geofence brake + watchdog)

**Files:**
- Modify: `src/flight_safety/dispatcher.py`
- Test: `tests/flight_safety/test_dispatcher_manual.py` (create)

- [ ] **Step 1: Write failing tests**

```python
# tests/flight_safety/test_dispatcher_manual.py
import pytest
from flight_safety.config import Limits
from flight_safety.dispatcher import Dispatcher
from flight_safety.models import Telemetry

def _tlm(lat=47.3978, lon=8.5456, yaw=0.0):
    return Telemetry(lat=lat, lon=lon, alt_m=10.0, speed_ms=0.0, battery_pct=1.0,
                     flight_mode="OFFBOARD", armed=True, gps_ok=True, ekf_ok=True, yaw=yaw)

# square geofence around home
FENCE = [(47.3970, 8.5450), (47.3990, 8.5450), (47.3990, 8.5470), (47.3970, 8.5470)]

def _disp(bridge=None):
    return Dispatcher(bridge or object(), Limits(), FENCE)

def test_setpoint_ignored_when_not_offboard():
    d = _disp(); d._tlm_cache = _tlm()
    d.manual_setpoint(5, 0, 0, 0)
    assert d._setpoint == (0.0, 0.0, 0.0, 0.0)

def test_setpoint_clamped_to_limits():
    d = _disp(); d._offboard = True; d._tlm_cache = _tlm()
    d.manual_setpoint(100.0, 0.0, 0.0, 999.0)  # way over
    f, r, dn, yr = d._setpoint
    assert abs((f**2 + r**2) ** 0.5 - 12.0) < 1e-6   # max_speed_ms
    assert yr == 90.0                                 # max_yaw_rate_dps

def test_geofence_brake_zeroes_horizontal_when_projected_outside():
    d = _disp(); d._offboard = True
    # near east edge, pushing further east (right, heading north -> east)
    d._tlm_cache = _tlm(lat=47.3980, lon=8.54699, yaw=0.0)
    d.manual_setpoint(0.0, 10.0, -1.0, 0.0)
    f, r, dn, yr = d._setpoint
    assert f == 0.0 and r == 0.0   # braked
    assert dn == -1.0              # vertical preserved

def test_effective_setpoint_decays_when_stale():
    d = _disp(); d._offboard = True; d._tlm_cache = _tlm()
    d.manual_setpoint(5.0, 0.0, 0.0, 0.0)
    assert d._effective_setpoint(now=d._setpoint_ts + 0.1) == d._setpoint
    assert d._effective_setpoint(now=d._setpoint_ts + 1.0) == (0.0, 0.0, 0.0, 0.0)
```

- [ ] **Step 2: Run, expect fail** — `pytest tests/flight_safety/test_dispatcher_manual.py -v`.

- [ ] **Step 3: Implement** (add imports, state in `__init__`, methods)

```python
# src/flight_safety/dispatcher.py
import math
import time
from flight_safety.geofence import inside_geofence, project_latlon
# (keep existing imports)

# in __init__ add:
        self._offboard = False
        self._setpoint = (0.0, 0.0, 0.0, 0.0)
        self._setpoint_ts = 0.0
        self._tlm_cache = None  # type: ignore
        self._stream_task = None
        self._clock = time.monotonic
        self._stale_s = 0.5

# new methods:
    def manual_setpoint(self, forward: float, right: float,
                        down: float, yaw_rate: float) -> None:
        """Validate + store a manual velocity setpoint (no-op unless OFFBOARD)."""
        if not self._offboard:
            return
        lim = self._limits
        # clamp horizontal magnitude, vertical, yaw-rate
        horiz = math.hypot(forward, right)
        if horiz > lim.max_speed_ms and horiz > 0:
            scale = lim.max_speed_ms / horiz
            forward, right = forward * scale, right * scale
        down = max(-lim.max_speed_ms, min(lim.max_speed_ms, down))
        yaw_rate = max(-lim.max_yaw_rate_dps, min(lim.max_yaw_rate_dps, yaw_rate))
        # geofence brake: if projected position would be outside, zero horizontal
        t = self._tlm_cache
        if t is not None and self._geofence:
            plat, plon = project_latlon(t.lat, t.lon, t.yaw, forward, right, dt=1.0)
            if not inside_geofence(plat, plon, self._geofence):
                forward, right = 0.0, 0.0
        self._setpoint = (forward, right, down, yaw_rate)
        self._setpoint_ts = self._clock()

    def _effective_setpoint(self, now: float) -> tuple[float, float, float, float]:
        if now - self._setpoint_ts > self._stale_s:
            return (0.0, 0.0, 0.0, 0.0)
        return self._setpoint
```

- [ ] **Step 4: Run, expect pass** — `pytest tests/flight_safety/test_dispatcher_manual.py -v`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(safety): manual_setpoint clamp + geofence brake + watchdog decay"`

---

### Task 4: Dispatcher takeover/handback + OFFBOARD stream loop

**Files:**
- Modify: `src/flight_safety/dispatcher.py`
- Test: `tests/flight_safety/test_dispatcher_offboard.py` (create)

- [ ] **Step 1: Write failing tests**

```python
# tests/flight_safety/test_dispatcher_offboard.py
import asyncio, pytest
from flight_safety.config import Limits
from flight_safety.dispatcher import Dispatcher
from flight_safety.models import Telemetry

class _Bridge:
    def __init__(self): self.took=False; self.gave=False; self.vels=[]
    async def takeover(self): self.took=True
    async def handback(self): self.gave=True
    async def set_velocity_body(self, f, r, d, yr): self.vels.append((f, r, d, yr))
    async def read_telemetry(self):
        return Telemetry(lat=47.3978, lon=8.5456, alt_m=10.0, speed_ms=0.0,
                         battery_pct=1.0, flight_mode="OFFBOARD", armed=True,
                         gps_ok=True, ekf_ok=True, yaw=0.0)

async def test_takeover_sets_offboard_and_streams_zero(monkeypatch):
    b = _Bridge()
    d = Dispatcher(b, Limits(), [])
    d._stream_hz = 100  # fast loop for the test
    await d.takeover()
    assert b.took is True and d._offboard is True
    await asyncio.sleep(0.05)   # let the loop tick
    assert b.vels and b.vels[-1] == (0.0, 0.0, 0.0, 0.0)
    await d.handback()
    assert b.gave is True and d._offboard is False

async def test_handback_stops_stream(monkeypatch):
    b = _Bridge(); d = Dispatcher(b, Limits(), []); d._stream_hz = 100
    await d.takeover(); await d.handback()
    n = len(b.vels); await asyncio.sleep(0.05)
    assert len(b.vels) == n  # no more setpoints after handback
```

- [ ] **Step 2: Run, expect fail** — `pytest tests/flight_safety/test_dispatcher_offboard.py -v`.

- [ ] **Step 3: Implement** (add `_stream_hz`, `takeover`, `handback`, `_stream_loop`; route verbs; update `abort`)

```python
# src/flight_safety/dispatcher.py
# in __init__ add:
        self._stream_hz = 20

    async def takeover(self) -> None:
        await self._bridge.takeover()
        self._offboard = True
        self._setpoint = (0.0, 0.0, 0.0, 0.0)
        self._setpoint_ts = self._clock()
        if self._stream_task is None or self._stream_task.done():
            self._stream_task = asyncio.create_task(self._stream_loop())

    async def handback(self) -> None:
        self._offboard = False
        if self._stream_task is not None:
            self._stream_task.cancel()
            self._stream_task = None
        await self._bridge.handback()

    async def _stream_loop(self) -> None:
        period = 1.0 / self._stream_hz
        try:
            ticks = 0
            while self._offboard:
                # refresh telemetry cache ~5 Hz for the geofence brake
                if ticks % max(1, self._stream_hz // 5) == 0:
                    try:
                        self._tlm_cache = await self._bridge.read_telemetry()
                    except Exception:
                        pass
                f, r, dn, yr = self._effective_setpoint(self._clock())
                try:
                    await self._bridge.set_velocity_body(f, r, dn, yr)
                except Exception:
                    pass
                ticks += 1
                await asyncio.sleep(period)
        except asyncio.CancelledError:
            pass
```

Add `import asyncio` at top. Then route the verbs and abort:

```python
# in _execute(): replace the takeover/handback branches
        elif cmd.verb == "takeover":
            await self.takeover()
        elif cmd.verb == "handback":
            await self.handback()

# replace abort():
    async def abort(self) -> None:
        """Immediate safe state: leave OFFBOARD, hand control back / hold."""
        await self.handback()
```

- [ ] **Step 4: Run, expect pass** — `pytest tests/flight_safety/test_dispatcher_offboard.py tests/flight_safety/test_dispatcher_manual.py -v`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(safety): OFFBOARD stream loop, takeover/handback dispatcher, abort->handback"`

---

### Task 5: Server `manual` ws message

**Files:**
- Modify: `src/flight_safety/server.py`
- Test: `tests/flight_safety/test_server_manual.py` (create)

- [ ] **Step 1: Write failing test** (uses FastAPI TestClient websocket)

```python
# tests/flight_safety/test_server_manual.py
from fastapi.testclient import TestClient
from flight_safety.server import build_app

class _Disp:
    def __init__(self): self.manual=[]
    async def telemetry(self): return {"alt_m": 1.0}
    def manual_setpoint(self, f, r, d, yr): self.manual.append((f, r, d, yr))
    async def handle(self, cmd): return {"status": "executed", "verb": cmd.get("verb")}
    async def abort(self): pass

def test_manual_message_routes_to_dispatcher_no_reply():
    disp = _Disp()
    app = build_app(disp, telemetry_interval_s=999)  # suppress push noise
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "manual", "forward": 1.0, "right": 2.0, "down": 0.0, "yaw_rate": 5.0})
        ws.send_json({"type": "get_telemetry", "id": "x"})  # round-trip to flush
        reply = ws.receive_json()
        assert reply.get("id") == "x"
    assert disp.manual == [(1.0, 2.0, 0.0, 5.0)]
```

- [ ] **Step 2: Run, expect fail** — `pytest tests/flight_safety/test_server_manual.py -v`.

- [ ] **Step 3: Implement** (add a branch in the ws message loop, before the `else`)

```python
# src/flight_safety/server.py — inside the `while True` message loop
                elif kind == "manual":
                    dispatcher.manual_setpoint(
                        float(msg.get("forward", 0.0)), float(msg.get("right", 0.0)),
                        float(msg.get("down", 0.0)), float(msg.get("yaw_rate", 0.0)))
                    # high-rate, fire-and-forget: no reply
```

- [ ] **Step 4: Run, expect pass** — `pytest tests/flight_safety/test_server_manual.py -v`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(safety): manual setpoint ws message (fire-and-forget)"`

---

# PHASE B — Assistant: streaming chat

### Task 6: LLM streaming

**Files:**
- Modify: `src/assistant/llm.py`
- Test: `tests/assistant/test_llm_stream.py` (create)

- [ ] **Step 1: Write failing test** (fake AsyncOpenAI-style client)

```python
# tests/assistant/test_llm_stream.py
import pytest
from types import SimpleNamespace
from assistant.llm import OpenRouterProvider

def _chunk(content=None, reasoning=None):
    delta = SimpleNamespace(content=content, reasoning_content=reasoning)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

class _Stream:
    def __init__(self, chunks): self._chunks=chunks
    def __aiter__(self):
        async def gen():
            for c in self._chunks: yield c
        return gen()

class _Completions:
    async def create(self, **kw):
        assert kw.get("stream") is True
        return _Stream([_chunk(reasoning="think "), _chunk(content="Hi "), _chunk(content="there")])

class _Client:
    chat = SimpleNamespace(completions=_Completions())

async def test_stream_yields_reply_and_thinking():
    p = OpenRouterProvider(model="m", client=_Client())
    out = [d async for d in p.stream("sys", "user")]
    assert {"thinking": "think "} in out
    assert {"reply": "Hi "} in out and {"reply": "there"} in out
```

- [ ] **Step 2: Run, expect fail** — `pytest tests/assistant/test_llm_stream.py -v`.

- [ ] **Step 3: Implement** (append method to `OpenRouterProvider`)

```python
# src/assistant/llm.py — add to OpenRouterProvider
    async def stream(self, system: str, user: str):
        """Yield {'reply': str} and/or {'thinking': str} deltas as they arrive."""
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0, stream=True)
        async for chunk in stream:
            delta = chunk.choices[0].delta
            think = getattr(delta, "reasoning_content", None)
            if think:
                yield {"thinking": think}
            if getattr(delta, "content", None):
                yield {"reply": delta.content}
```

Also extend the `Protocol`:

```python
# src/assistant/llm.py — LLMProvider Protocol
class LLMProvider(Protocol):
    async def complete(self, system: str, user: str) -> str: ...
    def stream(self, system: str, user: str): ...
```

- [ ] **Step 4: Run, expect pass** — `pytest tests/assistant/test_llm_stream.py -v`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(assistant): streaming LLM completions (reply + reasoning deltas)"`

---

### Task 7: command_gen — say + propose_stream

**Files:**
- Modify: `src/assistant/command_gen.py`
- Test: `tests/assistant/test_command_gen_stream.py` (create)

- [ ] **Step 1: Write failing tests**

```python
# tests/assistant/test_command_gen_stream.py
import pytest
from assistant.command_gen import propose_stream, CommandProposal, QuestionProposal

class _Provider:
    def __init__(self, text): self._text=text
    async def stream(self, system, user):
        for ch in self._text:   # stream char-by-char
            yield {"reply": ch}
    async def complete(self, system, user): return self._text

async def _collect(text):
    seen=[]
    async def on_delta(kind, t): seen.append((kind, t))
    res = await propose_stream(_Provider(text), "go", {}, on_delta)
    return res, seen

async def test_prose_then_command_parsed_and_say_streamed():
    text = 'Holding position now.\n{"action":"command","command":{"verb":"loiter"}}'
    res, seen = await _collect(text)
    assert isinstance(res, CommandProposal)
    assert res.command == {"verb": "loiter"}
    assert res.say.strip() == "Holding position now."
    # the prose (not the JSON) was streamed as reply deltas
    streamed = "".join(t for k, t in seen if k == "reply")
    assert "Holding position now." in streamed
    assert "{" not in streamed

async def test_ask_path():
    text = 'Where to?\n{"action":"ask","question":"Which location?"}'
    res, _ = await _collect(text)
    assert isinstance(res, QuestionProposal)
    assert res.question == "Which location?"
```

- [ ] **Step 2: Run, expect fail** — `pytest tests/assistant/test_command_gen_stream.py -v`.

- [ ] **Step 3: Implement** — update system prompt (prose then JSON, drop takeover/handback), add `say` to dataclasses, add `propose_stream`, robust JSON extraction.

```python
# src/assistant/command_gen.py
_VERB_HELP = """\
Allowed commands (emit ONE, with exact fields):
- arm_takeoff: {"verb":"arm_takeoff","alt":<m, 0-120>}
- goto: {"verb":"goto","lat":<deg>,"lon":<deg>,"alt":<m,0-120>}
- orbit: {"verb":"orbit","radius":<m,0-200>,"alt":<m,0-120>,"center":[<lat>,<lon>] or omit}
- loiter: {"verb":"loiter"}
- return_to_launch: {"verb":"return_to_launch"}
- land: {"verb":"land"}"""

_SYSTEM = f"""You are a UAV flight-command translator. First write ONE short sentence to the \
operator describing what you will do (or what you need). Then, on a NEW LINE, output ONLY a JSON \
object and nothing after it.
The JSON is either {{"action":"command","command":{{...}}}} using exactly one allowed command,
or {{"action":"ask","question":"..."}} if the request is ambiguous or missing required values.
{_VERB_HELP}
Never invent coordinates. If the user references a place you don't have coordinates for, ask."""


@dataclass
class CommandProposal:
    command: dict
    say: str = ""

@dataclass
class QuestionProposal:
    question: str
    say: str = ""

@dataclass
class ErrorProposal:
    reason: str
    say: str = ""


def _extract_json(text: str) -> tuple[str, dict]:
    """Return (prose_before_json, parsed_json). Finds the first balanced {...}."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no json object found")
    prose = text[:start].strip().strip("`").strip()
    return prose, json.loads(text[start:end + 1])


async def propose_stream(provider, nl: str, telemetry: dict, on_delta):
    """Stream prose to on_delta('reply'/'thinking'); parse the trailing JSON command."""
    user = f"Operator request: {nl}\nCurrent telemetry: {json.dumps(telemetry)}"
    acc = ""
    seen_brace = False
    async for d in provider.stream(_SYSTEM, user):
        if "thinking" in d:
            await on_delta("thinking", d["thinking"])
        if "reply" in d:
            chunk = d["reply"]
            acc += chunk
            if not seen_brace:
                bi = chunk.find("{")
                if bi < 0:
                    await on_delta("reply", chunk)
                else:
                    if bi > 0:
                        await on_delta("reply", chunk[:bi])
                    seen_brace = True
    try:
        prose, obj = _extract_json(acc)
    except (ValueError, IndexError):
        # one non-streamed retry
        raw = await provider.complete(
            _SYSTEM, "Your previous reply had no valid JSON. Re-send prose + JSON.")
        try:
            prose, obj = _extract_json(raw)
        except (ValueError, IndexError):
            return ErrorProposal(reason="no valid JSON after retry")
    if obj.get("action") == "ask":
        return QuestionProposal(question=str(obj.get("question", "Could you clarify?")), say=prose)
    if obj.get("action") == "command":
        cmd = obj.get("command", {})
        try:
            parse_command(cmd)
        except ValidationError as e:
            return ErrorProposal(reason=f"invalid command: {e.errors()[0]['msg']}", say=prose)
        return CommandProposal(command=cmd, say=prose)
    return ErrorProposal(reason="missing or unknown 'action'", say=prose)
```

Keep the existing non-streaming `propose()` for back-compat (tests rely on it); just leave it in place.

- [ ] **Step 4: Run, expect pass** — `pytest tests/assistant/test_command_gen_stream.py tests/assistant/ -v`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(assistant): propose_stream with prose say + JSON; drop takeover/handback from vocab"`

---

### Task 8: SafetyClient — last_telemetry, send_manual, takeover/handback

**Files:**
- Modify: `src/assistant/safety_client.py`
- Test: `tests/assistant/test_safety_client_manual.py` (create)

- [ ] **Step 1: Write failing tests** (fake ws captures sent frames)

```python
# tests/assistant/test_safety_client_manual.py
import json, asyncio, pytest
from assistant.safety_client import SafetyClient

class _WS:
    def __init__(self): self.sent=[]
    async def send(self, s): self.sent.append(json.loads(s))
    async def close(self): pass

async def test_send_manual_fire_and_forget():
    c = SafetyClient("ws://x"); c._ws=_WS()
    c._reader = asyncio.create_task(asyncio.sleep(3600))  # appear "connected"
    await c.send_manual(1.0, 2.0, 0.0, 5.0)
    assert c._ws.sent[-1] == {"type": "manual", "forward": 1.0, "right": 2.0, "down": 0.0, "yaw_rate": 5.0}
    assert "id" not in c._ws.sent[-1]
    c._reader.cancel()

def test_last_telemetry_updates_from_push():
    c = SafetyClient("ws://x")
    c._dispatch({"type": "telemetry", "data": {"alt_m": 5.0}})
    assert c.last_telemetry == {"alt_m": 5.0}
```

- [ ] **Step 2: Run, expect fail** — `pytest tests/assistant/test_safety_client_manual.py -v`.

- [ ] **Step 3: Implement** (add `last_telemetry`, update in `_dispatch`, add methods)

```python
# src/assistant/safety_client.py
# in __init__ add:
        self.last_telemetry: dict | None = None

# in _dispatch, inside the telemetry branch, after computing `data`:
            if data is not None:
                self.last_telemetry = data
                for cb in self._telemetry_subs:
                    ...

# new public methods:
    async def send_manual(self, forward: float, right: float,
                          down: float, yaw_rate: float) -> None:
        if self._reader is None or self._reader.done():
            return  # link down -> drop setpoint (watchdog will hover)
        await self._ws.send(json.dumps({"type": "manual", "forward": forward,
                                        "right": right, "down": down, "yaw_rate": yaw_rate}))

    async def takeover(self) -> dict:
        return await self.send_command({"verb": "takeover"})

    async def handback(self) -> dict:
        return await self.send_command({"verb": "handback"})
```

- [ ] **Step 4: Run, expect pass** — `pytest tests/assistant/test_safety_client_manual.py tests/assistant/ -v`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(assistant): SafetyClient last_telemetry + send_manual + takeover/handback"`

---

# PHASE C — Dashboard backend

### Task 9: Agent.propose_stream

**Files:**
- Modify: `src/assistant/agent.py`
- Test: `tests/assistant/test_agent_stream.py` (create)

- [ ] **Step 1: Write failing test**

```python
# tests/assistant/test_agent_stream.py
import pytest
from assistant.agent import Agent
from assistant.command_gen import CommandProposal

class _Client:
    def __init__(self): self.last_telemetry={"alt_m": 3.0}; self.tcalled=False
    async def get_telemetry(self): self.tcalled=True; return {"alt_m": 9.0}

class _Provider:
    async def stream(self, s, u):
        yield {"reply": 'ok\n{"action":"command","command":{"verb":"loiter"}}'}
    async def complete(self, s, u): return ""

async def test_propose_stream_uses_cached_telemetry():
    c = _Client(); a = Agent(_Provider(), c)
    deltas=[]
    res = await a.propose_stream("hold", lambda k, t: deltas.append((k, t)))
    assert isinstance(res, CommandProposal) and res.command == {"verb": "loiter"}
    assert c.tcalled is False  # used cached last_telemetry, no extra round-trip
```

- [ ] **Step 2: Run, expect fail** — `pytest tests/assistant/test_agent_stream.py -v`.

- [ ] **Step 3: Implement** (note: `on_delta` may be sync or async — wrap)

```python
# src/assistant/agent.py
import inspect
from assistant.command_gen import propose, propose_stream

class Agent:
    def __init__(self, provider, client) -> None:
        self._provider = provider
        self._client = client

    async def propose(self, nl: str):
        telemetry = self._client.last_telemetry or await self._client.get_telemetry()
        return await propose(self._provider, nl, telemetry)

    async def propose_stream(self, nl: str, on_delta):
        telemetry = self._client.last_telemetry or await self._client.get_telemetry()
        async def _emit(kind, text):
            r = on_delta(kind, text)
            if inspect.isawaitable(r):
                await r
        return await propose_stream(self._provider, nl, telemetry, _emit)

    async def execute(self, command: dict) -> dict:
        return await self._client.send_command(command)

    async def abort(self) -> dict:
        return await self._client.abort()
```

- [ ] **Step 4: Run, expect pass** — `pytest tests/assistant/test_agent_stream.py tests/assistant/ -v`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(assistant): Agent.propose_stream using cached telemetry"`

---

### Task 10: Hub — emit-based streaming + control state + quick + take/release

**Files:**
- Modify: `src/dashboard/hub.py`
- Test: `tests/dashboard/test_hub.py` (rewrite/extend)

- [ ] **Step 1: Write failing tests**

```python
# tests/dashboard/test_hub.py  (replace contents)
import pytest
from dashboard.hub import DashboardHub
from assistant.command_gen import CommandProposal, QuestionProposal

class _Agent:
    def __init__(self, proposal): self._p=proposal; self.executed=None
    async def propose_stream(self, nl, on_delta):
        await on_delta("reply", "doing it"); return self._p
    async def execute(self, cmd): self.executed=cmd; return {"status": "executed", "verb": cmd["verb"]}
    async def abort(self): return {"status": "aborted"}

class _Client:
    def __init__(self): self.cmds=[]
    async def takeover(self): self.cmds.append("takeover"); return {"status": "executed", "verb": "takeover"}
    async def handback(self): self.cmds.append("handback"); return {"status": "executed", "verb": "handback"}

async def _emit_collect():
    frames=[]
    async def emit(f): frames.append(f)
    return frames, emit

async def test_chat_streams_then_proposal():
    hub = DashboardHub(_Agent(CommandProposal({"verb": "loiter"}, say="doing it")), _Client())
    frames, emit = await _emit_collect()
    await hub.handle_chat("hold", emit)
    kinds = [f["type"] for f in frames]
    assert kinds[0] == "chat_start" and "chat_delta" in kinds and "chat_end" in kinds
    assert frames[-1]["type"] == "proposal" and frames[-1]["command"] == {"verb": "loiter"}

async def test_take_control_sets_manual_state():
    cl=_Client(); hub = DashboardHub(_Agent(None), cl)
    frames, emit = await _emit_collect()
    await hub.handle_take_control(emit)
    assert "takeover" in cl.cmds
    assert {"type": "control_state", "who": "manual"} in frames

async def test_release_sets_assistant_state():
    cl=_Client(); hub = DashboardHub(_Agent(None), cl)
    frames, emit = await _emit_collect()
    await hub.handle_release_control(emit)
    assert "handback" in cl.cmds
    assert {"type": "control_state", "who": "assistant"} in frames

async def test_quick_makes_proposal():
    hub = DashboardHub(_Agent(None), _Client())
    frames, emit = await _emit_collect()
    await hub.handle_quick("arm_takeoff", {"alt": 10}, emit)
    assert frames[-1]["type"] == "proposal" and frames[-1]["command"]["verb"] == "arm_takeoff"
    f2, emit2 = await _emit_collect()
    await hub.handle_confirm(emit2)
    assert any(f["type"] == "result" for f in f2)
```

- [ ] **Step 2: Run, expect fail** — `pytest tests/dashboard/test_hub.py -v`.

- [ ] **Step 3: Implement** (rewrite hub: emit callback; `control` state tracked)

```python
# src/dashboard/hub.py
from assistant.command_gen import CommandProposal, QuestionProposal, ErrorProposal


class DashboardHub:
    """Translate browser messages into Agent/SafetyClient calls; emit UI frames.

    `emit` is an async callback (one frame at a time) provided by the transport.
    Owns the authoritative control_state.
    """

    def __init__(self, agent, client) -> None:
        self._agent = agent
        self._client = client
        self._pending: dict | None = None
        self.control = "assistant"

    async def handle_chat(self, nl: str, emit) -> None:
        await emit({"type": "chat_start"})
        async def on_delta(kind, text):
            await emit({"type": "chat_delta", "kind": kind, "text": text})
        proposal = await self._agent.propose_stream(nl, on_delta)
        await emit({"type": "chat_end"})
        await self._present(proposal, emit)

    async def _present(self, proposal, emit) -> None:
        if isinstance(proposal, CommandProposal):
            self._pending = proposal.command
            await emit({"type": "proposal", "command": proposal.command, "say": proposal.say})
        elif isinstance(proposal, QuestionProposal):
            await emit({"type": "narration", "text": proposal.say or proposal.question})
        elif isinstance(proposal, ErrorProposal):
            await emit({"type": "narration", "text": f"Could not act: {proposal.reason}"})

    async def handle_quick(self, verb: str, args: dict, emit) -> None:
        self._pending = {"verb": verb, **(args or {})}
        await emit({"type": "proposal", "command": self._pending,
                    "say": f"Quick action: {verb}"})

    async def handle_confirm(self, emit) -> None:
        if self._pending is None:
            await emit({"type": "narration", "text": "Nothing to confirm."}); return
        cmd, self._pending = self._pending, None
        result = await self._agent.execute(cmd)
        await emit({"type": "result", **result})
        await emit({"type": "narration", "text": _narrate(result)})

    async def handle_cancel(self, emit) -> None:
        self._pending = None
        await emit({"type": "narration", "text": "Command cancelled."})

    async def handle_take_control(self, emit) -> None:
        result = await self._client.takeover()
        if result.get("status") == "executed":
            self.control = "manual"
            await emit({"type": "control_state", "who": "manual"})
            await emit({"type": "narration", "text": "You have manual control."})
        else:
            await emit({"type": "narration",
                        "text": f"Could not take control: {result.get('reason', 'unavailable')}"})

    async def handle_release_control(self, emit) -> None:
        result = await self._client.handback()
        self.control = "assistant"
        await emit({"type": "control_state", "who": "assistant"})
        await emit({"type": "narration", "text": "Control returned to assistant."})

    async def handle_abort(self, emit) -> None:
        result = await self._agent.abort()
        self._pending = None
        self.control = "assistant"
        await emit({"type": "result", **result})
        await emit({"type": "control_state", "who": "assistant"})
        await emit({"type": "narration", "text": "ABORT — control returned to pilot."})


def _narrate(result: dict) -> str:
    status = result.get("status")
    if status == "executed":
        return f"Executed {result.get('verb', 'command')}."
    if status == "rejected":
        return f"Rejected: {result.get('reason', 'unsafe')}."
    if status == "error":
        return f"Error: {result.get('reason', 'unknown')}."
    return str(result)
```

- [ ] **Step 4: Run, expect pass** — `pytest tests/dashboard/test_hub.py -v`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(dashboard): emit-based streaming hub with control-state, quick, take/release"`

---

### Task 11: App ws routing for the new protocol

**Files:**
- Modify: `src/dashboard/app.py` (the `/ws` handler + `build_app` signature now needs the client)
- Modify: `src/dashboard/__main__.py` (pass client to build_app; hub takes client)
- Test: `tests/dashboard/test_app_ws.py` (create)

- [ ] **Step 1: Write failing test** (in-process app with fakes)

```python
# tests/dashboard/test_app_ws.py
from fastapi.testclient import TestClient
from dashboard.app import build_app, Broadcaster
from dashboard.hub import DashboardHub

class _Agent:
    async def propose_stream(self, nl, on_delta): await on_delta("reply", "ok"); 
    async def execute(self, c): return {"status": "executed", "verb": c["verb"]}
    async def abort(self): return {"status": "aborted"}
from assistant.command_gen import CommandProposal
class _Agent2(_Agent):
    async def propose_stream(self, nl, on_delta):
        await on_delta("reply", "ok"); return CommandProposal({"verb": "loiter"}, say="ok")

class _Client:
    async def takeover(self): return {"status": "executed", "verb": "takeover"}
    async def handback(self): return {"status": "executed", "verb": "handback"}
    sent=[]
    async def send_manual(self, f, r, d, yr): _Client.sent.append((f, r, d, yr))

def test_chat_streams_over_ws():
    hub = DashboardHub(_Agent2(), _Client())
    app = build_app(hub, "http://v/stream.mjpg", broadcaster=Broadcaster(), client=_Client())
    with TestClient(app).websocket_connect("/ws") as ws:
        # drain connect frames (video_status + control_state) then chat
        ws.send_json({"type": "chat", "text": "hold"})
        types=set()
        for _ in range(12):
            types.add(ws.receive_json()["type"])
            if "proposal" in types: break
        assert {"chat_start", "chat_delta", "chat_end", "proposal"} <= types

def test_manual_routes_to_client():
    _Client.sent.clear()
    hub = DashboardHub(_Agent2(), _Client())
    app = build_app(hub, "http://v/stream.mjpg", broadcaster=Broadcaster(), client=_Client())
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "manual", "forward": 1.0, "right": 0.0, "down": 0.0, "yaw_rate": 0.0})
        ws.send_json({"type": "cancel"})  # flush
        for _ in range(8):
            if ws.receive_json()["type"] == "narration": break
    assert _Client.sent and _Client.sent[-1] == (1.0, 0.0, 0.0, 0.0)
```

- [ ] **Step 2: Run, expect fail** — `pytest tests/dashboard/test_app_ws.py -v`.

- [ ] **Step 3: Implement** — `build_app(hub, video_stream_url, broadcaster=None, static_dir=None, client=None)`; in the `/ws` handler send `control_state` on connect, route messages with `emit = broadcaster.broadcast` (fallback to per-socket send when no broadcaster), route `manual` to `client.send_manual`.

```python
# src/dashboard/app.py — inside the /ws handler, after accept + registering socket
        # send current video + control state on connect
        await send({"type": "video_status", "ok": False, "url": video_stream_url})
        await send({"type": "control_state", "who": hub.control})

        async def emit(frame: dict) -> None:
            if broadcaster is not None:
                await broadcaster.broadcast(frame)
            else:
                await send(frame)

        try:
            while True:
                msg = await socket.receive_json()
                t = msg.get("type")
                try:
                    if t == "chat":
                        await hub.handle_chat(msg.get("text", ""), emit)
                    elif t == "confirm":
                        await hub.handle_confirm(emit)
                    elif t == "cancel":
                        await hub.handle_cancel(emit)
                    elif t == "abort":
                        await hub.handle_abort(emit)
                    elif t == "take_control":
                        await hub.handle_take_control(emit)
                    elif t == "release_control":
                        await hub.handle_release_control(emit)
                    elif t == "quick":
                        await hub.handle_quick(msg.get("verb", ""), msg.get("args", {}), emit)
                    elif t == "manual" and client is not None:
                        await client.send_manual(
                            float(msg.get("forward", 0.0)), float(msg.get("right", 0.0)),
                            float(msg.get("down", 0.0)), float(msg.get("yaw_rate", 0.0)))
                except Exception as e:  # dead safety link -> narrate, don't drop socket
                    await send({"type": "narration", "text": f"Link error: {e}"})
        except WebSocketDisconnect:
            ...
```

Update `__main__.py`: `hub = DashboardHub(agent, client)` and `build_app(hub, dash.video_stream_url, broadcaster=broadcaster, static_dir=..., client=client)`.

- [ ] **Step 4: Run, expect pass** — `pytest tests/dashboard/test_app_ws.py tests/dashboard/ -v`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(dashboard): ws routing for streaming chat, take/release, manual, quick"`

---

# PHASE D — Frontend rebuild (immersive FPV cockpit)

> Apply the **frontend-design** skill for visual polish while implementing these tasks. Keep all logic in the hooks/`osd/math.ts` so it stays unit-testable. Dark tactical theme, monospace numerics.

### Task 12: Design system (theme + UI primitives)

**Files:**
- Create: `frontend/src/theme.ts`, `frontend/src/components/ui/Panel.tsx`, `Chip.tsx`, `Button.tsx`
- Test: `frontend/src/components/ui/Chip.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
// frontend/src/components/ui/Chip.test.tsx
import { render, screen } from "@testing-library/react";
import { Chip } from "./Chip";
test("renders label and status color", () => {
  render(<Chip label="LINK" status="ok" />);
  expect(screen.getByText("LINK")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run, expect fail** — `npm --prefix frontend test -- Chip`.

- [ ] **Step 3: Implement**

```ts
// frontend/src/theme.ts
export const theme = {
  color: { bg: "#05080d", panel: "rgba(13,18,28,0.82)", border: "#1f2a3a",
           text: "#e6edf3", dim: "#8b9bb0", accent: "#3ddc97", warn: "#f5b945",
           danger: "#ff4d4f", ok: "#3ddc97", lost: "#6b7787" },
  radius: { sm: 6, md: 10, lg: 16 },
  space: (n: number) => n * 4,
  font: { ui: "Inter, system-ui, sans-serif", mono: "'JetBrains Mono', ui-monospace, monospace" },
  z: { video: 0, osd: 10, hud: 20, panel: 30, modal: 40 },
} as const;
export type Status = "ok" | "warn" | "lost";
```

```tsx
// frontend/src/components/ui/Chip.tsx
import { theme, type Status } from "../../theme";
const dot: Record<Status, string> = { ok: theme.color.ok, warn: theme.color.warn, lost: theme.color.lost };
export function Chip({ label, value, status = "ok" }: { label: string; value?: string; status?: Status }) {
  return (
    <div style={{ display: "inline-flex", gap: 6, alignItems: "center", padding: "4px 9px",
      background: theme.color.panel, border: `1px solid ${theme.color.border}`,
      borderRadius: theme.radius.sm, font: `600 11px ${theme.font.ui}`, color: theme.color.text }}>
      <span style={{ width: 7, height: 7, borderRadius: 7, background: dot[status] }} />
      <span style={{ color: theme.color.dim, letterSpacing: 0.5 }}>{label}</span>
      {value && <span style={{ fontFamily: theme.font.mono }}>{value}</span>}
    </div>
  );
}
```

```tsx
// frontend/src/components/ui/Panel.tsx
import { theme } from "../../theme";
export function Panel({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <div style={{ background: theme.color.panel, border: `1px solid ${theme.color.border}`,
    borderRadius: theme.radius.md, backdropFilter: "blur(6px)", ...style }}>{children}</div>;
}
```

```tsx
// frontend/src/components/ui/Button.tsx
import { theme } from "../../theme";
type V = "default" | "accent" | "danger";
const bg: Record<V, string> = { default: "#16202e", accent: theme.color.accent, danger: theme.color.danger };
export function Button({ children, onClick, variant = "default", title }:
  { children: React.ReactNode; onClick?: () => void; variant?: V; title?: string }) {
  return <button onClick={onClick} title={title} style={{
    padding: "8px 12px", border: `1px solid ${theme.color.border}`, borderRadius: theme.radius.sm,
    background: bg[variant], color: variant === "accent" ? "#04130b" : theme.color.text,
    font: `700 12px ${theme.font.ui}`, cursor: "pointer" }}>{children}</button>;
}
```

- [ ] **Step 4: Run, expect pass** — `npm --prefix frontend test -- Chip`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(frontend): theme tokens + UI primitives (Chip/Panel/Button)"`

---

### Task 13: types + socket hook rewrite (streaming, control, manual, quick, events)

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/useDashboardSocket.ts`
- Test: `frontend/src/useDashboardSocket.test.ts`

- [ ] **Step 1: Failing test** (drive the hook's message reducer)

```ts
// frontend/src/useDashboardSocket.test.ts
import { reduceMessage, type ChatState, emptyChat } from "./useDashboardSocket";

test("assembles a streaming assistant turn", () => {
  let s: ChatState = emptyChat;
  s = reduceMessage(s, { type: "chat_start" });
  s = reduceMessage(s, { type: "chat_delta", kind: "thinking", text: "hmm" });
  s = reduceMessage(s, { type: "chat_delta", kind: "reply", text: "Holding" });
  s = reduceMessage(s, { type: "chat_end" });
  const last = s.messages[s.messages.length - 1];
  expect(last.role).toBe("assistant");
  expect(last.reply).toBe("Holding");
  expect(last.thinking).toBe("hmm");
  expect(s.streaming).toBe(false);
});

test("user echo + control state", () => {
  let s = reduceMessage(emptyChat, { type: "__user", text: "go" });
  expect(s.messages[0]).toEqual(expect.objectContaining({ role: "user", reply: "go" }));
});
```

- [ ] **Step 2: Run, expect fail** — `npm --prefix frontend test -- useDashboardSocket`.

- [ ] **Step 3: Implement** — export a pure `reduceMessage` reducer + `emptyChat`, and wire the hook around it; add `takeControl/release/sendManual/quick`, `events`, `control`.

```ts
// frontend/src/types.ts (append)
export interface ChatMessage { role: "user" | "assistant"; reply: string; thinking?: string; }
export interface ProposalView { command: any; say?: string; }
export interface EventEntry { ts: number; kind: string; text: string; }
```

```ts
// frontend/src/useDashboardSocket.ts (rewrite)
import { useEffect, useRef, useState, useCallback } from "react";
import type { Telemetry, VideoStatus, ControlWho, ChatMessage, ProposalView, EventEntry } from "./types";

export interface ChatState { messages: ChatMessage[]; streaming: boolean; }
export const emptyChat: ChatState = { messages: [], streaming: false };

export function reduceMessage(s: ChatState, m: any): ChatState {
  switch (m.type) {
    case "__user":
      return { ...s, messages: [...s.messages, { role: "user", reply: m.text }] };
    case "chat_start":
      return { ...s, streaming: true, messages: [...s.messages, { role: "assistant", reply: "", thinking: "" }] };
    case "chat_delta": {
      const msgs = s.messages.slice(); const last = { ...msgs[msgs.length - 1] };
      if (m.kind === "reply") last.reply += m.text; else last.thinking = (last.thinking || "") + m.text;
      msgs[msgs.length - 1] = last; return { ...s, messages: msgs };
    }
    case "chat_end":
      return { ...s, streaming: false };
    default:
      return s;
  }
}

export function useDashboardSocket(url: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [chat, setChat] = useState<ChatState>(emptyChat);
  const [proposal, setProposal] = useState<ProposalView | null>(null);
  const [control, setControl] = useState<ControlWho>("assistant");
  const [videoStatus, setVideoStatus] = useState<VideoStatus | null>(null);
  const [events, setEvents] = useState<EventEntry[]>([]);
  const logEvent = (kind: string, text: string) =>
    setEvents((e) => [...e.slice(-199), { ts: Date.now(), kind, text }]);

  useEffect(() => {
    const ws = new WebSocket(url); wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      switch (m.type) {
        case "telemetry": setTelemetry(m.data); break;
        case "video_status": setVideoStatus({ ok: m.ok, url: m.url }); break;
        case "control_state": setControl(m.who); logEvent("control", `control: ${m.who}`); break;
        case "proposal": setProposal({ command: m.command, say: m.say }); logEvent("proposal", m.say || JSON.stringify(m.command)); break;
        case "result": setProposal(null); logEvent("result", `${m.status} ${m.verb || ""}`.trim()); break;
        case "narration": logEvent("narration", m.text); setChat((s) => reduceMessage(reduceMessage(s, { type: "chat_start" }), { type: "chat_delta", kind: "reply", text: m.text })); setChat((s) => reduceMessage(s, { type: "chat_end" })); break;
        case "chat_start": case "chat_delta": case "chat_end": setChat((s) => reduceMessage(s, m)); break;
      }
    };
    return () => ws.close();
  }, [url]);

  const send = useCallback((o: unknown) => wsRef.current?.send(JSON.stringify(o)), []);
  const sendChat = useCallback((text: string) => { setChat((s) => reduceMessage(s, { type: "__user", text })); send({ type: "chat", text }); }, [send]);
  const confirm = useCallback(() => { setProposal(null); send({ type: "confirm" }); }, [send]);
  const cancel = useCallback(() => { setProposal(null); send({ type: "cancel" }); }, [send]);
  const abort = useCallback(() => send({ type: "abort" }), [send]);
  const takeControl = useCallback(() => send({ type: "take_control" }), [send]);
  const release = useCallback(() => send({ type: "release_control" }), [send]);
  const quick = useCallback((verb: string, args?: object) => send({ type: "quick", verb, args: args || {} }), [send]);
  const sendManual = useCallback((forward: number, right: number, down: number, yaw_rate: number) =>
    send({ type: "manual", forward, right, down, yaw_rate }), [send]);

  return { connected, telemetry, chat, proposal, control, videoStatus, events,
           sendChat, confirm, cancel, abort, takeControl, release, quick, sendManual };
}
```

- [ ] **Step 4: Run, expect pass** — `npm --prefix frontend test -- useDashboardSocket`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(frontend): socket hook with streaming chat reducer, control, events, manual/quick"`

---

### Task 14: useManualControl hook

**Files:**
- Create: `frontend/src/useManualControl.ts`
- Test: `frontend/src/useManualControl.test.ts`

- [ ] **Step 1: Failing test** (pure mapping fn)

```ts
// frontend/src/useManualControl.test.ts
import { keysToSetpoint } from "./useManualControl";

test("WASD maps to body velocity at cruise speed", () => {
  const sp = keysToSetpoint(new Set(["w"]), 12);
  expect(sp.forward).toBeCloseTo(6);  // half of max without boost
  expect(sp.right).toBe(0);
});
test("shift boosts to max", () => {
  expect(keysToSetpoint(new Set(["w", "shift"]), 12).forward).toBeCloseTo(12);
});
test("d strafes right, q yaws left", () => {
  expect(keysToSetpoint(new Set(["d"]), 12).right).toBeGreaterThan(0);
  expect(keysToSetpoint(new Set(["q"]), 12).yaw_rate).toBeLessThan(0);
});
test("r climbs (down negative)", () => {
  expect(keysToSetpoint(new Set(["r"]), 12).down).toBeLessThan(0);
});
test("no keys = zero", () => {
  const sp = keysToSetpoint(new Set(), 12);
  expect(sp).toEqual({ forward: 0, right: 0, down: 0, yaw_rate: 0 });
});
```

- [ ] **Step 2: Run, expect fail** — `npm --prefix frontend test -- useManualControl`.

- [ ] **Step 3: Implement**

```ts
// frontend/src/useManualControl.ts
import { useEffect, useRef } from "react";

export interface Setpoint { forward: number; right: number; down: number; yaw_rate: number; }
const YAW_RATE = 60; // deg/s at full deflection

export function keysToSetpoint(keys: Set<string>, maxSpeed: number): Setpoint {
  const boost = keys.has("shift") ? 1 : 0.5;
  const v = maxSpeed * boost;
  let forward = 0, right = 0, down = 0, yaw_rate = 0;
  if (keys.has("w")) forward += v;
  if (keys.has("s")) forward -= v;
  if (keys.has("d")) right += v;
  if (keys.has("a")) right -= v;
  if (keys.has("r")) down -= v;   // up
  if (keys.has("f")) down += v;   // down
  if (keys.has("e")) yaw_rate += YAW_RATE * (boost === 1 ? 1.5 : 1);
  if (keys.has("q")) yaw_rate -= YAW_RATE * (boost === 1 ? 1.5 : 1);
  return { forward, right, down, yaw_rate };
}

export function useManualControl(
  active: boolean, maxSpeed: number,
  send: (f: number, r: number, d: number, yr: number) => void,
) {
  const keys = useRef(new Set<string>());
  useEffect(() => {
    if (!active) return;
    const norm = (k: string) => (k === "Shift" ? "shift" : k.toLowerCase());
    const down = (e: KeyboardEvent) => { keys.current.add(norm(e.key)); };
    const up = (e: KeyboardEvent) => { keys.current.delete(norm(e.key)); };
    const clear = () => { keys.current.clear(); send(0, 0, 0, 0); };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", clear);
    document.addEventListener("visibilitychange", () => { if (document.hidden) clear(); });
    const id = setInterval(() => {
      const sp = keysToSetpoint(keys.current, maxSpeed);
      send(sp.forward, sp.right, sp.down, sp.yaw_rate);
    }, 50); // 20 Hz
    return () => {
      clearInterval(id); send(0, 0, 0, 0);
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", clear);
    };
  }, [active, maxSpeed, send]);
  return keys;
}
```

- [ ] **Step 4: Run, expect pass** — `npm --prefix frontend test -- useManualControl`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(frontend): useManualControl (keys->setpoint, 20Hz, blur-zero, manual-only)"`

---

### Task 15: OSD math

**Files:**
- Create: `frontend/src/osd/math.ts`
- Test: `frontend/src/osd/math.test.ts`

- [ ] **Step 1: Failing test**

```ts
// frontend/src/osd/math.test.ts
import { compassTicks, ladderTicks, headingLabel } from "./math";

test("headingLabel wraps to cardinal", () => {
  expect(headingLabel(0)).toBe("N");
  expect(headingLabel(90)).toBe("E");
  expect(headingLabel(180)).toBe("S");
  expect(headingLabel(270)).toBe("W");
});
test("compassTicks centers on heading within window", () => {
  const t = compassTicks(90, 60, 10); // heading 90, +/-30 window, step 10
  expect(t.some((x) => x.deg === 90 && Math.abs(x.x) < 1e-6)).toBe(true);
});
test("ladderTicks returns ticks around a value", () => {
  const t = ladderTicks(12, 5, 20); // value 12, step 5, span 20
  expect(t.map((x) => x.value)).toContain(10);
  expect(t.map((x) => x.value)).toContain(15);
});
```

- [ ] **Step 2: Run, expect fail** — `npm --prefix frontend test -- osd/math`.

- [ ] **Step 3: Implement**

```ts
// frontend/src/osd/math.ts
export function headingLabel(deg: number): string {
  const d = ((deg % 360) + 360) % 360;
  const names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return names[Math.round(d / 45) % 8];
}
export function compassTicks(heading: number, windowDeg: number, step: number) {
  const half = windowDeg / 2;
  const ticks: { deg: number; x: number; label: string }[] = [];
  const start = Math.ceil((heading - half) / step) * step;
  for (let d = start; d <= heading + half; d += step) {
    const norm = ((d % 360) + 360) % 360;
    ticks.push({ deg: norm, x: (d - heading) / half, // -1..1
      label: norm % 90 === 0 ? headingLabel(norm) : String(norm) });
  }
  return ticks;
}
export function ladderTicks(value: number, step: number, span: number) {
  const half = span / 2;
  const ticks: { value: number; y: number }[] = [];
  const start = Math.ceil((value - half) / step) * step;
  for (let v = start; v <= value + half; v += step) {
    ticks.push({ value: v, y: (value - v) / half }); // up is positive
  }
  return ticks;
}
```

- [ ] **Step 4: Run, expect pass** — `npm --prefix frontend test -- osd/math`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(frontend): OSD math (compass/ladder/heading)"`

---

### Task 16: OSD components + VideoPane/FallbackScene

**Files:**
- Create: `frontend/src/components/osd/AttitudeIndicator.tsx`, `CompassTape.tsx`, `Ladder.tsx`, `Crosshair.tsx`, `OsdOverlay.tsx`
- Modify: `frontend/src/components/VideoPane.tsx`, `frontend/src/components/FallbackScene.tsx`
- Test: `frontend/src/components/osd/OsdOverlay.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
// frontend/src/components/osd/OsdOverlay.test.tsx
import { render } from "@testing-library/react";
import { OsdOverlay } from "./OsdOverlay";
test("renders without telemetry", () => {
  const { container } = render(<OsdOverlay t={null} />);
  expect(container).toBeTruthy();
});
test("renders alt/speed when telemetry present", () => {
  const t: any = { alt_m: 12.3, speed_ms: 3.4, roll: 5, pitch: -3, yaw: 90, battery_pct: 0.8, gps_ok: true, ekf_ok: true, flight_mode: "HOLD", armed: true, lat: 0, lon: 0 };
  const { getByText } = render(<OsdOverlay t={t} />);
  expect(getByText(/12/)).toBeTruthy();
});
```

- [ ] **Step 2: Run, expect fail** — `npm --prefix frontend test -- OsdOverlay`.

- [ ] **Step 3: Implement** — SVG-based overlays positioned absolutely over the video, pointer-events none. `AttitudeIndicator` rotates/translates a horizon by roll/pitch; `CompassTape` uses `compassTicks`; `Ladder` uses `ladderTicks` (one for alt, one for speed); `Crosshair` static. `OsdOverlay` composes them from telemetry.

```tsx
// frontend/src/components/osd/Crosshair.tsx
export function Crosshair() {
  return (<svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }} viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
    <g stroke="#3ddc97" strokeWidth="0.4" fill="none" opacity="0.9">
      <line x1="46" y1="50" x2="49" y2="50" /><line x1="51" y1="50" x2="54" y2="50" />
      <line x1="50" y1="46" x2="50" y2="49" /><line x1="50" y1="51" x2="50" y2="54" />
    </g></svg>);
}
```

```tsx
// frontend/src/components/osd/AttitudeIndicator.tsx
export function AttitudeIndicator({ roll, pitch }: { roll: number; pitch: number }) {
  // pitch: ~1% screen per degree; roll rotates the horizon
  const t = `translate(0 ${pitch * 0.8}) rotate(${-roll} 50 50)`;
  return (<svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none", opacity: 0.7 }} viewBox="0 0 100 100" preserveAspectRatio="none">
    <g transform={t} stroke="#9fe3c4" strokeWidth="0.3">
      <line x1="20" y1="50" x2="80" y2="50" />
      {[-20, -10, 10, 20].map((p) => (<line key={p} x1="42" x2="58" y1={50 - p * 0.8} y2={50 - p * 0.8} />))}
    </g></svg>);
}
```

```tsx
// frontend/src/components/osd/CompassTape.tsx
import { compassTicks } from "../../osd/math";
export function CompassTape({ heading }: { heading: number }) {
  const ticks = compassTicks(heading, 90, 15);
  return (<svg style={{ position: "absolute", top: 8, left: "50%", transform: "translateX(-50%)", width: "60%", height: 34, pointerEvents: "none" }} viewBox="-100 0 200 34" preserveAspectRatio="xMidYMid meet">
    {ticks.map((tk) => (<g key={tk.deg + "-" + tk.x} transform={`translate(${tk.x * 100} 0)`}>
      <line x1="0" y1="6" x2="0" y2="14" stroke="#9fe3c4" strokeWidth="0.6" />
      <text x="0" y="26" fill="#cfe9dd" fontSize="9" textAnchor="middle" fontFamily="monospace">{tk.label}</text>
    </g>))}
    <polygon points="0,2 -3,-4 3,-4" fill="#3ddc97" /></svg>);
}
```

```tsx
// frontend/src/components/osd/Ladder.tsx
import { ladderTicks } from "../../osd/math";
export function Ladder({ value, step, span, unit, side }:
  { value: number; step: number; span: number; unit: string; side: "left" | "right" }) {
  const ticks = ladderTicks(value, step, span);
  const anchor = side === "left" ? "start" : "end";
  return (<svg style={{ position: "absolute", [side]: 10, top: "50%", transform: "translateY(-50%)", width: 70, height: 220, pointerEvents: "none" }} viewBox="0 -100 70 200" preserveAspectRatio="xMidYMid meet">
    {ticks.map((tk) => (<g key={tk.value} transform={`translate(0 ${-tk.y * 100})`}>
      <line x1={side === "left" ? 0 : 70} x2={side === "left" ? 8 : 62} y1="0" y2="0" stroke="#9fe3c4" strokeWidth="0.5" />
      <text x={side === "left" ? 12 : 58} y="3" fill="#cfe9dd" fontSize="9" textAnchor={anchor} fontFamily="monospace">{tk.value}</text>
    </g>))}
    <text x={side === "left" ? 2 : 68} y="-92" fill="#8b9bb0" fontSize="8" textAnchor={anchor} fontFamily="monospace">{unit}</text>
    <rect x="0" y="-7" width="70" height="14" fill="none" stroke="#3ddc97" strokeWidth="0.6" />
    <text x="35" y="3" fill="#3ddc97" fontSize="10" textAnchor="middle" fontFamily="monospace">{value.toFixed(1)}</text>
  </svg>);
}
```

```tsx
// frontend/src/components/osd/OsdOverlay.tsx
import type { Telemetry } from "../../types";
import { Crosshair } from "./Crosshair";
import { AttitudeIndicator } from "./AttitudeIndicator";
import { CompassTape } from "./CompassTape";
import { Ladder } from "./Ladder";
export function OsdOverlay({ t }: { t: Telemetry | null }) {
  if (!t) return <Crosshair />;
  return (<div style={{ position: "absolute", inset: 0, zIndex: 10, pointerEvents: "none" }}>
    <AttitudeIndicator roll={t.roll ?? 0} pitch={t.pitch ?? 0} />
    <Crosshair />
    <CompassTape heading={t.yaw ?? 0} />
    <Ladder value={t.alt_m} step={5} span={40} unit="ALT m" side="left" />
    <Ladder value={t.speed_ms} step={2} span={16} unit="SPD m/s" side="right" />
  </div>);
}
```

Update `VideoPane.tsx` to render the MJPEG `<img>` (or `FallbackScene`) full-bleed and overlay `OsdOverlay`. Keep the existing fallback logic (`videoStatus?.ok`).

- [ ] **Step 4: Run, expect pass** — `npm --prefix frontend test -- OsdOverlay`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(frontend): OSD overlay (attitude/compass/ladders/crosshair) on video"`

---

### Task 17: TopBar (health chips + control toggle + abort)

**Files:**
- Create: `frontend/src/components/TopBar.tsx`, `HealthChips.tsx`, `ControlToggle.tsx`, `AbortButton.tsx`
- Test: `frontend/src/components/ControlToggle.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
// frontend/src/components/ControlToggle.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { ControlToggle } from "./ControlToggle";
test("shows TAKE CONTROL in assistant, calls onTake", () => {
  const onTake = vi.fn();
  render(<ControlToggle control="assistant" onTake={onTake} onRelease={() => {}} />);
  fireEvent.click(screen.getByRole("button"));
  expect(onTake).toHaveBeenCalled();
});
test("shows RELEASE in manual, calls onRelease", () => {
  const onRelease = vi.fn();
  render(<ControlToggle control="manual" onTake={() => {}} onRelease={onRelease} />);
  fireEvent.click(screen.getByRole("button"));
  expect(onRelease).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run, expect fail** — `npm --prefix frontend test -- ControlToggle`.

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/ControlToggle.tsx
import type { ControlWho } from "../types";
import { Button } from "./ui/Button";
export function ControlToggle({ control, onTake, onRelease }:
  { control: ControlWho; onTake: () => void; onRelease: () => void }) {
  const manual = control === "manual";
  return (<div style={{ display: "flex", gap: 8, alignItems: "center" }}>
    <span style={{ font: "700 12px Inter, sans-serif", color: manual ? "#f5b945" : "#3ddc97" }}>
      {manual ? "MANUAL (YOU)" : "ASSISTANT"}</span>
    <Button variant={manual ? "default" : "accent"} onClick={manual ? onRelease : onTake}>
      {manual ? "RELEASE" : "TAKE CONTROL"}</Button>
  </div>);
}
```

`HealthChips` renders `Chip`s for safety link, video, GPS/EKF, battery with status derived from telemetry/connection. `AbortButton` is a red `Button` calling `onAbort`. `TopBar` lays them out (chips left, toggle + abort right) as a floating bar.

```tsx
// frontend/src/components/HealthChips.tsx
import type { Telemetry, VideoStatus } from "../types";
import { Chip } from "./ui/Chip";
export function HealthChips({ connected, telemetry, video }:
  { connected: boolean; telemetry: Telemetry | null; video: VideoStatus | null }) {
  const batt = telemetry ? Math.round(telemetry.battery_pct * 100) : null;
  return (<div style={{ display: "flex", gap: 8 }}>
    <Chip label="LINK" status={connected ? "ok" : "lost"} value={connected ? "up" : "down"} />
    <Chip label="VIDEO" status={video?.ok ? "ok" : "lost"} value={video?.ok ? "live" : "—"} />
    <Chip label="GPS/EKF" status={telemetry ? (telemetry.gps_ok && telemetry.ekf_ok ? "ok" : "warn") : "lost"}
      value={telemetry ? `${telemetry.gps_ok ? "ok" : "no"}/${telemetry.ekf_ok ? "ok" : "no"}` : "—"} />
    <Chip label="BATT" status={batt == null ? "lost" : batt < 20 ? "warn" : "ok"} value={batt == null ? "—" : `${batt}%`} />
  </div>);
}
```

- [ ] **Step 4: Run, expect pass** — `npm --prefix frontend test -- ControlToggle`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(frontend): TopBar with health chips, control toggle, abort"`

---

### Task 18: ChatDrawer (bubbles + streaming + proposal)

**Files:**
- Create: `frontend/src/components/ChatDrawer.tsx`
- Delete: `frontend/src/components/ChatPanel.tsx`
- Test: `frontend/src/components/ChatDrawer.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
// frontend/src/components/ChatDrawer.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatDrawer } from "./ChatDrawer";
const base = { chat: { messages: [{ role: "user", reply: "go" }, { role: "assistant", reply: "Holding", thinking: "reasoning" }], streaming: false } as any,
  proposal: null, onChat: () => {}, onConfirm: () => {}, onCancel: () => {} };
test("renders user + assistant bubbles", () => {
  render(<ChatDrawer {...base} />);
  expect(screen.getByText("go")).toBeInTheDocument();
  expect(screen.getByText("Holding")).toBeInTheDocument();
});
test("shows proposal confirm/cancel", () => {
  const onConfirm = vi.fn();
  render(<ChatDrawer {...base} proposal={{ command: { verb: "loiter" }, say: "ok" }} onConfirm={onConfirm} />);
  fireEvent.click(screen.getByText(/Confirm/));
  expect(onConfirm).toHaveBeenCalled();
});
test("shows thinking indicator while streaming", () => {
  render(<ChatDrawer {...base} chat={{ messages: base.chat.messages, streaming: true } as any} />);
  expect(screen.getByText(/thinking/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run, expect fail** — `npm --prefix frontend test -- ChatDrawer`.

- [ ] **Step 3: Implement** — message list (user bubbles right, assistant left), collapsible "thinking" under assistant bubbles, a "thinking…" indicator when `streaming`, proposal card (renders `say` + pretty command + Confirm/Cancel), input box with Send (Enter submits). Autoscroll to bottom on new messages.

- [ ] **Step 4: Run, expect pass** — `npm --prefix frontend test -- ChatDrawer`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(frontend): ChatDrawer with bubbles, thinking, streaming, proposal card"`

---

### Task 19: QuickActions + ManualHUD

**Files:**
- Create: `frontend/src/components/QuickActions.tsx`, `frontend/src/components/ManualHUD.tsx`
- Test: `frontend/src/components/QuickActions.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
// frontend/src/components/QuickActions.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { QuickActions } from "./QuickActions";
test("takeoff issues quick verb with alt", () => {
  const quick = vi.fn();
  render(<QuickActions quick={quick} />);
  fireEvent.click(screen.getByText(/Takeoff/));
  expect(quick).toHaveBeenCalledWith("arm_takeoff", expect.objectContaining({ alt: expect.any(Number) }));
});
test("RTL issues return_to_launch", () => {
  const quick = vi.fn();
  render(<QuickActions quick={quick} />);
  fireEvent.click(screen.getByText(/RTL/));
  expect(quick).toHaveBeenCalledWith("return_to_launch", {});
});
```

- [ ] **Step 2: Run, expect fail** — `npm --prefix frontend test -- QuickActions`.

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/QuickActions.tsx
import { Button } from "./ui/Button";
export function QuickActions({ quick }: { quick: (verb: string, args?: object) => void }) {
  return (<div style={{ display: "flex", gap: 8 }}>
    <Button onClick={() => quick("arm_takeoff", { alt: 10 })}>Takeoff</Button>
    <Button onClick={() => quick("orbit", { radius: 20, alt: 15 })}>Orbit</Button>
    <Button onClick={() => quick("loiter", {})}>Loiter</Button>
    <Button onClick={() => quick("return_to_launch", {})}>RTL</Button>
    <Button variant="danger" onClick={() => quick("land", {})}>Land</Button>
  </div>);
}
```

`ManualHUD` (shown only in manual): renders the key map (W/A/S/D, Q/E, R/F, Shift) highlighting pressed keys (from the `keys` ref passed in) and a live setpoint readout. Keep simple; no test beyond render.

- [ ] **Step 4: Run, expect pass** — `npm --prefix frontend test -- QuickActions`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(frontend): QuickActions + ManualHUD"`

---

### Task 20: EventLog

**Files:**
- Create: `frontend/src/components/EventLog.tsx`
- Test: `frontend/src/components/EventLog.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
// frontend/src/components/EventLog.test.tsx
import { render, screen } from "@testing-library/react";
import { EventLog } from "./EventLog";
test("renders entries newest first", () => {
  render(<EventLog events={[{ ts: 1, kind: "result", text: "executed loiter" }, { ts: 2, kind: "control", text: "control: manual" }]} />);
  const items = screen.getAllByRole("listitem");
  expect(items[0]).toHaveTextContent("control: manual");
});
```

- [ ] **Step 2: Run, expect fail** — `npm --prefix frontend test -- EventLog`.

- [ ] **Step 3: Implement** — a collapsible list, newest first, `kind`-colored tag + `HH:MM:SS` from `ts` + text; `role="list"`/`listitem`.

- [ ] **Step 4: Run, expect pass** — `npm --prefix frontend test -- EventLog`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(frontend): EventLog panel"`

---

### Task 21: App composition (immersive layout) + build

**Files:**
- Modify: `frontend/src/App.tsx`
- Delete: `frontend/src/components/AbortBar.tsx`, `frontend/src/components/TelemetryCards.tsx` (superseded by OSD + HealthChips; only if unused)
- Test: build + existing component tests

- [ ] **Step 1: Implement App** — full-bleed `VideoPane` + `OsdOverlay` base layer; floating `TopBar` (top); `QuickActions` (bottom-left); `ChatDrawer` (bottom-right); `ManualHUD` (bottom-center, manual only); `EventLog` (toggle). Wire `useDashboardSocket` + `useManualControl(control==="manual", maxSpeed, sendManual)`. `maxSpeed` constant 12 (matches `Limits.max_speed_ms`).

```tsx
// frontend/src/App.tsx (shape)
import { useDashboardSocket } from "./useDashboardSocket";
import { useManualControl } from "./useManualControl";
import { VideoPane } from "./components/VideoPane";
import { OsdOverlay } from "./components/osd/OsdOverlay";
import { TopBar } from "./components/TopBar";
import { QuickActions } from "./components/QuickActions";
import { ChatDrawer } from "./components/ChatDrawer";
import { ManualHUD } from "./components/ManualHUD";
import { EventLog } from "./components/EventLog";
import { theme } from "./theme";

const WS_URL = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";
const MAX_SPEED = 12;

export function App() {
  const d = useDashboardSocket(WS_URL);
  const keys = useManualControl(d.control === "manual", MAX_SPEED, d.sendManual);
  return (
    <div style={{ position: "fixed", inset: 0, background: theme.color.bg, color: theme.color.text,
                  fontFamily: theme.font.ui, overflow: "hidden" }}>
      <VideoPane videoStatus={d.videoStatus} telemetry={d.telemetry} />
      <OsdOverlay t={d.telemetry} />
      <TopBar connected={d.connected} telemetry={d.telemetry} video={d.videoStatus}
        control={d.control} onTake={d.takeControl} onRelease={d.release} onAbort={d.abort} />
      <div style={{ position: "absolute", left: 12, bottom: 12, zIndex: 30 }}>
        <QuickActions quick={d.quick} />
      </div>
      {d.control === "manual" && <ManualHUD keys={keys} />}
      <div style={{ position: "absolute", right: 12, bottom: 12, width: 360, maxHeight: "70vh", zIndex: 30 }}>
        <ChatDrawer chat={d.chat} proposal={d.proposal}
          onChat={d.sendChat} onConfirm={d.confirm} onCancel={d.cancel} />
      </div>
      <EventLog events={d.events} />
    </div>
  );
}
```

(Remove the stray `challenge` token shown above — it must not appear in real code; this is the layout reference only.)

- [ ] **Step 2: Typecheck + build** — `npm --prefix frontend run build` → expect success (no TS errors).
- [ ] **Step 3: Run full frontend suite** — `npm --prefix frontend test` → all pass.
- [ ] **Step 4: Apply frontend-design polish** — invoke the frontend-design skill to refine spacing, color, motion (thinking pulse, drawer transitions), and OSD legibility; re-run build.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(frontend): immersive FPV cockpit composition + build"`

---

# PHASE E — Live validation

### Task 22: Integration e2e + docs

**Files:**
- Modify: `tests/dashboard/test_integration.py` (add manual + streaming + quick cases)
- Modify: `ROADMAP.md` (status, run notes, new gotchas)
- Test: live SITL

- [ ] **Step 1: Write integration cases** (env `DASH_E2E_WS`, default `:8080`)

```python
# tests/dashboard/test_integration.py (append)
@pytest.mark.asyncio
async def test_take_control_and_manual_setpoints():
    async with websockets.connect(DASH_WS) as ws:
        # take off first via quick + confirm
        await ws.send(json.dumps({"type": "quick", "verb": "arm_takeoff", "args": {"alt": 8}}))
        # confirm when a proposal arrives
        for _ in range(40):
            f = json.loads(await asyncio.wait_for(ws.recv(), 5))
            if f.get("type") == "proposal": await ws.send(json.dumps({"type": "confirm"})); break
        # wait for takeoff result
        for _ in range(60):
            f = json.loads(await asyncio.wait_for(ws.recv(), 10))
            if f.get("type") == "result": break
        # take control, stream a few forward setpoints, then release
        await ws.send(json.dumps({"type": "take_control"}))
        saw_manual = False
        for _ in range(40):
            f = json.loads(await asyncio.wait_for(ws.recv(), 5))
            if f.get("type") == "control_state" and f.get("who") == "manual": saw_manual = True; break
        assert saw_manual
        for _ in range(20):
            await ws.send(json.dumps({"type": "manual", "forward": 2.0, "right": 0.0, "down": 0.0, "yaw_rate": 0.0}))
            await asyncio.sleep(0.05)
        await ws.send(json.dumps({"type": "release_control"}))
```

- [ ] **Step 2: Bring up the stack** (lighter `cam_test` world; one terminal each):

```bash
# SITL (camera world)
source /hey/projects/px4-build-venv/bin/activate && PX4_GZ_WORLD=cam_test HEADLESS=1 make -C /hey/projects/PX4-Autopilot px4_sitl gz_x500_mono_cam
# services
. .venv/bin/activate && python -m flight_safety
PYTHONPATH=src VB_TOPIC="/world/cam_test/model/x500_mono_cam_0/link/camera_link/sensor/camera/image" VB_PORT=8092 VB_JPEG_QUALITY=70 /usr/bin/python3 -m video_bridge
. .venv/bin/activate && DASH_PORT=8090 DASH_SAFETY_URL="ws://127.0.0.1:8765/ws" DASH_VIDEO_STREAM_URL="http://<host-ip>:8092/stream.mjpg" DASH_VIDEO_HEALTH_URL="http://127.0.0.1:8092/health" python -m dashboard
npm --prefix frontend run build
```

- [ ] **Step 3: Run integration** — `. .venv/bin/activate && DASH_E2E_WS=ws://127.0.0.1:8090/ws pytest -m integration tests/dashboard/test_integration.py -v` → expect PASS.
- [ ] **Step 4: Browser check** — open `http://<host-ip>:8090`: take off (quick) → TAKE CONTROL → fly with WASD/QE/RF (watch OSD + position move) → RELEASE; send a chat message and watch streaming + thinking; trigger ABORT.
- [ ] **Step 5: Update ROADMAP + commit** — record cockpit-v2 done, manual-control gotchas (OFFBOARD needs airborne; watchdog 500 ms; geofence brake), and that the takeover/handback M1 follow-up is closed. `git add -A && git commit -m "test(cockpit-v2): live e2e (manual control + streaming) + ROADMAP"`

---

## Self-review notes (author)

- **Spec coverage:** control toggle (T10/T17), gate-validated OFFBOARD (T2–T5), watchdog (T3/T4), geofence brake (T1/T3), streaming chat + thinking + echo (T6/T7/T9/T10/T13/T18), latency via cached telemetry (T8/T9), immersive OSD layout (T15/T16/T21), quick actions (T10/T19), event log (T13/T20), health chips (T17), unified service (no separate port — design §8, nothing to build). All covered.
- **Type consistency:** setpoint tuple `(forward,right,down,yaw_rate)` used uniformly; ws message field names (`forward/right/down/yaw_rate`) identical across server, safety_client, app, frontend; `control_state.who ∈ {manual,assistant}`; `CommandProposal{command,say}` used in command_gen/hub/app/frontend (`proposal.say`).
- **Deviation from spec:** `say` is emitted as prose *before* the JSON (streams for any model) rather than a JSON field — same intent, better streaming; noted in plan header.
