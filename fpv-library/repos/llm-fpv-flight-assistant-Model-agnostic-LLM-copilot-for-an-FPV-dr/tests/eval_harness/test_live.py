"""Live smoke: exercises the real OpenRouter call + full scoring path.
Deselected by default (needs AS_OPENROUTER_API_KEY). Run: pytest -m integration."""
import pytest
from assistant.config import AssistantSettings
from assistant.llm import OpenRouterProvider
from eval_harness.cases import load_cases
from eval_harness.runner import run_case
from eval_harness.scoring import score_case


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_one_case_runs_end_to_end():
    settings = AssistantSettings()
    if not settings.openrouter_api_key:
        pytest.skip("no AS_OPENROUTER_API_KEY")
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openrouter_api_key, base_url=settings.base_url)
    provider = OpenRouterProvider(model=settings.model, client=client)

    cases = load_cases("evals/cases")
    happy = next(c for c in cases if c.category == "happy_path")
    res = await run_case(provider, happy)
    score = score_case(happy, res)

    # We assert the PATH ran, not a quality threshold (model quality varies).
    assert res.proposal_kind in ("command", "question", "error")
    assert res.latency_s >= 0.0
    assert res.attempts >= 1
    assert isinstance(score.passed, bool)
