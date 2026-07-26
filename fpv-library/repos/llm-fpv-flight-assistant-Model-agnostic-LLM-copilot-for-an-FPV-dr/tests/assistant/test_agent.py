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
