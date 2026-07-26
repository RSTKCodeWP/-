# Eval baselines

Committed **baseline scorecards** from the M4 eval harness (`python -m eval_harness`),
kept as a durable reference so future model/prompt changes can be diff'd against a known result.

- Routine benchmark runs write to `evals/results/` at the repo root, which is **gitignored**
  (nondeterministic, regenerate on demand). Files here are deliberate, dated snapshots.
- Scoring is deterministic against the M1 command schema (`parse_command`) + validation gate
  (`validate_command`). See `docs/superpowers/specs/2026-06-09-m4-eval-harness-design.md`.
- **Note:** LLM output is not perfectly reproducible even at `temperature=0`, so the overall
  pass-rate can drift a point or two between runs of the *same* model. The **safety-relevant
  columns are the stable, load-bearing ones**: `Unsafe` (gate rejects every out-of-bounds command)
  and `Gate` (gate-agreement) should stay at 100% — that's the invariant the harness guards.

## Reproduce
```bash
. .venv/bin/activate
python -m eval_harness --models "$AS_MODEL" --out docs/evals   # writes <timestamp>-<model>.{md,json}
```

## Baselines

| Date | Model | Overall | Unsafe→gate | Gate-agreement | File |
|---|---|---|---|---|---|
| 2026-06-09 | `deepseek/deepseek-v4-flash` | 92% (22/24) | 6/6 | 100% | [`2026-06-09-baseline-deepseek-v4-flash.md`](2026-06-09-baseline-deepseek-v4-flash.md) |
