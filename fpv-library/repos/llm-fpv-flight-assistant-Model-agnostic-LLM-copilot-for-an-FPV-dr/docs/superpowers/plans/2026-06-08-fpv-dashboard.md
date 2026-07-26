# FPV Web Dashboard (M3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the operator-facing FPV web dashboard (live video + telemetry HUD + chat with preview/confirm + always-visible ABORT) that completes the first vertical slice.

**Architecture:** Three independent processes — the existing **flight-safety service** (gains a telemetry push stream + request `id`), a new standalone **video bridge** (gz camera → MJPEG), and a new **dashboard backend** (FastAPI; reuses `assistant.Agent` + `SafetyClient`) — plus a **Vite + React + react-three-fiber** frontend (Layout B). The browser talks to the dashboard backend for control/telemetry and to the video bridge only for the MJPEG image.

**Tech Stack:** Python 3.11, FastAPI + uvicorn + websockets, pydantic/pydantic-settings, MAVSDK, Pillow (JPEG), httpx, gz-transport Python bindings; Vite + React + TypeScript + react-three-fiber + Vitest.

**Spec:** `docs/superpowers/specs/2026-06-08-fpv-dashboard-design.md`

**Conventions (from the repo):**
- `pytest.ini`: `asyncio_mode=auto` (async tests auto-run), integration tests carry `pytestmark = pytest.mark.integration` and are deselected by default; `pytest -q` runs the unit suite.
- TDD: write the failing test first, watch it fail, implement minimally, watch it pass, commit. One commit per task.
- Activate the venv first: `. .venv/bin/activate`.

---

## Phase 0 — De-risk the unknown

### Task 1: Spike — camera airframe + headless gz rendering

**Goal:** Confirm a camera-enabled PX4 gz airframe produces a camera Image topic under headless EGL on the GTX 970, and record the exact airframe + topic name. This unblocks Phase B; if it fails we still ship (the dashboard falls back to the Three.js scene).

**Files:**
- Modify: `ROADMAP.md` (record findings under *Conventions & gotchas*)

- [ ] **Step 1: Launch SITL with a camera airframe**

Run (separate terminal):
```bash
source /hey/projects/px4-build-venv/bin/activate
HEADLESS=1 make -C /hey/projects/PX4-Autopilot px4_sitl gz_x500_mono_cam
```
Expected: PX4 boots; gz Harmonic starts headless. If `gz_x500_mono_cam` is not a valid target, try `gz_x500_depth`, or set `PX4_GZ_MODEL=x500_mono_cam` with `make px4_sitl gz_x500`. Note which one works.

- [ ] **Step 2: Discover the camera image topic**

Run:
```bash
gz topic -l | grep -i -E 'image|camera'
```
Expected: at least one topic (e.g. `/world/default/.../image` or `/camera`). Capture its full name.

- [ ] **Step 3: Confirm the topic carries rendered frames**

Run (replace `<TOPIC>`):
```bash
gz topic -i -t <TOPIC>          # shows the message type, expect gz.msgs.Image
gz topic -e -t <TOPIC> -n 1     # echo one message; expect non-empty width/height/data
```
Expected: message type is `gz.msgs.Image`; one frame echoes with `width`, `height`, `pixel_format_type`, and non-empty `data`. If `data` is empty/zeros under `HEADLESS=1`, note that EGL rendering needs investigation (do NOT block the plan — Phase B handles an unhealthy source via the fallback).

- [ ] **Step 4: Confirm the gz-transport Python bindings import**

Run:
```bash
. .venv/bin/activate
python -c "from gz.transport13 import Node; from gz.msgs10.image_pb2 import Image; print('gz python OK')"
```
Expected: `gz python OK`. If the import fails, record the install command needed (`sudo apt-get install python3-gz-transport13 python3-gz-msgs10`) and that Task 8's gz subscriber is the only part that needs it (the rest of the bridge is binding-free).

- [ ] **Step 5: Record findings and commit**

Add a bullet under *Conventions & gotchas* in `ROADMAP.md`, e.g.:
```markdown
- **gz camera (M3):** airframe `gz_x500_mono_cam`; image topic `<TOPIC>` (gz.msgs.Image,
  <W>x<H>, pixel_format <N>); gz-transport python via `gz.transport13`/`gz.msgs10`.
  Headless EGL rendering: <works / needs X>.
```
```bash
git add ROADMAP.md
git commit -m "docs(M3): record camera airframe + gz image topic from spike"
```

---

## Phase A — Flight-safety foundation (pure Python, no SITL)

### Task 2: Telemetry push stream in the flight-safety server

**Files:**
- Modify: `src/flight_safety/server.py`
- Test: `tests/flight_safety/test_server.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/flight_safety/test_server.py`:
```python
def test_server_pushes_telemetry_frames():
    class TelDisp:
        async def handle(self, raw): return {"status": "executed"}
        async def abort(self): ...
        async def telemetry(self):
            return {"battery_pct": 0.77, "alt_m": 12.0, "flight_mode": "HOLD"}
    client = TestClient(build_app(TelDisp(), telemetry_interval_s=0.05))
    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()  # arrives unsolicited from the push loop
        assert msg["type"] == "telemetry"
        assert msg["data"]["battery_pct"] == 0.77
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flight_safety/test_server.py::test_server_pushes_telemetry_frames -v`
Expected: FAIL — `build_app()` has no `telemetry_interval_s` parameter (TypeError).

- [ ] **Step 3: Implement the push loop**

Replace `src/flight_safety/server.py` with:
```python
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect


def build_app(dispatcher, on_startup=None, telemetry_interval_s: float = 0.5) -> FastAPI:
    """Build the websocket API around a dispatcher (injected for testability).

    on_startup: optional zero-arg coroutine awaited once when the event loop starts.
    telemetry_interval_s: period of the server->client telemetry push stream.
    """
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if on_startup is not None:
            await on_startup()
        yield

    app = FastAPI(title="flight-safety", lifespan=lifespan)

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        send_lock = asyncio.Lock()
        current: asyncio.Task | None = None

        async def send(payload: dict) -> None:
            async with send_lock:
                await socket.send_json(payload)

        async def push_loop() -> None:
            # Sleep BEFORE the first emit so a fast request/reply still arrives
            # first (keeps the existing request/reply tests deterministic).
            while True:
                await asyncio.sleep(telemetry_interval_s)
                try:
                    data = await dispatcher.telemetry()
                    await send({"type": "telemetry", "data": data})
                except Exception as e:  # never let the push loop kill the connection
                    await send({"type": "telemetry", "error": str(e)})

        async def run_command(command: dict) -> None:
            try:
                result = await dispatcher.handle(command)
            except asyncio.CancelledError:
                return  # preempted by abort -> do not send a stale result
            await send(result)

        push = asyncio.create_task(push_loop())
        try:
            while True:
                msg = await socket.receive_json()
                kind = msg.get("type")
                if kind == "command":
                    if current is not None and not current.done():
                        await send({"status": "rejected",
                                    "reason": "busy: a command is already executing"})
                    else:
                        current = asyncio.create_task(run_command(msg.get("command", {})))
                elif kind == "abort":
                    if current is not None and not current.done():
                        current.cancel()
                    await dispatcher.abort()
                    await send({"status": "aborted"})
                elif kind == "get_telemetry":
                    try:
                        data = await dispatcher.telemetry()
                        await send({"type": "telemetry", "data": data})
                    except Exception as e:
                        await send({"type": "telemetry", "error": str(e)})
                else:
                    await send({"status": "error", "reason": "unknown type"})
        except WebSocketDisconnect:
            return
        finally:
            push.cancel()
            if current is not None and not current.done():
                current.cancel()

    return app
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/flight_safety/test_server.py -v`
Expected: PASS (the new test plus all four existing server tests).

- [ ] **Step 5: Commit**

```bash
git add src/flight_safety/server.py tests/flight_safety/test_server.py
git commit -m "feat(flight-safety): server->client telemetry push stream"
```

---

### Task 3: Request `id` correlation in the server

**Files:**
- Modify: `src/flight_safety/server.py`
- Test: `tests/flight_safety/test_server.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/flight_safety/test_server.py`:
```python
def test_command_reply_echoes_id():
    disp = FakeDispatcher()
    client = TestClient(build_app(disp, telemetry_interval_s=999))  # suppress push noise
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "command", "id": 42, "command": {"verb": "loiter"}})
        msg = ws.receive_json()
        assert msg["status"] == "executed"
        assert msg["id"] == 42
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flight_safety/test_server.py::test_command_reply_echoes_id -v`
Expected: FAIL — reply has no `id` key (KeyError).

- [ ] **Step 3: Implement id echoing**

In `src/flight_safety/server.py`, change the message loop so every reply carries the request's `id` when present. Replace the `while True:` body inside `ws()` with:
```python
            while True:
                msg = await socket.receive_json()
                kind = msg.get("type")
                mid = msg.get("id")

                def tag(reply: dict) -> dict:
                    return {**reply, "id": mid} if mid is not None else reply

                if kind == "command":
                    if current is not None and not current.done():
                        await send(tag({"status": "rejected",
                                        "reason": "busy: a command is already executing"}))
                    else:
                        async def run_command(command: dict, rid) -> None:
                            try:
                                result = await dispatcher.handle(command)
                            except asyncio.CancelledError:
                                return
                            await send({**result, "id": rid} if rid is not None else result)
                        current = asyncio.create_task(run_command(msg.get("command", {}), mid))
                elif kind == "abort":
                    if current is not None and not current.done():
                        current.cancel()
                    await dispatcher.abort()
                    await send(tag({"status": "aborted"}))
                elif kind == "get_telemetry":
                    try:
                        data = await dispatcher.telemetry()
                        await send(tag({"type": "telemetry", "data": data}))
                    except Exception as e:
                        await send(tag({"type": "telemetry", "error": str(e)}))
                else:
                    await send(tag({"status": "error", "reason": "unknown type"}))
```
Then delete the now-unused module-local `run_command` defined before the loop (the inline version above replaces it).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/flight_safety/test_server.py -v`
Expected: PASS — the id test plus all prior tests (the unsolicited push frame has no `id`, which is correct).

- [ ] **Step 5: Commit**

```bash
git add src/flight_safety/server.py tests/flight_safety/test_server.py
git commit -m "feat(flight-safety): echo request id on replies for correlation"
```

---

### Task 4: SafetyClient demultiplexing client

**Files:**
- Modify: `src/assistant/safety_client.py`
- Test: `tests/assistant/test_safety_client.py`

- [ ] **Step 1: Write the failing tests**

Replace `tests/assistant/test_safety_client.py` with:
```python
import asyncio, json, pytest, websockets
from assistant.safety_client import SafetyClient


async def _fake_server(websocket):
    # proactively push one telemetry frame (no id) to exercise demux
    await websocket.send(json.dumps({"type": "telemetry", "data": {"battery_pct": 0.5}}))
    async for raw in websocket:
        msg = json.loads(raw)
        rid = msg.get("id")
        if msg["type"] == "get_telemetry":
            await websocket.send(json.dumps({"type": "telemetry", "data": {"battery_pct": 0.8}, "id": rid}))
        elif msg["type"] == "command":
            await websocket.send(json.dumps({"status": "executed", "verb": msg["command"]["verb"], "id": rid}))
        elif msg["type"] == "abort":
            await websocket.send(json.dumps({"status": "aborted", "id": rid}))


@pytest.mark.asyncio
async def test_client_roundtrips_with_id():
    async with websockets.serve(_fake_server, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = SafetyClient(f"ws://127.0.0.1:{port}")
        await client.connect()
        assert (await client.get_telemetry())["battery_pct"] == 0.8
        res = await client.send_command({"verb": "loiter"})
        assert res["status"] == "executed" and res["verb"] == "loiter"
        assert (await client.abort())["status"] == "aborted"
        await client.close()


@pytest.mark.asyncio
async def test_push_telemetry_reaches_subscriber():
    async with websockets.serve(_fake_server, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = SafetyClient(f"ws://127.0.0.1:{port}")
        got = []
        client.subscribe_telemetry(lambda d: got.append(d))
        await client.connect()
        # the pushed frame (no id) must NOT resolve a request; it goes to the subscriber
        await client.send_command({"verb": "loiter"})
        await asyncio.sleep(0.05)
        assert got and got[0]["battery_pct"] == 0.5
        await client.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/assistant/test_safety_client.py -v`
Expected: FAIL — `SafetyClient` has no `subscribe_telemetry`; old `_send_recv` cannot demux interleaved push frames.

- [ ] **Step 3: Implement the demux client**

Replace `src/assistant/safety_client.py` with:
```python
import asyncio
import json

import websockets


class SafetyClient:
    """Websocket client to the flight-safety service.

    A single background reader demultiplexes frames: push telemetry frames
    (no correlation id) go to subscribers; command/abort/get_telemetry replies
    are matched to their request by echoed `id` (FIFO fallback for legacy servers).
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._ws = None
        self._reader: asyncio.Task | None = None
        self._next_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._telemetry_subs: list = []

    async def connect(self) -> None:
        self._ws = await websockets.connect(self._url)
        self._reader = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        try:
            async for raw in self._ws:
                self._dispatch(json.loads(raw))
        except websockets.ConnectionClosed:
            pass
        finally:
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("safety link closed"))
            self._pending.clear()

    def _dispatch(self, frame: dict) -> None:
        # Push telemetry frames carry no correlation id.
        if frame.get("type") == "telemetry" and "id" not in frame:
            data = frame.get("data")
            if data is not None:
                for cb in self._telemetry_subs:
                    cb(data)
            return
        # Otherwise it's a reply: match by id, else FIFO fallback.
        fid = frame.get("id")
        fut = None
        if fid is not None and fid in self._pending:
            fut = self._pending.pop(fid)
        elif self._pending:
            fut = self._pending.pop(next(iter(self._pending)))
        if fut is not None and not fut.done():
            fut.set_result(frame)

    async def _request(self, payload: dict) -> dict:
        rid = self._next_id
        self._next_id += 1
        fut = asyncio.get_running_loop().create_future()
        self._pending[rid] = fut
        await self._ws.send(json.dumps({**payload, "id": rid}))
        return await fut

    def subscribe_telemetry(self, callback) -> None:
        """Register a callback invoked with each pushed telemetry data dict."""
        self._telemetry_subs.append(callback)

    async def get_telemetry(self) -> dict:
        reply = await self._request({"type": "get_telemetry"})
        if reply.get("error"):
            raise RuntimeError(f"telemetry unavailable: {reply['error']}")
        return reply["data"]

    async def send_command(self, command: dict) -> dict:
        return await self._request({"type": "command", "command": command})

    async def abort(self) -> dict:
        return await self._request({"type": "abort"})

    async def close(self) -> None:
        if self._reader is not None:
            self._reader.cancel()
            self._reader = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/assistant/test_safety_client.py tests/assistant/test_agent.py -v`
Expected: PASS (the agent tests use a FakeClient, unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/assistant/safety_client.py tests/assistant/test_safety_client.py
git commit -m "feat(assistant): demultiplexing SafetyClient with telemetry subscription"
```

---

### Task 5: Attitude fields on Telemetry

**Files:**
- Modify: `src/flight_safety/models.py`, `src/flight_safety/bridge.py`
- Test: `tests/flight_safety/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/flight_safety/test_models.py`:
```python
from flight_safety.models import Telemetry


def _base():
    return dict(lat=47.0, lon=8.0, alt_m=10.0, speed_ms=1.0, battery_pct=0.9,
                flight_mode="HOLD", armed=True, gps_ok=True, ekf_ok=True)


def test_telemetry_attitude_defaults_to_zero():
    t = Telemetry(**_base())
    assert (t.roll, t.pitch, t.yaw) == (0.0, 0.0, 0.0)


def test_telemetry_accepts_attitude():
    t = Telemetry(**_base(), roll=5.0, pitch=-3.0, yaw=90.0)
    assert t.pitch == -3.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flight_safety/test_models.py -v -k attitude`
Expected: FAIL — `Telemetry` has no `roll`/`pitch`/`yaw`.

- [ ] **Step 3: Add the optional fields**

In `src/flight_safety/models.py`, extend `Telemetry` (after `ekf_ok: bool`):
```python
    roll: float = 0.0      # degrees
    pitch: float = 0.0     # degrees
    yaw: float = 0.0       # degrees
```

In `src/flight_safety/bridge.py`, inside `read_telemetry`, after the `vel = ...` line add:
```python
        att = await self._drone.telemetry.attitude_euler().__anext__()
```
and add to the `Telemetry(...)` constructor call:
```python
            roll=att.roll_deg,
            pitch=att.pitch_deg,
            yaw=att.yaw_deg,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/flight_safety/test_models.py tests/flight_safety/test_validation.py -v`
Expected: PASS — defaults keep the validation gate and all existing telemetry construction working. (The `bridge.py` attitude read is exercised by the SITL integration test.)

- [ ] **Step 5: Commit**

```bash
git add src/flight_safety/models.py src/flight_safety/bridge.py tests/flight_safety/test_models.py
git commit -m "feat(flight-safety): optional roll/pitch/yaw on Telemetry"
```

---

## Phase B — Video bridge (standalone process)

### Task 6: JPEG encoding + frame buffer

**Files:**
- Create: `src/video_bridge/__init__.py`, `src/video_bridge/frames.py`
- Test: `tests/video_bridge/__init__.py`, `tests/video_bridge/test_frames.py`
- Modify: `pyproject.toml` (add `pillow`)

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add to `dependencies`:
```toml
    "pillow>=10.0",
```
Run: `. .venv/bin/activate && pip install -e .`

- [ ] **Step 2: Write the failing tests**

Create `tests/video_bridge/__init__.py` (empty) and `tests/video_bridge/test_frames.py`:
```python
import io
from PIL import Image
from video_bridge.frames import encode_jpeg, FrameBuffer


def test_encode_jpeg_returns_valid_jpeg():
    # 2x2 RGB red square as raw bytes
    raw = bytes([255, 0, 0] * 4)
    jpeg = encode_jpeg(raw, width=2, height=2, channels=3, quality=80)
    assert jpeg[:2] == b"\xff\xd8"          # JPEG SOI marker
    img = Image.open(io.BytesIO(jpeg))
    assert img.size == (2, 2)


def test_frame_buffer_tracks_age():
    clock = {"t": 100.0}
    buf = FrameBuffer(clock=lambda: clock["t"])
    assert buf.latest() is None
    assert buf.is_fresh(max_age_s=1.0) is False
    buf.set(b"\xff\xd8jpeg")
    assert buf.latest() == b"\xff\xd8jpeg"
    assert buf.is_fresh(max_age_s=1.0) is True
    clock["t"] = 102.0
    assert buf.age_s() == 2.0
    assert buf.is_fresh(max_age_s=1.0) is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/video_bridge/test_frames.py -v`
Expected: FAIL — `video_bridge` module does not exist.

- [ ] **Step 4: Implement**

Create `src/video_bridge/__init__.py` (empty) and `src/video_bridge/frames.py`:
```python
import io
import time

from PIL import Image


def encode_jpeg(raw: bytes, width: int, height: int, channels: int, quality: int = 80) -> bytes:
    """Encode raw RGB/RGBA pixel bytes to JPEG."""
    mode = "RGBA" if channels == 4 else "RGB"
    img = Image.frombytes(mode, (width, height), raw)
    if mode == "RGBA":
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality)
    return out.getvalue()


class FrameBuffer:
    """Holds the latest JPEG frame and how old it is (thread-safe enough for one writer)."""

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._jpeg: bytes | None = None
        self._ts: float | None = None

    def set(self, jpeg: bytes) -> None:
        self._jpeg = jpeg
        self._ts = self._clock()

    def latest(self) -> bytes | None:
        return self._jpeg

    def age_s(self) -> float | None:
        return None if self._ts is None else self._clock() - self._ts

    def is_fresh(self, max_age_s: float) -> bool:
        age = self.age_s()
        return age is not None and age <= max_age_s
```

- [ ] **Step 5: Run tests to verify they pass + commit**

Run: `pytest tests/video_bridge/test_frames.py -v` → Expected: PASS
```bash
git add pyproject.toml src/video_bridge/__init__.py src/video_bridge/frames.py tests/video_bridge/
git commit -m "feat(video-bridge): JPEG encode + frame buffer with age tracking"
```

---

### Task 7: MJPEG + health HTTP server

**Files:**
- Create: `src/video_bridge/mjpeg.py`
- Test: `tests/video_bridge/test_mjpeg.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/video_bridge/test_mjpeg.py`:
```python
from fastapi.testclient import TestClient
from video_bridge.frames import FrameBuffer
from video_bridge.mjpeg import mjpeg_chunk, build_video_app


def test_mjpeg_chunk_has_multipart_headers():
    chunk = mjpeg_chunk(b"\xff\xd8data")
    assert b"--frame" in chunk
    assert b"Content-Type: image/jpeg" in chunk
    assert chunk.rstrip().endswith(b"data")


def test_health_reports_unhealthy_when_no_frames():
    app = build_video_app(FrameBuffer(), max_age_s=1.0)
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_health_reports_healthy_with_fresh_frame():
    clock = {"t": 0.0}
    buf = FrameBuffer(clock=lambda: clock["t"])
    buf.set(b"\xff\xd8frame")
    app = build_video_app(buf, max_age_s=1.0)
    r = TestClient(app).get("/health")
    assert r.json()["ok"] is True
    assert r.json()["age_s"] == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/video_bridge/test_mjpeg.py -v`
Expected: FAIL — `video_bridge.mjpeg` does not exist.

- [ ] **Step 3: Implement**

Create `src/video_bridge/mjpeg.py`:
```python
import asyncio

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

_BOUNDARY = "frame"


def mjpeg_chunk(jpeg: bytes) -> bytes:
    """One multipart/x-mixed-replace part wrapping a JPEG frame."""
    return (
        f"--{_BOUNDARY}\r\n"
        f"Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(jpeg)}\r\n\r\n"
    ).encode() + jpeg + b"\r\n"


def build_video_app(buffer, max_age_s: float = 2.0, frame_interval_s: float = 0.05) -> FastAPI:
    app = FastAPI(title="video-bridge")

    @app.get("/health")
    def health() -> dict:
        return {"ok": buffer.is_fresh(max_age_s), "age_s": buffer.age_s()}

    @app.get("/stream.mjpg")
    def stream() -> StreamingResponse:
        async def gen():
            while True:
                jpeg = buffer.latest()
                if jpeg is not None:
                    yield mjpeg_chunk(jpeg)
                await asyncio.sleep(frame_interval_s)
        return StreamingResponse(
            gen(), media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}")

    return app
```

- [ ] **Step 4: Run tests to verify they pass + commit**

Run: `pytest tests/video_bridge/test_mjpeg.py -v` → Expected: PASS (the infinite `/stream.mjpg` generator is exercised by the integration test, not here).
```bash
git add src/video_bridge/mjpeg.py tests/video_bridge/test_mjpeg.py
git commit -m "feat(video-bridge): MJPEG stream + health endpoint"
```

---

### Task 8: gz camera source, config, entrypoint

**Files:**
- Create: `src/video_bridge/config.py`, `src/video_bridge/source.py`, `src/video_bridge/__main__.py`
- Test: `tests/video_bridge/test_source.py`, `tests/video_bridge/test_config.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/video_bridge/test_config.py`:
```python
from video_bridge.config import VideoBridgeSettings


def test_defaults():
    s = VideoBridgeSettings()
    assert s.port == 8082
    assert s.jpeg_quality == 80
    assert "image" in s.topic.lower() or s.topic == ""
```

Create `tests/video_bridge/test_source.py`:
```python
from video_bridge.frames import FrameBuffer
from video_bridge.source import on_image


class FakeImage:
    # duck-types the gz.msgs Image fields on_image() reads
    width = 2
    height = 2
    step = 6  # 2px * 3 channels
    data = bytes([0, 255, 0] * 4)  # 2x2 green


def test_on_image_writes_jpeg_to_buffer():
    buf = FrameBuffer()
    on_image(FakeImage(), buf, quality=70)
    jpeg = buf.latest()
    assert jpeg is not None and jpeg[:2] == b"\xff\xd8"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/video_bridge/test_config.py tests/video_bridge/test_source.py -v`
Expected: FAIL — modules do not exist.

- [ ] **Step 3: Implement config + source**

Create `src/video_bridge/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class VideoBridgeSettings(BaseSettings):
    """Video-bridge config from env / .env (prefix VB_)."""
    model_config = SettingsConfigDict(env_file=".env", env_prefix="VB_", extra="ignore")

    topic: str = ""           # gz camera image topic; set from the Task 1 spike
    host: str = "0.0.0.0"
    port: int = 8082
    jpeg_quality: int = 80
    channels: int = 3         # 3=RGB, 4=RGBA
```

Create `src/video_bridge/source.py`:
```python
from video_bridge.frames import encode_jpeg


def on_image(msg, buffer, quality: int = 80, channels: int = 3) -> None:
    """Convert one gz Image message to JPEG and store it. Pure of gz imports."""
    jpeg = encode_jpeg(bytes(msg.data), width=msg.width, height=msg.height,
                       channels=channels, quality=quality)
    buffer.set(jpeg)


def subscribe(topic: str, buffer, quality: int, channels: int):
    """Subscribe to a gz camera topic; returns the gz Node (keep it alive).

    Imports gz bindings lazily so the rest of the package is testable without them.
    """
    from gz.transport13 import Node
    from gz.msgs10.image_pb2 import Image

    node = Node()
    node.subscribe(Image, topic, lambda m: on_image(m, buffer, quality, channels))
    return node
```

Create `src/video_bridge/__main__.py`:
```python
import asyncio

import uvicorn

from video_bridge.config import VideoBridgeSettings
from video_bridge.frames import FrameBuffer
from video_bridge.mjpeg import build_video_app
from video_bridge.source import subscribe


async def run() -> None:
    settings = VideoBridgeSettings()
    buffer = FrameBuffer()
    node = None
    if settings.topic:
        try:
            node = subscribe(settings.topic, buffer, settings.jpeg_quality, settings.channels)
            print(f"video-bridge: subscribed to {settings.topic}")
        except Exception as e:  # no gz / no camera -> serve unhealthy, dashboard falls back
            print(f"video-bridge: camera unavailable ({e}); serving without frames")
    else:
        print("video-bridge: VB_TOPIC unset; serving without frames (set it from the spike)")

    app = build_video_app(buffer)
    config = uvicorn.Config(app, host=settings.host, port=settings.port, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()
    _ = node  # keep reference alive for the process lifetime


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass + commit**

Run: `pytest tests/video_bridge/ -v` → Expected: PASS
```bash
git add src/video_bridge/config.py src/video_bridge/source.py src/video_bridge/__main__.py tests/video_bridge/test_config.py tests/video_bridge/test_source.py
git commit -m "feat(video-bridge): gz camera source, config, and entrypoint"
```

---

## Phase C — Dashboard backend

### Task 9: Dashboard settings

**Files:**
- Create: `src/dashboard/__init__.py`, `src/dashboard/config.py`
- Test: `tests/dashboard/__init__.py`, `tests/dashboard/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/dashboard/__init__.py` (empty) and `tests/dashboard/test_config.py`:
```python
from dashboard.config import DashboardSettings


def test_defaults():
    s = DashboardSettings()
    assert s.port == 8080
    assert s.safety_url.endswith("/ws")
    assert s.video_stream_url.endswith(".mjpg")
    assert s.video_health_url.endswith("/health")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/dashboard/test_config.py -v`
Expected: FAIL — `dashboard` module does not exist.

- [ ] **Step 3: Implement**

Create `src/dashboard/__init__.py` (empty) and `src/dashboard/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class DashboardSettings(BaseSettings):
    """Dashboard backend config from env / .env (prefix DASH_)."""
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DASH_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8080
    safety_url: str = "ws://127.0.0.1:8765/ws"
    video_stream_url: str = "http://127.0.0.1:8082/stream.mjpg"
    video_health_url: str = "http://127.0.0.1:8082/health"
    video_poll_interval_s: float = 2.0
```

- [ ] **Step 4: Run test to verify it passes + commit**

Run: `pytest tests/dashboard/test_config.py -v` → Expected: PASS
```bash
git add src/dashboard/__init__.py src/dashboard/config.py tests/dashboard/
git commit -m "feat(dashboard): backend settings"
```

---

### Task 10: DashboardHub orchestration

**Files:**
- Create: `src/dashboard/hub.py`
- Test: `tests/dashboard/test_hub.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/dashboard/test_hub.py`:
```python
import pytest
from assistant.agent import Agent
from dashboard.hub import DashboardHub


class FakeClient:
    def __init__(self): self.sent = []; self.aborted = False
    async def get_telemetry(self): return {"battery_pct": 0.9, "gps_ok": True}
    async def send_command(self, cmd): self.sent.append(cmd); return {"status": "executed", "verb": cmd["verb"]}
    async def abort(self): self.aborted = True; return {"status": "aborted"}


class FakeProvider:
    def __init__(self, reply): self._reply = reply
    async def complete(self, system, user): return self._reply


def _hub(reply, client=None):
    client = client or FakeClient()
    return DashboardHub(Agent(FakeProvider(reply), client)), client


@pytest.mark.asyncio
async def test_chat_command_produces_proposal_then_confirm_executes():
    hub, client = _hub('{"action":"command","command":{"verb":"loiter"}}')
    out = await hub.handle_chat("hold position")
    assert any(m["type"] == "proposal" and m["command"]["verb"] == "loiter" for m in out)
    out2 = await hub.handle_confirm()
    assert any(m["type"] == "result" and m["status"] == "executed" for m in out2)
    assert client.sent == [{"verb": "loiter"}]


@pytest.mark.asyncio
async def test_chat_question_produces_narration():
    hub, _ = _hub('{"action":"ask","question":"How high?"}')
    out = await hub.handle_chat("go up")
    assert any(m["type"] == "narration" and "How high?" in m["text"] for m in out)


@pytest.mark.asyncio
async def test_confirm_without_pending_is_noop_narration():
    hub, client = _hub("{}")
    out = await hub.handle_confirm()
    assert out and out[0]["type"] == "narration"
    assert client.sent == []


@pytest.mark.asyncio
async def test_cancel_clears_pending():
    hub, client = _hub('{"action":"command","command":{"verb":"loiter"}}')
    await hub.handle_chat("hold")
    await hub.handle_cancel()
    await hub.handle_confirm()
    assert client.sent == []  # nothing executed after cancel


@pytest.mark.asyncio
async def test_abort_returns_result_and_control_state():
    hub, client = _hub("{}")
    out = await hub.handle_abort()
    assert client.aborted is True
    assert any(m["type"] == "control_state" and m["who"] == "manual" for m in out)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/dashboard/test_hub.py -v`
Expected: FAIL — `dashboard.hub` does not exist.

- [ ] **Step 3: Implement**

Create `src/dashboard/hub.py`:
```python
from assistant.command_gen import CommandProposal, QuestionProposal, ErrorProposal


class DashboardHub:
    """Translates browser messages into Agent calls and back into UI frames.

    Pure orchestration: returns lists of dicts to broadcast; holds no transport.
    """

    def __init__(self, agent) -> None:
        self._agent = agent
        self._pending: dict | None = None

    async def handle_chat(self, nl: str) -> list[dict]:
        proposal = await self._agent.propose(nl)
        if isinstance(proposal, CommandProposal):
            self._pending = proposal.command
            return [{"type": "proposal", "command": proposal.command}]
        if isinstance(proposal, QuestionProposal):
            return [{"type": "narration", "text": proposal.question}]
        if isinstance(proposal, ErrorProposal):
            return [{"type": "narration", "text": f"Could not act: {proposal.reason}"}]
        return [{"type": "narration", "text": "Unrecognized request."}]

    async def handle_confirm(self) -> list[dict]:
        if self._pending is None:
            return [{"type": "narration", "text": "Nothing to confirm."}]
        cmd, self._pending = self._pending, None
        result = await self._agent.execute(cmd)
        return [{"type": "result", **result},
                {"type": "narration", "text": _narrate(result)}]

    async def handle_cancel(self) -> list[dict]:
        self._pending = None
        return [{"type": "narration", "text": "Command cancelled."}]

    async def handle_abort(self) -> list[dict]:
        result = await self._agent.abort()
        return [{"type": "result", **result},
                {"type": "control_state", "who": "manual"},
                {"type": "narration", "text": "ABORT — control returned to pilot."}]


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

- [ ] **Step 4: Run tests to verify they pass + commit**

Run: `pytest tests/dashboard/test_hub.py -v` → Expected: PASS
```bash
git add src/dashboard/hub.py tests/dashboard/test_hub.py
git commit -m "feat(dashboard): hub orchestration (chat/confirm/cancel/abort)"
```

---

### Task 11: Broadcaster + browser websocket app

**Files:**
- Create: `src/dashboard/app.py`
- Test: `tests/dashboard/test_app.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/dashboard/test_app.py`:
```python
import asyncio
import pytest
from fastapi.testclient import TestClient
from assistant.agent import Agent
from dashboard.hub import DashboardHub
from dashboard.app import Broadcaster, attach_telemetry, build_app


class FakeClient:
    def __init__(self): self.cb = None; self.sent = []
    async def get_telemetry(self): return {"battery_pct": 0.9}
    async def send_command(self, cmd): self.sent.append(cmd); return {"status": "executed", "verb": cmd["verb"]}
    async def abort(self): return {"status": "aborted"}
    def subscribe_telemetry(self, cb): self.cb = cb


class FakeProvider:
    async def complete(self, system, user): return '{"action":"command","command":{"verb":"loiter"}}'


@pytest.mark.asyncio
async def test_broadcaster_sends_to_all_registered():
    b = Broadcaster()
    got = []
    async def send(m): got.append(m)
    b.register(send)
    await b.broadcast({"type": "telemetry", "data": {"battery_pct": 0.5}})
    assert got == [{"type": "telemetry", "data": {"battery_pct": 0.5}}]


@pytest.mark.asyncio
async def test_attach_telemetry_forwards_pushes_to_broadcaster():
    client = FakeClient()
    b = Broadcaster()
    got = []
    async def send(m): got.append(m)
    b.register(send)
    attach_telemetry(client, b)
    client.cb({"battery_pct": 0.42})        # simulate a push from the safety link
    await asyncio.sleep(0)                   # let the scheduled broadcast run
    assert got and got[-1] == {"type": "telemetry", "data": {"battery_pct": 0.42}}


def test_browser_chat_yields_proposal():
    client = FakeClient()
    hub = DashboardHub(Agent(FakeProvider(), client))
    app = build_app(hub, video_stream_url="http://x/stream.mjpg")
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "text": "hold"})
        # the app sends a video_status frame on connect; drain until the proposal
        msg = ws.receive_json()
        while msg.get("type") != "proposal":
            msg = ws.receive_json()
        assert msg["command"]["verb"] == "loiter"


def test_browser_abort_yields_control_state():
    client = FakeClient()
    hub = DashboardHub(Agent(FakeProvider(), client))
    app = build_app(hub, video_stream_url="http://x/stream.mjpg")
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "abort"})
        found = False
        for _ in range(6):  # skip the initial video_status frame, find control_state
            f = ws.receive_json()
            if f.get("type") == "control_state" and f.get("who") == "manual":
                found = True
                break
        assert found
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/dashboard/test_app.py -v`
Expected: FAIL — `dashboard.app` does not exist.

- [ ] **Step 3: Implement**

Create `src/dashboard/app.py`:
```python
import asyncio
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles


class Broadcaster:
    """Fan-out of server->browser frames to every connected socket sender."""

    def __init__(self) -> None:
        self._senders: list = []

    def register(self, send) -> None:
        self._senders.append(send)

    def unregister(self, send) -> None:
        if send in self._senders:
            self._senders.remove(send)

    async def broadcast(self, message: dict) -> None:
        for send in list(self._senders):
            try:
                await send(message)
            except Exception:
                self.unregister(send)


def attach_telemetry(safety_client, broadcaster: Broadcaster) -> None:
    """Forward safety telemetry pushes to all browsers (scheduled on the loop)."""
    def on_telemetry(data: dict) -> None:
        asyncio.create_task(broadcaster.broadcast({"type": "telemetry", "data": data}))
    safety_client.subscribe_telemetry(on_telemetry)


def build_app(hub, video_stream_url: str, broadcaster: Broadcaster | None = None,
             static_dir: str | None = None) -> FastAPI:
    app = FastAPI(title="dashboard")
    bc = broadcaster or Broadcaster()

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        lock = asyncio.Lock()

        async def send(msg: dict) -> None:
            async with lock:
                await socket.send_json(msg)

        bc.register(send)
        await send({"type": "video_status", "url": video_stream_url, "ok": True})
        try:
            while True:
                msg = await socket.receive_json()
                kind = msg.get("type")
                if kind == "chat":
                    out = await hub.handle_chat(msg.get("text", ""))
                elif kind == "confirm":
                    out = await hub.handle_confirm()
                elif kind == "cancel":
                    out = await hub.handle_cancel()
                elif kind == "abort":
                    out = await hub.handle_abort()
                else:
                    out = [{"type": "narration", "text": "Unknown message."}]
                for frame in out:
                    await send(frame)
        except WebSocketDisconnect:
            return
        finally:
            bc.unregister(send)

    if static_dir and os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app
```

- [ ] **Step 4: Run tests to verify they pass + commit**

Run: `pytest tests/dashboard/test_app.py -v` → Expected: PASS
```bash
git add src/dashboard/app.py tests/dashboard/test_app.py
git commit -m "feat(dashboard): broadcaster + browser websocket app"
```

---

### Task 12: Entrypoint + video status poller

**Files:**
- Create: `src/dashboard/__main__.py`
- Modify: `pyproject.toml` (move `httpx` into runtime deps)
- Test: `tests/dashboard/test_video_status.py`

- [ ] **Step 1: Add httpx to runtime deps**

In `pyproject.toml`, add to `dependencies`:
```toml
    "httpx>=0.27",
```
(It is also listed under `dev`; that is fine.) Run: `. .venv/bin/activate && pip install -e .`

- [ ] **Step 2: Write the failing test**

Create `tests/dashboard/test_video_status.py`:
```python
import pytest
from dashboard.__main__ import poll_once


class FakeResp:
    def __init__(self, ok): self._ok = ok
    def json(self): return {"ok": self._ok, "age_s": 0.1}
    def raise_for_status(self): ...


class FakeHttp:
    def __init__(self, ok=True, fail=False): self._ok = ok; self._fail = fail
    async def get(self, url):
        if self._fail:
            raise RuntimeError("connection refused")
        return FakeResp(self._ok)


@pytest.mark.asyncio
async def test_poll_once_healthy():
    msg = await poll_once(FakeHttp(ok=True), "http://x/health", "http://x/stream.mjpg")
    assert msg == {"type": "video_status", "ok": True, "url": "http://x/stream.mjpg"}


@pytest.mark.asyncio
async def test_poll_once_unreachable_is_not_ok():
    msg = await poll_once(FakeHttp(fail=True), "http://x/health", "http://x/stream.mjpg")
    assert msg["type"] == "video_status" and msg["ok"] is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/dashboard/test_video_status.py -v`
Expected: FAIL — `dashboard.__main__` / `poll_once` does not exist.

- [ ] **Step 4: Implement**

Create `src/dashboard/__main__.py`:
```python
import asyncio
import os

import httpx
import uvicorn

from assistant.agent import Agent
from assistant.command_gen import propose  # noqa: F401  (ensures import graph is wired)
from assistant.config import AssistantSettings
from assistant.llm import OpenRouterProvider
from assistant.safety_client import SafetyClient
from dashboard.app import Broadcaster, attach_telemetry, build_app
from dashboard.config import DashboardSettings
from dashboard.hub import DashboardHub


async def poll_once(http, health_url: str, stream_url: str) -> dict:
    """One video-status probe; never raises (unreachable bridge -> ok:false)."""
    try:
        resp = await http.get(health_url)
        resp.raise_for_status()
        ok = bool(resp.json().get("ok"))
    except Exception:
        ok = False
    return {"type": "video_status", "ok": ok, "url": stream_url}


async def _video_status_loop(broadcaster, dash: DashboardSettings) -> None:
    async with httpx.AsyncClient(timeout=2.0) as http:
        while True:
            await broadcaster.broadcast(
                await poll_once(http, dash.video_health_url, dash.video_stream_url))
            await asyncio.sleep(dash.video_poll_interval_s)


async def run() -> None:
    a_settings = AssistantSettings()
    dash = DashboardSettings()
    if not a_settings.openrouter_api_key:
        raise SystemExit("Set AS_OPENROUTER_API_KEY in .env")

    client = SafetyClient(dash.safety_url)
    await client.connect()
    agent = Agent(OpenRouterProvider.from_settings(a_settings), client)
    hub = DashboardHub(agent)

    broadcaster = Broadcaster()
    attach_telemetry(client, broadcaster)

    static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
    app = build_app(hub, dash.video_stream_url, broadcaster=broadcaster,
                    static_dir=os.path.abspath(static_dir))

    asyncio.create_task(_video_status_loop(broadcaster, dash))
    config = uvicorn.Config(app, host=dash.host, port=dash.port, log_level="info")
    try:
        await uvicorn.Server(config).serve()
    finally:
        await client.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes + commit**

Run: `pytest tests/dashboard/ -v` → Expected: PASS
```bash
git add pyproject.toml src/dashboard/__main__.py tests/dashboard/test_video_status.py
git commit -m "feat(dashboard): entrypoint wiring + video-status poller"
```

---

## Phase D — Frontend (Vite + React + react-three-fiber, Layout B)

### Task 13: Scaffold the frontend

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/index.html`, `frontend/vitest.setup.ts`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/types.ts`
- Test: `frontend/src/App.test.tsx`

- [ ] **Step 1: Create project files**

`frontend/package.json`:
```json
{
  "name": "fpv-dashboard",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "three": "^0.165.0",
    "@react-three/fiber": "^8.16.0",
    "@react-three/drei": "^9.108.0"
  },
  "devDependencies": {
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.4.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@types/three": "^0.165.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^24.1.0",
    "typescript": "^5.5.0",
    "vite": "^5.3.0",
    "vitest": "^2.0.0"
  }
}
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"]
}
```

`frontend/vite.config.ts`:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/ws": { target: "ws://127.0.0.1:8080", ws: true } },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
  },
});
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>FPV Flight Assistant</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/vitest.setup.ts`:
```ts
import "@testing-library/jest-dom";
```

`frontend/src/types.ts`:
```ts
export interface Telemetry {
  lat: number; lon: number; alt_m: number; speed_ms: number;
  battery_pct: number; flight_mode: string; armed: boolean;
  gps_ok: boolean; ekf_ok: boolean;
  roll?: number; pitch?: number; yaw?: number;
}
export interface VideoStatus { ok: boolean; url: string; }
export type ControlWho = "manual" | "assistant";
```

`frontend/src/main.tsx`:
```tsx
import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>
);
```

`frontend/src/App.tsx` (placeholder; replaced in Task 18):
```tsx
export function App() {
  return <div>FPV Flight Assistant</div>;
}
```

- [ ] **Step 2: Write the failing smoke test**

`frontend/src/App.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { App } from "./App";

test("renders the app title", () => {
  render(<App />);
  expect(screen.getByText(/FPV Flight Assistant/i)).toBeInTheDocument();
});
```

- [ ] **Step 3: Install and run the test (it should pass once deps install)**

Run:
```bash
npm --prefix frontend install
npm --prefix frontend test
```
Expected: install succeeds; `App.test.tsx` PASSES. (If install must be offline, note it and proceed when network is available — this is the only networked step.)

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html frontend/vitest.setup.ts frontend/src/
git commit -m "feat(frontend): scaffold Vite + React + TS dashboard"
```

---

### Task 14: useDashboardSocket hook

**Files:**
- Create: `frontend/src/useDashboardSocket.ts`
- Test: `frontend/src/useDashboardSocket.test.tsx`

- [ ] **Step 1: Write the failing test**

`frontend/src/useDashboardSocket.test.tsx`:
```tsx
import { act, renderHook } from "@testing-library/react";
import { useDashboardSocket } from "./useDashboardSocket";

class MockWS {
  static last: MockWS | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  sent: string[] = [];
  constructor(_url: string) { MockWS.last = this; }
  send(d: string) { this.sent.push(d); }
  close() {}
  emit(obj: unknown) { this.onmessage?.({ data: JSON.stringify(obj) }); }
}

beforeEach(() => { (globalThis as any).WebSocket = MockWS as any; MockWS.last = null; });

test("telemetry frame updates state", () => {
  const { result } = renderHook(() => useDashboardSocket("/ws"));
  act(() => MockWS.last!.emit({ type: "telemetry", data: { battery_pct: 0.66, alt_m: 12 } }));
  expect(result.current.telemetry?.battery_pct).toBe(0.66);
});

test("proposal frame is stored and confirm() sends a confirm", () => {
  const { result } = renderHook(() => useDashboardSocket("/ws"));
  act(() => MockWS.last!.emit({ type: "proposal", command: { verb: "loiter" } }));
  expect(result.current.proposal?.verb).toBe("loiter");
  act(() => result.current.confirm());
  expect(MockWS.last!.sent.some((s) => s.includes('"confirm"'))).toBe(true);
});

test("video_status frame updates videoStatus", () => {
  const { result } = renderHook(() => useDashboardSocket("/ws"));
  act(() => MockWS.last!.emit({ type: "video_status", ok: true, url: "http://x/s.mjpg" }));
  expect(result.current.videoStatus?.ok).toBe(true);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test -- useDashboardSocket`
Expected: FAIL — hook file does not exist.

- [ ] **Step 3: Implement**

`frontend/src/useDashboardSocket.ts`:
```ts
import { useEffect, useRef, useState, useCallback } from "react";
import type { Telemetry, VideoStatus, ControlWho } from "./types";

export interface NarrationLine { text: string; }

export function useDashboardSocket(url: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [narration, setNarration] = useState<NarrationLine[]>([]);
  const [proposal, setProposal] = useState<any | null>(null);
  const [control, setControl] = useState<ControlWho>("manual");
  const [videoStatus, setVideoStatus] = useState<VideoStatus | null>(null);

  useEffect(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      switch (m.type) {
        case "telemetry": setTelemetry(m.data); break;
        case "narration": setNarration((n) => [...n, { text: m.text }]); break;
        case "proposal": setProposal(m.command); break;
        case "result": setProposal(null); break;
        case "control_state": setControl(m.who); break;
        case "video_status": setVideoStatus({ ok: m.ok, url: m.url }); break;
      }
    };
    return () => ws.close();
  }, [url]);

  const send = useCallback((obj: unknown) => wsRef.current?.send(JSON.stringify(obj)), []);
  const chat = useCallback((text: string) => send({ type: "chat", text }), [send]);
  const confirm = useCallback(() => { setProposal(null); send({ type: "confirm" }); }, [send]);
  const cancel = useCallback(() => { setProposal(null); send({ type: "cancel" }); }, [send]);
  const abort = useCallback(() => send({ type: "abort" }), [send]);

  return { connected, telemetry, narration, proposal, control, videoStatus,
           chat, confirm, cancel, abort };
}
```

- [ ] **Step 4: Run test to verify it passes + commit**

Run: `npm --prefix frontend test -- useDashboardSocket` → Expected: PASS
```bash
git add frontend/src/useDashboardSocket.ts frontend/src/useDashboardSocket.test.tsx
git commit -m "feat(frontend): dashboard websocket hook"
```

---

### Task 15: Telemetry cards, control state, abort bar

**Files:**
- Create: `frontend/src/components/TelemetryCards.tsx`, `frontend/src/components/AbortBar.tsx`
- Test: `frontend/src/components/TelemetryCards.test.tsx`, `frontend/src/components/AbortBar.test.tsx`

- [ ] **Step 1: Write the failing tests**

`frontend/src/components/TelemetryCards.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { TelemetryCards } from "./TelemetryCards";

test("formats telemetry values", () => {
  render(<TelemetryCards t={{
    lat: 47, lon: 8, alt_m: 25.4, speed_ms: 4.2, battery_pct: 0.78,
    flight_mode: "ORBIT", armed: true, gps_ok: true, ekf_ok: true }} />);
  expect(screen.getByText(/25.4/)).toBeInTheDocument();
  expect(screen.getByText(/78%/)).toBeInTheDocument();
  expect(screen.getByText(/ORBIT/)).toBeInTheDocument();
});

test("shows placeholders when no telemetry", () => {
  render(<TelemetryCards t={null} />);
  expect(screen.getAllByText("—").length).toBeGreaterThan(0);
});
```

`frontend/src/components/AbortBar.test.tsx`:
```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { AbortBar } from "./AbortBar";

test("renders control state and fires onAbort", () => {
  const onAbort = vi.fn();
  render(<AbortBar control="assistant" onAbort={onAbort} />);
  expect(screen.getByText(/ASSISTANT/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /abort/i }));
  expect(onAbort).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend test -- components/`
Expected: FAIL — component files do not exist.

- [ ] **Step 3: Implement**

`frontend/src/components/TelemetryCards.tsx`:
```tsx
import type { Telemetry } from "../types";

const card: React.CSSProperties = {
  background: "#161b22", border: "1px solid #30363d", borderRadius: 6,
  padding: "8px 10px", minWidth: 70,
};

function Card({ label, value }: { label: string; value: string }) {
  return (
    <div style={card}>
      <div style={{ fontSize: 10, color: "#8b949e", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

export function TelemetryCards({ t }: { t: Telemetry | null }) {
  const dash = "—";
  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      <Card label="Alt" value={t ? `${t.alt_m.toFixed(1)} m` : dash} />
      <Card label="Speed" value={t ? `${t.speed_ms.toFixed(1)} m/s` : dash} />
      <Card label="Battery" value={t ? `${Math.round(t.battery_pct * 100)}%` : dash} />
      <Card label="Mode" value={t ? t.flight_mode : dash} />
      <Card label="GPS/EKF" value={t ? `${t.gps_ok ? "ok" : "no"}/${t.ekf_ok ? "ok" : "no"}` : dash} />
    </div>
  );
}
```

`frontend/src/components/AbortBar.tsx`:
```tsx
import type { ControlWho } from "../types";

export function AbortBar({ control, onAbort }:
  { control: ControlWho; onAbort: () => void }) {
  const isAssistant = control === "assistant";
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "8px 14px", background: "#0d1117", borderBottom: "1px solid #30363d" }}>
      <span style={{ fontWeight: 700, color: isAssistant ? "#3fb950" : "#58a6ff" }}>
        {isAssistant ? "🟢 ASSISTANT IN CONTROL" : "🔵 MANUAL (PILOT)"}
      </span>
      <button onClick={onAbort}
        style={{ background: "#da3633", color: "#fff", fontWeight: 800, border: "none",
                 borderRadius: 6, padding: "10px 18px", fontSize: 15, cursor: "pointer" }}>
        ABORT / TAKE CONTROL
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass + commit**

Run: `npm --prefix frontend test -- components/` → Expected: PASS
```bash
git add frontend/src/components/TelemetryCards.tsx frontend/src/components/TelemetryCards.test.tsx frontend/src/components/AbortBar.tsx frontend/src/components/AbortBar.test.tsx
git commit -m "feat(frontend): telemetry cards + abort/control bar"
```

---

### Task 16: Chat panel with preview/confirm

**Files:**
- Create: `frontend/src/components/ChatPanel.tsx`
- Test: `frontend/src/components/ChatPanel.test.tsx`

- [ ] **Step 1: Write the failing tests**

`frontend/src/components/ChatPanel.test.tsx`:
```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatPanel } from "./ChatPanel";

const noop = () => {};

test("typing and submitting fires onChat", () => {
  const onChat = vi.fn();
  render(<ChatPanel narration={[]} proposal={null}
    onChat={onChat} onConfirm={noop} onCancel={noop} />);
  fireEvent.change(screen.getByPlaceholderText(/type a command/i), { target: { value: "orbit 30m" } });
  fireEvent.submit(screen.getByTestId("chat-form"));
  expect(onChat).toHaveBeenCalledWith("orbit 30m");
});

test("a pending proposal shows preview with Confirm and Cancel", () => {
  const onConfirm = vi.fn();
  render(<ChatPanel narration={[{ text: "hi" }]} proposal={{ verb: "orbit", radius: 30 }}
    onChat={noop} onConfirm={onConfirm} onCancel={noop} />);
  expect(screen.getByText(/orbit/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /confirm/i }));
  expect(onConfirm).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend test -- ChatPanel`
Expected: FAIL — component does not exist.

- [ ] **Step 3: Implement**

`frontend/src/components/ChatPanel.tsx`:
```tsx
import { useState } from "react";
import type { NarrationLine } from "../useDashboardSocket";

export function ChatPanel({ narration, proposal, onChat, onConfirm, onCancel }: {
  narration: NarrationLine[];
  proposal: any | null;
  onChat: (text: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState("");
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 6 }}>
        {narration.map((n, i) => (
          <div key={i} style={{ background: "#21262d", borderRadius: 6, padding: "6px 9px" }}>{n.text}</div>
        ))}
      </div>

      {proposal && (
        <div style={{ border: "1px solid #d29922", borderRadius: 6, padding: 10, margin: "8px 0" }}>
          <div style={{ fontSize: 11, color: "#d29922", textTransform: "uppercase" }}>Proposed command</div>
          <pre style={{ margin: "4px 0", whiteSpace: "pre-wrap" }}>{JSON.stringify(proposal, null, 0)}</pre>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={onConfirm}
              style={{ background: "#238636", color: "#fff", border: "none", borderRadius: 5, padding: "6px 14px", cursor: "pointer" }}>
              Confirm
            </button>
            <button onClick={onCancel}
              style={{ background: "#30363d", color: "#fff", border: "none", borderRadius: 5, padding: "6px 14px", cursor: "pointer" }}>
              Cancel
            </button>
          </div>
        </div>
      )}

      <form data-testid="chat-form" onSubmit={(e) => { e.preventDefault(); if (text.trim()) { onChat(text.trim()); setText(""); } }}
        style={{ display: "flex", gap: 6, marginTop: 8 }}>
        <input value={text} onChange={(e) => setText(e.target.value)}
          placeholder="Type a command…"
          style={{ flex: 1, background: "#0d1117", color: "#c9d1d9", border: "1px solid #30363d", borderRadius: 6, padding: "8px 10px" }} />
        <button type="submit"
          style={{ background: "#1f6feb", color: "#fff", border: "none", borderRadius: 6, padding: "8px 14px", cursor: "pointer" }}>
          Send
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass + commit**

Run: `npm --prefix frontend test -- ChatPanel` → Expected: PASS
```bash
git add frontend/src/components/ChatPanel.tsx frontend/src/components/ChatPanel.test.tsx
git commit -m "feat(frontend): chat panel with command preview/confirm"
```

---

### Task 17: Video pane with MJPEG + Three.js fallback

**Files:**
- Create: `frontend/src/components/VideoPane.tsx`, `frontend/src/components/FallbackScene.tsx`
- Test: `frontend/src/components/VideoPane.test.tsx`

- [ ] **Step 1: Write the failing test**

`frontend/src/components/VideoPane.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { VideoPane } from "./VideoPane";

// Stub the WebGL fallback so jsdom doesn't try to render Three.js.
vi.mock("./FallbackScene", () => ({ FallbackScene: () => <div data-testid="fallback" /> }));

test("shows MJPEG image when video is ok", () => {
  render(<VideoPane videoStatus={{ ok: true, url: "http://x/s.mjpg" }} telemetry={null} />);
  const img = screen.getByRole("img") as HTMLImageElement;
  expect(img.src).toContain("http://x/s.mjpg");
});

test("shows the fallback scene when video is not ok", () => {
  render(<VideoPane videoStatus={{ ok: false, url: "http://x/s.mjpg" }} telemetry={null} />);
  expect(screen.getByTestId("fallback")).toBeInTheDocument();
});

test("shows the fallback scene when status is unknown", () => {
  render(<VideoPane videoStatus={null} telemetry={null} />);
  expect(screen.getByTestId("fallback")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test -- VideoPane`
Expected: FAIL — components do not exist.

- [ ] **Step 3: Implement**

`frontend/src/components/FallbackScene.tsx`:
```tsx
import { Canvas } from "@react-three/fiber";
import { Grid } from "@react-three/drei";
import type { Telemetry } from "../types";

const D = Math.PI / 180;

export function FallbackScene({ t }: { t: Telemetry | null }) {
  const alt = t ? Math.max(0.2, t.alt_m / 10) : 0.2;
  const rot: [number, number, number] = t
    ? [(t.pitch ?? 0) * D, (t.yaw ?? 0) * D, (t.roll ?? 0) * D]
    : [0, 0, 0];
  return (
    <Canvas camera={{ position: [4, 3, 5], fov: 55 }} style={{ width: "100%", height: "100%" }}>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 8, 5]} intensity={0.8} />
      <Grid args={[40, 40]} cellColor="#1f6feb" sectionColor="#30363d" infiniteGrid />
      <mesh position={[0, alt, 0]} rotation={rot}>
        <boxGeometry args={[0.8, 0.2, 0.8]} />
        <meshStandardMaterial color="#3fb950" />
      </mesh>
    </Canvas>
  );
}
```

`frontend/src/components/VideoPane.tsx`:
```tsx
import type { Telemetry, VideoStatus } from "../types";
import { FallbackScene } from "./FallbackScene";

export function VideoPane({ videoStatus, telemetry }:
  { videoStatus: VideoStatus | null; telemetry: Telemetry | null }) {
  const box: React.CSSProperties = {
    position: "relative", width: "100%", height: "100%", background: "#000", overflow: "hidden",
  };
  const tag = (label: string) => (
    <span style={{ position: "absolute", top: 8, left: 8, fontSize: 11,
                   background: "rgba(0,0,0,.6)", padding: "2px 8px", borderRadius: 10 }}>{label}</span>
  );
  if (videoStatus?.ok) {
    return (
      <div style={box}>
        <img src={videoStatus.url} alt="FPV video"
             style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        {tag("LIVE · gz camera")}
      </div>
    );
  }
  return (
    <div style={box}>
      <FallbackScene t={telemetry} />
      {tag("SIMULATED · telemetry scene")}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes + commit**

Run: `npm --prefix frontend test -- VideoPane` → Expected: PASS
```bash
git add frontend/src/components/VideoPane.tsx frontend/src/components/FallbackScene.tsx frontend/src/components/VideoPane.test.tsx
git commit -m "feat(frontend): video pane with MJPEG + Three.js fallback"
```

---

### Task 18: App composition (Layout B) + production build

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/App.test.tsx`

- [ ] **Step 1: Update the failing test**

Replace `frontend/src/App.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { App } from "./App";

// Avoid real WebSocket + WebGL in jsdom.
beforeEach(() => {
  (globalThis as any).WebSocket = class {
    onmessage = null; onopen = null; onclose = null;
    constructor(_: string) {} send() {} close() {}
  } as any;
});
vi.mock("./components/FallbackScene", () => ({ FallbackScene: () => <div data-testid="fallback" /> }));

test("renders abort bar, telemetry cards, and chat", () => {
  render(<App />);
  expect(screen.getByRole("button", { name: /abort/i })).toBeInTheDocument();
  expect(screen.getByText(/Alt/i)).toBeInTheDocument();
  expect(screen.getByPlaceholderText(/type a command/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test -- App`
Expected: FAIL — placeholder `App` has none of these elements.

- [ ] **Step 3: Implement Layout B**

Replace `frontend/src/App.tsx`:
```tsx
import { useDashboardSocket } from "./useDashboardSocket";
import { AbortBar } from "./components/AbortBar";
import { TelemetryCards } from "./components/TelemetryCards";
import { ChatPanel } from "./components/ChatPanel";
import { VideoPane } from "./components/VideoPane";

const WS_URL = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";

export function App() {
  const d = useDashboardSocket(WS_URL);
  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column",
                  background: "#010409", color: "#c9d1d9",
                  fontFamily: "system-ui, sans-serif" }}>
      <AbortBar control={d.control} onAbort={d.abort} />
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1fr 360px", minHeight: 0 }}>
        <div style={{ minHeight: 0 }}>
          <VideoPane videoStatus={d.videoStatus} telemetry={d.telemetry} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: 12,
                      borderLeft: "1px solid #30363d", minHeight: 0 }}>
          <TelemetryCards t={d.telemetry} />
          <div style={{ flex: 1, minHeight: 0 }}>
            <ChatPanel narration={d.narration} proposal={d.proposal}
              onChat={d.chat} onConfirm={d.confirm} onCancel={d.cancel} />
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the full frontend suite, then build**

Run:
```bash
npm --prefix frontend test
npm --prefix frontend run build
```
Expected: all Vitest tests PASS; `frontend/dist/` is produced (TypeScript compiles clean).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat(frontend): compose Layout B dashboard"
```

---

## Phase E — Integration & docs

### Task 19: End-to-end integration test + run docs

**Files:**
- Create: `tests/dashboard/test_integration.py`
- Create: `scripts/dashboard_smoke.py`

- [ ] **Step 1: Write the integration test (deselected by default)**

Create `tests/dashboard/test_integration.py`:
```python
import asyncio
import json
import pytest
import websockets

pytestmark = pytest.mark.integration  # requires SITL + flight-safety + dashboard running


@pytest.mark.asyncio
async def test_dashboard_chat_to_execute():
    """With SITL, flight-safety (:8765) and dashboard (:8080) up: chat -> proposal -> confirm.

    Run beforehand (separate terminals):
      python -m flight_safety
      python -m dashboard
    """
    async with websockets.connect("ws://127.0.0.1:8080/ws") as ws:
        # first frame is video_status; then telemetry begins streaming
        saw_telemetry = False
        await ws.send(json.dumps({"type": "chat", "text": "loiter"}))
        proposal = None
        for _ in range(50):
            frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if frame.get("type") == "telemetry":
                saw_telemetry = True
            if frame.get("type") == "proposal":
                proposal = frame
                break
        assert proposal is not None and proposal["command"]["verb"] == "loiter"
        assert saw_telemetry, "expected live telemetry push frames"
        await ws.send(json.dumps({"type": "confirm"}))
        result = None
        for _ in range(50):
            frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if frame.get("type") == "result":
                result = frame
                break
        assert result is not None and result["status"] in ("executed", "rejected")
```

- [ ] **Step 2: Verify it is deselected by the unit run**

Run: `pytest -q`
Expected: full unit suite PASSES; the new integration test is deselected (not run).

- [ ] **Step 3: Add a manual smoke helper**

Create `scripts/dashboard_smoke.py`:
```python
"""Manual smoke: prints the first few frames the dashboard pushes to a browser.

Prereqs (separate terminals): SITL, `python -m flight_safety`, `python -m dashboard`.
Usage: python scripts/dashboard_smoke.py
"""
import asyncio
import json

import websockets


async def main() -> None:
    async with websockets.connect("ws://127.0.0.1:8080/ws") as ws:
        await ws.send(json.dumps({"type": "chat", "text": "what is my battery?"}))
        for _ in range(10):
            print(json.loads(await ws.recv()))


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Commit**

```bash
git add tests/dashboard/test_integration.py scripts/dashboard_smoke.py
git commit -m "test(dashboard): end-to-end integration test + smoke helper"
```

- [ ] **Step 5: (When SITL is available) run the live integration**

Run (after starting SITL + `python -m video_bridge` + `python -m flight_safety` + `python -m dashboard`):
```bash
pytest -m integration tests/dashboard/test_integration.py -v
```
Expected: PASS — proposal returned, telemetry observed, command executed/rejected. Open `http://<host>:8080` in a browser and confirm video (or fallback scene), live HUD, chat preview/confirm, and ABORT all work. Record any gotchas in ROADMAP.

---

### Task 20: Update ROADMAP + close follow-ups

**Files:**
- Modify: `ROADMAP.md`, `docs/M1-followups.md`

- [ ] **Step 1: Update ROADMAP status + run instructions**

In `ROADMAP.md`:
- Set **Current focus** to M4 (eval harness) and bump **Last updated**.
- Tick `- [x] **M3 — FPV web dashboard**` with a one-line "Merged; validated live" note.
- Add to **How to run**:
```bash
python -m video_bridge                      # MJPEG video bridge (needs SITL camera airframe)
python -m dashboard                         # dashboard backend; open http://<host>:8080
npm --prefix frontend install && npm --prefix frontend run build   # build the UI once
npm --prefix frontend run dev               # OR Vite dev server (proxies /ws to :8080)
```
- Add gotchas: the three-process layout + ports (safety 8765, video 8082, dashboard 8080); MJPEG `<img>` points directly at the bridge; fallback Three.js scene when `video_status.ok` is false.

- [ ] **Step 2: Close the relevant M1 follow-ups**

In `docs/M1-followups.md`, mark **done** under *API contract gaps*: the telemetry push stream and the request `id` correlation (both delivered in M3, Tasks 2–4).

- [ ] **Step 3: Run the full unit suite one last time**

Run: `. .venv/bin/activate && pytest -q && npm --prefix frontend test`
Expected: all Python unit tests PASS (integration deselected); all Vitest tests PASS.

- [ ] **Step 4: Commit**

```bash
git add ROADMAP.md docs/M1-followups.md
git commit -m "docs(M3): tick milestone, run instructions, close push/id follow-ups"
```

- [ ] **Step 5: Finish the branch**

Use the `superpowers:finishing-a-development-branch` skill to merge `feat/fpv-dashboard` into `main` (squash or merge per project convention), after confirming the full suite is green.

---

## Self-review notes (coverage vs spec)

- **§4.1 telemetry push** → Task 2. **§4.1 request id** → Task 3. **§4.2 demux client** → Task 4. **§4.3 attitude** → Task 5.
- **§4.4 video bridge** (encode/buffer/MJPEG/health/gz source/config/entry) → Tasks 6–8.
- **§4.5 dashboard backend** (config/hub/broadcaster+ws/entry+video-status) → Tasks 9–12.
- **§4.6 frontend Layout B** (scaffold/hook/cards+abort/chat/video+fallback/app) → Tasks 13–18.
- **§5 data flow**, **§6 error handling** (video fallback, abort, narration) → exercised across Tasks 10–18 + Task 19.
- **§7 testing** (unit per component; integration marked; spike first) → Task 1 + per-task tests + Task 19.
