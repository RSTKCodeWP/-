# Assistant Core (M2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A model-agnostic LLM assistant that turns natural-language operator requests into the **structured commands the M1 Flight-Safety service already validates and flies**, with a confirm step and result reporting — delivered as a CLI loop (the web dashboard is M3).

**Architecture:** A new `assistant` package (the "Assistant + Dashboard service" from the design spec, dashboard deferred to M3). It talks to the M1 service over its websocket API. The LLM emits **constrained JSON** (validated against the M1 command schema, with one retry on invalid) — never native tool-calling — so any OpenRouter/OpenAI-compatible model works. The assistant fetches a **telemetry snapshot on demand** for command context (a new `get_telemetry` request added to the M1 service); the real-time HUD stream is M3.

**Tech Stack:** Python 3.11, asyncio, `openai` SDK (pointed at OpenRouter), `websockets` (client to the M1 service), pydantic v2 (reuse `flight_safety.models` for command validation), pytest + pytest-asyncio.

**Conventions:** Run from project root `/hey/projects/yzup-demo`; venv at `.venv` (`. .venv/bin/activate`). Branch `feat/assistant-core`. Live-LLM tasks need an OpenRouter key in `.env` (`AS_OPENROUTER_API_KEY=...`); live end-to-end also needs the M1 service + PX4 SITL running. Tasks that need either are marked and deferred to run-time.

---

## Task M2.0: Add `get_telemetry` to the M1 service

**Files:**
- Modify: `src/flight_safety/dispatcher.py` (add `telemetry()`)
- Modify: `src/flight_safety/server.py` (handle `get_telemetry`)
- Modify: `tests/flight_safety/test_server.py` (add a test)

- [ ] **Step 1: Write the failing test** — append to `tests/flight_safety/test_server.py`:
```python
def test_get_telemetry_returns_snapshot():
    class TelemetryDispatcher:
        async def handle(self, raw): return {"status": "executed"}
        async def abort(self): ...
        async def telemetry(self):
            return {"lat": 47.0, "lon": 8.0, "alt_m": 0.0, "battery_pct": 0.9,
                    "flight_mode": "HOLD", "armed": False, "gps_ok": True, "ekf_ok": True,
                    "speed_ms": 0.0}
    client = TestClient(build_app(TelemetryDispatcher()))
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "get_telemetry"})
        msg = ws.receive_json()
        assert msg["type"] == "telemetry"
        assert msg["data"]["battery_pct"] == 0.9
```

- [ ] **Step 2: Run it, verify it fails**

Run: `pytest tests/flight_safety/test_server.py::test_get_telemetry_returns_snapshot -v`
Expected: FAIL (server replies `{"status":"error","reason":"unknown type"}`, so `msg["type"]` KeyErrors / assertion fails).

- [ ] **Step 3: Add `telemetry()` to `Dispatcher`** in `src/flight_safety/dispatcher.py`:
```python
    async def telemetry(self) -> dict:
        """Return a current telemetry snapshot as a plain dict (for the assistant)."""
        return (await self._bridge.read_telemetry()).model_dump()
```

- [ ] **Step 4: Handle `get_telemetry` in the `/ws` loop** in `src/flight_safety/server.py`. Add this branch BEFORE the final `else:` in the message loop:
```python
                elif kind == "get_telemetry":
                    try:
                        data = await dispatcher.telemetry()
                        await send({"type": "telemetry", "data": data})
                    except Exception as e:
                        await send({"type": "telemetry", "error": str(e)})
```

- [ ] **Step 5: Run tests, verify pass**

Run: `pytest tests/flight_safety/test_server.py -v` → all pass (existing + new). Then `pytest -q` → full suite green (was 39 passed + 3 deselected; now 40 + 3).

- [ ] **Step 6: Commit**
```bash
git add src/flight_safety/dispatcher.py src/flight_safety/server.py tests/flight_safety/test_server.py
git commit -m "feat(m2.0): get_telemetry snapshot request on the flight-safety service"
```

---

## Task M2.1: Assistant package scaffold + config

**Files:**
- Modify: `pyproject.toml` (add `openai` dep)
- Create: `src/assistant/__init__.py`, `tests/assistant/__init__.py`
- Create: `src/assistant/config.py`, `tests/assistant/test_config.py`
- Modify: `.env.example`

- [ ] **Step 1: Add the dependency** — in `pyproject.toml`, add `"openai>=1.40"` to `dependencies`. Then `pip install -e ".[dev]"`.

- [ ] **Step 2: Write the failing test** — `tests/assistant/test_config.py`:
```python
from assistant.config import AssistantSettings


def test_defaults():
    s = AssistantSettings(openrouter_api_key="sk-test")
    assert s.model
    assert s.base_url.startswith("https://")
    assert s.safety_url.startswith("ws://")
    assert s.openrouter_api_key == "sk-test"
```

- [ ] **Step 3: Run it, verify it fails** — `pytest tests/assistant/test_config.py -v` → `ModuleNotFoundError: No module named 'assistant.config'`.

- [ ] **Step 4: Implement** — `src/assistant/__init__.py`:
```python
"""Model-agnostic LLM flight assistant (talks to the flight-safety service)."""
```
`src/assistant/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class AssistantSettings(BaseSettings):
    """Assistant config from env / .env (prefix AS_)."""
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AS_", extra="ignore")

    openrouter_api_key: str = ""
    model: str = "google/gemini-2.0-flash-001"   # any OpenRouter model id
    base_url: str = "https://openrouter.ai/api/v1"
    safety_url: str = "ws://127.0.0.1:8765/ws"
```
Create empty `tests/assistant/__init__.py`.

- [ ] **Step 5: Run, verify pass** — `pytest tests/assistant/test_config.py -v` → 1 passed.

- [ ] **Step 6: Update `.env.example`** — append:
```
# Assistant (M2). Get a key at https://openrouter.ai/keys
AS_OPENROUTER_API_KEY=sk-or-...
AS_MODEL=google/gemini-2.0-flash-001
```

- [ ] **Step 7: Commit**
```bash
git add pyproject.toml src/assistant/__init__.py src/assistant/config.py tests/assistant/__init__.py tests/assistant/test_config.py .env.example
git commit -m "chore(m2.1): scaffold assistant package + config"
```

---

## Task M2.2: LLM provider abstraction + OpenRouter adapter

**Files:**
- Create: `src/assistant/llm.py`, `tests/assistant/test_llm.py`

- [ ] **Step 1: Write the failing test** — `tests/assistant/test_llm.py` (uses a fake OpenAI-compatible client, no network):
```python
import pytest
from assistant.llm import OpenRouterProvider


class _FakeMessage:
    def __init__(self, content): self.message = type("M", (), {"content": content})


class _FakeCompletions:
    def __init__(self, recorder): self._rec = recorder
    async def create(self, **kwargs):
        self._rec.update(kwargs)
        return type("R", (), {"choices": [_FakeMessage("hello")]})


class _FakeClient:
    def __init__(self, recorder): self.chat = type("C", (), {"completions": _FakeCompletions(recorder)})


@pytest.mark.asyncio
async def test_provider_calls_model_and_returns_text():
    rec = {}
    p = OpenRouterProvider(model="test/model", client=_FakeClient(rec))
    out = await p.complete("SYS", "USER")
    assert out == "hello"
    assert rec["model"] == "test/model"
    assert rec["messages"][0]["role"] == "system" and rec["messages"][0]["content"] == "SYS"
    assert rec["messages"][1]["role"] == "user" and rec["messages"][1]["content"] == "USER"
    assert rec["temperature"] == 0
```

- [ ] **Step 2: Run, verify fail** — `ModuleNotFoundError: No module named 'assistant.llm'`.

- [ ] **Step 3: Implement** — `src/assistant/llm.py`:
```python
from typing import Protocol


class LLMProvider(Protocol):
    async def complete(self, system: str, user: str) -> str: ...


class OpenRouterProvider:
    """Model-agnostic provider over any OpenAI-compatible endpoint (OpenRouter by default)."""

    def __init__(self, model: str, client) -> None:
        self._model = model
        self._client = client

    @classmethod
    def from_settings(cls, settings) -> "OpenRouterProvider":
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openrouter_api_key, base_url=settings.base_url)
        return cls(model=settings.model, client=client)

    async def complete(self, system: str, user: str) -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0,
        )
        return resp.choices[0].message.content
```

- [ ] **Step 4: Run, verify pass** — `pytest tests/assistant/test_llm.py -v` → 1 passed.

- [ ] **Step 5: Commit**
```bash
git add src/assistant/llm.py tests/assistant/test_llm.py
git commit -m "feat(m2.2): model-agnostic LLM provider (OpenRouter adapter)"
```

---

## Task M2.3: Command generation (constrained structured output + retry)

**Files:**
- Create: `src/assistant/command_gen.py`, `tests/assistant/test_command_gen.py`

- [ ] **Step 1: Write the failing tests** — `tests/assistant/test_command_gen.py`:
```python
import pytest
from assistant.command_gen import propose, CommandProposal, QuestionProposal, ErrorProposal


class FakeProvider:
    def __init__(self, replies): self._replies = list(replies); self.calls = []
    async def complete(self, system, user):
        self.calls.append((system, user))
        return self._replies.pop(0)


TLM = {"lat": 47.397, "lon": 8.545, "alt_m": 0.0, "battery_pct": 0.9,
       "flight_mode": "HOLD", "armed": False, "gps_ok": True, "ekf_ok": True, "speed_ms": 0.0}


@pytest.mark.asyncio
async def test_valid_command_json():
    p = FakeProvider(['{"action":"command","command":{"verb":"orbit","radius":30,"alt":25}}'])
    out = await propose(p, "orbit the building at 25 meters, 30 meter radius", TLM)
    assert isinstance(out, CommandProposal)
    assert out.command["verb"] == "orbit" and out.command["radius"] == 30


@pytest.mark.asyncio
async def test_strips_markdown_fences():
    p = FakeProvider(['```json\n{"action":"command","command":{"verb":"return_to_launch"}}\n```'])
    out = await propose(p, "come home", TLM)
    assert isinstance(out, CommandProposal) and out.command["verb"] == "return_to_launch"


@pytest.mark.asyncio
async def test_clarifying_question():
    p = FakeProvider(['{"action":"ask","question":"Which altitude should I use?"}'])
    out = await propose(p, "fly up", TLM)
    assert isinstance(out, QuestionProposal) and "altitude" in out.question.lower()


@pytest.mark.asyncio
async def test_invalid_then_valid_retry():
    p = FakeProvider([
        '{"action":"command","command":{"verb":"orbit","radius":-5,"alt":25}}',  # invalid radius
        '{"action":"command","command":{"verb":"orbit","radius":30,"alt":25}}',  # corrected
    ])
    out = await propose(p, "orbit", TLM)
    assert isinstance(out, CommandProposal) and out.command["radius"] == 30
    assert len(p.calls) == 2  # retried once


@pytest.mark.asyncio
async def test_persistently_invalid_returns_error():
    p = FakeProvider(['not json', 'still not json'])
    out = await propose(p, "do something", TLM)
    assert isinstance(out, ErrorProposal)
    assert len(p.calls) == 2
```

- [ ] **Step 2: Run, verify fail** — `ModuleNotFoundError: No module named 'assistant.command_gen'`.

- [ ] **Step 3: Implement** — `src/assistant/command_gen.py`:
```python
import json
from dataclasses import dataclass
from pydantic import ValidationError
from flight_safety.models import parse_command

_VERB_HELP = """\
Allowed commands (emit ONE, with exact fields):
- arm_takeoff: {"verb":"arm_takeoff","alt":<m, 0-120>}
- goto: {"verb":"goto","lat":<deg>,"lon":<deg>,"alt":<m,0-120>}
- orbit: {"verb":"orbit","radius":<m,0-200>,"alt":<m,0-120>,"center":[<lat>,<lon>] or omit}
- loiter: {"verb":"loiter"}
- return_to_launch: {"verb":"return_to_launch"}
- land: {"verb":"land"}
- takeover: {"verb":"takeover"}
- handback: {"verb":"handback"}"""

_SYSTEM = f"""You are a UAV flight-command translator. Convert the operator's request into ONE \
structured action. Reply with ONLY a JSON object, no prose, no markdown.
Either: {{"action":"command","command":{{...}}}} using exactly one allowed command,
or:     {{"action":"ask","question":"..."}} if the request is ambiguous or missing required values.
{_VERB_HELP}
Never invent coordinates. If the user references a place you don't have coordinates for, ask."""


@dataclass
class CommandProposal:
    command: dict

@dataclass
class QuestionProposal:
    question: str

@dataclass
class ErrorProposal:
    reason: str


def _extract_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```")[1]
        if t.startswith("json"):
            t = t[4:]
    return json.loads(t.strip())


async def propose(provider, nl: str, telemetry: dict, max_retries: int = 1):
    """Ask the LLM for a structured command/question; validate; retry once on invalid."""
    user = f"Operator request: {nl}\nCurrent telemetry: {json.dumps(telemetry)}"
    last_err = "no response"
    for attempt in range(max_retries + 1):
        raw = await provider.complete(_SYSTEM, user)
        try:
            obj = _extract_json(raw)
        except (ValueError, IndexError):
            last_err = "output was not valid JSON"
            user = f"Your previous reply was not valid JSON. {last_err}. Re-send ONLY the JSON object."
            continue
        if obj.get("action") == "ask":
            return QuestionProposal(question=str(obj.get("question", "Could you clarify?")))
        if obj.get("action") == "command":
            cmd = obj.get("command", {})
            try:
                parse_command(cmd)  # validate against the M1 schema
            except ValidationError as e:
                last_err = f"command failed validation: {e.errors()[0]['msg']}"
                user = f"Your command was invalid ({last_err}). Re-send a corrected JSON object only."
                continue
            return CommandProposal(command=cmd)
        last_err = "missing or unknown 'action'"
        user = f"Your reply was malformed ({last_err}). Re-send ONLY {{'action':...}} JSON."
    return ErrorProposal(reason=f"Could not produce a valid command after retries: {last_err}")
```

- [ ] **Step 4: Run, verify pass** — `pytest tests/assistant/test_command_gen.py -v` → 5 passed.

- [ ] **Step 5: Commit**
```bash
git add src/assistant/command_gen.py tests/assistant/test_command_gen.py
git commit -m "feat(m2.3): constrained structured-output command generation with validation+retry"
```

---

## Task M2.4: Safety-service websocket client

**Files:**
- Create: `src/assistant/safety_client.py`, `tests/assistant/test_safety_client.py`

- [ ] **Step 1: Write the failing test** — `tests/assistant/test_safety_client.py` (spins a tiny in-process fake ws server, no SITL):
```python
import asyncio, json, pytest, websockets
from assistant.safety_client import SafetyClient


async def _fake_server(websocket):
    async for raw in websocket:
        msg = json.loads(raw)
        if msg["type"] == "get_telemetry":
            await websocket.send(json.dumps({"type": "telemetry", "data": {"battery_pct": 0.8}}))
        elif msg["type"] == "command":
            await websocket.send(json.dumps({"status": "executed", "verb": msg["command"]["verb"]}))
        elif msg["type"] == "abort":
            await websocket.send(json.dumps({"status": "aborted"}))


@pytest.mark.asyncio
async def test_client_roundtrips():
    async with websockets.serve(_fake_server, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = SafetyClient(f"ws://127.0.0.1:{port}")
        await client.connect()
        tlm = await client.get_telemetry()
        assert tlm["battery_pct"] == 0.8
        res = await client.send_command({"verb": "loiter"})
        assert res["status"] == "executed" and res["verb"] == "loiter"
        ab = await client.abort()
        assert ab["status"] == "aborted"
        await client.close()
```

- [ ] **Step 2: Run, verify fail** — `ModuleNotFoundError: No module named 'assistant.safety_client'`.

- [ ] **Step 3: Implement** — `src/assistant/safety_client.py`:
```python
import json
import websockets


class SafetyClient:
    """Websocket client to the flight-safety service."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._ws = None

    async def connect(self) -> None:
        self._ws = await websockets.connect(self._url)

    async def _send_recv(self, payload: dict) -> dict:
        await self._ws.send(json.dumps(payload))
        return json.loads(await self._ws.recv())

    async def get_telemetry(self) -> dict:
        reply = await self._send_recv({"type": "get_telemetry"})
        if reply.get("error"):
            raise RuntimeError(f"telemetry unavailable: {reply['error']}")
        return reply["data"]

    async def send_command(self, command: dict) -> dict:
        return await self._send_recv({"type": "command", "command": command})

    async def abort(self) -> dict:
        return await self._send_recv({"type": "abort"})

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
```

- [ ] **Step 4: Run, verify pass** — `pytest tests/assistant/test_safety_client.py -v` → 1 passed.

- [ ] **Step 5: Commit**
```bash
git add src/assistant/safety_client.py tests/assistant/test_safety_client.py
git commit -m "feat(m2.4): websocket client to the flight-safety service"
```

---

## Task M2.5: Agent loop

**Files:**
- Create: `src/assistant/agent.py`, `tests/assistant/test_agent.py`

- [ ] **Step 1: Write the failing tests** — `tests/assistant/test_agent.py`:
```python
import pytest
from assistant.agent import Agent
from assistant.command_gen import CommandProposal, QuestionProposal


class FakeClient:
    def __init__(self): self.sent = []; self._tlm = {"battery_pct": 0.9, "gps_ok": True}
    async def get_telemetry(self): return self._tlm
    async def send_command(self, cmd): self.sent.append(cmd); return {"status": "executed", "verb": cmd["verb"]}
    async def abort(self): return {"status": "aborted"}


class FakeProvider:
    def __init__(self, reply): self._reply = reply
    async def complete(self, system, user): return self._reply


@pytest.mark.asyncio
async def test_propose_returns_command_with_telemetry_context():
    client = FakeClient()
    agent = Agent(FakeProvider('{"action":"command","command":{"verb":"loiter"}}'), client)
    proposal = await agent.propose("hold position")
    assert isinstance(proposal, CommandProposal) and proposal.command["verb"] == "loiter"


@pytest.mark.asyncio
async def test_propose_can_ask():
    agent = Agent(FakeProvider('{"action":"ask","question":"How high?"}'), FakeClient())
    proposal = await agent.propose("go up")
    assert isinstance(proposal, QuestionProposal)


@pytest.mark.asyncio
async def test_execute_sends_command():
    client = FakeClient()
    agent = Agent(FakeProvider("{}"), client)
    res = await agent.execute({"verb": "loiter"})
    assert res["status"] == "executed"
    assert client.sent == [{"verb": "loiter"}]


@pytest.mark.asyncio
async def test_abort_delegates():
    client = FakeClient()
    agent = Agent(FakeProvider("{}"), client)
    assert (await agent.abort())["status"] == "aborted"
```

- [ ] **Step 2: Run, verify fail** — `ModuleNotFoundError: No module named 'assistant.agent'`.

- [ ] **Step 3: Implement** — `src/assistant/agent.py`:
```python
from assistant.command_gen import propose


class Agent:
    """Coordinates: fetch telemetry context -> LLM proposes -> (caller confirms) -> execute."""

    def __init__(self, provider, client) -> None:
        self._provider = provider
        self._client = client

    async def propose(self, nl: str):
        """Return a CommandProposal / QuestionProposal / ErrorProposal for the request."""
        telemetry = await self._client.get_telemetry()
        return await propose(self._provider, nl, telemetry)

    async def execute(self, command: dict) -> dict:
        return await self._client.send_command(command)

    async def abort(self) -> dict:
        return await self._client.abort()
```

- [ ] **Step 4: Run, verify pass** — `pytest tests/assistant/test_agent.py -v` → 4 passed. Then `pytest -q` → full suite green.

- [ ] **Step 5: Commit**
```bash
git add src/assistant/agent.py tests/assistant/test_agent.py
git commit -m "feat(m2.5): assistant agent loop (telemetry context -> propose -> execute)"
```

---

## Task M2.6: CLI entrypoint + live end-to-end

**Files:**
- Create: `src/assistant/__main__.py`

- [ ] **Step 1: Implement the CLI** — `src/assistant/__main__.py`:
```python
import asyncio
from assistant.config import AssistantSettings
from assistant.llm import OpenRouterProvider
from assistant.safety_client import SafetyClient
from assistant.agent import Agent
from assistant.command_gen import CommandProposal, QuestionProposal, ErrorProposal


async def run() -> None:
    settings = AssistantSettings()
    if not settings.openrouter_api_key:
        raise SystemExit("Set AS_OPENROUTER_API_KEY in .env")
    client = SafetyClient(settings.safety_url)
    await client.connect()
    agent = Agent(OpenRouterProvider.from_settings(settings), client)
    print(f"Assistant ready (model={settings.model}). Type a request, 'abort', or 'quit'.")
    try:
        while True:
            nl = (await asyncio.to_thread(input, "> ")).strip()
            if not nl:
                continue
            if nl in ("quit", "exit"):
                break
            if nl == "abort":
                print(await agent.abort())
                continue
            proposal = await agent.propose(nl)
            if isinstance(proposal, QuestionProposal):
                print(f"[assistant asks] {proposal.question}")
            elif isinstance(proposal, ErrorProposal):
                print(f"[error] {proposal.reason}")
            elif isinstance(proposal, CommandProposal):
                print(f"[proposed command] {proposal.command}")
                ok = (await asyncio.to_thread(input, "execute? [y/N] ")).strip().lower()
                if ok == "y":
                    print(await agent.execute(proposal.command))
                else:
                    print("cancelled")
    finally:
        await client.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it imports** — `python -c "import assistant.__main__"` → no error. (Do NOT run `main()` without a key + running service.)

- [ ] **Step 3: Commit**
```bash
git add src/assistant/__main__.py
git commit -m "feat(m2.6): assistant CLI entrypoint"
```

- [ ] **Step 4: LIVE end-to-end (manual, needs OpenRouter key + M1 service + SITL)** — controller-run, not a subagent step:
  1. PX4 SITL running; `AS_OPENROUTER_API_KEY` in `.env`; geofence set via `FS_GEOFENCE`.
  2. Terminal A: `python -m flight_safety` (connects to SITL).
  3. Terminal B: `python -m assistant`. Try: "take off to 5 meters" (→ arm_takeoff proposal → y → executes), "orbit here at 20 meters radius 15" , "return home", "abort".
  4. Confirm proposals match intent, the gate rejects an out-of-bounds request, and commands fly the drone.

---

## Definition of Done (M2)
- `pytest -q` green (unit), including the new `assistant` tests; `python -m assistant` runs a CLI that turns NL into validated commands, asks when ambiguous, confirms before executing, and reports results.
- The assistant is model-agnostic (swap `AS_MODEL` to any OpenRouter model; the structured-output path doesn't depend on tool-calling).
- Live end-to-end verified against SITL (M2.6 step 4).
- Next: **M3** (FPV web dashboard: video + HUD + chat + ABORT, and the real-time telemetry stream).

## Self-review notes
- Spec coverage: model-agnostic provider (§4.2), constrained structured output (§4.2), agent loop with confirm (§4.2/§7 data flow), talks to M1 validated API (§3). Telemetry: snapshot-on-demand now; real-time stream explicitly deferred to M3 (design decision, recorded in docs/M1-followups.md).
- Type consistency: `propose()` returns `CommandProposal | QuestionProposal | ErrorProposal`; `Agent.propose` passes them through; CLI matches all three. `parse_command` (from `flight_safety.models`) is the single validation authority, reused — the assistant never re-defines the schema.
- Known deferrals for M3: real-time telemetry/HUD stream, voice I/O, Turkish, `takeover`/`handback` true OFFBOARD/manual wiring (tracked in docs/M1-followups.md).
