import inspect

from assistant.command_gen import propose, propose_stream


class Agent:
    """Coordinates: fetch telemetry context -> LLM proposes -> (caller confirms) -> execute."""

    def __init__(self, provider, client) -> None:
        self._provider = provider
        self._client = client

    async def _telemetry(self) -> dict:
        """Prefer the client's cached telemetry; fall back to a live fetch (cuts latency)."""
        return getattr(self._client, "last_telemetry", None) or await self._client.get_telemetry()

    async def propose(self, nl: str):
        """Return a CommandProposal / QuestionProposal / ErrorProposal for the request."""
        telemetry = await self._telemetry()
        return await propose(self._provider, nl, telemetry)

    async def propose_stream(self, nl: str, on_delta):
        """Stream prose deltas via on_delta (sync or async); return the parsed proposal."""
        telemetry = await self._telemetry()

        async def _emit(kind, text):
            r = on_delta(kind, text)
            if inspect.isawaitable(r):
                await r

        return await propose_stream(self._provider, nl, telemetry, _emit)

    async def execute(self, command: dict) -> dict:
        return await self._client.send_command(command)

    async def abort(self) -> dict:
        return await self._client.abort()
