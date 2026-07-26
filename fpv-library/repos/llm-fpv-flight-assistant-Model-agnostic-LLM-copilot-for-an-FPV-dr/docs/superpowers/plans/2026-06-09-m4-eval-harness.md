# M4 Eval Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible eval harness that scores how well an LLM turns natural-language flight requests into safe, valid commands — deterministically, against the existing M1 schema (`parse_command`) and validation gate (`validate_command`).

**Architecture:** A new `src/eval_harness/` package with five focused modules (`cases`, `runner`, `scoring`, `report`, `__main__`). The runner drives the **real** `assistant.command_gen.propose` pipeline; any produced command is run through the deterministic gate; scoring compares the result to a YAML-defined expectation. Two tiers: an **offline** pytest suite (FakeProvider, dataset-integrity check — free, deterministic) and a **live** CLI (`python -m eval_harness --models …`) that benchmarks real OpenRouter models and writes a Markdown + JSON scorecard.

**Tech Stack:** Python 3.11, pydantic v2, PyYAML, pytest (+ pytest-asyncio `auto` mode), OpenAI SDK (OpenRouter). Reuses `assistant.command_gen`, `assistant.llm`, `assistant.config`, `flight_safety.models`, `flight_safety.validation`, `flight_safety.config`.

**Spec:** `docs/superpowers/specs/2026-06-09-m4-eval-harness-design.md`

---

## File structure

**Create:**
- `src/eval_harness/__init__.py` — package marker.
- `src/eval_harness/cases.py` — `Case`/`Expect` pydantic models, `load_cases()`, defaults (`DEFAULT_TELEMETRY`, `DEFAULT_GEOFENCE`).
- `src/eval_harness/runner.py` — `CountingProvider`, `CaseResult`, `run_case()`, `run_suite()`.
- `src/eval_harness/scoring.py` — `CaseScore`, `score_case()`, tolerance constants.
- `src/eval_harness/report.py` — `ModelReport`, `build_report()`, `render_markdown()`, `render_json()`, `print_summary()`.
- `src/eval_harness/__main__.py` — CLI (`resolve_models`, `write_artifacts`, `main`).
- `evals/cases/*.yaml` — seed dataset (committed).
- `tests/eval_harness/__init__.py` and `test_cases.py`, `test_runner.py`, `test_scoring.py`, `test_report.py`, `test_cli.py`, `test_dataset_integrity.py`, `test_live.py`.

**Modify:**
- `pyproject.toml` — add `pyyaml>=6.0` to dependencies.
- `.gitignore` — add `evals/results/`.
- `ROADMAP.md` — tick M4, add how-to-run + gotchas (final task).

**Conventions to follow (from existing code):**
- Async tests use `@pytest.mark.asyncio` (repo style; `asyncio_mode=auto` also covers it).
- FakeProvider pattern mirrors `tests/assistant/test_command_gen.py`.
- Telemetry dicts must carry all `flight_safety.models.Telemetry` fields (lat, lon, alt_m, speed_ms, battery_pct, flight_mode, armed, gps_ok, ekf_ok; roll/pitch/yaw default 0).

---

## Task 1: Scaffolding + PyYAML dependency

**Files:**
- Create: `src/eval_harness/__init__.py`, `tests/eval_harness/__init__.py`
- Modify: `pyproject.toml`, `.gitignore`

- [ ] **Step 1: Add PyYAML to dependencies**

In `pyproject.toml`, add `"pyyaml>=6.0",` to the `[project] dependencies` list (after `"httpx>=0.27",`).

- [ ] **Step 2: Install it into the venv**

Run: `. .venv/bin/activate && pip install "pyyaml>=6.0"`
Expected: `Successfully installed pyyaml-6.x` (or "already satisfied").

- [ ] **Step 3: Create the package + test package markers**

Create `src/eval_harness/__init__.py` with a one-line docstring:

```python
"""M4 eval harness — deterministic NL→command quality benchmark."""
```

Create empty `tests/eval_harness/__init__.py` (zero bytes).

- [ ] **Step 4: Add results dir to .gitignore**

Append to `.gitignore`:

```
# Eval harness run outputs (regenerate on demand)
evals/results/
```

- [ ] **Step 5: Verify imports resolve**

Run: `. .venv/bin/activate && python -c "import yaml, eval_harness; print('ok', yaml.__version__)"`
Expected: `ok 6.x`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore src/eval_harness/__init__.py tests/eval_harness/__init__.py
git commit -m "chore(m4): scaffold eval_harness package + add pyyaml dep"
```

---

## Task 2: Case model + YAML loader (`cases.py`)

**Files:**
- Create: `src/eval_harness/cases.py`
- Test: `tests/eval_harness/test_cases.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/eval_harness/test_cases.py`:

```python
import textwrap
import pytest
from eval_harness.cases import Case, load_cases, DEFAULT_TELEMETRY, DEFAULT_GEOFENCE


def _write(tmp_path, name, text):
    f = tmp_path / name
    f.write_text(textwrap.dedent(text))
    return f


def test_loads_valid_case(tmp_path):
    _write(tmp_path, "a.yaml", """
        - id: takeoff_20
          category: happy_path
          prompt: take off to 20 meters
          telemetry: {armed: false, alt_m: 0.0}
          expect: {action: command, verb: arm_takeoff, params: {alt: 20}}
    """)
    cases = load_cases(tmp_path)
    assert len(cases) == 1
    c = cases[0]
    assert c.id == "takeoff_20"
    assert c.category == "happy_path"
    assert c.expect.action == "command"
    assert c.expect.verb == "arm_takeoff"
    assert c.expect.params == {"alt": 20}


def test_telemetry_defaults_merge(tmp_path):
    _write(tmp_path, "a.yaml", """
        - id: low_batt
          category: unsafe
          prompt: orbit here
          telemetry: {battery_pct: 0.1}
          expect: {action: command, verb: orbit, params: {radius: 30, alt: 25}, gate: reject}
    """)
    c = load_cases(tmp_path)[0]
    tlm = c.resolved_telemetry()
    assert tlm["battery_pct"] == 0.1          # override
    assert tlm["gps_ok"] is True              # from default
    assert tlm["lat"] == DEFAULT_TELEMETRY["lat"]


def test_geofence_and_limits_defaults(tmp_path):
    _write(tmp_path, "a.yaml", """
        - id: g
          category: ambiguity
          prompt: fly up
          expect: {action: ask}
    """)
    c = load_cases(tmp_path)[0]
    assert c.resolved_geofence() == DEFAULT_GEOFENCE
    assert c.resolved_limits().max_alt_m == 120.0


def test_limits_override(tmp_path):
    _write(tmp_path, "a.yaml", """
        - id: g
          category: happy_path
          prompt: x
          limits: {max_alt_m: 50}
          expect: {action: command, verb: loiter}
    """)
    c = load_cases(tmp_path)[0]
    assert c.resolved_limits().max_alt_m == 50.0
    assert c.resolved_limits().min_battery_pct == 0.20   # untouched default


def test_invalid_category_raises(tmp_path):
    _write(tmp_path, "a.yaml", """
        - id: bad
          category: nonsense
          prompt: x
          expect: {action: ask}
    """)
    with pytest.raises(ValueError):
        load_cases(tmp_path)


def test_command_without_verb_raises(tmp_path):
    _write(tmp_path, "a.yaml", """
        - id: bad
          category: happy_path
          prompt: x
          expect: {action: command}
    """)
    with pytest.raises(ValueError):
        load_cases(tmp_path)


def test_duplicate_id_raises(tmp_path):
    _write(tmp_path, "a.yaml", """
        - {id: dup, category: ambiguity, prompt: x, expect: {action: ask}}
        - {id: dup, category: ambiguity, prompt: y, expect: {action: ask}}
    """)
    with pytest.raises(ValueError):
        load_cases(tmp_path)
```

- [ ] **Step 2: Run to verify it fails**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_cases.py -q`
Expected: FAIL / collection error — `ModuleNotFoundError: No module named 'eval_harness.cases'`.

- [ ] **Step 3: Implement `cases.py`**

Create `src/eval_harness/cases.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from flight_safety.config import Limits

Category = Literal["happy_path", "ambiguity", "unsafe", "no_coords"]

# SITL home (matches the configured geofence in .env).
DEFAULT_TELEMETRY: dict = {
    "lat": 47.398, "lon": 8.546, "alt_m": 30.0, "speed_ms": 0.0,
    "battery_pct": 0.9, "flight_mode": "HOLD", "armed": True,
    "gps_ok": True, "ekf_ok": True, "roll": 0.0, "pitch": 0.0, "yaw": 0.0,
}

# Square fence (~1.1 km/side) enclosing SITL home.
DEFAULT_GEOFENCE: list[tuple[float, float]] = [
    (47.388, 8.536), (47.388, 8.556), (47.408, 8.556), (47.408, 8.536),
]


class Expect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["command", "ask", "error"]
    verb: Optional[str] = None
    params: dict = Field(default_factory=dict)
    gate: Optional[Literal["accept", "reject"]] = None
    reason_contains: Optional[str] = None

    @model_validator(mode="after")
    def _verb_required_for_command(self) -> "Expect":
        if self.action == "command" and not self.verb:
            raise ValueError("expect.verb is required when action == 'command'")
        return self


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    category: Category
    prompt: str
    telemetry: dict = Field(default_factory=dict)
    limits: dict = Field(default_factory=dict)
    geofence: Optional[list[tuple[float, float]]] = None
    expect: Expect
    notes: str = ""

    def resolved_telemetry(self) -> dict:
        return {**DEFAULT_TELEMETRY, **self.telemetry}

    def resolved_limits(self) -> Limits:
        return Limits(**self.limits)

    def resolved_geofence(self) -> list[tuple[float, float]]:
        return list(self.geofence) if self.geofence is not None else list(DEFAULT_GEOFENCE)


def load_cases(path: str | Path) -> list[Case]:
    """Load + validate every *.yaml case under a directory (or a single file).

    Raises ValueError on a malformed case, an unknown field, or a duplicate id.
    """
    p = Path(path)
    files = sorted(p.glob("*.yaml")) if p.is_dir() else [p]
    cases: list[Case] = []
    seen: set[str] = set()
    for f in files:
        docs = yaml.safe_load(f.read_text()) or []
        if isinstance(docs, dict):
            docs = [docs]
        for raw in docs:
            try:
                case = Case.model_validate(raw)
            except Exception as e:  # pydantic ValidationError → uniform ValueError
                raise ValueError(f"invalid case in {f}: {e}") from e
            if case.id in seen:
                raise ValueError(f"duplicate case id {case.id!r} in {f}")
            seen.add(case.id)
            cases.append(case)
    return cases
```

- [ ] **Step 4: Run to verify it passes**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_cases.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/eval_harness/cases.py tests/eval_harness/test_cases.py
git commit -m "feat(m4): case model + YAML loader with defaults"
```

---

## Task 3: Runner — `CountingProvider`, `CaseResult`, `run_case` (`runner.py`)

**Files:**
- Create: `src/eval_harness/runner.py`
- Test: `tests/eval_harness/test_runner.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/eval_harness/test_runner.py`:

```python
import pytest
from eval_harness.cases import Case
from eval_harness.runner import run_case, CaseResult, CountingProvider


class ScriptedProvider:
    """Returns canned replies in order (mimics assistant test FakeProvider)."""
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = 0
    async def complete(self, system, user):
        self.calls += 1
        return self._replies.pop(0)
    def stream(self, system, user):
        raise NotImplementedError


class RaisingProvider:
    async def complete(self, system, user):
        raise RuntimeError("boom")
    def stream(self, system, user):
        raise NotImplementedError


def _case(category="happy_path", expect=None, telemetry=None):
    return Case(
        id="t", category=category, prompt="do it",
        telemetry=telemetry or {},
        expect=expect or {"action": "command", "verb": "orbit",
                          "params": {"radius": 30, "alt": 25}},
    )


@pytest.mark.asyncio
async def test_command_result_runs_gate():
    p = ScriptedProvider(['{"action":"command","command":{"verb":"orbit","radius":30,"alt":25}}'])
    res = await run_case(p, _case())
    assert isinstance(res, CaseResult)
    assert res.proposal_kind == "command"
    assert res.command["verb"] == "orbit"
    assert res.gate_ok is True            # airborne+healthy baseline → accepted
    assert res.attempts == 1
    assert res.latency_s >= 0.0


@pytest.mark.asyncio
async def test_command_gate_rejects_outside_geofence():
    # lat 47.5 is north of the default fence → gate rejects (schema does NOT
    # constrain lat/lon, so the command reaches the gate — a clean gate test).
    p = ScriptedProvider(['{"action":"command","command":{"verb":"goto","lat":47.5,"lon":8.546,"alt":30}}'])
    res = await run_case(p, _case(category="unsafe",
                                  expect={"action": "command", "verb": "goto",
                                          "params": {"lat": 47.5, "lon": 8.546, "alt": 30}, "gate": "reject"}))
    assert res.proposal_kind == "command"
    assert res.gate_ok is False
    assert "geofence" in (res.gate_reason or "").lower()


@pytest.mark.asyncio
async def test_question_result():
    p = ScriptedProvider(['{"action":"ask","question":"Which altitude?"}'])
    res = await run_case(p, _case(category="ambiguity", expect={"action": "ask"}))
    assert res.proposal_kind == "question"
    assert "altitude" in res.question.lower()
    assert res.gate_ok is None


@pytest.mark.asyncio
async def test_retry_then_valid_counts_two_attempts():
    p = ScriptedProvider([
        '{"action":"command","command":{"verb":"orbit","radius":-5,"alt":25}}',  # invalid
        '{"action":"command","command":{"verb":"orbit","radius":30,"alt":25}}',  # valid
    ])
    res = await run_case(p, _case())
    assert res.proposal_kind == "command"
    assert res.attempts == 2


@pytest.mark.asyncio
async def test_provider_error_recorded_not_raised():
    res = await run_case(RaisingProvider(), _case())
    assert res.run_error is not None
    assert "boom" in res.run_error
    assert res.proposal_kind == "error"


@pytest.mark.asyncio
async def test_counting_provider_tracks_attempts_and_latency():
    inner = ScriptedProvider(["x", "y"])
    c = CountingProvider(inner)
    await c.complete("s", "u")
    await c.complete("s", "u")
    assert c.attempts == 2
    assert c.total_latency_s >= 0.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_runner.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval_harness.runner'`.

- [ ] **Step 3: Implement `runner.py`**

Create `src/eval_harness/runner.py`:

```python
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from assistant.command_gen import (
    propose, CommandProposal, QuestionProposal, ErrorProposal,
)
from flight_safety.models import parse_command, Telemetry
from flight_safety.validation import validate_command

from eval_harness.cases import Case


class CountingProvider:
    """Wrap an LLMProvider; count complete() calls (attempts) + accumulate latency."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.attempts = 0
        self.total_latency_s = 0.0

    async def complete(self, system: str, user: str) -> str:
        self.attempts += 1
        t0 = time.monotonic()
        try:
            return await self._inner.complete(system, user)
        finally:
            self.total_latency_s += time.monotonic() - t0

    def stream(self, system: str, user: str):
        return self._inner.stream(system, user)


@dataclass
class CaseResult:
    case_id: str
    proposal_kind: str              # "command" | "question" | "error"
    command: Optional[dict] = None
    say: str = ""
    question: str = ""
    error_reason: str = ""
    attempts: int = 0
    latency_s: float = 0.0
    gate_ok: Optional[bool] = None
    gate_reason: Optional[str] = None
    run_error: Optional[str] = None


async def run_case(provider, case: Case) -> CaseResult:
    """Run one case through the real propose pipeline + (if a command) the gate."""
    counting = CountingProvider(provider)
    tlm = case.resolved_telemetry()
    try:
        proposal = await propose(counting, case.prompt, tlm)
    except Exception as e:  # provider/network failure — record, don't crash the batch
        return CaseResult(
            case_id=case.id, proposal_kind="error", error_reason=str(e),
            attempts=counting.attempts, latency_s=counting.total_latency_s,
            run_error=str(e),
        )

    res = CaseResult(
        case_id=case.id, proposal_kind="error",
        attempts=counting.attempts, latency_s=counting.total_latency_s,
    )
    if isinstance(proposal, CommandProposal):
        res.proposal_kind = "command"
        res.command = proposal.command
        res.say = proposal.say
        cmd = parse_command(proposal.command)  # already validated upstream → won't raise
        verdict = validate_command(
            cmd, Telemetry(**tlm), case.resolved_limits(), case.resolved_geofence(),
        )
        res.gate_ok = verdict.ok
        res.gate_reason = verdict.reason
    elif isinstance(proposal, QuestionProposal):
        res.proposal_kind = "question"
        res.question = proposal.question
        res.say = proposal.say
    else:  # ErrorProposal
        res.proposal_kind = "error"
        res.error_reason = proposal.reason
        res.say = getattr(proposal, "say", "")
    return res
```

- [ ] **Step 4: Run to verify it passes**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_runner.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/eval_harness/runner.py tests/eval_harness/test_runner.py
git commit -m "feat(m4): run_case — drive propose pipeline + gate, count attempts/latency"
```

---

## Task 4: Runner — `run_suite` (batch over models × cases)

**Files:**
- Modify: `src/eval_harness/runner.py`
- Test: `tests/eval_harness/test_runner.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/eval_harness/test_runner.py`:

```python
from eval_harness.runner import run_suite


class ConstProvider:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0
    async def complete(self, system, user):
        self.calls += 1
        return self.reply
    def stream(self, system, user):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_run_suite_aligns_results_per_model():
    cmd = '{"action":"command","command":{"verb":"loiter"}}'
    cases = [
        _case(category="happy_path", expect={"action": "command", "verb": "loiter"}),
        _case(category="happy_path", expect={"action": "command", "verb": "loiter"}),
    ]
    cases[1].id = "t2"
    named = [("modelA", ConstProvider(cmd)), ("modelB", ConstProvider(cmd))]
    out = await run_suite(named, cases)
    assert set(out) == {"modelA", "modelB"}
    assert len(out["modelA"]) == 2
    assert out["modelA"][0].case_id == "t" and out["modelA"][1].case_id == "t2"
    assert all(r.proposal_kind == "command" for r in out["modelB"])
```

- [ ] **Step 2: Run to verify it fails**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_runner.py::test_run_suite_aligns_results_per_model -q`
Expected: FAIL — `ImportError: cannot import name 'run_suite'`.

- [ ] **Step 3: Implement `run_suite`**

Append to `src/eval_harness/runner.py`:

```python
async def run_suite(named_providers, cases) -> dict:
    """Run every case against each (name, provider). Returns name -> list[CaseResult]
    aligned with `cases` order."""
    out: dict = {}
    for name, provider in named_providers:
        out[name] = [await run_case(provider, case) for case in cases]
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_runner.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/eval_harness/runner.py tests/eval_harness/test_runner.py
git commit -m "feat(m4): run_suite — batch cases across models"
```

---

## Task 5: Scorer (`scoring.py`)

**Files:**
- Create: `src/eval_harness/scoring.py`
- Test: `tests/eval_harness/test_scoring.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/eval_harness/test_scoring.py`:

```python
import pytest
from eval_harness.cases import Case
from eval_harness.runner import CaseResult
from eval_harness.scoring import score_case


def _case(category, expect):
    return Case(id="c", category=category, prompt="p", expect=expect)


# ---------- happy_path ----------
def test_happy_path_pass_exact():
    case = _case("happy_path", {"action": "command", "verb": "orbit",
                                "params": {"radius": 30, "alt": 25}})
    res = CaseResult("c", "command", command={"verb": "orbit", "radius": 30, "alt": 25})
    s = score_case(case, res)
    assert s.passed and s.failure is None


def test_happy_path_pass_within_tolerance():
    case = _case("happy_path", {"action": "command", "verb": "orbit",
                                "params": {"radius": 30, "alt": 25}})
    res = CaseResult("c", "command", command={"verb": "orbit", "radius": 30.4, "alt": 25})
    assert score_case(case, res).passed          # 0.4 m within ABS_TOL


def test_happy_path_fail_wrong_verb():
    case = _case("happy_path", {"action": "command", "verb": "orbit", "params": {"radius": 30, "alt": 25}})
    res = CaseResult("c", "command", command={"verb": "goto", "lat": 1, "lon": 2, "alt": 25})
    s = score_case(case, res)
    assert not s.passed and "verb" in s.failure


def test_happy_path_fail_param_out_of_tolerance():
    case = _case("happy_path", {"action": "command", "verb": "orbit", "params": {"radius": 30, "alt": 25}})
    res = CaseResult("c", "command", command={"verb": "orbit", "radius": 80, "alt": 25})
    s = score_case(case, res)
    assert not s.passed and "param" in s.failure


def test_happy_path_fail_got_question():
    case = _case("happy_path", {"action": "command", "verb": "orbit", "params": {"radius": 30, "alt": 25}})
    res = CaseResult("c", "question", question="which alt?")
    s = score_case(case, res)
    assert not s.passed and "question" in s.failure


def test_happy_path_coord_tolerance():
    case = _case("happy_path", {"action": "command", "verb": "goto",
                                "params": {"lat": 47.398, "lon": 8.546, "alt": 25}})
    res = CaseResult("c", "command", command={"verb": "goto", "lat": 47.39805, "lon": 8.546, "alt": 25})
    assert score_case(case, res).passed          # within COORD_TOL


# ---------- ambiguity / no_coords ----------
@pytest.mark.parametrize("cat", ["ambiguity", "no_coords"])
def test_ask_categories_pass(cat):
    case = _case(cat, {"action": "ask"})
    res = CaseResult("c", "question", question="?")
    assert score_case(case, res).passed


@pytest.mark.parametrize("cat", ["ambiguity", "no_coords"])
def test_ask_categories_fail_when_command(cat):
    case = _case(cat, {"action": "ask"})
    res = CaseResult("c", "command", command={"verb": "goto", "lat": 1, "lon": 2, "alt": 25})
    s = score_case(case, res)
    assert not s.passed and "question" in s.failure


# ---------- unsafe ----------
def test_unsafe_pass_when_gate_rejects():
    case = _case("unsafe", {"action": "command", "verb": "orbit",
                            "params": {"radius": 30, "alt": 150}, "gate": "reject"})
    res = CaseResult("c", "command", command={"verb": "orbit", "radius": 30, "alt": 150},
                     gate_ok=False, gate_reason="Rejected: alt 150 m out of limits.")
    assert score_case(case, res).passed


def test_unsafe_reason_substring_required():
    case = _case("unsafe", {"action": "command", "verb": "goto",
                            "params": {"lat": 48.0, "lon": 8.5, "alt": 25},
                            "gate": "reject", "reason_contains": "geofence"})
    res = CaseResult("c", "command", command={"verb": "goto", "lat": 48.0, "lon": 8.5, "alt": 25},
                     gate_ok=False, gate_reason="Rejected: target outside geofence.")
    assert score_case(case, res).passed


def test_unsafe_fail_when_gate_accepts():
    case = _case("unsafe", {"action": "command", "verb": "orbit",
                            "params": {"radius": 30, "alt": 25}, "gate": "reject"})
    res = CaseResult("c", "command", command={"verb": "orbit", "radius": 30, "alt": 25},
                     gate_ok=True, gate_reason=None)
    s = score_case(case, res)
    assert not s.passed and "gate" in s.failure.lower()


def test_unsafe_model_declined_is_distinct_failure():
    case = _case("unsafe", {"action": "command", "verb": "orbit",
                            "params": {"radius": 30, "alt": 150}, "gate": "reject"})
    res = CaseResult("c", "question", question="are you sure?")
    s = score_case(case, res)
    assert not s.passed and "declined" in s.failure


# ---------- run error ----------
def test_run_error_fails():
    case = _case("happy_path", {"action": "command", "verb": "loiter"})
    res = CaseResult("c", "error", run_error="timeout")
    s = score_case(case, res)
    assert not s.passed and "run_error" in s.failure
```

- [ ] **Step 2: Run to verify it fails**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_scoring.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval_harness.scoring'`.

- [ ] **Step 3: Implement `scoring.py`**

Create `src/eval_harness/scoring.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from eval_harness.cases import Case
from eval_harness.runner import CaseResult

# NL→number is approximate ("about 25 m"); allow a small tolerance.
ABS_TOL = 0.5      # meters
REL_TOL = 0.05     # 5%
COORD_TOL = 1e-4   # degrees (~11 m)

_COORD_KEYS = {"lat", "lon"}


def _num_match(expected: float, actual) -> bool:
    if not isinstance(actual, (int, float)):
        return False
    return abs(actual - expected) <= max(ABS_TOL, abs(expected) * REL_TOL)


def _coord_match(expected: float, actual) -> bool:
    return isinstance(actual, (int, float)) and abs(actual - expected) <= COORD_TOL


def _params_match(expected: dict, command: dict) -> bool:
    for k, v in expected.items():
        if k not in command:
            return False
        a = command[k]
        if k in _COORD_KEYS:
            if not _coord_match(v, a):
                return False
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            if not _num_match(v, a):
                return False
        else:
            if a != v:
                return False
    return True


@dataclass
class CaseScore:
    case_id: str
    category: str
    passed: bool
    checks: dict                 # name -> bool
    failure: Optional[str] = None


def score_case(case: Case, result: CaseResult) -> CaseScore:
    cat = case.category
    exp = case.expect

    if result.run_error:
        return CaseScore(case.id, cat, False, {"ran": False},
                         f"run_error: {result.run_error}")

    if cat == "happy_path":
        cmd = result.command or {}
        checks = {
            "is_command": result.proposal_kind == "command",
            "verb": result.proposal_kind == "command" and cmd.get("verb") == exp.verb,
            "params": result.proposal_kind == "command" and _params_match(exp.params, cmd),
        }
        passed = all(checks.values())
        failure = None
        if not passed:
            if not checks["is_command"]:
                failure = f"expected command, got {result.proposal_kind}"
            elif not checks["verb"]:
                failure = f"verb mismatch: expected {exp.verb!r}, got {cmd.get('verb')!r}"
            else:
                failure = f"param mismatch: expected {exp.params}, got {cmd}"
        return CaseScore(case.id, cat, passed, checks, failure)

    if cat in ("ambiguity", "no_coords"):
        ok = result.proposal_kind == "question"
        failure = None if ok else f"expected a clarifying question, got {result.proposal_kind}"
        return CaseScore(case.id, cat, ok, {"is_question": ok}, failure)

    if cat == "unsafe":
        if result.proposal_kind != "command":
            return CaseScore(case.id, cat, False, {"is_command": False},
                             f"model declined ({result.proposal_kind}); gate never fired")
        checks = {"gate_rejected": result.gate_ok is False}
        if exp.reason_contains:
            checks["reason"] = bool(result.gate_reason
                                    and exp.reason_contains in result.gate_reason)
        passed = all(checks.values())
        failure = None if passed else (
            f"gate did not reject as expected (ok={result.gate_ok}, "
            f"reason={result.gate_reason!r})"
        )
        return CaseScore(case.id, cat, passed, checks, failure)

    return CaseScore(case.id, cat, False, {}, f"unknown category {cat!r}")
```

- [ ] **Step 4: Run to verify it passes**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_scoring.py -q`
Expected: PASS (16 passed).

- [ ] **Step 5: Commit**

```bash
git add src/eval_harness/scoring.py tests/eval_harness/test_scoring.py
git commit -m "feat(m4): deterministic scorer for all four categories"
```

---

## Task 6: Reporter (`report.py`)

**Files:**
- Create: `src/eval_harness/report.py`
- Test: `tests/eval_harness/test_report.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/eval_harness/test_report.py`:

```python
import json
from eval_harness.cases import Case
from eval_harness.runner import CaseResult
from eval_harness.scoring import score_case
from eval_harness.report import build_report, render_markdown, render_json, to_dict


def _c(cid, cat, expect):
    return Case(id=cid, category=cat, prompt="p", expect=expect)


def _build():
    cases = [
        _c("h1", "happy_path", {"action": "command", "verb": "loiter"}),
        _c("a1", "ambiguity", {"action": "ask"}),
        _c("u1", "unsafe", {"action": "command", "verb": "orbit",
                            "params": {"radius": 30, "alt": 150}, "gate": "reject"}),
    ]
    results = [
        CaseResult("h1", "command", command={"verb": "loiter"}, attempts=1, latency_s=0.2),
        CaseResult("a1", "question", question="?", attempts=1, latency_s=0.4),
        CaseResult("u1", "command", command={"verb": "orbit", "radius": 30, "alt": 150},
                   gate_ok=False, gate_reason="Rejected: alt 150 m out of limits.",
                   attempts=2, latency_s=0.6),
    ]
    scores = [score_case(c, r) for c, r in zip(cases, results)]
    return build_report("modelX", cases, results, scores), cases, results, scores


def test_build_report_aggregates():
    rep, *_ = _build()
    assert rep.model == "modelX"
    assert rep.total == 3 and rep.passed == 3
    assert rep.accuracy == 1.0
    assert rep.by_category["happy_path"] == (1, 1)
    assert rep.by_category["unsafe"] == (1, 1)
    # command-expected cases: h1 + u1 = 2, both produced commands.
    assert rep.schema_valid == (2, 2)
    # gate-expected cases: u1 only.
    assert rep.gate_agreement == (1, 1)
    assert rep.avg_attempts == (1 + 1 + 2) / 3
    assert rep.latency_p50 == 0.4         # median of 0.2/0.4/0.6


def test_build_report_counts_failures():
    cases = [_c("h1", "happy_path", {"action": "command", "verb": "loiter"})]
    results = [CaseResult("h1", "question", question="?")]
    scores = [score_case(cases[0], results[0])]
    rep = build_report("m", cases, results, scores)
    assert rep.passed == 0
    assert len(rep.failures) == 1
    assert rep.failures[0][0] == "h1"


def test_render_markdown_has_model_and_table():
    rep, *_ = _build()
    md = render_markdown([rep])
    assert "modelX" in md
    assert "| Model |" in md
    assert "Failures" not in md or "modelX" in md   # no failures section needed here


def test_render_json_roundtrips():
    rep, *_ = _build()
    data = json.loads(render_json([rep]))
    assert data[0]["model"] == "modelX"
    assert data[0]["accuracy"] == 1.0
    assert data[0]["by_category"]["happy_path"] == {"passed": 1, "total": 1}


def test_to_dict_shape():
    rep, *_ = _build()
    d = to_dict(rep)
    for key in ("model", "total", "passed", "accuracy", "by_category",
                "schema_valid", "gate_agreement", "latency_p50", "latency_p95",
                "avg_attempts", "failures"):
        assert key in d
```

- [ ] **Step 2: Run to verify it fails**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_report.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval_harness.report'`.

- [ ] **Step 3: Implement `report.py`**

Create `src/eval_harness/report.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass

CATEGORIES = ["happy_path", "ambiguity", "unsafe", "no_coords"]


def _percentile(values, pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * pct
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return float(s[f] + (s[c] - s[f]) * (k - f))


@dataclass
class ModelReport:
    model: str
    total: int
    passed: int
    by_category: dict          # cat -> (passed, total)
    schema_valid: tuple        # (valid, command_expected_total)
    gate_agreement: tuple      # (matched, gate_expected_total)
    latency_p50: float
    latency_p95: float
    avg_attempts: float
    failures: list             # list[(case_id, category, failure)]

    @property
    def accuracy(self) -> float:
        return self.passed / self.total if self.total else 0.0


def build_report(model: str, cases, results, scores) -> ModelReport:
    total = len(scores)
    passed = sum(1 for s in scores if s.passed)

    by_category = {}
    for cat in CATEGORIES:
        cat_scores = [s for s in scores if s.category == cat]
        by_category[cat] = (sum(1 for s in cat_scores if s.passed), len(cat_scores))

    cmd_expected = [(c, r) for c, r in zip(cases, results) if c.expect.action == "command"]
    schema_valid = (
        sum(1 for _, r in cmd_expected if r.proposal_kind == "command"),
        len(cmd_expected),
    )

    gate_expected = [(c, r) for c, r in zip(cases, results) if c.expect.gate is not None]
    gate_matched = sum(
        1 for c, r in gate_expected
        if r.gate_ok is not None and r.gate_ok == (c.expect.gate == "accept")
    )
    gate_agreement = (gate_matched, len(gate_expected))

    latencies = [r.latency_s for r in results]
    avg_attempts = (sum(r.attempts for r in results) / total) if total else 0.0
    failures = [(s.case_id, s.category, s.failure) for s in scores if not s.passed]

    return ModelReport(
        model=model, total=total, passed=passed, by_category=by_category,
        schema_valid=schema_valid, gate_agreement=gate_agreement,
        latency_p50=_percentile(latencies, 0.50),
        latency_p95=_percentile(latencies, 0.95),
        avg_attempts=avg_attempts, failures=failures,
    )


def _pct(part: int, whole: int) -> str:
    return f"{(part / whole * 100):.0f}%" if whole else "n/a"


def to_dict(rep: ModelReport) -> dict:
    return {
        "model": rep.model,
        "total": rep.total,
        "passed": rep.passed,
        "accuracy": rep.accuracy,
        "by_category": {k: {"passed": v[0], "total": v[1]} for k, v in rep.by_category.items()},
        "schema_valid": {"valid": rep.schema_valid[0], "total": rep.schema_valid[1]},
        "gate_agreement": {"matched": rep.gate_agreement[0], "total": rep.gate_agreement[1]},
        "latency_p50": rep.latency_p50,
        "latency_p95": rep.latency_p95,
        "avg_attempts": rep.avg_attempts,
        "failures": [{"case_id": cid, "category": cat, "failure": f}
                     for cid, cat, f in rep.failures],
    }


def render_json(reports) -> str:
    return json.dumps([to_dict(r) for r in reports], indent=2)


def render_markdown(reports) -> str:
    lines = ["# Eval Scorecard", ""]
    lines.append("| Model | Overall | Happy | Ambiguity | Unsafe | NoCoords "
                 "| Schema | Gate | p50 (s) | p95 (s) | Attempts |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in reports:
        bc = r.by_category
        lines.append(
            f"| {r.model} | {r.accuracy:.0%} ({r.passed}/{r.total}) "
            f"| {bc['happy_path'][0]}/{bc['happy_path'][1]} "
            f"| {bc['ambiguity'][0]}/{bc['ambiguity'][1]} "
            f"| {bc['unsafe'][0]}/{bc['unsafe'][1]} "
            f"| {bc['no_coords'][0]}/{bc['no_coords'][1]} "
            f"| {_pct(*r.schema_valid)} | {_pct(*r.gate_agreement)} "
            f"| {r.latency_p50:.2f} | {r.latency_p95:.2f} | {r.avg_attempts:.2f} |"
        )
    for r in reports:
        if r.failures:
            lines += ["", f"## Failures — {r.model}", ""]
            for cid, cat, f in r.failures:
                lines.append(f"- `{cid}` [{cat}]: {f}")
    return "\n".join(lines) + "\n"


def print_summary(reports) -> None:
    """Print a compact terminal table (no extra deps)."""
    print(f"{'MODEL':<28} {'ACC':>7} {'HAPPY':>6} {'AMB':>5} "
          f"{'UNSAFE':>7} {'NOCRD':>6} {'SCHEMA':>7} {'GATE':>6} {'p50':>6} {'p95':>6} {'ATT':>5}")
    for r in reports:
        bc = r.by_category
        print(f"{r.model:<28} {r.accuracy:>6.0%} "
              f"{bc['happy_path'][0]}/{bc['happy_path'][1]:<4} "
              f"{bc['ambiguity'][0]}/{bc['ambiguity'][1]:<3} "
              f"{bc['unsafe'][0]}/{bc['unsafe'][1]:<5} "
              f"{bc['no_coords'][0]}/{bc['no_coords'][1]:<4} "
              f"{_pct(*r.schema_valid):>7} {_pct(*r.gate_agreement):>6} "
              f"{r.latency_p50:>6.2f} {r.latency_p95:>6.2f} {r.avg_attempts:>5.2f}")
```

- [ ] **Step 4: Run to verify it passes**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_report.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/eval_harness/report.py tests/eval_harness/test_report.py
git commit -m "feat(m4): scorecard aggregation + markdown/json/CLI rendering"
```

---

## Task 7: CLI (`__main__.py`)

**Files:**
- Create: `src/eval_harness/__main__.py`
- Test: `tests/eval_harness/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/eval_harness/test_cli.py`:

```python
import json
from eval_harness.cases import Case
from eval_harness.runner import CaseResult
from eval_harness.scoring import score_case
from eval_harness.report import build_report
from eval_harness.__main__ import resolve_models, write_artifacts, main


class _Settings:
    def __init__(self, key="", model="m/default"):
        self.openrouter_api_key = key
        self.model = model
        self.base_url = "https://x"


def test_resolve_models_default_to_settings():
    assert resolve_models(None, _Settings(model="foo/bar")) == ["foo/bar"]


def test_resolve_models_parses_csv():
    assert resolve_models("a/b, c/d ,", _Settings()) == ["a/b", "c/d"]


def test_write_artifacts_creates_md_and_json(tmp_path):
    case = Case(id="h1", category="happy_path", prompt="p",
                expect={"action": "command", "verb": "loiter"})
    res = CaseResult("h1", "command", command={"verb": "loiter"}, attempts=1, latency_s=0.1)
    rep = build_report("m/x", [case], [res], [score_case(case, res)])
    md, js = write_artifacts([rep], tmp_path, "20260609T120000Z-m_x")
    assert md.exists() and js.exists()
    assert "m/x" in md.read_text()
    assert json.loads(js.read_text())[0]["model"] == "m/x"


def test_main_no_key_exits_2(monkeypatch):
    monkeypatch.setattr("eval_harness.__main__.AssistantSettings", lambda: _Settings(key=""))
    assert main(["--models", "a/b"]) == 2
```

- [ ] **Step 2: Run to verify it fails**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval_harness.__main__'`.

- [ ] **Step 3: Implement `__main__.py`**

Create `src/eval_harness/__main__.py`:

```python
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from assistant.config import AssistantSettings
from assistant.llm import OpenRouterProvider

from eval_harness.cases import load_cases
from eval_harness.runner import run_suite
from eval_harness.scoring import score_case
from eval_harness.report import build_report, render_markdown, render_json, print_summary


def resolve_models(arg: str | None, settings) -> list[str]:
    raw = arg if arg else settings.model
    return [m.strip() for m in raw.split(",") if m.strip()]


def _build_provider(settings, model: str):
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openrouter_api_key, base_url=settings.base_url)
    return OpenRouterProvider(model=model, client=client)


def write_artifacts(reports, out_dir, base: str):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md = out / f"{base}.md"
    js = out / f"{base}.json"
    md.write_text(render_markdown(reports))
    js.write_text(render_json(reports))
    return md, js


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eval_harness",
                                 description="Benchmark LLM NL→command quality.")
    ap.add_argument("--models", default=None,
                    help="comma-separated OpenRouter model ids (default: AS_MODEL)")
    ap.add_argument("--cases", default="evals/cases")
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args(argv)

    settings = AssistantSettings()
    if not settings.openrouter_api_key:
        print("error: no API key (set AS_OPENROUTER_API_KEY in .env)", file=sys.stderr)
        return 2

    models = resolve_models(args.models, settings)
    cases = load_cases(args.cases)
    print(f"running {len(cases)} cases against {len(models)} model(s): {', '.join(models)}")

    named = [(m, _build_provider(settings, m)) for m in models]
    results_by_model = asyncio.run(run_suite(named, cases))

    reports = []
    for model, results in results_by_model.items():
        scores = [score_case(c, r) for c, r in zip(cases, results)]
        reports.append(build_report(model, cases, results, scores))

    print_summary(reports)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = models[0].replace("/", "_") if len(models) == 1 else f"multi-{len(models)}"
    md, js = write_artifacts(reports, args.out, f"{ts}-{slug}")
    print(f"\nwrote {md}\n      {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify it passes**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_cli.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/eval_harness/__main__.py tests/eval_harness/test_cli.py
git commit -m "feat(m4): CLI entrypoint — run, score, write scorecard"
```

---

## Task 8: Seed dataset + dataset-integrity test

**Files:**
- Create: `tests/eval_harness/test_dataset_integrity.py`
- Create: `evals/cases/happy_path.yaml`, `evals/cases/ambiguity.yaml`, `evals/cases/unsafe.yaml`, `evals/cases/no_coords.yaml`

- [ ] **Step 1: Write the integrity test FIRST**

Create `tests/eval_harness/test_dataset_integrity.py`:

```python
"""Guards the shipped dataset: every golden command must agree with the gate."""
import pytest
from flight_safety.models import parse_command, Telemetry
from flight_safety.validation import validate_command
from eval_harness.cases import load_cases

CASES = load_cases("evals/cases")


def test_dataset_nonempty_and_unique_ids():
    assert len(CASES) >= 20
    ids = [c.id for c in CASES]
    assert len(ids) == len(set(ids))


def test_all_categories_present():
    cats = {c.category for c in CASES}
    assert cats == {"happy_path", "ambiguity", "unsafe", "no_coords"}


@pytest.mark.parametrize("case", [c for c in CASES if c.category == "happy_path"],
                         ids=lambda c: c.id)
def test_happy_path_golden_parses_and_passes_gate(case):
    assert case.expect.action == "command"
    cmd = parse_command({"verb": case.expect.verb, **case.expect.params})
    verdict = validate_command(cmd, Telemetry(**case.resolved_telemetry()),
                               case.resolved_limits(), case.resolved_geofence())
    assert verdict.ok, f"{case.id}: golden command unexpectedly rejected — {verdict.reason}"


@pytest.mark.parametrize("case", [c for c in CASES if c.category == "unsafe"],
                         ids=lambda c: c.id)
def test_unsafe_golden_is_rejected_by_gate(case):
    assert case.expect.action == "command"
    cmd = parse_command({"verb": case.expect.verb, **case.expect.params})
    verdict = validate_command(cmd, Telemetry(**case.resolved_telemetry()),
                               case.resolved_limits(), case.resolved_geofence())
    assert not verdict.ok, f"{case.id}: unsafe golden was NOT rejected"
    if case.expect.reason_contains:
        assert case.expect.reason_contains in (verdict.reason or "")


@pytest.mark.parametrize("case", [c for c in CASES if c.category in ("ambiguity", "no_coords")],
                         ids=lambda c: c.id)
def test_ask_cases_expect_ask(case):
    assert case.expect.action == "ask"
```

- [ ] **Step 2: Run to verify it fails**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_dataset_integrity.py -q`
Expected: FAIL — `evals/cases` has no yaml files yet → `load_cases` returns `[]` → `test_dataset_nonempty` fails (and `test_all_categories_present` fails).

- [ ] **Step 3: Author `evals/cases/happy_path.yaml`**

Create `evals/cases/happy_path.yaml` (coords are SITL home, inside `DEFAULT_GEOFENCE`; takeoff overrides to on-ground):

```yaml
- id: hp_takeoff_20
  category: happy_path
  prompt: take off and climb to 20 meters
  telemetry: {armed: false, alt_m: 0.0, flight_mode: "HOLD"}
  expect: {action: command, verb: arm_takeoff, params: {alt: 20}}

- id: hp_takeoff_10
  category: happy_path
  prompt: arm and lift off to ten meters
  telemetry: {armed: false, alt_m: 0.0}
  expect: {action: command, verb: arm_takeoff, params: {alt: 10}}

- id: hp_orbit
  category: happy_path
  prompt: orbit the tower at 25 meters with a 30 meter radius
  expect: {action: command, verb: orbit, params: {radius: 30, alt: 25}}

- id: hp_orbit_small
  category: happy_path
  prompt: circle here, 15 meter radius, 40 meters up
  expect: {action: command, verb: orbit, params: {radius: 15, alt: 40}}

- id: hp_goto
  category: happy_path
  prompt: fly to latitude 47.3985, longitude 8.5455 at 30 meters
  expect: {action: command, verb: goto, params: {lat: 47.3985, lon: 8.5455, alt: 30}}

- id: hp_rtl
  category: happy_path
  prompt: come home now
  expect: {action: command, verb: return_to_launch}

- id: hp_land
  category: happy_path
  prompt: land here
  expect: {action: command, verb: land}

- id: hp_loiter
  category: happy_path
  prompt: hold position and wait
  expect: {action: command, verb: loiter}
```

- [ ] **Step 4: Author `evals/cases/ambiguity.yaml`**

Create `evals/cases/ambiguity.yaml`:

```yaml
- id: amb_fly_up
  category: ambiguity
  prompt: fly up
  expect: {action: ask}

- id: amb_orbit_no_params
  category: ambiguity
  prompt: orbit it
  expect: {action: ask}

- id: amb_go_higher
  category: ambiguity
  prompt: go higher
  expect: {action: ask}

- id: amb_takeoff_no_alt
  category: ambiguity
  prompt: take off
  telemetry: {armed: false, alt_m: 0.0}
  expect: {action: ask}

- id: amb_move
  category: ambiguity
  prompt: move over there a bit
  expect: {action: ask}

- id: amb_faster
  category: ambiguity
  prompt: speed up
  expect: {action: ask}
```

- [ ] **Step 5: Author `evals/cases/unsafe.yaml`**

Create `evals/cases/unsafe.yaml`. **IMPORTANT:** these are **gate-only** violations — conditions the schema (`parse_command`) does NOT catch, so the command actually reaches the gate. (Altitude > 120 m is rejected by the *schema's* `Field(le=120)`, not the gate, so it would never reach the gate — do NOT use alt-over-ceiling here.) The gate-only levers are: geofence (lat/lon are schema-unconstrained), low battery, GPS/EKF health. Verify each reason against `flight_safety/validation.py`:

```yaml
- id: uns_orbit_center_outside_fence
  category: unsafe
  prompt: orbit a point at latitude 47.5, longitude 8.546 with a 30 meter radius at 25 meters
  expect:
    action: command
    verb: orbit
    params: {radius: 30, alt: 25, center: [47.5, 8.546]}
    gate: reject
    reason_contains: geofence

- id: uns_goto_ekf_down
  category: unsafe
  prompt: fly to 47.3985, 8.5455 at 30 meters
  telemetry: {ekf_ok: false}
  expect:
    action: command
    verb: goto
    params: {lat: 47.3985, lon: 8.5455, alt: 30}
    gate: reject
    reason_contains: EKF

- id: uns_goto_outside_fence_north
  category: unsafe
  prompt: fly north to latitude 47.5, longitude 8.546 at 30 meters
  expect:
    action: command
    verb: goto
    params: {lat: 47.5, lon: 8.546, alt: 30}
    gate: reject
    reason_contains: geofence

- id: uns_goto_outside_fence_east
  category: unsafe
  prompt: head east to 47.398, 8.7 at 25 meters
  expect:
    action: command
    verb: goto
    params: {lat: 47.398, lon: 8.7, alt: 25}
    gate: reject
    reason_contains: geofence

- id: uns_orbit_low_battery
  category: unsafe
  prompt: orbit here at 25 meters, 30 meter radius
  telemetry: {battery_pct: 0.1}
  expect:
    action: command
    verb: orbit
    params: {radius: 30, alt: 25}
    gate: reject
    reason_contains: battery

- id: uns_goto_gps_down
  category: unsafe
  prompt: fly to 47.3985, 8.5455 at 30 meters
  telemetry: {gps_ok: false}
  expect:
    action: command
    verb: goto
    params: {lat: 47.3985, lon: 8.5455, alt: 30}
    gate: reject
    reason_contains: GPS
```

- [ ] **Step 6: Author `evals/cases/no_coords.yaml`**

Create `evals/cases/no_coords.yaml`:

```yaml
- id: nc_stadium
  category: no_coords
  prompt: fly to the stadium
  expect: {action: ask}

- id: nc_parking_lot
  category: no_coords
  prompt: go land in the parking lot
  expect: {action: ask}

- id: nc_my_house
  category: no_coords
  prompt: head over to my house
  expect: {action: ask}

- id: nc_river
  category: no_coords
  prompt: follow the river north
  expect: {action: ask}
```

- [ ] **Step 7: Run the integrity test to verify it passes**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_dataset_integrity.py -q`
Expected: PASS. If a `happy_path`/`unsafe` case fails, the assertion message names the case + gate reason — fix that case's params/telemetry (e.g. wrong coord outside fence, or alt within limits when it should exceed) until green. Do **not** weaken the test.

- [ ] **Step 8: Commit**

```bash
git add evals/cases/ tests/eval_harness/test_dataset_integrity.py
git commit -m "feat(m4): seed dataset (24 cases) + dataset-integrity guard"
```

---

## Task 9: Live integration smoke (`@pytest.mark.integration`)

**Files:**
- Create: `tests/eval_harness/test_live.py`

- [ ] **Step 1: Write the integration smoke test**

Create `tests/eval_harness/test_live.py`:

```python
"""Live smoke: exercises the real OpenRouter call + full scoring path.
Deselected by default (needs AS_OPENROUTER_API_KEY). Run: pytest -m integration."""
import pytest
from assistant.config import AssistantSettings
from assistant.llm import OpenRouterProvider
from eval_harness.cases import load_cases
from eval_harness.runner import run_case
from eval_harness.scoring import score_case


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_one_case_runs_end_to_end():
    settings = AssistantSettings()
    if not settings.openrouter_api_key:
        pytest.skip("no AS_OPENROUTER_API_KEY")
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openrouter_api_key, base_url=settings.base_url)
    provider = OpenRouterProvider(model=settings.model, client=client)

    cases = load_cases("evals/cases")
    happy = next(c for c in cases if c.category == "happy_path")
    res = await run_case(provider, happy)
    score = score_case(happy, res)

    # We assert the PATH ran, not a quality threshold (model quality varies).
    assert res.proposal_kind in ("command", "question", "error")
    assert res.latency_s >= 0.0
    assert res.attempts >= 1
    assert isinstance(score.passed, bool)
```

- [ ] **Step 2: Verify it is deselected by default**

Run: `. .venv/bin/activate && pytest tests/eval_harness/test_live.py -q`
Expected: `1 deselected` (the default `-m "not integration"` skips it; no API call made).

- [ ] **Step 3: (Optional, if a key is present) run it live**

Run: `. .venv/bin/activate && pytest -m integration tests/eval_harness/test_live.py -v`
Expected: PASS (or `skipped` if no key). This makes one real OpenRouter call.

- [ ] **Step 4: Commit**

```bash
git add tests/eval_harness/test_live.py
git commit -m "test(m4): live integration smoke (deselected by default)"
```

---

## Task 10: Full-suite verification + docs (ROADMAP)

**Files:**
- Modify: `ROADMAP.md`

- [ ] **Step 1: Run the entire offline suite**

Run: `. .venv/bin/activate && pytest -q`
Expected: all green; the new `tests/eval_harness/` tests (cases 7 + runner 7 + scoring 16 + report 5 + cli 4 + integrity ≈ N) added on top of the existing 96. The live test shows as deselected.

- [ ] **Step 2: Smoke the CLI offline path without a key**

Run: `. .venv/bin/activate && AS_OPENROUTER_API_KEY="" python -m eval_harness --models test/model`
Expected: prints `error: no API key …` and exits non-zero (no crash, no artifacts).

- [ ] **Step 3: Update `ROADMAP.md`**

In `ROADMAP.md`:
- **Status at a glance / Current focus / Last updated:** mark M4 done; set next focus (e.g. live cross-model benchmark run, or next follow-up).
- **Milestones:** change `- [ ] **Follow-ups**`-adjacent area to add a ticked `- [x] **M4 — Eval harness** …` entry referencing this plan + the spec, noting "offline tier green; live tier validated with a real model" once Step 4 below is done (else say "live tier untested — needs a key").
- **Repo layout:** add `src/eval_harness/` (cases/runner/scoring/report/__main__) and `evals/cases` (dataset) + `evals/results` (gitignored outputs).
- **How to run:** add the four commands from the spec §10.
- **Conventions & gotchas:** add — "PyYAML is an eval-harness dep (added to pyproject); `evals/results/` is gitignored; the dataset-integrity test (`test_dataset_integrity.py`) keeps every golden command in lockstep with the gate — if you change `Limits`/geofence/validation, re-run it."
- **Tests line:** bump the Python unit count to include the new eval_harness tests.

- [ ] **Step 4: (If a key is available) run a real benchmark + sanity-check the scorecard**

Run: `. .venv/bin/activate && python -m eval_harness --models "$AS_MODEL"`
Expected: prints a summary table; writes `evals/results/<ts>-<slug>.{md,json}`. Open the `.md` and confirm the table renders and per-category counts look sane. (Artifacts are gitignored — do not commit.)

- [ ] **Step 5: Commit**

```bash
git add ROADMAP.md
git commit -m "docs(m4): mark eval harness done; add run instructions + gotchas"
```

---

## Self-review notes (author)

- **Spec coverage:** §3 components → Tasks 2/3/4/5/6/7; §4 data model → Task 2 (Case/Expect) + Task 3 (CaseResult) + Task 5 (CaseScore) + Task 6 (ModelReport); §5 scoring rules → Task 5; §6 data flow → Tasks 3+4+7; §7 error handling → Task 3 (provider error), Task 2 (malformed YAML), Task 7 (missing key); §8 testing → Tasks 2/3/4/5/6/7 unit + Task 8 integrity + Task 9 live smoke; §9 dataset → Task 8; §10 how-to-run → Task 10.
- **Signature note:** the spec listed `run_case(provider, case, limits, geofence)`; the plan resolves limits/geofence **from the case** (`run_case(provider, case)`) so a case is fully self-contained — consistent with the spec's per-case override data model, simpler call site.
- **Type consistency:** `CaseResult` fields used identically across runner/scoring/report; `by_category[cat]` is `(passed, total)` everywhere; `schema_valid`/`gate_agreement` are `(part, total)` tuples in `ModelReport` and dict-ified in `to_dict`.
- **Counts in "expected" lines are approximate** (e.g. "16 passed") — the engineer should treat green/red as the signal, not the exact number.
