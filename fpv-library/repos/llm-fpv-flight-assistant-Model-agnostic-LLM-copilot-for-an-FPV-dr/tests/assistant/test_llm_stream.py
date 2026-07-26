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
