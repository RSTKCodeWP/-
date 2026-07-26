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
        '{"action":"command","command":{"verb":"orbit","radius":-5,"alt":25}}',
        '{"action":"command","command":{"verb":"orbit","radius":30,"alt":25}}',
    ])
    out = await propose(p, "orbit", TLM)
    assert isinstance(out, CommandProposal) and out.command["radius"] == 30
    assert len(p.calls) == 2


@pytest.mark.asyncio
async def test_persistently_invalid_returns_error():
    p = FakeProvider(['not json', 'still not json'])
    out = await propose(p, "do something", TLM)
    assert isinstance(out, ErrorProposal)
    assert len(p.calls) == 2
