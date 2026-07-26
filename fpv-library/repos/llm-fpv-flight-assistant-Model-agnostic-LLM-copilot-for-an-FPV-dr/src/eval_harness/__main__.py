from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from assistant.config import AssistantSettings
from assistant.llm import OpenRouterProvider

from eval_harness.cases import load_cases
from eval_harness.runner import run_suite
from eval_harness.scoring import score_case
from eval_harness.report import build_report, render_markdown, render_json, print_summary


def resolve_models(arg: str | None, settings) -> list[str]:
    raw = arg if arg else settings.model
    return [m.strip() for m in raw.split(",") if m.strip()]


def _build_provider(settings, model: str):
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openrouter_api_key, base_url=settings.base_url)
    return OpenRouterProvider(model=model, client=client)


def write_artifacts(reports, out_dir, base: str):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md = out / f"{base}.md"
    js = out / f"{base}.json"
    md.write_text(render_markdown(reports))
    js.write_text(render_json(reports))
    return md, js


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eval_harness",
                                 description="Benchmark LLM NL→command quality.")
    ap.add_argument("--models", default=None,
                    help="comma-separated OpenRouter model ids (default: AS_MODEL)")
    ap.add_argument("--cases", default="evals/cases",
                    help="case dir or file (default: evals/cases)")
    ap.add_argument("--out", default="evals/results",
                    help="output dir for scorecard artifacts (default: evals/results)")
    args = ap.parse_args(argv)

    settings = AssistantSettings()
    if not settings.openrouter_api_key:
        print("error: no API key (set AS_OPENROUTER_API_KEY in .env)", file=sys.stderr)
        return 2

    models = resolve_models(args.models, settings)
    if not models:
        print("error: no models to run (--models was empty)", file=sys.stderr)
        return 2
    cases = load_cases(args.cases)
    print(f"running {len(cases)} cases against {len(models)} model(s): {', '.join(models)}")

    named = [(m, _build_provider(settings, m)) for m in models]
    results_by_model = asyncio.run(run_suite(named, cases))

    reports = []
    for model, results in results_by_model.items():
        scores = [score_case(c, r) for c, r in zip(cases, results)]
        reports.append(build_report(model, cases, results, scores))

    print_summary(reports)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = models[0].replace("/", "_") if len(models) == 1 else f"multi-{len(models)}"
    md, js = write_artifacts(reports, args.out, f"{ts}-{slug}")
    print(f"\nwrote {md}\n      {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
