from assistant.command_gen import CommandProposal, QuestionProposal, ErrorProposal


class DashboardHub:
    """Translate browser messages into Agent/SafetyClient calls; emit UI frames.

    `emit` is an async callback (one frame at a time) provided by the transport.
    Owns the authoritative control_state.
    """

    def __init__(self, agent, client) -> None:
        self._agent = agent
        self._client = client
        self._pending: dict | None = None
        self.control = "assistant"

    async def handle_chat(self, nl: str, emit) -> None:
        await emit({"type": "chat_start"})
        async def on_delta(kind, text):
            await emit({"type": "chat_delta", "kind": kind, "text": text})
        proposal = await self._agent.propose_stream(nl, on_delta)
        await emit({"type": "chat_end"})
        await self._present(proposal, emit)

    async def _present(self, proposal, emit) -> None:
        if isinstance(proposal, CommandProposal):
            self._pending = proposal.command
            await emit({"type": "proposal", "command": proposal.command, "say": proposal.say})
        elif isinstance(proposal, QuestionProposal):
            await emit({"type": "narration", "text": proposal.say or proposal.question})
        elif isinstance(proposal, ErrorProposal):
            await emit({"type": "narration", "text": f"Could not act: {proposal.reason}"})

    async def handle_quick(self, verb: str, args: dict, emit) -> None:
        self._pending = {"verb": verb, **(args or {})}
        await emit({"type": "proposal", "command": self._pending,
                    "say": f"Quick action: {verb}"})

    async def handle_confirm(self, emit) -> None:
        if self._pending is None:
            await emit({"type": "narration", "text": "Nothing to confirm."}); return
        cmd, self._pending = self._pending, None
        result = await self._agent.execute(cmd)
        await emit({"type": "result", **result})
        await emit({"type": "narration", "text": _narrate(result)})

    async def handle_cancel(self, emit) -> None:
        self._pending = None
        await emit({"type": "narration", "text": "Command cancelled."})

    async def handle_take_control(self, emit) -> None:
        result = await self._client.takeover()
        if result.get("status") == "executed":
            self.control = "manual"
            await emit({"type": "control_state", "who": "manual"})
            await emit({"type": "narration", "text": "You have manual control."})
        else:
            await emit({"type": "narration",
                        "text": f"Could not take control: {result.get('reason', 'unavailable')}"})

    async def handle_release_control(self, emit) -> None:
        result = await self._client.handback()
        if result.get("status") == "executed":
            self.control = "assistant"
            await emit({"type": "control_state", "who": "assistant"})
            await emit({"type": "narration", "text": "Control returned to assistant."})
        else:
            await emit({"type": "narration",
                        "text": f"Could not release control: {result.get('reason', 'unavailable')}"})

    async def handle_abort(self, emit) -> None:
        result = await self._agent.abort()
        self._pending = None
        self.control = "assistant"
        await emit({"type": "result", **result})
        await emit({"type": "control_state", "who": "assistant"})
        await emit({"type": "narration", "text": "ABORT — control returned to pilot."})


def _narrate(result: dict) -> str:
    status = result.get("status")
    if status == "executed":
        return f"Executed {result.get('verb', 'command')}."
    if status == "rejected":
        return f"Rejected: {result.get('reason', 'unsafe')}."
    if status == "error":
        return f"Error: {result.get('reason', 'unknown')}."
    return str(result)
