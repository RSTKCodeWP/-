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

async def test_release_failure_keeps_control():
    class _BadClient(_Client):
        async def handback(self): return {"status": "error", "reason": "link down"}
    hub = DashboardHub(_Agent(None), _BadClient())
    frames, emit = await _emit_collect()
    await hub.handle_release_control(emit)
    assert hub.control == "assistant"  # default unchanged (was never manual here)
    assert not any(f.get("type") == "control_state" for f in frames)
    assert any(f["type"] == "narration" and "Could not release" in f["text"] for f in frames)

async def test_quick_makes_proposal():
    hub = DashboardHub(_Agent(None), _Client())
    frames, emit = await _emit_collect()
    await hub.handle_quick("arm_takeoff", {"alt": 10}, emit)
    assert frames[-1]["type"] == "proposal" and frames[-1]["command"]["verb"] == "arm_takeoff"
    f2, emit2 = await _emit_collect()
    await hub.handle_confirm(emit2)
    assert any(f["type"] == "result" for f in f2)
