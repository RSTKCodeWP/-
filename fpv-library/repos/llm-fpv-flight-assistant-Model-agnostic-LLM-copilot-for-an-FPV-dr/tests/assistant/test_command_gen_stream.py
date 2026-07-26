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
