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
