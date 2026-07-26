from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from assistant.command_gen import (
    propose, CommandProposal, QuestionProposal, ErrorProposal,
)
from flight_safety.models import parse_command, Telemetry
from flight_safety.validation import validate_command

from eval_harness.cases import Case


class CountingProvider:
    """Wrap an LLMProvider; count complete() calls (attempts) + accumulate latency."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.attempts = 0
        self.total_latency_s = 0.0

    async def complete(self, system: str, user: str) -> str:
        self.attempts += 1
        t0 = time.monotonic()
        try:
            return await self._inner.complete(system, user)
        finally:
            self.total_latency_s += time.monotonic() - t0

    def stream(self, system: str, user: str):
        return self._inner.stream(system, user)


@dataclass
class CaseResult:
    case_id: str
    proposal_kind: str              # "command" | "question" | "error"
    command: Optional[dict] = None
    say: str = ""
    question: str = ""
    error_reason: str = ""
    attempts: int = 0
    latency_s: float = 0.0
    gate_ok: Optional[bool] = None
    gate_reason: Optional[str] = None
    run_error: Optional[str] = None


async def run_case(provider, case: Case) -> CaseResult:
    """Run one case through the real propose pipeline + (if a command) the gate."""
    counting = CountingProvider(provider)
    tlm = case.resolved_telemetry()
    try:
        proposal = await propose(counting, case.prompt, tlm)
    except Exception as e:  # provider/network failure — record, don't crash the batch
        return CaseResult(
            case_id=case.id, proposal_kind="error", error_reason=str(e),
            attempts=counting.attempts, latency_s=counting.total_latency_s,
            run_error=str(e),
        )

    res = CaseResult(
        case_id=case.id, proposal_kind="error",
        attempts=counting.attempts, latency_s=counting.total_latency_s,
    )
    if isinstance(proposal, CommandProposal):
        res.proposal_kind = "command"
        res.command = proposal.command
        res.say = proposal.say
        cmd = parse_command(proposal.command)  # already validated upstream → won't raise
        verdict = validate_command(
            cmd, Telemetry(**tlm), case.resolved_limits(), case.resolved_geofence(),
        )
        res.gate_ok = verdict.ok
        res.gate_reason = verdict.reason
    elif isinstance(proposal, QuestionProposal):
        res.proposal_kind = "question"
        res.question = proposal.question
        res.say = proposal.say
    else:  # ErrorProposal
        res.proposal_kind = "error"
        res.error_reason = proposal.reason
        res.say = getattr(proposal, "say", "")
    return res


async def run_suite(named_providers, cases) -> dict:
    """Run every case against each (name, provider). Returns name -> list[CaseResult]
    aligned with `cases` order."""
    out: dict = {}
    for name, provider in named_providers:
        out[name] = [await run_case(provider, case) for case in cases]
    return out
