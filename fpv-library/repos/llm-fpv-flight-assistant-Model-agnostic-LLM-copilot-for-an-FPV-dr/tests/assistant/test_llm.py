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
