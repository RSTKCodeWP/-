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
