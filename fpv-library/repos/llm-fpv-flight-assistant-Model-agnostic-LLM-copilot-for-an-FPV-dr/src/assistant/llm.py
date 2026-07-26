from typing import Protocol


class LLMProvider(Protocol):
    async def complete(self, system: str, user: str) -> str: ...
    def stream(self, system: str, user: str): ...


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

    async def stream(self, system: str, user: str):
        """Yield {'reply': str} and/or {'thinking': str} deltas as they arrive."""
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0, stream=True)
        async for chunk in stream:
            delta = chunk.choices[0].delta
            think = getattr(delta, "reasoning_content", None)
            if think:
                yield {"thinking": think}
            if getattr(delta, "content", None):
                yield {"reply": delta.content}
